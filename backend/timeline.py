"""Per-site chronological evidence timeline.

Live queries return only live events. Replay queries return replay events plus live
crew reports (which keep event_mode "live"); replay events never appear in live queries.
Hold expiry is derived from hold_until and the clock, never stored as a flag.
"""
from datetime import datetime

from .briefings import HOLD_TYPES
from .ops_common import iso, mode_label, parse_iso

REPORT_TYPES = ('report_created', 'report_resolved')
EXPIRED_SUMMARY = ('Lightning hold countdown ended. Only the lightning hold is lifted; other hazards '
                   'and lightning feed coverage are unchanged.')
EMPTY_NOTE = 'No operational events recorded for this site. This does not mean there is no hazard.'


def _until(event):
    value = event['details']['hold_until']
    return parse_iso(value, 'hold_until') if isinstance(value, str) else value


def derive_expirations(hold_events, now):
    """Expired events at the end of each hold episode whose hold_until has passed."""
    expired, current = [], None
    for event in sorted(hold_events, key=lambda e: (e['occurred_at'], e['id'])):
        if event['type'] == 'lightning_hold_started' and current is not None and current <= event['occurred_at']:
            expired.append(current)
        until = _until(event)
        current = until if current is None else max(current, until)
    if current is not None and current <= now:
        expired.append(current)
    return expired


def _expired_event(site_id, event_mode, until):
    prefix = 'Simulated replay: ' if event_mode == 'replay' else ''
    return {'id': f'{event_mode}:hold-expired:{site_id}:{iso(until)}', 'site_id': site_id, 'type': 'lightning_hold_expired',
            'occurred_at': until, 'source': 'planit-control (computed from hold_until)', 'event_mode': event_mode,
            'summary': prefix + EXPIRED_SUMMARY, 'details': {'hold_until': iso(until), 'clears_only': 'lightning_hold'}}


def event_view(event):
    occurred = event['occurred_at']
    return {'id': event['id'], 'site_id': event['site_id'], 'type': event['type'],
            'occurred_at': iso(occurred) if isinstance(occurred, datetime) else occurred,
            'source': event['source'], 'event_mode': event['event_mode'], 'summary': event['summary'],
            'details': event['details']}


def site_timeline(store, site, event_mode, now):
    events = [e for e in store.list_events(site['id'], event_mode) if e['occurred_at'] <= now]
    holds = [e for e in events if e['type'] in HOLD_TYPES]
    events += [_expired_event(site['id'], event_mode, until) for until in derive_expirations(holds, now)]
    if event_mode == 'replay':
        events += [e for e in store.list_events(site['id'], 'live') if e['type'] in REPORT_TYPES]
    events.sort(key=lambda e: (e['occurred_at'], e['id']))
    includes = ['live events only'] if event_mode == 'live' else ['simulated replay events', 'live crew reports (event_mode "live")']
    return {'site_id': site['id'], 'event_mode': event_mode, 'label': mode_label(event_mode), 'as_of': iso(now),
            'includes': includes, 'events': [event_view(e) for e in events], 'count': len(events),
            'note': EMPTY_NOTE if not events else None}
