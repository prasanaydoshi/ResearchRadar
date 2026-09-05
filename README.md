# ResearchRadar

**Rank AI papers before their later citations are revealed, then audit what actually happened.**

ResearchRadar is a runnable research-impact experiment and paper explorer. It includes a real OpenAlex corpus, a trained and calibrated model, chronological evaluation, a browser scoring engine, a FastAPI service, and a reproducible ingestion/training pipeline. The static explorer needs no API key, paid model service, or Python dependencies.

This is a **retrospective research prototype**, not a validated predictor of scientific merit. Its strongest result is the transparent experiment: the simple metadata baseline outperforms the richer text model on this held-out sample. That finding is retained, not tuned away.

## Run in 30 seconds

From the repository root, with Python 3.11+:

```bash
python -m http.server 8000 --directory dist
```

Open **http://localhost:8000**. Historical replay, explanations, reading lists, exports, manual scoring, and the evaluation view all work in this static mode. Serve over HTTP; opening `index.html` as a `file://` URL prevents JSON loading in many browsers.

For the full API and live paper search:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m radar.cli serve
```

Open **http://localhost:8000**, or **http://localhost:8000/docs** for the API reference. The API binds to loopback by default. Run commands from the repository root; the source checkout contains the corpus and model assets. Do not treat the Python package alone as a self-contained wheel distribution.

```bash
docker build -t research-radar .
docker run --rm -p 8000:8000 research-radar
```

The Dockerfile is included; container execution must be verified in an environment with Docker. Never put secrets in an image. Set `OPENALEX_API_KEY` at runtime if your OpenAlex access requires a higher budget.

## What the app does

- **Historical replay:** select a held-out 2023 or 2024 paper cohort; rank by predicted attention; reveal citations in the following calendar year.
- **Inspectable scores:** title-token and numeric-feature contributions, paper authors, links, and observed cohort thresholds.
- **Reading workflow:** title/topic search, device-local reading list, pagination, and JSON export. Filters and year selection also apply to the reading-list view.
- **Manual scoring:** the trained model runs in JavaScript with the same weights and arithmetic as Python. Unprovided graph features default to zero.
- **Live search:** the Python server retrieves and ranks the first 20 matching OpenAlex AI papers. This is a search-result ranking, not exhaustive discovery.
- **Evidence:** training/calibration/test cohorts, baselines, a reliability chart, machine-readable metrics, and explicit limitations.

## Target and population

The target is **membership in the top citation decile of the sampled AI publication-year cohort, using citations received during the following calendar year**. For a paper published in 2023, the outcome counts citations during January–December 2024. Ties at the threshold are included; consequently the positive share can exceed 10%. Zero citations never qualify merely because a cohort is sparse.

This is **not exactly twelve months after publication**. The end of the observation window is between 12 and 24 months after publication, and publication-year citations are excluded. OpenAlex annual counts do not provide exact monthly timing. Exact 12-month prediction would require dated citation edges or suitable historical snapshots and a new evaluation.

The included corpus contains **4,799 unique real papers** sampled using seed 42, with approximately 600 articles/preprints per year, 2017–2024. The filter uses OpenAlex's **Artificial Intelligence subfield 1702**. Current taxonomy membership defines the population but is not a model feature. The corpus is not representative of every discipline, all preprints, or the full AI literature.

## Measured results

Fixed models, evaluated on **1,200 untouched papers published in 2023–2024**. Observed positive prevalence: **11.25%**. Values below are generated from the included corpus, not demo placeholders.

| Model | Precision@20 | NDCG@20 | Average precision | Brier score ↓ |
|---|---:|---:|---:|---:|
| Title + metadata + sampled graph | 55.0% | 0.630 | 0.392 | 0.0838 |
| Metadata + sampled graph baseline | **65.0%** | **0.676** | **0.400** | **0.0828** |

The richer model achieves **4.89× top-20 lift over the held-out prevalence**, but does **not** beat the simpler baseline. It is retained as the pre-specified experiment; there is no test-driven model selection. Full title-only and constant baselines, per-year metrics, calibration bins, and a paired bootstrap interval are in [`dist/evaluation.json`](dist/evaluation.json). The bootstrap resamples individual papers and does not account for author/topic dependence.

Precision@20 above pools both test years. The explorer ranks one publication-year cohort at a time, so its top-20 outcomes need not match the pooled figure. Per-year results are included in the report.

## Temporal evaluation and leakage controls

| Stage | Publication years | Outcome years | Role |
|---|---|---|---|
| Train | 2017–2019 | 2018–2020 | Fit vocabulary, feature scaling and logistic model |
| Gap/context | 2020 | Not used for fitting | Allow training labels to mature |
| Calibrate | 2021 | 2022 | Fit sigmoid calibration on separate papers |
| Gap/context | 2022 | Not used for fitting | Allow calibration labels to mature |
| Test | 2023–2024 | 2024–2025 | Evaluate the frozen model |

The resulting model can be regarded as ready on **January 1, 2023**, subject to the snapshot caveat below. Vocabulary and scaling are fit on training papers only. Graph histories count papers with strictly earlier publication dates; same-day papers cannot see one another. Context and test-period papers can enter graph history after their publication, but their outcome labels never enter model inputs or fitting. Records are deduplicated by work ID and DOI before splitting.

Allowed features: unigram title TF-IDF, log author count, log matched-reference count, log title length, log sampled prior author works, and log references linked to earlier sampled papers. No lifetime citations, future citation counts, current h-index, current FWCI, venue reputation, or topic labels enter the model.

**Important residual limitation:** this is a current metadata snapshot, not an archival snapshot of what was indexed on each prediction date. Titles, authorship, references, publication dates, and coverage can be revised. Graph counts and matched-reference counts may therefore contain retrospective coverage advantages even with date-order checks. The project does not claim a perfectly point-in-time backtest. Citation labels also reflect today's indexing of historical citations.

## Reproduce or extend

The committed normalized corpus is enough to reproduce training without network access:

```bash
python -m radar.cli train
python -m pytest -q
node tests/portable.cjs
```

To retrieve a new sample:

```bash
python -m radar.cli ingest --start 2017 --end 2024 --per-year 600 --seed 42
python -m radar.cli train
```

Requests are bounded, retried on transient errors, and cached in `data/raw/`. Interrupted collection resumes from cached pages; only after successful collection is the normalized corpus written. Query parameters, retrieval timestamps, response hashes and corpus hash are recorded in `data/corpus.manifest.json`. API keys are never persisted. A seed makes the query repeatable within a stable snapshot, not immutable as OpenAlex changes. Refreshing data changes the experiment and requires updating reported results.

Increase `--per-year` up to 10,000 for a larger sample (up to 80,000 across eight years). Respect your OpenAlex API budget; this does not purchase credits. For later observation dates, audit the rolling annual citation-history window before including older cohorts.

Dependencies are bounded in `requirements.txt`; `requirements-lock.txt` records the resolved application environment for tighter reproduction. The CI workflow runs tests, checks JavaScript scoring against Python for every bundled paper, and retrains offline to compare predictions. It does not ingest fresh data or require secrets.

## API

| Endpoint | Behavior |
|---|---|
| `GET /api/health` | Service and model availability |
| `GET /api/papers?year=2023&limit=20` | Ranked held-out papers, outcomes hidden by default |
| `GET /api/papers?year=2023&reveal=true` | Reveal later citation outcomes |
| `POST /api/predict` | Score allowlisted publication metadata |
| `GET /api/evaluation` | Full measured report |
| `GET /api/search?q=robotics&year=2026` | Retrieve and rank live OpenAlex matches |

```bash
curl http://localhost:8000/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"title":"Graph neural networks for molecular discovery","author_count":5,"reference_count":30}'
```

Inputs have size/range checks and unknown scoring fields are rejected. Untrusted paper text is inserted with `textContent`, not HTML. Paper links only accept HTTPS. The model format is JSON and never deserializes arbitrary Python objects. The service has no accounts or remote write endpoints. Before exposing the full API publicly, add deployment-level rate limiting and authentication if you use a private API budget; live search incurs requests. Fonts are optional Google Fonts with system fallbacks.

## Deployment

- Static: host `dist/` on any static host. All bundled functionality except live API search works.
- GitHub Pages: choose **GitHub Actions** in repository Pages settings, then run the manual **Publish static explorer** workflow. This publishes the demo, not the Python API. The workflow is included; it is not evidence that a deployment has occurred.
- API: use the supplied Dockerfile or run uvicorn via the CLI. The model assets are loaded once per process. Restart after retraining.

## Project map

```text
radar/ingest.py       OpenAlex sampling, cache and provenance
radar/features.py     Allowlisted features, chronological graph, labels
radar/model.py        Training, calibration, evaluation, portable inference
radar/api.py          FastAPI endpoints and static explorer
radar/cli.py          Ingest / train / serve commands
data/                Real corpus and source manifest
dist/                Static app, model, scores and measured evaluation
tests/               Leakage, API and Python/JavaScript parity checks
docs/                Data/model documentation and demo guide
```

## Data and license

[OpenAlex API reference](https://help.openalex.org/api/) · [Citation construction](https://help.openalex.org/data/works/citations/) · [OpenAlex work fields](https://docs.openalex.org/api-entities/works/work-object)

Code: MIT. OpenAlex metadata: CC0. This repository includes metadata, not paper PDFs or abstracts. Citations measure attention and can reflect popularity, age, field, access, or flawed work; they do not establish scientific validity. Read the underlying papers.
