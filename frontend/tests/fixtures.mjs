// Synthetic API-contract fixtures for tests only. Never imported by the application.
export function siteRow(id, now, overrides = {}) {
  const fetched = new Date(now).toISOString();
  const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(now));
  const next = new Date(`${date}T12:00:00Z`); next.setUTCDate(next.getUTCDate() + 1);
  return {
    site: { id, source_plant_id: id, name: `Fixture plant ${id}`, county: 'Test county', state: 'FL', latitude: 29 + id / 10, longitude: -82 - id / 10, timezone: 'America/New_York', source_version: 'TEST FIXTURE' },
    rank: id, hazard_state: 'NO_ACTIVE_ALERTS', coverage: 'PARTIAL',
    weather: { source: 'TEST FIXTURE', fetched_at: fetched, cached: true, stale: false,
      current: { time: Math.floor(now / 1000), temperature_2m: 25, apparent_temperature: 27, relative_humidity_2m: 70, precipitation: 0, wind_gusts_10m: 10 },
      current_units: { temperature_2m: '°C', apparent_temperature: '°C', relative_humidity_2m: '%', precipitation: 'mm', wind_gusts_10m: 'km/h' },
      hourly: {}, hourly_units: {}, note: 'Synthetic test conditions.', current_evidence_type: 'modeled_current_conditions', hourly_evidence_type: 'forecast' },
    weather_monitoring: { state: 'COMPLETE', last_attempt_at: fetched, last_success_at: fetched, error_code: null },
    official_alerts_monitoring: { state: 'COMPLETE', fetched_at: fetched },
    alerts: [], lightning_hold: null, unresolved_reports: [], model_index: null, prediction: null,
    planning_weather: { target_date: next.toISOString().slice(0, 10), heat_index_max_f: 85, precipitation_sum_mm: 12, soil_moisture_max_m3_m3: 0.2, source: 'TEST FIXTURE', evidence_type: 'derived_from_forecast', heat_method: 'TEST FIXTURE', note: 'TEST FIXTURE' },
    river_proximity: { status: 'unknown', source: null },
    unavailable_layers: ['lightning', 'wildfire', 'wildlife', 'model'], reasons: ['Live strike monitoring is unavailable.'], ...overrides,
  };
}

export function floodAlert(now, overrides = {}) {
  return { id: 'fixture-flood', event: 'Flood Warning', hazard: 'flood', severity: 'Severe', certainty: 'Observed', urgency: 'Immediate',
    effective: new Date(now - 60000).toISOString(), onset: new Date(now - 60000).toISOString(),
    expires: new Date(now + 3600000).toISOString(), ends: null, headline: 'TEST FIXTURE flood warning',
    description: 'Synthetic warning used only for browser verification.', instruction: 'TEST FIXTURE instructions.', area_description: 'Test county',
    source: 'TEST FIXTURE NWS', evidence_type: 'official_warning', ...overrides };
}
