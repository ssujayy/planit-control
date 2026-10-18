"""Stored evidence and explicit attention ranking. No provider calls or ML fabrication."""
from datetime import date, datetime, timezone
import math

from . import db
from .official_alerts import FRESHNESS_SECONDS as OFFICIAL_FRESHNESS_SECONDS
from .planning_weather import summarize

WEATHER_FRESHNESS_SECONDS = 1800
UNIMPLEMENTED_LAYERS = ['lightning', 'flood', 'wildfire', 'wildlife', 'model']
CURRENT_FIELDS = ['temperature_2m', 'relative_humidity_2m', 'apparent_temperature', 'precipitation', 'wind_gusts_10m']
HOURLY_FIELDS = [*CURRENT_FIELDS, 'soil_moisture_0_to_1cm']


def iso(value):
    return value.isoformat() if value is not None else None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def mapping(value):
    return value if isinstance(value, dict) else {}


def serialize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def official_evidence(record, now):
    payload = record.get('payload')
    monitoring = {'state': 'UNAVAILABLE', 'fetched_at': None}
    if not payload:
        return None, monitoring
    fetched = db.timestamp(payload['fetched_at'])
    stale = not 0 <= (now - fetched).total_seconds() <= OFFICIAL_FRESHNESS_SECONDS or bool(record.get('error_code'))
    monitoring = {'state': 'STALE' if stale else 'COMPLETE', 'fetched_at': fetched.isoformat()}
    active = []
    for alert in payload['alerts']:
        expires = db.timestamp(alert['expires'])
        if alert.get('ends'):
            expires = min(expires, db.timestamp(alert['ends']))
        if db.timestamp(alert['effective']) <= now < expires:
            event = alert['event'].lower()
            hazard = 'flood' if 'flood' in event else ('fire_weather' if 'fire' in event or 'red flag' in event else 'weather')
            active.append({**alert, 'hazard': hazard})
    return active, monitoring


def missing_fields(payload):
    missing = []
    current = mapping(payload.get('current'))
    if not number(current.get('time')):
        missing.append('current.time')
    for name in CURRENT_FIELDS:
        if not number(current.get(name)) or not mapping(payload.get('current_units')).get(name):
            missing.append(f'current.{name}')
    hourly = mapping(payload.get('hourly'))
    times = hourly.get('time', [])
    if not isinstance(times, list) or not times or not all(number(value) for value in times):
        missing.append('hourly.time')
        times = []
    for name in HOURLY_FIELDS:
        values = hourly.get(name)
        if (not isinstance(values, list) or not times or len(values) != len(times)
                or not all(number(value) for value in values)
                or not mapping(payload.get('hourly_units')).get(name)):
            missing.append(f'hourly.{name}')
    return missing


def build_outlook(mode, *, now=None):
    now = now or datetime.now(timezone.utc)
    sites = db.list_sites(mode)
    stored = db.latest_weather() if mode == 'live' else {}
    official = db.latest_official_alerts() if mode == 'live' else {}
    holds = db.get_lightning_holds(mode='live') if mode == 'live' else {}
    reports = db.list_crew_reports(mode='live', unresolved_only=True) if mode == 'live' else []
    predictions = db.next_day_predictions(now=now, mode='live') if mode == 'live' else {}
    by_site = {}
    for report in reports:
        by_site.setdefault(report['site_id'], []).append(report)
    rows = []
    for site in sites:
        record = stored.get(site['id'], {})
        payload = record.get('payload')
        monitoring = {
            'state': 'UNAVAILABLE',
            'last_attempt_at': iso(record.get('last_attempt_at')),
            'last_success_at': iso(record.get('last_success_at')),
            'error_code': record.get('error_code'),
        }
        weather = None
        unavailable = list(UNIMPLEMENTED_LAYERS)
        reasons = []
        if payload:
            try:
                fetched = datetime.fromisoformat(payload['fetched_at'])
                age = (now - fetched).total_seconds()
            except (KeyError, ValueError, TypeError):
                age = -1
            stale = not 0 <= age <= WEATHER_FRESHNESS_SECONDS or bool(record.get('error_code'))
            valid_time = mapping(payload.get('current')).get('time')
            if number(valid_time):
                valid_age = now.timestamp() - valid_time
                stale = stale or valid_age > WEATHER_FRESHNESS_SECONDS or valid_age < -900
            missing = missing_fields(payload)
            monitoring['state'] = 'STALE' if stale else ('PARTIAL' if missing else 'COMPLETE')
            weather = {
                **payload, 'cached': True, 'stale': stale,
                'current_evidence_type': 'modeled_current_conditions',
                'hourly_evidence_type': 'forecast',
            }
            coverage = 'STALE' if stale else 'PARTIAL'
            if stale:
                reasons.append('Stored weather is stale or its latest refresh failed.')
            if missing:
                reasons.append('Missing weather values or units: ' + ', '.join(missing) + '.')
        else:
            unavailable.insert(0, 'weather')
            coverage = 'UNAVAILABLE'
            reasons.append('No stored weather snapshot.')
        active_alerts, official_monitoring = official_evidence(official.get(site['id'], {}), now)
        if official_monitoring['state'] == 'COMPLETE':
            unavailable.remove('flood')
        else:
            reasons.append('Official warning monitoring is ' + official_monitoring['state'].lower() + '.')
        if official_monitoring['state'] == 'STALE':
            coverage = 'STALE'
        if official_monitoring['state'] == 'COMPLETE' and coverage == 'UNAVAILABLE':
            coverage = 'PARTIAL'
        hold = holds.get(site['id'])
        if hold and hold['hold_until'] <= now:
            hold = None  # Expiration affects lightning only; other evidence is retained.
        if hold:
            hold = {**hold, 'seconds_remaining': max(0, int((hold['hold_until'] - now).total_seconds()))}
            reasons.insert(0, 'Active lightning hold until ' + hold['hold_until'].isoformat() + '.')
        site_reports = by_site.get(site['id'], [])
        prediction = predictions.get(site['id'])
        if prediction:
            prediction = {**prediction, 'evidence_type': 'experimental_prediction', 'label': 'experimental model index'}
            unavailable.remove('model')
        if active_alerts:
            reasons.insert(0, 'Official alerts: ' + ', '.join(alert['event'] for alert in active_alerts) + '.')
        if site_reports:
            reasons.insert(0, f'{len(site_reports)} unresolved crew report(s).')
        planning = summarize(weather, site, now)
        missing_summary = [name for name in ('heat_index_max_f', 'precipitation_sum_mm', 'soil_moisture_max_m3_m3')
                           if planning[name] is None]
        if weather and missing_summary:
            reasons.append('Incomplete next-local-day forecast: ' + ', '.join(missing_summary) + '.')
            if monitoring['state'] == 'COMPLETE':
                monitoring['state'] = 'PARTIAL'
        if planning['heat_index_max_f'] is not None:
            reasons.append(f"Tomorrow's derived forecast heat index reaches {planning['heat_index_max_f']} °F.")
        reasons.append('Incomplete monitoring: ' + ', '.join(unavailable) + '.')
        if mode == 'demo':
            reasons.append('Hazard integrations and ranking are not implemented in demo storage.')
        hazard_state = ('STOP_WORK' if hold else 'ALERT' if active_alerts else 'ELEVATED' if site_reports
                        else 'NO_ACTIVE_ALERTS' if official_monitoring['state'] == 'COMPLETE' else None)
        rows.append({
            'site': site, 'weather': weather, 'weather_monitoring': monitoring,
            'coverage': coverage, 'hazard_state': hazard_state, 'alerts': active_alerts,
            'model_index': prediction['score'] if prediction else None,
            'prediction': prediction, 'planning_weather': planning,
            'official_alerts_monitoring': official_monitoring, 'lightning_hold': hold,
            'unresolved_reports': site_reports,
            'river_proximity': {'status': 'unknown', 'source': None},
            'unavailable_layers': unavailable, 'reasons': reasons,
        })
    if mode == 'live':
        def priority(row):
            alerts = row['alerts'] or []
            severe = any(alert['severity'] in ('Extreme', 'Severe')
                         and ('warning' in alert['event'].lower() or alert.get('urgency') == 'Immediate')
                         for alert in alerts)
            level = (0 if row['lightning_hold'] else 1 if severe else 2 if alerts else
                     3 if row['unresolved_reports'] else 4 if 'lightning' in row['unavailable_layers'] else 5)
            heat = row['planning_weather']['heat_index_max_f']
            score = row['model_index']
            return (level, -heat if heat is not None else float('inf'),
                    -score if score is not None else float('inf'), row['site']['state'], row['site']['name'])
        rows.sort(key=priority)
    for index, row in enumerate(rows, 1):
        row['rank'] = index if mode == 'live' else None
    return {
        'storage_mode': mode, 'event_mode': 'live', 'as_of': now.isoformat(),
        'weather_freshness_seconds': WEATHER_FRESHNESS_SECONDS,
        'ranking_status': 'evidence_based' if mode == 'live' else 'not_implemented',
        'count': len(rows), 'sites': serialize(rows),
    }
