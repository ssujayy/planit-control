import io

import pytest

from backend.ops_store import MemoryStore
from backend.reports import PHOTO_LIMIT
from ops_support import SITES, Clock, make_client, site

DEERHAVEN = site(663)
from image_support import JPEG, PNG, WEBP


@pytest.fixture
def store():
    return MemoryStore(SITES)


@pytest.fixture
def clock():
    return Clock('2026-10-17T20:00:00+00:00')


@pytest.fixture
def client(monkeypatch, store, clock):
    return make_client(monkeypatch, store, clock)


def form(**overrides):
    data = {'site_id': '663', 'latitude': str(DEERHAVEN['latitude']), 'longitude': str(DEERHAVEN['longitude']),
            'category': 'wildlife', 'note': 'Alligator near the north culvert.'}
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def post(client, photo=JPEG, filename='photo.jpg', **overrides):
    data = form(**overrides)
    if photo is not None:
        data['photo'] = (io.BytesIO(photo), filename)
    return client.post('/api/reports', data=data, content_type='multipart/form-data')


def test_valid_upload_with_photo(client):
    response = post(client, JPEG)
    assert response.status_code == 201
    report = response.json['report']
    assert report['has_photo'] is True and report['photo_content_type'] == 'image/jpeg'
    assert report['status'] == 'unresolved' and report['event_mode'] == 'live'
    assert report['created_at'] == report['observed_at'] == '2026-10-17T20:00:00+00:00'
    assert report['location_flag'] is None


def test_photo_is_required(client):
    response = post(client, photo=None)
    assert response.status_code == 400 and 'photo is required' in response.json['error']


def test_webp_accepted(client):
    report = post(client, WEBP, filename='x.webp').json['report']
    assert report['photo_content_type'] == 'image/webp'


def test_note_is_required_and_limited(client):
    assert post(client, note='').status_code == 400
    assert post(client, note='x' * 2001).status_code == 400
    assert post(client, note='x' * 2000).status_code == 201


def test_required_and_legacy_categories(client):
    for category in ('wildlife', 'water', 'access', 'fire', 'other', 'heat', 'lightning', 'flooding', 'mud'):
        assert post(client, category=category).status_code == 201
    assert post(client, category='invalid').status_code == 400


@pytest.mark.parametrize('photo', [b'\x89PNG\r\n\x1a\n' + b'\x00'*64, JPEG[:25], PNG[:-20]])
def test_corrupt_images_rejected(client, photo):
    assert post(client, photo).status_code == 400


def test_history_filters_keep_resolved_records(client):
    first = post(client, note='Alligator near culvert').json['report']
    post(client, category='mud', note='Rutted ground')
    client.post(f"/api/reports/{first['id']}/resolve")
    filtered = client.get('/api/reports?site_id=663&category=wildlife&status=resolved&q=culvert').json
    assert [row['id'] for row in filtered['history']] == [first['id']]
    assert client.get('/api/reports?site_id=663&since=bad').status_code == 400
    assert client.get('/api/reports?site_id=663&status=bad').status_code == 400


def test_oversize_photo_rejected(client):
    response = post(client, b'\xff\xd8\xff' + b'\x00' * PHOTO_LIMIT)
    assert response.status_code == 413
    assert response.json['code'] == 'photo_too_large'


def test_wrong_type_rejected(client):
    response = post(client, b'GIF89a' + b'\x00' * 32, filename='photo.gif')
    assert response.status_code == 400


def test_empty_file_rejected(client):
    assert post(client, b'', filename='photo.jpg').status_code == 400


def test_spoofed_extension_rejected(client):
    response = post(client, b'%PDF-1.7 not an image', filename='photo.jpg')
    assert response.status_code == 400
    assert 'JPEG, PNG or WebP' in response.json['error']


@pytest.mark.parametrize('field,value', [('latitude', '95'), ('longitude', 'abc'), ('latitude', None)])
def test_bad_coordinates_rejected(client, field, value):
    assert post(client, **{field: value}).status_code == 400


def test_far_coordinates_are_flagged_not_blocked(client):
    response = post(client, latitude='30.5')
    assert response.status_code == 201
    assert response.json['report']['location_flag'] == 'far_from_site'


def test_unknown_site_and_category(client):
    assert post(client, site_id='9999999').status_code == 404
    assert post(client, site_id='abc').status_code == 400
    assert post(client, category='aliens').status_code == 400


def test_history_order_and_shared_across_clients(monkeypatch, client, store, clock):
    first = post(client, PNG, filename='a.png').json['report']
    clock.set('2026-10-17T20:05:00+00:00')
    other_device = make_client(monkeypatch, store, clock)
    second = post(other_device, category='access', note='Truck stuck at gate 2').json['report']
    payload = client.get('/api/reports?site_id=663').json
    assert [r['id'] for r in payload['history']] == [second['id'], first['id']]
    assert payload['counts'] == {'unresolved': 2, 'total': 2}
    assert all('photo' not in r for r in payload['history'])


def test_resolve_preserves_history(client, clock):
    report = post(client).json['report']
    clock.set('2026-10-17T21:00:00+00:00')
    resolved = client.post(f"/api/reports/{report['id']}/resolve").json['report']
    assert resolved['status'] == 'resolved' and resolved['resolved_at'] == '2026-10-17T21:00:00+00:00'
    clock.set('2026-10-17T22:00:00+00:00')
    again = client.post(f"/api/reports/{report['id']}/resolve").json['report']
    assert again['resolved_at'] == '2026-10-17T21:00:00+00:00'
    payload = client.get('/api/reports?site_id=663').json
    assert payload['current_unresolved'] == []
    assert [r['id'] for r in payload['history']] == [report['id']]
    assert client.post('/api/reports/nope/resolve').status_code == 404


def test_photo_retrieval_content_type(client):
    report = post(client, PNG, filename='x.jpg').json['report']
    response = client.get(report['photo_url'])
    assert response.status_code == 200
    assert response.mimetype == 'image/png'
    assert response.data == PNG
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert client.get('/api/reports/not-a-report/photo').status_code == 404


def test_reports_require_site_id(client):
    assert client.get('/api/reports').status_code == 400
    assert client.get('/api/reports?site_id=9999999').status_code == 404


def test_without_database_returns_503(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('backend.app.load_dotenv', lambda *a, **kw: None)
    from backend.app import create_app
    client = create_app().test_client()
    response = client.get('/api/reports?site_id=663')
    assert response.status_code == 503
    assert response.json['code'] == 'database_unavailable'
    assert client.get('/api/sites/663/lightning').status_code == 503


def test_unknown_api_route_still_404(client):
    assert client.get('/api/reports/abc/unknown').status_code == 404
    assert client.get('/api/lightning/nothing').status_code == 404
