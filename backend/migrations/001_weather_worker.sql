-- Additive; do not edit after application. Add another numbered file instead.
CREATE TABLE IF NOT EXISTS weather_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    source text NOT NULL,
    fetched_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    UNIQUE (site_id, event_mode, source, fetched_at)
);
CREATE INDEX IF NOT EXISTS weather_snapshots_latest
    ON weather_snapshots (site_id, event_mode, fetched_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS weather_ingestion (
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    last_attempt_at timestamptz NOT NULL,
    last_success_at timestamptz,
    error_code text CHECK (error_code IS NULL OR error_code = 'weather_unavailable'),
    PRIMARY KEY (site_id, event_mode)
);

CREATE TABLE IF NOT EXISTS worker_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_name text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'partial', 'failed')),
    summary jsonb
);
