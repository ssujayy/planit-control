import React, { useEffect, useState } from 'react';
import SiteMap from './SiteMap';
import { getJson } from './api';

export default function App() {
  const [mode, setMode] = useState('demo');
  const [sites, setSites] = useState([]), [selectedId, setSelectedId] = useState(null);
  const [health, setHealth] = useState(null), [error, setError] = useState('');
  const [weather, setWeather] = useState(null), [weatherError, setWeatherError] = useState(''), [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    getJson('/api/health', controller.signal).then(setHealth).catch(() => setHealth({ database: 'unavailable' }));
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError(''); setSites([]); setSelectedId(null); setWeather(null);
    getJson(`/api/sites?mode=${mode}`, controller.signal).then(data => {
      setSites(data.sites); setSelectedId(data.sites[0]?.id ?? null);
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [mode]);
  useEffect(() => { setWeather(null); setWeatherError(''); setLoading(false); }, [selectedId, mode]);
  const site = sites.find(s => s.id === selectedId);
  useEffect(() => {
    if (!loading || !site) return;
    const controller = new AbortController();
    getJson(`/api/sites/${site.id}/weather?mode=${mode}`, controller.signal)
      .then(data => setWeather(data.weather))
      .catch(e => { if (e.name !== 'AbortError') setWeatherError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [loading, selectedId, mode]);
  const visible = sites.filter(s => `${s.name} ${s.state} ${s.county}`.toLowerCase().includes(filter.toLowerCase()));
  const current = weather?.current;
  return <>
    <header><div className="brand"><span className="logo">P</span><div><strong>PlanIT Control</strong><small>Utility site environmental intelligence</small></div></div><span className="tag">Foundation build</span></header>
    <main>
      <section className="intro"><div><p className="eyebrow">SUPERVISOR WORKSPACE</p><h1>Start with the evidence.</h1><p>Real plant locations and a verified weather connection. Alerting and risk models are the next workstreams.</p></div><label className="mode">Site data<select value={mode} onChange={e => setMode(e.target.value)}><option value="demo">Demo file — real EIA plants</option><option value="live">Tiger Data database</option></select></label></section>
    <section className="notice" role="status">{mode === 'demo' ? 'DEMO STORAGE: plant locations are read from the included EIA-derived file, not Tiger Data. Weather can be fetched live.' : 'DATABASE MODE: site records are requested from Tiger Data.'} No risk scoring or all-clear status is implemented.</section>
      <div className="metrics"><div><small>Distinct sites</small><strong>{sites.length}</strong></div><div><small>Tiger Data</small><strong className="status">{health?.database?.replaceAll('_', ' ') || 'checking'}</strong></div><div><small>Hazard model</small><strong className="status">Not implemented</strong></div><div><small>Alert monitoring</small><strong className="status">Not connected</strong></div></div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="workspace"><section className="panel site-list"><div className="panel-title"><h2>Monitored locations</h2><span>{visible.length}</span></div><label className="search">Find a plant<input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Name, state, or county" /></label><div className="sites">{visible.map(s => <button key={s.id} className={s.id === selectedId ? 'selected' : ''} onClick={() => setSelectedId(s.id)} aria-pressed={s.id === selectedId}><strong>{s.name}</strong><small>{s.county}, {s.state} · EIA {s.source_plant_id}</small></button>)}{!visible.length && <p className="muted">No locations to display.</p>}</div></section><section className="panel geography"><div className="panel-title"><h2>Site overview</h2><span>Locations only</span></div><SiteMap sites={sites} selectedId={selectedId} onSelect={setSelectedId}/></section></div>
      <section className="panel detail"><div><p className="eyebrow">SELECTED SITE</p><h2>{site?.name || 'Select a location'}</h2>{site && <p className="muted">{site.latitude.toFixed(4)}, {site.longitude.toFixed(4)} · {site.timezone} · {site.source_version}</p>}</div><button className="primary" disabled={!site || loading} onClick={() => { setWeatherError(''); setLoading(true); }}>{loading ? 'Fetching conditions…' : 'Fetch current weather'}</button>
        {weatherError && <p className="error" role="alert">{weatherError}</p>}
        {current && <div className="weather"><div><small>Temperature</small><strong>{current.temperature_2m ?? 'Unavailable'} {weather.current_units.temperature_2m}</strong></div><div><small>Apparent temperature</small><strong>{current.apparent_temperature ?? 'Unavailable'} {weather.current_units.apparent_temperature}</strong></div><div><small>Humidity</small><strong>{current.relative_humidity_2m ?? 'Unavailable'} {weather.current_units.relative_humidity_2m}</strong></div><div><small>Wind gusts</small><strong>{current.wind_gusts_10m ?? 'Unavailable'} {weather.current_units.wind_gusts_10m}</strong></div><p className={weather.stale ? 'error' : 'muted'}>{weather.stale ? 'STALE — last retrieved conditions. ' : ''}Source: {weather.source} · Retrieved {new Date(weather.fetched_at).toLocaleString()} · Model valid time {new Date(current.time * 1000).toLocaleString()}<br/>{weather.note}</p></div>}
      </section>
      <footer>Map © OpenStreetMap contributors · Plant data: EIA 2025 annual inventory · No operational safety decisions are provided by this starter.</footer>
    </main>
  </>;
}

