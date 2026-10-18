import React, { useEffect, useState } from 'react';
import L from 'leaflet';
import { getJson } from './api';
import { formatTime } from './outlook';

export default function RadarControls({ map, site, enabled }) {
  const [radar, setRadar] = useState(null), [error, setError] = useState('');
  const [visible, setVisible] = useState(true), [dark, setDark] = useState(true);
  const [selectedTime, setSelectedTime] = useState(null), [playing, setPlaying] = useState(false);
  const [loadingTiles, setLoadingTiles] = useState(false), [tileError, setTileError] = useState('');
  const frames = radar?.frames ?? [];
  const frameIndex = selectedTime == null ? frames.length - 1 : Math.max(0, frames.findIndex(frame => frame.time === selectedTime));
  const frame = frames[frameIndex];
  const timezone = site?.timezone ?? 'America/New_York';

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer;
    async function refresh() {
      try {
        const data = await getJson('/api/radar?mode=live', controller.signal);
        if (!Array.isArray(data.frames)) throw new Error('Rain radar returned invalid information.');
        if (!controller.signal.aborted) { setRadar(data); setError(''); }
      } catch (error) {
        if (!controller.signal.aborted) setError(error.message);
      }
      if (!controller.signal.aborted) timer = setTimeout(refresh, 60000);
    }
    refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [enabled]);

  useEffect(() => {
    const container = map.getContainer();
    container.classList.toggle('radar-dark', dark);
    return () => container.classList.remove('radar-dark');
  }, [map, dark]);

  useEffect(() => {
    if (!enabled || !visible || !frame) { setLoadingTiles(false); setTileError(''); return; }
    setLoadingTiles(true); setTileError('');
    let active = true;
    const layer = L.tileLayer(frame.tile_url, {
      pane: 'rainRadar', opacity: 0.8, maxNativeZoom: 7, maxZoom: 18,
      tileSize: 256, keepBuffer: 1, updateWhenIdle: true,
      className: 'rain-radar-tile',
    });
    layer.on('loading', () => { if (active) setLoadingTiles(true); });
    layer.on('load', () => { if (active) setLoadingTiles(false); });
    layer.on('tileerror', () => { if (active) setTileError('Some radar images could not load. Rain coverage may be incomplete.'); });
    layer.addTo(map);
    return () => {
      active = false;
      // Leaflet's remove event unregisters map listeners before local handlers are cleared.
      if (map.hasLayer(layer)) map.removeLayer(layer);
      layer.off();
    };
  }, [map, enabled, visible, frame?.tile_url]);

  useEffect(() => {
    if (!playing || !visible || !enabled || frames.length < 2) return;
    const timer = setInterval(() => setSelectedTime(previous => {
      const index = previous == null ? frames.length - 1 : Math.max(0, frames.findIndex(frame => frame.time === previous));
      const next = (index + 1) % frames.length;
      return next === frames.length - 1 ? null : frames[next].time;
    }), 1200);
    return () => clearInterval(timer);
  }, [playing, visible, enabled, frames]);

  function chooseFrame(index) {
    setPlaying(false);
    const next = Math.max(0, Math.min(frames.length - 1, index));
    setSelectedTime(next === frames.length - 1 ? null : frames[next]?.time ?? null);
  }
  const ready = enabled && !!frame;
  const stale = !!error || radar?.stale || frames.length > 0 && Date.now() - frames.at(-1).time * 1000 > 1800000;
  return <section className="radar-controls" aria-label="Rain radar controls">
    <div className="radar-heading">
      <div><strong>Rain radar</strong><span className="radar-time" role="status">
        {!enabled ? 'Unavailable in inventory mode' : !visible ? 'Overlay off' : !frame ? error ? 'Unavailable' : radar ? 'Waiting for radar update' : 'Loading radar…'
          : `${stale ? 'Needs update · ' : ''}${frameIndex === frames.length - 1 ? 'Latest' : 'History'} · ${formatTime(frame.frame_time, timezone)}`}
      </span></div>
      <div className="radar-actions">
        <button type="button" className="radar-toggle" aria-pressed={visible} disabled={!enabled} onClick={() => { setVisible(value => !value); setPlaying(false); }}>{!enabled ? 'Rain unavailable' : `Rain ${visible ? 'on' : 'off'}`}</button>
        <button type="button" className="radar-dark-toggle" aria-pressed={dark} onClick={() => setDark(value => !value)}>Dark map</button>
        <button type="button" className="radar-focus" disabled={!site} onClick={() => map.setView([site.latitude, site.longitude], 7, { animate: false })}>Focus selected site</button>
      </div>
    </div>
    {ready && <>
      <div className="radar-playback">
        <button type="button" className="radar-step-back" disabled={!visible} aria-label="Previous radar frame" onClick={() => chooseFrame(frameIndex - 1)}>‹</button>
        <button type="button" className="radar-play" disabled={!visible || frames.length < 2} aria-pressed={playing} onClick={() => setPlaying(value => !value)}>{playing ? 'Pause' : 'Play'}</button>
        <input className="radar-timeline" type="range" min="0" max={frames.length - 1} step="1" value={frameIndex} disabled={!visible}
          aria-label="Radar frame time" aria-valuetext={formatTime(frame.frame_time, timezone)} onChange={event => chooseFrame(Number(event.target.value))}/>
        <button type="button" className="radar-step-forward" disabled={!visible} aria-label="Next radar frame" onClick={() => chooseFrame(frameIndex + 1)}>›</button>
        <button type="button" className="radar-latest" disabled={!visible} onClick={() => { setPlaying(false); setSelectedTime(null); }}>Latest</button>
      </div>
    </>}
    {loadingTiles && visible && <p className="radar-loading" role="status">Loading radar images…</p>}
    {(error || tileError || radar?.reason) && <p className="radar-warning" role="status">{[error, tileError, radar?.reason].filter(Boolean).join(' ')}{error && frame ? ' Showing older radar information.' : ''}</p>}
  </section>;
}
