import copy
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from radar.api import app
from radar.features import history_features, make_labels, numeric
from radar.ingest import normalize
from radar.model import metrics, predict, validate_split


def row(identifier="W1", date="2020-01-01", authors=None, refs=None):
    return {"id": identifier, "title": "Learning useful representations", "publication_date": date,
            "publication_year": int(date[:4]), "author_ids": authors or ["A1"], "references": refs or [],
            "author_count": 1, "reference_count": 2, "citation_years": {"2021": 3}}


def test_future_citations_never_enter_features():
    a = row()
    b = {**a, "citation_years": {"2021": 999999}, "cited_by_count": 999999, "fwci": 5000, "target": 1}
    assert numeric(a) == numeric(b)


def test_same_day_and_future_graph_edges_do_not_leak():
    a, b, c = row("A"), row("B", refs=["A"]), row("C", "2020-02-01", refs=["A", "B"])
    results = history_features([c, b, a])
    assert results["A"]["sampled_author_history"] == 0
    assert results["B"]["sampled_reference_links"] == 0
    assert results["C"] == {"sampled_author_history": 2, "sampled_reference_links": 2}
    assert history_features([a, b]) == {k: v for k, v in results.items() if k != "C"}


def test_unmatured_and_old_outcomes_excluded():
    rows = [row(str(i), "2025-01-01") for i in range(40)]
    assert make_labels(rows, 2025)[0] == {}
    old = [row(str(i), "2000-01-01") for i in range(40)]
    assert make_labels(old, 2025)[0] == {}


def test_labels_use_next_year_not_lifetime_and_handle_ties():
    rows = [row(str(i)) for i in range(40)]
    for i, r in enumerate(rows):
        r["citation_years"] = {"2021": i // 5, "2022": 100000 - i}
    labels, cohorts = make_labels(rows, 2025)
    assert labels["39"]["target"] == 1
    assert labels["0"]["target"] == 0
    assert labels["39"]["target_citations"] == 7
    assert cohorts["2020"]["positive_rate"] == 0.125


def test_split_rejects_unavailable_training_labels():
    train = [{"target_year": 2021, "publication_year": 2020, "target": v} for v in (0, 1)]
    cal = [{"target_year": 2022, "publication_year": 2021, "target": v} for v in (0, 1)]
    test = [{"target_year": 2024, "publication_year": 2023, "target": 1}]
    with pytest.raises(ValueError, match="mature"):
        validate_split(train, cal, test)


def test_normalize_missing_title_and_optional_fields():
    assert normalize({"id": "W1", "title": None}) is None
    r = normalize({"id": "W1", "title": "A valid title", "publication_date": "2020-01-01", "publication_year": 2020})
    assert r["reference_count"] == 0
    assert r["authors"] == []


def test_metrics_perfect_ranking_and_zero_positives():
    m = metrics([1] * 20 + [0] * 80, [0.9] * 20 + [0.1] * 80)
    assert m["precision_at_20"] == 1
    assert m["lift_at_20"] == 5
    assert metrics([0, 0], [0.2, 0.3])["average_precision"] is None


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health_validation_and_hidden_outcomes(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/papers?limit=-1").status_code == 422
    assert client.post("/api/predict", json={"title": "A useful paper", "author_count": -1}).status_code == 422
    assert client.post("/api/predict", json={"title": "A useful paper", "cited_by_count": 1000}).status_code == 422
    response = client.get("/api/papers?limit=2").json()
    assert len(response["papers"]) == 2
    assert all("outcome" not in p for p in response["papers"])
    assert "outcome" in client.get("/api/papers?limit=1&reveal=true").json()["papers"][0]


def test_bundled_predictions_match_portable_model(client):
    model = json.loads((Path(__file__).parents[1] / "dist/model.json").read_text())
    rows = client.get("/api/papers?limit=20").json()["papers"]
    for r in rows:
        assert predict(model, r)["probability"] == pytest.approx(r["probability"], abs=1e-12)
        mutated = {**r, "outcome": {"target": 1}, "citation_years": {"2024": 9999}}
        assert predict(model, mutated)["probability"] == predict(model, r)["probability"]


def test_html_and_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ResearchRadar" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


def test_live_search_provider_failure_is_explicit(client, monkeypatch):
    def fail(params):
        raise RuntimeError("OpenAlex unavailable")
    monkeypatch.setattr("radar.api.request", fail)
    assert client.get("/api/search?q=learning").status_code == 502


def test_api_prediction_returns_finite_probability(client):
    result = client.post("/api/predict", json={"title": "Graph neural networks for molecular discovery", "author_count": 5, "reference_count": 30})
    assert result.status_code == 200
    assert 0 <= result.json()["probability"] <= 1
