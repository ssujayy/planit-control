# Team ownership and next actions

Role letters follow the latest human assignment (October 17, 2026). This session
is explicitly assigned A; actual human names for the other roles are not known.
Record actual coordination only in each owner's own docs/coordination log.

| Owner | Files and responsibility | Next acceptance check |
|---|---|---|
| A Backend integration | backend/db.py, backend/schema.sql and migrations, shared routes and backend wiring, seed, ingestion, the single worker and worker registration | 55 database-backed plants, cached weather/NWS monitoring, evidence ranking and shared B/C repositories (see docs/BACKEND_HANDOFF.md); new tables applied to Tiger Data; the worker runs B's briefing function and stays single |
| B Operational events (alerts and crew workflow) | backend/lightning.py, reports.py, briefings.py and their routes, docs/replay/, behavior tests; register jobs with A's worker | Persistent isolated lightning holds, cross-device photo reports, one briefing per site/date/mode at site-local 18:00 |
| C ML | ml/ folder; historical data, NOAA/weather joins, training, model, evaluation and inference; register jobs with A's worker | Verified historical dataset, saved model/evaluation and actual predictions, stored and shown with the extrapolation label |
| D Frontend | frontend/src; Shift Outlook (attention queue, site-by-time matrix, evidence timeline) state, components, styling and visualization; map (preserve), report form, briefing inbox | Views run on contract fixtures first, then real endpoints, with honest missing states |

## What is already scaffolded

React/Vite, Flask factory, PostgreSQL schema and additive migrations, 55
deduplicated EIA plants, map/list and manual weather endpoint. A verified the
configured Tiger Data connection, 55 database-backed plants, 55 persisted live
weather snapshots and fresh official NWS monitoring for all 55 in a fresh process.
GET /api/outlook composes and ranks stored evidence without provider calls.
The worker runs weather/NWS rotations and accepts explicit B/C job factories.
Migration 002 supplies lightning, photo/report, briefing and prediction storage;
storage does not implement the B/C business workflows. The frontend defaults to demo file storage
and has not yet been connected to the new Outlook route. See A's log for exact
verification, interfaces and limitations.

## What is not built

The merged ML work includes a saved trained logistic model, evaluation,
inference and optional model contributions, plus a separate offline tree
comparison. Prepared historical datasets remain ignored and are not shipped by
Git. Automatic forecast-to-model prediction persistence, verified live strike
ingestion, 10-mile strike processing, report upload APIs, briefing scheduler,
Gemini integration, authentication and public deployment remain unfinished.
NWS flood/fire-weather monitoring does not provide river gauges/proximity or
active-fire detections. Storage and evidence ranking do not complete these requirements. Do not present placeholders
as features. No persistent worker was left running by A's bounded checks.

## Next shared integration milestone

1. D consumes the ranked Outlook and site-evidence responses for the attention queue, site-by-time matrix and timeline.
2. B connects validated strike processing, shared photo upload/history and local 18:00 scheduling to A's repositories; propose additive schema/interface changes to A if needed.
3. Connect C's saved model to full site-local daily forecast features, save_prediction and a bounded inference job factory; see docs/INTEGRATION_BACKEND_ML.md.
4. A integrates B/C jobs and feed coverage; D presents missing coverage independently of hazard state.
5. Register B/C factories in one worker, verify live/replay isolation and scheduled delivery, and run an integrated clean-clone check. Commit only when the human authorizes it.

Ask the Sperry mentor about accessible strike data, acceptable replay, briefing delivery, and county-level ML scope while the rest of the team builds.

## Checkpoints in Eastern time

The playbook baseline is October 17, 2026. Saturday 11 AM: 50 distinct sites, cached weather, verified small ML join. 2 PM: incident workflow. 5 PM: model output and template scheduler integrated. 6 PM: observe scheduled delivery. 9 PM: evaluation and polish. Sunday 12:30 AM: freeze. Sunday 7 AM: submit; 7:30 AM: verify. Use the earlier 8 AM published deadline. If starting later, cut optional work instead of moving submission.

