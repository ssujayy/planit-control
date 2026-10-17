# PlanIT Control - Shared Project Instructions

Read this file before making changes. It applies to every coding assistant in this repository. Claude Code reads CLAUDE.md, which imports this file, so edit rules HERE only.

## 1. Objective and authority

Build PlanIT Control for the SwampHacks XII Sperry Tech challenge.

Core workflow: identify a site needing attention -> explain the evidence -> alert the crew -> collect a field report -> prepare tomorrow's briefing.

Optimize for a complete, reliable, understandable demonstration and legitimate challenge coverage. The starter is a foundation, not a finished safety product: inspect the current repository before assuming a planned feature exists.

When sources disagree, follow this order and name the conflict before changing any shared contract:
1. The team's latest explicit instruction (relayed by the human owner).
2. The Sperry brief (docs/brief.md) and the SwampHacks XII rules, for requirements and eligibility.
3. The repository's agreed API contract, fixtures and database schema, for implementation. [FILL IN the actual paths here once confirmed.]
4. This file, for execution guidance.

Do not silently invent a replacement architecture or a competing contract in a separate document.

## 2. Required capabilities

Implement all six in the simplest honest working form:

1. Combined environmental conditions for at least 50 distinct real power plants: weather, heat, rainfall, soil moisture, official alerts, fire evidence, and wildlife/local hazards reported by crews. Explicitly label unavailable feeds.
2. Danger alerts: a lightning hold within 10 miles with a 30-minute countdown extended by qualifying strikes, and flood-related warnings/advisories.
3. A next-day briefing delivered to an in-app supervisor inbox at 6 PM in each site's local timezone. Confirm with Sperry whether another channel is required.
4. Crew reports with photo, location, category, note, timestamp and site, available in shared site history. Wildlife is a report category.
5. A supervisor map and ranked list that explain why sites need attention.
6. An experimental 0-10 index produced by an ML model trained on historical data.

A missing feature or a replay does not count as a completed live integration. Track unresolved sponsor interpretations (section 11) instead of assuming approval.

## 3. Stack, foundation and current verified state

- Frontend: React + Vite, JavaScript. Map: preserve the existing Leaflet integration unless a change has a clear benefit.
- Backend: Flask, Python 3.11+. Use ONE Python version on every laptop. If a pinned package will not install on a very new Python (for example 3.14), move all laptops to 3.12 or 3.13 rather than loosening pins.
- Database: Tiger Data PostgreSQL through Psycopg. Keep SQL in the existing database adapter.
- Worker: one separate Python process for ingestion, briefings and predictions.
- ML: pandas + scikit-learn (see section 9). Briefings: deterministic template first; optional Gemini rewrite.
- Dependencies: backend/worker use the root requirements.txt; ML uses ml/requirements.txt. Keep both pinned. Put a new package in the right file and tell the team if it affects shared setup. Routine work within your scope does not need repeated approval.

Tiger Data is the selected shared database. Diagnose connection failures first. A switch to another database is a team architecture decision, never an automatic fallback. The existing file/demo storage mode is an explicit foundation feature; it does not prove Tiger Data integration and must not silently replace a failed database. PostgreSQL/Timescale-specific SQL needs deliberate changes if the database changes.

Verified state (Saturday Oct 17, about 3:30 PM ET) - re-check before relying on it:
- 55 distinct plants seeded into Tiger Data from the official EIA-860 2025 annual inventory. Preserve stable source identifiers and provenance. Inventory-year operating status is not verified current operating status.
- GET /api/sites returns an OBJECT, not a bare list: { as_of, count, mode, risk_status, sites: [...] }. Each site has: id, source_plant_id, source_version, name, state, county, latitude, longitude, timezone. There is no near_river or plant_type field yet. risk_status is currently "not_implemented".
- Sites span multiple timezones (for example America/Chicago and America/New_York). Scheduling and display must use each site's own timezone.
- An ML baseline exists on branch feature/ml (section 9).

Startup commands (run from the repository root; each person makes their own .venv, which is never committed):
```
python3 -m venv .venv                       # Windows: py -m venv .venv
source .venv/bin/activate                   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m scripts.seed_database             # writes to the SHARED database; confirm it is idempotent before re-running
python -m flask --app backend.app:create_app run --port 5000
cd frontend && npm install && npm run dev
```
Seed first, then start Flask. On Windows without activating, use .venv\Scripts\python.exe -m ... in place of python -m ...

## 4. Team ownership and parallel development

Four human owners work simultaneously, each using their own coding assistant:
- Frontend: dashboard, map, site detail/timeline, report form, briefing inbox.
- Backend/data: plant data, database, ingestion, shared data interfaces.
- Alerts/reports: lightning state, reporting, briefing generation and scheduling.
- ML: dataset, labels, training, evaluation, prediction export.

Assign one integration owner to coordinate shared contracts and merges.

Work on a feature branch. Before editing, pull, inspect git status and read the relevant files. Do not overwrite another person's uncommitted work. Coordinate before changing another owner's active module, shared API response shapes, the schema or shared dependencies. Use fixtures that match the agreed API contract so work continues before other modules are ready. Keep changes focused: no unrelated refactors or formatting churn.

For each handoff, report: what works; changed files; commands/checks run and their results; remaining gaps and integration needs.

Commit completed, verified steps when the human owner requests or authorizes it. Never discard work or force-push shared history without explicit authorization.

## 5. Data integrity and secrets

- The repository is PUBLIC. Never commit secrets: the Tiger Data connection string, Gemini or any provider key, or any .env file. Keep credentials in gitignored local environment files and call provider APIs from the backend/worker only. Keep .env.example to names and safe placeholders. Check staged changes for keys, connection strings and .env files before every push.
- Preserve source, observation/forecast time, retrieval time and units for stored data.
- Distinguish observations, forecasts, official warnings, modeled proxies, crew reports and replay events.
- Missing or stale data must not appear as zero risk. "No recent reports" does not mean "no hazard."
- Fire-weather warnings and satellite fire detections are different evidence.
- Open-Meteo apparent temperature is not the NWS heat index.
- Cache upstream responses and persist useful observation/forecast snapshots. Dashboard polling must read stored data, never fan out to upstream APIs. A manual weather-fetch action may remain during transition; move routine refreshes into the worker.
- Verify an actual provider response before wiring fields into ingestion. The NWS API requires a descriptive User-Agent header; confirm in its documentation.
- Credit actual data sources, libraries and AI tools in the README. Use only code written during the permitted hackathon period; do not copy implementation code from prior personal projects.

## 6. Hazard status, coverage and ranking

Track each hazard independently. Compute the presentation from those components; never use one stored flag that clears unrelated hazards.

Represent separately:
- Hazard state: STOP_WORK, ALERT, ELEVATED or NO_ACTIVE_ALERTS.
- Monitoring coverage: COMPLETE, PARTIAL, STALE or UNAVAILABLE.

Coverage refers only to configured monitoring and its documented freshness rules. It does not certify site safety. Never label a site "safe" or "all clear".

Examples:
- An active lightning hold remains STOP_WORK even if another feed is unavailable.
- A missing strike feed remains visibly unavailable after the timer expires.
- NO_ACTIVE_ALERTS means no active alerts in the available monitored evidence.

Rank active lightning holds and severe official warnings first, then other alerts/advisories and relevant unresolved reports, then model/weather signals. Show the reasons and feed coverage on each row. Make missing critical monitoring visible rather than burying it at the bottom.

Never average a lightning hold into an overall numeric score. The ML index never overrides an official warning.

## 7. Lightning and replay isolation

Use UTC internally; convert to local time only for display and scheduling. Use geographic (haversine) distance; 10 miles is about 16.09 km.

For each accepted strike:
1. Validate its identifier, coordinates, timestamp and mode.
2. Ignore duplicates within the same source/mode.
3. Find sites within 10 miles.
4. Set hold_until = max(existing hold_until, strike_time + 30 minutes).
5. Persist the resulting state.

An older delayed strike cannot shorten an existing hold. A new event extends a hold only when its calculated expiration is later. Expiration clears only the lightning hold.

Live and replay may share one processing function but must have separate state and queries. Key lightning state by (site_id, mode) and namespace event identifiers by source/mode. Replay must not modify live ranking, live alerts or live briefings. Pass mode explicitly through the replay workflow and label it visibly. Do not confuse data-storage mode (file/database) with event mode (live/replay). Use a replay session identifier to reset and restart demonstrations cleanly. Accelerated playback must use one consistent replay clock for event time, countdowns and expiration.

Write tests first:
- A strike at 9 miles triggers a hold; a strike at 11 miles does not.
- Duplicate processing is a no-op.
- An older event cannot shorten a hold; a later qualifying event extends it.
- Expiration preserves unrelated hazards.
- Stale/unavailable monitoring remains visible.
- Replay cannot change live state.

## 8. Flood, heat and fire

- Keep official flood alerts separate from rainfall-based advisories. An illustrative rainfall rule must be labeled an advisory with a documented threshold, never an official flood warning.
- Do not infer river proximity from a plant name. Document how near-river sites were identified; unknown proximity stays unknown. (A near-river field does not exist yet - see section 11.)
- Document the heat metric, units and thresholds actually used.
- Implement the minimum fire coverage the Sperry brief requires, using official fire-weather alerts and/or accessible fire detections with distinct labels. If a required layer is unavailable, disclose the gap rather than reclassifying it as optional.

## 9. ML implementation

First prove an end-to-end pipeline on a small geographic sample, then expand.

Initial model:
- Unit: county-day, avoiding duplicate rows for plants in the same county.
- Label: a reported Thunderstorm Wind, Hail, Tornado or Flash Flood event. Restrict the first join to county-based NOAA records (CZ_TYPE = C). Join on verified state/county identifiers and consistent local dates. Define multi-day event handling explicitly.
- A negative label means no selected event was reported, not proven safety.
- Features: daily weather summaries and seasonal features. Split chronologically using years actually available and sufficiently complete.
- Start with logistic regression and a simple baseline. Fit preprocessing on training data only. Select thresholds on training/validation data, never the final test set.
- Report dataset size, positive prevalence, missingness, baseline, average precision, and precision/recall at the selected threshold. Report ROC-AUC only when defined.
- Save the model, preprocessing, feature order, model version and evaluation. The UI must display actual saved model predictions.
- Index = 10 x model probability, bounded to 0-10, labeled "experimental model index". Never call it an injury probability or claim calibration without evidence.
- Historical evaluation uses observed weather; deployment uses forecast summaries. Keep feature definitions and units consistent, and document the difference.

Delivered baseline (branch feature/ml; merge through the integration owner):
- Files: ml/predict.py, ml/artifacts/model.joblib, ml/results.json, docs/ML.md, ml/requirements.txt.
- Interface:
```
from ml.predict import predict_site
result = predict_site(
    {"temperature_2m_max": <deg C>, "precipitation_sum": <mm>, "wind_gusts_10m_max": <km/h>},
    target_date="YYYY-MM-DD")
```
- Inputs must cover the ENTIRE target day in the site's local timezone. Request Open-Meteo daily forecasts with that site's IANA timezone. Never pass current readings or partial daily totals. Confirm units in docs/ML.md before wiring.
- Returns: status, model_index, probability, target_date, model_version, feature_version, computed_at, outside_training_range. Seasonal features are derived inside the function.
- Unavailable inputs return status="unavailable" with a null index. The UI shows "unavailable", never 0.
- Scope: a five-county historical baseline. Predictions elsewhere are geographic extrapolation, so the UI and briefings must show the outside_training_range label. Historical evaluation does not establish next-day forecast performance; say so wherever the model is described.
- Persist each result through the agreed predictions schema, including model_version, feature_version, computed_at and outside_training_range. If the schema lacks a column for any of these, raise it with the backend/data owner.
- Official alerts and lightning holds stay independent of the model.

## 10. Reports and briefings

Reports:
- Validate site, coordinates, category, note and uploaded image. Apply a file-size limit and verify image content.
- Persist photos and metadata in the agreed storage design. Do not rely on temporary local files for the shared demonstration.
- A report submitted on another device must appear in site history.

Briefings:
- Build a deterministic template before Gemini. Include tomorrow's forecast, active alerts, unresolved reports, missing data, and the model index with its extrapolation label where shown.
- Gemini may rewrite supplied facts only; it must not invent measurements or policies. Store the generated result and keep the template fallback.
- Run one worker, independent of Flask's development reloader. Schedule at 18:00 using each site's IANA timezone.
- Distinguish briefing delivery date from forecast target date. Enforce one scheduled briefing per site per local delivery date at the database level.
- Manual demonstration generation uses the same idempotent generation function. Keep replay briefings isolated from live scheduled delivery.
- Test scheduling before waiting for the real 6 PM run.

## 11. Integration, verification and open items

Preserve and extend the existing API contract, fixtures, schema and startup commands. Coordinate any breaking change before implementing it.

A feature is complete when: its data persists where required; the frontend consumes the agreed response; missing/error states are visible; relevant behavior checks pass; its limitations are documented.

Prioritize checks for:
- At least 50 unique source plant IDs.
- Real database seed and database-mode retrieval.
- Alert-driven ranking updates.
- Persistent and isolated lightning state.
- Shared photo reports.
- Duplicate-free scheduled briefings.
- Actual saved-model outputs.
- Clean-clone startup and a frontend production build.

Do not claim an unrun test passed. Do not delete a failing test to hide an implementation defect.

Open items - resolve with the team and record the answer here; do not guess:
- The meaning of the "mode" field in /api/sites (storage mode vs event mode). Rename or document it so "live" never implies live conditions.
- Near-river identification: source, method and the field to add.
- Photo storage design.
- Sperry questions: is a labeled lightning replay acceptable if no live strike feed is reachable; does an in-app briefing satisfy delivery; is a county-level reported-event model acceptable for the prototype index.
- Paths of the API contract and schema files (section 1).
- Submission deadline: the pasted SwampHacks rules say Sunday 8:30 AM ET; another source reported 8:00 AM on Devpost. Check Devpost directly and target 7:30 AM.

## 12. Timeline and scope control

All times are America/New_York. Status at 3:30 PM Saturday: 55 plants seeded; ML baseline delivered; risk, alerts, reports, briefings and the ML wiring are not yet built or integrated.

Saturday, Oct 17:
- 5 PM: required features integrated; model output wired; briefing scheduler tested with manual generation.
- 6 PM: first real scheduled briefings for Eastern-timezone sites; Central-timezone sites (America/Chicago) run at 7 PM ET.
- 9 PM: evaluation, freshness labels, replay isolation; optional Gemini.

Sunday, Oct 18:
- 12:30 AM: feature freeze, clean-clone check, backup demo recording.
- 5-7 AM: rehearsal, documentation, submission.
- 7:30 AM: target submission with links verified.

These are working targets. If one slips, report the gap and cut optional scope. Verify current official submission requirements before final submission.

Cut first: extra integrations, animations, extra AI features, work-period comparison, additional models/tuning, complex report management, extra delivery channels.

Protect: the six required capabilities in minimal form, 50+ distinct plants, honest labels, a functioning workflow, evaluation, and a reliable demonstration.

Never hide an incomplete requirement by renaming a substitute.