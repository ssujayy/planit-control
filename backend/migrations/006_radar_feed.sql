CREATE TABLE radar_feed (
    source text PRIMARY KEY CHECK (source = 'RainViewer'),
    payload jsonb,
    last_attempt_at timestamptz NOT NULL,
    last_success_at timestamptz,
    error_code text
);
