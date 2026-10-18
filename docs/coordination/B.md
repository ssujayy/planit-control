# Workstream B coordination log (operational events)

Written for Dev and teammates A, C and D. Factual record only.

## 1. Scoped task and owned files

Lightning holds and simulated replay, crew photo reports, next-day briefings, and the per-site evidence timeline.

Owned files:
- **Backend:** backend/lightning.py, replay.py, reports.py, briefings.py, timeline.py, ops_routes.py, ops_store.py, ops_common.py.
- **Data and docs:** docs/replay/strikes.json, docs/fixtures/ops_*.json, this file.
- **Tests:** tests/test_lightning.py, test_replay.py, test_reports.py, test_briefings.py, test_timeline.py, ops_support.py, ops_fixtures.py.

Shared files changed (additive only):
- backend/db.py: the `ops_*` block at the end. A's functions are unchanged.
- backend/migrations/003_operational_events.sql: new.
- backend/app.py: one registration line.
- docs/API_CONTRACT.md: the section "Operational events (proposed, Workstream B)".
- scripts/inspect_schema.py: new, read-only.

## 2. Assumptions and contracts checked

- **Documents read:** AGENTS.md, docs/WORKSTREAMS.md, SETUP_STATUS.md, API_CONTRACT.md, brief.md, BACKEND_HANDOFF.md, migrations 001/002, backend/db.py, backend/outlook.py, backend/worker.py.
- **Naming:** `event_mode` (live | replay) is always separate from the storage `mode` (live | demo).
- **Errors:** 400, 404 and 503 per the contract. Unknown `/api/*` routes still return 404 through A's catch-all.
- **Storage:** follows A's BACKEND_HANDOFF.md.
  - Strikes use `store_lightning_event` and `get_lightning_holds`.
  - Reports use `save_crew_report`, `list_crew_reports` and `get_report_photo`.
  - Briefings use `save_briefing` and `list_briefings`.
  - JSON goes through `outlook.serialize`.
  - The worker registers `Job('briefings', ..., 30)`.

## 3. Mismatches found and how they were resolved

1. **B's first schema proposal duplicated A's tables.** It appended `lightning_holds`, `crew_reports` and `briefings` to backend/schema.sql with columns different from A's migration 002. A's `db.migrate()` runs schema.sql before the migrations, so on a clean database B's definitions would have won and 002's would have been silently skipped.
   - Resolved: B's block was removed from schema.sql, which is now byte-identical to origin/main. B uses A's 002 tables only.
2. **`ops_events` in the shared database is the old shape.** Dev verified it was created from B's first proposal: no `ref_table`, no `ref_key`, no `type` CHECK. Because of that, `CREATE TABLE IF NOT EXISTS` in 003 will skip it.
   - Resolved additively in 003 (nothing dropped): `ADD COLUMN IF NOT EXISTS ref_table, ref_key`.
   - A guarded `DO` block adds the NOT NULL and CHECK constraints only when `ops_events` has no rows.
   - `lightning_feed_status` and `replay_sessions` in 003 are column-for-column identical to the first proposal, so they need no reconciliation.
3. **The old proposal's other tables may also be in the shared database. Not verified.**
   - `lightning_strikes` may exist. The application no longer writes to it; it is left alone, never dropped or altered.
   - If the old schema.sql block ran before 002, then `lightning_holds`, `crew_reports` and `briefings` would carry B's first columns, and A's repositories would fail against them. Signs to look for in the inspector output: `crew_reports.status`, `briefings.content`, `lightning_holds.last_strike_event_id`.
   - **This needs A's decision. B will not alter A's tables.**
4. **Crew report categories changed** to A's list: wildlife, water, access, fire, other. The sponsor brief (docs/brief.md) names hazards that these five can only approximate. Flagged for Dev; nothing was silently dropped:
   - **Heat** ("extreme heat", "heat index will surpass 110°F"): no category. A crew member would have to use `other`.
   - **Lightning**: no category; `other`. Lightning is covered by the automatic hold, not by reports.
   - **Soil saturation / mud / vehicles stuck** maps to `access` (approximate). **Flooding** maps to `water`. **Wildfire** maps to `fire`. **Wildlife** maps to `wildlife`. **Crash or debris on the road** maps to `access`.
5. **Port 5001 incident (Oct 17, about 11:15 PM ET).** During a smoke test, a Flask server that someone else had started was already on port 5001. B's requests reached it, then B's cleanup command stopped it.
   - Those requests were SELECT-only and wrote nothing.
   - Since then, B starts no servers; Dev runs any live smoke test.
6. **Port 5000 conflict on Dev's Mac.** Port 5000 is used by macOS ControlCenter (AirPlay Receiver).

## 4. Decisions where something was ambiguous

- **HTTP strike ingest is replay-only.** Live strikes enter only through a configured feed in the worker (`lightning.poll_source`), so the public API cannot create live holds.
- **Unknown lightning state is `null`.** With no hold and coverage that is not COMPLETE, `hazard.state` is `null` (unknown), never NO_ACTIVE_ALERTS. `coverage.feed_connected` separates "connected, no strikes" from "disconnected".
- **Reports are always `event_mode: "live"`.** Crew input is real. Replay timelines and replay briefings read live reports (read-only) and label them as real; this follows Dev's instruction.
- **Briefing timing.** A manual live briefing is allowed only after site-local 6 PM (otherwise 409), so it cannot fake or pre-empt the scheduled delivery. A manual replay briefing is allowed any time on the replay clock.
- **Briefing facts come from A's stored Outlook evidence:** forecast summary (derived heat index, precipitation sum, shallow soil moisture), official alerts, and the saved next-day prediction. Missing facts read "unavailable" and are listed in `missing_inputs`. Replay briefings use the same real stored facts; only lightning is simulated.
- **The timeline derives from canonical records.** `ops_events` stores only hold changes, each referencing its `lightning_events` row. Report, briefing and hold-expiry events are read from `crew_reports`, `briefings` and `lightning_holds`, so the timeline and the Outlook agree.
- **Replay reset deletes only replay rows.** It removes `event_mode = 'replay'` rows from `ops_events`, `lightning_feed_status`, `lightning_holds`, `lightning_events`, `briefings` and `crew_reports`, using row-level DELETE only, and never touches `lightning_strikes`.
- **Timestamps use `+00:00`.** All timestamps go through `outlook.serialize`, so they use the offset form, not `Z`.
- **Hold history is not backfilled.** `hazard.last_strike` reports only what `lightning_holds` stores (source, last_strike_at). Distance per strike is in the matching `ops_events.details`.

## 5. Verification actually run

- `.venv/bin/python -m pytest -q` (Oct 18, about 12:05 AM ET): **135 passed, 12 skipped.** The skips are A's `--run-database` tests. Everything ran offline with MemoryStore and an injected clock.
- `git diff origin/main -- backend/schema.sql`: empty. `git diff origin/main -- docs/API_CONTRACT.md`: insertions only.
- Fixtures were regenerated from the real endpoints (`python tests/ops_fixtures.py`). A test checks they match live response shapes.
- **Not run:** migration 003, `PostgresStore`, the `db.py` `ops_*` functions, the worker job and `scripts/inspect_schema.py` have **not** run against any PostgreSQL database. No local PostgreSQL was available, and B does not touch the shared database. The SQL in 003 has not been executed anywhere.
- A real site-local 6 PM run was not observed. Scheduling was verified with an injected clock (Eastern vs Central, DST fall-back, duplicate runs) plus manual generation.

## 6. Retained SQL (migration `backend/migrations/003_operational_events.sql`)

Exact file contents:

```sql
-- Workstream B: operational-event tables that A's 002 does not provide.
-- Strikes and holds live in 002's lightning_events / lightning_holds; reports and
-- briefings live in 002's crew_reports / briefings. These tables only add feed
-- freshness, replay sessions and hold-change history that points at canonical rows.
CREATE TABLE IF NOT EXISTS lightning_feed_status (
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    source text NOT NULL,
    last_event_received_at timestamptz,
    last_feed_check_at timestamptz,
    PRIMARY KEY (event_mode, source)
);
CREATE TABLE IF NOT EXISTS replay_sessions (
    session_id text PRIMARY KEY,
    started_at timestamptz NOT NULL,
    replay_epoch timestamptz NOT NULL,
    speed double precision NOT NULL CHECK (speed > 0),
    active boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS ops_events (
    id text PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    type text NOT NULL CHECK (type IN ('lightning_hold_started', 'lightning_hold_extended')),
    occurred_at timestamptz NOT NULL,
    source text NOT NULL,
    summary text NOT NULL,
    ref_table text NOT NULL CHECK (ref_table IN ('lightning_events', 'lightning_holds', 'crew_reports', 'briefings')),
    ref_key jsonb NOT NULL CHECK (jsonb_typeof(ref_key) = 'object'),
    details jsonb NOT NULL CHECK (jsonb_typeof(details) = 'object')
);
CREATE INDEX IF NOT EXISTS ops_events_site_timeline ON ops_events (site_id, event_mode, occurred_at);

-- Reconcile databases where ops_events was created earlier from B's first proposal
-- (no ref_table, ref_key or type/details CHECK). Additive only: nothing is dropped.
-- On a clean database the strict CREATE above already has these, so this is a no-op.
ALTER TABLE ops_events ADD COLUMN IF NOT EXISTS ref_table text;
ALTER TABLE ops_events ADD COLUMN IF NOT EXISTS ref_key jsonb;
DO $$
BEGIN
    -- Constraints are only tightened while the table is empty, so existing rows are never rejected.
    IF NOT EXISTS (SELECT 1 FROM ops_events) THEN
        ALTER TABLE ops_events ALTER COLUMN ref_table SET NOT NULL;
        ALTER TABLE ops_events ALTER COLUMN ref_key SET NOT NULL;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'ops_events'::regclass AND conname = 'ops_events_type_check') THEN
            ALTER TABLE ops_events ADD CONSTRAINT ops_events_type_check
                CHECK (type IN ('lightning_hold_started', 'lightning_hold_extended'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'ops_events'::regclass AND conname = 'ops_events_ref_table_check') THEN
            ALTER TABLE ops_events ADD CONSTRAINT ops_events_ref_table_check
                CHECK (ref_table IN ('lightning_events', 'lightning_holds', 'crew_reports', 'briefings'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'ops_events'::regclass AND conname = 'ops_events_ref_key_check') THEN
            ALTER TABLE ops_events ADD CONSTRAINT ops_events_ref_key_check CHECK (jsonb_typeof(ref_key) = 'object');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'ops_events'::regclass AND conname = 'ops_events_details_check') THEN
            ALTER TABLE ops_events ADD CONSTRAINT ops_events_details_check CHECK (jsonb_typeof(details) = 'object');
        END IF;
    END IF;
END $$;
```

No other B tables or indexes are retained. `lightning_strikes`, if it exists in the shared database, is no longer used by the application and is left untouched.

### db.py functions added (end of file, "Workstream B" block)

`ops_record_feed`, `ops_get_feeds`, `ops_start_replay_session`, `ops_get_replay_session`, `ops_reset_replay`, `ops_add_event`, `ops_list_events`, `ops_get_crew_report`, `ops_resolve_crew_report`, `ops_get_briefing`.

### Schema inspection (read-only; Dev runs it)

```
.venv/bin/python -m scripts.inspect_schema        # macOS/Linux
.venv\Scripts\python.exe -m scripts.inspect_schema   # Windows
```

It prints, for lightning_events, lightning_holds, crew_reports, briefings, lightning_strikes, lightning_feed_status, replay_sessions and ops_events: columns, types, nullability, defaults, constraints, indexes and an approximate row count. It also lists the applied `schema_migrations`. It runs in a READ ONLY transaction, uses SELECTs on information_schema/pg_catalog only, and prints no connection details.

Comparison against 002/003: **pending Dev's output.** Every difference will be recorded here.

## 7. Ready-to-paste messages

**To A (backend):**
> B is on main + feature/ops-events (not yet merged). B adds migration 003_operational_events.sql: lightning_feed_status, replay_sessions, ops_events, plus an additive reconciliation for the old ops_events (ADD COLUMN IF NOT EXISTS ref_table/ref_key; NOT NULL/CHECK only while empty). Exact SQL is in docs/coordination/B.md section 6.
> B's old block in schema.sql is removed. Strikes/holds go through your store_lightning_event; reports/briefings through your repositories. New ops_* functions are at the end of db.py; your functions are unchanged.
> Worker: register `--job-module backend.briefings:worker_jobs` (Job 'briefings', 30 s). Real (non-replay) briefings only exist if the worker runs tonight after each site's local 6 PM (Eastern 6 PM ET, Central 7 PM ET).
> Please run migrate once after review (B has not), then Dev runs scripts.inspect_schema. If lightning_holds/crew_reports/briefings show B's old columns, that needs your decision; B will not alter your tables.
> app.py has one line: `from .ops_routes import ops_bp; app.register_blueprint(ops_bp)`. Windows needs the `tzdata` package for zoneinfo; please add it to requirements.txt if Windows laptops run the worker.

**To D (frontend):**
> Endpoints are in docs/API_CONTRACT.md "Operational events (proposed, Workstream B)". Fixtures: docs/fixtures/ops_*.json (lightning_live, lightning_replay_hold, lightning_holds, replay_session, strike_ingest, report_created, report_resolved, reports, briefings, briefing_generate, timeline, errors).
> Timeline event types: lightning_hold_started, lightning_hold_extended, lightning_hold_expired, report_created, report_resolved, briefing_delivered. Replay timelines include live crew reports (event_mode "live").
> Show coverage next to hazard state; hazard.state null means unknown, never clear. Label replay "simulated replay".
> Report form: multipart with site_id, latitude, longitude, category (wildlife/water/access/fire/other), note (1-2000 characters) and photo (required, JPEG/PNG/WebP, 5 MiB max). Timestamps are +00:00 UTC.

**To C (ML):**
> Briefings read the model index only from A's stored next-day prediction (Outlook row `prediction`), never by calling the model.
> Shown as "Experimental model index (0-10; not a probability or calibrated risk)", with "Daily model output for the whole local day, not an hourly forecast."
> If provenance contains `outside_training_counties: true`, the briefing adds "Outside training counties (geographic extrapolation)". `outside_training_range` features are listed. Absent: "Training-county status: unknown".
> No saved prediction for the target date reads "unavailable". Please include those two provenance keys when calling save_prediction.

## 8. How Dev verifies (beginner steps)

1. Run the tests (offline, no database):
   `.venv/bin/python -m pytest -q`. Expected: `135 passed, 12 skipped`.
2. Regenerate the fixtures (offline):
   `.venv/bin/python tests/ops_fixtures.py`. Expected: a line starting `Wrote ops_briefing_generate.json, ...`. `git status` should show no changes except fixture ids and session ids, which are random.
3. After A runs migrate, check the schema (read-only):
   `.venv/bin/python -m scripts.inspect_schema`. Paste the output to B.
4. Live smoke test (Dev runs it; use port 5001 because 5000 is AirPlay on this Mac). Start `.venv/bin/python -m flask --app backend.app:create_app run --port 5001`, then in a second terminal:
   - `curl -s localhost:5001/api/sites/663/lightning`: expect `"coverage": {... "status": "UNAVAILABLE" ...}` and `"state": null`.
   - `curl -s -X POST localhost:5001/api/replay/sessions -H 'Content-Type: application/json' -d '{"speed":10}'`: expect 201 with `"label": "simulated replay"`.
   - Wait about 1 minute, then `curl -s 'localhost:5001/api/lightning/holds?event_mode=replay'`: expect holds at Deerhaven, Grand Gulf and Edwin I Hatch.
   - `curl -s -F site_id=663 -F latitude=29.76 -F longitude=-82.39 -F category=wildlife -F note='Gator by culvert' -F photo=@some.jpg localhost:5001/api/reports`: expect 201 with a `report` object.
   - `curl -s 'localhost:5001/api/reports?site_id=663'`: expect that report in `current_unresolved`.
   - `curl -s -X POST localhost:5001/api/reports/<id>/resolve`: expect `"status": "resolved"`.
   - `curl -s -o x.jpg -w '%{content_type}\n' localhost:5001/api/reports/<id>/photo`: expect `image/jpeg`.
   - `curl -s -X POST localhost:5001/api/briefings/generate -H 'Content-Type: application/json' -d '{"site_id":663}'`: expect 201 replay briefing.
   - `curl -s 'localhost:5001/api/sites/663/timeline?event_mode=replay'`: expect hold, report and briefing events.
   - `curl -s -X POST localhost:5001/api/replay/reset`: expect `"reset": true`.
   Before migration 003 is applied, the lightning/replay endpoints return 503 `database_unavailable`, which is expected.

## 9. Known gaps

- No live lightning feed: live coverage stays UNAVAILABLE. A real feed needs an accessible strike provider (open question with the Sperry mentor), a `LiveSource(feed=...)` callable and a worker job calling `lightning.poll_source`.
- No DB-backed path has been exercised against a real database (see section 5).
- Each PostgresStore call opens its own connection (A's repository pattern), so a request makes several round trips.
- Missed 6 PM deliveries are not backfilled after midnight.
- Gemini rewrite (optional M8) was not built. The template is the only output; `rewrite_status` is `not_requested`.
- The venv on Dev's Mac is Python 3.14; AGENTS.md prefers 3.12.
