# Supervisor dashboard handoff

## Current integration - October 18, 2026

The default dashboard now uses plain labels, two-decimal today/tomorrow model
indices, crew lightning recording/history and an automatically generated
tomorrow-report display. Preview GET and observation GET/POST routes are
documented in API_CONTRACT.md. Shared tables/dependencies are unchanged.
The small Debug button exposes metadata, contributors, full report text, detailed
coverage and storage selection. Its preference survives reload; critical missing
feeds and stale conditions stay visible with Debug off. Lightning observations
require confirmation at the selected plant now and persist holds within 10 miles;
they do not connect an automatic strike feed. Previews do not count as delivery.

Latest verification: 199 Python/database checks passed, one skipped; 17 frontend
checks and build passed; HTTP-fixture and actual-database browser checks passed
on desktop/mobile, including score/API equality and report auto-load. All 55
sites have actual saved today/tomorrow predictions at verification. One worker
is active; scheduled persistence/deduplication is tested, but actual wall-clock
18:00 delivery is not yet observed. See SETUP_STATUS.md for remaining gaps.

## Archived foundation-only handoff (superseded above)

The frontend consumes the existing API contract; no backend, database schema,
dependencies, or shared response shapes were changed.

## Connected behavior

- Tiger Data storage is selected on initial load. File inventory remains an
  explicit option with unavailable monitoring; database failures never switch it.
- `/api/outlook?mode=live|demo` supplies the attention queue, numbered/color-coded
  Leaflet map, official warnings, lightning holds, forecast summaries, unresolved
  report evidence, and genuine saved predictions. Stored evidence refreshes every
  15 seconds after the previous request completes. No provider weather requests
  are made by the dashboard. `/api/readiness` and `/api/health` refresh initially
  and every fourth cycle.
- Active holds outrank severe warnings, other warnings/advisories, reports, and
  model/weather signals. Rows show reasons and independent feed coverage.
- A persisted `hold_until` drives a one-second countdown using the server
  snapshot clock offset. A later expiration extends it. Expiry clears only the
  hold; unexpired official warnings, reports, and unavailable feeds remain.
- New stored alerts and extended holds produce visible, accessible in-app
  notices. Official warning instructions and source/validity are available in
  site details. The UI does not claim crew push/SMS delivery.
- Model cards use only actual next-local-day `prediction` records. Zero displays
  as 0.0; absent, invalid, or out-of-date predictions display unavailable. The
  index is labeled experimental and never overrides official alerts.
- The briefing panel shows the requested 18:00 local delivery window and its
  next-day forecast target, with delivery explicitly unavailable. This is not a
  generated, stored, scheduled, or delivered briefing.
- Forecasts retain source, retrieval/valid time, units, and freshness. Failed
  polling retains prior evidence and marks coverage stale. Expired snapshots
  become stale locally even while requests fail.

## Exact resources still missing

| Requirement | Missing resource in this checkout | What it prevents |
|---|---|---|
| New lightning alerts | Verified strike provider and source/time validation plus geographic 10-mile ingestion connected to `store_lightning_event` | Detecting real nearby strikes and starting/extending holds automatically. Storage/presentation alone do not do this. |
| Instant crew notification | Server event transport and an agreed crew delivery channel | The current interface can show new stored alerts on its next 15-second poll, plus request time; it cannot promise instant or background crew delivery. NWS rotation adds ingestion latency. |
| Overnight river-flood advisory | Verified river-site mapping, observed overnight precipitation/window, and documented advisory threshold (and gauges if required) | Inferring a river-specific overnight-rainfall warning. Existing official NWS flood products and tomorrow's forecast rain are shown separately. |
| 18:00 next-day briefing | Deterministic generation, site-IANA-timezone scheduling in the existing worker, and the planned `GET /api/briefings?site_id=...` inbox API with an agreed response envelope | Generating/delivering briefings and retrieving saved bodies in the browser. `db.save_briefing`/`list_briefings` and uniqueness constraints already exist. No speculative HTTP response contract was added. |
| Actual 0–10 site predictions | Forecast-to-feature inference job using the saved model and `db.save_prediction`, registered with the existing worker | Populating the score cards. The frontend will display real records once the current Outlook returns them. No substitute weather-rule scores are generated. |
| Fresh evidence | A continuously running `python -m backend.worker` process | Keeping weather/NWS snapshots current. Polling the dashboard does not refresh providers. |

The current trained model targets selected reported county-day severe-weather
events. It is not a validated model of worker injury or every on-site hazard;
the UI labels that scope explicitly.

## Changed frontend files

`frontend/src/App.jsx`, `DashboardPanels.jsx`, `useOutlook.js`, `outlook.js`,
`SiteMap.jsx`, and `styles.css`; contract-shaped test fixtures and Node checks
are under `frontend/tests`. Existing U.S. zoom constraints and the user's header,
notice-banner, and favicon changes are preserved.

## Verification commands

From `frontend/`: `npm.cmd run build`, `node --test tests/outlook.test.mjs`,
`node tests/dashboard.browser.mjs`. To exercise the real database responses,
start Flask separately and run
`node tests/dashboard.browser.mjs --live http://127.0.0.1:5000`.

The browser checks cover map rendering, ranked selection, flood evidence, a
ticking/extended countdown, saved zero scores, automatic polling, failed-poll
retention, file-mode isolation, and desktop/mobile layout. Synthetic fixtures
are confined to the test server; live mode performs read-only API requests.

## Verified in this session

- Frontend production build and `git diff --check`: passed.
- Node behavior checks: 13 passed.
- Headless Chrome fixture checks: passed, including a failed connection retry
  preserving an active hold and visible notices for newly received alerts.
- Headless Chrome against a temporary local Flask server and the configured
  Tiger Data database: passed on desktop and 390-pixel mobile layouts. Confirmed
  55 plants, actual map markers, unavailable saved predictions and briefing
  delivery, and zero calls to the provider-refresh weather endpoint.
- Live stored weather and official monitoring were stale. No ingestion worker
  was started and no database writes or schema changes were made. The temporary
  verification server was stopped afterward.

These checks establish frontend behavior and database reads. They do not prove
live strike ingestion, crew notification delivery, flood advisory generation,
scheduled briefing delivery, or forecast-to-model persistence.
