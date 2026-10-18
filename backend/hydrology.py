"""USGS stream proximity plus an explicitly illustrative overnight-rain advisory."""
from datetime import datetime, time, timedelta, timezone
import json
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from . import db
from .planning_weather import numeric
from .providers import open_provider

URL = 'https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/6/query'
FRESHNESS = timedelta(days=30)
RADIUS_METERS = 1000
RAIN_THRESHOLD_MM = 25


def fetch_context(site):
    params = {'f': 'json', 'where': 'ftype=460',
              'geometry': f"{site['longitude']},{site['latitude']}", 'geometryType': 'esriGeometryPoint',
              'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects', 'distance': RADIUS_METERS,
              'units': 'esriSRUnit_Meter', 'outFields': 'permanent_identifier,gnis_name,ftype',
              'returnGeometry': 'false'}
    request = urllib.request.Request(URL + '?' + urllib.parse.urlencode(params),
                                     headers={'User-Agent': 'PlanIT-Control-Hackathon/0.1'})
    try:
        with open_provider(request, timeout=12) as response:
            raw = json.load(response)
        if 'error' in raw or not isinstance(raw.get('features'), list) or raw.get('exceededTransferLimit'):
            raise ValueError('Invalid or truncated geometry query')
        features = [feature['attributes'] for feature in raw['features']]
        if any(not feature.get('permanent_identifier') or feature.get('ftype') != 460 for feature in features):
            raise ValueError('Unexpected flowline fields')
        return {'status': 'near_mapped_stream' if features else 'no_mapped_stream_within_radius',
                'near_stream': bool(features), 'source': 'USGS National Hydrography Dataset',
                'source_url': URL, 'radius_meters': RADIUS_METERS, 'features': features,
                'evidence_type': 'geographic_context',
                'method': 'NHD StreamRiver centerlines intersecting a 1 km buffer around EIA plant coordinates.',
                'note': 'Not a floodplain, river gauge, bank-distance measurement or proof of absence of flood exposure.'}
    except Exception:
        raise RuntimeError('USGS stream proximity unavailable.') from None


def context_view(record, now):
    if not record.get('payload'):
        return {'status': 'unknown', 'source': None, 'monitoring': 'UNAVAILABLE'}
    fetched = db.timestamp(record['fetched_at'])
    stale = not timedelta(0) <= now - fetched <= FRESHNESS or bool(record.get('error_code'))
    return {**record['payload'], 'fetched_at': fetched.isoformat(), 'monitoring': 'STALE' if stale else 'COMPLETE'}


def overnight_advisory(site, weather, context, now):
    zone = ZoneInfo(site['timezone'])
    local = now.astimezone(zone)
    end_day = local.date() if local.hour >= 6 else local.date() - timedelta(days=1)
    start = datetime.combine(end_day - timedelta(days=1), time(18), tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(end_day, time(6), tzinfo=zone).astimezone(timezone.utc)
    result = {'id': f"rainfall-stream:{site['id']}:{end_day}", 'active': None, 'severity': 'advisory',
              'source': 'USGS NHD + Open-Meteo modeled past conditions', 'evidence_type': 'modeled_rainfall_advisory',
              'window_start': start.isoformat(), 'window_end': end.isoformat(), 'occurred_at': end.isoformat(),
              'threshold_mm': RAIN_THRESHOLD_MM, 'rainfall_mm': None,
              'reason': 'Complete fresh overnight rainfall and stream proximity context are required.',
              'recommended_action': 'Review official flood instructions and inspect wet access routes under the site work plan.',
              'note': 'Illustrative 25 mm overnight rainfall + stream within 1 km rule; not an official flood warning. Rainfall is modeled, not a rain-gauge observation.'}
    if (context.get('monitoring') != 'COMPLETE' or not isinstance(context.get('near_stream'), bool)
            or not weather or weather.get('stale')):
        return result
    hourly, units = weather.get('hourly') or {}, weather.get('hourly_units') or {}
    times, rain = hourly.get('time') or [], hourly.get('precipitation') or []
    # Provider precipitation is a preceding-hour sum; exclude start, include end.
    expected = set(range(int(start.timestamp()) + 3600, int(end.timestamp()) + 1, 3600))
    indices = [i for i, value in enumerate(times) if numeric(value) and value in expected]
    if (units.get('precipitation') != 'mm' or len(times) != len(rain) or len(indices) != len(expected)
            or {times[i] for i in indices} != expected or any(not numeric(rain[i]) or rain[i] < 0 for i in indices)):
        return result
    total = round(sum(rain[i] for i in indices), 2)
    active = context.get('near_stream') is True and total >= RAIN_THRESHOLD_MM
    return {**result, 'active': active, 'rainfall_mm': total,
            'reason': f'Modeled overnight rainfall {total} mm; nearby mapped stream: {context.get("near_stream")}.',
            'weather_fetched_at': weather.get('fetched_at')}


def refresh_context(*, site_ids=None):
    from .ingestion import selected_sites
    now, records = datetime.now(timezone.utc), db.latest_hydrology()
    succeeded = failed = 0
    for site in selected_sites(site_ids):
        if context_view(records.get(site['id'], {}), now)['monitoring'] == 'COMPLETE':
            succeeded += 1
            continue
        try:
            payload = fetch_context(site)
        except RuntimeError:
            db.save_hydrology(site['id'], now, None)
            failed += 1
        else:
            db.save_hydrology(site['id'], now, payload)
            succeeded += 1
    return {'succeeded': succeeded, 'failed': failed}


class HydrologyRotation:
    def __init__(self, site_ids=None):
        self.site_ids, self.position = site_ids, 0

    def __call__(self):
        from .ingestion import selected_sites
        sites = selected_sites(self.site_ids)
        site = sites[self.position % len(sites)]
        self.position += 1
        return refresh_context(site_ids=[site['id']])
