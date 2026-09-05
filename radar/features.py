"""Allowlisted input features: citation labels never enter the feature vector."""
import math
import re
from collections import Counter
import numpy as np

FEATURE_NAMES = ["log_authors", "log_references", "log_title_words", "log_sampled_author_history", "log_sampled_reference_links"]


def tokens(title):
    return re.findall(r"[a-z0-9]{2,}", title.lower())


def history_features(rows):
    """Update history only after every work with the same date is scored."""
    from itertools import groupby
    authors, known, output = Counter(), set(), {}
    for _, day in groupby(sorted(rows, key=lambda r: (r["publication_date"], r["id"])), lambda r: r["publication_date"]):
        batch = list(day)
        for r in batch:
            output[r["id"]] = {
                "sampled_author_history": sum(authors[a] for a in set(r.get("author_ids", []))),
                "sampled_reference_links": sum(ref in known for ref in set(r.get("references", []))),
            }
        for r in batch:
            authors.update(set(r.get("author_ids", [])))
            known.add(r["id"])
    return output


def numeric(row):
    values = [row.get("author_count", 0), row.get("reference_count", 0), len(tokens(row["title"])),
              row.get("sampled_author_history", 0), row.get("sampled_reference_links", 0)]
    return [math.log1p(max(0, float(v))) for v in values]


def make_labels(rows, observed_through_year, top_fraction=0.1, min_cohort=30):
    """Top decile of the sampled ML publication-year cohort, ties included.

    Horizon is citations IN the following calendar year, not lifetime citations
    or exactly twelve months after publication. Missing older citation years are
    rejected because OpenAlex retains only a rolling ten-year history.
    """
    from collections import defaultdict
    cohorts = defaultdict(list)
    for row in rows:
        target_year = row["publication_year"] + 1
        if target_year <= observed_through_year and target_year >= observed_through_year - 8:
            cohorts[row["publication_year"]].append(row)
    labels, summary = {}, {}
    for year, cohort in cohorts.items():
        if len(cohort) < min_cohort:
            continue
        citations = np.array([r.get("citation_years", {}).get(str(year + 1), 0) for r in cohort])
        threshold = max(1, int(np.quantile(citations, 1 - top_fraction, method="higher")))
        for r, count in zip(cohort, citations):
            labels[r["id"]] = {"target": int(count >= threshold), "target_citations": int(count), "threshold": threshold, "target_year": year + 1}
        summary[str(year)] = {"n": len(cohort), "threshold": threshold, "positive_rate": float((citations >= threshold).mean())}
    return labels, summary
