# PlanIT Control

SwampHacks XII starter for a utility-site environmental safety platform. Stack: React/Vite, Flask, Tiger Data PostgreSQL, and a separate future Python ML/worker process.

**Foundation only.** This is a runnable starting point, not a completed safety product. It has no hazard model, official alert ingestion, live strike monitoring, reporting or briefing scheduler yet. See docs/WORKSTREAMS.md.

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

The seed command creates tables and upserts by the stable source plant ID. It does not delete existing records. No real connection was available during scaffold creation because DATABASE_URL was absent. A successful future seed and database-mode response are required before claiming Tiger Data integration.

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

The tests verify source-record uniqueness, explicit demo mode, database failures without silent fallback, invalid modes, unknown sites and stale-weather behavior. They do not verify an unavailable Tiger Data account or unfinished alert/ML features.

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

Weather is cached in memory for 15 minutes in this starter. A failed refresh retains a previous response with an explicit stale flag. Restarting Flask clears this cache. The next ingestion milestone should persist observations and forecast snapshots in Tiger Data and move ingestion into a worker.

## Sources and credit

- EIA-860 2025: https://www.eia.gov/electricity/data/eia860/
- Actual archive: https://www.eia.gov/electricity/data/eia860/xls/eia8602025.zip
- Open-Meteo: https://open-meteo.com/en/docs — modeled weather; preserve attribution and review current service limits.
- NOAA Storm Events: https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/
- Leaflet, React, Vite, Flask, Psycopg, pandas, openpyxl and scikit-learn retain their respective licenses.
- Map tiles and data: OpenStreetMap contributors; preserve the visible attribution and tile usage policy. An offline/restricted network may prevent map tiles loading even though the site list still works.
- AI assistance: OpenAI ChatGPT/Codex assisted with architecture, source inspection, scaffolding and checks. Add every other coding tool your team actually uses before submitting.

Sponsor entry requires real working use. The app never labels missing hazard monitoring as safe.
