from datetime import timedelta

import pytest

from backend.lightning import LiveSource, haversine_km, lightning_status, parse_strike, poll_source, process_strike
from backend.ops_common import ValidationError
from backend.ops_store import MemoryStore
from ops_support import SITES, at, site, strike_payload

DEERHAVEN = site(663)
OTHER = site(6072)  # Grand Gulf, far from Deerhaven
T0 = '2026-10-17T18:00:00+00:00'


@pytest.fixture
def store():
    return MemoryStore(SITES)


def strike(event_id, miles, when=T0, **kw):
    return parse_strike(strike_payload(event_id, DEERHAVEN, miles, when, **kw))


def run(store, s, now=None):
    return process_strike(store, s, SITES, now or s['occurred_at'])


def status(store, now, event_mode='live', **kw):
    return lightning_status(store, DEERHAVEN, event_mode, at(now), **kw)


def test_haversine_matches_known_distance():
    # Gainesville to Jacksonville area plants are roughly 99.5 km apart.
    assert haversine_km(29.7592, -82.3878, 30.364818, -81.625967) == pytest.approx(99.5, abs=0.5)


def test_strike_at_9_miles_starts_hold(store):
    result = run(store, strike('s1', 9))
    assert [a['site_id'] for a in result['affected_sites']] == [663]
    assert result['affected_sites'][0]['effect'] == 'started'
    view = status(store, '2026-10-17T18:10:00+00:00')
    assert view['hazard']['state'] == 'STOP_WORK'
    assert view['hazard']['hold_until'] == '2026-10-17T18:30:00Z'
    assert view['hazard']['seconds_remaining'] == 20 * 60


def test_strike_at_11_miles_does_not_hold(store):
    result = run(store, strike('s1', 11))
    assert result['affected_sites'] == []
    assert status(store, '2026-10-17T18:10:00+00:00')['hazard']['hold_active'] is False


def test_duplicate_is_noop(store):
    run(store, strike('s1', 9))
    later = strike('s1', 5, when='2026-10-17T18:20:00+00:00')
    result = run(store, later)
    assert result['duplicate'] is True and result['accepted'] is False
    assert store.get_hold(663, 'live')['hold_until'] == at('2026-10-17T18:30:00+00:00')
    assert len(store.list_events(663, 'live')) == 1


def test_late_older_strike_does_not_shorten(store):
    run(store, strike('s1', 9, when='2026-10-17T18:10:00+00:00'))
    late = strike('s0', 4, when='2026-10-17T18:00:00+00:00')
    result = run(store, late, now=at('2026-10-17T18:12:00+00:00'))
    assert result['affected_sites'][0]['effect'] == 'no_change_older_strike'
    assert store.get_hold(663, 'live')['hold_until'] == at('2026-10-17T18:40:00+00:00')


def test_later_strike_extends(store):
    run(store, strike('s1', 9))
    result = run(store, strike('s2', 3, when='2026-10-17T18:15:00+00:00'))
    assert result['affected_sites'][0]['effect'] == 'extended'
    assert status(store, '2026-10-17T18:35:00+00:00')['hazard']['hold_until'] == '2026-10-17T18:45:00Z'
    assert [e['type'] for e in store.list_events(663, 'live')] == ['lightning_hold_started', 'lightning_hold_extended']


def test_expiry_clears_only_lightning_hold(store):
    run(store, strike('s1', 9))
    other = parse_strike(strike_payload('o1', OTHER, 2, '2026-10-17T18:20:00+00:00'))
    process_strike(store, other, SITES, other['occurred_at'])
    store.create_report({'id': 'r1', 'site_id': 663, 'event_mode': 'live', 'status': 'unresolved',
                         'created_at': at(T0), 'category': 'wildlife'}, None)
    view = status(store, '2026-10-17T18:31:00+00:00')
    assert view['hazard']['hold_active'] is False
    assert view['hazard']['state'] is None  # unknown: no live feed, never "clear"
    assert 'safe' not in str(view).lower() and 'all clear' not in str(view).lower()
    assert lightning_status(store, OTHER, 'live', at('2026-10-17T18:31:00+00:00'))['hazard']['state'] == 'STOP_WORK'
    assert store.get_report('r1')['status'] == 'unresolved'


def test_missing_live_feed_is_unavailable_not_clear(store):
    view = status(store, T0, live_source=LiveSource())
    assert view['coverage']['status'] == 'UNAVAILABLE'
    assert view['hazard']['state'] is None
    assert 'not evidence of no strikes' in view['coverage']['note']


def test_stale_live_feed_is_marked_stale(store):
    source = LiveSource(feed=lambda since, now: [])
    poll_source(store, source, SITES, at(T0))
    assert status(store, '2026-10-17T18:05:00+00:00', live_source=source)['coverage']['status'] == 'COMPLETE'
    stale = status(store, '2026-10-17T18:30:00+00:00', live_source=source)
    assert stale['coverage']['status'] == 'STALE'
    assert stale['hazard']['state'] is None


def test_unconfigured_live_source_processes_nothing(store):
    assert poll_source(store, LiveSource(), SITES, at(T0))['status'] == 'UNAVAILABLE'
    assert store.get_feeds('live') == []


def test_replay_cannot_change_live_state(store):
    run(store, strike('r1', 2, event_mode='replay'))
    assert store.get_hold(663, 'live') is None
    assert store.list_events(663, 'live') == []
    assert status(store, '2026-10-17T18:05:00+00:00')['hazard']['hold_active'] is False
    assert store.get_hold(663, 'replay') is not None


def test_same_event_id_in_other_mode_is_not_duplicate(store):
    run(store, strike('x', 2, event_mode='replay'))
    assert run(store, strike('x', 2))['duplicate'] is False


@pytest.mark.parametrize('change', [
    {'occurred_at': '2026-10-17T18:00:00'},          # naive
    {'occurred_at': 'yesterday'},
    {'latitude': 91},
    {'longitude': -181},
    {'latitude': True},
    {'event_id': ''},
    {'source': None},
    {'event_mode': 'demo'},
])
def test_invalid_payloads_rejected(change):
    payload = dict(strike_payload('s1', DEERHAVEN, 9, T0), **change)
    with pytest.raises(ValidationError):
        parse_strike(payload)


def test_future_strike_rejected(store):
    with pytest.raises(ValidationError):
        process_strike(store, strike('s1', 9, when='2026-10-17T19:00:00+00:00'), SITES, at(T0))


def test_state_survives_reloading_the_store(store):
    run(store, strike('s1', 9))
    reopened = MemoryStore(SITES, data=store.data)
    view = lightning_status(reopened, DEERHAVEN, 'live', at(T0) + timedelta(minutes=29))
    assert view['hazard']['state'] == 'STOP_WORK'
    later = lightning_status(reopened, DEERHAVEN, 'live', at(T0) + timedelta(minutes=30))
    assert later['hazard']['hold_active'] is False
