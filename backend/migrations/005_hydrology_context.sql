CREATE TABLE site_hydrology (
    site_id integer PRIMARY KEY REFERENCES sites(id),
    fetched_at timestamptz,
    attempted_at timestamptz NOT NULL,
    error_code text,
    payload jsonb
);
