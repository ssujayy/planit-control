"""Verified Open-Meteo fields. No safety classifications are inferred here."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from threading import Lock

CACHE_SECONDS = 900
_cache = {}
_lock = Lock()


def fetch_weather(site):
    key = (site['latitude'], site['longitude'])
    with _lock:
        entry = _cache.get(key)
        if entry and time.monotonic() - entry['cached_at'] < CACHE_SECONDS:
            return {**entry['payload'], 'cached': True, 'stale': False}
    params = {
        'latitude': site['latitude'], 'longitude': site['longitude'],
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_gusts_10m',
        'hourly': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_gusts_10m,soil_moisture_0_to_1cm',
        # Three UTC days also cover all of tomorrow in the supported US zones.
        'forecast_days': 3, 'timezone': 'UTC', 'timeformat': 'unixtime',
    }
    req = urllib.request.Request('https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params), headers={'User-Agent': 'PlanIT-Control-Hackathon/0.1'})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = json.load(response)
        if 'temperature_2m' not in raw.get('current', {}):
            raise ValueError('Missing current conditions')
        payload = {
            'source': 'Open-Meteo', 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'current': raw['current'], 'current_units': raw.get('current_units', {}),
            'hourly': raw.get('hourly', {}), 'hourly_units': raw.get('hourly_units', {}),
            'note': 'Modeled current conditions and forecasts; apparent temperature is not a calculated NWS heat index.',
        }
        with _lock:
            _cache[key] = {'cached_at': time.monotonic(), 'payload': payload}
        return {**payload, 'cached': False, 'stale': False}
    except Exception:
        if entry:
            return {**entry['payload'], 'cached': True, 'stale': True, 'warning': 'Refresh failed; showing last retrieved conditions.'}
        raise RuntimeError('Weather provider unavailable. No conditions or safety status can be inferred.') from None

