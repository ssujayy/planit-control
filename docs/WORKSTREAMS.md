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

The October 18 repository-wide compliance request authorizes integration across
the owned paths above on a separate feature branch. The dashboard consumes the
ranked Outlook and now connects photo/pin reports, filtered history, resolution
and the briefing inbox/preview. The single worker registers weather/NWS/USGS,
daily model predictions and scheduled briefings. Migrations 003/004/005 have now
been applied to Tiger Data, and all 55 sites have stored forecasts and both daily
model indices. Real database checks passed. See docs/SETUP_STATUS.md for
the current verification and docs/requirements-audit.md for acceptance evidence.

## What is not built

Verified live strike ingestion remains absent. River gauges, floodplain and
active-fire detections are absent; USGS stream geometry supplies explicitly
limited location context for a modeled-rainfall advisory. Historical datasets and
the original training manifest/county mapping are not shipped. Gemini,
authentication and public deployment remain unimplemented. Database tests now
verify persistence; manual cross-device crew demonstration and observed scheduled
18:00 delivery remain to be exercised.

## Next shared integration milestone

1. Keep exactly one worker running; the current process holds the database lease.
2. Exercise cross-device reports/photos and observe duplicate-free 18:00 inbox
   delivery; run the credentialed clean-clone and browser checks.
3. Restore the verified ML manifest/crosswalk and resolve the strike provider and
   sponsor questions. Commit only when the human authorizes it.

Ask the Sperry mentor about accessible strike data, acceptable replay, briefing delivery, and county-level ML scope while the rest of the team builds.

## Checkpoints in Eastern time

The playbook baseline is October 17, 2026. Saturday 11 AM: 50 distinct sites, cached weather, verified small ML join. 2 PM: incident workflow. 5 PM: model output and template scheduler integrated. 6 PM: observe scheduled delivery. 9 PM: evaluation and polish. Sunday 12:30 AM: freeze. Sunday 7 AM: submit; 7:30 AM: verify. Use the earlier 8 AM published deadline. If starting later, cut optional work instead of moving submission.

