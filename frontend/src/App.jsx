import React, { useEffect, useMemo, useRef, useState } from 'react';
import SiteMap from './SiteMap';
import useOutlook from './useOutlook';
import { AlertCenter, Badge, HazardBadge, IntegrationCoverage, SiteDetails } from './DashboardPanels';
import { activeAlerts, activeHold, attentionReasons, coverageState, feedState, formatTime, hazardState, predictionFor, predictionReason, rankRows } from './outlook';

export default function App() {
  const [mode, setMode] = useState('live');
  return <Dashboard key={mode} mode={mode} onModeChange={setMode}/>;
}

function Dashboard({ mode, onModeChange }) {
  const [retry, setRetry] = useState(0), [clock, setClock] = useState(Date.now());
  const [selectedId, setSelectedId] = useState(null), [filter, setFilter] = useState(''), [view, setView] = useState('all');
  const [announcement, setAnnouncement] = useState('');
  const announced = useRef(new Set());
  const { outlook, readiness, health, loading, error, readinessError, offset } = useOutlook(mode, retry);
  const now = clock + offset;
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    if (!outlook) return;
    setSelectedId(previous => outlook.sites.some(row => row.site.id === previous) ? previous : outlook.sites[0]?.site.id ?? null);
    const messages = [];
    for (const row of outlook.sites) {
      const hold = activeHold(row, Date.now() + offset);
      const events = [
        ...(hold ? [{ key: 'hold:' + row.site.id + ':' + hold.hold_until, message: 'Stop work at ' + row.site.name + '. Lightning hold until ' + formatTime(hold.hold_until, row.site.timezone) + '.' }] : []),
        ...activeAlerts(row, Date.now() + offset).map(alert => ({ key: 'alert:' + row.site.id + ':' + alert.id + ':' + alert.expires, message: alert.event + ' at ' + row.site.name + '.' })),
        ...(row.flood_advisory?.active ? [{ key: row.flood_advisory.id, message: 'Illustrative rainfall/stream advisory at ' + row.site.name + '. Review site evidence.' }] : []),
      ];
      for (const event of events) if (!announced.current.has(event.key)) {
        announced.current.add(event.key); messages.push(event.message);
      }
    }
    if (messages.length) setAnnouncement(messages.slice(0, 3).join(' ') + (messages.length > 3 ? ` Plus ${messages.length - 3} more alerts in the crew alert list.` : ''));
  }, [outlook, offset]);
  const rows = useMemo(() => rankRows(outlook?.sites ?? [], now), [outlook, now]);
  const selected = rows.find(row => row.site.id === selectedId);
  const stops = rows.filter(row => activeHold(row, now)).length;
  const alerts = rows.filter(row => activeAlerts(row, now).length).length;
  const hasGap = row => row.unavailable_layers?.length || feedState(row, 'weather', now, !!error) !== 'COMPLETE' || feedState(row, 'official', now, !!error) !== 'COMPLETE';
  const gaps = rows.filter(hasGap).length;
  const visible = rows.filter(row => {
    const matches = (row.site.name + ' ' + row.site.state + ' ' + row.site.county).toLowerCase().includes(filter.toLowerCase());
    const state = hazardState(row, now, !!error);
    return matches && (view === 'all' || view === 'alerts' && ['STOP_WORK', 'ALERT', 'ELEVATED'].includes(state) || view === 'gaps' && hasGap(row));
  });
  const mapSites = rows.map((row, index) => ({ ...row.site,
    attention_state: hazardState(row, now, !!error), attention_rank: mode === 'live' ? index + 1 : null,
    coverage_label: 'Weather ' + feedState(row, 'weather', now, !!error).toLowerCase() + ' · NWS ' + feedState(row, 'official', now, !!error).toLowerCase(),
    model_label: 'Today’s experimental daily index: ' + (predictionFor(row, now, 0)?.score.toFixed(2) ?? 'Unavailable'),
  }));
  function selectSite(id, focus = false) {
    setSelectedId(id);
    if (focus) requestAnimationFrame(() => document.getElementById('site-details')?.focus());
  }
  return <>
    <header>
      <div className="brand"><span className="logo">P</span><div><strong>PlanIT Control</strong><small>Utility site environmental intelligence</small></div></div>
      <nav aria-label="Dashboard sections"><a href="#alerts">Alerts</a><a href="#site-details">Site evidence</a><a href="#briefings">Briefings</a></nav>
    </header>
    <main>
      <section className="intro"><div><p className="eyebrow">SUPERVISOR WORKSPACE</p><h1>Know where to focus.</h1><p>Prioritize lightning holds and official warnings, inspect site evidence, and plan for tomorrow.</p></div>
        <label className="mode">Site data<select value={mode} onChange={event => onModeChange(event.target.value)}><option value="live">Tiger Data database</option><option value="demo">File inventory · no stored monitoring</option></select></label>
      </section>
      <div className="sync-line"><span><span className={'connection-dot ' + (health?.database === 'connected' ? 'connected' : '')}/>{mode === 'live' ? 'Tiger Data' : 'File plant inventory'} · {mode === 'live' ? health?.database?.replaceAll('_', ' ') ?? 'checking connection' : 'monitoring unavailable'}</span>
        <span>{outlook ? 'Snapshot ' + formatTime(outlook.as_of) + ' · ' : ''}Stored evidence refreshes every 15 seconds</span></div>
      {error && <div className="error" role="alert"><strong>{outlook ? 'Updates interrupted. Showing the last received evidence.' : 'Site evidence could not be loaded.'}</strong><p>{error}</p><button type="button" className="text-button" onClick={() => setRetry(value => value + 1)}>Retry connection</button></div>}
      {announcement && <aside className="alert-toast" role="alert" aria-atomic="true"><div className="card-heading"><strong>New alert evidence</strong><button type="button" aria-label="Dismiss alert notice" onClick={() => setAnnouncement('')}>×</button></div><p>{announcement}</p><a href="#alerts">Review crew alerts</a></aside>}
      <div className="metrics">
        <div><small>Sites in view</small><strong>{outlook ? rows.length : '—'}</strong><p>{mode === 'live' ? 'Database-backed plant inventory' : 'File-based plant inventory'}</p></div>
        <div><small>Stop-work holds</small><strong className={stops ? 'danger-text' : ''}>{outlook ? stops : '—'}</strong><p>Recorded lightning holds · live feed {readiness?.lightning?.live_feed_connected ? 'connected' : 'unavailable'}</p></div>
        <div><small>Official alert sites</small><strong>{outlook ? alerts : '—'}</strong><p>Unexpired NWS warnings, watches & advisories</p></div>
        <div><small>Sites with monitoring gaps</small><strong>{outlook ? gaps : '—'}</strong><p>Missing, partial, or stale evidence</p></div>
      </div>
      <AlertCenter rows={rows} now={now} onSelect={selectSite} lightningConnected={!!readiness?.lightning?.live_feed_connected} loading={loading} available={!!outlook}/>
      <div className="workspace">
        <section className="panel site-list" aria-labelledby="queue-title">
          <div className="panel-title"><h2 id="queue-title">Attention queue</h2><span>{visible.length} / {rows.length} sites</span></div>
          <div className="queue-controls"><label>Find a plant<input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Name, state, or county"/></label>
            <label>Show<select value={view} onChange={event => setView(event.target.value)}><option value="all">All sites</option><option value="alerts">Active alerts & crew reports</option><option value="gaps">Monitoring gaps</option></select></label></div>
          <div className="sites" aria-busy={loading}>{visible.map(row => {
            const rank = mode === 'live' ? rows.indexOf(row) + 1 : null;
            const prediction = predictionFor(row, now);
            const currentPrediction = predictionFor(row, now, 0);
            const reasons = attentionReasons(row, now);
            return <button type="button" key={row.site.id} className={row.site.id === selectedId ? 'selected' : ''} onClick={() => selectSite(row.site.id)} aria-pressed={row.site.id === selectedId}>
              <span className="queue-name"><span className="rank">{rank ?? '·'}</span><strong>{row.site.name}</strong></span>
              <small>{row.site.county}, {row.site.state} · EIA {row.site.source_plant_id}</small>
              <HazardBadge row={row} now={now} disconnected={!!error}/>
              <span className="queue-reason">{reasons.slice(0, 2).join(' ') || 'Monitoring evidence unavailable.'}</span>
              <span className="feed-line">Weather: {feedState(row, 'weather', now, !!error).toLowerCase()} · NWS: {feedState(row, 'official', now, !!error).toLowerCase()}</span>
              {!!row.unavailable_layers?.length && <span className="feed-line">Unavailable: {row.unavailable_layers.join(', ')}</span>}
              <span className="index-label today-model" title={predictionReason(row, now, 0)}>Today’s model index <strong>{currentPrediction ? currentPrediction.score.toFixed(2) + ' / 10' : 'Unavailable'}</strong></span>
              <span className="index-label tomorrow-model" title={predictionReason(row, now)}>Tomorrow’s model index <strong>{prediction ? prediction.score.toFixed(2) + ' / 10' : 'Unavailable'}</strong></span>
              <span className="feed-line">Experimental daily forecasts</span>
            </button>;
          })}{!visible.length && <p className="empty-state">{loading ? 'Loading stored site evidence…' : error && !outlook ? 'Resolve the connection error to load sites.' : 'No sites match this view.'}</p>}</div>
          <p className="queue-footnote">{mode === 'live' ? 'Holds → severe official warnings → other alerts → crew evidence → monitoring gaps and forecast/model signals.' : 'File storage has no hazard ranking or stored monitoring.'}</p>
        </section>
        <section className="panel geography" aria-labelledby="map-title"><div className="panel-title"><h2 id="map-title">Site priority map</h2><span>{mode === 'live' ? 'Numbers match the attention queue' : 'Inventory locations'}</span></div>
          <SiteMap sites={mapSites} selectedId={selectedId} onSelect={selectSite}/>
          <div className="map-legend"><span><i className="legend-stop"/>Stop work</span><span><i className="legend-alert"/>Official alert</span><span><i className="legend-elevated"/>Crew report / advisory</span><span><i className="legend-none"/>No active alerts*</span><span><i className="legend-unknown"/>Unknown</span></div>
          <p className="map-note">*No active alerts in available monitored evidence. Feed coverage is separate; this does not certify safety.</p>
        </section>
      </div>
      {selected ? <><section className="panel reasons-panel"><div className="card-heading"><h2>Why this site needs attention</h2><Badge state={coverageState(selected, now, !!error)}>{coverageState(selected, now, !!error).toLowerCase()} coverage</Badge></div><ul>{attentionReasons(selected, now).map(reason => <li key={reason}>{reason}</li>)}</ul></section>
        <SiteDetails key={selected.site.id} row={selected} now={now} disconnected={!!error} readiness={readiness} storageMode={mode} onChanged={() => setRetry(value => value + 1)}/></>
        : <section className="panel empty-state" id="site-details"><h2>{loading ? 'Loading site evidence…' : 'Select a site to inspect its evidence'}</h2></section>}
      <IntegrationCoverage readiness={readiness} readinessError={readinessError} rows={rows} now={now} disconnected={!!error}/>
      <footer>Plant inventory: EIA-860 2025 · Weather: Open-Meteo · Official alerts: National Weather Service · Map: Leaflet / OpenStreetMap<br/>Inventory-year operating status is not verified current operating status. Missing evidence does not mean no hazard. Alerts shown here are in-app; crew push/SMS delivery is not connected.</footer>
    </main>
  </>;
}

