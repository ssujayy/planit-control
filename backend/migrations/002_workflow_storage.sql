-- Shared repositories only. Owners B/C supply business logic and real feeds/models.
CREATE TABLE IF NOT EXISTS official_alert_snapshots (
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    fetched_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (site_id, event_mode)
);
CREATE TABLE IF NOT EXISTS official_alert_ingestion (
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    last_attempt_at timestamptz NOT NULL,
    error_code text CHECK (error_code IS NULL OR error_code = 'official_alerts_unavailable'),
    PRIMARY KEY (site_id, event_mode)
);
CREATE TABLE IF NOT EXISTS lightning_events (
    source text NOT NULL,
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    event_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, event_mode, event_id)
);
CREATE TABLE IF NOT EXISTS lightning_holds (
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    hold_until timestamptz NOT NULL,
    last_strike_at timestamptz NOT NULL,
    source text NOT NULL,
    PRIMARY KEY (site_id, event_mode)
);
CREATE TABLE IF NOT EXISTS crew_reports (
    id uuid PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    observed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    category text NOT NULL CHECK (category IN ('wildlife', 'water', 'access', 'fire', 'other')),
    note text NOT NULL CHECK (length(note) BETWEEN 1 AND 2000),
    photo bytea NOT NULL CHECK (octet_length(photo) BETWEEN 1 AND 5242880),
    photo_content_type text NOT NULL CHECK (photo_content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    resolved_at timestamptz
);
CREATE INDEX IF NOT EXISTS crew_reports_history ON crew_reports (site_id, event_mode, observed_at DESC);
CREATE TABLE IF NOT EXISTS briefings (
    id uuid PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    delivery_local_date date NOT NULL,
    target_date date NOT NULL CHECK (target_date = delivery_local_date + 1),
    generated_at timestamptz NOT NULL DEFAULT now(),
    body text NOT NULL CHECK (length(body) BETWEEN 1 AND 30000),
    facts jsonb NOT NULL CHECK (jsonb_typeof(facts) = 'object'),
    UNIQUE (site_id, event_mode, delivery_local_date)
);
CREATE TABLE IF NOT EXISTS model_predictions (
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    valid_date date NOT NULL,
    model_version text NOT NULL,
    feature_version text NOT NULL,
    score double precision NOT NULL CHECK (score BETWEEN 0 AND 10),
    computed_at timestamptz NOT NULL,
    provenance jsonb NOT NULL CHECK (jsonb_typeof(provenance) = 'object'),
    PRIMARY KEY (site_id, event_mode, valid_date, model_version, feature_version)
);
