"""Training, calibration, temporal audit and portable JSON inference."""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, ndcg_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from radar.features import FEATURE_NAMES, history_features, make_labels, numeric, tokens


def sigmoid(x):
    return 1 / (1 + math.exp(-max(-35, min(35, float(x)))))


def predict(bundle, row):
    counts = Counter(tokens(row["title"]))
    text_values = {term: count * bundle["idf"][term] for term, count in counts.items() if term in bundle["idf"]}
    norm = math.sqrt(sum(v * v for v in text_values.values())) or 1
    contributions = [(term, value / norm * bundle["text_weights"][term]) for term, value in text_values.items()]
    for name, value, mean, scale, coef in zip(FEATURE_NAMES, numeric(row), bundle["means"], bundle["scales"], bundle["numeric_weights"]):
        contributions.append((name, (value - mean) / scale * coef))
    logit = bundle["intercept"] + sum(v for _, v in contributions)
    probability = sigmoid(bundle["calibration"]["slope"] * logit + bundle["calibration"]["intercept"])
    effects = sorted(contributions, key=lambda pair: abs(pair[1]), reverse=True)[:6]
    return {"probability": probability, "raw_probability": sigmoid(logit),
            "contributions": [{"feature": name, "log_odds": value} for name, value in effects]}


def metrics(y, probabilities, k=20):
    y, probabilities = np.asarray(y), np.asarray(probabilities)
    k = min(k, len(y))
    order = np.argsort(-probabilities, kind="stable")[:k]
    rate = float(y.mean())
    bins = []
    for lo, hi in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
        mask = (probabilities >= lo) & ((probabilities < hi) if hi < 1 else (probabilities <= hi))
        if mask.any():
            bins.append({"n": int(mask.sum()), "predicted": float(probabilities[mask].mean()), "observed": float(y[mask].mean())})
    return {"n": len(y), "positive_rate": rate, "precision_at_20": float(y[order].mean()),
            "recall_at_20": float(y[order].sum() / max(1, y.sum())),
            "lift_at_20": float(y[order].mean() / rate) if rate else None,
            "ndcg_at_20": float(ndcg_score([y], [probabilities], k=k)) if len(y) > 1 else None,
            "average_precision": float(average_precision_score(y, probabilities)) if y.sum() else None,
            "roc_auc": float(roc_auc_score(y, probabilities)) if len(set(y)) == 2 else None,
            "brier": float(brier_score_loss(y, probabilities)),
            "ece": float(sum(b["n"] * abs(b["predicted"] - b["observed"]) for b in bins) / len(y)),
            "reliability_bins": bins}


def validate_split(train, calibration, test):
    if not train or not calibration or not test:
        raise ValueError("Training, calibration and test cohorts must all be non-empty")
    # A label for publication year Y closes on December 31 of Y+1.
    if max(r["target_year"] for r in train) >= min(r["publication_year"] for r in calibration):
        raise ValueError("Training labels were not mature before calibration predictions")
    if max(r["target_year"] for r in calibration) >= min(r["publication_year"] for r in test):
        raise ValueError("Calibration labels were not mature before test predictions")
    for group in (train, calibration):
        if len({r["target"] for r in group}) != 2:
            raise ValueError("Training and calibration each need both target classes")


def train(corpus_path, destination, observed_through=2025, train_end=2019, calibration_year=2021, test_start=2023):
    corpus_path, destination = Path(corpus_path), Path(destination)
    rows = json.loads(corpus_path.read_text())
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate work IDs in corpus")
    # Collapse DOI-identical records before any split; retain earliest publication.
    unique, seen = [], set()
    for row in sorted(rows, key=lambda r: (r["publication_date"], r["id"])):
        key = (row.get("doi") or row["id"]).lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            unique.append(row)
    rows = unique
    history = history_features(rows)
    labels, cohorts = make_labels(rows, observed_through)
    enriched = [{**r, **history[r["id"]], **labels[r["id"]]} for r in rows if r["id"] in labels]
    training = [r for r in enriched if r["publication_year"] <= train_end]
    calibration = [r for r in enriched if r["publication_year"] == calibration_year]
    test = [r for r in enriched if r["publication_year"] >= test_start]
    validate_split(training, calibration, test)
    tfidf = TfidfVectorizer(tokenizer=tokens, token_pattern=None, lowercase=False, min_df=3, max_features=6000)
    texts = tfidf.fit_transform([r["title"] for r in training])
    scaler = StandardScaler().fit([numeric(r) for r in training])

    def matrix(group):
        return hstack([tfidf.transform([r["title"] for r in group]), csr_matrix(scaler.transform([numeric(r) for r in group]))]).tocsr()

    model = LogisticRegression(C=1.0, max_iter=1500, random_state=42).fit(matrix(training), [r["target"] for r in training])
    cal = LogisticRegression(C=1.0, max_iter=1000).fit(model.decision_function(matrix(calibration)).reshape(-1, 1), [r["target"] for r in calibration])
    names = tfidf.get_feature_names_out()
    bundle = {"version": 1, "trained_at": datetime.now(timezone.utc).isoformat(),
              "model_ready_date": f"{calibration_year + 2}-01-01",
              "target": "Top decile within sampled AI publication-year cohort by citations received in the following calendar year (ties included)",
              "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
              "idf": dict(zip(names, tfidf.idf_.tolist())),
              "text_weights": dict(zip(names, model.coef_[0, :len(names)].tolist())),
              "numeric_weights": model.coef_[0, len(names):].tolist(), "feature_names": FEATURE_NAMES,
              "means": scaler.mean_.tolist(), "scales": scaler.scale_.tolist(), "intercept": float(model.intercept_[0]),
              "calibration": {"slope": float(cal.coef_[0, 0]), "intercept": float(cal.intercept_[0])}}
    test_probs = cal.predict_proba(model.decision_function(matrix(test)).reshape(-1, 1))[:, 1]
    portable_probs = np.array([predict(bundle, r)["probability"] for r in test])
    if not np.allclose(test_probs, portable_probs, atol=1e-10):
        raise AssertionError("Portable model disagrees with sklearn")
    baseline = LogisticRegression(C=1.0, max_iter=1000).fit(scaler.transform([numeric(r) for r in training]), [r["target"] for r in training])
    baseline_cal = LogisticRegression(C=1.0).fit(baseline.decision_function(scaler.transform([numeric(r) for r in calibration])).reshape(-1, 1), [r["target"] for r in calibration])
    baseline_probs = baseline_cal.predict_proba(baseline.decision_function(scaler.transform([numeric(r) for r in test])).reshape(-1, 1))[:, 1]
    text_model = LogisticRegression(C=1.0, max_iter=1000).fit(texts, [r["target"] for r in training])
    text_cal = LogisticRegression(C=1.0).fit(text_model.decision_function(tfidf.transform([r["title"] for r in calibration])).reshape(-1, 1), [r["target"] for r in calibration])
    text_probs = text_cal.predict_proba(text_model.decision_function(tfidf.transform([r["title"] for r in test])).reshape(-1, 1))[:, 1]
    y = np.array([r["target"] for r in test])
    rng = np.random.default_rng(42)
    differences = []
    for _ in range(500):
        idx = rng.integers(0, len(y), len(y))
        differences.append(float(np.mean((test_probs[idx] - y[idx]) ** 2 - (baseline_probs[idx] - y[idx]) ** 2)))
    report = {"target": bundle["target"], "model_ready_date": bundle["model_ready_date"],
              "sample_size": len(rows), "train_n": len(training), "calibration_n": len(calibration), "test_n": len(test),
              "train_years": sorted(set(r["publication_year"] for r in training)), "calibration_year": calibration_year,
              "test_years": sorted(set(r["publication_year"] for r in test)), "cohorts": cohorts,
              "full_model": metrics(y, test_probs), "metadata_baseline": metrics(y, baseline_probs),
              "title_only_ablation": metrics(y, text_probs),
              "constant_baseline": metrics(y, np.full(len(y), np.mean([r["target"] for r in training]))),
              "brier_difference_vs_metadata_bootstrap_95": np.quantile(differences, [0.025, 0.975]).tolist(),
              "bootstrap_note": "Paired paper bootstrap; exploratory interval, does not model author/topic dependence",
              "by_year": {str(year): metrics(y[np.array([r["publication_year"] == year for r in test])], test_probs[np.array([r["publication_year"] == year for r in test])]) for year in sorted(set(r["publication_year"] for r in test))},
              "limitations": ["Current metadata snapshot, not point-in-time archived records; titles/authorship/references can change after publication.",
                              "Next calendar year is a variable 12–24 month endpoint from publication, not an exact 12-month horizon.",
                              "Top-decile threshold is relative to sampled AI cohort; ties can make prevalence exceed 10%.",
                              "No citation counts, current author h-index, venue prestige or current topic labels enter model features.",
                              "Graph history reflects only sampled prior papers, not complete scholarly histories.",
                              "Citations measure attention, not scientific validity; no claim of causal impact or universal generalization.",
                              "No model selection on test results; current-paper predictions may drift and are not guaranteed calibrated."]}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "model.json").write_text(json.dumps(bundle))
    (destination / "evaluation.json").write_text(json.dumps(report, indent=2))
    test_ids = {r["id"] for r in test}
    cal_ids = {r["id"] for r in calibration}
    train_ids = {r["id"] for r in training}
    papers = []
    for row in rows:
        r = {**row, **history[row["id"]]}
        split = "test" if r["id"] in test_ids else "calibration" if r["id"] in cal_ids else "train" if r["id"] in train_ids else "context"
        record = {k: r[k] for k in ["id", "doi", "title", "publication_date", "publication_year", "authors", "author_count", "reference_count", "topic", "subfield", "sampled_author_history", "sampled_reference_links"]}
        record.update(predict(bundle, r))
        record["split"] = split
        if r["id"] in labels:
            record["outcome"] = labels[r["id"]]
        papers.append(record)
    (destination / "papers.json").write_text(json.dumps(papers, ensure_ascii=False))
    return report
