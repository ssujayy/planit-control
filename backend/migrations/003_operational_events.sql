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
