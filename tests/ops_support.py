"""Shared helpers for Workstream B tests (no database needed)."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = json.loads((ROOT / 'data' / 'sites.json').read_text())['sites']
KM_PER_MILE = 1.609344


def site(site_id):
    return next(s for s in SITES if s['id'] == site_id)


def offset_point(lat, lon, miles, bearing_deg):
    """Point at a great-circle distance and bearing from (lat, lon)."""
    r = 6371.0088
    d = miles * KM_PER_MILE / r
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def at(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def strike_payload(event_id, base_site, miles, when, event_mode='live', source='test-feed', bearing=0):
    lat, lon = offset_point(base_site['latitude'], base_site['longitude'], miles, bearing)
    return {'event_id': event_id, 'source': source, 'latitude': lat, 'longitude': lon,
            'occurred_at': when, 'event_mode': event_mode}


def make_client(monkeypatch, store, clock):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('backend.app.load_dotenv', lambda *a, **kw: None)
    from backend.app import create_app
    app = create_app()
    app.config['OPS_STORE'] = store
    app.config['OPS_CLOCK'] = clock
    app.config['OPS_OUTLOOK'] = lambda now: None  # no database offline
    return app.test_client()


class Clock:
    """Mutable injected clock for route tests."""

    def __init__(self, text):
        self.now = at(text)

    def __call__(self):
        return self.now

    def set(self, text):
        self.now = at(text)
