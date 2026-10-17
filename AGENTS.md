# PlanIT Control - Shared Project Instructions

Read this file before making changes. It applies to every coding assistant in this repository (Claude Code, Codex, Copilot, others). CLAUDE.md tells Claude Code to read this file, so edit shared rules HERE only.

This file holds STABLE rules. Anything that changes hour to hour (what is built, what is blocked, open decisions, verified results) lives in docs/SETUP_STATUS.md. Read that file too, and update it, not this one, when status changes.

## 1. Objective and authority

Build PlanIT Control for the SwampHacks XII Sperry Tech challenge.

Core workflow: identify a site needing attention -> explain the evidence -> alert the crew -> collect a field report -> prepare tomorrow's briefing.

Optimize for a complete, reliable, understandable demonstration and legitimate challenge coverage. The repository began as a foundation, not a finished safety product: inspect the current code and docs/SETUP_STATUS.md before assuming a feature exists.

When sources disagree, follow this order and name the conflict before changing any shared contract:
1. The team's latest explicit instruction (relayed by the human owner).
2. The Sperry brief (docs/brief.md) and the SwampHacks XII rules, for requirements and eligibility. If docs/brief.md is missing, ask the integration owner to add it; do not rely on memory of the brief.
3. The agreed implementation documents: docs/API_CONTRACT.md (API shapes and error behavior), backend/schema.sql (database), fixtures, and docs/WORKSTREAMS.md (ownership and checkpoints).
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

A missing feature or a replay does not count as a completed live integration. Unresolved sponsor interpretations are tracked in docs/SETUP_STATUS.md; do not assume approval.

## 3. Stack and foundation

- Frontend: React + Vite, JavaScript. Preserve the existing Leaflet map unless a change has a clear benefit.
- Backend: Flask, Python 3.11+. Use ONE Python version on every laptop, preferably 3.12 (the ML model was trained under 3.12.10). If a pinned package will not install on a very new Python (for example 3.14, where pandas 2.2.3 compiles from source), move all laptops to 3.12 instead of loosening pins.
- Database: Tiger Data PostgreSQL through Psycopg. Keep SQL in the existing database adapter (backend/db.py) and schema in backend/schema.sql.
- Worker: ONE separate Python process for ingestion, briefings and predictions (create it only when its owner starts it; run exactly one).
- ML: pandas + scikit-learn (section 9). Briefings: deterministic template first; optional Gemini rewrite.
- Dependencies: backend/worker use the root requirements.txt (dev tools in requirements-dev.txt, data tools in requirements-data.txt); ML uses ml/requirements.txt. Keep all pinned. Put a new package in the right file and tell the team if it affects shared setup. Routine work inside your scope does not need repeated approval.

Tiger Data is the selected shared database. Diagnose connection failures first. A switch to another database is a team architecture decision, never an automatic fallback. The file/demo storage mode is an explicit foundation feature; it does not prove Tiger Data integration and must never silently replace a failed database (the API returns 503 instead).

The plant list is 55 distinct plants from the official EIA-860 2025 annual inventory (data/sites.json). Preserve stable source plant IDs and provenance. Inventory-year operating status is not verified current operating status.

Startup (run from the repository root; each person makes their own .venv, never committed):
```
python3 -m venv .venv                          # Windows: py -m venv .venv
source .venv/bin/activate                      # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m flask --app backend.app:create_app run --port 5000
cd frontend && npm ci && npm run dev           # second terminal
```
Flask does not reload by itself: restart it after backend changes. Without activating on Windows, use .venv\Scripts\python.exe -m ... in place of python -m ...

Database seeding (python -m scripts.seed_database) writes to the SHARED database. It creates tables with CREATE TABLE IF NOT EXISTS and upserts plants by source plant ID, so rerunning is safe, but it does NOT alter existing tables. Adding a column to an existing table needs an explicit ALTER statement added to the schema workflow and an announcement to the team. Only the backend/data owner runs it unless told otherwise.

## 4. Team ownership and parallel development

Four human owners work simultaneously, each with their own coding assistant. Roles:
- Frontend: dashboard, map, site detail/timeline, report form, briefing inbox.
- Backend/data: plant data, database, ingestion, shared data interfaces.
- Alerts/reports: lightning state, reporting, briefing generation and scheduling.
- ML: dataset, labels, training, evaluation, prediction export.

docs/WORKSTREAMS.md is the authority for who owns which paths. Some documents refer to owners by letter (A, B, C, D) and the letters differ between documents (for example docs/ML.md calls the ML owner C). Use role names when messaging teammates and check WORKSTREAMS.md when unsure.

One integration owner coordinates shared contracts and merges.

Git rules:
- Work on a feature branch, never directly on main. Before editing: git pull, git status, read the relevant files.
- Do not overwrite another person's uncommitted work. Commit before switching branches.
- Coordinate before changing another owner's active module, shared API response shapes, the schema or shared dependencies. Update docs/API_CONTRACT.md and notify affected owners BEFORE changing a field name or shape.
- Use fixtures that match the contract so work continues before other modules are ready.
- Keep changes focused: no unrelated refactors or formatting churn.
- Commit completed, verified steps when the human owner requests or authorizes it. Never force-push, rewrite shared history or discard others' work without explicit authorization.

Handoff report: what works; changed files; commands/checks run and their results; remaining gaps and integration needs.

## 5. Data integrity, API behavior and secrets

- The repository is PUBLIC. Never commit secrets: the Tiger Data connection string, Gemini or any provider key, or any .env file. Credentials live in gitignored .env files; keep .env.example to names only. Call provider APIs from the backend or worker only. Check staged changes for keys and connection strings before every push. Coding assistants must not read, print or paste the contents of .env.
- If a secret is ever committed or pushed, tell the team immediately; the key must be rotated (deleting the file from a later commit does not remove it from history).
- Preserve source, observation/forecast time, retrieval time and units for stored data. Distinguish observations, forecasts, official warnings, modeled proxies, crew reports and replay events.
- Unknown values are null, never zero. Missing or stale data must not appear as zero risk. "No recent reports" does not mean "no hazard."
- API behavior follows docs/API_CONTRACT.md: no catch-all endpoint that returns plausible success; unknown routes return 404; a missing or failing database returns 503 with no silent fallback; a failed upstream provider returns 502 unless a stale cached copy exists, in which case return it with stale: true. Time values are labeled and unambiguous.
- Fire-weather warnings and satellite fire detections are different evidence. Open-Meteo apparent temperature is not the NWS heat index.
- Cache upstream responses and persist useful observation/forecast snapshots. Dashboard polling reads stored data and never fans out to upstream APIs. A manual weather-fetch action may remain during transition; move routine refreshes into the worker.
- Verify an actual provider response before wiring fields into ingestion. The NWS API requires a descriptive User-Agent header.
- Credit real data sources, libraries and EVERY AI tool the team used (Claude Code, ChatGPT/Codex, Gemini, others) in the README before submission. Use only code written during the permitted hackathon period; do not copy implementation code from prior personal projects. Prebuilt libraries and credited open-source code are allowed; do not present them as original work.

## 6. Hazard status, coverage and ranking

Track each hazard independently. Compute presentation from those components; never use one stored flag that clears unrelated hazards.

Represent separately:
- Hazard state: STOP_WORK, ALERT, ELEVATED or NO_ACTIVE_ALERTS.
- Monitoring coverage: COMPLETE, PARTIAL, STALE or UNAVAILABLE.

Coverage refers only to configured monitoring and its documented freshness rules. It does not certify site safety. Never label a site "safe" or "all clear". NO_ACTIVE_ALERTS means no active alerts in the available monitored evidence.

Examples: an active lightning hold remains STOP_WORK even if another feed is unavailable; a missing strike feed stays visibly unavailable after the timer expires.

Rank active lightning holds and severe official warnings first, then other alerts/advisories and relevant unresolved reports, then model/weather signals. Show reasons and feed coverage on each row. Make missing critical monitoring visible rather than burying it at the bottom. Never average a lightning hold into an overall numeric score. The ML index never overrides an official warning.

## 7. Lightning and replay isolation

Use UTC internally; convert to local time only for display and scheduling. Use haversine distance; 10 miles is about 16.09 km.

For each accepted strike:
1. Validate its identifier, coordinates, timestamp and event mode.
2. Ignore duplicates within the same source/event mode.
3. Find sites within 10 miles.
4. Set hold_until = max(existing hold_until, strike_time + 30 minutes).
5. Persist the resulting state.

An older delayed strike cannot shorten an existing hold. Expiration clears only the lightning hold.

Naming rule: the word "mode" in the existing API (live | demo) means DATA STORAGE (Tiger Data vs file). Lightning and replay use a separate field named event_mode with values live | replay. Never reuse "mode" for event mode, and never let storage "live" imply live conditions in the UI.

Live and replay may share one processing function but have separate state and queries. Key lightning state by (site_id, event_mode) and namespace event identifiers by source and event mode. Replay must not modify live ranking, live alerts or live briefings. Pass event_mode explicitly through the replay workflow and label it visibly as simulated replay. Use a replay session identifier to reset and restart demonstrations cleanly. Accelerated playback uses one consistent replay clock for event time, countdowns and expiration.

Write tests first:
- 9 miles triggers a hold; 11 miles does not.
- Duplicate processing is a no-op.
- An older event cannot shorten a hold; a later qualifying event extends it.
- Expiration preserves unrelated hazards.
- Stale/unavailable monitoring remains visible.
- Replay cannot change live state.

## 8. Flood, heat and fire

- Keep official flood alerts separate from rainfall-based advisories. An illustrative rainfall rule is labeled an advisory with a documented threshold, never an official flood warning.
- Do not infer river proximity from a plant name. Document how near-river sites were identified; unknown proximity stays unknown (no near-river field exists unless docs/SETUP_STATUS.md says otherwise).
- Document the heat metric, units and thresholds actually used.
- Implement the minimum fire coverage the Sperry brief requires, using official fire-weather alerts and/or accessible fire detections with distinct labels. If a required layer is unavailable, disclose the gap rather than reclassifying it as optional.

## 9. ML implementation

Prove the pipeline on a small sample, then expand.

Model design:
- Unit: county-day (no duplicate rows for plants in the same county).
- Label: a reported Thunderstorm Wind, Hail, Tornado or Flash Flood event; county-based NOAA records only (CZ_TYPE = C); verified state/county identifiers (county names in sites are not FIPS; use a verified crosswalk); consistent local dates; multi-day events expanded explicitly.
- A negative label means no selected event was reported, not proven safety.
- Features: daily weather summaries and seasonal features. Chronological split. Logistic regression plus a simple baseline. Fit preprocessing on training data only. Choose thresholds on validation data, never the final test set.
- Report dataset size, positive prevalence, missingness, baseline, average precision, precision/recall at the chosen threshold, and ROC-AUC only when defined. Evaluation lives in ml/results.json.
- Index = 10 x model probability, bounded 0-10, labeled "experimental model index". Never call it an injury probability, and never claim calibration without evidence.
- Historical evaluation uses observed weather; deployment uses forecast summaries. Keep features and units consistent and document the difference. Historical scores do not establish next-day forecast performance; say so wherever the model is described.

Delivered baseline (ML owner's branch; merged through the integration owner): ml/predict.py (interface), ml/artifacts/model.joblib, ml/results.json, ml/requirements.txt, docs/ML.md, ml/build_dataset.py, ml/train.py, ml/common.py, ml/test_ml.py, ml/START_HERE.md. Read docs/ML.md and ml/results.json for the actual training years, counties, features, threshold and metrics rather than trusting a summary here.

Interface:
```
from ml.predict import predict_site
result = predict_site(
    {"temperature_2m_max": <deg C>, "precipitation_sum": <mm>, "wind_gusts_10m_max": <km/h>},
    target_date="YYYY-MM-DD")
```
- Inputs must cover the ENTIRE target day in the site's local timezone: request Open-Meteo DAILY forecast values with that site's IANA timezone. Never pass current readings, partial daily totals, or hourly data that does not cover the full local day. The existing hourly weather response may not.
- Returns: status, model_index, probability, target_date, model_version, feature_version, computed_at, outside_training_range and a note (plus a reason when unavailable). Seasonal features are derived inside the function.
- Unavailable inputs return status="unavailable" with a null index. Show "unavailable", never 0.
- outside_training_range is a LIST naming input features outside the range seen in training (empty means all inputs were in range). It does NOT say whether the site is in a training county.
- The model does not know the site's county. For any site outside the training counties the prediction is geographic extrapolation. The backend computes that flag by comparing the site's county FIPS with the training counties and stores it. UI and briefings show it as "outside training counties" and also show any features in outside_training_range.
- Persist results through the predictions table. The contract's minimum keys are site ID, valid_date, model_version, feature_version, score and computed_at. Also store status, probability, outside_training_range (JSON) and the geographic extrapolation flag. Add missing columns through the backend/data owner and update docs/API_CONTRACT.md.
- Load only trusted joblib artifacts. The artifact needs the versions in ml/requirements.txt (notably scikit-learn); a different version can fail to load or change results. Run ML code in an environment that matches it.
- Official alerts and lightning holds stay independent of the model.

## 10. Reports and briefings

Reports:
- Validate site, coordinates, category (heat, lightning, flooding, mud, fire, wildlife, other), note and uploaded image. Apply a file-size limit (suggest 5 MB) and verify the file is really an image.
- Store photos and metadata in the database so a report submitted on one device appears on another. Do not depend on temporary local files for the shared demonstration. The uploads/ folder is gitignored and is not shared storage.
- Endpoints follow docs/API_CONTRACT.md.

Briefings:
- Build the deterministic template first. Include tomorrow's forecast, active alerts, unresolved reports, missing-data notes, and the model index with its extrapolation label where shown.
- Gemini may rewrite supplied facts only; it must not invent measurements or policies. Store the result and keep the template fallback.
- Run one worker, independent of Flask's development reloader. Schedule at 18:00 in each site's IANA timezone (sites in America/Chicago run at 7 PM Eastern).
- Distinguish briefing delivery date from forecast target date. Enforce one scheduled briefing per site per local delivery date at the database level (UNIQUE site_id, local_date).
- Manual demonstration generation uses the same idempotent generation function. Keep replay briefings isolated from live scheduled delivery.
- Test scheduling before waiting for the real 6 PM run.

## 11. Verification

A feature is complete when: its data persists where required; the frontend consumes the agreed response; missing and error states are visible; relevant behavior checks pass; its limitations are documented.

Prioritize checks for:
- At least 50 unique source plant IDs.
- Real database seed and database-mode retrieval.
- Alert-driven ranking updates.
- Persistent and isolated lightning state.
- Shared photo reports across devices.
- Duplicate-free scheduled briefings.
- Actual saved-model outputs displayed.
- Clean-clone startup (README procedure) and a frontend production build.
- A manual browser check of map and mobile layout; automated tests do not cover it.

Run: python -m pytest -q, and in frontend/ npm run build. Do not claim an unrun check passed. Do not delete a failing test to hide a defect. Report what you actually ran.

Open decisions and sponsor questions are tracked in docs/SETUP_STATUS.md. Do not guess answers; ask the human owner, and record the resolution there.

## 12. Timeline and scope control

All times America/New_York. Working targets (current progress is in docs/SETUP_STATUS.md):
- Sat 5 PM: required features integrated; model output wired; scheduler tested with manual generation.
- Sat 6 PM: first real scheduled briefings for Eastern sites; Central sites at 7 PM.
- Sat 9 PM: evaluation, freshness labels, replay isolation; optional Gemini.
- Sun 12:30 AM: feature freeze, clean-clone check, backup demo recording.
- Sun 5-7 AM: rehearsal, documentation, submission.
- Sun 7:30 AM: target submission with links verified. Official end is 8:30 AM per the pasted rules; one source showed 8:00 AM on Devpost. Treat the earlier time as the deadline and verify on Devpost.

If a target slips, report the gap and cut optional scope. After the freeze, fix bugs and documentation only.

Cut first: extra integrations, animations, extra AI features, work-period comparison, additional models/tuning, complex report management, extra delivery channels.

Protect: the six required capabilities in minimal form, 50+ distinct plants, honest labels, a functioning workflow, the ML evaluation, and a reliable demonstration.

Never hide an incomplete requirement by renaming a substitute.