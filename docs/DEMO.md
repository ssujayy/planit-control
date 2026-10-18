# Demonstration walkthrough

Use the README setup. This is a prototype; provider/data gaps remain visible.

1. Configure DATABASE_URL locally, run `python -m scripts.seed_database`, then
   `python -m backend.worker --once`. Migration 004 adds report categories and
   nullable prediction status/probability/geography; 005 adds stream context.
   Never edit already-applied migrations. Start Flask and exactly one worker.
2. Open the dashboard in Tiger Data storage. Confirm 55 sites. Select the first
   ranked site; inspect official warnings and today/tomorrow model scores.
   Toggle the small Debug button for weather units/valid/retrieval times,
   coverage and tomorrow's experimental index. Holds and official warnings
   outrank the numeric score. No recorded alert is not a safety clearance.
3. Inspect flood evidence: official NWS products stay distinct from the
   illustrative USGS-stream/overnight-rain advisory. Explain the 1 km / 25 mm
   thresholds, modeled rainfall, incomplete inputs and absence of river gauges.
4. Under Crew reports, click/drag the pin or edit coordinates. Take/upload a
   real photo, choose wildlife (or another category) and enter a description.
   Submit. Open the site in another browser session, wait up to 15 seconds and
   confirm the photo/pin/history. Mark resolved and find it with the history
   filters. Restart Flask and verify the same report/photo still exists. These
   cross-device/restart steps require the configured database; they have not
   been demonstrated against Tiger Data by this branch's author.
5. Tomorrow's report appears automatically; inspect its forecast cards and
   summary without pressing a preview button. It is labeled not delivered and
   does not reserve the scheduled record. At/after 18:00 site-local, the worker
   writes an inbox record. Restart/repeat the job; the same site/local date
   must have one delivery. Eastern and Central sites deliver at different UTC
   times. Do not claim that a preview is scheduled delivery.
6. Demonstrate deterministic lightning with the isolated replay APIs below.
   Replay is not a live strike feed and never changes the live dashboard rank.
   For an actual crew sighting at the plant, check the observation confirmation
   in its Lightning hold card and select Record lightning. Verify the countdown
   and recorded hold history. Do not record invented sightings as real evidence.

PowerShell replay commands (with configured database and Flask running):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/replay/sessions -ContentType application/json -Body '{"speed":10}'
Invoke-RestMethod http://localhost:5000/api/sites/663/lightning?event_mode=replay
Invoke-RestMethod http://localhost:5000/api/sites/663/timeline?event_mode=replay
Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/briefings/generate -ContentType application/json -Body '{"site_id":663,"event_mode":"replay"}'
Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/replay/reset
```

The script includes 9-mile/11-mile strikes and later extensions, driven by one
accelerated replay clock. Radius boundary, duplicates, delayed strikes, expiry,
unavailable/stale monitoring and live isolation are automated behavior checks.
The HTTP strike endpoint rejects attempts to inject live events. A real provider
must implement the `StrikeSource` protocol and use `poll_source` in the existing
worker, with a verified actual payload, licensing and reconnect/checkpoint rules.

Without database credentials, enable Debug and select file inventory to inspect the 55 real
locations with explicitly unavailable monitoring. Use `python -m
scripts.verify_providers` for a bounded actual-provider/model check, and
`node tests/dashboard.browser.mjs` in frontend for isolated UI fixtures.
Neither substitutes for shared database or live lightning verification.
