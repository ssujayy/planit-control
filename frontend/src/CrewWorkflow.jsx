import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { getJson } from './api';
import { formatDate, formatTime } from './outlook';

const categories = ['wildlife', 'heat', 'lightning', 'flooding', 'mud', 'fire', 'other', 'water', 'access'];

async function postJson(path, body) {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Action failed');
  return payload;
}

function useSiteData(path, enabled, revision) {
  const [state, setState] = useState({ data: null, error: '', loading: enabled });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer;
    async function refresh() {
      try {
        const data = await getJson(path, controller.signal);
        if (!controller.signal.aborted) setState({ data, error: '', loading: false });
      } catch (error) {
        if (!controller.signal.aborted) setState(previous => ({ ...previous, error: error.message, loading: false }));
      }
      if (!controller.signal.aborted) timer = setTimeout(refresh, 15000);
    }
    refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [path, enabled, revision]);
  return state;
}

function ReportMap({ site, pin, onPin, reports }) {
  const element = useRef(), map = useRef(), marker = useRef(), history = useRef();
  const change = useRef(onPin);
  change.current = onPin;
  useEffect(() => {
    map.current = L.map(element.current).setView([site.latitude, site.longitude], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 18 }).addTo(map.current);
    L.circleMarker([site.latitude, site.longitude], { radius: 10, color: '#1b663c' }).addTo(map.current).bindTooltip('Plant inventory location');
    marker.current = L.marker([site.latitude, site.longitude], { draggable: true,
      icon: L.divIcon({ className: 'report-location-pin', html: '<span>+</span>', iconSize: [30, 30], iconAnchor: [15, 15] }) }).addTo(map.current);
    marker.current.on('dragend', () => { const p = marker.current.getLatLng(); change.current({ latitude: p.lat, longitude: p.lng }); });
    map.current.on('click', event => change.current({ latitude: event.latlng.lat, longitude: event.latlng.lng }));
    history.current = L.layerGroup().addTo(map.current);
    return () => map.current.remove();
  }, [site.id]);
  useEffect(() => {
    if (Number.isFinite(pin.latitude) && Number.isFinite(pin.longitude) && Math.abs(pin.latitude) <= 90 && Math.abs(pin.longitude) <= 180) {
      marker.current.setLatLng([pin.latitude, pin.longitude]);
    }
  }, [pin]);
  useEffect(() => {
    history.current.clearLayers();
    for (const report of reports) {
      const label = document.createElement('span');
      label.textContent = `${report.category} · ${report.status} · ${report.note}`;
      L.circleMarker([report.latitude, report.longitude], { radius: 7, color: report.status === 'resolved' ? '#697780' : '#b96b19' })
        .bindTooltip(label).addTo(history.current);
    }
  }, [reports]);
  return <div className="report-map" ref={element} aria-label="Hazard location map. Click or drag the plus pin; coordinates can also be edited below."/>;
}

export function CrewReports({ site, enabled, onChanged }) {
  const [revision, setRevision] = useState(0), [status, setStatus] = useState(''), [category, setCategory] = useState(''), [query, setQuery] = useState('');
  const [pin, setPin] = useState({ latitude: site.latitude, longitude: site.longitude });
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [actionError, setActionError] = useState('');
  const params = new URLSearchParams({ site_id: site.id, ...(status && { status }), ...(category && { category }), ...(query && { q: query }) });
  const { data, error, loading } = useSiteData('/api/reports?' + params, enabled, revision);
  const reports = data?.history ?? [];
  function changed() { setRevision(value => value + 1); onChanged?.(); }
  async function submit(event) {
    event.preventDefault();
    setBusy(true); setMessage(''); setActionError('');
    const form = event.currentTarget;
    try {
      const body = new FormData(form);
      body.set('site_id', site.id); body.set('latitude', pin.latitude); body.set('longitude', pin.longitude);
      const photo = body.get('photo');
      if (!photo?.size || photo.size > 5 * 1024 * 1024) throw new Error('Choose a JPEG, PNG or WebP photo up to 5 MiB.');
      const response = await fetch('/api/reports', { method: 'POST', body });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Report could not be submitted');
      form.reset(); setMessage('Report saved and shared in this site’s history.'); changed();
    } catch (error) { setActionError(error.message); }
    finally { setBusy(false); }
  }
  async function resolve(id) {
    setBusy(true); setActionError('');
    try { await postJson(`/api/reports/${id}/resolve`, {}); changed(); }
    catch (error) { setActionError(error.message); }
    finally { setBusy(false); }
  }
  return <section className="panel evidence-card" id="reports" aria-labelledby="reports-title">
    <div className="panel-title"><h3 id="reports-title">Crew hazard reports & location history</h3><span>Refreshes every 15 seconds</span></div>
    <p className="muted">Crew-reported sightings and local conditions. No recent reports does not mean no hazard. Resolved reports remain in history.</p>
    {!enabled ? <p className="integration-note">Select Tiger Data storage to submit and read shared reports. File inventory has no report storage.</p> : <>
      <ReportMap site={site} pin={pin} onPin={setPin} reports={reports}/>
      <form className="report-form" onSubmit={submit}>
        <p>Click the map or drag the + pin to locate the hazard. Edit coordinates for keyboard access.</p>
        <div className="form-grid"><label>Latitude<input aria-label="Hazard latitude" type="number" step="any" min="-90" max="90" required value={pin.latitude} onChange={event => setPin({ ...pin, latitude: event.target.value === '' ? '' : Number(event.target.value) })}/></label>
          <label>Longitude<input aria-label="Hazard longitude" type="number" step="any" min="-180" max="180" required value={pin.longitude} onChange={event => setPin({ ...pin, longitude: event.target.value === '' ? '' : Number(event.target.value) })}/></label>
          <label>Hazard category<select name="category" required>{categories.map(value => <option key={value}>{value}</option>)}</select></label>
          <label>Take or upload a photo<input type="file" name="photo" accept="image/jpeg,image/png,image/webp" capture="environment" required/></label></div>
        <label>Description<textarea name="note" required minLength={1} maxLength={2000} rows={3} placeholder="What did you see, and where?"/></label>
        <button className="text-button" type="submit" disabled={busy}>Share hazard report</button>
      </form>
      <div className="form-grid history-filters"><label>Search history<input aria-label="Search report history" value={query} onChange={event => setQuery(event.target.value)} placeholder="Description text"/></label>
        <label>History status<select value={status} onChange={event => setStatus(event.target.value)}><option value="">All reports</option><option value="unresolved">Active</option><option value="resolved">Resolved</option></select></label>
        <label>History category<select value={category} onChange={event => setCategory(event.target.value)}><option value="">All categories</option>{categories.map(value => <option key={value}>{value}</option>)}</select></label></div>
      {loading && <p>Loading report history…</p>}
      {error && <p className="error" role="alert">Report history unavailable: {error}</p>}
      {data && !reports.length && <p>No reports match this history view.</p>}
      {reports.map(report => <article className="report history-report" key={report.id}>
        <div><strong>{report.category} · {report.status === 'unresolved' ? 'Active' : 'Resolved'}</strong><p>{report.note}</p>
          <small>{formatTime(report.observed_at, site.timezone)} · {report.latitude.toFixed(5)}, {report.longitude.toFixed(5)} · Crew report</small>
          {report.location_flag && <p className="integration-note">Pin is over 5 km from the inventory site. Verify its location.</p>}
          {report.status === 'unresolved' && <p><button className="text-button" disabled={busy} onClick={() => resolve(report.id)}>Mark resolved</button></p>}</div>
        <a href={report.photo_url} target="_blank" rel="noreferrer"><img src={report.photo_url} loading="lazy" alt={`Crew photo: ${report.category}`}/></a>
      </article>)}
    </>}
    {message && <p role="status">{message}</p>}{actionError && <p className="error" role="alert">{actionError}</p>}
  </section>;
}

export function BriefingInbox({ site, enabled }) {
  const [preview, setPreview] = useState(null), [busy, setBusy] = useState(false), [actionError, setActionError] = useState('');
  const { data, error } = useSiteData(`/api/briefings?site_id=${site.id}&event_mode=live`, enabled, 0);
  async function showPreview() {
    setBusy(true); setActionError('');
    try { setPreview((await postJson('/api/briefings/preview', { site_id: site.id })).briefing); }
    catch (error) { setActionError(error.message); }
    finally { setBusy(false); }
  }
  return <article className="panel evidence-card" id="briefings">
    <h3>Daily briefing inbox</h3><p className="briefing-time">6:00 PM <span>{site.timezone}</span></p>
    <p>Delivered here for the next local day. The background worker must be running. Previews do not count as delivery.</p>
    {!enabled ? <p className="integration-note">Shared briefings require Tiger Data storage.</p> : <>
      <button type="button" className="text-button" disabled={busy} onClick={showPreview}>Preview tomorrow’s briefing</button>
      {preview && <details open className="briefing-record"><summary>Preview · not delivered · target {formatDate(preview.forecast_target_date)}</summary><p className="alert-copy">{preview.body_text}</p></details>}
      {data?.briefings.map(briefing => <details className="briefing-record" key={briefing.id}><summary>Delivered {formatTime(briefing.delivered_at, site.timezone)} · for {formatDate(briefing.forecast_target_date)}</summary><p className="alert-copy">{briefing.body_text}</p></details>)}
      {data && !data.briefings.length && <p>No delivered briefing is recorded for this site.</p>}
      {(error || actionError) && <p className="error" role="alert">{actionError || error}</p>}
    </>}
  </article>;
}
