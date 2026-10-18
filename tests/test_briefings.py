import pytest

from backend.briefings import deliver_briefing, due_date, generate_briefing, run_due_briefings, store_inputs_provider
from backend.ops_store import MemoryStore
from ops_support import SITES, Clock, at, make_client, site

DEERHAVEN = site(663)          # America/New_York
GRAND_GULF = site(6072)        # America/Chicago
EASTERN = {s['id'] for s in SITES if s['timezone'] == 'America/New_York'}
CENTRAL = {s['id'] for s in SITES if s['timezone'] == 'America/Chicago'}


@pytest.fixture
def store():
    return MemoryStore(SITES)


def run(store, text, **kw):
    return run_due_briefings(at(text), store, SITES, **kw)


def created_ids(results):
    return {r['site_id'] for r in results if r['created']}


def test_before_6pm_local_does_nothing(store):
    assert run(store, '2026-10-17T21:59:00+00:00') == []  # 5:59 PM EDT
    assert store.list_briefings(None, 'live') == []


def test_eastern_at_6pm_generates_once_and_central_waits(store):
    first = run(store, '2026-10-17T22:00:00+00:00')  # 6 PM EDT, 5 PM CDT
    assert created_ids(first) == EASTERN
    assert run(store, '2026-10-17T22:30:00+00:00') == []
    central = run(store, '2026-10-17T23:00:00+00:00')  # 6 PM CDT = 7 PM EDT
    assert created_ids(central) == CENTRAL
    assert len(store.list_briefings(None, 'live')) == len(SITES)


def test_delivery_date_and_target_date_are_local_and_distinct(store):
    # 00:30 UTC on Oct 18 is still 7:30 PM Oct 17 in Chicago.
    run(store, '2026-10-18T00:30:00+00:00')
    briefing = store.get_briefing(6072, '2026-10-17', 'live')
    assert briefing['delivery_local_date'] == '2026-10-17'
    assert briefing['forecast_target_date'] == '2026-10-18'
    assert briefing['timezone'] == 'America/Chicago'


def test_dst_fall_back_edge(store):
    # Nov 1 2026: clocks fall back; 6 PM EST is 23:00 UTC (not 22:00 as in EDT).
    assert not created_ids(run(store, '2026-11-01T22:30:00+00:00')) & EASTERN
    assert created_ids(run(store, '2026-11-01T23:00:00+00:00')) == EASTERN
    assert due_date(GRAND_GULF, at('2026-11-01T23:59:00+00:00')) is None  # 5:59 PM CST
    assert str(due_date(GRAND_GULF, at('2026-11-02T00:00:00+00:00'))) == '2026-11-01'


def test_duplicate_execution_creates_one_row(store):
    now = at('2026-10-17T22:05:00+00:00')
    inputs = store_inputs_provider(store)(DEERHAVEN, '2026-10-17', 'live', now)
    first, created = deliver_briefing(store, DEERHAVEN, '2026-10-17', inputs, 'live', now)
    again, created_again = deliver_briefing(store, DEERHAVEN, '2026-10-17', inputs, 'live', now)
    assert created and not created_again and first['id'] == again['id']
    assert len(store.list_briefings(663, 'live')) == 1
    # The store itself refuses a second row for the same key.
    assert store.save_briefing(dict(first, id='other')) == (first['id'], False)


def test_replay_and_live_are_isolated(store):
    run(store, '2026-10-17T22:00:00+00:00', event_mode='replay')
    assert store.list_briefings(663, 'live') == []
    run(store, '2026-10-17T22:00:00+00:00')
    assert len(store.list_briefings(663, 'live')) == 1
    replay = store.list_briefings(663, 'replay')
    assert len(replay) == 1 and replay[0]['label'] == 'simulated replay'
    assert replay[0]['body_text'].startswith('SIMULATED REPLAY.')


def test_missing_inputs_are_stated_not_filled(store):
    now = at('2026-10-17T22:00:00+00:00')
    inputs = store_inputs_provider(store)(DEERHAVEN, '2026-10-17', 'live', now)
    briefing = generate_briefing(DEERHAVEN, '2026-10-17', inputs, 'live', now)
    assert set(briefing['missing_inputs']) >= {'forecast', 'official alerts', 'model index', 'lightning feed'}
    forecast = next(s for s in briefing['sections'] if s['key'] == 'forecast')
    assert forecast['available'] is False and 'Forecast unavailable' in forecast['lines'][0]
    assert not any(ch.isdigit() for ch in ' '.join(forecast['lines']))
    assert 'Official alerts: unavailable' in briefing['body_text']
    assert 'safe' not in briefing['body_text'].lower()


def test_supplied_inputs_with_labels():
    inputs = {
        'forecast': {'source': 'Open-Meteo', 'valid_date': '2026-10-18', 'retrieved_at': '2026-10-17T21:00:00+00:00',
                     'values': {'temperature_2m_max': {'value': 31.2, 'unit': '°C'}, 'precipitation_sum': {'value': None, 'unit': 'mm'}}},
        'active_alerts': [], 'lightning_today': [], 'unresolved_reports': [],
        'lightning_coverage': {'status': 'COMPLETE'},
        'model': {'status': 'ok', 'model_index': 6.24, 'target_date': '2026-10-18', 'model_version': 'v1',
                  'outside_training_range': ['wind_gusts_10m_max'], 'outside_training_counties': True},
    }
    briefing = generate_briefing(DEERHAVEN, '2026-10-17', inputs, 'live', at('2026-10-17T22:00:00+00:00'))
    text = briefing['body_text']
    assert 'Maximum air temperature: 31.2 °C' in text
    assert 'Total precipitation: unavailable' in text
    assert 'Experimental model index (0-10; not a probability' in text and '6.2' in text
    assert 'Outside training counties' in text and 'wind_gusts_10m_max' in text
    assert briefing['missing_inputs'] == ['forecast precipitation_sum']


def test_rewriter_failure_falls_back_to_template():
    def broken(text):
        raise RuntimeError('provider down')
    now = at('2026-10-17T22:00:00+00:00')
    briefing = generate_briefing(DEERHAVEN, '2026-10-17', {}, 'live', now, rewriter=broken)
    assert briefing['rewrite_status'] == 'failed_fallback_template'
    assert briefing['rewritten_text'] is None and briefing['body_text']
    ok = generate_briefing(DEERHAVEN, '2026-10-17', {}, 'live', now, rewriter=lambda text: 'Rewritten.')
    assert ok['rewrite_status'] == 'rewritten' and ok['rewritten_text'] == 'Rewritten.'


def test_manual_generation_routes(monkeypatch, store):
    clock = Clock('2026-10-17T20:00:00+00:00')  # 4 PM EDT
    client = make_client(monkeypatch, store, clock)
    early = client.post('/api/briefings/generate', json={'site_id': 663, 'event_mode': 'live'})
    assert early.status_code == 409 and early.json['code'] == 'not_due'
    replay = client.post('/api/briefings/generate', json={'site_id': 663})
    assert replay.status_code == 201 and replay.json['briefing']['event_mode'] == 'replay'
    assert client.post('/api/briefings/generate', json={'site_id': 663}).json['created'] is False
    clock.set('2026-10-17T22:01:00+00:00')
    live = client.post('/api/briefings/generate', json={'site_id': 663, 'event_mode': 'live'})
    assert live.status_code == 201 and live.json['briefing']['trigger'] == 'manual'
    listed = client.get('/api/briefings?site_id=663').json
    assert listed['event_mode'] == 'live' and [b['event_mode'] for b in listed['briefings']] == ['live']
    assert client.get('/api/briefings?site_id=663&event_mode=replay').json['count'] == 1
    assert client.post('/api/briefings/generate', json={'site_id': 9999999}).status_code == 404
    assert client.post('/api/briefings/generate', json={'site_id': 663, 'event_mode': 'demo'}).status_code == 400
