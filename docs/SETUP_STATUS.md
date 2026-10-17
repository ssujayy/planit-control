# Setup status

This is the ONE file for changing facts: what is built, what is blocked, open decisions. Stable rules are in AGENTS.md. Update this file (small edits, with the date and time in ET) instead of editing AGENTS.md. Do not record secrets here.

Last updated: Saturday Oct 17, about 6 PM ET (update when you change it).

## Verified working
- Repository on GitHub (public). Foundation: React/Vite frontend, Flask backend, backend tests, production frontend build.
- 55 distinct plants from the EIA-860 2025 annual inventory (data/sites.json) seeded into Tiger Data. GET /api/sites?mode=live returns them from the database; mode=demo reads the file.
- GET /api/health, /api/sites, /api/sites/{id}, /api/sites/{id}/weather exist and follow docs/API_CONTRACT.md.
- Weather is cached in memory only (15 minutes); restarting Flask clears it.
- ML baseline exists on branch feature/ml (model, results, predict_site, tests, docs/ML.md). Not yet merged into main, and not connected to the backend.

## Not built yet (do not describe these as implemented)
- Official alert ingestion (NWS) and flood advisory
- Lightning hold logic, replay and tests
- Risk status and ranking (risk_status is "not_implemented")
- Crew reports (photo, pin, category) and shared history
- Briefing generation, scheduler and worker process
- Persisted observations and forecast snapshots
- Supervisor ranked list and map status
- Prediction table, county FIPS mapping and wiring of the ML index
- Optional: Gemini briefing rewrite, NASA FIRMS fire detections

## Open decisions (resolve with the team, then record the answer)
- Event mode naming: the API field "mode" (live|demo) is data storage. AGENTS.md section 7 sets event_mode (live|replay) for lightning and replay. Add it to docs/API_CONTRACT.md when the alerts owner builds that endpoint.
- Near-river identification: source, method, and the field to add (needed for the flood advisory).
- Site county FIPS: add a verified crosswalk column or lookup so the backend can tell whether a site is inside the ML training counties.
- Prediction storage: columns beyond the contract minimum (status, probability, outside_training_range JSON, geographic extrapolation flag).
- Merge feature/ml into main (integration owner) and decide how ML dependencies (ml/requirements.txt) are installed on every laptop.
- docs/brief.md: transcribed from the sponsor PDF and added. If anything in it looks wrong, the original PDF governs.
- Sperry questions: is a labeled lightning replay acceptable if no live strike feed is reachable; does an in-app briefing satisfy delivery; is a county-level reported-event model acceptable for the prototype index.
- Submission deadline: rules say Sunday 8:30 AM ET; another source said 8:00 AM on Devpost. Check Devpost and target 7:30 AM.
- README credits: add every AI tool the team actually used (currently lists only ChatGPT/Codex).

## Known limits
- Browser-level testing has not been run by the original scaffold. Map rendering and mobile layout need a manual check.
- Inventory-year plant data does not verify current operating status.
- Some Windows/Mac commands differ; see README and AGENTS.md section 3.

## First manual check
Run both servers, confirm 55 sites in database mode, select a plant, fetch weather and inspect source/units, narrow the window to test mobile layout. If map tiles fail, use the list; tiles are a separate network dependency.