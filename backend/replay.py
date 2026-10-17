"""Simulated lightning replay. Always labeled "simulated replay"; never touches live state.

One replay clock drives event time, countdowns and expiry:
replay_now = replay_epoch + (wall_now - started_at) * speed.
"""
import json
import uuid
from datetime import timedelta
from pathlib import Path

from .lightning import parse_strike, process_strike
from .ops_common import REPLAY_LABEL, ValidationError, iso

SCRIPT_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'replay' / 'strikes.json'
DEFAULT_SPEED = 10
MAX_SPEED = 120


def load_script(path=SCRIPT_PATH):
    return json.loads(Path(path).read_text())


def parse_speed(value):
    if value is None:
        return DEFAULT_SPEED
    if isinstance(value, bool):
        raise ValidationError(f'speed must be a number from 1 to {MAX_SPEED}')
    try:
        speed = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f'speed must be a number from 1 to {MAX_SPEED}') from None
    if not 1 <= speed <= MAX_SPEED:
        raise ValidationError(f'speed must be a number from 1 to {MAX_SPEED}')
    return speed


def replay_now(session, wall_now):
    elapsed = max(wall_now - session['started_at'], timedelta(0))
    return session['replay_epoch'] + elapsed * session['speed']


class ReplaySource:
    """Strike source backed by the scripted replay file."""
    name = 'simulated-replay'
    configured = True

    def __init__(self, script=None):
        self.script = script or load_script()

    def due(self, session, now):
        """Strikes delivered at or before replay time `now`, each with its replay-clock delivery time."""
        epoch = session['replay_epoch']
        for entry in sorted(self.script['strikes'], key=lambda e: e['delivered_offset_s']):
            delivered = epoch + timedelta(seconds=entry['delivered_offset_s'])
            if delivered > now:
                break
            payload = {'event_id': entry['event_id'], 'source': self.script.get('source', self.name),
                       'latitude': entry['latitude'], 'longitude': entry['longitude'],
                       'occurred_at': iso(epoch + timedelta(seconds=entry['occurred_offset_s'])),
                       'event_mode': 'replay', 'replay_session_id': session['session_id']}
            yield parse_strike(payload), delivered


def start_session(store, wall_now, speed=None, script=None):
    """Reset every replay row, then start a fresh session."""
    script = script or load_script()
    session = {'session_id': uuid.uuid4().hex[:12], 'started_at': wall_now,
               'replay_epoch': wall_now.replace(microsecond=0), 'speed': parse_speed(speed), 'active': True}
    store.reset_replay()
    store.start_replay_session(session)
    return session


def sync(store, wall_now, sites, script=None):
    """Process scripted strikes that are due on the replay clock. Idempotent via strike dedup."""
    session = store.get_replay_session()
    if session is None:
        return None, None
    now = replay_now(session, wall_now)
    source = ReplaySource(script)
    for strike, delivered in source.due(session, now):
        process_strike(store, strike, sites, delivered)
    store.record_feed('replay', source.script.get('source', source.name), checked_at=now)
    return session, now


def session_view(session, wall_now, script=None):
    if session is None:
        return {'active': False, 'label': REPLAY_LABEL, 'session': None, 'replay_now': None,
                'note': 'No simulated replay session is running. POST /api/replay/sessions to start one.'}
    script = script or load_script()
    now = replay_now(session, wall_now)
    elapsed = (now - session['replay_epoch']).total_seconds()
    return {
        'active': True, 'label': REPLAY_LABEL,
        'session': {'session_id': session['session_id'], 'started_at': iso(session['started_at']),
                    'replay_epoch': iso(session['replay_epoch']), 'speed': session['speed']},
        'replay_now': iso(now), 'replay_elapsed_seconds': int(elapsed),
        'scripted_strikes': len(script['strikes']),
        'delivered_strikes': sum(1 for e in script['strikes'] if e['delivered_offset_s'] <= elapsed),
        'note': 'Simulated replay. Replay timestamps come from the replay clock and are not real observations.',
    }
