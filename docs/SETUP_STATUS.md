# Setup status

## Completed

- Local Git repository initialized on main.
- React/Vite frontend and Flask backend scaffolded.
- Production frontend build succeeds.
- Six focused backend tests pass.
- Official EIA 2025 annual Plant and Operable generator sheets inspected.
- 55 distinct plants selected across five southeastern states; provenance and archive hash recorded in data/sites.json.
- Actual Open-Meteo response fields verified, including hourly soil moisture. Flask's weather endpoint returned HTTP 200 for a selected real EIA plant.
- NOAA 2024 details-file header read from its actual gzip stream; fields saved in data/source_checks/noaa_headers.json.
- API contract, module ownership, source-recreation procedure, environment example and Tiger Data seed command provided.

## Requires your account configuration

- DATABASE_URL is absent. Enter the Tiger Data URI locally in .env, then run python -m scripts.seed_database and verify database-mode sites.
- No external GitHub repository has been created or pushed. This is a local repository and a portable source package.
- Gemini and FIRMS credentials are not configured. These do not block the current foundation.

## Verification limits

A browser-level smoke test was attempted but could not run: the Chromium executable was unavailable and its download returned an invalid archive. The frontend compiles, but map rendering, mobile layout and click behavior still need a manual browser check using the README procedure. No screenshots or browser success are claimed.

Only a bounded NOAA header read was performed. No full training archive, ML dataset or model exists yet. Current weather caching is in memory, not persisted observations. Alert monitoring, reports and scheduled briefings remain next workstreams.

## First manual check

Run both servers, confirm 55 demo-file sites, select a plant, fetch weather, inspect source/units, test a narrow mobile window, and switch to database mode after seeding Tiger Data. If map tiles are unavailable, use the site list; the tile service is a separate network dependency.

