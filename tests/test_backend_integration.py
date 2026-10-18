from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from types import ModuleType
import sys

import pytest

from backend import db, ingestion, outlook, worker
from backend.app import create_app


NOW = datetime(2026, 10, 17, 18, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def empty_workflow_storage(monkeypatch):
    monkeypatch.setattr(db, 'latest_official_alerts', lambda: {})
    monkeypatch.setattr(db, 'get_lightning_holds', lambda **kwargs: {})
    monkeypatch.setattr(db, 'list_crew_reports', lambda **kwargs: [])
    monkeypatch.setattr(db, 'next_day_predictions', lambda **kwargs: {})


@pytest.fixture
def site():
    return db.demo_sites()[0]


@pytest.fixture
def payload():
    stored = json.loads((db.ROOT / 'data/source_checks/weather_integration.json').read_text())['weather']
    # The current provider contract covers three UTC days, not the older 48-hour sample.
    start = NOW.replace(hour=0)
    stored['hourly']['time'] = [int((start+timedelta(hours=hour)).timestamp()) for hour in range(72)]
    for name, values in stored['hourly'].items():
        if name != 'time':
            stored['hourly'][name] = values + values[-24:]
    return {**stored, 'fetched_at': NOW.isoformat(), 'current': {**stored['current'], 'time': int(NOW.timestamp())}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('backend.app.load_dotenv', lambda *args, **kwargs: None)
    return create_app().test_client()


def test_demo_outlook_has_55_real_sites_without_provider_or_database(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('The polling endpoint must not query providers or a database in demo storage.')
    monkeypatch.setattr(db, 'latest_weather', forbidden)
    monkeypatch.setattr(ingestion, 'fetch_weather', forbidden)
    response = client.get('/api/outlook?mode=demo')
    assert response.status_code == 200
    result = response.json
    assert result['storage_mode'] == 'demo'
    assert result['event_mode'] == 'live'
    assert result['count'] == 55
    assert len({row['site']['source_plant_id'] for row in result['sites']}) == 55
    assert all(row['weather'] is None and row['hazard_state'] is None for row in result['sites'])
    assert all(row['coverage'] == 'UNAVAILABLE' for row in result['sites'])
    assert result['ranking_status'] == 'not_implemented'


def test_outlook_does_not_fallback_when_database_unconfigured(client):
    assert client.get('/api/outlook').status_code == 503


def test_outlook_rejects_invalid_storage_mode(client):
    assert client.get('/api/outlook?mode=replay').status_code == 400


@pytest.mark.parametrize('age,error_code,expected', [
    (0, None, 'COMPLETE'),
    (1800, None, 'COMPLETE'),
    (1801, None, 'STALE'),
    (-1, None, 'STALE'),
    (0, 'weather_unavailable', 'STALE'),
])
def test_outlook_freshness_and_failed_refresh(site, payload, monkeypatch, age, error_code, expected):
    fetched = NOW - timedelta(seconds=age)
    payload['fetched_at'] = fetched.isoformat()
    monkeypatch.setattr(db, 'list_sites', lambda mode: [site])
    monkeypatch.setattr(db, 'latest_weather', lambda: {site['id']: {
        'payload': payload, 'last_success_at': fetched, 'last_attempt_at': NOW, 'error_code': error_code,
    }})
    row = outlook.build_outlook('live', now=NOW)['sites'][0]
    assert row['weather_monitoring']['state'] == expected
    assert row['coverage'] == ('PARTIAL' if expected == 'COMPLETE' else 'STALE')
    assert row['weather']['stale'] is (expected == 'STALE')
    assert row['weather']['hourly'] == payload['hourly']
    assert row['weather']['current_units'] == payload['current_units']
    assert row['weather']['current_evidence_type'] == 'modeled_current_conditions'
    assert row['hazard_state'] is None
    assert 'lightning' in row['unavailable_layers']


def test_ingestion_persists_fresh_result(site, payload, monkeypatch):
    saved = []
    monkeypatch.setattr(ingestion, 'fetch_weather', lambda selected: payload)
    monkeypatch.setattr(db, 'save_weather_snapshot', lambda *args: saved.append(args))
    assert ingestion.refresh_site_weather(site) == payload
    assert saved[0][0:2] == (site['id'], payload)
    assert saved[0][2].tzinfo is not None


def test_missing_hourly_values_are_partial_and_preserved(site, payload, monkeypatch):
    payload['hourly']['soil_moisture_0_to_1cm'][0] = None
    monkeypatch.setattr(db, 'list_sites', lambda mode: [site])
    monkeypatch.setattr(db, 'latest_weather', lambda: {site['id']: {'payload': payload}})
    row = outlook.build_outlook('live', now=NOW)['sites'][0]
    assert row['weather_monitoring']['state'] == 'PARTIAL'
    assert row['weather']['hourly']['soil_moisture_0_to_1cm'][0] is None
    assert any('hourly.soil_moisture_0_to_1cm' in reason for reason in row['reasons'])


def test_old_current_valid_time_is_stale_even_if_just_retrieved(site, payload, monkeypatch):
    payload['current']['time'] = int((NOW - timedelta(hours=1)).timestamp())
    monkeypatch.setattr(db, 'list_sites', lambda mode: [site])
    monkeypatch.setattr(db, 'latest_weather', lambda: {site['id']: {'payload': payload}})
    row = outlook.build_outlook('live', now=NOW)['sites'][0]
    assert row['weather_monitoring']['state'] == 'STALE'


def test_regular_weather_rotation_bounds_work_and_visits_each_site(monkeypatch):
    monkeypatch.setattr(db, 'list_sites', lambda mode: [{'id': 1}, {'id': 2}])
    visited = []
    def refresh(*, site_ids):
        visited.extend(site_ids)
        return {'sites': 1, 'succeeded': 1, 'failed': 0}
    monkeypatch.setattr(ingestion, 'refresh_weather', refresh)
    rotation = ingestion.WeatherRotation()
    for _ in range(3):
        rotation()
    assert visited == [1, 2, 1]


def test_ingestion_does_not_turn_stale_cache_into_success(site, payload, monkeypatch):
    attempts = []
    monkeypatch.setattr(ingestion, 'fetch_weather', lambda selected: {**payload, 'stale': True})
    monkeypatch.setattr(db, 'record_weather_failure', lambda *args: attempts.append(args))
    monkeypatch.setattr(db, 'save_weather_snapshot', lambda *args: pytest.fail('Stale data must not be saved as new success.'))
    assert ingestion.refresh_site_weather(site)['stale'] is True
    assert attempts[0][0] == site['id']


def test_ingestion_continues_after_provider_failure_but_not_database_failure(monkeypatch):
    monkeypatch.setattr(db, 'list_sites', lambda mode: [{'id': 1}, {'id': 2}])
    def refresh(site):
        if site['id'] == 1:
            raise RuntimeError('Provider offline')
        return {'stale': False}
    monkeypatch.setattr(ingestion, 'refresh_site_weather', refresh)
    assert ingestion.refresh_weather() == {'sites': 2, 'succeeded': 1, 'failed': 1}
    def database_failure(site):
        raise db.DatabaseUnavailable('Database unavailable')
    monkeypatch.setattr(ingestion, 'refresh_site_weather', database_failure)
    with pytest.raises(db.DatabaseUnavailable):
        ingestion.refresh_weather()


def test_worker_runs_other_jobs_after_failure_without_logging_secret(monkeypatch, capsys):
    completed = []
    @contextmanager
    def lease():
        yield object()
    monkeypatch.setattr(db, 'worker_lease', lease)
    monkeypatch.setattr(db, 'recover_job_runs', lambda conn: 0)
    monkeypatch.setattr(db, 'start_job', lambda conn, name: name)
    monkeypatch.setattr(db, 'finish_job', lambda conn, run_id, status, summary: completed.append((run_id, status, summary)))
    def failing_job():
        raise RuntimeError('postgresql://user:PRIVATE_PASSWORD@host')
    jobs = [worker.Job('failing', failing_job, 60), worker.Job('next', lambda: {'succeeded': 1}, 60)]
    assert worker.run_worker(jobs, once=True) == 1
    assert [row[1] for row in completed] == ['failed', 'succeeded']
    assert 'PRIVATE_PASSWORD' not in capsys.readouterr().out
    assert completed[0][2]['error_code'] == 'job_failed'


def test_worker_refuses_duplicate_registered_names(monkeypatch):
    module = ModuleType('planit_test_jobs')
    module.jobs = lambda: [worker.Job('weather', lambda: {}, 60)]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with pytest.raises(ValueError, match='Duplicate'):
        worker.build_jobs(job_modules=['planit_test_jobs:jobs'])


def test_live_manual_weather_keeps_response_contract_and_persists(client, site, payload, monkeypatch):
    monkeypatch.setattr('backend.app.list_sites', lambda mode: [site])
    called = []
    def refresh(selected):
        called.append(selected['id'])
        return payload
    monkeypatch.setattr('backend.app.refresh_site_weather', refresh)
    result = client.get(f"/api/sites/{site['id']}/weather?mode=live")
    assert result.status_code == 200
    assert result.json == {'site_id': site['id'], 'site_mode': 'live', 'weather': payload}
    assert called == [site['id']]


def test_manual_weather_database_failure_is_503_not_weather_failure(client, site, monkeypatch):
    monkeypatch.setattr('backend.app.list_sites', lambda mode: [site])
    def refresh(selected):
        raise db.DatabaseUnavailable('Storage unavailable')
    monkeypatch.setattr('backend.app.refresh_site_weather', refresh)
    result = client.get(f"/api/sites/{site['id']}/weather?mode=live")
    assert result.status_code == 503
    assert result.json['code'] == 'database_unavailable'
