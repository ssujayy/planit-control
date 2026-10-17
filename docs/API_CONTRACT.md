# Foundation API contract

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

