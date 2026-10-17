# PlanIT Control

SwampHacks XII starter for a utility-site environmental safety platform. Stack: React/Vite, Flask, Tiger Data PostgreSQL, and a separately started Python ingestion worker. Historical ML remains a separate unfinished workstream.

**Integration in progress.** The backend persists weather and NWS official
warnings for 55 plants, composes a stored evidence-ranked Outlook, and supplies
repositories for B/C workflows. Live strike ingestion, report upload APIs,
briefing scheduling and a trained model remain unfinished. See
[the short backend handoff](docs/BACKEND_HANDOFF.md) and docs/WORKSTREAMS.md.

## Run locally

Requires Python 3.11+ and a Node version supported by the pinned Vite release (Node 22.12+ is a suitable baseline).

From the repository root:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m flask --app backend.app:create_app run --port 5000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the Vite URL printed in the terminal (normally http://localhost:5173). The Vite proxy forwards /api to Flask. The demo file mode shows 55 **real** plant records from EIA's 2025 inventory without needing a database. Click Fetch current weather for an actual provider request; it may take several seconds. Demo describes site storage, not fabricated weather.

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
arguments select a subset. A failed/partial one-pass run exits nonzero and keeps
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
current bounded callback. Briefing and prediction jobs are not implemented yet.

`GET /api/outlook?mode=live` returns all plants with stored weather, official
warnings, available saved holds/reports/model outputs, provenance, units, valid
times, retrieval times and monitoring coverage. Its evidence ranking prioritizes
holds and official warnings above model signals. It never requests provider
data. Use it for the upcoming site-by-time frontend matrix. Site-specific
`/api/sites/{id}/evidence` and aggregate `/api/readiness` are also read-only.
`mode=demo` returns file-based plant records and explicitly unavailable stored
weather. Existing manual weather fetch remains available; database-mode manual
fetches also persist their results. See docs/API_CONTRACT.md for exact fields.

Weather covers three UTC calendar days. The current fields are modeled current
conditions; hourly fields are forecasts. Apparent temperature is not NWS heat
index. Shallow modeled soil moisture is not a measurement of trafficability.
Missing values stay missing. Official NWS flood/fire-weather products are now
monitored, but no river proximity, gauges or active-fire detections are inferred.
Lightning feeds, photo upload/reporting APIs, briefings and trained model
predictions still require their owners' integrations. The next-day heat index is
calculated from modeled temperature/RH using the published NWS formula and kept
separate from provider apparent temperature; no operational heat threshold or
soil trafficability threshold is invented.

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
```

The default tests cover source uniqueness, explicit storage modes, errors,
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
They do not verify a live strike feed, image upload validation, scheduled
delivery, training/evaluation or the connected frontend.

## Recreate the source selection

```bash
python -m pip install -r requirements-data.txt
python -m scripts.prepare_sites
```

This downloads the official 2025 annual EIA archive if absent, inspects the actual Plant and Operable generator sheets, selects plants with OP generators, deduplicates plant codes and writes 55 records. The raw download is about 24 MB and is excluded from Git and the starter package. EIA-860M workbook requests timed out or returned non-workbook content during setup; the verified annual archive was used instead. Monthly data can replace the input later with a separate verified importer.

data/source_checks/noaa_headers.json contains the actual 2024 NOAA details-file column names, retrieved from the gzip stream. No historical model has been trained. The ML owner should use CZ_TYPE, STATE_FIPS and CZ_FIPS carefully; county names in the plant data need a verified FIPS crosswalk.

## Structure and parallel work

- frontend/src: App, SiteMap and API helper. Split the forthcoming timeline and report form into owned components.
- backend: Flask app, database adapter, verified weather fields and initial SQL schema.
- scripts: source preparation and database seeding.
- docs: interface contract, ownership and checkpoint plan.
- tests: foundation behavior checks.

The manual provider helper still has a 15-minute in-process cache. Database
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
- Derived heat-index formula: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml (applied to modeled Open-Meteo inputs, not an official NWS observation).
- Leaflet, React, Vite, Flask, Psycopg, pandas, openpyxl and scikit-learn retain their respective licenses.
- Map tiles and data: OpenStreetMap contributors; preserve the visible attribution and tile usage policy. An offline/restricted network may prevent map tiles loading even though the site list still works.
- AI assistance: OpenAI ChatGPT/Codex assisted with architecture, source inspection, scaffolding and checks. Add every other coding tool your team actually uses before submitting.

Sponsor entry requires real working use. The app never labels missing hazard monitoring as safe.
