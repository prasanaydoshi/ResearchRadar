"""Resumable, bounded OpenAlex sampling. No API credentials are persisted."""
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.openalex.org/works"
FIELDS = "id,doi,title,publication_date,publication_year,authorships,referenced_works,counts_by_year,primary_topic,type"


def request(params, attempts=3):
    params = dict(params)
    if os.getenv("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    for attempt in range(attempts):
        try:
            req = Request(BASE_URL + "?" + urlencode(params), headers={"User-Agent": "ResearchRadar/1.0 (research metadata analysis)"})
            with urlopen(req, timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"OpenAlex returned HTTP {exc.code}; check query or API access") from None
            if attempt + 1 == attempts:
                raise RuntimeError(f"OpenAlex unavailable after {attempts} attempts (HTTP {exc.code})") from None
            delay = exc.headers.get("Retry-After", "")
            time.sleep(min(float(delay) if delay.isdigit() else 2 ** attempt, 30))
        except (URLError, TimeoutError):
            if attempt + 1 == attempts:
                raise RuntimeError("OpenAlex request timed out or network unavailable") from None
            time.sleep(2 ** attempt)


def normalize(work):
    title = (work.get("title") or "").strip()
    if not title or not work.get("publication_date") or not work.get("id"):
        return None
    authors = work.get("authorships") or []
    topic = work.get("primary_topic") or {}
    return {
        "id": work["id"], "doi": work.get("doi"), "title": title,
        "publication_date": work["publication_date"], "publication_year": work["publication_year"],
        "authors": [a.get("author", {}).get("display_name", "Unknown") for a in authors][:12],
        "author_ids": [a["author"]["id"] for a in authors if a.get("author", {}).get("id")],
        "author_count": len(authors), "reference_count": len(work.get("referenced_works") or []),
        "references": work.get("referenced_works") or [],
        "citation_years": {str(v["year"]): v["cited_by_count"] for v in work.get("counts_by_year", [])},
        "topic": topic.get("display_name", "Unclassified"),
        "subfield": (topic.get("subfield") or {}).get("display_name", "Unclassified"),
        "type": work.get("type", "unknown"),
    }


def collect(output, years, per_year=600, seed=42):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not 1 <= per_year <= 10000:
        raise ValueError("per_year must be between 1 and 10000; sample API has a finite limit")
    cache = output.parent / "raw"
    cache.mkdir(exist_ok=True)
    rows, provenance = {}, []
    for year in years:
        for page in range(1, (per_year + 99) // 100 + 1):
            params = {"filter": f"publication_year:{year},primary_topic.subfield.id:1702,type:article|preprint", "sample": per_year,
                      "seed": seed, "per_page": 100, "page": page, "select": FIELDS}
            fingerprint = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
            path = cache / f"{year}-{fingerprint}.json"
            if path.exists():
                payload = json.loads(path.read_text())
            else:
                data = request(params)
                payload = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "query": params, "data": data}
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(payload))
                tmp.replace(path)
                time.sleep(0.15)
            for w in payload["data"].get("results", []):
                row = normalize(w)
                if row:
                    rows[row["id"]] = row
            provenance.append({"query": params, "retrieved_at": payload["retrieved_at"],
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "returned": len(payload["data"].get("results", []))})
            print(f"Collected {year} page {page}: {len(rows)} unique papers", flush=True)
    ordered = sorted(rows.values(), key=lambda r: (r["publication_date"], r["id"]))
    output.write_text(json.dumps(ordered, ensure_ascii=False))
    manifest = {"source": BASE_URL, "license": "CC0 metadata", "seed": seed, "papers": len(ordered),
                "created_at": datetime.now(timezone.utc).isoformat(), "queries": provenance,
                "corpus_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "sampling": "Seeded uniform OpenAlex sample within publication year and Artificial Intelligence subfield 1702, article/preprint types; current snapshot, not an archival snapshot"}
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return ordered
