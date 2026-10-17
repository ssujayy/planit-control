-- Run once with: python -m scripts.seed_database
CREATE TABLE IF NOT EXISTS sites (
    id integer PRIMARY KEY,
    source_plant_id integer UNIQUE NOT NULL,
    name text NOT NULL,
    state text NOT NULL,
    county text,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    timezone text NOT NULL,
    source_version text NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    site_id integer REFERENCES sites(id),
    observed_at timestamptz NOT NULL,
    fetched_at timestamptz NOT NULL,
    source text NOT NULL,
    metric text NOT NULL,
    value double precision,
    unit text NOT NULL,
    mode text NOT NULL CHECK (mode IN ('live', 'demo'))
);


-- Workstream B (proposed; A reviews)
-- Operational events: lightning holds, simulated replay, crew reports, briefings, evidence timeline.
-- event_mode (live | replay) is event provenance; it is unrelated to the storage field "mode".
CREATE TABLE IF NOT EXISTS lightning_strikes (
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    source text NOT NULL,
    event_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    replay_session_id text,
    PRIMARY KEY (event_mode, source, event_id)
);
CREATE TABLE IF NOT EXISTS lightning_holds (
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    hold_until timestamptz NOT NULL,
    last_strike_source text NOT NULL,
    last_strike_event_id text NOT NULL,
    last_strike_at timestamptz NOT NULL,
    last_strike_distance_km double precision NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (site_id, event_mode)
);
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
CREATE TABLE IF NOT EXISTS crew_reports (
    id text PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    category text NOT NULL CHECK (category IN ('heat', 'lightning', 'flooding', 'mud', 'fire', 'wildlife', 'other')),
    note text NOT NULL CHECK (char_length(note) <= 1000),
    created_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('unresolved', 'resolved')),
    resolved_at timestamptz,
    distance_from_site_km double precision,
    location_flag text,
    photo bytea,
    photo_content_type text CHECK (photo_content_type IN ('image/jpeg', 'image/png')),
    photo_size_bytes integer CHECK (photo_size_bytes BETWEEN 1 AND 5242880)
);
CREATE TABLE IF NOT EXISTS briefings (
    id text PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    delivery_local_date date NOT NULL,
    forecast_target_date date NOT NULL,
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    trigger text NOT NULL CHECK (trigger IN ('scheduled', 'manual')),
    timezone text NOT NULL,
    delivered_at timestamptz NOT NULL,
    generator text NOT NULL,
    content jsonb NOT NULL,
    body_text text NOT NULL,
    UNIQUE (site_id, delivery_local_date, event_mode)
);
CREATE TABLE IF NOT EXISTS ops_events (
    id text PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites(id),
    event_mode text NOT NULL CHECK (event_mode IN ('live', 'replay')),
    type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    source text NOT NULL,
    summary text NOT NULL,
    details jsonb NOT NULL
);
