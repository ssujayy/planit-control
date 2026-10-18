import io
import json

import pytest

from backend.lightning import parse_strike, process_strike
from backend.ops_store import MemoryStore
from backend.timeline import site_timeline
from ops_fixtures import FIXTURES, build_responses
from ops_support import SITES, Clock, at, make_client, site, strike_payload
from image_support import JPEG

DEERHAVEN = site(663)
EVENT_TYPES = {'lightning_hold_started', 'lightning_hold_extended', 'lightning_hold_expired',
               'report_created', 'report_resolved', 'briefing_delivered'}


def add_strike(store, event_id, miles, when, event_mode='live'):
    strike = parse_strike(strike_payload(event_id, DEERHAVEN, miles, when, event_mode=event_mode))
    process_strike(store, strike, SITES, strike['occurred_at'])


def types(payload):
    return [e['type'] for e in payload['events']]


def test_expiry_is_derived_per_hold_episode():
    store = MemoryStore(SITES)
    add_strike(store, 'a', 5, '2026-10-17T18:00:00+00:00')
    add_strike(store, 'b', 5, '2026-10-17T18:10:00+00:00')
    add_strike(store, 'c', 5, '2026-10-17T19:00:00+00:00')  # after the first hold ended
    during = site_timeline(store, DEERHAVEN, 'live', at('2026-10-17T19:10:00+00:00'))
    assert types(during) == ['lightning_hold_started', 'lightning_hold_extended', 'lightning_hold_expired', 'lightning_hold_started']
    assert during['events'][2]['occurred_at'] == '2026-10-17T18:40:00+00:00'
    after = site_timeline(store, DEERHAVEN, 'live', at('2026-10-17T19:31:00+00:00'))
    assert types(after)[-1] == 'lightning_hold_expired'
    assert 'Only the lightning hold is lifted' in after['events'][-1]['summary']
    assert all(e['occurred_at'].endswith('+00:00') for e in after['events'])


def test_live_never_shows_replay_and_replay_shows_live_reports(monkeypatch):
    store = MemoryStore(SITES)
    clock = Clock('2026-10-17T22:00:00+00:00')
    client = make_client(monkeypatch, store, clock)
    client.post('/api/replay/sessions', json={'speed': 10})
    client.post('/api/reports', content_type='multipart/form-data',
                data={'site_id': '663', 'latitude': '29.76', 'longitude': '-82.39', 'category': 'other', 'note': 'Hot',
                      'photo': (io.BytesIO(JPEG), 'p.jpg')})
    clock.set('2026-10-17T22:02:00+00:00')
    replay = client.get('/api/sites/663/timeline?event_mode=replay').json
    live = client.get('/api/sites/663/timeline').json
    assert {e['event_mode'] for e in live['events']} == {'live'}
    assert types(live) == ['report_created']
    assert {(e['type'], e['event_mode']) for e in replay['events']} >= {('report_created', 'live'), ('lightning_hold_started', 'replay')}
    assert replay['label'] == 'simulated replay' and live['label'] is None


def test_empty_timeline_and_unknown_site(monkeypatch):
    client = make_client(monkeypatch, MemoryStore(SITES), Clock('2026-10-17T22:00:00+00:00'))
    empty = client.get('/api/sites/6051/timeline').json
    assert empty['events'] == [] and 'does not mean there is no hazard' in empty['note']
    assert client.get('/api/sites/9999999/timeline').status_code == 404
    assert client.get('/api/sites/663/timeline?event_mode=demo').status_code == 400


def test_strike_ingest_is_replay_only(monkeypatch):
    client = make_client(monkeypatch, MemoryStore(SITES), Clock('2026-10-17T22:00:00+00:00'))
    live = strike_payload('x', DEERHAVEN, 2, '2026-10-17T21:59:00+00:00')
    assert client.post('/api/lightning/strikes', json=live).status_code == 400
    replay = dict(live, event_mode='replay')
    assert client.post('/api/lightning/strikes', json=replay).status_code == 400  # no session yet
    client.post('/api/replay/sessions', json={})
    response = client.post('/api/lightning/strikes', json=replay)
    assert response.status_code == 200 and response.json['affected_sites'][0]['site_id'] == 663
    assert client.post('/api/lightning/strikes', json=replay).json['duplicate'] is True
    assert client.get('/api/lightning/holds').json['holds'] == []
    assert client.post('/api/replay/reset').json['reset'] is True
    assert client.get('/api/lightning/holds?event_mode=replay').json['holds'] == []


@pytest.fixture(scope='module')
def fresh(request):
    mp = pytest.MonkeyPatch()
    request.addfinalizer(mp.undo)
    return build_responses(lambda store, clock: make_client(mp, store, clock))


def shape(value):
    """Nested key structure, ignoring values (ids and timestamps differ between runs)."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items() if k not in ('fixture', 'http_status')}
    if isinstance(value, list):
        return [shape(value[0])] if value and isinstance(value[0], dict) else 'list'
    return 'value'


def test_fixtures_are_marked_and_match_real_responses(fresh):
    files = sorted(FIXTURES.glob('ops_*.json'))
    assert {p.stem for p in files} == {n for n in fresh if not n.startswith('_')}
    for path in files:
        fixture = json.loads(path.read_text())
        assert fixture['fixture'] is True, path.name
        status, body = fresh[path.stem]
        assert fixture['http_status'] == status, path.name
        if path.stem in ('ops_timeline', 'ops_errors'):
            continue
        assert shape(fixture) == shape(body), path.name


def test_timeline_fixture_has_every_event_type_and_empty_state():
    examples = json.loads((FIXTURES / 'ops_timeline.json').read_text())['examples']
    assert set(types(examples['replay'])) | set(types(examples['live'])) == EVENT_TYPES
    assert examples['empty']['events'] == []
    assert all(e['event_mode'] == 'live' for e in examples['live']['events'])
