# Foundation API contract

Dates: UTC ISO 8601 unless explicitly marked as Unix seconds. Unknown values use null, never zero. Every component must distinguish live provider data, cached data, and demo file storage.

## Implemented now

- `GET /api/health`: `{application: "ready", database: "connected" | "not_configured" | "unavailable", as_of}`. Database status is not proof that schema or seeding is complete; verify `/api/sites?mode=live` too.
- `GET /api/sites?mode=live|demo`: `{mode, sites, count, risk_status: "not_implemented", as_of}`. Default is live. Missing database configuration returns HTTP 503; no silent fallback.
- `GET /api/sites/{id}?mode=live|demo`: `{mode, site, alerts: null, model_index: null, implementation: "foundation"}`. Null alerts means unimplemented, not no hazards.
- `GET /api/sites/{id}/weather?mode=live|demo`: `{site_id, site_mode, weather}`. `site_mode` describes plant storage; the weather call goes to the actual provider in either mode. `weather` carries source, fetched_at, cached, stale, current, current_units, hourly, hourly_units, note. Provider times are Unix seconds in UTC. Units are carried from the actual response. Initial provider failure returns 502. A refresh failure with a prior cache retains the data with `stale: true`.

Site fields: `id`, `source_plant_id`, `name`, `state`, `county`, `latitude`, `longitude`, `timezone`, `source_version`. IDs are stable EIA plant identifiers. County names are not county FIPS; add a verified crosswalk before county ML joins.

## Next owner interfaces

- Alerts owner: add independent active alerts and lightning_hold_until; preserve other hazards when a hold expires. Keep replay separate from live.
- Reports owner: `POST /api/reports` with validated image, site ID, latitude, longitude, category and note; `GET /api/reports?site_id=...`.
- Briefing owner: `GET /api/briefings?site_id=...`; persist site/local-date uniqueness; scheduled worker separate from Flask.
- ML owner: predictions keyed by site ID, valid_date, model_version, feature_version, score and computed_at. Score may be null until genuinely computed.

Do not implement a catch-all endpoint that returns plausible success for unfinished features. Unknown API routes return 404. Update this file and notify affected owners before changing field names.

