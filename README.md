# PlanIT Control

SwampHacks XII starter for a utility-site environmental safety platform. Stack: React/Vite, Flask, Tiger Data PostgreSQL, a separately started Python ingestion worker, and a saved historical ML baseline.

The dashboard combines stored weather/NWS evidence for 55 plants with photo
reports, geographic report history, a supervisor briefing inbox, and a genuine
experimental model index. One worker handles ingestion, stream context, daily
model predictions and site-local 6 PM briefings. Live strike monitoring remains
unconnected. See the [requirement audit](docs/requirements-audit.md) for evidence
and gaps and the [demo walkthrough](docs/DEMO.md).

The October 18 follow-up connected this checkout to Tiger Data, applied
migrations 003–005 and verified stored forecasts and today/tomorrow indices for
all 55 plants. Credentials remain local in ignored `.env`; a fresh clone still
needs its own configuration. Actual 6 PM delivery remains to be observed.
See docs/SETUP_STATUS.md for current verification.

Rows now show today's and tomorrow's experimental daily indices. Weather
callbacks compute both immediately after storing the site's forecast; manual
refresh also updates them. The model uses entire local-day features and cannot
produce an instantaneous score from current readings.

Tomorrow's rainfall prefers the complete provider DAILY value for the exact
local date/timezone and mm units, independently of hourly coverage. The legacy
hourly fallback follows preceding-hour intervals. Heat/soil still require all
23/24/25 local-day hours; missing values explain their cause. Each successful
weather JSON snapshot records the next-day summary/rainfall alongside raw data.
Zero rainfall is 0 mm; unavailable rainfall stays null. The cache refreshes after
site-local midnight, and dashboard reads account for concurrent worker writes.

## Run locally

Use Python 3.12 (the saved artifact was trained under 3.12.10), and a Node version
supported by the pinned Vite release (Node 22.12+ is a suitable baseline). This
session's checks used Python 3.13.14 with the exact pinned ML package versions;
no model or dependency pins were replaced.

From the repository root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt -r ml/requirements.txt
python -m flask --app backend.app:create_app run --port 5000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the Vite URL printed in the terminal (normally http://localhost:5173). The Vite proxy forwards /api to Flask. The dashboard defaults to Tiger Data and automatically reads stored evidence; run the separate worker for fresh conditions. The file-inventory option shows 55 **real** EIA plants without a database, with monitoring explicitly unavailable. It never silently replaces a failed database connection. See [the frontend handoff](docs/FRONTEND_HANDOFF.md) for functionality and outstanding integrations.

The checked-in inventory establishes plants with an operating generator in that source year. It does not verify current operating status. The selection covers FL, GA, AL, MS and LA; Florida is restricted to known Eastern-time counties. See data/sites.json for provenance and SHA-256.

## Connect Tiger Data

1. Create or select your Tiger Data PostgreSQL service.
2. Copy `.env.example` to `.env` at the repository root. Enter its database connection URI as DATABASE_URL. Keep TLS parameters from the provider. Do not paste the URI into chat or commit it.
3. With the Python environment active, run:

```bash
python -m scripts.seed_database
```

4. Restart Flask if .env changed. Confirm http://localhost:5000/api/health reports database connected, then confirm http://localhost:5000/api/sites?mode=live returns sites. Select Tiger Data database in the frontend.

The seed command creates the base tables, applies numbered additive migrations,
and upserts by stable source plant ID. It does not delete existing records.
Applied migration checksums prevent silently changing previously applied SQL;
add a new migration for later schema changes. The connection and database-mode
retrieval must be checked against your own configured service.

## Run ingestion and read the Shift Outlook

After seeding, fill the stored forecasts once:

```bash
python -m backend.worker --once
```

For a bounded single-site check, add `--site-id 663`. Multiple `--site-id`
arguments select a subset for ingestion, context, predictions and briefings.
A failed/partial one-pass run exits nonzero and keeps
previously stored snapshots. Provider failures are recorded per site.

Then start exactly one regular worker in its own terminal:

```bash
python -m backend.worker
```

Flask never starts the worker. A PostgreSQL session advisory lock excludes a
second worker connected to the same database. Regular runs rotate one plant
per 15-second interval, revisiting all 55 in roughly 15 minutes plus network
time. This bounds each weather callback so other registered jobs can run.
NWS official monitoring rotates one plant per five-second job interval (plus
network time), with a 10-minute feed freshness rule. Its job is separate from
the weather rotation so official checks need not wait for a full weather pass.
Job outcomes are stored in worker_runs; snapshots and ingestion freshness
survive Flask restarts. The worker is serial, so a due job can wait for the
current bounded callback. Prediction work rotates one site per 15-second interval
and scores today and tomorrow from provider DAILY values. USGS stream context
also rotates every 15 seconds and caches successful geometry queries for 30 days.
Briefings are checked every 30 seconds. All five jobs are registered by default.
HTTP 429/503 responses establish a per-provider cooldown using Retry-After
(60 seconds when absent); retained cached evidence stays visibly stale.

Expected NWS detection latency is up to one roughly five-minute rotation plus
provider/network/database delays, then up to 15 seconds for the dashboard poll.
Weather/model/context rotations take roughly 14 minutes plus processing time for
55 plants. These are polling targets, not guaranteed immediate detection.
Freshness is 30 minutes for weather/model, 10 minutes for NWS and 30 days for
static stream geometry. Provider failures remain visible independently of alerts.

`GET /api/outlook?mode=live` returns all plants with stored weather, official
warnings, available saved holds/reports/model outputs, provenance, units, valid
times, retrieval times and monitoring coverage. Its evidence ranking prioritizes
holds and official warnings above model signals. It never requests provider
data. The frontend uses it for the ranked queue, map, and selected-site evidence. Site-specific
`/api/sites/{id}/evidence` and aggregate `/api/readiness` are also read-only.
`mode=demo` returns file-based plant records and explicitly unavailable stored
weather. The dashboard polls this stored-data route every 15 seconds and never
calls the provider-refresh weather endpoint. Site selection reads the already
loaded evidence. The older weather endpoint remains available for explicit API
requests. See docs/API_CONTRACT.md for exact fields.

Weather covers three site-local forecast days and two past days. Timestamps are
Unix UTC; daily boundaries follow each site's IANA timezone. Current fields are
modeled conditions; past hourly rainfall is a modeled proxy and future hourly
fields are forecasts. Apparent temperature is not NWS heat
index. Shallow modeled soil moisture is not a measurement of trafficability.
Missing values stay missing. Official NWS flood/fire-weather products are now
monitored. USGS NHD stream/river centerlines within 1 km supply location context.
An illustrative advisory requires that context AND at least 25 mm of modeled
rainfall in the latest completed 18:00–06:00 local night. Unknown/partial/stale
inputs cannot produce a negative advisory result. This is not a floodplain,
river gauge or official flood warning. Gauges and active-fire detections remain
unconnected. The next-day heat index is
calculated from modeled temperature/RH using the published NWS formula and kept
separate from provider apparent temperature. Illustrative forecast planning
periods flag hourly derived heat index ≥103 °F, rain ≥10 mm, or gusts ≥50 km/h;
these are planning signals, not official operational work policies. No soil
trafficability classification is inferred.

Photo reports accept JPEG/PNG/WebP up to 5 MiB and 25 million pixels, verify
structure and pixel decoding, and store bytes with metadata in PostgreSQL.
Use the site map's draggable pin or keyboard coordinate fields. History filters
support description, category and active/resolved state; resolution preserves
history and photos. Other sessions refresh every 15 seconds. Authentication was
not present in the baseline and has not been added.

The in-app supervisor inbox is the delivery channel; no external sending channel
existed. A nonpersisted preview works before 6 PM. The scheduler uses zoneinfo,
including DST, and the database enforces one briefing per site/delivery date/event
mode. Restart/retry after 18:00 catches up the current local date and never
overwrites an existing briefing. It does not backfill missed previous days.
Replay/manual delivery is separate. Start the worker before 18:00; template
generation includes forecast periods, official alerts, active reports,
illustrative advisories, model limits, missing inputs and planning precautions.

Worker extension factories return `backend.worker.Job` objects and can be
registered with repeated `--job-module package.module:factory_name` arguments.
See docs/coordination/A.md for the interface and owner handoff. Do not start a
separate competing briefing or prediction worker.

## Build one-origin demo

```bash
cd frontend
npm run build
cd ..
python -m flask --app backend.app:create_app run --port 5000
```

Flask serves frontend/dist once it exists. The Flask development server is for local development. Before public deployment, select a proper WSGI server and keep uploads on persistent storage; do not expose a debug console. No public deployment has been created.

## Verify the foundation

```bash
python -m pytest -q
cd frontend
npm run build
node --test tests/outlook.test.mjs
```

Frontend behavior checks cover lightning expiration/extension presentation,
hazard priority, stale coverage, missing versus zero model scores, and local
briefing dates including daylight-saving transitions. Optional browser checks
use an installed Chromium browser without additional npm dependencies:

```bash
cd frontend
node tests/dashboard.browser.mjs
# With Flask running on port 5000, verify the real stored database responses:
node tests/dashboard.browser.mjs --live http://127.0.0.1:5000
# Without database credentials, exercise the actual file inventory:
node tests/dashboard.browser.mjs --inventory http://127.0.0.1:5000
```

Browser fixtures are synthetic test data served only by the test script. They
are never bundled into the app or written to Tiger Data. Screenshots go into
the gitignored frontend/dist/checks directory. PLANIT_BROWSER can specify a
Chromium executable when Chrome/Edge is not found automatically.

The default backend tests cover source uniqueness, explicit storage modes, errors,
stored-data polling, freshness/missing fields, forecast local-day/DST summaries,
official-warning composition/ranking, bounded ingestion and worker failure
handling. PostgreSQL integration checks are opt-in:

```bash
python -m pytest -q --run-database
```

These checks load DATABASE_URL locally, create a uniquely named test schema
inside a transaction, and roll it back. They verify real migrations, repeated
seeding, snapshot/event deduplication, replay filtering, shared photo bytes,
local-day briefing uniqueness, prediction provenance and advisory locking without
changing application records. The role needs permission to create a schema.
These tests do not establish a live strike feed or observed 6 PM delivery. The
default suite verifies image decoding, report APIs, scheduler boundaries and
replay isolation; browser fixtures exercise report submission/resolution and
briefing preview. The default suite also checks the saved ML
artifact, inference failure states and model contributions. Full historical
dataset and tree-result reproduction require the ignored prepared data; see
docs/ML.md and ml/experiments/gbt_v1/REPORT.md.

A bounded actual-provider check, independent of database configuration, is:

```bash
python -m scripts.verify_providers --site-id 663
```

It requests actual Open-Meteo DAILY weather, USGS context and NWS point alerts,
then invokes the saved model. It writes no database records and never supplies
an application fallback. For full ML reproduction, install requirements-data.txt,
run `python -m ml.build_dataset --limit 0`, then `python -m ml.train` and
`python -m ml.verify`. These commands download historical data and replace the
local artifact/results when training; run them on a separate feature branch.
Without the original manifest and verified county mapping, geographic training
membership remains unknown, explicitly shown in the UI. Historical observed-
weather metrics do not establish current/next-day forecast performance.

## Recreate the source selection

```bash
python -m pip install -r requirements-data.txt
python -m scripts.prepare_sites
```

This downloads the official 2025 annual EIA archive if absent, inspects the actual Plant and Operable generator sheets, selects plants with OP generators, deduplicates plant codes and writes 55 records. The raw download is about 24 MB and is excluded from Git and the starter package. EIA-860M workbook requests timed out or returned non-workbook content during setup; the verified annual archive was used instead. Monthly data can replace the input later with a separate verified importer.

data/source_checks/noaa_headers.json contains the actual 2024 NOAA details-file
column names, retrieved from the gzip stream. The saved model uses 54 counties
covering the 55 plants and 2022–2024 county-day data. See docs/ML.md for the
verified crosswalk, label construction, evaluation and reproduction limitations.
Prepared training data are ignored by Git and are not included in this clone.

## Structure and parallel work

- frontend/src: App, SiteMap and API helper. Split the forthcoming timeline and report form into owned components.
- backend: Flask app, database adapter, verified weather fields and initial SQL schema.
- scripts: source preparation and database seeding.
- docs: interface contract, ownership and checkpoint plan.
- tests: foundation behavior checks.

The provider helper still has a 15-minute in-process cache. Database
storage additionally retains complete provider snapshots in weather_snapshots,
with latest attempt/success metadata in weather_ingestion. A failed refresh
never replaces the prior snapshot with empty/zero conditions. The original
observations table is retained but is not populated by this snapshot pipeline.
The stored Outlook marks retrieval/current conditions over 30 minutes old or a
failed latest refresh as stale; missing required weather values/units are
partial. NWS has separate 10-minute freshness and preserves unexpired warnings
after refresh failure. Missing required hazard integrations remain disclosed.

## Sources and credit

- EIA-860 2025: https://www.eia.gov/electricity/data/eia860/
- Actual archive: https://www.eia.gov/electricity/data/eia860/xls/eia8602025.zip
- Open-Meteo: https://open-meteo.com/en/docs — modeled weather; preserve attribution and review current service limits.
- NOAA Storm Events: https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/
- NWS official point alerts and API: https://www.weather.gov/documentation/services-web-alerts and https://www.weather.gov/documentation/services-web-api
- USGS National Hydrography Dataset: https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/6 (StreamRiver proximity context, not floodplain/gauge observations).
- Derived heat-index formula: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml (applied to modeled Open-Meteo inputs, not an official NWS observation).
- Leaflet, React, Vite, Flask, Psycopg, Pillow, tzdata, pandas, openpyxl and scikit-learn retain their respective licenses.
- Map tiles and data: OpenStreetMap contributors; preserve the visible attribution and tile usage policy. An offline/restricted network may prevent map tiles loading even though the site list still works.
- AI assistance: OpenAI ChatGPT/Codex assisted with architecture, source inspection, scaffolding and checks. Add every other coding tool your team actually uses before submitting.

Sponsor entry requires real working use. The app never labels missing hazard monitoring as safe.
