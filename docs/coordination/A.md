# A — database, shared backend integration, worker registration

## Scope and ownership

### October 18, 2026, 3:35 AM ET - model display, crew lightning, tomorrow reports

Human requested four fixes across the integrated dashboard/operational flow.
Updated API_CONTRACT before adding read-only automatic briefing preview,
structured generated report fields and crew-observation routes. Reused existing
lightning/report/briefing storage; no schema/dependency/credential changes.
Changed backend/briefings.py, lightning.py, ops_routes.py and frontend dashboard,
workflow, display helpers/styles. No ML model or numeric rescaling changes.
Updated matching fixture fields without replacing other fixtures' IDs.

199 Python tests passed, one historical-data test skipped; 17 frontend checks,
build and fixture/live database Chromium checks passed. Rolled-back DB tests
verified observation persistence across new app instances, deduplication and
stored scheduled display uniqueness. Real browser main scores matched API values;
all 55 daily indices and tomorrow metrics were available. Inspected mobile report
screenshots. Restarted current backend and one leased worker; retired competing
Flask listeners. No production lightning event was invented, no commit/push.

Handoff: normal UI is simpler; Debug reveals sources/model/full report/coverage.
Crew recording works, but automatic live strikes still need a verified feed.
Actual 18:00 delivery remains unobserved; original ML geography artifacts and
sponsor questions remain open. No other owner's coordination log was edited.

### October 18, 2026, about 2:40 AM ET — forecast/model follow-up

Human requested missing current/tomorrow indices and next-day heat/soil/rainfall
fixes, then authorized migrating private configuration and retiring old servers.
Older examples contained placeholders; migrated the older working private
configuration into this checkout's ignored `.env` without displaying values.
Applied 003/004/005, preserving 55 plants. No secret was added to a template.

Updated API_CONTRACT first, then planning_weather.py, weather.py, predictions.py,
outlook.py, worker.py, app.py, dashboard/model/map presentation and focused tests.
DAILY rain is independent of hourly availability and recorded in saved JSON;
legacy rain integration follows preceding-hour intervals. Missing heat/soil
explains absent local-day values. Weather and inference are synchronized per
site; midnight cache refresh and concurrent-read freshness fixes prevent missing
forecasts and hidden fresh predictions. Both daily scores are visible.
Instantaneous ML is unsupported by the existing daily model.

Real worker pass: 55 weather successes, 110 available predictions, 55 NWS and 55
USGS successes; no briefings due. Stored Outlook confirms all 55 today/tomorrow
indices and all three tomorrow fields. Full suite: 184 passed, 1 skipped;
frontend: 15 passed; build, fixture Chromium and real-data Chromium desktop/mobile
passed. Old listeners replaced with this checkout on 5000/5173; one current worker
remains active. Local logs/PIDs are ignored under `.runtime/`. No commit, push,
merge, deployment, other-owner conversation or delegation.

### October 18, 2026, about 2:15 AM ET — repository-wide compliance integration

The human requested audit, implementation and verification across the repository
on a feature branch. Started from clean/up-to-date main; branch is
`feature/challenge-compliance`. No other agents/owners were contacted or
delegated to; no conversations are claimed. API_CONTRACT was updated before
changing interfaces. The real mismatch was the five-category report CHECK versus
the shared heat/lightning/flooding/mud requirement; migration 004 preserves the
legacy values and adds the required ones. Migration 005 adds USGS context.

Changes span A's worker/repositories/migrations, operational validation and
preview/filter routes, DAILY forecast-to-model inference, React reporting/inbox
components and coverage, tests/fixtures and setup/audit/demo docs. Existing plant
data, trained artifact/results and applied migrations were preserved. New root
dependencies are Pillow==12.0.0 and tzdata==2025.2. Details, actual commands and
results are in docs/requirements-audit.md and docs/SETUP_STATUS.md.

Default checks, frontend build/behavior tests, bounded real Open-Meteo/NWS/USGS
and saved-model inference, fixture browser flows, and actual-app inventory
desktop/mobile checks passed. DB opt-in checks fail because this checkout lacks
DATABASE_URL. Port 5000 was an older app; this branch was verified on 5127.
Shared migration application, real report/briefing persistence, 55-site worker
operation and live strikes remain unverified. No .env content read, no shared DB
writes, commit, push, merge or deployment. Do not equate the fixture or read-only
provider checks with durable integration. This entry supplements the older log.

Assigned explicitly by the human in this session on October 17, 2026.
The latest assignment supersedes the older letters in docs/WORKSTREAMS.md:
A backend/database/worker, B lightning/reports/briefings, C historical ML,
D frontend. No conversation with another agent has occurred in this session.

Owned changes: backend/db.py, backend/app.py integration, additive migrations,
weather ingestion/storage, the shared worker entry point, backend checks,
scripts/seed_database.py, and documentation for these interfaces.
Do not modify B/C/D modules or their logs. Preserve .env, ignored downloads,
model artifacts, existing API fields, and source plant identifiers.

## Inspection and actual problems

- This directory was a source export without .git. Initialized the requested
  feature branch feat/a-backend-integration; no commit, merge, or push.
- Only the foundation is present: 55 plants, manual weather fetching, in-memory
  cache, basic schema. No worker, persistent weather, alerts, reports, briefings,
  or model modules were found. No Python worker/downloader process was found
  with Get-Process; full Win32_Process inspection was denied by Windows.
- The local Python environment initially contained only pip. Installing the
  existing requirements-dev.txt needed network permission; no dependency
  additions or version changes are proposed.
- Existing mode=live|demo means plant storage, not event mode. Existing routes
  and response meanings must remain compatible.

## Additive interface proposal (recorded before implementation)

GET /api/outlook?mode=live|demo will read stored data only. It never contacts a
weather provider and does not mutate live/replay hazard state. Existing manual
GET /api/sites/{id}/weather remains available. Its database-storage path will
also persist successful responses; demo requests retain explicit file storage.

Exact example for a site without ingested weather (timestamps illustrative):

```json
{
  "storage_mode": "demo",
  "event_mode": "live",
  "as_of": "2026-10-17T12:00:00+00:00",
  "weather_freshness_seconds": 1800,
  "ranking_status": "not_implemented",
  "count": 1,
  "sites": [
    {
      "site": {
        "id": 663,
        "source_plant_id": 663,
        "name": "Deerhaven Generating Station",
        "state": "FL",
        "county": "Alachua",
        "latitude": 29.7592,
        "longitude": -82.3878,
        "timezone": "America/New_York",
        "source_version": "EIA-860 2025 annual inventory"
      },
      "weather": null,
      "weather_monitoring": {
        "state": "UNAVAILABLE",
        "last_attempt_at": null,
        "last_success_at": null,
        "error_code": null
      },
      "coverage": "UNAVAILABLE",
      "hazard_state": null,
      "alerts": null,
      "model_index": null,
      "unavailable_layers": ["weather", "lightning", "flood", "wildfire", "wildlife", "model"],
      "reasons": ["No stored weather snapshot.", "Hazard integrations and ranking are not implemented."]
    }
  ]
}
```

When present, weather preserves the existing weather payload (source,
fetched_at, current/current_units, hourly/hourly_units, note) and adds
cached=true, stale, current_evidence_type=modeled_current_conditions and
hourly_evidence_type=forecast. Freshness uses retrieval age <= 1800 seconds;
a failed most recent refresh also marks the previous snapshot STALE. Missing
weather remains null, never a zero-filled forecast. Coverage is PARTIAL when
fresh weather exists because the remaining hazard layers are unfinished.
hazard_state stays null until B integrates actual hazard evidence; alphabetical
site order is explicitly not a risk ranking. Daily model output is not expanded
into hourly forecast values.

## Worker interface proposal

One process: python -m backend.worker. PostgreSQL session advisory locking
prevents concurrent worker instances against the same database. No worker is
started by Flask. The weather job's final cadence is described below. A job is
Job(name, callback, interval_seconds); callback takes no arguments and returns
a JSON-serializable summary. B/C can supply explicit --job-module module:function
factories returning Job objects. Factories must not start threads/processes or
perform ingestion at import time. Job failures are recorded and do not stop
unrelated jobs; startup/configuration errors fail visibly.

No briefing or prediction job is claimed to exist until B/C supplies one.

### Refinements recorded before implementation

The existing two UTC-day request can omit the final hours of tomorrow in an
American site's local timezone. Request three UTC calendar days using the same
verified fields; consumers must use hourly.time and the site's IANA timezone,
not assume a fixed number of hours. This changes array length, not field names.

Weather monitoring may also be PARTIAL when required values/units are missing.
Exact affected field example: "weather_monitoring": {"state": "PARTIAL",
"last_attempt_at": "2026-10-17T12:00:00+00:00", "last_success_at":
"2026-10-17T12:00:00+00:00", "error_code": null}. The existing reasons array
will name missing fields; null measurements remain null. A current valid time
older than 30 minutes also makes weather stale, even if just retrieved.

A full 55-site sweep with 12-second timeouts could delay B's scheduled jobs.
Regular worker operation will rotate one site per 15-second job interval,
bounding each weather callback to one provider request. --once deliberately
runs one complete sweep (or the explicit --site-id subset) for initial fill and
verification. B/C callbacks must likewise be bounded. The worker is serial;
delivery may be delayed by one in-progress callback and is not a hard real-time
scheduler. Each site is revisited roughly every 15 minutes plus request time.

## Verification and handoff

### Implemented and checked

- Additive numbered/checksummed migration plus serialized migration execution.
  Existing base tables and identifiers are preserved. Seed SQL was moved into
  the existing database adapter; no production SQL was added to route handlers.
- weather_snapshots retains source payload, current/forecast valid timestamps,
  units and retrieval time. weather_ingestion retains attempts, last success
  and sanitized error codes. Failed refreshes preserve earlier snapshots.
- Snapshot storage and queries explicitly separate event_mode from API plant
  storage mode. The Outlook excludes replay snapshots, including later replay
  timestamps. No lightning/replay state is changed by this work.
- Live manual weather requests persist; demo manual behavior and all existing
  response field names are preserved. Polling /api/outlook reads only storage.
- Worker lease, bounded normal rotation, explicit job factories, persisted job
  summaries, failure isolation and recovery of interrupted running records.
- .env.example restored with safe placeholders. Existing dependency versions
  were installed unchanged. No credentials or local .env edits were made.

### Actual problems and resolutions

- Initial sandboxed provider sweep failed requests (33 failed attempts observed,
  no successful snapshot at that point). Stopped that process before retrying;
  no duplicate worker was launched. A network-approved single-site check then
  succeeded, followed by one complete approved 55-site sweep.
- The interrupted sweep left a running job record. Added recovery after acquiring
  the exclusive lease: unfinished prior runs become failed with the sanitized
  worker_interrupted code. Successful/partial/completed runs are preserved.
- A full weather sweep could block B's scheduling; normal weather ticks now
  handle one site. --once remains an explicit bounded initial-fill command.
- Two UTC forecast days could miss tomorrow's local evening; actual provider
  responses now contain 72 hourly entries, verified to span each plant's entire
  local tomorrow. Missing fields and stale current valid times are checked.

### Commands and results actually run

- python -m pytest -q -p no:cacheprovider --run-database: **30 passed**. Includes
  the original six foundation tests and real PostgreSQL tests in unique schemas
  rolled back afterward. Real checks cover migration/seed repeatability,
  checksum mismatch detection, snapshot uniqueness, delayed-write freshness,
  replay filtering, worker lock exclusion/release and interrupted-run recovery.
- python -m scripts.seed_database: **one migration applied; 55 plants present**.
- python -m backend.worker --once --site-id 663 (network-approved): **1/1 success**.
- python -m backend.worker --once (network-approved): **55/55 success, 0 failed**.
- Separate fresh Python/Flask test-client process: /api/health, database-mode
  /api/sites and /api/outlook all HTTP 200; database connected; **55 unique source
  plant IDs; 55 fresh stored forecasts; 55 complete weather components; all 55
  local-tomorrow forecast horizons covered**. Overall coverage remains PARTIAL
  for all 55 because other required hazard layers are unfinished. alerts,
  hazard_state and model_index remain null; ranking is explicitly unimplemented.
- git check-ignore confirmed .env, .venv and frontend/node_modules remain ignored.
  Secret-pattern review found only the deliberate .env.example placeholder and
  fake password in the exception-redaction test, not actual credentials.
- Branch: feat/a-backend-integration. This started as a source export, so files
  remain untracked in the newly initialized repository; no commit, merge or push.
- No frontend/browser verification was run for this backend-only change.
  No persistent worker was left running after the bounded verification passes.
- Final audit: 17 changed files checked with no trailing whitespace; zero Python
  processes remained. Persisted worker history showed two succeeded runs and one
  failed/interrupted run, with no records incorrectly left running.

### Changed files

.env.example; backend/app.py; backend/db.py; backend/weather.py;
backend/ingestion.py; backend/outlook.py; backend/worker.py;
backend/migrations/001_weather_worker.sql; scripts/seed_database.py;
tests/conftest.py; tests/test_backend_integration.py; tests/test_database.py;
README.md; docs/API_CONTRACT.md; docs/WORKSTREAMS.md; docs/SETUP_STATUS.md;
docs/coordination/A.md. Shared ownership letters and the historical status note
were reconciled with the latest human assignment and actual verification.

### Required next owner actions

- **B**: supply persistent lightning/report/briefing data contracts and request
  their additive migrations from A before shared schema changes. Implement and
  test 18:00 site-local idempotent briefing delivery. Expose a factory returning
  Job objects for the shared worker, with short callbacks. No briefing is
  currently scheduled or delivered by this worker.
- **C**: supply saved prediction/read interfaces (valid_date, model_version,
  feature_version, score, computed_at) and required database migration shape.
  Provide a bounded inference Job factory; no historical downloader/model job
  is started by A. Evaluation and genuine model outputs are still required.
- **D**: consume GET /api/outlook?mode=live for the forecast matrix/evidence
  display; join on site.id, render hourly.time in the site's timezone and keep
  missing/stale/partial evidence visible. Preserve daily ML granularity when C
  integrates. Current rows are not a risk-ranked attention queue.
- **Integration owner/A**: after B/C publish real interfaces, integrate them into
  the shared response and apply additive migrations. Register their factories
  in the same worker command, then start exactly one regular worker. Do not
  start the weather-only worker and separate briefing/model workers together.
- Required coverage still incomplete: live lightning; official flood/river
  evidence; wildfire evidence; shared wildlife/photo reports; hazard-driven
  ranking; local 18:00 briefings; historically trained model predictions.
  Shallow modeled soil moisture alone does not establish soil trafficability or
  saturation thresholds. No sponsor requirement is claimed complete by renaming
  one of these substitutes.

Example registration interface for B/C (the modules/functions are to be supplied
by those owners; this is not a claim they exist):

```python
from backend.worker import Job

def worker_jobs():
    return [Job('briefings', run_due_briefings, 30)]
```

After B/C deliver their modules, stop any old worker and run one command such as
`python -m backend.worker --job-module backend.briefings:worker_jobs
--job-module ml.inference:worker_jobs`. A callback takes no arguments, returns a
JSON-safe aggregate summary, and must not include credentials or raw provider
exceptions. A returned failed count produces failed/partial job status; raised
exceptions are recorded with only a sanitized error code and exception type.

## Follow-up: sponsor workflow backend (October 17)

Human requested a working backend supporting the complete sponsor workflow and
a short integration document. Inspection still found no B/C implementation or
logs. No agent conversations are claimed. Preserve B/C business ownership:
A adds shared database repositories, official-warning ingestion and composition;
B implements strike acceptance/distance, uploads and briefing scheduling;
C trains/evaluates the model; D consumes the API. Existing weather storage and
provider are retained. No competing worker/downloader will be started.

### Additive proposal, recorded before implementation

New migration 002 adds NWS snapshots/status and storage for lightning events and
holds, shared photo-report bytes/metadata, idempotent briefings, and genuine model
predictions. Existing migration 001 is immutable. All SQL stays in db.py or SQL
migrations. Repositories validate modes and identifiers; live reads always filter
event_mode='live'. No public write endpoints or fake model/strike feeds are added.

Outlook preserves existing fields and adds official_alerts_monitoring,
planning_weather, lightning_hold, unresolved_reports, prediction and rank.
alerts becomes an actual list only after official monitoring/report evidence
exists; otherwise it remains null. model_index is the actual saved score or null;
prediction retains its date/version/provenance. Weather is never a model score.
Exact additional field example (illustrative, not real current evidence):

```json
{
  "official_alerts_monitoring": {"state": "COMPLETE", "fetched_at": "2026-10-17T12:00:00+00:00"},
  "planning_weather": {
    "target_date": "2026-10-18", "heat_index_max_f": 111.2,
    "precipitation_sum_mm": 12.0, "soil_moisture_max_m3_m3": 0.4,
    "source": "Open-Meteo", "evidence_type": "derived_from_forecast",
    "heat_method": "NWS Rothfusz/Steadman formula applied to modeled temperature and humidity",
    "note": "Shallow modeled soil moisture does not measure trafficability."
  },
  "lightning_hold": null,
  "unresolved_reports": [],
  "prediction": null,
  "rank": 1
}
```

ranking_status becomes 'evidence_based' only for database Outlook. Order:
active holds; severe official warnings; other official warnings/advisories and
unresolved reports; missing critical monitoring; then weather/model planning
signals. reasons explains placement. A failed/old official feed retains prior
unexpired warnings and marks coverage stale. Fire-weather products remain
separate from active-fire detections. No river proximity is inferred from names.

New read-only GET /api/sites/{id}/evidence returns the same Outlook row;
GET /api/readiness summarizes stored feed coverage and unimplemented features.
Existing manual weather routes are retained. A's short handoff will refer to
docs/API_CONTRACT.md as the canonical API definition and list exact repository
function arguments B/C can use, rather than inventing alternative endpoints.

Derived next-day heat index uses the published NWS calculation, not provider
apparent_temperature. Missing inputs/hours produce null summaries. The displayed
result is a calculation from modeled forecasts, not an official NWS observation.
No new occupational stop-work thresholds or saturation thresholds are invented.

### Follow-up implementation and actual results

Implemented migration 002 without modifying applied migration 001. Added shared
repositories and database constraints for official-warning snapshots/failure
status, namespaced strike deduplication and monotonic holds, photo bytes and
report metadata, one briefing per site/event-mode/local delivery day, and
versioned real-model predictions. B's 10-mile distance/provider acceptance,
actual-image verification/upload APIs and scheduling remain B's responsibilities.
C must supply the trained artifact and actual scores. No sample score, report,
strike or briefing was inserted into the production database.

Verified NWS's actual point response and a real national alert's property fields
before writing ingestion. Source evidence is saved in
data/source_checks/nws_alerts.json and nws_alert_sample.json. The sandboxed
point request failed with URLError; the approved request succeeded. The worker
now has a separate bounded official-alert rotation (one site per five-second
interval plus request time) and retains previous snapshots on refresh failure.
NWS freshness is 600 seconds; no instant lightning-feed coverage is claimed.

Added site-local next-day summary calculations. The NWS heat-index formula is
applied to modeled temperature/RH, separate from provider apparent temperature;
all expected local-day hours and correct units are required. 23- and 25-hour DST
days are tested. Missing values stay null. Soil moisture has no invented
trafficability threshold and rainfall does not become an official flood warning.

Outlook now ranks actual saved evidence, preserving STOP_WORK holds ahead of
official warnings, other alerts/reports, missing critical monitoring and model/
forecast signals. Expired holds do not clear other hazards. Official flood and
fire-weather products are classified separately; river proximity remains
explicitly unknown, and fire-weather is not described as active-fire detection.
GET /api/sites/{id}/evidence and /api/readiness read storage only. Prediction
selection uses each site's local tomorrow; daily values are not repeated hourly.

Actual commands/results for this follow-up:

- python -m pytest -q -p no:cacheprovider --run-database: **47 passed**.
  Includes original tests and real rolled-back PostgreSQL checks for the new
  repositories, replay isolation, duplicate-free briefings, photo persistence,
  monotonic lightning holds, delayed prediction writes, failure retention and
  warning-driven ordering. This does not test a live strike provider, actual
  photo upload validation, 18:00 scheduling, model training or the frontend.
- python -m scripts.seed_database: **migration 002 applied; 55 plants present**.
- python -m backend.worker --once (approved external network): weather **55/55
  succeeded** and official_alerts **55/55 succeeded**, zero failed.
- Fresh Python/Flask process: health, live sites, Outlook, site 663 evidence and
  readiness all HTTP 200. **55 unique plants; 55 complete weather components;
  55 fresh official-monitoring components; 55 complete next-local-day summaries.**
  At verification, stored evidence contained **17 active site-alert matches** and
  zero saved model predictions. Requirements_complete remained false and overall
  coverage did not incorrectly become COMPLETE. Invalid storage mode replay was
  rejected with HTTP 400. Counts describe this run, not a promise of current data.

Follow-up changed files: backend/db.py, app.py, outlook.py, worker.py;
backend/official_alerts.py; backend/planning_weather.py;
backend/migrations/002_workflow_storage.sql; tests/test_backend_integration.py;
tests/test_database.py; tests/test_workflow_backend.py; .env.example; README.md;
docs/API_CONTRACT.md; docs/BACKEND_HANDOFF.md; docs/WORKSTREAMS.md;
docs/SETUP_STATUS.md; docs/coordination/A.md; the two NWS source-check JSON files.
No dependencies, frontend files, private .env values or original site records
were changed. No commit, merge or push. No B/C logs were edited.

The short document requested by the human is **docs/BACKEND_HANDOFF.md**. B/C can
now implement against the documented repositories without inventing SQL or a
second worker. D can consume actual ranked evidence through the documented API.
Final audit checked 19 changed files with zero whitespace issues; the handoff is
76 lines. Migrations 001/002 are recorded in the real database. Worker history
has four succeeded runs and the prior interrupted failed run; none is left
running. Zero Python processes remained. No frontend/browser check was run.
