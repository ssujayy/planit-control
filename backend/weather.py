"""Verified Open-Meteo fields. No safety classifications are inferred here."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from threading import Lock
from zoneinfo import ZoneInfo
from .providers import open_provider

CACHE_SECONDS = 900
_cache = {}
_lock = Lock()


def fetch_weather(site):
    key = (site['latitude'], site['longitude'], site['timezone'])
    local_day = datetime.now(ZoneInfo(site['timezone'])).date().isoformat()
    with _lock:
        entry = _cache.get(key)
        if entry and entry.get('local_day') == local_day and time.monotonic() - entry['cached_at'] < CACHE_SECONDS:
            return {**entry['payload'], 'cached': True, 'stale': False}
    params = {
        'latitude': site['latitude'], 'longitude': site['longitude'],
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_gusts_10m',
        'hourly': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_gusts_10m,soil_moisture_0_to_1cm',
        'daily': 'temperature_2m_max,precipitation_sum,wind_gusts_10m_max',
        # Before 06:00, the latest completed overnight window starts two days ago.
        'forecast_days': 3, 'past_days': 2, 'timezone': site['timezone'], 'timeformat': 'unixtime',
        'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh', 'precipitation_unit': 'mm',
    }
    req = urllib.request.Request('https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params), headers={'User-Agent': 'PlanIT-Control-Hackathon/0.1'})
    try:
        with open_provider(req, timeout=12) as response:
            raw = json.load(response)
        if 'temperature_2m' not in raw.get('current', {}):
            raise ValueError('Missing current conditions')
        payload = {
            'source': 'Open-Meteo', 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'current': raw['current'], 'current_units': raw.get('current_units', {}),
            'hourly': raw.get('hourly', {}), 'hourly_units': raw.get('hourly_units', {}),
            'daily': raw.get('daily', {}), 'daily_units': raw.get('daily_units', {}),
            'daily_timezone': raw.get('timezone'),
            'daily_dates': [datetime.fromtimestamp(value, ZoneInfo(site['timezone'])).date().isoformat()
                            for value in raw.get('daily', {}).get('time', [])],
            'note': 'Modeled current conditions and forecasts; apparent temperature is not a calculated NWS heat index.',
        }
        from .planning_weather import summarize
        payload['planning_weather'] = summarize(payload, site, datetime.now(timezone.utc))
        with _lock:
            _cache[key] = {'cached_at': time.monotonic(), 'local_day': local_day, 'payload': payload}
        return {**payload, 'cached': False, 'stale': False}
    except Exception:
        if entry:
            return {**entry['payload'], 'cached': True, 'stale': True, 'warning': 'Refresh failed; showing last retrieved conditions.'}
        raise RuntimeError('Weather provider unavailable. No conditions or safety status can be inferred.') from None

