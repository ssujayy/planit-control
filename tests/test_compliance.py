"""Focused integration checks; all environmental values here are test fixtures."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from backend import db, outlook, predictions, worker
from backend import ingestion
from backend import providers
from backend.hydrology import context_view, overnight_advisory
from backend.lightning import LiveSource, coverage, parse_strike, process_strike
from backend.ops_store import MemoryStore
from ops_support import SITES, Clock, make_client, site, strike_payload

NOW = datetime(2026, 10, 18, 16, tzinfo=timezone.utc)
SITE = site(663)


def daily_record():
    return {'payload': {'fetched_at': NOW.isoformat(), 'source': 'TEST FIXTURE',
                        'daily_timezone': SITE['timezone'], 'daily_dates': ['2026-10-18', '2026-10-19'],
                        'daily_units': predictions.UNITS,
                        'daily': {'temperature_2m_max': [25, 30], 'precipitation_sum': [0, 25],
                                  'wind_gusts_10m_max': [10, 50]}}}


def test_saved_model_receives_complete_daily_features_and_no_current_readings():
    result, provenance = predictions.compute_prediction(SITE, daily_record(), '2026-10-19', NOW)
    assert result['status'] == 'available'
    assert 0 <= result['model_index'] <= 10
    assert result['model_index'] == round(result['probability'] * 10, 2)
    assert provenance['input_kind'] == 'full_local_day_forecast'
    assert provenance['features']['precipitation_sum'] == 25
    assert len(provenance['artifact_sha256']) == 64
    assert result['model_contributions']['features']


@pytest.mark.parametrize('change', ['timezone', 'units', 'duplicate', 'partial', 'stale', 'failed'])
def test_unusable_daily_forecasts_never_produce_zero_scores(change):
    record = deepcopy(daily_record())
    payload = record['payload']
    if change == 'timezone': payload['daily_timezone'] = 'UTC'
    if change == 'units': payload['daily_units']['wind_gusts_10m_max'] = 'mph'
    if change == 'duplicate': payload['daily_dates'] = ['2026-10-19', '2026-10-19']
    if change == 'partial': payload['daily']['precipitation_sum'] = [0]
    if change == 'stale': payload['fetched_at'] = (NOW-timedelta(hours=1)).isoformat()
    if change == 'failed': record['error_code'] = 'weather_unavailable'
    result, _ = predictions.compute_prediction(SITE, record, '2026-10-19', NOW)
    assert result['status'] == 'unavailable' and result['model_index'] is None


def test_both_local_days_persist_real_model_results(monkeypatch):
    saved = []
    monkeypatch.setattr(db, 'list_sites', lambda mode: [SITE])
    monkeypatch.setattr(db, 'latest_weather', lambda: {SITE['id']: daily_record()})
    monkeypatch.setattr(db, 'save_prediction', lambda **row: saved.append(row))
    result = predictions.refresh_predictions(now=NOW)
    assert result == {'succeeded': 2, 'failed': 0}
    assert [str(row['valid_date']) for row in saved] == ['2026-10-18', '2026-10-19']
    assert all(row['mode'] == 'live' and row['status'] == 'available' for row in saved)


def test_default_worker_includes_bounded_prediction_and_briefing_jobs():
    jobs = worker.build_jobs()
    assert [job.name for job in jobs] == ['weather', 'official_alerts', 'hydrology', 'predictions', 'briefings']
    assert isinstance(jobs[3].callback, predictions.PredictionRotation)
    explicit = worker.build_jobs(job_modules=['backend.briefings:worker_jobs', 'backend.predictions:worker_jobs'])
    assert len(explicit) == len(jobs)


def test_preview_before_6pm_does_not_reserve_delivery(monkeypatch):
    store = MemoryStore(SITES)
    clock = Clock('2026-10-18T16:00:00+00:00')
    client = make_client(monkeypatch, store, clock)
    response = client.post('/api/briefings/preview', json={'site_id': 663})
    assert response.status_code == 200
    assert response.json['preview'] and not response.json['delivered']
    assert response.json['briefing']['delivered_at'] is None
    assert store.list_briefings(None, 'live') == []
    clock.set('2026-10-18T22:00:00+00:00')
    assert client.post('/api/briefings/generate', json={'site_id': 663, 'event_mode': 'live'}).status_code == 201


def rain_weather(total=30):
    start = datetime(2026, 10, 17, 22, tzinfo=timezone.utc)
    return {'stale': False, 'fetched_at': NOW.isoformat(), 'hourly_units': {'precipitation': 'mm'},
            'hourly': {'time': [int((start + timedelta(hours=i)).timestamp()) for i in range(1, 13)],
                       'precipitation': [total/12]*12}}


def test_rainfall_rule_requires_location_context_and_complete_nonstale_night():
    context = {'monitoring': 'COMPLETE', 'near_stream': True}
    result = overnight_advisory(SITE, rain_weather(), context, NOW)
    assert result['active'] and result['rainfall_mm'] == 30
    assert result['evidence_type'] == 'modeled_rainfall_advisory'
    assert not overnight_advisory(SITE, rain_weather(), {**context, 'near_stream': False}, NOW)['active']
    assert not overnight_advisory(SITE, rain_weather(24), context, NOW)['active']
    assert overnight_advisory(SITE, {**rain_weather(), 'stale': True}, context, NOW)['active'] is None
    partial = rain_weather(); partial['hourly']['precipitation'][0] = None
    assert overnight_advisory(SITE, partial, context, NOW)['active'] is None
    assert overnight_advisory(SITE, rain_weather(), {'monitoring': 'UNAVAILABLE'}, NOW)['active'] is None


def test_context_freshness_and_failures_keep_geography_unknown():
    assert context_view({}, NOW)['status'] == 'unknown'
    record = {'fetched_at': NOW - timedelta(days=31), 'payload': {'near_stream': True}}
    assert context_view(record, NOW)['monitoring'] == 'STALE'
    record.update(fetched_at=NOW, error_code='hydrology_unavailable')
    assert context_view(record, NOW)['monitoring'] == 'STALE'


@pytest.mark.parametrize('now,start,hours,per_hour,active', [
    ('2026-11-01T16:00:00+00:00', '2026-10-31T22:00:00+00:00', 13, 2, True),
    ('2026-03-08T16:00:00+00:00', '2026-03-07T23:00:00+00:00', 11, 2.2, False),
])
def test_overnight_advisory_counts_real_hours_through_dst(now, start, hours, per_hour, active):
    origin = datetime.fromisoformat(start)
    weather = {'stale': False, 'hourly_units': {'precipitation': 'mm'},
               'hourly': {'time': [int((origin+timedelta(hours=i)).timestamp()) for i in range(1, hours+1)],
                          'precipitation': [per_hour]*hours}}
    result = overnight_advisory(SITE, weather, {'monitoring': 'COMPLETE', 'near_stream': True}, datetime.fromisoformat(now))
    assert result['active'] is active
    assert result['rainfall_mm'] == round(hours*per_hour, 2)


@pytest.mark.parametrize('miles,held', [(9, True), (10, True), (10.0001, False), (11, False)])
def test_lightning_exact_radius_boundary(miles, held):
    store = MemoryStore([SITE])
    strike = parse_strike(strike_payload('boundary', SITE, miles, NOW.isoformat()))
    process_strike(store, strike, [SITE], NOW)
    assert bool(store.get_hold(SITE['id'], 'live')) is held


def test_future_feed_heartbeat_is_not_complete_coverage():
    store = MemoryStore(SITES)
    store.record_feed('live', 'TEST', checked_at=NOW+timedelta(hours=1))
    assert coverage(store, 'live', NOW, LiveSource(lambda *_: []))['status'] == 'STALE'


def test_provider_failure_after_restart_returns_persistent_stale_cache(monkeypatch):
    record = daily_record()
    def fail(_): raise RuntimeError('provider offline')
    monkeypatch.setattr(ingestion, 'fetch_weather', fail)
    monkeypatch.setattr(db, 'record_weather_failure', lambda *_: None)
    monkeypatch.setattr(db, 'latest_weather', lambda: {663: record})
    result = ingestion.refresh_site_weather(SITE)
    assert result['stale'] is True and result['cached'] is True
    assert result['daily'] == record['payload']['daily']


def test_no_persistent_cache_keeps_upstream_failure_visible(monkeypatch):
    def fail(_): raise RuntimeError('provider offline')
    monkeypatch.setattr(ingestion, 'fetch_weather', fail)
    monkeypatch.setattr(db, 'record_weather_failure', lambda *_: None)
    monkeypatch.setattr(db, 'latest_weather', lambda: {})
    with pytest.raises(RuntimeError, match='provider offline'):
        ingestion.refresh_site_weather(SITE)


def test_rate_limit_honors_provider_cooldown_without_another_request(monkeypatch):
    import urllib.error
    import urllib.request
    calls = []
    monkeypatch.setattr(providers, '_cooldowns', {})
    def limited(*args, **kwargs):
        calls.append(True)
        raise urllib.error.HTTPError('https://fixture.invalid', 429, 'limited', {'Retry-After': '120'}, None)
    monkeypatch.setattr(providers.urllib.request, 'urlopen', limited)
    request = urllib.request.Request('https://fixture.invalid/data')
    with pytest.raises(urllib.error.HTTPError): providers.open_provider(request, timeout=1)
    with pytest.raises(RuntimeError, match='cooldown'): providers.open_provider(request, timeout=1)
    assert calls == [True]


def test_readiness_does_not_count_unavailable_prediction_records(monkeypatch):
    from backend.app import create_app
    monkeypatch.setattr('backend.app.load_dotenv', lambda *_: None)
    monkeypatch.setattr('backend.app.build_outlook', lambda *_: {'as_of': NOW.isoformat(), 'sites': [
        {'weather_monitoring': {'state': 'UNAVAILABLE'}, 'official_alerts_monitoring': {'state': 'UNAVAILABLE'},
         'prediction': {'status': 'unavailable', 'score': None}, 'model_index': None}]})
    result = create_app().test_client().get('/api/readiness?mode=demo').json
    assert result['model']['saved_next_day_predictions'] == 0
