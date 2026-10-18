import React from 'react';
import { BriefingInbox, CrewReports } from './CrewWorkflow';
import {
  activeAlerts, activeHold, addDays, countdown, feedState,
  formatDate, formatTime, HAZARD_LABELS, hazardState, localDate, predictionFor, predictionReason,
} from './outlook';

export function Badge({ state, children }) {
  return <span className={`badge badge-${String(state).toLowerCase()}`}>{children ?? String(state).replaceAll('_', ' ').toLowerCase()}</span>;
}

export function HazardBadge({ row, now, disconnected }) {
  const state = hazardState(row, now, disconnected);
  return <Badge state={state}>{HAZARD_LABELS[state]}</Badge>;
}

export function OfficialAlert({ alert, timezone }) {
  const end = Math.min(Date.parse(alert.expires), alert.ends ? Date.parse(alert.ends) : Infinity);
  return <article className="official-alert">
    <div className="card-heading"><strong>{alert.event}</strong><Badge state="ALERT">{alert.severity}</Badge></div>
    <p>{alert.headline}</p>
    <p className="muted">{alert.source} · Valid until {formatTime(end, timezone)}</p>
    {(alert.description || alert.instruction) && <details>
      <summary>Read warning and instructions</summary>
      {alert.description && <p className="alert-copy">{alert.description}</p>}
      {alert.instruction && <p className="alert-copy"><strong>Official instructions</strong><br/>{alert.instruction}</p>}
    </details>}
  </article>;
}

export function AlertCenter({ rows, now, onSelect, lightningConnected, loading, available }) {
  const active = rows.filter(row => activeHold(row, now) || activeAlerts(row, now).length || row.flood_advisory?.active);
  return <section className="panel alert-center" id="alerts" aria-labelledby="alerts-title">
    <div className="panel-title"><h2 id="alerts-title">Crew alerts</h2><span>{active.length} sites with recorded active alerts</span></div>
    {active.length ? <div className="alert-grid">{active.map(row => {
      const hold = activeHold(row, now), alerts = activeAlerts(row, now);
      return <button type="button" className={`alert-site ${hold ? 'stop-work' : ''}`} key={row.site.id} onClick={() => onSelect(row.site.id, true)}>
        <span className="card-heading"><strong>{row.site.name}</strong><HazardBadge row={row} now={now}/></span>
        {hold && <span className="hold-line">Lightning hold <strong>{countdown(hold, now)}</strong></span>}
        {alerts.length > 0 && <span>{alerts.map(alert => alert.event).join(' · ')}</span>}
        {row.flood_advisory?.active && <span>Illustrative stream/rainfall advisory · {row.flood_advisory.rainfall_mm} mm overnight</span>}
        <small>Open site evidence →</small>
      </button>;
    })}</div> : <div className="empty-state compact">
      <strong>{loading ? 'Loading stored alert evidence…' : !available ? 'Alert evidence unavailable' : 'No active alerts in the stored evidence'}</strong>
      <p>Coverage is shown separately for each site. {!lightningConnected && 'Live lightning monitoring is unavailable.'} This is not an all-clear.</p>
    </div>}
  </section>;
}

function Metric({ label, value, unit, metadata }) {
  return <div><small>{label}</small><strong>{Number.isFinite(value) ? `${value}${unit ? ` ${unit}` : ''}` : 'Unavailable'}</strong>
    {metadata?.reason && <p className="metric-note">{metadata.reason}</p>}
    {metadata?.source === 'provider_daily_forecast' && <small>Complete site-local daily forecast</small>}</div>;
}

export function SiteDetails({ row, now, disconnected, readiness, storageMode, onChanged }) {
  const site = row.site, hold = activeHold(row, now), alerts = activeAlerts(row, now);
  const floods = alerts.filter(alert => alert.hazard === 'flood' || /flood/i.test(alert.event));
  const otherAlerts = alerts.filter(alert => !floods.includes(alert));
  const weatherState = feedState(row, 'weather', now, disconnected);
  const officialState = feedState(row, 'official', now, disconnected);
  const weather = row.weather, current = weather?.current, units = weather?.current_units ?? {};
  const tomorrow = addDays(localDate(now, site.timezone), 1);
  const planning = row.planning_weather?.target_date === tomorrow ? row.planning_weather : null;
  const prediction = predictionFor(row, now);
  const currentPrediction = predictionFor(row, now, 0);
  return <section className="site-detail" id="site-details" tabIndex={-1} aria-labelledby="selected-site-title">
    <div className="detail-heading">
      <div><p className="eyebrow">SELECTED SITE · EIA {site.source_plant_id}</p><h2 id="selected-site-title">{site.name}</h2>
        <p className="muted">{site.county}, {site.state} · {site.latitude.toFixed(4)}, {site.longitude.toFixed(4)} · {site.timezone}</p></div>
      <HazardBadge row={row} now={now} disconnected={disconnected}/>
    </div>
    <div className="detail-grid">
      <article className={`panel evidence-card ${hold ? 'lightning-active' : ''}`}>
        <div className="card-heading"><h3>Lightning hold</h3><Badge state={hold ? 'STOP_WORK' : 'UNAVAILABLE'}>{hold ? 'Stop work' : 'Monitoring unavailable'}</Badge></div>
        {hold ? <>
          <p className="countdown-label">Hold remaining</p><p className="countdown" aria-label={`${countdown(hold, now)} remaining on lightning hold`}>{countdown(hold, now)}</p>
          <p>Last qualifying strike: {formatTime(hold.last_strike_at, site.timezone)}<br/>Hold expires: {formatTime(hold.hold_until, site.timezone)}</p>
          <p className="muted">Source: {hold.source}. A later qualifying strike extends this countdown. Expiration ends only the lightning hold.</p>
        </> : <div className="empty-state compact"><strong>No active hold in stored evidence</strong><p>A verified strike within 10 miles must trigger a 30-minute hold. New qualifying strikes extend its expiration.</p></div>}
        {!readiness?.lightning?.live_feed_connected && <p className="integration-note">Live strike monitoring is unavailable. New nearby strikes cannot currently be detected by this dashboard.</p>}
      </article>

      <article className="panel evidence-card">
        <div className="card-heading"><h3>Flood warnings</h3><Badge state={officialState}>NWS {officialState.toLowerCase()}</Badge></div>
        {floods.length ? floods.map(alert => <OfficialAlert key={alert.id} alert={alert} timezone={site.timezone}/>)
          : <p>{officialState === 'COMPLETE' ? 'No active official flood warning, watch, or advisory in the monitored evidence.' : 'No active flood alert is recorded; official monitoring is stale or unavailable.'}</p>}
        <div className="inline-metric"><span>Tomorrow’s rainfall forecast</span><strong>{Number.isFinite(planning?.precipitation_sum_mm) ? `${planning.precipitation_sum_mm} mm` : 'Unavailable'}</strong></div>
        <p className="muted">River proximity: {row.river_proximity?.status ?? 'unknown'}{row.river_proximity?.source ? ` · ${row.river_proximity.source}` : ''}.</p>
        <p className="muted">Stream context: {row.river_proximity?.monitoring ?? 'UNAVAILABLE'} · {row.river_proximity?.radius_meters ? row.river_proximity.radius_meters + ' m search radius' : 'radius unavailable'} · retrieved {formatTime(row.river_proximity?.fetched_at, site.timezone)}.</p>
        {row.flood_advisory?.active === true ? <div className="integration-note"><strong>Illustrative rainfall/stream advisory</strong><p>{row.flood_advisory.reason}</p><p>{row.flood_advisory.recommended_action}</p></div> : <p>{row.flood_advisory?.active === false ? 'Illustrative rainfall/stream rule is not triggered in the available evidence.' : 'Illustrative rainfall/stream advisory unavailable: complete fresh inputs are required.'}</p>}
        <p className="integration-note">USGS mapped stream centerlines within 1 km supply location context. This is not a floodplain assessment or river gauge. The illustrative rule uses at least 25 mm modeled rainfall over the last completed 6 PM–6 AM local night; modeled past rainfall is not a gauge observation. Official NWS flood warnings stay independent.</p>
      </article>

      <article className="panel evidence-card model-card" id="model">
        <div className="card-heading"><h3>Experimental model index</h3><Badge state={prediction ? 'PARTIAL' : 'UNAVAILABLE'}>{prediction ? 'Saved prediction' : 'Unavailable'}</Badge></div>
        <p className="model-score">{prediction ? prediction.score.toFixed(1) : '—'}<span> / 10</span></p>
        {prediction && <meter min="0" max="10" value={prediction.score} aria-label="Experimental model index"/>}
        <p>Next-day index for {formatDate(tomorrow)} · {site.timezone}</p>
        <p className="today-index">Today’s experimental model index: <strong>{currentPrediction ? currentPrediction.score.toFixed(2) + ' / 10' : 'Unavailable'}</strong></p>
        {!currentPrediction && <p className="integration-note">{predictionReason(row, now, 0)}</p>}
        {!prediction && <p className="integration-note">Tomorrow: {predictionReason(row, now)}</p>}
        <p className="muted">Both indices use the latest full-day forecast. A model trained on daily maxima and totals cannot give an instantaneous rating from current readings.</p>
        {prediction ? <dl className="metadata"><dt>Model</dt><dd>{prediction.model_version}</dd><dt>Computed</dt><dd>{formatTime(prediction.computed_at, site.timezone)}</dd><dt>Artifact</dt><dd>{prediction.provenance?.model_artifact ?? 'Not supplied'}</dd></dl>
          : <p className="integration-note">No saved next-day prediction is available. A score can be shown when model results are available for this site and forecast date.</p>}
        <p className="muted">The initial model uses historical county-day weather and selected reported severe-weather events. The index is 10 × model probability; it is not an injury probability or a safety clearance. Official warnings and lightning holds take priority.</p>
        {prediction && <p className="integration-note">{prediction.outside_training_counties === true ? 'Outside training counties: geographic extrapolation.' : prediction.outside_training_counties === false ? 'Within the documented training counties.' : 'Training-county membership is unknown; the verified crosswalk and training manifest are unavailable.'} {prediction.outside_training_range?.length ? `Inputs outside training range: ${prediction.outside_training_range.join(', ')}.` : ''}</p>}
        <p className="muted">Historical observed-weather evaluation does not establish forecast performance.</p>
        {prediction?.provenance?.model_contributions?.features && <details><summary>Fitted model contributors</summary><ul>{prediction.provenance.model_contributions.features.map(entry => <li key={entry.feature}>{entry.feature}: {entry.contribution.toFixed(2)} model log-odds</li>)}</ul><p className="muted">Contributions are relative to the fitted intercept, not causal effects or percentage-point changes.</p></details>}
      </article>

      <BriefingInbox site={site} enabled={storageMode === 'live'}/>
    </div>

    <section className="panel weather-panel" aria-labelledby="weather-title">
      <div className="panel-title"><h3 id="weather-title">Weather & tomorrow’s outlook</h3><Badge state={weatherState}>Weather {weatherState.toLowerCase()}</Badge></div>
      <div className="weather-grid">
        <Metric label="Current modeled temperature" value={current?.temperature_2m} unit={units.temperature_2m}/>
        <Metric label="Current apparent temperature" value={current?.apparent_temperature} unit={units.apparent_temperature}/>
        <Metric label="Current relative humidity" value={current?.relative_humidity_2m} unit={units.relative_humidity_2m}/>
        <Metric label="Current wind gusts" value={current?.wind_gusts_10m} unit={units.wind_gusts_10m}/>
        <Metric label="Tomorrow’s derived maximum heat index" value={planning?.heat_index_max_f} unit="°F" metadata={planning?.metrics?.heat_index_max_f}/>
        <Metric label="Tomorrow’s forecast rainfall" value={planning?.precipitation_sum_mm} unit="mm" metadata={planning?.metrics?.precipitation_sum_mm}/>
        <Metric label="Tomorrow’s maximum shallow soil moisture" value={planning?.soil_moisture_max_m3_m3} unit="m³/m³" metadata={planning?.metrics?.soil_moisture_max_m3_m3}/>
        <div><small>Local forecast date</small><strong>{formatDate(tomorrow)}</strong></div>
      </div>
      <p className="source-line">Source: {weather?.source ?? 'unavailable'} · Retrieved {formatTime(weather?.fetched_at, site.timezone)} · Current valid time {formatTime(Number.isFinite(current?.time) ? current.time * 1000 : null, site.timezone)}</p>
      <p className="source-line">{weather?.note ?? 'No stored weather snapshot is available. Weather updates are unavailable.'} Derived heat index uses the NWS formula on modeled temperature and humidity; apparent temperature is a separate metric. Shallow soil moisture does not measure trafficability.</p>
      {weatherState === 'STALE' && <p className="source-line stale-text">These stored conditions are stale. Retained values do not establish current conditions.</p>}
      {planning?.hazardous_periods?.length > 0 && <details><summary>Forecast planning periods</summary><p className="muted">Illustrative hourly thresholds: derived heat index ≥103 °F, rainfall ≥10 mm/hour, or gusts ≥50 km/h. These are planning signals, not official warnings.</p><ul>{planning.hazardous_periods.map(period => <li key={period.valid_at}>{formatTime(period.valid_at, site.timezone)}: {period.signals.join(', ')}</li>)}</ul></details>}
    </section>

    {otherAlerts.length > 0 && <section className="panel evidence-card"><h3>Other official warnings & advisories</h3>{otherAlerts.map(alert => <OfficialAlert key={alert.id} alert={alert} timezone={site.timezone}/>)}</section>}
    {row.unresolved_reports?.length > 0 && <section className="panel evidence-card"><h3>Unresolved crew evidence</h3>{row.unresolved_reports.map(report => <article className="report" key={report.id}><strong>{report.category}</strong><p>{report.note}</p><small>{formatTime(report.observed_at, site.timezone)}</small></article>)}</section>}
    <CrewReports site={site} enabled={storageMode === 'live'} onChanged={onChanged}/>
  </section>;
}

export function IntegrationCoverage({ readiness, readinessError, rows, now, disconnected }) {
  const freshWeather = rows.filter(row => feedState(row, 'weather', now, disconnected) === 'COMPLETE').length;
  const freshOfficial = rows.filter(row => feedState(row, 'official', now, disconnected) === 'COMPLETE').length;
  return <section className="panel integration-panel" aria-labelledby="coverage-title">
    <div className="panel-title"><h2 id="coverage-title">Monitoring & delivery coverage</h2><span>Coverage does not certify site safety</span></div>
    <div className="integration-grid">
      <div><strong>Weather snapshots</strong><p>{freshWeather} / {rows.length} sites with complete, fresh weather</p><small>Stored weather becomes stale after 30 minutes or a failed refresh.</small></div>
      <div><strong>Official NWS monitoring</strong><p>{freshOfficial} / {rows.length} sites with fresh official monitoring</p><small>10-minute freshness limit. Fire-weather warnings are separate from fire detections.</small></div>
      <div><strong>Lightning detection</strong><p>{readiness?.lightning?.live_feed_connected ? 'Provider connected' : 'Live strike monitoring unavailable'}</p><small>Stored holds remain visible. Monitoring must be connected to detect new nearby strikes.</small></div>
      <div><strong>Daily briefing delivery</strong><p>{readiness?.briefings?.scheduled_delivery_implemented ? 'In-app inbox connected' : 'Delivery implementation unavailable'}</p><small>Worker required at 6 PM local. Check the selected site’s inbox for persisted delivery records.</small></div>
    </div>
    {readinessError && <p className="source-line stale-text" role="status">{readinessError} Availability cannot be confirmed.</p>}
  </section>;
}
