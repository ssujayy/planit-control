# Foundation API contract

## Readable dashboard and lightning recording (October 18, 2026)

- Model scores retain their saved numeric values. All dashboard and briefing
  displays use two decimals; today and tomorrow remain separate daily forecasts.
- `POST /api/sites/<id>/lightning/observations` accepts a JSON object with
  `observed: true` and a required unique `event_id` (reuse it when retrying).
  It records a crew observation **at the selected plant now**, using server UTC,
  fixed source `crew-observed` and fixed `event_mode: live`. Provider/source,
  coordinates, event time and event-mode overrides are rejected. This starts or
  extends the persisted 30-minute hold at all plants within 10 miles. The response
  is the existing strike-processing result; duplicates return 200, new records
  201. It does not connect or certify automatic strike monitoring. Existing
  `/api/lightning/strikes` remains replay-only over HTTP.
- `GET /api/sites/<id>/lightning/observations?event_mode=live|replay` returns
  `site_id`, `event_mode`, `as_of`, `count` and `events`: the site's persisted
  hold-start/extension history, newest first, with the existing operational-event
  shape (source, occurred_at, summary, details and canonical event reference).
  Expired holds remain in history. This is hold history, not a complete strike feed.
- `GET /api/sites/<id>/briefing-preview` is a read-only equivalent of the existing
  POST preview: `preview: true`, `delivered: false`, `briefing`. The UI loads it
  automatically; it never reserves a scheduled delivery or writes a briefing.
- Newly generated preview/scheduled briefings add `generated_at` and `display`
  in existing JSON facts (no schema change). `display` contains `target_date`,
  `based_on` (forecast retrieval time), `summary`, `conditions` (key, label,
  value, unit, status), `attention` (plain text list), `missing_data` (list), and
  `model` (nullable score, outside_training_counties, outside_training_range).
  Missing, stale or wrong-date forecasts have null display values and explicit
  status. Legacy `sections`/`body_text` remain available. The same deterministic
  generator supplies previews and duplicate-free site-local 18:00 delivery.

## Compliance integration changes (October 18, 2026)

### Weather/model follow-up fixes

- `planning_weather.precipitation_sum_mm` prefers the provider's complete DAILY
  rainfall value for the exact target local date and timezone, independently of
  hourly coverage. Complete hourly sums remain compatible with older snapshots.
  Hourly precipitation is a preceding-hour sum: fallback integration uses the
  hours ending 01:00 through next-day 00:00, unlike instantaneous temperature/
  soil samples at 00:00 through 23:00. No previous day's rain is included.
  Heat/soil still require every real local-day hour (23/24/25 as applicable).
- `planning_weather.metrics` adds one record per metric with `status`, `reason`,
  `source`, `unit`, `expected_hours`, `available_hours`, `retrieved_at` and
  `target_date`. Unknown inputs stay null with a reason; real zero rainfall is 0.
  Successful weather snapshots persist the derived next-day `planning_weather`
  alongside raw hourly and DAILY data in the existing JSON snapshot storage.
- Today/tomorrow prediction availability now exposes a `reason` and a separate
  `current_prediction_monitoring`. Dashboard site rows display both daily indices.
  Neither is called an instantaneous current-weather prediction: the saved
  model was trained on entire local days, and current readings cannot replace
  maximum temperature, daily rainfall sum or maximum gust inputs.
- Weather ingestion and forecast-model inference run together per selected site
  in a bounded worker callback, so a fresh snapshot does not wait for a separate
  model rotation. The standalone prediction job remains a repair/retry path.
  An explicit manual weather refresh also updates that site's saved predictions.

The repository-wide implementation request authorizes A/B/C/D integration in
this branch. These additive changes supersede the scaffold descriptions below:

- Crew categories retain `wildlife`, `water`, `access`, `fire`, `other`, and add
  `heat`, `lightning`, `flooding`, `mud` (migration 004). The prior five-category
  CHECK conflicted with AGENTS.md section 10. Uploads must decode as a complete
  JPEG, PNG or WebP, up to 5 MiB and 25 million pixels.
- Report history keeps its existing response and accepts optional `category`,
  `status=unresolved|resolved`, `q`, `since` (UTC ISO timestamp) filters. Coordinates
  remain available for map display. Filters never delete resolved records.
- Weather snapshots add `daily`, `daily_units`, `daily_timezone` and
  `daily_dates` (site-local ISO dates) from provider DAILY values, with explicit
  Celsius, mm and km/h. Forecasts cover today and tomorrow in the site's IANA
  timezone. Hourly/current times remain Unix UTC. Existing fields remain intact.
- Prediction migration 004 adds status, probability, range warnings and nullable
  geographic extrapolation. Unavailable predictions persist null scores and a
  reason. `provenance` retains model artifact, source/retrieval, input values,
  units, input kind and forecast date. `current_prediction` / `current_model_index`
  represent today's **full-day forecast**, never a current-instant hazard score.
  `prediction` / `model_index` retain next-day meaning. Predictions older than
  30 minutes, derived from failed/stale weather, or unavailable keep stored
  provenance but expose null displayed scores. No hourly interpolation.
- Outlook adds `crew_reports_monitoring` and `prediction_monitoring`. Wildlife
  coverage is crew-reported only; no sightings is not proof of no wildlife.
- Readiness reports implemented upload/scheduling accurately and distinguishes
  scheduler implementation from runtime delivery evidence. `requirements_complete`
  remains false while real strike data and river-specific monitoring are missing.
- The single worker registers predictions and scheduled briefings by default.
  Existing explicit factory registration remains accepted without double running
  built-in jobs. No additional worker process is introduced.
  `--site-id` restricts all built-in jobs, including briefings, to the requested
  sites. Available-prediction readiness counts exclude unavailable/stale rows.
- Migration 005 stores USGS NHD stream/river proximity context. The single
  worker queries NHD flowlines (`ftype=460`) intersecting a 1 km site buffer,
  caching successful context for 30 days and retrying failed requests. Outlook's
  `river_proximity` records the method/radius/source/features/retrieval and a
  separate monitoring state. No match means no mapped stream in that radius,
  never verified absence of flood exposure. This is centerline context, not a
  floodplain or river gauge. `flood_advisory` combines fresh context with complete
  modeled rainfall over the latest completed 18:00–06:00 local night. At least
  25 mm AND a nearby stream yields `active:true`, stable `id`, reason, source,
  severity `advisory`, action and event time. Unknown inputs yield `active:null`.
  This is an illustrative rainfall/location rule, not an official warning or
  ML output. Current hourly snapshots add `past_days=2` for that modeled proxy,
  including before 06:00 when the latest completed window begins two days ago.
- `POST /api/briefings/preview`, body `{site_id}`, builds an unpersisted live-fact
  preview before 18:00. It returns `{preview:true, delivered:false, briefing}`;
  it cannot reserve or suppress the scheduled delivery. Existing replay/manual
  delivery stays isolated. No external messaging channel exists.

Dates: UTC ISO 8601 unless explicitly marked as Unix seconds. Unknown values use null, never zero. Every component must distinguish live provider data, cached data, and demo file storage.

## Implemented now

- `GET /api/health`: `{application: "ready", database: "connected" | "not_configured" | "unavailable", as_of}`. Database status is not proof that schema or seeding is complete; verify `/api/sites?mode=live` too.
- `GET /api/sites?mode=live|demo`: `{mode, sites, count, risk_status: "not_implemented", as_of}`. Default is live. Missing database configuration returns HTTP 503; no silent fallback.
- `GET /api/sites/{id}?mode=live|demo`: `{mode, site, alerts: null, model_index: null, implementation: "foundation"}`. Null alerts means unimplemented, not no hazards.
- `GET /api/sites/{id}/weather?mode=live|demo`: `{site_id, site_mode, weather}`. `site_mode` describes plant storage; the weather call goes to the actual provider in either mode. `weather` carries source, fetched_at, cached, stale, current, current_units, hourly, hourly_units, note. Provider times are Unix seconds in UTC. Units are carried from the actual response. Initial provider failure returns 502. A refresh failure with a prior cache retains the data with `stale: true`.

Database-storage manual weather requests now persist successful responses in
Tiger Data. A storage failure returns 503, never a successful file fallback.
Demo-storage weather requests preserve the original manual, in-memory behavior.
The provider request covers three UTC calendar days to include all of tomorrow
in the selected plants' local timezones; use hourly.time rather than assuming
48 or 72 entries. No risk classification is inferred by this route.

### Stored Shift Outlook (A's additive integration)

`GET /api/outlook?mode=live|demo` reads stored evidence only. Default storage is
live. Invalid storage mode returns 400; missing/broken database or migrations
returns 503 in live storage. Demo returns the real file-based plants with null
stored weather; it does not use saved source-check responses as current data.
This route never contacts providers and supports dashboard polling without
upstream fan-out. Its event mode is explicitly live; replay is not accepted by
this route and replay snapshots are excluded by the database query.

Selected core fields from the original absent-data/demo shape (new fields are
documented in the following section):

```json
{
  "storage_mode": "demo",
  "event_mode": "live",
  "as_of": "2026-10-17T12:00:00+00:00",
  "weather_freshness_seconds": 1800,
  "ranking_status": "not_implemented",
  "count": 1,
  "sites": [
    {
      "site": {
        "id": 663,
        "source_plant_id": 663,
        "name": "Deerhaven Generating Station",
        "state": "FL",
        "county": "Alachua",
        "latitude": 29.7592,
        "longitude": -82.3878,
        "timezone": "America/New_York",
        "source_version": "EIA-860 2025 annual inventory"
      },
      "weather": null,
      "weather_monitoring": {
        "state": "UNAVAILABLE",
        "last_attempt_at": null,
        "last_success_at": null,
        "error_code": null
      },
      "coverage": "UNAVAILABLE",
      "hazard_state": null,
      "alerts": null,
      "model_index": null,
      "unavailable_layers": ["weather", "lightning", "flood", "wildfire", "wildlife", "model"],
      "reasons": ["No stored weather snapshot.", "Hazard integrations and ranking are not implemented."]
    }
  ]
}
```

The example shows one site; the response includes every plant in the selected
storage. When available, weather has the same source/current/hourly/unit fields
as the existing weather route, plus cached=true, stale,
current_evidence_type="modeled_current_conditions", and
hourly_evidence_type="forecast". Units and null values are preserved.

weather_monitoring.state is COMPLETE, PARTIAL, STALE, or UNAVAILABLE. A snapshot
is stale if retrieval is over 1800 seconds old, retrieval is in the future,
the most recent refresh failed, or current valid time is over 1800 seconds old
(or over 900 seconds in the future). Missing required weather values or units
produce PARTIAL with the fields identified in reasons. STALE takes precedence.
The source's actual current valid time is current.time, in Unix seconds UTC;
fetched_at is retrieval time. Hourly time entries are forecast valid times.

Overall coverage remains PARTIAL even with complete fresh weather because other
hazard integrations are unfinished. Stale stored weather makes coverage STALE.
An absent weather snapshot is UNAVAILABLE unless fresh official monitoring
provides partial coverage. Coverage does not certify safety. Live alert/hold/
prediction composition and ranking follow the definitions below; demo storage
has no evidence ranking. No daily model output is repeated as hourly data.

### Sponsor workflow additions (migration 002)

The preceding one-site JSON is the original absent-data/demo example. Live
Outlook now sets ranking_status="evidence_based" and includes these fields on
each row; existing weather fields remain intact:

| Field | Meaning |
|---|---|
| rank | One-based attention rank in live storage; null in demo storage. |
| official_alerts_monitoring | `{state: COMPLETE\|STALE\|UNAVAILABLE, fetched_at: ISO timestamp\|null}`. Official feed freshness is 600 seconds; a failed latest refresh is stale. |
| alerts | null when never monitored; otherwise a list of currently effective, unexpired official warnings/watches/advisories. Each includes id, event, severity, certainty, urgency, headline, description, instruction, effective, onset, expires, ends, area_description, source, evidence_type and hazard. hazard is flood, fire_weather or weather. |
| lightning_hold | null when absent/expired; otherwise site_id, hold_until, last_strike_at, source and seconds_remaining. Explicitly live state only. |
| unresolved_reports | Stored live unresolved crew-report metadata, excluding image bytes. B must implement upload/history/photo HTTP endpoints. |
| model_index | Genuine saved next-day score 0–10, otherwise null. Never derived from weather rules. |
| prediction | Actual saved prediction with site_id, valid_date, model_version, feature_version, score, computed_at and provenance, plus evidence_type="experimental_prediction" and label="experimental model index", or null. Daily granularity only. |
| planning_weather | `{target_date, heat_index_max_f, precipitation_sum_mm, soil_moisture_max_m3_m3, source, evidence_type, heat_method, note}`. Aggregates require every expected local-day hour and compatible units; otherwise the affected summary is null. Handles 23/25-hour DST days. |
| river_proximity | Currently `{status:"unknown", source:null}`. Never inferred from plant names. |

Ordering: active lightning holds; severe official warnings; other official
alerts; relevant unresolved reports; critical missing monitoring; then forecast
heat and actual model signals within those groups. Reasons identify evidence
and missing layers. A prediction cannot outrank an active hold or official alert.
Hazard state is STOP_WORK for a hold, ALERT for official alerts, ELEVATED for
unresolved reports, NO_ACTIVE_ALERTS only when the available official feed is
fresh with no active alert, otherwise null. Missing monitoring stays visible
independently. NO_ACTIVE_ALERTS is not a safety clearance.

Unavailable B/C outputs remain null/empty, never fabricated.
Stale official feeds retain earlier unexpired warnings; expiry clears only the
expired warning. A warning's ends timestamp can end it before expires.
Fire-weather alerts are not active-fire detections. Flood products come from
NWS point monitoring; river proximity/gauges and rainfall-based flood advisories
are not implemented. Derived heat uses the published NWS formula on modeled
temperature/RH, not Open-Meteo apparent_temperature or an official measurement.

`GET /api/sites/{id}/evidence?mode=live|demo` returns
`{storage_mode, event_mode:"live", as_of, evidence:<same Outlook row>}`; 404 for an
unknown site, 400 for an invalid storage mode and 503 on live database failure.

`GET /api/readiness?mode=live|demo` returns storage_mode, event_mode, as_of,
plant_count, requirements_complete=false, weather_fresh_sites,
official_alerts_fresh_sites, and feature objects: lightning {storage_ready,
live_feed_connected}, reports {storage_ready,upload_api_implemented}, briefings
{storage_ready,scheduled_delivery_implemented}, model {storage_ready,
saved_next_day_predictions}, plus limitations. Storage readiness does not mean
the business workflow or provider is implemented. This endpoint is read-only.

### Shared database repository interfaces for B/C

Import `from backend import db`. All mode arguments below are explicit event
modes (live or replay), never plant storage mode (live or demo). Timestamps must
be timezone-aware datetime values or ISO strings. Dates are ISO local dates.

```python
store_lightning_event(*, source, event_id, occurred_at, latitude, longitude,
                      affected_site_ids, mode)  # {accepted: bool, affected_sites: int}
get_lightning_holds(*, mode)  # {site_id: hold}; includes expired holds for inspection
save_crew_report(*, site_id, latitude, longitude, category, note, observed_at,
                 photo, photo_content_type, mode)  # UUID string
list_crew_reports(*, site_id=None, mode, unresolved_only=False)  # metadata list
get_report_photo(report_id, *, mode)  # {photo: bytes, photo_content_type} or None
save_briefing(*, site_id, delivery_local_date, target_date, body, facts, mode)  # UUID
list_briefings(*, site_id=None, mode)  # inbox records
save_prediction(*, site_id, valid_date, model_version, feature_version,
                score, computed_at, provenance, mode)
next_day_predictions(*, now, mode)  # {site_id: prediction}, each site's local tomorrow
```

B must validate strike time/provider and calculate the accepted sites within ten
miles before store_lightning_event. Storage atomically deduplicates by source,
event mode and event_id, and uses max expiration so delayed events cannot shorten
holds. Expiration never deletes unrelated hazards. Replay reset/session clocks
and verified strike ingestion remain B's work.

B must verify actual image content, validate coordinates/site/category/note and
implement HTTP upload limits before save_crew_report. Storage accepts JPEG, PNG
or WebP bytes, at most 5 MiB; category is wildlife, water, access, fire or other;
note is 1–2000 characters. Photos and metadata are stored together in PostgreSQL.
No temporary local path or fabricated photo URL is returned.

Briefings require target_date = delivery_local_date + one day. Unique
(site_id,event_mode,delivery_local_date) makes repeated generation return the
same UUID without overwriting the original body/facts. B owns timezone-aware
18:00 scheduling, deterministic generation and delivery APIs; none is implied by
calling the storage function. C supplies finite real scores in [0,10], actual
model/feature versions and provenance identifying model_artifact. Newer computed
predictions replace older same-version rows; delayed writes cannot replace them.
No trained model is bundled by A. Keep all future SQL in this adapter/migrations.

Site fields: `id`, `source_plant_id`, `name`, `state`, `county`, `latitude`, `longitude`, `timezone`, `source_version`. IDs are stable EIA plant identifiers. County names are not county FIPS; add a verified crosswalk before county ML joins.

## Next owner interfaces

- Alerts owner: add independent active alerts and lightning_hold_until; preserve other hazards when a hold expires. Keep replay separate from live.
- Reports owner: `POST /api/reports` with validated image, site ID, latitude, longitude, category and note; `GET /api/reports?site_id=...`.
- Briefing owner: `GET /api/briefings?site_id=...`; persist site/local-date uniqueness; scheduled worker separate from Flask.
- ML owner: predictions keyed by site ID, valid_date, model_version, feature_version, score and computed_at. Score may be null until genuinely computed.

Current role letters follow the human's updated assignment: A database/backend/
worker, B lightning/reports/briefings, C ML, D frontend. A's actual coordination,
worker Job interface, verification and pending owner actions are in
docs/coordination/A.md. No B/C job is automatically imported or claimed working.

Do not implement a catch-all endpoint that returns plausible success for unfinished features. Unknown API routes return 404. Update this file and notify affected owners before changing field names.


## Operational events (proposed, Workstream B)

Status: implemented in `backend/ops_routes.py` on top of A's repositories (`backend/db.py`). Additive only; no existing field changed. Full example responses: `docs/fixtures/ops_*.json` (each has `"fixture": true` and `http_status`). Lists below are shortened to one item.

Storage: strikes and holds use A's `lightning_events` / `lightning_holds` via `db.store_lightning_event`; reports use `crew_reports`; briefings use `briefings`. B adds only `lightning_feed_status`, `replay_sessions` and `ops_events` (migration `003_operational_events.sql`). `lightning_strikes` (from B's earlier proposal) is no longer written by the application.

Rules for every endpoint in this section:
- `event_mode` is `live` or `replay` (default `live`). It is event provenance, unrelated to the storage field `mode` (live | demo). Invalid values return 400.
- Replay responses carry `"label": "simulated replay"`; live responses carry `"label": null`. Replay never changes live holds, alerts, ranking or briefings.
- Timestamps are UTC ISO 8601 in offset form (`+00:00`), produced with `backend.outlook.serialize`. Fields named `*_local_*` / `delivered_local_time` are site-local and say so.
- Hazard state (`STOP_WORK`, `NO_ACTIVE_ALERTS`, or `null` = unknown) is separate from monitoring coverage (`COMPLETE`, `STALE`, `UNAVAILABLE`). Show both. `coverage.feed_connected` distinguishes a connected feed with no strikes (`COMPLETE`, no `last_event_received_at`) from a disconnected feed (`UNAVAILABLE`). The words "safe" and "all clear" are never used.
- Errors: 400 `invalid_input`; 404 `not_found`; 409 `not_due` (live briefing before site-local 6 PM); 413 `photo_too_large`; 503 `database_unavailable` (generic message to clients, underlying driver error logged server-side without connection details; no silent fallback). Body: `{"error": "...", "code": "..."}`.

### Lightning

`GET /api/sites/{id}/lightning?event_mode=live|replay` - one site's hold and coverage. "Held" is computed from `lightning_holds.hold_until` and the clock (replay uses the replay clock). `hazard.last_strike` mirrors `lightning_holds.source` / `last_strike_at`. With no live feed connected, live coverage is `UNAVAILABLE` and `hazard.state` is `null`.

Live, no feed connected (`ops_lightning_live.json`):
```json
{
  "as_of": "2026-10-17T22:00:00+00:00",
  "clock": "server",
  "coverage": {
    "feed_connected": false,
    "last_event_received_at": null,
    "last_feed_check_at": null,
    "note": "No live lightning feed is connected. The absence of a hold is not evidence of no strikes.",
    "source": "live-strike-feed",
    "status": "UNAVAILABLE"
  },
  "event_mode": "live",
  "hazard": {
    "hold_active": false,
    "hold_until": null,
    "last_strike": null,
    "seconds_remaining": 0,
    "site_id": 663,
    "site_name": "Deerhaven Generating Station",
    "state": null,
    "state_reason": "Lightning hazard state unknown: monitoring coverage is UNAVAILABLE.",
    "type": "lightning"
  },
  "hold_minutes": 30,
  "label": null,
  "note": "Lightning hold status covers only lightning. When the countdown ends, only the lightning hold is lifted; other hazards and feed coverage are unchanged.",
  "radius_miles": 10,
  "site_id": 663
}
```

Replay, during a hold (`ops_lightning_replay_hold.json`):
```json
{
  "as_of": "2026-10-17T22:20:00+00:00",
  "clock": "replay",
  "coverage": {
    "feed_connected": true,
    "last_event_received_at": "2026-10-17T22:20:00+00:00",
    "last_feed_check_at": "2026-10-17T22:20:00+00:00",
    "note": "Simulated replay. Not real lightning data.",
    "source": "simulated replay script",
    "status": "COMPLETE"
  },
  "event_mode": "replay",
  "hazard": {
    "hold_active": true,
    "hold_until": "2026-10-17T22:40:00+00:00",
    "last_strike": {
      "occurred_at": "2026-10-17T22:10:00+00:00",
      "source": "simulated-replay"
    },
    "seconds_remaining": 1200,
    "site_id": 663,
    "site_name": "Deerhaven Generating Station",
    "state": "STOP_WORK",
    "state_reason": "Lightning strike within 10 miles in the last 30 minutes.",
    "type": "lightning"
  },
  "hold_minutes": 30,
  "label": "simulated replay",
  "note": "Lightning hold status covers only lightning. When the countdown ends, only the lightning hold is lifted; other hazards and feed coverage are unchanged.",
  "radius_miles": 10,
  "site_id": 663
}
```

`GET /api/lightning/holds?event_mode=live|replay` - active holds only, longest remaining first, plus coverage (`ops_lightning_holds.json`):
```json
{
  "as_of": "2026-10-17T22:20:00+00:00",
  "count": 3,
  "coverage": {
    "feed_connected": true,
    "last_event_received_at": "2026-10-17T22:20:00+00:00",
    "last_feed_check_at": "2026-10-17T22:20:00+00:00",
    "note": "Simulated replay. Not real lightning data.",
    "source": "simulated replay script",
    "status": "COMPLETE"
  },
  "event_mode": "replay",
  "hold_minutes": 30,
  "holds": [
    {
      "hold_active": true,
      "hold_until": "2026-10-17T22:45:00+00:00",
      "last_strike": {
        "occurred_at": "2026-10-17T22:15:00+00:00",
        "source": "simulated-replay"
      },
      "seconds_remaining": 1500,
      "site_id": 6051,
      "site_name": "Edwin I Hatch"
    }
  ],
  "label": "simulated replay",
  "note": "Lightning hold status covers only lightning. When the countdown ends, only the lightning hold is lifted; other hazards and feed coverage are unchanged.",
  "radius_miles": 10
}
```

`POST /api/lightning/strikes` - JSON body. Only `event_mode: "replay"` is accepted over HTTP, and only while a replay session is running (otherwise 400). Live strikes come only from a configured live feed inside the worker. Sites within 10 miles (16.0934 km, haversine) are passed to `db.store_lightning_event`, which deduplicates `(source, event_mode, event_id)` and sets `hold_until = GREATEST(existing, strike + 30 min)`. A duplicate returns 200 with `accepted: false, duplicate: true`. `effect` is `started`, `extended` or `no_change_older_strike`.

Request:
```json
{
  "event_id": "demo-manual-001",
  "source": "simulated-replay",
  "latitude": 29.7592,
  "longitude": -82.3545,
  "occurred_at": "2026-10-17T22:20:00+00:00",
  "event_mode": "replay"
}
```

Response 200 (`ops_strike_ingest.json`):
```json
{
  "accepted": true,
  "affected_sites": [
    {
      "distance_km": 3.22,
      "distance_miles": 2.0,
      "effect": "extended",
      "hold_until": "2026-10-17T22:50:00+00:00",
      "site_id": 663,
      "site_name": "Deerhaven Generating Station"
    }
  ],
  "duplicate": false,
  "event_mode": "replay",
  "label": "simulated replay",
  "strike": {
    "event_id": "demo-manual-001",
    "latitude": 29.7592,
    "longitude": -82.35446,
    "occurred_at": "2026-10-17T22:20:00+00:00",
    "source": "simulated-replay"
  }
}
```

### Simulated replay

`POST /api/replay/sessions` - body `{"speed": 10}` (1-120, default 10). Deletes all `event_mode = 'replay'` rows (never live rows, never `lightning_strikes`), starts a session in `replay_sessions`, and replays `docs/replay/strikes.json` on one replay clock: `replay_now = replay_epoch + (wall_now - started_at) * speed`. Scripted strikes are applied when replay-mode endpoints are read. Response 201 (`ops_replay_session.json`):
```json
{
  "active": true,
  "delivered_strikes": 1,
  "label": "simulated replay",
  "note": "Simulated replay. Replay timestamps come from the replay clock and are not real observations.",
  "replay_elapsed_seconds": 0,
  "replay_now": "2026-10-17T22:00:00+00:00",
  "scripted_strikes": 9,
  "session": {
    "replay_epoch": "2026-10-17T22:00:00+00:00",
    "session_id": "61caec5d845d",
    "speed": 10.0,
    "started_at": "2026-10-17T22:00:00+00:00"
  }
}
```

`GET /api/replay/session` - same shape; `{"active": false, "session": null, "replay_now": null, ...}` when none is running.

`POST /api/replay/reset` - removes replay rows only:
```json
{
  "reset": true,
  "active": false,
  "label": "simulated replay",
  "note": "All simulated replay holds, events and briefings were removed. Live data was not touched."
}
```

### Crew reports

`POST /api/reports` - `multipart/form-data` with `site_id`, `latitude`, `longitude`, `category` (exactly: wildlife | water | access | fire | other), `note` (required, 1-2000 characters) and `photo` (required; JPEG, PNG or WebP verified by file signature; at most 5 MiB; stored in `crew_reports.photo`). `observed_at` is server time. More than 5 km from the site gives `location_flag: "far_from_site"` (derived, not stored) but is accepted. Reports are always real (`event_mode: "live"`). Response 201 (`ops_report_created.json`):
```json
{
  "report": {
    "category": "wildlife",
    "created_at": "2026-10-17T22:02:00+00:00",
    "distance_from_site_km": 0.19,
    "event_mode": "live",
    "evidence_type": "crew_report",
    "has_photo": true,
    "id": "b5de736f-e56d-46e0-be9d-dc59d5bc8190",
    "latitude": 29.7601,
    "location_flag": null,
    "longitude": -82.3861,
    "note": "Alligator seen near the north culvert.",
    "observed_at": "2026-10-17T22:02:00+00:00",
    "photo_content_type": "image/png",
    "photo_url": "/api/reports/b5de736f-e56d-46e0-be9d-dc59d5bc8190/photo",
    "resolved_at": null,
    "site_id": 663,
    "status": "unresolved"
  }
}
```

`GET /api/reports?site_id={id}` - site history, newest first, no image bytes. `current_unresolved` is current evidence; `history` is every report including resolved ones. `status` is derived from `resolved_at` (`ops_reports.json`):
```json
{
  "as_of": "2026-10-17T22:04:00+00:00",
  "counts": {
    "total": 2,
    "unresolved": 1
  },
  "current_unresolved": [
    {
      "category": "wildlife",
      "created_at": "2026-10-17T22:02:00+00:00",
      "distance_from_site_km": 0.19,
      "event_mode": "live",
      "evidence_type": "crew_report",
      "has_photo": true,
      "id": "b5de736f-e56d-46e0-be9d-dc59d5bc8190",
      "latitude": 29.7601,
      "location_flag": null,
      "longitude": -82.3861,
      "note": "Alligator seen near the north culvert.",
      "observed_at": "2026-10-17T22:02:00+00:00",
      "photo_content_type": "image/png",
      "photo_url": "/api/reports/b5de736f-e56d-46e0-be9d-dc59d5bc8190/photo",
      "resolved_at": null,
      "site_id": 663,
      "status": "unresolved"
    }
  ],
  "event_mode": "live",
  "history": [
    {
      "category": "access",
      "created_at": "2026-10-17T22:03:00+00:00",
      "distance_from_site_km": 0.19,
      "event_mode": "live",
      "evidence_type": "crew_report",
      "has_photo": true,
      "id": "cf9c5b30-1067-411c-b03f-65c04c16b8a7",
      "latitude": 29.7601,
      "location_flag": null,
      "longitude": -82.3861,
      "note": "Access road rutted at gate 2.",
      "observed_at": "2026-10-17T22:03:00+00:00",
      "photo_content_type": "image/png",
      "photo_url": "/api/reports/cf9c5b30-1067-411c-b03f-65c04c16b8a7/photo",
      "resolved_at": "2026-10-17T22:04:00+00:00",
      "site_id": 663,
      "status": "resolved"
    }
  ],
  "note": "Crew reports are field observations from people on site. \"No recent reports\" does not mean no hazard.",
  "site_id": 663
}
```

`GET /api/reports/{id}/photo` - the image bytes with the stored `Content-Type` and `X-Content-Type-Options: nosniff`; 404 when the report does not exist.

`POST /api/reports/{id}/resolve` - idempotent; sets `resolved_at` once and the report stays in history (`ops_report_resolved.json`):
```json
{
  "report": {
    "category": "access",
    "created_at": "2026-10-17T22:03:00+00:00",
    "distance_from_site_km": 0.19,
    "event_mode": "live",
    "evidence_type": "crew_report",
    "has_photo": true,
    "id": "cf9c5b30-1067-411c-b03f-65c04c16b8a7",
    "latitude": 29.7601,
    "location_flag": null,
    "longitude": -82.3861,
    "note": "Access road rutted at gate 2.",
    "observed_at": "2026-10-17T22:03:00+00:00",
    "photo_content_type": "image/png",
    "photo_url": "/api/reports/cf9c5b30-1067-411c-b03f-65c04c16b8a7/photo",
    "resolved_at": "2026-10-17T22:04:00+00:00",
    "site_id": 663,
    "status": "resolved"
  }
}
```

### Briefings

One briefing per `(site_id, event_mode, delivery_local_date)`, enforced by A's `briefings` table. `delivery_local_date` is the site-local date of the 6 PM delivery; `forecast_target_date` (stored as `target_date`) is the next local day. `body_text` is stored as `body`; the full structured briefing is stored in `facts`. Forecast, official alerts and the model index come from A's stored Outlook evidence when available; otherwise they read "unavailable" and are listed in `missing_inputs`. Scheduled live briefings come from A's single worker via `backend.briefings:worker_jobs` (`Job('briefings', scheduled_briefings, 30)`).

`GET /api/briefings?site_id={id}&event_mode=live|replay` - `site_id` optional. Shape: `{"site_id", "event_mode", "label", "briefings": [<briefing>], "count", "as_of"}` (`ops_briefings.json`).

`POST /api/briefings/generate` - body `{"site_id": 663, "event_mode": "replay"}` (default `replay`). Uses the same idempotent function as the scheduler. `replay` generates at any time on the replay clock. `live` works only after site-local 6 PM (otherwise 409 `not_due`). Returns 201 `{"created": true, ...}` or 200 `{"created": false, ...}` (`ops_briefing_generate.json`, sections shortened):
```json
{
  "briefing": {
    "body_text": "SIMULATED REPLAY. Next-day briefing for Deerhaven Generating Station (America/New_York). Delivery date 2026-10-17 at 6:00 PM site-local time; forecast target date 2026-10-18.\n\nTomorrow's forecast\nForecast unavailable: no stored next-day forecast for this site. No forecast values are shown.\n\nToday's evidence\nOfficial alerts: unavailable. The absence of alerts here is not evidence that no warnings exist.\nLightning holds today: 1 hold(s) started, 2 extension(s); latest hold end 18:50 site-local (2026-10-17T22:50:00+00:00).\nUnresolved crew reports (real crew reports, not simulated): 1.\n- wildlife: Alligator seen near the north culvert. (reported 2026-10-17T22:02:00+00:00)\n\nExperimental model index\nExperimental model index: unavailable (no saved prediction for the target date).\n\nMissing data\nMissing: forecast.\nMissing: official alerts.\nMissing: model index.",
    "delivered_at": "2026-10-17T23:20:00+00:00",
    "delivered_local_time": "2026-10-17T19:20:00-04:00",
    "delivery_local_date": "2026-10-17",
    "event_mode": "replay",
    "forecast_target_date": "2026-10-18",
    "generator": "template-v1",
    "id": "7de41ed6-a444-4511-a20d-5008599a6d9e",
    "label": "simulated replay",
    "missing_inputs": [
      "forecast",
      "official alerts",
      "model index"
    ],
    "note": "Generated from supplied facts only. Forecasts, official alerts, crew reports and the experimental model index are different kinds of evidence. Missing inputs are listed, not filled in.",
    "rewrite_status": "not_requested",
    "rewritten_text": null,
    "scheduled_local_time": "18:00",
    "sections": [
      {
        "available": false,
        "evidence_type": "forecast",
        "key": "forecast",
        "lines": [
          "Forecast unavailable: no stored next-day forecast for this site. No forecast values are shown."
        ],
        "title": "Tomorrow's forecast"
      },
      {
        "...": "today_evidence, model, missing_data sections (see fixture)"
      }
    ],
    "site_id": 663,
    "site_name": "Deerhaven Generating Station",
    "timezone": "America/New_York",
    "trigger": "manual"
  },
  "created": true
}
```

### Evidence timeline

`GET /api/sites/{id}/timeline?event_mode=live|replay` - chronological (oldest first) events for one site, derived from canonical records so it agrees with the Outlook:
- `lightning_hold_started` / `lightning_hold_extended`: rows in `ops_events`, each with `ref_table: "lightning_events"` and `ref_key` = that strike's `(source, event_mode, event_id)`.
- `lightning_hold_expired`: computed from those events and the current `lightning_holds.hold_until` (`ref_table: "lightning_holds"`); it ends only the lightning hold.
- `report_created` / `report_resolved`: read from `crew_reports` (`ref_table: "crew_reports"`, `ref_key: {"id"}`).
- `briefing_delivered`: read from `briefings` (`ref_table: "briefings"`, `ref_key: {"id"}`).

Each event has `id, site_id, type, occurred_at, source, event_mode, summary, ref_table, ref_key, details`. A live query returns live records only. A replay query returns replay records plus live crew-report events, which keep `event_mode: "live"`. Replay records never appear in live queries. Live reports use the wall clock; replay events use the replay clock, which starts at the session's wall-clock start and runs faster.

Replay example (`ops_timeline.json` -> `examples.replay`):
```json
{
  "as_of": "2026-10-17T23:20:00+00:00",
  "count": 8,
  "event_mode": "replay",
  "events": [
    {
      "details": {
        "distance_km": 14.48,
        "distance_miles": 9.0,
        "hold_until": "2026-10-17T22:30:00+00:00",
        "lightning_hold": {
          "event_mode": "replay",
          "site_id": 663
        },
        "previous_hold_until": null
      },
      "event_mode": "replay",
      "id": "replay:simulated-replay:dh-001:663",
      "occurred_at": "2026-10-17T22:00:00+00:00",
      "ref_key": {
        "event_id": "dh-001",
        "event_mode": "replay",
        "source": "simulated-replay"
      },
      "ref_table": "lightning_events",
      "site_id": 663,
      "source": "simulated-replay",
      "summary": "Simulated replay: Strike 9.0 mi from site started a 30-minute lightning stop-work hold.",
      "type": "lightning_hold_started"
    },
    {
      "details": {
        "category": "wildlife",
        "has_photo": true,
        "report_id": "b5de736f-e56d-46e0-be9d-dc59d5bc8190"
      },
      "event_mode": "live",
      "id": "live:report:b5de736f-e56d-46e0-be9d-dc59d5bc8190:created",
      "occurred_at": "2026-10-17T22:02:00+00:00",
      "ref_key": {
        "id": "b5de736f-e56d-46e0-be9d-dc59d5bc8190"
      },
      "ref_table": "crew_reports",
      "site_id": 663,
      "source": "crew_report",
      "summary": "Crew report (wildlife) with photo: Alligator seen near the north culvert.",
      "type": "report_created"
    },
    {
      "details": {
        "category": "access",
        "has_photo": true,
        "report_id": "cf9c5b30-1067-411c-b03f-65c04c16b8a7"
      },
      "event_mode": "live",
      "id": "live:report:cf9c5b30-1067-411c-b03f-65c04c16b8a7:created",
      "occurred_at": "2026-10-17T22:03:00+00:00",
      "ref_key": {
        "id": "cf9c5b30-1067-411c-b03f-65c04c16b8a7"
      },
      "ref_table": "crew_reports",
      "site_id": 663,
      "source": "crew_report",
      "summary": "Crew report (access) with photo: Access road rutted at gate 2.",
      "type": "report_created"
    },
    {
      "details": {
        "category": "access",
        "has_photo": true,
        "report_id": "cf9c5b30-1067-411c-b03f-65c04c16b8a7"
      },
      "event_mode": "live",
      "id": "live:report:cf9c5b30-1067-411c-b03f-65c04c16b8a7:resolved",
      "occurred_at": "2026-10-17T22:04:00+00:00",
      "ref_key": {
        "id": "cf9c5b30-1067-411c-b03f-65c04c16b8a7"
      },
      "ref_table": "crew_reports",
      "site_id": 663,
      "source": "crew_report",
      "summary": "Crew report (access) marked resolved; it stays in site history.",
      "type": "report_resolved"
    },
    {
      "details": {
        "distance_km": 8.05,
        "distance_miles": 5.0,
        "hold_until": "2026-10-17T22:40:00+00:00",
        "lightning_hold": {
          "event_mode": "replay",
          "site_id": 663
        },
        "previous_hold_until": "2026-10-17T22:30:00+00:00"
      },
      "event_mode": "replay",
      "id": "replay:simulated-replay:dh-003:663",
      "occurred_at": "2026-10-17T22:10:00+00:00",
      "ref_key": {
        "event_id": "dh-003",
        "event_mode": "replay",
        "source": "simulated-replay"
      },
      "ref_table": "lightning_events",
      "site_id": 663,
      "source": "simulated-replay",
      "summary": "Simulated replay: Strike 5.0 mi from site extended the lightning stop-work hold.",
      "type": "lightning_hold_extended"
    },
    {
      "details": {
        "distance_km": 3.22,
        "distance_miles": 2.0,
        "hold_until": "2026-10-17T22:50:00+00:00",
        "lightning_hold": {
          "event_mode": "replay",
          "site_id": 663
        },
        "previous_hold_until": "2026-10-17T22:40:00+00:00"
      },
      "event_mode": "replay",
      "id": "replay:simulated-replay:demo-manual-001:663",
      "occurred_at": "2026-10-17T22:20:00+00:00",
      "ref_key": {
        "event_id": "demo-manual-001",
        "event_mode": "replay",
        "source": "simulated-replay"
      },
      "ref_table": "lightning_events",
      "site_id": 663,
      "source": "simulated-replay",
      "summary": "Simulated replay: Strike 2.0 mi from site extended the lightning stop-work hold.",
      "type": "lightning_hold_extended"
    },
    {
      "details": {
        "clears_only": "lightning_hold",
        "hold_until": "2026-10-17T22:50:00+00:00"
      },
      "event_mode": "replay",
      "id": "replay:hold-expired:663:2026-10-17T22:50:00+00:00",
      "occurred_at": "2026-10-17T22:50:00+00:00",
      "ref_key": {
        "event_mode": "replay",
        "site_id": 663
      },
      "ref_table": "lightning_holds",
      "site_id": 663,
      "source": "planit-control (computed from hold_until)",
      "summary": "Simulated replay: Lightning hold countdown ended. Only the lightning hold is lifted; other hazards and lightning feed coverage are unchanged.",
      "type": "lightning_hold_expired"
    },
    {
      "details": {
        "briefing_id": "7de41ed6-a444-4511-a20d-5008599a6d9e",
        "delivery_local_date": "2026-10-17",
        "forecast_target_date": "2026-10-18",
        "missing_inputs": [
          "forecast",
          "official alerts",
          "model index"
        ],
        "trigger": "manual"
      },
      "event_mode": "replay",
      "id": "replay:briefing:7de41ed6-a444-4511-a20d-5008599a6d9e",
      "occurred_at": "2026-10-17T23:20:00+00:00",
      "ref_key": {
        "id": "7de41ed6-a444-4511-a20d-5008599a6d9e"
      },
      "ref_table": "briefings",
      "site_id": 663,
      "source": "planit-control briefing generator",
      "summary": "Simulated replay: Next-day briefing delivered for 2026-10-18 (forecast target date).",
      "type": "briefing_delivered"
    }
  ],
  "includes": [
    "simulated replay events",
    "live crew reports (event_mode \"live\")"
  ],
  "label": "simulated replay",
  "note": null,
  "site_id": 663
}
```

Empty state (`examples.empty`):
```json
{
  "as_of": "2026-10-17T22:08:00+00:00",
  "count": 0,
  "event_mode": "live",
  "events": [],
  "includes": [
    "live events only"
  ],
  "label": null,
  "note": "No operational events recorded for this site. This does not mean there is no hazard.",
  "site_id": 6051
}
```

Error bodies (`ops_errors.json`):
```json
{
  "invalid_input_400": {
    "status": 400,
    "body": {
      "code": "invalid_input",
      "error": "event_mode must be live or replay"
    }
  },
  "not_found_404": {
    "status": 404,
    "body": {
      "code": "not_found",
      "error": "Site not found"
    }
  },
  "live_briefing_not_due_409": {
    "status": 409,
    "body": {
      "code": "not_due",
      "error": "Live briefings for this site are delivered at 6 PM America/Chicago time; it is 17:30 there. Use event_mode \"replay\" to demonstrate."
    }
  },
  "photo_too_large_413": {
    "status": 413,
    "body": {
      "code": "photo_too_large",
      "error": "photo must be 5 MiB or smaller"
    }
  },
  "database_unavailable_503": {
    "status": 503,
    "body": {
      "error": "DATABASE_URL is not configured. Add your Tiger Data URI to .env.",
      "code": "database_unavailable"
    }
  }
}
```
