from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image
import pytest

from backend import db, radar
from backend.app import create_app

NOW = datetime(2026, 10, 18, 8, 20, tzinfo=timezone.utc)


def raw_manifest():
    return {'host': radar.TILE_HOST, 'generated': int(NOW.timestamp()), 'radar': {'past': [
        {'time': int((NOW-timedelta(minutes=10)).timestamp()), 'path': '/v2/radar/verified-frame'},
        {'time': int(NOW.timestamp()), 'path': '/v2/radar/new-frame'}], 'nowcast': []}}


def record():
    return {'payload': radar.normalize_manifest(raw_manifest(), NOW), 'error_code': None}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr('backend.app.load_dotenv', lambda *a, **kw: None)
    monkeypatch.setattr(radar, 'utc_now', lambda: NOW)
    monkeypatch.setattr(db, 'latest_radar_feed', record)
    radar._tiles.clear()
    return create_app().test_client()


def test_metadata_uses_stored_frames_only_and_preserves_generation_times(client, monkeypatch):
    monkeypatch.setattr(radar, 'open_provider', lambda *a, **kw: pytest.fail('Metadata reads must not call providers'))
    data = client.get('/api/radar').get_json()
    assert data['status'] == 'available' and not data['stale']
    assert data['max_native_zoom'] == 7
    assert data['frames'][-1]['tile_url'] == '/api/radar/tiles/new-frame/{z}/{x}/{y}.png'
    assert data['frames'][-1]['frame_time'] == NOW.isoformat()
    assert 'not necessarily no rain' in data['note']
    assert client.get('/api/radar?mode=demo').get_json()['frames'] == []
    assert client.get('/api/radar?mode=replay').status_code == 400


@pytest.mark.parametrize('change', ['host', 'path', 'future', 'duplicate', 'empty', 'type'])
def test_malformed_manifest_cannot_control_tile_host_or_path(change):
    raw = deepcopy(raw_manifest())
    if change == 'host': raw['host'] = 'https://example.com'
    if change == 'path': raw['radar']['past'][0]['path'] = '/v2/radar/../../private'
    if change == 'future': raw['generated'] += 3600
    if change == 'duplicate': raw['radar']['past'].append(raw['radar']['past'][0])
    if change == 'empty': raw['radar']['past'] = []
    if change == 'type': raw['radar']['past'] = [42]
    with pytest.raises(ValueError): radar.normalize_manifest(raw, NOW)


def test_failure_retains_old_frames_with_stale_state(client, monkeypatch):
    saved = record()
    saved['error_code'] = 'radar_unavailable'
    monkeypatch.setattr(db, 'latest_radar_feed', lambda: saved)
    data = client.get('/api/radar').get_json()
    assert data['stale'] and data['frames']
    assert radar.radar_view(record(), NOW+timedelta(minutes=16))['stale']
    monkeypatch.setattr(db, 'latest_radar_feed', lambda: {'payload': None, 'error_code': 'radar_unavailable'})
    assert client.get('/api/radar').status_code == 502
    monkeypatch.setattr(db, 'latest_radar_feed', lambda: None)
    assert client.get('/api/radar').get_json()['status'] == 'unavailable'
    def failure(): raise db.DatabaseUnavailable('Database unavailable')
    monkeypatch.setattr(db, 'latest_radar_feed', failure)
    assert client.get('/api/radar').status_code == 503


def test_tiles_are_validated_cached_and_browser_cacheable(client, monkeypatch):
    image = BytesIO()
    Image.new('RGBA', (256, 256), (0, 0, 0, 0)).save(image, format='PNG')
    calls = []
    def fetch(request, **kwargs):
        calls.append(request.full_url)
        return BytesIO(image.getvalue())
    monkeypatch.setattr(radar, 'open_provider', fetch)
    path = '/api/radar/tiles/new-frame/7/35/54.png'
    first = client.get(path)
    assert first.status_code == 200 and first.mimetype == 'image/png'
    assert first.headers['Cache-Control'] == 'public, max-age=600'
    assert client.get(path).data == first.data and len(calls) == 1
    assert client.get(path, headers={'If-None-Match': first.headers['ETag']}).status_code == 304
    assert calls[0] == radar.TILE_HOST+'/v2/radar/new-frame/256/7/35/54/2/1_0.png'
    for invalid in ['unknown/7/35/54', 'new-frame/8/35/54', 'new-frame/7/128/54']:
        assert client.get('/api/radar/tiles/'+invalid+'.png').status_code == 404
    assert len(calls) == 1
    monkeypatch.setattr(radar, 'open_provider', lambda *a, **kw: BytesIO(b'<html>Provider error</html>'))
    assert client.get('/api/radar/tiles/new-frame/7/36/54.png').status_code == 502


def test_worker_records_failure_without_replacing_success(monkeypatch):
    writes = []
    monkeypatch.setattr(radar, 'fetch_manifest', lambda: record()['payload'])
    monkeypatch.setattr(db, 'save_radar_feed', lambda *args: writes.append('success'))
    monkeypatch.setattr(db, 'record_radar_failure', lambda *args: writes.append('failure'))
    assert radar.refresh_radar()['succeeded'] == 1
    def failure(): raise RuntimeError('Provider offline')
    monkeypatch.setattr(radar, 'fetch_manifest', failure)
    assert radar.refresh_radar()['failed'] == 1
    assert writes == ['success', 'failure']
