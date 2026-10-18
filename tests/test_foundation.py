import pytest
from backend.app import create_app
from backend import weather


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('backend.app.load_dotenv', lambda *a, **kw: None)
    return create_app().test_client()


def test_live_without_database_does_not_silently_use_demo(client):
    response = client.get('/api/sites')
    assert response.status_code == 503
    assert response.json['code'] == 'database_unavailable'


def test_real_plants_are_distinct_and_explicitly_demo(client):
    response = client.get('/api/sites?mode=demo')
    assert response.status_code == 200
    payload = response.json
    assert payload['mode'] == 'demo'
    assert len(payload['sites']) >= 50
    assert len({s['source_plant_id'] for s in payload['sites']}) == len(payload['sites'])
    assert all(-90 <= s['latitude'] <= 90 and -180 <= s['longitude'] <= 180 for s in payload['sites'])
    assert payload['risk_status'] == 'not_implemented'


def test_unknown_site_returns_404(client):
    assert client.get('/api/sites/9999999?mode=demo').status_code == 404


def test_invalid_mode_rejected(client):
    assert client.get('/api/sites?mode=other').status_code == 400


def test_failed_weather_is_unavailable_not_safe(client, monkeypatch):
    site_id = client.get('/api/sites?mode=demo').json['sites'][0]['id']
    def unavailable(site):
        raise RuntimeError('Provider unavailable')
    monkeypatch.setattr('backend.app.fetch_weather', unavailable)
    response = client.get(f'/api/sites/{site_id}/weather?mode=demo')
    assert response.status_code == 502
    assert response.json['code'] == 'weather_unavailable'


def test_cached_weather_is_marked_stale_after_refresh_failure(monkeypatch):
    key = (29.0, -82.0, 'America/New_York')
    weather._cache[key] = {'cached_at': -1000000, 'payload': {'source': 'Open-Meteo', 'current': {'temperature_2m': 22}}}
    def fail(*a, **kw):
        raise OSError('offline')
    monkeypatch.setattr(weather.urllib.request, 'urlopen', fail)
    result = weather.fetch_weather({'latitude': key[0], 'longitude': key[1], 'timezone': key[2]})
    assert result['stale'] is True
    assert result['current']['temperature_2m'] == 22
    weather._cache.pop(key)

