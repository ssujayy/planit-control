# Setup status

## Readable dashboard, lightning recording and reports - October 18, 2026, 3:35 AM ET

- Fixed the main model card's one-decimal rounding. Cards, queue, map and newly
  generated briefings now show the saved daily score to two decimals, including
  genuine zero. Today and tomorrow remain separate; no model or score rescaling.
- Added crew lightning recording at the selected plant with explicit observation
  confirmation. Fixed source/server time, retry deduplication, 10-mile processing,
  persisted 30-minute holds/extensions and retained hold history use the existing
  database tables. Manual observations remain labeled crew evidence. Replay and
  provider impersonation are rejected; automatic monitoring stays unavailable.
- Tomorrow's report loads automatically and refreshes from stored information.
  It shows a generated summary, next-day temperature/derived heat/rain/gusts/soil,
  official warnings, today's lightning activity, unresolved crew reports, missing
  information and the experimental score. The same template supplies the one
  scheduled report per site/date at 18:00 local. Previews never write or reserve
  delivery; legacy delivered records remain readable. No migration needed.
- Simplified default labels, removed infrastructure/provenance comments from
  normal view, increased reading sizes, and added a small persistent **Debug**
  button. Debug shows model metadata/contributors, sources, freshness details,
  full generated report, coverage and the file-inventory selector. Missing feeds,
  stale conditions, official instructions and model limitations remain visible.
- `python -m pytest -q -p no:cacheprovider --run-database`: **199 passed, 1 skipped**
  (ignored historical experiment data). The cache override avoids Windows cache
  permissions. **17 Node checks passed**; frontend production build passed.
  Chromium fixture flows verified recording, history, report auto-load, Debug
  persistence, alerts/polling and mobile layout. Real database browser checks
  verified all 55 today/tomorrow scores, main-card/API equality, site switching,
  complete tomorrow metrics, automatic report cards, Debug, map and mobile layout.
  Desktop/mobile report screenshots were inspected. Production lightning records
  were not fabricated: persistence tests used isolated PostgreSQL schemas and
  rolled back, while browser recording used labeled synthetic HTTP fixtures.
- Current app remains http://localhost:5173 and http://localhost:5000. Replaced
  two competing Flask instances with one current backend and restarted the one
  leased worker. No dependency/schema/credential changes, commit, push or deploy.

Remaining: automatic lightning detection requires a verified strike data feed
and adapter; manual recording does not satisfy that live integration. Actual
wall-clock 18:00 delivery has not yet been observed (timezone/DST, persistence
and duplicate prevention are tested). Sponsor and ML geography questions below
remain open. No blocker remains for the four requested local UI/workflow fixes.

## Forecast/model fixes — October 18, 2026, about 2:40 AM ET

This supersedes the earlier missing-DATABASE_URL and unapplied-migration notes.
The human authorized migrating private configuration and replacing old servers.
No credential values were displayed.

- This checkout now has a gitignored `.env`, migrated from the older working
  checkout's private configuration. `.env.example` remains a blank template;
  the older example files contained placeholders, not usable credentials.
- Tiger Data connects. Migrations **003/004/005** were applied, preserving all 55
  plants. The full real-provider worker pass succeeded: 55 weather forecasts,
  110 today/tomorrow predictions, 55 NWS checks and 55 USGS contexts. The later
  prediction job also saved 110 available results. No briefings were due.
- Actual stored Outlook verified **55/55 today indices, 55/55 tomorrow indices,
  55/55 tomorrow rainfall, 55/55 derived heat and 55/55 shallow soil moisture**.
  Successful JSON snapshots record next-day rainfall/metric metadata alongside
  raw hourly/DAILY values, with matching local dates and units.
- Root causes: the older app had yesterday's stale, short-horizon snapshots and
  no model outputs; the summary discarded all metrics if hourly coverage was
  incomplete; the queue exposed only tomorrow's index; weather/model rotations
  were independent. Fixed each, plus a concurrent-read freshness race that could
  briefly hide a newly written prediction.
- Rainfall prefers complete DAILY values independently of hourly coverage. The
  legacy fallback sums preceding-hour intervals ending 01:00 through next
  midnight. Heat/soil retain complete-local-day requirements and show specific
  missing reasons. The weather cache refreshes after site-local midnight.
- Weather callbacks immediately save both daily model predictions for that
  site; explicit manual refresh does the same. The repair prediction job stays.
  Rows show both indices, map tooltips include today's index, and missing model
  outputs explain their cause. These are **daily forecast** indices. An
  instantaneous current-reading model needs separately trained/evaluated
  time-aligned subdaily features and labels; the existing model cannot supply it.
- **184 passed, 1 skipped** with `python -m pytest -q --run-database` (the skip
  requires ignored historical experiment data); **15 frontend checks passed**;
  production build passed. Chromium on real Tiger Data verified all 55 daily
  indices, successive site selections with all three tomorrow metrics, map and
  desktop/mobile layout. Fixture browser flows also passed.
- Old PlanIT listeners on 5000/5173 were stopped, including an additional old
  backend discovered during cutover. Current frontend: http://localhost:5173;
  Flask/current production build: http://localhost:5000. One current leased
  worker remains running. Hidden background logs/PIDs live under ignored
  `.runtime/`. No commit, push, merge or deployment.

Remaining challenge gaps include verified live strikes, the original ML
geography manifest/crosswalk, actual observed 18:00 delivery, and sponsor
interpretations below. Database configuration and the reported daily index /
tomorrow forecast display/storage issues are no longer blocked.

## Earlier compliance verification — October 18, 2026, about 2:15 AM ET

Branch `feature/challenge-compliance`, based on clean/up-to-date main. The
repository-wide request authorizes the integration changes across A/B/C/D.
Current evidence is in [requirements-audit.md](requirements-audit.md); the
scaffold-era notes below are archived, not current feature claims.

- Preserved 55 distinct real EIA plants and the Leaflet map. Connected report
  submission with photo/pin, filters and resolution, and a persisted-briefing
  inbox with an explicitly unpersisted preview.
- One worker now registers weather, NWS, USGS stream context, genuine DAILY
  model inference for today/tomorrow and local 18:00 briefing delivery by default.
  Scheduling/replay tests pass; actual scheduled delivery is still unverified.
- Added migrations 004 (report categories and model availability metadata) and
  005 (USGS context). They have NOT been applied to the shared Tiger Data DB.
  Existing migrations are unchanged. Coordinate the application before running
  the seed/migration command on the shared service.
- Source check at about 1:59 AM ET retrieved actual Open-Meteo daily/hourly
  weather, NWS point alerts and two nearby USGS StreamRiver flowlines for EIA
  663. Actual saved model output for Oct 19 was 0.06/10, not simulated. This
  one-site check is not proof of 55-site continuous ingestion or persistence.
- Illustrative flood advisory: nearby mapped stream within 1 km AND ≥25 mm
  modeled rainfall in the latest completed 18:00–06:00 local night. Missing or
  stale inputs leave it unknown. It is not an official warning, gauge or
  floodplain assessment. Official NWS flood/fire-weather warnings remain separate.
- Image validation now verifies structure and decodes pixels; corrupt/truncated
  files are rejected. Required categories preserve legacy `water`/`access` and add
  heat/lightning/flooding/mud. Added Pillow 12.0.0 and tzdata 2025.2 to root pins.
- Fixed exact 10-mile boundary and future feed-clock freshness. Failed manual
  weather refreshes retain a persisted stale snapshot across process restarts.
  Provider 429/503 handling honors Retry-After with a cooldown.
- Default Python/model checks: 162 passed, 14 skipped (13 database checks and
  one ignored historical dataset check). Frontend build and 14 behavior checks
  passed. Chromium fixtures exercised submission, resolution, preview, alert
  transitions, desktop/mobile layouts and map rendering; screenshots inspected.
- Actual checkout ran on port 5127: health `not_configured`, live storage 503,
  unknown API 404, file inventory 55 unique IDs with unavailable coverage.
  Actual-app desktop/mobile inventory browser checks passed. Port 5000 belongs
  to an older app instance; its DB-connected response does not verify this code.
- Opt-in PostgreSQL suite was attempted: DATABASE_URL is absent in this checkout;
  10 setup errors and 1 failure were environmental, with no application DB writes.
  Cross-device/restart persistence and new SQL remain unverified here. A real
  worker was not started; only bounded read-only provider checks ran.

### Remaining gaps / externally needed

- Verified, licensed live strike provider and adapter/checkpoint configuration.
  Existing source protocol/poll function and isolated replay do not meet live
  detection. Do not equate a thunderstorm warning with a strike feed.
- Local DATABASE_URL, shared migration application, real DB suite, report/photo
  cross-device/restart exercise and observed site-local 6 PM delivery.
- Original ML manifest/county mapping and ignored historical dataset. Inference
  works; geographic training membership stays unknown without the verified
  mapping/manifest. Saved historical metrics were not recomputed in this clone.
- No river gauges, floodplain or active-fire detections. NWS fire-weather evidence
  is available. No identity system or external notification channel existed.
- Sponsor questions remain unresolved: acceptable lightning replay, in-app
  delivery channel and county-event proxy model; submission deadline verification
  and crediting any other AI tools used by the human team remain with the owner.
- Clean-clone startup with credentials and permitted hackathon-period eligibility
  are not established by these checks. No commit, merge, push or deployment.

<details>
<summary>Archived scaffold-era notes (superseded by the current record above)</summary>

This is the ONE file for changing facts: what is built, what is blocked, open decisions. Stable rules are in AGENTS.md. Update this file (small edits, with the date and time in ET) instead of editing AGENTS.md. Do not record secrets here.

This is the original scaffold-era record. The current verified backend status
is in [A's coordination log](coordination/A.md). On October 17, 2026, A verified
the configured Tiger Data connection, 55 database-backed plants, 55 persisted
live weather forecasts, NWS monitoring for all 55 and 47 passing backend/database
checks. See [the short handoff](BACKEND_HANDOFF.md) for B/C/D integration. Earlier notes
below about absent DATABASE_URL, memory-only weather and the previous Git branch
describe the scaffold, not the updated state. Frontend/browser limitations,
unconnected strike/report/briefing workflows and the missing model still apply.

## Completed

Last updated: Saturday Oct 17, about 6 PM ET (update when you change it).

## Verified working
- Repository on GitHub (public). Foundation: React/Vite frontend, Flask backend, backend tests, production frontend build.
- 55 distinct plants from the EIA-860 2025 annual inventory (data/sites.json) seeded into Tiger Data. GET /api/sites?mode=live returns them from the database; mode=demo reads the file.
- GET /api/health, /api/sites, /api/sites/{id}, /api/sites/{id}/weather exist and follow docs/API_CONTRACT.md.
- Weather is cached in memory only (15 minutes); restarting Flask clears it.
- ML baseline exists on branch feature/ml (model, results, predict_site, tests, docs/ML.md). Not yet merged into main, and not connected to the backend.

## Not built yet (do not describe these as implemented)
- Official alert ingestion (NWS) and flood advisory
- Lightning hold logic, replay and tests
- Risk status and ranking (risk_status is "not_implemented")
- Crew reports (photo, pin, category) and shared history
- Briefing generation, scheduler and worker process
- Persisted observations and forecast snapshots
- Supervisor ranked list and map status
- Prediction table, county FIPS mapping and wiring of the ML index
- Optional: Gemini briefing rewrite, NASA FIRMS fire detections

## Open decisions (resolve with the team, then record the answer)
- Event mode naming: the API field "mode" (live|demo) is data storage. AGENTS.md section 7 sets event_mode (live|replay) for lightning and replay. Add it to docs/API_CONTRACT.md when the alerts owner builds that endpoint.
- Near-river identification: source, method, and the field to add (needed for the flood advisory).
- Site county FIPS: add a verified crosswalk column or lookup so the backend can tell whether a site is inside the ML training counties.
- Prediction storage: columns beyond the contract minimum (status, probability, outside_training_range JSON, geographic extrapolation flag).
- Merge feature/ml into main (integration owner) and decide how ML dependencies (ml/requirements.txt) are installed on every laptop.
- docs/brief.md: transcribed from the sponsor PDF and added. If anything in it looks wrong, the original PDF governs.
- Sperry questions: is a labeled lightning replay acceptable if no live strike feed is reachable; does an in-app briefing satisfy delivery; is a county-level reported-event model acceptable for the prototype index.
- Submission deadline: rules say Sunday 8:30 AM ET; another source said 8:00 AM on Devpost. Check Devpost and target 7:30 AM.
- README credits: add every AI tool the team actually used (currently lists only ChatGPT/Codex).

## Known limits
- Browser-level testing has not been run by the original scaffold. Map rendering and mobile layout need a manual check.
- Inventory-year plant data does not verify current operating status.
- Some Windows/Mac commands differ; see README and AGENTS.md section 3.

## First manual check
Run both servers, confirm 55 sites in database mode, select a plant, fetch weather and inspect source/units, narrow the window to test mobile layout. If map tiles fail, use the list; tiles are a separate network dependency.

</details>
