"""Read-only paper explorer plus explicit metadata scoring and live search."""
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from radar.features import history_features
from radar.ingest import normalize, request
from radar.model import predict

ROOT = Path(os.getenv("RADAR_ROOT", Path(__file__).resolve().parents[1]))
app = FastAPI(title="ResearchRadar", version="1.0.0", description="Research attention estimates with honest historical evaluation.")


@lru_cache(maxsize=3)
def load(name):
    path = ROOT / "dist" / f"{name}.json"
    if not path.exists():
        raise HTTPException(503, "Model assets are missing. Run python -m radar.cli train first.")
    return json.loads(path.read_text())


@app.middleware("http")
async def security_headers(request_obj, call_next):
    response = await call_next(request_obj)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "model_ready": (ROOT / "dist/model.json").exists()}


@app.get("/api/evaluation")
def evaluation():
    return load("evaluation")


@app.get("/api/papers")
def papers(q: str = Query("", max_length=200), year: int | None = Query(None, ge=1900, le=2100),
           split: Literal["test", "train", "calibration", "context", "all"] = "test",
           limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0), reveal: bool = False):
    rows = [r for r in load("papers") if (year is None or r["publication_year"] == year)
            and (split == "all" or r["split"] == split) and q.lower() in r["title"].lower()]
    rows.sort(key=lambda r: (-r["probability"], r["id"]))
    result = []
    for r in rows[offset:offset + limit]:
        record = dict(r)
        if not reveal:
            record.pop("outcome", None)
        result.append(record)
    return {"total": len(rows), "papers": result, "outcomes_revealed": reveal}


class PaperInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    title: str = Field(min_length=3, max_length=2000)
    author_count: int = Field(default=1, ge=0, le=10000)
    reference_count: int = Field(default=0, ge=0, le=10000)
    sampled_author_history: int = Field(default=0, ge=0, le=100000)
    sampled_reference_links: int = Field(default=0, ge=0, le=10000)


@app.post("/api/predict")
def score(paper: PaperInput):
    return {**predict(load("model"), paper.model_dump()), "target": load("model")["target"],
            "warning": "Experimental estimate from a historical sample. Not a measure of scientific quality."}


@app.get("/api/search")
def search(q: str = Query(..., min_length=2, max_length=150), year: int = Query(2026, ge=2023, le=2100)):
    try:
        data = request({"search": q, "filter": f"publication_year:{year},primary_topic.subfield.id:1702,type:article|preprint",
                        "per_page": 20, "select": "id,doi,title,publication_date,publication_year,authorships,referenced_works,primary_topic,type"})
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None
    live = [r for w in data.get("results", []) if (r := normalize(w))]
    # Historical graph from bundled corpus; future records never count.
    corpus_path = ROOT / "data/corpus.json"
    corpus = json.loads(corpus_path.read_text()) if corpus_path.exists() else []
    known_ids = {r["id"] for r in corpus}
    history = history_features(corpus + [r for r in live if r["id"] not in known_ids])
    result = []
    for row in live:
        r = {**row, **history.get(row["id"], {})}
        result.append({**r, **predict(load("model"), r)})
    result.sort(key=lambda r: -r["probability"])
    return {"papers": result, "source": "OpenAlex live API", "warning": "Ranked within the first 20 search matches. No full-universe or current-calibration claim."}


app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="explorer")
