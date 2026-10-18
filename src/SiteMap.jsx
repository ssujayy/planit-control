import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function SiteMap({ sites, selectedId, onSelect }) {
  const element = useRef(null), map = useRef(null), layer = useRef(null);
  const select = useRef(onSelect);
  select.current = onSelect;
  useEffect(() => {
    map.current = L.map(element.current).setView([30.5, -84], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors', maxZoom: 18,
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { map.current.remove(); map.current = null; };
  }, []);
  useEffect(() => {
    layer.current.clearLayers();
    sites.forEach(site => {
      const selected = site.id === selectedId;
      const marker = L.circleMarker([site.latitude, site.longitude], {
        radius: selected ? 9 : 5, color: selected ? '#0d6758' : '#5c7680',
        fillColor: selected ? '#22a98c' : '#9bb3b8', fillOpacity: .9, weight: 2,
      });
      const text = document.createElement('span'); text.textContent = site.name;
      marker.bindTooltip(text).on('click', () => select.current(site.id));
      marker.addTo(layer.current);
    });
    if (sites.length && !map.current._planitFitted) {
      map.current.fitBounds(L.latLngBounds(sites.map(s => [s.latitude, s.longitude])), { padding: [25, 25], maxZoom: 8 });
      map.current._planitFitted = true;
    }
  }, [sites, selectedId]);
  return <div ref={element} className="map" aria-label="Power plant locations; use the adjacent keyboard-accessible site list to select a site" />;
}

