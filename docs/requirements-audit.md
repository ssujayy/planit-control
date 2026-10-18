# Challenge requirements audit

## Follow-up verification: October 18, 2026, about 2:40 AM ET

This supersedes the initial database blockers below. The human authorized
configuration migration and replacement of old servers. Tiger Data now connects;
migrations 003/004/005 applied successfully. Private values were not displayed;
`.env.example` is blank and `.env` is ignored.

The complete live-provider worker pass saved **55 weather snapshots and 110
available today/tomorrow predictions**, refreshed NWS and USGS for all 55, and
exited successfully. No briefing was due at 2 AM. One regular worker now runs.
Database-backed Outlook verified **55/55 for both model indices and all three
tomorrow metrics** (rainfall, derived heat, shallow soil moisture).

Missing values came from the older running checkout's yesterday snapshots,
all-or-nothing hourly summarization and absent model outputs. Fixes prefer
complete DAILY rainfall independently of hourly coverage, record the next-day
summary/rainfall, retain complete-day heat/soil rules with specific missing
reasons, refresh caches after local midnight, and compute scores immediately
after each site's weather ingestion. The dashboard shows both indices per site;
a concurrent-read timing race no longer hides new predictions.

The model remains a **daily** model. A legitimate instantaneous current-weather
index needs subdaily historical features, time-aligned labels, training/evaluation
and a new inference contract. Current readings are not substituted for daily
maxima/totals. Today's index uses the latest full-day forecast.

Verification: **184 passed, 1 skipped** with database tests enabled (only ignored
historical experiment data skipped); **15 frontend checks passed**; production
build and fixture browser flows passed. Actual database Chromium verified all
55 daily indices, successive site selections with all three tomorrow values,
Leaflet and desktop/mobile layout. Earlier counts/failures below are historical.

Current app: http://localhost:5173 and http://localhost:5000. Old listeners were
stopped. One current worker remains active. No commit, push, merge or deployment.

Baseline inspected October 18, 2026 (America/New_York), branch
`feature/challenge-compliance`. The initial tree was clean and origin was current.
This is a code audit, not sponsor approval or a safety certification.

## Initial findings

| Requirement | Existing evidence | Initial gap / planned work | Status |
|---|---|---|---|
| 50 real sites | `data/sites.json`, `scripts/prepare_sites.py`, EIA provenance, 55 IDs | Preserve inventory; verify database separately | Complete inventory; database unverified here |
| Combined conditions | `outlook.py`, `weather.py`, NWS point alerts, heat/soil forecast summaries | Predictions not generated; reports not usable in UI; missing live strikes and river context | Partial |
| Continuous alerts | Single leased worker, persisted snapshots, 15s dashboard poll, NWS warnings, lightning processor and replay | Register operational jobs; verify boundary/staleness; real strike adapter externally blocked | Partial |
| River/rain flood advisory | Site-specific NWS flood products | No verified river proximity, river gauges or overnight rain integration; do not fabricate | Missing |
| 6 PM briefing | `briefings.py` local/DST scheduler, DB uniqueness, manual replay API | Worker defaults omit job; dashboard inbox disconnected; precautions/periods limited | Partial |
| Crew reporting | Upload/history/photo/resolve APIs, PostgreSQL image bytes | UI absent, no history filters, signature-only image validation, required categories missing | Partial |
| Supervisor dashboard | Leaflet map, ranked queue, explanations, missing states, 15s polling | Connect report/briefing workflows, model limitations and current-day scoring | Partial |
| Genuine ML | Saved logistic model, reproducible builder/train, `ml/results.json`, 2022/23/24 split | No forecast-to-inference/persistence; verified county mapping not shipped; current-day forecast scoring absent | Partial |
| Reliability/setup | Error semantics, migrations, isolated replay, tests | `.env.example` absent; status docs obsolete; install model deps and Windows timezone data | Partial |

## Baseline checks

- `python -m pytest tests -q`: 101 passed, 11 database checks skipped.
- Full `python -m pytest -q`: collection blocked by missing ML dependencies.
- Frontend production build passed; frontend behavior checks: 13 passed.
- Windows sandbox requires escalation for Git metadata, Vite child processes and
  virtual-environment bootstrapping. No user work was overwritten.

Implementation and final verification evidence will be recorded below.

## Implemented result

Status meanings: **complete** means the listed bounded behavior was actually
verified; **partial** means working code/evidence exists but the full acceptance
flow is unverified; **missing** means absent functionality; **externally blocked**
identifies a missing credential/service/artifact. No overall compliance claim is
made. A database-backed path being implemented is not evidence that it persisted.

| Requirement / acceptance behavior | Implementation evidence and work | Verification / remaining gap | Result |
|---|---|---|---|
| ≥50 actual sites and provenance | Preserved `data/sites.json`, EIA source IDs/coordinates/provenance and importer | Actual Flask file-inventory response: 55 rows, 55 source IDs; source uniqueness tests pass. Inventory status is not current operating status. | Complete inventory |
| Shared actual sites | Existing Tiger Data adapter and idempotent seed | Current checkout health says `not_configured`; live routes return 503. An older process on port 5000 is not evidence for this branch. | Externally blocked |
| Weather, heat, rainfall, soil | Site-local DAILY values plus existing current/hourly weather, NWS-formula derived heat, modeled shallow soil moisture | Actual Open-Meteo response verified; units/times preserved; nulls, failed refresh and full local-day/DST summaries tested | Complete bounded provider path; 55-site worker run unverified |
| Official flood/fire-weather evidence | Existing NWS point queries, persisted snapshots and unexpired alert composition | Actual NWS response for EIA 663 verified; severe-warning ordering/expiry/stale tests pass; no active warning fabricated | Partial pending shared ingestion |
| Wildlife / local hazards | Crew reports integrated into history, map and ranking; coverage says crew sightings only | Real-image API tests plus browser fixtures; no reports never means no wildlife | Partial pending database |
| Measurement source, units, observation/retrieval, severity | Outlook/detail retain metadata and distinguish forecasts, modeled current/past values, geographic context, official warnings and crew reports | Tests and screenshots confirm explicit unavailable/stale states | Complete presentation behavior |
| Automatic background monitoring | Exactly one separately started worker; default weather/NWS/hydrology/prediction/briefing jobs | Worker registration, bounded rotation, failure continuation/lease logic covered. No real worker started without local DB credentials | Partial |
| Refresh intervals, rate limits, latency | README documents rotations/freshness and 15s dashboard polling. New `providers.py` cooldown handles 429/503 and Retry-After | Cooldown test ensures no second upstream request; serial callbacks/network time can lengthen nominal detection latency | Complete bounded behavior |
| Persisted/deduplicated alerts | NWS snapshots, canonical lightning event key/holds, deterministic advisory ID; frontend notices keyed by event/expiry | Lightning duplicate/delayed-strike tests pass; real durable state unverified. Notices deduplicate during a mounted session, and initial active alerts appear again on reload | Partial |
| Alert source/site/severity/time/reason/action | Official warning details retain instructions; hold displays strike/expiry/source; illustrative advisory has event/window/source/reason/action | Browser checks warning/hold selection and extension; only in-app delivery exists | Partial without live strike provider |
| Lightning radius/countdown/duplicates/out-of-order/expiry | Existing processor preserved; corrected rounded distance constant and future-heartbeat freshness | Regression tests first failed at exactly 10 mi and future heartbeat, then passed. 9, 10, 10.0001, 11 mi, reset/duplicate/older/later/expiry tests pass | Complete deterministic state machine |
| Lightning live/reconnect/restart | Existing `StrikeSource`, `LiveSource(feed)` and `poll_source` form the adapter boundary; DB state and isolated replay already exist | No verified/licensed provider payload, credentials, reconnect cursor or running adapter. HTTP refuses live strike injection. Thunderstorm warnings are not substituted | Missing live integration / externally blocked |
| No confident all-clear with unavailable feed | Independent coverage and hazard state; expiry only clears lightning | Backend/frontend stale/unavailable/independent-hazard checks pass; unknown monitoring remains visible | Complete deterministic behavior |
| River-specific heavy-overnight-rain signal | New USGS NHD StreamRiver query within 1 km; cached geographic context; ≥25 mm modeled rainfall over latest completed local 18:00–06:00 night | Actual query returned 2 nearby flowlines for EIA 663. Location threshold, complete rainfall, stale/null inputs tested; 23/25-hour dates handled via UTC window endpoints. No plant-name inference | Partial: proxy advisory, not measured river flooding |
| Flood limitations and official separation | Advisory says modeled rainfall/context, not official warning; no-match is not absence of exposure | No floodplain, bank survey or river gauge integration. Official NWS products stay independent | Explicit remaining gap |
| Automatic 18:00 local/DST briefing | Existing scheduler now default job; deterministic template adds forecast periods, precautions, advisories and missing layers | Eastern/Central/DST, next-day dates, duplicates and live/replay tests pass. Database uniqueness exists; actual scheduled delivery not observed | Partial / externally blocked |
| Briefing persistence, inbox, restart/retry | PostgreSQL body/facts; new connected frontend inbox; current-local-day catch-up and idempotent schedule | API schedule tests pass; real worker/inbox after restart not verified. Does not backfill previous missed local dates | Partial |
| Manual demonstration without waiting | Existing isolated replay generation plus new live-fact, unpersisted `/api/briefings/preview` | Before-18:00 preview test proves no delivery date reserved; browser preview labeled not delivered | Complete preview behavior |
| Delivery channel | In-app supervisor inbox; no external channel existed | No SMS/email/push sending added; sponsor acceptance of in-app delivery still unresolved | Complete channel implementation; sponsor interpretation open |
| Report description/category/photo/site/location | Existing APIs hardened with actual decoding; required and legacy categories supported by migration 004 | Valid JPEG/PNG/WebP, corrupt/truncated/spoofed/oversize uploads, coordinate/note/category validation all pass | Complete bounded validation |
| Capture/upload and adjustable map pin | New `CrewWorkflow.jsx`, photo capture/upload input, Leaflet draggable/clickable pin and keyboard coordinates | Chromium exercised form/pin coordinates, HTTP submission, shared history and resolution through isolated fixtures | Complete local UI behavior |
| Report persistence across devices/restarts | PostgreSQL bytes and metadata remain canonical; no temporary upload path introduced | Shared-client API tests use memory; two new opt-in DB checks cover new app instances and resolution, but cannot run without DATABASE_URL | Externally blocked acceptance |
| Searchable/filterable geographic history, resolved status | Existing resolution preserved; category/status/text/UTC-since filters added; pins and photos remain in history | Filter/resolve/API tests and browser history flow pass; current frontend filters are per selected site | Complete bounded API/UI behavior |
| Identity/access | No identity/access controls existed in inspected baseline | No authentication introduced; local prototype access only. Not certified or publicly deployed | Missing identity; no existing controls bypassed |
| Supervisor map/ranking/filters/consistency | Preserved Leaflet, ranked list, legend, independent feed coverage; connected reporting/advisory/model/inbox paths | Holds > severe warnings > other alerts > reports/advisories > gaps/model/weather. Within equal groups model precedes heat. Marker/list/detail selection and automatic update behavior pass | Complete local presentation; live persistence unverified |
| Genuine trained ML and bounded 0–10 inference | Existing trusted logistic artifact retained; `predictions.py` invokes actual fitted model on full provider DAILY inputs | Artifact hash matches saved results; actual live-input output 0.06/10 for EIA 663 on 2026-10-19; fitted contributors reconstruct probability | Complete inference path, persistence blocked |
| Historical sources/target/time split/baseline/evaluation | Existing builder/train/results inspected: 59,184 county-days, selected reported county severe events; 2022 train, 2023 validation, 2024 test; preprocessing fitted on train | Saved AP 0.1243 vs constant 0.0158; precision 0.1380, recall 0.4455 at threshold 0.05. These are existing recorded metrics, not new measurements by this audit | Partial reproduction |
| Reproducible training/model persistence | Preserved source downloads, county verification, chronological training, saved artifact; README/ML docs give full commands | Original ignored dataset/manifest/crosswalk absent; full historical metric reproduction not run. No synthetic replacement or retraining on fixtures | Externally needed artifacts/data reconstruction |
| Current and forecast scoring | Today and tomorrow use separate complete local-day forecast summaries, explicit units and dates; nulls for unavailable/stale inputs | Saved-model tests verify distinct dates, provenance and units. Today's value is a full-day forecast, never a current-instant reading | Complete bounded computation; DB storage unverified |
| Geographic/range/model limitations and contributors | Range warnings/probability/geography get dedicated storage columns; UI/briefings label unknown or outside training counties; contributors are log-odds, not causes | Geographic flag computes only with original verified mapping and matching dataset manifest. These files are absent; unknown remains explicit | Partial geographic verification |
| No rules presented as ML / authoritative safety rules | Model score is 10× genuine probability; rainfall/heat rules separately labeled; official holds/warnings stay higher priority | No heuristic score fallback exists. Observed-weather historical evaluation does not establish next-day forecast accuracy | Complete deterministic separation |
| Durable failures/restarts and honest missing states | Persistent-cache retention on refresh failure added; 503 for missing DB, 502 without upstream cache, 404 unknown API; live/replay separated | Default suite and actual Flask HTTP checks pass. Durable SQL/restarts pending credentials; no silent demo substitution | Partial durable verification |
| Secrets/setup/credits | Added name-only `.env.example`; pinned Pillow/tzdata; README commands and AI/data/library credits | No .env content was read or printed. Existing human-team AI usage and hackathon timing eligibility cannot be certified here | Setup supplied; team attestations open |

## Verification actually performed

- Baseline backend tests: 101 passed, 11 database checks skipped; initial full
  collection failed because ML packages were not installed. A local `.venv` now
  contains the pinned backend and model dependencies. Python 3.13.14 was available;
  the trained artifact specifies 3.12.10 and README recommends 3.12 for the team.
- Final default Python run: **162 passed, 14 skipped**. Thirteen skipped checks
  require PostgreSQL; one requires the ignored historical ML dataset. No failed
  test was deleted or hidden. Exact-radius/future-clock regression checks were
  run failing first, then fixed. The final DST advisory cases pass as well.
- PostgreSQL opt-in run was attempted: **159 passed, 1 skipped, 1 failed, 10 setup
  errors**; all 11 database failures were `DATABASE_URL is not configured`.
  No migration or seed ran against shared application records. Two additional
  opt-in database checks were subsequently added; these remain unverified.
- Frontend production build passed; **14 frontend behavior checks passed**.
- Chromium HTTP-fixture exercise passed submission, pin coordinates, history,
  resolution, unpersisted preview, warning selection, hold extension/countdown,
  zero scores, polling errors/retention and file/live isolation. Desktop 1440×1100
  and mobile 390×844 layouts passed overflow/JavaScript checks; screenshots inspected.
- Actual Flask app on **5127** returned `database:not_configured`; live storage
  503; unknown API paths including `/api` 404; 55 unique real inventory rows with
  unavailable coverage. The actual-app Chromium inventory check passed desktop/
  mobile map/layout and disabled shared-write states. Port 5000 was an older app
  instance and its database-connected response was excluded from branch evidence.
- `python -m scripts.verify_providers --site-id 663` passed at about **1:59 AM ET
  October 18** with actual Open-Meteo (120 hourly entries, local daily dates,
  Celsius/mm/km/h), NWS (0 active records), USGS (2 flowlines) and saved model
  inference (0.06/10 for Oct 19, model `county-weather-logreg-277e4566fcdb`).
  The check wrote no database records and supplies no application fallback.
- Operational JSON fixtures regenerated with real encoded test images and the
  updated briefing template. `git diff --check` passed before final documentation.
- No clean-clone credentialed startup, actual shared-device/restart report demo,
  real 18:00 scheduled delivery, historical dataset rebuild, live strike feed,
  sponsor approval, commit, push, merge or deployment is claimed.

## Setup / remaining handoff

Follow README and [DEMO.md](DEMO.md). Required local input: DATABASE_URL, entered
privately in the ignored `.env`. Apply new **004/005** migrations via
`python -m scripts.seed_database` in coordination with the shared database owner,
then start **one** `python -m backend.worker`. Configure a descriptive optional
NWS_USER_AGENT. Open-Meteo/USGS/NWS bounded requests used here need no added key.

To complete acceptance: run `python -m pytest -q --run-database`; exercise report
sharing/restarts and actual briefing inbox delivery; populate all 55 sites through
the worker; restore the matching ML manifest/county mapping; obtain and verify a
licensed live strike feed adapter. River-gauge/floodplain and active-fire evidence
remain absent. The sponsor's in-app/replay/model interpretations remain unresolved.
