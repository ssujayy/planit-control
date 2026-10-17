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

