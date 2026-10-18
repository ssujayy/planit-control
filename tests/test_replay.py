from datetime import timedelta

import pytest

from backend.lightning import RADIUS_KM, haversine_km, lightning_status
from backend.ops_store import MemoryStore
from backend.replay import load_script, parse_speed, start_session, sync
from backend.ops_common import ValidationError
from ops_support import SITES, at, site

WALL = at('2026-10-17T22:00:00+00:00')
EXPECTED_SITES = {'dh-001': {663}, 'dh-002': set(), 'dh-003': {663}, 'dh-004': {663},
                  'gg-001': {6072}, 'gg-002': {6072}, 'ht-001': {6051}, 'ht-002': set()}


def test_script_is_labeled_and_distances_hold():
    script = load_script()
    assert script['label'] == 'simulated replay'
    assert 'SIMULATED' in script['description']
    for entry in script['strikes']:
        within = {s['id'] for s in SITES
                  if haversine_km(entry['latitude'], entry['longitude'], s['latitude'], s['longitude']) <= RADIUS_KM}
        assert within == EXPECTED_SITES[entry['event_id']], entry['event_id']
    assert site(6072)['timezone'] == 'America/Chicago'


def test_replay_session_drives_holds_on_one_clock():
    store = MemoryStore(SITES)
    session = start_session(store, WALL, speed=10)
    epoch = session['replay_epoch']
    # Two wall minutes at 10x is twenty replay minutes.
    _, now = sync(store, WALL + timedelta(minutes=2), SITES)
    assert now == epoch + timedelta(minutes=20)
    assert store.get_hold(663, 'replay')['hold_until'] == epoch + timedelta(minutes=40)
    assert store.get_hold(6072, 'replay')['hold_until'] == epoch + timedelta(minutes=35)
    assert store.get_hold(6051, 'replay')['hold_until'] == epoch + timedelta(minutes=45)
    view = lightning_status(store, site(663), 'replay', now, replay_session=session)
    assert view['label'] == 'simulated replay'
    assert view['hazard']['seconds_remaining'] == 20 * 60
    assert view['coverage']['status'] == 'COMPLETE'
    # Later: Grand Gulf extended; the delayed Deerhaven strike did not shorten anything.
    _, now = sync(store, WALL + timedelta(minutes=3), SITES)
    assert store.get_hold(6072, 'replay')['hold_until'] == epoch + timedelta(minutes=55)
    assert store.get_hold(663, 'replay')['hold_until'] == epoch + timedelta(minutes=40)
    # Repeated syncs are idempotent.
    events = len(store.list_events(663, 'replay'))
    sync(store, WALL + timedelta(minutes=3), SITES)
    assert len(store.list_events(663, 'replay')) == events == 2
    # Live state untouched.
    assert store.list_holds('live') == [] and store.list_events(663, 'live') == []


def test_restarting_session_resets_replay_only():
    store = MemoryStore(SITES)
    store.store_strike({'event_mode': 'live', 'source': 'feed', 'event_id': 'l1', 'occurred_at': WALL,
                        'latitude': 29.76, 'longitude': -82.39}, [663])
    start_session(store, WALL)
    sync(store, WALL + timedelta(minutes=2), SITES)
    assert store.list_holds('replay')
    second = start_session(store, WALL + timedelta(minutes=5))
    assert store.list_holds('replay') == []
    assert store.get_replay_session()['session_id'] == second['session_id']
    assert store.get_hold(663, 'live') is not None


@pytest.mark.parametrize('bad', [0, 121, 'fast', True])
def test_invalid_speed_rejected(bad):
    with pytest.raises(ValidationError):
        parse_speed(bad)
