"""Lightning stop-work holds: 10-mile radius, 30-minute countdown extended by later strikes.

Pure logic over an OpsStore. All times are UTC. "Held" is always computed from
hold_until and the supplied clock, never from a stored flag. Expiry ends only the
lightning hold; it is not a site-wide clearance.
"""
import math
from datetime import timedelta
from typing import Protocol

from .ops_common import EVENT_MODES, ValidationError, iso, mode_label, parse_coordinate, parse_iso

RADIUS_MILES = 10
RADIUS_KM = 16.0934
HOLD_MINUTES = 30
HOLD = timedelta(minutes=HOLD_MINUTES)
STALE_AFTER = timedelta(minutes=10)
FUTURE_TOLERANCE = timedelta(minutes=5)
EARTH_RADIUS_KM = 6371.0088
KM_PER_MILE = 1.609344
STATUS_NOTE = ('Lightning hold status covers only lightning. When the countdown ends, only the lightning hold '
               'is lifted; other hazards and feed coverage are unchanged.')


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _text(payload, field, limit):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{field} is required')
    if len(value) > limit:
        raise ValidationError(f'{field} must be at most {limit} characters')
    return value.strip()


def parse_strike(payload):
    """Validate a strike payload; returns a normalized strike dict or raises ValidationError."""
    if not isinstance(payload, dict):
        raise ValidationError('Strike must be a JSON object')
    event_mode = payload.get('event_mode')
    if event_mode not in EVENT_MODES:
        raise ValidationError('event_mode must be live or replay')
    session = payload.get('replay_session_id')
    if session is not None and (not isinstance(session, str) or len(session) > 64):
        raise ValidationError('replay_session_id must be a short string')
    return {
        'event_id': _text(payload, 'event_id', 128),
        'source': _text(payload, 'source', 64),
        'latitude': parse_coordinate(payload.get('latitude'), 'latitude', -90, 90),
        'longitude': parse_coordinate(payload.get('longitude'), 'longitude', -180, 180),
        'occurred_at': parse_iso(payload.get('occurred_at'), 'occurred_at'),
        'event_mode': event_mode,
        'replay_session_id': session,
    }


def _hold_event(strike, site_id, effect, distance_km, previous, new):
    miles = distance_km / KM_PER_MILE
    prefix = 'Simulated replay: ' if strike['event_mode'] == 'replay' else ''
    if effect == 'started':
        summary = f'{prefix}Strike {miles:.1f} mi from site started a {HOLD_MINUTES}-minute lightning stop-work hold.'
    else:
        summary = f'{prefix}Strike {miles:.1f} mi from site extended the lightning stop-work hold.'
    return {
        'id': f"{strike['event_mode']}:{strike['source']}:{strike['event_id']}:{site_id}",
        'site_id': site_id, 'type': f'lightning_hold_{effect}', 'occurred_at': strike['occurred_at'],
        'source': strike['source'], 'event_mode': strike['event_mode'], 'summary': summary,
        # Canonical record: the lightning_events row (source, event_mode, event_id). The hold itself is
        # lightning_holds (site_id, event_mode); hold_until here is the value this strike produced.
        'ref_table': 'lightning_events',
        'ref_key': {'source': strike['source'], 'event_mode': strike['event_mode'], 'event_id': strike['event_id']},
        'details': {'lightning_hold': {'site_id': site_id, 'event_mode': strike['event_mode']},
                    'distance_km': round(distance_km, 2), 'distance_miles': round(miles, 2),
                    'hold_until': iso(new), 'previous_hold_until': iso(previous)},
    }


def process_strike(store, strike, sites, now):
    """Apply one validated strike via the shared repository. Duplicates (event_mode, source, event_id) are a no-op."""
    if strike['occurred_at'] > now + FUTURE_TOLERANCE:
        raise ValidationError('occurred_at is in the future relative to the clock for this event_mode')
    result = {'accepted': True, 'duplicate': False, 'event_mode': strike['event_mode'], 'label': mode_label(strike['event_mode']),
              'strike': {'event_id': strike['event_id'], 'source': strike['source'], 'occurred_at': iso(strike['occurred_at']),
                         'latitude': strike['latitude'], 'longitude': strike['longitude']},
              'affected_sites': []}
    affected = []
    for site in sites:
        distance = haversine_km(strike['latitude'], strike['longitude'], site['latitude'], site['longitude'])
        if distance <= RADIUS_KM:
            affected.append((site, distance))
    before = {h['site_id']: h['hold_until'] for h in store.list_holds(strike['event_mode'])} if affected else {}
    if not store.store_strike(strike, [site['id'] for site, _ in affected]):
        return dict(result, accepted=False, duplicate=True)
    store.record_feed(strike['event_mode'], strike['source'], received_at=now)
    candidate = strike['occurred_at'] + HOLD
    for site, distance in affected:
        previous = before.get(site['id'])
        new = candidate if previous is None else max(previous, candidate)
        if previous is None or previous <= strike['occurred_at']:
            effect = 'started'
        elif new > previous:
            effect = 'extended'
        else:
            effect = 'no_change_older_strike'
        if effect != 'no_change_older_strike':
            store.add_event(_hold_event(strike, site['id'], effect, distance, previous, new))
        result['affected_sites'].append({
            'site_id': site['id'], 'site_name': site.get('name'), 'distance_km': round(distance, 2),
            'distance_miles': round(distance / KM_PER_MILE, 2), 'effect': effect, 'hold_until': iso(new)})
    result['affected_sites'].sort(key=lambda a: a['distance_km'])
    return result


class StrikeSource(Protocol):
    name: str
    configured: bool

    def fetch(self, since, now): ...


class LiveSource:
    """Placeholder for a real strike feed. No accessible feed is configured, so coverage is UNAVAILABLE."""
    name = 'live-strike-feed'

    def __init__(self, feed=None):
        self.feed = feed
        self.configured = feed is not None

    def fetch(self, since, now):
        if not self.configured:
            return []
        return self.feed(since, now)


def poll_source(store, source, sites, now, since=None):
    """For the single worker: fetch strikes from a configured live source and process them."""
    if not source.configured:
        return {'status': 'UNAVAILABLE', 'processed': 0, 'note': 'No live strike feed configured.'}
    results = [process_strike(store, parse_strike(dict(raw, event_mode='live', source=source.name)), sites, now)
               for raw in source.fetch(since, now)]
    store.record_feed('live', source.name, checked_at=now)
    return {'status': 'CHECKED', 'processed': len(results), 'note': None}


def coverage(store, event_mode, now, live_source=None, replay_session=None):
    """Monitoring coverage for lightning, kept separate from hazard state."""
    if event_mode == 'replay':
        if replay_session is None:
            return {'status': 'UNAVAILABLE', 'source': None, 'feed_connected': False, 'last_event_received_at': None, 'last_feed_check_at': None,
                    'note': 'No simulated replay session is running.'}
        received = [f['last_event_received_at'] for f in store.get_feeds('replay') if f['last_event_received_at']]
        return {'status': 'COMPLETE', 'source': 'simulated replay script', 'feed_connected': True, 'last_event_received_at': iso(max(received, default=None)),
                'last_feed_check_at': iso(now), 'note': 'Simulated replay. Not real lightning data.'}
    feeds = store.get_feeds('live')
    received = max((f['last_event_received_at'] for f in feeds if f['last_event_received_at']), default=None)
    checked = max((f['last_feed_check_at'] for f in feeds if f['last_feed_check_at']), default=None)
    connected = live_source is not None and live_source.configured
    base = {'source': live_source.name if live_source else None, 'feed_connected': connected,
            'last_event_received_at': iso(received), 'last_feed_check_at': iso(checked)}
    if not connected:
        return dict(base, status='UNAVAILABLE', note='No live lightning feed is connected. The absence of a hold is not evidence of no strikes.')
    if checked is None:
        return dict(base, status='UNAVAILABLE', note='The live lightning feed has not been checked yet.')
    if now - checked > STALE_AFTER:
        return dict(base, status='STALE', note=f'The live lightning feed was last checked more than {int(STALE_AFTER.total_seconds() // 60)} minutes ago.')
    note = None if received else 'Feed connected and checked; no strikes have been received.'
    return dict(base, status='COMPLETE', note=note)


def hold_view(hold, now, site=None):
    """hold is a lightning_holds row: site_id, hold_until, last_strike_at, source."""
    held = hold is not None and hold['hold_until'] > now
    return {
        'site_id': hold['site_id'] if hold else (site['id'] if site else None),
        'site_name': site.get('name') if site else None,
        'hold_active': held,
        'hold_until': iso(hold['hold_until']) if hold else None,
        'seconds_remaining': int((hold['hold_until'] - now).total_seconds()) if held else 0,
        'last_strike': {'source': hold['source'], 'occurred_at': iso(hold['last_strike_at'])} if hold else None,
    }


def lightning_status(store, site, event_mode, now, live_source=None, replay_session=None):
    cov = coverage(store, event_mode, now, live_source, replay_session)
    view = hold_view(store.get_hold(site['id'], event_mode), now, site)
    if view['hold_active']:
        state, reason = 'STOP_WORK', f'Lightning strike within {RADIUS_MILES} miles in the last {HOLD_MINUTES} minutes.'
    elif cov['status'] == 'COMPLETE':
        state, reason = 'NO_ACTIVE_ALERTS', 'No active lightning hold in the monitored evidence.'
    else:
        state, reason = None, f"Lightning hazard state unknown: monitoring coverage is {cov['status']}."
    return {
        'site_id': site['id'], 'event_mode': event_mode, 'label': mode_label(event_mode),
        'hazard': dict(view, type='lightning', state=state, state_reason=reason),
        'coverage': cov, 'radius_miles': RADIUS_MILES, 'hold_minutes': HOLD_MINUTES,
        'as_of': iso(now), 'clock': 'replay' if event_mode == 'replay' else 'server', 'note': STATUS_NOTE,
    }
