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


## Operational events (proposed, Workstream B)

Status: proposed by Workstream B and implemented in `backend/ops_routes.py`. Additive only; no existing field changed. Full example responses live in `docs/fixtures/ops_*.json` (each marked `"fixture": true`, with `http_status`). Lists below are shortened to one item.

Rules for every endpoint in this section:
- `event_mode` is `live` or `replay` (default `live`). It is event provenance and is unrelated to the storage field `mode` (live | demo). An invalid value returns 400.
- Replay responses carry `"label": "simulated replay"`; live responses carry `"label": null`. Replay never changes live holds, alerts, ranking or briefings.
- Times are UTC ISO 8601 with `Z`, except fields named `*_local_*` / `delivered_local_time`, which are site-local and say so.
- Hazard state (`STOP_WORK`, `NO_ACTIVE_ALERTS`, or `null` = unknown) is separate from monitoring coverage (`COMPLETE`, `STALE`, `UNAVAILABLE`). Show both. `null` state with `UNAVAILABLE` coverage is "unknown", never "clear". The words "safe" and "all clear" are never used.
- Errors: 400 `invalid_input`; 404 `not_found` (unknown site, report or photo); 409 `not_due` (live briefing before site-local 6 PM); 413 `photo_too_large`; 503 `database_unavailable` (no silent fallback). Body: `{"error": "...", "code": "..."}`.

### Lightning

`GET /api/sites/{id}/lightning?event_mode=live|replay` - one site's lightning hold and coverage. "Held" is computed from `hold_until` and the clock (replay uses the replay clock). With no live feed connected, live coverage is `UNAVAILABLE` and `hazard.state` is `null`.

Live, no feed connected (`ops_lightning_live.json`):
```json
{
  "as_of": "2026-10-17T22:00:00Z",
  "clock": "server",
  "coverage": {
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
    "last_qualifying_strike": null,
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
  "as_of": "2026-10-17T22:20:00Z",
  "clock": "replay",
  "coverage": {
    "last_event_received_at": "2026-10-17T22:20:00Z",
    "last_feed_check_at": "2026-10-17T22:20:00Z",
    "note": "Simulated replay. Not real lightning data.",
    "source": "simulated replay script",
    "status": "COMPLETE"
  },
  "event_mode": "replay",
  "hazard": {
    "hold_active": true,
    "hold_until": "2026-10-17T22:40:00Z",
    "last_qualifying_strike": {
      "distance_km": 8.05,
      "distance_miles": 5.0,
      "event_id": "dh-003",
      "occurred_at": "2026-10-17T22:10:00Z",
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
  "as_of": "2026-10-17T22:20:00Z",
  "count": 3,
  "coverage": {
    "last_event_received_at": "2026-10-17T22:20:00Z",
    "last_feed_check_at": "2026-10-17T22:20:00Z",
    "note": "Simulated replay. Not real lightning data.",
    "source": "simulated replay script",
    "status": "COMPLETE"
  },
  "event_mode": "replay",
  "hold_minutes": 30,
  "holds": [
    {
      "hold_active": true,
      "hold_until": "2026-10-17T22:45:00Z",
      "last_qualifying_strike": {
        "distance_km": 4.83,
        "distance_miles": 3.0,
        "event_id": "ht-001",
        "occurred_at": "2026-10-17T22:15:00Z",
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

`POST /api/lightning/strikes` - JSON body. Only `event_mode: "replay"` is accepted over HTTP, and only while a replay session is running (otherwise 400). Live strikes come only from a configured live feed inside the worker. Duplicate `(event_mode, source, event_id)` returns 200 with `accepted: false, duplicate: true`. `effect` is `started`, `extended` or `no_change_older_strike`.

Request:
```json
{
  "event_id": "demo-manual-001",
  "source": "simulated-replay",
  "latitude": 29.7592,
  "longitude": -82.3545,
  "occurred_at": "2026-10-17T22:20:00Z",
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
      "hold_until": "2026-10-17T22:50:00Z",
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
    "occurred_at": "2026-10-17T22:20:00Z",
    "source": "simulated-replay"
  }
}
```

### Simulated replay

`POST /api/replay/sessions` - body `{"speed": 10}` (1-120, default 10). Deletes all previous replay rows, starts a session, and replays `docs/replay/strikes.json` on one replay clock: `replay_now = replay_epoch + (wall_now - started_at) * speed`. Scripted strikes are applied when replay-mode endpoints are read. Response 201 (`ops_replay_session.json`):
```json
{
  "active": true,
  "delivered_strikes": 1,
  "label": "simulated replay",
  "note": "Simulated replay. Replay timestamps come from the replay clock and are not real observations.",
  "replay_elapsed_seconds": 0,
  "replay_now": "2026-10-17T22:00:00Z",
  "scripted_strikes": 9,
  "session": {
    "replay_epoch": "2026-10-17T22:00:00Z",
    "session_id": "8e62c41a8611",
    "speed": 10.0,
    "started_at": "2026-10-17T22:00:00Z"
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

`POST /api/reports` - `multipart/form-data` with `site_id`, `latitude`, `longitude`, `category` (heat | lightning | flooding | mud | fire | wildlife | other), optional `note` (max 1000 chars) and optional `photo` (JPEG or PNG verified by file signature, max 5 MB, stored in the database). `created_at` is server time. More than 5 km from the site sets `location_flag: "far_from_site"` but is accepted. Reports are always real (`event_mode: "live"`). Response 201 (`ops_report_created.json`):
```json
{
  "report": {
    "category": "wildlife",
    "created_at": "2026-10-17T22:02:00Z",
    "distance_from_site_km": 0.19,
    "event_mode": "live",
    "evidence_type": "crew_report",
    "has_photo": true,
    "id": "a20a5dcadc94457199df16f43de688f6",
    "latitude": 29.7601,
    "location_flag": null,
    "longitude": -82.3861,
    "note": "Alligator seen near the north culvert.",
    "photo_content_type": "image/png",
    "photo_size_bytes": 72,
    "photo_url": "/api/reports/a20a5dcadc94457199df16f43de688f6/photo",
    "resolved_at": null,
    "site_id": 663,
    "status": "unresolved"
  }
}
```

`GET /api/reports?site_id={id}` - site history, newest first, no image bytes. `current_unresolved` is current evidence; `history` is every report including resolved ones (`ops_reports.json`):
```json
{
  "as_of": "2026-10-17T22:04:00Z",
  "counts": {
    "total": 2,
    "unresolved": 1
  },
  "current_unresolved": [
    {
      "category": "wildlife",
      "created_at": "2026-10-17T22:02:00Z",
      "distance_from_site_km": 0.19,
      "event_mode": "live",
      "evidence_type": "crew_report",
      "has_photo": true,
      "id": "a20a5dcadc94457199df16f43de688f6",
      "latitude": 29.7601,
      "location_flag": null,
      "longitude": -82.3861,
      "note": "Alligator seen near the north culvert.",
      "photo_content_type": "image/png",
      "photo_size_bytes": 72,
      "photo_url": "/api/reports/a20a5dcadc94457199df16f43de688f6/photo",
      "resolved_at": null,
      "site_id": 663,
      "status": "unresolved"
    }
  ],
  "event_mode": "live",
  "history": [
    {
      "category": "mud",
      "created_at": "2026-10-17T22:03:00Z",
      "distance_from_site_km": 0.19,
      "event_mode": "live",
      "evidence_type": "crew_report",
      "has_photo": false,
      "id": "85f61b593b4f4f8d9a3796794f36aecd",
      "latitude": 29.7601,
      "location_flag": null,
      "longitude": -82.3861,
      "note": "Access road rutted at gate 2.",
      "photo_content_type": null,
      "photo_size_bytes": null,
      "photo_url": null,
      "resolved_at": "2026-10-17T22:04:00Z",
      "site_id": 663,
      "status": "resolved"
    }
  ],
  "note": "Crew reports are field observations from people on site. \"No recent reports\" does not mean no hazard.",
  "site_id": 663
}
```

`GET /api/reports/{id}/photo` - the image bytes with `Content-Type: image/jpeg|image/png` and `X-Content-Type-Options: nosniff`; 404 when the report or photo does not exist.

`POST /api/reports/{id}/resolve` - idempotent; the report stays in history with `resolved_at` (`ops_report_resolved.json`):
```json
{
  "report": {
    "category": "mud",
    "created_at": "2026-10-17T22:03:00Z",
    "distance_from_site_km": 0.19,
    "event_mode": "live",
    "evidence_type": "crew_report",
    "has_photo": false,
    "id": "85f61b593b4f4f8d9a3796794f36aecd",
    "latitude": 29.7601,
    "location_flag": null,
    "longitude": -82.3861,
    "note": "Access road rutted at gate 2.",
    "photo_content_type": null,
    "photo_size_bytes": null,
    "photo_url": null,
    "resolved_at": "2026-10-17T22:04:00Z",
    "site_id": 663,
    "status": "resolved"
  }
}
```

### Briefings

One briefing per `(site_id, delivery_local_date, event_mode)`, enforced by the database. `delivery_local_date` is the site-local date of the 6 PM delivery; `forecast_target_date` is the next local day. Missing inputs are listed in `missing_inputs` and the `missing_data` section; they are never filled in. Scheduled live briefings come from the single worker calling `backend.briefings.run_due_briefings`.

`GET /api/briefings?site_id={id}&event_mode=live|replay` - `site_id` optional (all sites, newest first, max 200). Shape: `{"site_id", "event_mode", "label", "briefings": [<briefing>], "count", "as_of"}` (`ops_briefings.json`).

`POST /api/briefings/generate` - body `{"site_id": 663, "event_mode": "replay"}` (default `replay`). Uses the same idempotent function as the scheduler. `replay` generates at any time on the replay clock. `live` works only after site-local 6 PM (otherwise 409 `not_due`), so a manual run cannot fake the scheduled delivery. Returns 201 `{"created": true, ...}` or 200 `{"created": false, ...}` with the existing briefing (`ops_briefing_generate.json`, sections shortened):
```json
{
  "briefing": {
    "body_text": "SIMULATED REPLAY. Next-day briefing for Deerhaven Generating Station (America/New_York). Delivery date 2026-10-17 at 6:00 PM site-local time; forecast target date 2026-10-18.\n\nTomorrow's forecast\nForecast unavailable: no stored next-day forecast for this site. No forecast values are shown.\n\nToday's evidence\nOfficial alerts: not yet integrated. The absence of alerts here is not evidence that no warnings exist.\nLightning holds today: 1 hold(s) started, 2 extension(s); latest hold end 18:50 site-local (2026-10-17T22:50:00Z).\nUnresolved crew reports (real crew reports, not simulated): 1.\n- wildlife: Alligator seen near the north culvert. (reported 2026-10-17T22:02:00Z)\n\nExperimental model index\nExperimental model index: not yet integrated.\n\nMissing data\nMissing: forecast.\nMissing: official alerts.\nMissing: model index.",
    "delivered_at": "2026-10-17T23:20:00Z",
    "delivered_local_time": "2026-10-17T19:20:00-04:00",
    "delivery_local_date": "2026-10-17",
    "event_mode": "replay",
    "forecast_target_date": "2026-10-18",
    "generator": "template-v1",
    "id": "replay:663:2026-10-17",
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

`GET /api/sites/{id}/timeline?event_mode=live|replay` - chronological (oldest first) events for one site. Event `type` is one of `lightning_hold_started`, `lightning_hold_extended`, `lightning_hold_expired`, `report_created`, `report_resolved`, `briefing_delivered`. Each event has `id, site_id, type, occurred_at, source, event_mode, summary, details`. `lightning_hold_expired` is computed from `hold_until` and ends only the lightning hold.

Mixing rule: a live query returns live events only. A replay query returns replay events **plus live crew-report events** (`report_created`, `report_resolved`), which keep `event_mode: "live"` so they can appear in the replay sequence. Nothing else from live appears in replay, and replay events never appear in live queries. Live reports use the wall clock and replay events use the replay clock, which starts at the session's wall-clock start and runs faster.

Replay example (`ops_timeline.json` -> `examples.replay`):
```json
{
  "as_of": "2026-10-17T23:20:00Z",
  "count": 8,
  "event_mode": "replay",
  "events": [
    {
      "details": {
        "distance_km": 14.48,
        "distance_miles": 9.0,
        "hold_until": "2026-10-17T22:30:00Z",
        "previous_hold_until": null,
        "strike_event_id": "dh-001"
      },
      "event_mode": "replay",
      "id": "replay:simulated-replay:dh-001:663",
      "occurred_at": "2026-10-17T22:00:00Z",
      "site_id": 663,
      "source": "simulated-replay",
      "summary": "Simulated replay: Strike 9.0 mi from site started a 30-minute lightning stop-work hold.",
      "type": "lightning_hold_started"
    },
    {
      "details": {
        "category": "wildlife",
        "has_photo": true,
        "location_flag": null,
        "report_id": "a20a5dcadc94457199df16f43de688f6"
      },
      "event_mode": "live",
      "id": "live:report:a20a5dcadc94457199df16f43de688f6:created",
      "occurred_at": "2026-10-17T22:02:00Z",
      "site_id": 663,
      "source": "crew_report",
      "summary": "Crew report (wildlife) with photo: Alligator seen near the north culvert.",
      "type": "report_created"
    },
    {
      "details": {
        "category": "mud",
        "has_photo": false,
        "location_flag": null,
        "report_id": "85f61b593b4f4f8d9a3796794f36aecd"
      },
      "event_mode": "live",
      "id": "live:report:85f61b593b4f4f8d9a3796794f36aecd:created",
      "occurred_at": "2026-10-17T22:03:00Z",
      "site_id": 663,
      "source": "crew_report",
      "summary": "Crew report (mud): Access road rutted at gate 2.",
      "type": "report_created"
    },
    {
      "details": {
        "category": "mud",
        "has_photo": false,
        "location_flag": null,
        "report_id": "85f61b593b4f4f8d9a3796794f36aecd"
      },
      "event_mode": "live",
      "id": "live:report:85f61b593b4f4f8d9a3796794f36aecd:resolved",
      "occurred_at": "2026-10-17T22:04:00Z",
      "site_id": 663,
      "source": "crew_report",
      "summary": "Crew report (mud) marked resolved; it stays in site history.",
      "type": "report_resolved"
    },
    {
      "details": {
        "distance_km": 8.05,
        "distance_miles": 5.0,
        "hold_until": "2026-10-17T22:40:00Z",
        "previous_hold_until": "2026-10-17T22:30:00Z",
        "strike_event_id": "dh-003"
      },
      "event_mode": "replay",
      "id": "replay:simulated-replay:dh-003:663",
      "occurred_at": "2026-10-17T22:10:00Z",
      "site_id": 663,
      "source": "simulated-replay",
      "summary": "Simulated replay: Strike 5.0 mi from site extended the lightning stop-work hold.",
      "type": "lightning_hold_extended"
    },
    {
      "details": {
        "distance_km": 3.22,
        "distance_miles": 2.0,
        "hold_until": "2026-10-17T22:50:00Z",
        "previous_hold_until": "2026-10-17T22:40:00Z",
        "strike_event_id": "demo-manual-001"
      },
      "event_mode": "replay",
      "id": "replay:simulated-replay:demo-manual-001:663",
      "occurred_at": "2026-10-17T22:20:00Z",
      "site_id": 663,
      "source": "simulated-replay",
      "summary": "Simulated replay: Strike 2.0 mi from site extended the lightning stop-work hold.",
      "type": "lightning_hold_extended"
    },
    {
      "details": {
        "clears_only": "lightning_hold",
        "hold_until": "2026-10-17T22:50:00Z"
      },
      "event_mode": "replay",
      "id": "replay:hold-expired:663:2026-10-17T22:50:00Z",
      "occurred_at": "2026-10-17T22:50:00Z",
      "site_id": 663,
      "source": "planit-control (computed from hold_until)",
      "summary": "Simulated replay: Lightning hold countdown ended. Only the lightning hold is lifted; other hazards and lightning feed coverage are unchanged.",
      "type": "lightning_hold_expired"
    },
    {
      "details": {
        "briefing_id": "replay:663:2026-10-17",
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
      "id": "replay:briefing:663:2026-10-17",
      "occurred_at": "2026-10-17T23:20:00Z",
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
  "as_of": "2026-10-17T22:08:00Z",
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
      "error": "photo must be 5 MB or smaller"
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
