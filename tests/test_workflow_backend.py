from datetime import datetime, timedelta, timezone
import json

import pytest

from backend import db, official_alerts, outlook
from backend.app import create_app
from backend.planning_weather import heat_index_f, summarize

NOW = datetime(2026, 10, 17, 18, tzinfo=timezone.utc)


def alert(event='Flood Warning', severity='Severe', expires=None):
    return {'id': 'verified-fixture', 'event': event, 'severity': severity,
            'effective': (NOW - timedelta(hours=1)).isoformat(),
            'expires': (expires or NOW + timedelta(hours=1)).isoformat(),
            'source': 'National Weather Service', 'evidence_type': 'official_warning'}


def configure(monkeypatch, *, official=None, holds=None, reports=None, predictions=None):
    sites = db.demo_sites()[:2]
    monkeypatch.setattr(db, 'list_sites', lambda mode: sites)
    monkeypatch.setattr(db, 'latest_weather', lambda: {})
    monkeypatch.setattr(db, 'latest_official_alerts', lambda: official or {})
    monkeypatch.setattr(db, 'get_lightning_holds', lambda **kwargs: holds or {})
    monkeypatch.setattr(db, 'list_crew_reports', lambda **kwargs: reports or [])
    monkeypatch.setattr(db, 'next_day_predictions', lambda **kwargs: predictions or {})
    monkeypatch.setattr(db, 'daily_predictions', lambda **kwargs: {})
    monkeypatch.setattr(db, 'latest_hydrology', lambda: {})
    return sites


def official_record(alerts, *, failed=False):
    return {'payload': {'fetched_at': NOW.isoformat(), 'alerts': alerts},
            'error_code': 'official_alerts_unavailable' if failed else None}


def test_failed_official_refresh_retains_unexpired_warning(monkeypatch):
    site = db.demo_sites()[0]
    configure(monkeypatch, official={site['id']: official_record([alert()], failed=True)})
    row = outlook.build_outlook('live', now=NOW)['sites'][0]
    assert row['site']['id'] == site['id']
    assert row['hazard_state'] == 'ALERT'
    assert row['official_alerts_monitoring']['state'] == 'STALE'
    assert row['coverage'] == 'STALE'
    assert row['alerts'][0]['hazard'] == 'flood'


def test_expiring_hold_does_not_clear_official_warning(monkeypatch):
    site = db.demo_sites()[0]
    configure(monkeypatch, official={site['id']: official_record([alert()])},
              holds={site['id']: {'hold_until': NOW, 'last_strike_at': NOW-timedelta(minutes=30), 'source': 'fixture'}})
    row = next(row for row in outlook.build_outlook('live', now=NOW)['sites'] if row['site']['id'] == site['id'])
    assert row['lightning_hold'] is None
    assert row['hazard_state'] == 'ALERT'
    assert 'lightning' in row['unavailable_layers']


def test_active_hold_ranks_above_high_model_score(monkeypatch):
    first, second = db.demo_sites()[:2]
    configure(monkeypatch, holds={first['id']: {
        'hold_until': NOW+timedelta(minutes=20), 'last_strike_at': NOW-timedelta(minutes=10), 'source': 'fixture'}},
        predictions={second['id']: {'score': 10, 'valid_date': NOW.date()+timedelta(days=1),
                                  'model_version': 'fixture-only', 'feature_version': 'fixture', 'computed_at': NOW}})
    rows = outlook.build_outlook('live', now=NOW)['sites']
    assert rows[0]['site']['id'] == first['id']
    assert rows[0]['hazard_state'] == 'STOP_WORK'
    assert rows[0]['lightning_hold']['seconds_remaining'] == 1200
    assert rows[1]['model_index'] == 10
    assert rows[1]['prediction']['valid_date'] == '2026-10-18'


def test_fire_weather_does_not_claim_active_fire_detection(monkeypatch):
    site = db.demo_sites()[0]
    configure(monkeypatch, official={site['id']: official_record([alert('Red Flag Warning')])})
    row = outlook.build_outlook('live', now=NOW)['sites'][0]
    assert row['alerts'][0]['hazard'] == 'fire_weather'
    assert 'wildfire' in row['unavailable_layers']
    assert row['river_proximity']['status'] == 'unknown'


def test_severe_watch_does_not_outrank_severe_warning(monkeypatch):
    first, second = db.demo_sites()[:2]
    configure(monkeypatch, official={first['id']: official_record([alert('Flood Watch')]),
                                    second['id']: official_record([alert('Flood Warning')])})
    assert outlook.build_outlook('live', now=NOW)['sites'][0]['site']['id'] == second['id']


def test_expired_official_alert_is_not_active(monkeypatch):
    site = db.demo_sites()[0]
    configure(monkeypatch, official={site['id']: official_record([alert(expires=NOW)])})
    row = next(row for row in outlook.build_outlook('live', now=NOW)['sites'] if row['site']['id'] == site['id'])
    assert row['alerts'] == []
    assert row['hazard_state'] == 'NO_ACTIVE_ALERTS'
    assert row['coverage'] == 'PARTIAL'


def test_heat_index_uses_nws_formula_and_missing_inputs_stay_missing():
    assert heat_index_f(90, 70) == pytest.approx(105.9, abs=.1)
    assert heat_index_f(95, 60) == pytest.approx(113.1, abs=.1)
    assert heat_index_f(100, 10) == pytest.approx(94.1, abs=.1)
    assert heat_index_f(None, 70) is None
    assert heat_index_f(90, 101) is None


def forecast(times):
    count = len(times)
    return {'source': 'fixture', 'hourly': {'time': times, 'temperature_2m': [32.222222]*count,
            'relative_humidity_2m': [70]*count, 'precipitation': [1]*count,
            'soil_moisture_0_to_1cm': [.4]*count},
            'hourly_units': {'temperature_2m': '°C', 'relative_humidity_2m': '%',
            'precipitation': 'mm', 'soil_moisture_0_to_1cm': 'm³/m³'}}


def test_local_day_summary_requires_all_hours_and_correct_units():
    site = db.demo_sites()[0]
    start = datetime(2026, 10, 18, 4, tzinfo=timezone.utc)
    times = [int((start+timedelta(hours=hour)).timestamp()) for hour in range(25)]
    data = forecast(times)
    result = summarize(data, site, NOW)
    assert result['heat_index_max_f'] == pytest.approx(105.9, abs=.1)
    assert result['precipitation_sum_mm'] == 24
    assert result['soil_moisture_max_m3_m3'] == .4
    data['hourly_units']['precipitation'] = 'inch'
    assert summarize(data, site, NOW)['precipitation_sum_mm'] is None
    assert summarize(forecast(times[1:]), site, NOW)['heat_index_max_f'] is None
    assert summarize({'hourly': ['invalid'], 'hourly_units': None}, site, NOW)['heat_index_max_f'] is None


@pytest.mark.parametrize('now,start,hours', [
    (datetime(2026, 10, 31, 18, tzinfo=timezone.utc), datetime(2026, 11, 1, 4, tzinfo=timezone.utc), 25),
    (datetime(2026, 3, 7, 18, tzinfo=timezone.utc), datetime(2026, 3, 8, 5, tzinfo=timezone.utc), 23),
])
def test_daylight_saving_day_is_not_forced_into_24_hours(now, start, hours):
    site = db.demo_sites()[0]
    times = [int((start+timedelta(hours=hour)).timestamp()) for hour in range(hours+1)]
    assert summarize(forecast(times), site, now)['precipitation_sum_mm'] == hours


def test_provider_parses_verified_sample_and_discards_test_alerts(monkeypatch):
    sample = json.loads((db.ROOT/'data/source_checks/nws_alert_sample.json').read_text(encoding='utf-8'))['sample']
    collection = {'type': 'FeatureCollection', 'features': [sample], 'updated': NOW.isoformat()}
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps(collection).encode()
    monkeypatch.setattr(official_alerts.urllib.request, 'urlopen', lambda *args, **kwargs: Response())
    result = official_alerts.fetch_official_alerts(db.demo_sites()[0])
    assert result['alerts'][0]['event'] == sample['properties']['event']
    sample['properties']['status'] = 'Test'
    assert official_alerts.fetch_official_alerts(db.demo_sites()[0])['alerts'] == []


def test_cached_read_endpoints_do_not_contact_providers(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr('backend.app.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setattr(official_alerts.urllib.request, 'urlopen', lambda *args, **kwargs: pytest.fail('Read endpoint fetched a provider.'))
    client = create_app().test_client()
    assert client.get('/api/readiness').json['requirements_complete'] is False
    result = client.get('/api/sites/663/evidence')
    assert result.status_code == 200
    assert result.json['evidence']['site']['id'] == 663
    assert client.get('/api/sites/999999/evidence').status_code == 404
