"""Regression tests for independent tomorrow metrics and current-day model wiring."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json

import pytest

from backend import db, ingestion, predictions, weather
from backend import outlook
from backend.planning_weather import summarize

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def full_forecast(site):
    zone = ZoneInfo(site['timezone'])
    start = datetime(2026, 10, 19, tzinfo=zone)
    return {'source': 'TEST FIXTURE', 'fetched_at': NOW.isoformat(),
            'daily_timezone': site['timezone'], 'daily_dates': ['2026-10-18', '2026-10-19'],
            'daily_units': {'precipitation_sum': 'mm'}, 'daily': {'precipitation_sum': [3, 17.5]},
            'hourly': {'time': [int((start+timedelta(hours=i)).timestamp()) for i in range(24)],
                       'temperature_2m': [30]*24, 'relative_humidity_2m': [65]*24,
                       'precipitation': [2]*24, 'soil_moisture_0_to_1cm': [.35]*24},
            'hourly_units': {'temperature_2m': '°C', 'relative_humidity_2m': '%',
                             'precipitation': 'mm', 'soil_moisture_0_to_1cm': 'm³/m³'}}


@pytest.mark.parametrize('zone', ['America/New_York', 'America/Chicago'])
def test_all_three_tomorrow_metrics_for_each_site_timezone(zone):
    site = {**db.demo_sites()[0], 'timezone': zone}
    result = summarize(full_forecast(site), site, NOW)
    assert result['precipitation_sum_mm'] == 17.5  # Provider DAILY value, not 48 mm hourly sum.
    assert result['soil_moisture_max_m3_m3'] == .35
    assert result['heat_index_max_f'] > 86
    assert all(metric['status'] == 'available' for metric in result['metrics'].values())


def test_complete_daily_rainfall_survives_missing_hourly_coverage():
    site = db.demo_sites()[0]
    payload = full_forecast(site)
    payload['hourly'] = {}
    result = summarize(payload, site, NOW)
    assert result['precipitation_sum_mm'] == 17.5
    assert result['metrics']['precipitation_sum_mm']['source'] == 'provider_daily_forecast'
    assert result['heat_index_max_f'] is None and result['soil_moisture_max_m3_m3'] is None
    assert 'expected 24 distinct hours, found 0' in result['metrics']['heat_index_max_f']['reason']


def test_one_missing_soil_value_does_not_hide_rainfall_or_heat():
    site = db.demo_sites()[0]
    payload = full_forecast(site)
    payload['hourly']['soil_moisture_0_to_1cm'][5] = None
    result = summarize(payload, site, NOW)
    assert result['precipitation_sum_mm'] == 17.5 and result['heat_index_max_f'] is not None
    assert result['soil_moisture_max_m3_m3'] is None
    assert 'soil_moisture' in result['metrics']['soil_moisture_max_m3_m3']['reason']


def test_daily_rainfall_requires_matching_local_date_timezone_and_units():
    site = db.demo_sites()[0]
    payload = full_forecast(site)
    payload['hourly'] = {}
    for change in ('date', 'timezone', 'unit', 'null'):
        invalid = deepcopy(payload)
        if change == 'date': invalid['daily_dates'] = ['2026-10-17', '2026-10-18']
        if change == 'timezone': invalid['daily_timezone'] = 'UTC'
        if change == 'unit': invalid['daily_units']['precipitation_sum'] = 'inch'
        if change == 'null': invalid['daily']['precipitation_sum'][1] = None
        assert summarize(invalid, site, NOW)['precipitation_sum_mm'] is None
    payload['daily']['precipitation_sum'][1] = 0
    assert summarize(payload, site, NOW)['precipitation_sum_mm'] == 0


def test_legacy_hourly_rainfall_excludes_previous_night_and_includes_last_hour():
    site = db.demo_sites()[0]
    payload = full_forecast(site)
    payload.pop('daily')
    payload['hourly']['time'].append(payload['hourly']['time'][-1] + 3600)
    payload['hourly']['precipitation'] = [90] + [0]*23 + [7]
    result = summarize(payload, site, NOW)
    assert result['precipitation_sum_mm'] == 7  # Midnight's 90 mm belongs to yesterday.
    assert result['metrics']['precipitation_sum_mm']['source'] == 'derived_from_hourly_forecast'


def test_worker_computes_model_before_advancing_to_next_site(monkeypatch):
    sites, events = db.demo_sites()[:2], []
    monkeypatch.setattr(db, 'list_sites', lambda mode: sites)
    def fetch(site):
        events.append(('weather', site['id']))
        return full_forecast(site)
    def predict(**kwargs):
        events.append(('model', kwargs['site_ids'][0]))
        assert kwargs['records'][kwargs['site_ids'][0]]['payload']['daily_dates']
        return {'succeeded': 2, 'failed': 0}
    monkeypatch.setattr(ingestion, 'refresh_site_weather', fetch)
    monkeypatch.setattr(predictions, 'refresh_predictions', predict)
    result = predictions.refresh_weather_and_predictions()
    assert events == [('weather', sites[0]['id']), ('model', sites[0]['id']),
                      ('weather', sites[1]['id']), ('model', sites[1]['id'])]
    assert result['predictions_succeeded'] == 4


def test_provider_snapshot_contains_recorded_tomorrow_rainfall(monkeypatch):
    site = db.demo_sites()[0]
    raw = full_forecast(site)
    raw['daily']['time'] = [int(datetime(2026, 10, day, tzinfo=ZoneInfo(site['timezone'])).timestamp()) for day in (18, 19)]
    raw['timezone'] = site['timezone']
    raw['current'] = {'temperature_2m': 25}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps(raw).encode()
    monkeypatch.setattr(weather, '_cache', {})
    monkeypatch.setattr(weather, 'open_provider', lambda *args, **kwargs: Response())
    class ProviderClock(datetime):
        @classmethod
        def now(cls, tz=None): return NOW.astimezone(tz or timezone.utc)
    monkeypatch.setattr(weather, 'datetime', ProviderClock)
    result = weather.fetch_weather(site)
    assert result['planning_weather']['target_date'] == '2026-10-19'
    assert result['planning_weather']['precipitation_sum_mm'] == 17.5


def test_prediction_written_during_dashboard_read_is_not_mistaken_for_future_data(monkeypatch):
    site = db.demo_sites()[0]
    clock = [NOW]
    class RequestClock(datetime):
        @classmethod
        def now(cls, tz=None): return clock[0]
    monkeypatch.setattr(outlook, 'datetime', RequestClock)
    monkeypatch.setattr(db, 'list_sites', lambda mode: [site])
    monkeypatch.setattr(db, 'latest_weather', lambda: {})
    monkeypatch.setattr(db, 'latest_official_alerts', lambda: {})
    monkeypatch.setattr(db, 'get_lightning_holds', lambda **kwargs: {})
    monkeypatch.setattr(db, 'list_crew_reports', lambda **kwargs: [])
    prediction = {'computed_at': NOW+timedelta(seconds=1), 'score': 4.25, 'status': 'available'}
    monkeypatch.setattr(db, 'next_day_predictions', lambda **kwargs: {site['id']: prediction})
    monkeypatch.setattr(db, 'daily_predictions', lambda **kwargs: {site['id']: prediction})
    def last_query():
        clock[0] = NOW+timedelta(seconds=2)
        return {}
    monkeypatch.setattr(db, 'latest_hydrology', last_query)
    row = outlook.build_outlook('live')['sites'][0]
    assert row['current_model_index'] == 4.25 and row['model_index'] == 4.25
    assert row['current_prediction']['stale'] is False
