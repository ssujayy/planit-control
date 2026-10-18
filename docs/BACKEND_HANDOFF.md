# Backend handoff — PlanIT Control

A owns database migrations, shared API integration and the single worker.
The canonical field definitions are in [API_CONTRACT.md](API_CONTRACT.md).
Actual verification and coordination are in [A's log](coordination/A.md).

## What A added

- Tiger Data persistence for 55 real plants and provider weather snapshots.
- NWS point-warning ingestion, including official flood and fire-weather products.
- Cached, evidence-ranked Outlook; stale/missing coverage stays visible.
- Next-local-day rainfall, shallow soil moisture and derived heat-index summaries.
  The heat index uses the NWS formula on modeled inputs, separately from
  Open-Meteo apparent temperature; it is not an official NWS measurement.
- Migration 002 and repositories for lightning, shared photo bytes/history,
  duplicate-free briefings, and actual versioned model predictions.
- One locked worker with independent job registration and persisted outcomes.

## How each owner connects

| Owner | Next implementation |
|---|---|
| B: lightning | Validate the source/event/time and calculate sites within 10 miles, then call `db.store_lightning_event(..., affected_site_ids=ids, mode='live')`. Storage deduplicates events and atomically extends holds. Use `mode='replay'` explicitly for replay; never pass plant-storage mode here. Live Outlook reads live holds only. |
| B: crew reports | Implement the agreed upload/history/photo endpoints. Verify actual image content and size, then use `save_crew_report`, `list_crew_reports`, and `get_report_photo`. Image bytes live in PostgreSQL, not temporary files. Categories: wildlife, water, access, fire, other; JPEG/PNG/WebP, maximum 5 MiB. |
| B: briefings | Generate deterministic facts/body for tomorrow and schedule at 18:00 in each site's IANA timezone. Use `save_briefing` for both scheduled/manual generation; its site/mode/local-delivery-date constraint prevents duplicates. Expose the inbox using `list_briefings`. Storage alone does not schedule or deliver reports. |
| C: model | Train/evaluate the historical model. Call `save_prediction` with the real score, local valid date, model/feature versions, UTC computation time and `provenance={'model_artifact': 'actual artifact path/version'}`. The Outlook reads only predictions for each site's local tomorrow. Never fill a missing score with zero. |
| D: frontend | Read `/api/outlook?mode=live`; use `rank` and `reasons` for the attention queue, `weather.hourly.time` plus site timezone for the matrix, and `/api/sites/{id}/evidence` for the evidence view. Show coverage separately from hazard state. Preserve the map and label daily predictions as daily. |

All repository functions are in `backend/db.py`; exact arguments are documented
in API_CONTRACT.md. B/C should propose additional fields to A before changing
shared schema or response shapes. No public write API was added by A.
For B's JSON endpoints, `backend.outlook.serialize(records)` converts repository
date/timestamp values to the contract's ISO format before `jsonify`.

## Worker registration

B/C return `backend.worker.Job(name, callback, interval_seconds)` objects from a
factory. Callbacks take no arguments and return a JSON-safe aggregate summary;
keep them bounded so they do not block other jobs. Example for B, after B supplies
the actual `run_due_briefings` implementation:

```python
from backend.worker import Job

def worker_jobs():
    return [Job('briefings', run_due_briefings, 30)]
```

Stop an existing worker before replacing it. Once the B/C modules exist, register
their factories with repeated `--job-module package.module:worker_jobs` options.
Never start separate competing ingestion, briefing and inference workers.

## Run and check

From the root, using the project's Python environment:

```powershell
python -m scripts.seed_database
python -m backend.worker --once
python -m pytest -q --run-database
python -m flask --app backend.app:create_app run --port 5000
```

Run `python -m backend.worker` separately for continuing updates. Weather rotates
one plant per 15-second interval; NWS rotates one per 5-second interval, plus
request time. `/api/readiness?mode=live` reports stored coverage and outstanding
workflow gaps. Read endpoints never fetch providers. The worker is serial and
official warnings are polled; this is not an instant strike-monitoring feed.

## Still required

B's verified strike feed/10-mile processing, image validation/upload APIs,
18:00 scheduling/inbox; C's genuine training/evaluation/predictions; D's connected
UI. River proximity/gauges and active-fire detections remain unavailable. NWS
fire-weather warnings are a separate layer; no rainfall-to-official-flood rule,
soil trafficability threshold, or site-wide all-clear is invented.
