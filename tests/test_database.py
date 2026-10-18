"""Opt-in PostgreSQL checks; fixtures and schema are rolled back, not retained."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import uuid
import base64

from dotenv import load_dotenv
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from backend import db

pytestmark = pytest.mark.database


@pytest.fixture
def isolated_database(monkeypatch):
    load_dotenv(db.ROOT / '.env')
    with db.connection() as conn:
        with conn.transaction(force_rollback=True):
            schema = sql.Identifier('planit_test_' + uuid.uuid4().hex)
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(schema))
            conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(schema))
            @contextmanager
            def isolated_connection(**kwargs):
                yield conn
            monkeypatch.setattr(db, 'connection', isolated_connection)
            yield conn


def weather_payload():
    payload = json.loads((db.ROOT / 'data/source_checks/weather_integration.json').read_text())['weather']
    return {**payload, 'fetched_at': datetime.now(timezone.utc).isoformat()}


def test_migrations_and_seed_are_repeatable(isolated_database):
    assert db.migrate() == ['001_weather_worker.sql', '002_workflow_storage.sql', '003_operational_events.sql', '004_compliance.sql', '005_hydrology_context.sql']
    assert db.migrate() == []
    assert db.seed_sites() == 55
    assert db.seed_sites() == 55
    sites = db.list_sites('live')
    assert len({site['source_plant_id'] for site in sites}) == 55
    assert {site['source_plant_id'] for site in sites} == {site['source_plant_id'] for site in db.demo_sites()}


def test_crew_lightning_route_persists_across_app_instances(isolated_database, monkeypatch):
    from backend.app import create_app
    from backend.ops_store import PostgresStore
    from backend.briefings import run_due_briefings
    db.migrate()
    db.seed_sites()
    now = datetime(2026, 10, 17, 22, tzinfo=timezone.utc)
    monkeypatch.setattr('backend.app.load_dotenv', lambda *a, **kw: None)
    app = create_app()
    app.config.update(OPS_CLOCK=lambda: now, OPS_OUTLOOK=lambda at: None)
    client = app.test_client()
    path = '/api/sites/663/lightning/observations'
    assert client.post(path, json={'observed': True, 'event_id': 'isolated-observation'}).status_code == 201
    assert client.post(path, json={'observed': True, 'event_id': 'isolated-observation'}).status_code == 200
    restarted = create_app()
    restarted.config.update(OPS_CLOCK=lambda: now, OPS_OUTLOOK=lambda at: None)
    history = restarted.test_client().get(path).get_json()
    assert history['count'] == 1 and history['events'][0]['source'] == 'crew-observed'
    assert PostgresStore().get_hold(663, 'live')['hold_until'] == now + timedelta(minutes=30)
    assert PostgresStore().get_hold(663, 'replay') is None
    # The same scheduled function saves the new display once, including today's observation.
    store = PostgresStore()
    plant = store.get_site(663)
    assert run_due_briefings(now, store, sites=[plant])[0]['created'] is True
    assert run_due_briefings(now, store, sites=[plant]) == []
    record = PostgresStore().list_briefings(663, 'live')[0]
    assert record['display']['target_date'] == '2026-10-18'
    assert 'Lightning was recorded today.' in ' '.join(record['display']['attention'])
    assert record['generated_at'] == now.isoformat()


def test_applied_migration_changes_are_rejected(isolated_database):
    db.migrate()
    isolated_database.execute("UPDATE schema_migrations SET checksum = 'changed'")
    with pytest.raises(RuntimeError, match='has changed'):
        db.migrate()


def test_snapshots_are_idempotent_and_failure_preserves_last_success(isolated_database):
    db.migrate()
    db.seed_sites()
    site_id = db.demo_sites()[0]['id']
    payload = weather_payload()
    now = datetime.now(timezone.utc)
    db.save_weather_snapshot(site_id, payload, now)
    db.save_weather_snapshot(site_id, payload, now)
    assert isolated_database.execute('SELECT count(*) AS count FROM weather_snapshots').fetchone()['count'] == 1
    db.record_weather_failure(site_id, now + timedelta(seconds=1))
    # A delayed successful write must not clear the newer failure.
    db.save_weather_snapshot(site_id, payload, now - timedelta(seconds=1))
    record = db.latest_weather()[site_id]
    assert record['payload']['current'] == payload['current']
    assert record['last_success_at'].isoformat() == payload['fetched_at']
    assert record['error_code'] == 'weather_unavailable'
    db.record_weather_failure(site_id, now - timedelta(seconds=2))
    assert db.latest_weather()[site_id]['last_attempt_at'] == now + timedelta(seconds=1)


def test_replay_weather_cannot_replace_live_weather(isolated_database):
    db.migrate()
    db.seed_sites()
    site_id = db.demo_sites()[0]['id']
    payload = weather_payload()
    now = datetime.now(timezone.utc)
    db.save_weather_snapshot(site_id, payload, now)
    replay = {**payload, 'source': 'REPLAY_ONLY', 'fetched_at': (now + timedelta(days=1)).isoformat()}
    isolated_database.execute('''INSERT INTO weather_snapshots
        (site_id, event_mode, source, fetched_at, payload) VALUES (%s, 'replay', %s, %s, %s)''',
        (site_id, replay['source'], now + timedelta(days=1), Jsonb(replay)))
    record = db.latest_weather()[site_id]
    assert record['payload']['source'] == 'Open-Meteo'
    assert isolated_database.execute('SELECT count(*) AS count FROM weather_snapshots').fetchone()['count'] == 2


def test_worker_restart_marks_abandoned_runs_failed(isolated_database):
    db.migrate()
    interrupted = db.start_job(isolated_database, 'weather')
    complete = db.start_job(isolated_database, 'model')
    db.finish_job(isolated_database, complete, 'succeeded', {'succeeded': 1})
    assert db.recover_job_runs(isolated_database) == 1
    row = isolated_database.execute('SELECT status, summary FROM worker_runs WHERE id = %s', (interrupted,)).fetchone()
    assert row == {'status': 'failed', 'summary': {'error_code': 'worker_interrupted'}}
    assert db.recover_job_runs(isolated_database) == 0


def test_worker_lock_excludes_second_connection_and_releases(monkeypatch):
    load_dotenv(db.ROOT / '.env')
    # Separate lock namespace avoids interacting with any real running worker.
    monkeypatch.setattr(db, 'WORKER_LOCK', uuid.uuid4().int % (2 ** 63 - 1))
    with db.worker_lease():
        with pytest.raises(db.WorkerAlreadyRunning):
            with db.worker_lease():
                pytest.fail('A second connection acquired the lease.')
    with db.worker_lease():
        pass


def test_lightning_storage_deduplicates_extends_and_isolates_replay(isolated_database):
    db.migrate()
    db.seed_sites()
    site_id = db.demo_sites()[0]['id']
    now = datetime.now(timezone.utc)
    strike = dict(source='repository-test', event_id='first', occurred_at=now,
                  latitude=29.7592, longitude=-82.3878, affected_site_ids=[site_id], mode='live')
    assert db.store_lightning_event(**strike)['accepted'] is True
    assert db.store_lightning_event(**strike)['accepted'] is False
    db.store_lightning_event(**{**strike, 'event_id': 'older', 'occurred_at': now-timedelta(minutes=5)})
    assert db.get_lightning_holds(mode='live')[site_id]['hold_until'] == now+timedelta(minutes=30)
    db.store_lightning_event(**{**strike, 'event_id': 'later', 'occurred_at': now+timedelta(minutes=5)})
    assert db.get_lightning_holds(mode='live')[site_id]['hold_until'] == now+timedelta(minutes=35)
    db.store_lightning_event(**{**strike, 'mode': 'replay', 'occurred_at': now+timedelta(days=1)})
    assert db.get_lightning_holds(mode='live')[site_id]['hold_until'] == now+timedelta(minutes=35)
    assert db.get_lightning_holds(mode='replay')[site_id]['hold_until'] == now+timedelta(days=1, minutes=30)
    with pytest.raises(ValueError):
        db.store_lightning_event(**{**strike, 'event_id': 'bad', 'mode': 'demo'})


def test_report_photo_and_history_are_stored_together_and_mode_filtered(isolated_database):
    db.migrate()
    db.seed_sites()
    photo = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=')
    report_id = db.save_crew_report(site_id=663, latitude=29.7592, longitude=-82.3878,
        category='wildlife', note='Repository test only', observed_at=datetime.now(timezone.utc),
        photo=photo, photo_content_type='image/png', mode='replay')
    assert db.list_crew_reports(site_id=663, mode='live') == []
    history = db.list_crew_reports(site_id=663, mode='replay')
    assert history[0]['id'] == report_id
    assert 'photo' not in history[0]
    assert db.get_report_photo(report_id, mode='live') is None
    assert db.get_report_photo(report_id, mode='replay')['photo'] == photo


def test_briefing_storage_is_idempotent_by_local_delivery_day(isolated_database):
    db.migrate()
    db.seed_sites()
    arguments = dict(site_id=663, delivery_local_date='2026-10-17', target_date='2026-10-18',
                     body='Repository test only', facts={'missing': ['lightning']}, mode='live')
    first = db.save_briefing(**arguments)
    assert db.save_briefing(**arguments) == first
    assert len(db.list_briefings(site_id=663, mode='live')) == 1
    assert db.save_briefing(**{**arguments, 'mode': 'replay'}) != first
    with pytest.raises(ValueError):
        db.save_briefing(**{**arguments, 'target_date': '2026-10-17'})


def test_prediction_storage_requires_real_artifact_provenance_and_local_target_day(isolated_database):
    db.migrate()
    db.seed_sites()
    now = datetime(2026, 10, 18, 1, tzinfo=timezone.utc)  # Still October 17 at this site.
    arguments = dict(site_id=663, valid_date='2026-10-18', model_version='repository-test',
        feature_version='test-v1', score=7.5, computed_at=now,
        provenance={'model_artifact': 'test-only—not a production model'}, mode='replay')
    db.save_prediction(**arguments)
    assert db.next_day_predictions(now=now, mode='live') == {}
    assert db.next_day_predictions(now=now, mode='replay')[663]['score'] == 7.5
    db.save_prediction(**{**arguments, 'score': 1, 'computed_at': now-timedelta(hours=1)})
    assert db.next_day_predictions(now=now, mode='replay')[663]['score'] == 7.5
    for invalid in (float('nan'), float('inf'), -1, 11, True):
        with pytest.raises(ValueError):
            db.save_prediction(**{**arguments, 'score': invalid})
    with pytest.raises(ValueError):
        db.save_prediction(**{**arguments, 'provenance': {}})


def test_official_refresh_failure_retains_last_alert_snapshot(isolated_database):
    db.migrate()
    db.seed_sites()
    now = datetime.now(timezone.utc)
    payload = {'fetched_at': now.isoformat(), 'source': 'National Weather Service', 'alerts': []}
    db.save_official_alerts(663, payload, now)
    db.record_official_alert_failure(663, now+timedelta(seconds=1))
    db.save_official_alerts(663, payload, now-timedelta(seconds=1))
    record = db.latest_official_alerts()[663]
    assert record['payload'] == payload
    assert record['error_code'] == 'official_alerts_unavailable'


def test_unavailable_predictions_and_hydrology_survive_new_repository_reads(isolated_database):
    db.migrate()
    db.seed_sites()
    now = datetime.now(timezone.utc)
    db.save_prediction(site_id=663, valid_date=now.date(), model_version='unavailable',
                       feature_version='daily-weather-v1', score=None, computed_at=now,
                       provenance={'model_artifact': 'ml/artifacts/model.joblib', 'reason': 'Missing forecast'},
                       mode='live', status='unavailable')
    row = isolated_database.execute('SELECT status, score, probability FROM model_predictions').fetchone()
    assert row == {'status': 'unavailable', 'score': None, 'probability': None}
    context = {'source': 'TEST FIXTURE', 'near_stream': True}
    db.save_hydrology(663, now, context)
    db.save_hydrology(663, now+timedelta(seconds=1), None)
    retained = db.latest_hydrology()[663]
    assert retained['payload'] == context
    assert retained['error_code'] == 'hydrology_unavailable'


def test_photo_report_is_shared_across_app_instances_and_survives_resolution(isolated_database, monkeypatch):
    import io
    from backend.app import create_app
    from image_support import PNG
    db.migrate()
    db.seed_sites()
    monkeypatch.setattr('backend.app.load_dotenv', lambda *_: None)
    first = create_app().test_client()
    created = first.post('/api/reports', data={'site_id': '663', 'latitude': '29.76', 'longitude': '-82.39',
                          'category': 'mud', 'note': 'TEST FIXTURE wet road', 'photo': (io.BytesIO(PNG), 'road.png')})
    assert created.status_code == 201
    report = created.json['report']
    second = create_app().test_client()
    assert second.get(report['photo_url']).data == PNG
    assert second.post(f"/api/reports/{report['id']}/resolve").json['report']['status'] == 'resolved'
    restarted = create_app().test_client()
    history = restarted.get('/api/reports?site_id=663&status=resolved&category=mud').json
    assert [row['id'] for row in history['history']] == [report['id']]
