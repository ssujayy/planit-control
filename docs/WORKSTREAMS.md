# Team ownership and next actions

Assign actual names before editing the same files. Owners are proposed roles, not assigned people.

| Owner | Files and responsibility | Next acceptance check |
|---|---|---|
| A Backend integration | backend/db.py, backend/schema.sql and migrations, seed, ingestion, shared backend wiring, the single worker | New tables applied to Tiger Data; the worker runs B's briefing function and stays single |
| B Operational events | backend/lightning.py, reports.py, briefings.py and their routes, docs/replay/, behavior tests | Persistent isolated lightning holds, cross-device photo reports, one briefing per site/date/mode |
| C ML | ml/ folder; NOAA/weather joins, model, evaluation, inference | Baseline done on feature/ml; predictions stored and shown with the extrapolation label |
| D Frontend | frontend/src; Shift Outlook (attention queue, site-by-time matrix, evidence timeline), map, report form, briefing inbox | Views run on contract fixtures first, then real endpoints |

## What is already scaffolded

React/Vite, Flask factory, initial PostgreSQL schema and seed command, 55 deduplicated EIA plants, map and keyboard-accessible list, live weather endpoint and a short-lived cache. The frontend clearly defaults to demo file storage; Tiger Data mode is explicit. Source headers and retrieval notes are included.

## What is not built

No completed Tiger Data connection, historical training dataset, trained model, risk classification, alert ingestion, lightning processing, report uploads, briefing scheduler, Gemini integration, authentication or public deployment. Do not present placeholders as features.

## First shared integration milestone

1. Copy `.env.example` to `.env`; the account owner enters the Tiger Data URI locally.
2. Run the schema/seed command in the README.
3. Confirm health reports connected AND database-mode `/api/sites` returns 55 plants.
4. Select Tiger Data database in the UI and fetch weather for one site.
5. Commit the working state without `.env` and split module ownership.

Ask the Sperry mentor about accessible strike data, acceptable replay, briefing delivery, and county-level ML scope while the rest of the team builds.

## Checkpoints in Eastern time

The playbook baseline is October 17, 2026. Saturday 11 AM: 50 distinct sites, cached weather, verified small ML join. 2 PM: incident workflow. 5 PM: model output and template scheduler integrated. 6 PM: observe scheduled delivery. 9 PM: evaluation and polish. Sunday 12:30 AM: freeze. Sunday 7 AM: submit; 7:30 AM: verify. Use the earlier 8 AM published deadline. If starting later, cut optional work instead of moving submission.

