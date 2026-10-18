"""Regression checks for crew lightning recording and automatic tomorrow reports."""
import pytest

from backend.briefings import generate_briefing
from backend.lightning import lightning_status
from backend.ops_store import MemoryStore
from ops_support import Clock, SITES, at, make_client, site


def test_crew_lightning_is_persisted_deduplicated_and_keeps_feed_unavailable(monkeypatch):
    store, clock = MemoryStore(SITES), Clock('2026-10-17T18:00:00+00:00')
    client = make_client(monkeypatch, store, clock)
    path = '/api/sites/663/lightning/observations'
    body = {'observed': True, 'event_id': 'crew-1'}
    assert client.post(path, json=body).status_code == 201
    assert client.post(path, json=body).status_code == 200
    reopened = MemoryStore(SITES, data=store.data)
    view = lightning_status(reopened, site(663), 'live', clock())
    assert view['hazard']['state'] == 'STOP_WORK'
    assert view['coverage']['status'] == 'UNAVAILABLE'
    assert reopened.get_hold(663, 'replay') is None
    history = client.get(path).get_json()
    assert history['count'] == 1
    assert history['events'][0]['source'] == 'crew-observed'
    clock.set('2026-10-17T18:10:00+00:00')
    assert client.post(path, json={'observed': True, 'event_id': 'crew-2'}).status_code == 201
    assert store.get_hold(663, 'live')['hold_until'] == at('2026-10-17T18:40:00+00:00')
    clock.set('2026-10-17T18:41:00+00:00')
    assert client.get(path).get_json()['count'] == 2
    assert lightning_status(store, site(663), 'live', clock())['hazard']['hold_active'] is False


@pytest.mark.parametrize('body', [None, [], {'observed': False, 'event_id': 'a'},
    {'observed': True}, {'observed': True, 'event_id': 'a', 'event_mode': 'replay'},
    {'observed': True, 'event_id': 'a', 'source': 'provider'},
    {'observed': True, 'event_id': 'a', 'occurred_at': '2026-10-17T18:00:00Z'},
    {'observed': True, 'event_id': 'a', 'latitude': 0}])
def test_crew_lightning_requires_confirmation_and_cannot_impersonate_feed(monkeypatch, body):
    store = MemoryStore(SITES)
    client = make_client(monkeypatch, store, Clock('2026-10-17T18:00:00+00:00'))
    assert client.post('/api/sites/663/lightning/observations', json=body).status_code == 400
    assert store.data['lightning_events'] == {}


def test_auto_preview_is_read_only_and_matches_target_day(monkeypatch):
    store = MemoryStore(SITES)
    client = make_client(monkeypatch, store, Clock('2026-10-17T18:00:00+00:00'))
    payload = client.get('/api/sites/663/briefing-preview').get_json()
    assert payload['preview'] is True and payload['delivered'] is False
    assert payload['briefing']['display']['target_date'] == '2026-10-18'
    assert payload['briefing']['delivered_at'] is None
    assert store.list_briefings(None, 'live') == []


def test_replay_query_cannot_record_live_crew_observation(monkeypatch):
    store = MemoryStore(SITES)
    client = make_client(monkeypatch, store, Clock('2026-10-17T18:00:00+00:00'))
    response = client.post('/api/sites/663/lightning/observations?event_mode=replay',
                           json={'observed': True, 'event_id': 'simulated'})
    assert response.status_code == 400
    assert store.data['lightning_events'] == {}


@pytest.mark.parametrize('stale,valid_date,expected', [
    (False, '2026-10-18', 29), (True, '2026-10-18', None), (False, '2026-10-17', None)])
def test_report_display_uses_forecast_not_current_readings(stale, valid_date, expected):
    inputs = {'forecast': {'valid_date': valid_date, 'stale': stale, 'retrieved_at': '2026-10-17T17:00:00Z',
        'values': {'precipitation_sum_mm': {'value': 29, 'unit': 'mm'}}},
        'model': {'model_index': .064, 'target_date': '2026-10-18'}}
    report = generate_briefing(site(663), '2026-10-17', inputs, 'live', at('2026-10-17T18:00:00Z'))
    rain = next(item for item in report['display']['conditions'] if item['key'] == 'precipitation_sum_mm')
    assert rain['value'] == expected
    assert '0.06' in report['body_text']
    assert report['display']['based_on'] == '2026-10-17T17:00:00Z'
    assert report['display']['missing_data']
