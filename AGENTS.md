# PlanIT Control — Shared Project Instructions

Read this file before making changes. It applies to every coding assistant working in this repository.

## 1. Project objective and authority

Build PlanIT Control for the SwampHacks XII Sperry Tech challenge.

The core workflow is:
identify a site needing attention → explain the evidence → alert the crew →
collect a field report → prepare tomorrow’s briefing.

Optimize for a complete, reliable, understandable demonstration and legitimate
challenge coverage.

Follow the team’s latest explicit instructions. The master team playbook governs
objectives and scheduling; the verified sponsor brief governs sponsor requirements.
The repository’s agreed API contract and database schema govern implementation.

This file summarizes execution guidance. If documents or code disagree, identify
the specific conflict before changing a shared contract. Do not silently invent
a replacement architecture.

The starter is a foundation, not a finished safety product. Inspect the current
repository before assuming a planned feature exists.

## 2. Required capabilities

Implement all six in the simplest honest working form:

1. Combined environmental conditions for at least 50 distinct real power plants:
   weather, heat, rainfall, soil moisture, official alerts, fire evidence, and
   wildlife/local hazards reported by crews. Explicitly label unavailable feeds.
2. Danger alerts, including a lightning hold within 10 miles with a 30-minute
   countdown extended by qualifying strikes, and flood-related warnings/advisories.
3. A next-day briefing delivered to an in-app supervisor inbox at 6 PM in each
   site's local timezone. Confirm with Sperry whether another channel is required.
4. Crew reports containing a photo, location, category, note, timestamp, and site,
   available in shared site history.
5. A supervisor map and ranked list that explain why sites need attention.
6. An experimental 0–10 index produced by an ML model trained on historical data.

A missing feature or replay does not count as completed live integration.
Track unresolved sponsor interpretations rather than assuming approval.

## 3. Stack and existing foundation

- Frontend: React + Vite, JavaScript.
- Map: preserve the existing Leaflet integration unless a change has a clear benefit.
- Backend: Flask, Python 3.11+.
- Database: Tiger Data PostgreSQL through Psycopg.
- Worker: one separate Python process for ingestion, briefings, and predictions.
- ML: pandas + scikit-learn.
- Briefings: deterministic template first; optional Gemini rewrite.

The starter contains 55 distinct plants selected from the official EIA-860
2025 annual inventory. Preserve stable source identifiers and provenance.
Inventory-year operating status is not verified current operating status.

Existing file/demo storage mode is an explicit foundation feature. It does not
prove Tiger Data integration and must not silently replace a failed database.

Tiger Data is the selected shared database. Diagnose connection failures first.
A switch to another database is a team architecture decision, not an automatic
fallback. PostgreSQL-specific SQL and Timescale features require deliberate
changes if the database changes.

Keep SQL in the existing database adapter. Inspect the current requirements and
package files before adding dependencies. Coordinate additions affecting shared
setup or architecture; routine implementation within the assigned scope does not
require repeated approval.

## 4. Team ownership and parallel development

Four human owners work simultaneously, each using their own coding assistant:

- Frontend: dashboard, map, site detail/timeline, report form, briefing inbox.
- Backend/data: plant data, database, ingestion, shared data interfaces.
- Alerts/reports: lightning state, reporting, briefing generation and scheduling.
- ML: dataset, labels, training, evaluation, prediction export.

Assign one integration owner to coordinate shared contracts and merges.

Work on a feature branch. Before editing, inspect Git status and relevant files.
Do not overwrite another person's uncommitted work.

Coordinate before changing another owner's active module, shared API response
shapes, schema, or dependencies. Routine changes within assigned scope may proceed.

Use fixtures matching the agreed API contract so development can continue before
other modules are ready. Do not create competing contracts in separate documents.

Keep changes focused. Avoid unrelated refactors and formatting churn.

For each handoff, report:
- What works.
- Changed files.
- Commands/checks run and their results.
- Remaining gaps and integration needs.

Commit completed, verified steps when the human owner requests or authorizes it.
Never discard work or force-push shared history without explicit authorization.

## 5. Data integrity and secrets

- Never commit secrets. Keep credentials in gitignored local environment files.
- Keep .env.example limited to configuration names and safe placeholders.
- Preserve source, observation/forecast time, retrieval time, and units.
- Distinguish observations, forecasts, official warnings, modeled proxies,
  crew reports, and replay events.
- Missing or stale data must not appear as zero risk.
- "No recent reports" does not mean "no hazard."
- Fire-weather warnings and satellite fire detections are different evidence.
- Open-Meteo apparent temperature is not the NWS heat index.
- Cache upstream responses and persist useful observations/forecast snapshots.
- Dashboard polling must read cached/stored data, not fan out to upstream APIs.
- The starter's explicit manual weather-fetch action may remain during transition;
  move routine refreshes into the worker.
- Verify an actual provider response before wiring fields into ingestion.
- Credit actual data sources, libraries, and AI tools in README.

Use code produced during the permitted hackathon period and follow the verified
event rules. Do not copy implementation code from prior personal projects.

## 6. Hazard status, coverage, and ranking

Track each hazard independently. Compute the current presentation from those
components; do not use one stored flag that clears unrelated hazards.

Represent separately:
- Hazard state: STOP_WORK, ALERT, ELEVATED, or NO_ACTIVE_ALERTS.
- Monitoring coverage: COMPLETE, PARTIAL, STALE, or UNAVAILABLE.

Coverage refers only to configured monitoring and its documented freshness rules.
It does not certify site safety.

Examples:
- An active lightning hold remains STOP_WORK even if another feed is unavailable.
- A missing strike feed remains visibly unavailable after the timer expires.
- NO_ACTIVE_ALERTS means no active alerts in available monitored evidence.

Rank active lightning holds and severe official warnings first, followed by other
alerts/advisories and relevant unresolved reports, then model/weather signals.
Show the reasons and feed coverage on each row.
Make missing critical monitoring visible rather than burying it at the bottom.

Never average a lightning hold into an overall numeric score.
The ML index must never override an official warning.

## 7. Lightning and replay isolation

For each accepted strike:
1. Validate its identifier, coordinates, timestamp, and mode.
2. Ignore duplicates within the same source/mode.
3. Find sites within 10 miles using geographic distance.
4. Set hold_until to max(existing hold_until, strike_time + 30 minutes).
5. Persist the resulting state.

An older delayed strike cannot shorten an existing hold.
A new event extends a hold only when its calculated expiration is later.
Expiration clears only the lightning hold.

Live and replay may use the same processing function, but must have separate
state and queries. Use a key such as (site_id, mode) for lightning state and
suitable source/mode namespacing for event identifiers.

Replay must not modify live ranking, live alerts, or live briefings.
Pass mode explicitly through the replay workflow and label it visibly.
Do not confuse data-storage mode (file/database) with event mode (live/replay).

Use a replay session identifier if needed to reset/restart demonstrations cleanly.
Accelerated playback must use a consistent replay clock for event time,
countdowns, and expiration.

Test:
- Strike at 9 miles triggers a hold; strike at 11 miles does not.
- Duplicate processing is a no-op.
- Older events cannot shorten a hold.
- A later qualifying event extends it.
- Expiration preserves unrelated hazards.
- Stale/unavailable monitoring remains visible.
- Replay cannot change live state.

## 8. Flood, heat, and fire

Keep official flood alerts separate from rainfall-based advisories.
An illustrative rainfall rule must be labeled as an advisory with a documented
threshold, not an official flood warning.

Do not infer river proximity from a plant name. Document how near-river sites
were identified; unknown proximity remains unknown.

Document the heat metric, units, and thresholds actually used.

Implement the minimum fire coverage needed by the verified sponsor brief.
Use official fire-weather alerts and/or accessible fire detections with distinct
labels. If a required layer is unavailable, disclose the gap rather than
reclassifying it as optional.

## 9. ML implementation

First prove an end-to-end pipeline on a small geographic sample, then expand.

Initial model:
- Unit: county-day, avoiding duplicate rows for plants in the same county.
- Label: a reported Thunderstorm Wind, Hail, Tornado, or Flash Flood event.
- Restrict the first join to compatible county-based NOAA records (CZ_TYPE = C).
- Join using verified state/county identifiers and consistent local dates.
- Define treatment of multi-day events explicitly.
- A negative label means no selected event was reported, not proven safety.
- Features: available daily weather summaries and seasonal features.
- Split chronologically; choose years actually available and sufficiently complete.
- Start with logistic regression and a simple baseline.
- Fit preprocessing only on training data.
- Select thresholds using training/validation data, not the final test set.

Report dataset size, positive prevalence, missingness, baseline, average precision,
and precision/recall at the selected threshold. Report ROC-AUC only when defined.

Save the model, preprocessing, feature order, model version, and evaluation.
The UI must display actual saved model predictions.

For the initial index, use 10 × model probability, bounded to 0–10 and labeled
"experimental model index." Do not call it an injury probability or claim
calibration without evidence.

Historical evaluation uses observed weather; deployment uses forecast summaries.
Document this difference. Preserve consistent feature definitions and units.
Missing required features must produce an unavailable prediction or use the
model's explicitly trained missing-data treatment.

## 10. Reports and briefings

Reports:
- Validate site, coordinates, category, note, and uploaded image.
- Apply a file-size limit and verify image content.
- Persist photos and metadata in the agreed storage design.
- Do not rely on temporary local files for the shared demonstration.
- Reports submitted on another device must appear in site history.

Briefings:
- Build a deterministic template before Gemini.
- Include tomorrow's forecast, active alerts, unresolved reports, and missing data.
- Gemini may rewrite supplied facts; it must not invent measurements or policies.
- Store the generated result and retain template fallback.
- Run one worker, independent of Flask's development reloader.
- Schedule at 18:00 using each site's IANA timezone.
- Distinguish briefing delivery date from forecast target date.
- Enforce one scheduled briefing per site/local delivery date at the database level.
- Manual demonstration generation uses the same idempotent generation function.
- Keep replay briefings isolated from live scheduled delivery.
- Test scheduling before waiting for the actual 6 PM run.

## 11. Integration and verification

Preserve and extend the existing API contract, fixtures, schema, and startup
commands. Coordinate any breaking change before implementation.

A feature is complete when:
- Its data persists where required.
- The frontend consumes the agreed response.
- Missing/error states are visible.
- Relevant behavior checks pass.
- Its limitations are documented.

Prioritize checks for:
- At least 50 unique source plant IDs.
- Real database seed and database-mode retrieval.
- Alert-driven ranking updates.
- Persistent and isolated lightning state.
- Shared photo reports.
- Duplicate-free scheduled briefings.
- Actual model outputs.
- Clean-clone startup and frontend production build.

Do not claim an unrun test passed.
Do not delete a failing test to hide an implementation defect.

## 12. Timeline and scope control

All milestone times below are America/New_York.

Saturday, October 17:
- Immediately: shared instructions, owners, API/schema agreement, Tiger Data
  connection and seed, and a small real ML-data pipeline.
- 11 AM: 50+ database-backed sites, cached conditions, verified initial dataset.
- 2 PM: dashboard/site view, persistent lightning logic, saved photo reports.
- 5 PM: integrated required features, model output, tested briefing scheduler.
- 6 PM: actual scheduled briefing delivery.
- 9 PM: evaluation, freshness labels, replay isolation; optional Gemini.

Sunday, October 18:
- 12:30 AM: feature freeze, clean-clone check, backup demo recording.
- 5–7 AM: rehearsal, documentation, submission.
- 7:30 AM: target submission and verified links.

These are working targets. If one slips, report the gap and cut optional scope.
Verify current official submission requirements before final submission.

Cut first:
extra integrations, animations, extra AI features, work-period comparison,
additional models/tuning, complex report management, extra delivery channels.

Protect:
the six required capabilities in minimal form, 50+ distinct plants, honest labels,
a functioning workflow, evaluation, and a reliable demonstration.

Never hide an incomplete requirement by renaming a substitute.