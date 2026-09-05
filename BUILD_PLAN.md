# ResearchRadar build plan

This is project 1 of 6 requested by the owner. Work on only one project at a time.

- [x] Define the population, outcome horizon, and retrospective limitations.
- [x] Implement resumable OpenAlex collection with query provenance and hashes.
- [x] Build date-ordered author/reference graph features and citation-label isolation.
- [x] Implement chronological model training, independent calibration, and held-out evaluation.
- [x] Add a metadata baseline, title ablation, calibration plot, and paired uncertainty interval.
- [x] Build paper explorer, outcome reveal, explanations, local reading list, export, manual scoring, and live search.
- [x] Run data/model/API verification and cross-language inference checks.
- [x] Record results and reproducible setup instructions.
- [x] Publish a separate ResearchRadar repository under prasanaydoshi and verify the remote files.

## Sequential continuation

1. ResearchRadar — started September 4, 2026 in America/Toronto. Publish before starting another project.
2. FlightGuard — earliest next local day after ResearchRadar ships.
3. InspectIQ — earliest next local day after FlightGuard ships.
4. ScentCompass (working name) — earliest next local day after InspectIQ ships.
5. DiveKit (working name) — scuba-gear buying and learning app, next day after ScentCompass.
6. PilotDeck (working name) — ForeFlight-style private-pilot planning app, next day after DiveKit.

For each future project, break work into: requirements/data audit, data preparation, model/decision logic, application, tests/evaluation, documentation/reproduction, publication/read-back. Keep SHIP_STATUS.json truthful. Stop the daily task after all six are shipped. Report blockers or actual execution/usage failures; do not claim access to a usage meter.

### FlightGuard acceptance criteria
Official flight data; timezone-aware historical connection construction; clearly labeled synthetic passenger-connection outcomes; calibrated risk and disruption comparison; cancellations and overnight flight tests; temporal evaluation; app, reproducible data pipeline, CI, Docker, README, separate repository.

### InspectIQ acceptance criteria
Public restaurant-inspection history; inspection-event deduplication and strict pre-event features; temporal calibration and test split; fixed-capacity ranking evaluation with selection-bias caveat; meaningful leakage tests; app, ingestion pipeline, CI, Docker, README, separate repository.

### ScentCompass acceptance criteria
Configurable country/currency, budget, notes liked/disliked, occasions and strength; source-backed fragrance catalog; explainable ranking and comparison; normalized bottle/concentration and price-per-mL offers with source timestamps; local shortlist; retailer buy links, no automatic purchases; tests, documentation, separate repository. Use later user preferences if provided. Never invent live prices or stock.

### DiveKit acceptance criteria
Source-backed scuba equipment catalog; explain categories, fit, maintenance and manufacturer-stated compatibility; preferences and budget; compare configurations and timestamped retailer offers; shortlist and purchase links. Do not place purchases. Do not invent pressure, oxygen-compatibility or life-support specifications. Use manufacturer documentation for safety-critical claims; no decompression or dive-computer replacement. Subtasks: sources, catalog/schema, preference matching and compatibility rules, comparison/learning UI, tests, docs, publish.

### PilotDeck acceptance criteria
User explicitly clarified BUILD a ForeFlight replica, not buy one. Build an original branded ForeFlight-style responsive planning/learning app for private pilots: airport search and map, route legs, distance/time/fuel planning, weather METAR/TAF with source timestamps and age indicators, aircraft profiles, checklists and logbook. Use documented public/appropriately licensed data, original code and design; no copying proprietary code/assets/charts or claiming ForeFlight affiliation. Scope the initial release to planning/simulation, not operational navigation, certified flight readiness, official briefing or flight-plan filing. Never fabricate current aeronautical data. Subtasks: source/coverage audit, data ingestion, route/math/weather parsing, UI/persistence, edge-case and stale-data tests, documented limitations/demo, publish.

Repository visibility: public, explicitly approved by the user September 5, 2026.

Shipped September 5, 2026: https://github.com/prasanaydoshi/ResearchRadar . All 32 remote files matched the verified local build at commit `412e7c7470ee484e4fd1a29314ff4515dc0354f5`. GitHub Actions run `33988302363` passed tests, portable inference and deterministic retraining. FlightGuard is next, no earlier than September 6, 2026 Toronto time.
