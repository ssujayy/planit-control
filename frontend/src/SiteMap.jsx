import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import RadarControls from './RadarControls';

export default function SiteMap({ sites, selectedId, onSelect, storageMode }) {
  const element = useRef(null), map = useRef(null), layer = useRef(null);
  const [readyMap, setReadyMap] = useState(null);
  const select = useRef(onSelect);
  const lastRender = useRef('');
  select.current = onSelect;
  useEffect(() => {
    lastRender.current = '';
    const usBounds = L.latLngBounds([[24.4, -125], [49.4, -66.9]]);
    map.current = L.map(element.current, {
      maxBounds: usBounds,
      maxBoundsViscosity: 1,
    }).setView([30.5, -84], 5);
    // Keep the widest view at the contiguous U.S., including on smaller screens.
    const updateMinZoom = () => map.current.setMinZoom(map.current.getBoundsZoom(usBounds));
    updateMinZoom();
    map.current.on('resize', updateMinZoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors · <a href="https://www.rainviewer.com/" target="_blank" rel="noreferrer">RainViewer</a>', maxZoom: 18, className: 'base-map-tiles',
    }).addTo(map.current);
    const radarPane = map.current.createPane('rainRadar');
    radarPane.style.zIndex = '350';
    radarPane.style.pointerEvents = 'none';
    layer.current = L.layerGroup().addTo(map.current);
    setReadyMap(map.current);
    return () => { map.current.remove(); map.current = null; };
  }, []);
  useEffect(() => {
    const signature = JSON.stringify([selectedId, sites]);
    if (lastRender.current === signature) return;
    lastRender.current = signature;
    layer.current.clearLayers();
    sites.forEach(site => {
      const selected = site.id === selectedId;
      const state = site.attention_state ?? 'UNKNOWN';
      const marker = L.marker([site.latitude, site.longitude], {
        icon: L.divIcon({
          className: `site-pin pin-${state.toLowerCase()} ${selected ? 'is-selected' : ''}`,
          html: `<span>${Number.isInteger(site.attention_rank) ? site.attention_rank : '·'}</span>`,
          iconSize: [28, 28], iconAnchor: [14, 14],
        }),
        keyboard: false, zIndexOffset: selected ? 1000 : 0,
      });
      const text = document.createElement('span');
      text.textContent = [site.attention_rank ? `#${site.attention_rank}` : null, site.name].filter(Boolean).join(' · ');
      marker.bindTooltip(text).on('click', () => select.current(site.id));
      marker.addTo(layer.current);
    });
    if (sites.length && !map.current._planitFitted) {
      map.current.fitBounds(L.latLngBounds(sites.map(s => [s.latitude, s.longitude])), { padding: [25, 25], maxZoom: 8 });
      map.current._planitFitted = true;
    }
    const selected = sites.find(site => site.id === selectedId);
    if (selected) map.current.panInside([selected.latitude, selected.longitude], { padding: [35, 35], animate: false });
  }, [sites, selectedId]);
  return <><div ref={element} className="map" aria-label="Power plant locations and rain radar; use the adjacent keyboard-accessible site list to select a site" />
    {readyMap && <RadarControls map={readyMap} site={sites.find(site => site.id === selectedId)} enabled={storageMode === 'live'}/>}</>;
}

