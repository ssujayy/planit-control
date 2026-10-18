"""Builds the docs/fixtures/ops_*.json examples by running the real endpoints.

Regenerate from the repository root:  python tests/ops_fixtures.py
Uses an in-memory store and a fixed injected clock; no database and no .env.
"""
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'docs' / 'fixtures'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


def build_responses(make_client):
    """make_client(store, clock) -> Flask test client. Returns {name: (status, json)}."""
    from backend.ops_store import MemoryStore
    from ops_support import SITES, Clock, offset_point, site

    store = MemoryStore(SITES)
    clock = Clock('2026-10-17T22:00:00+00:00')  # 6:00 PM EDT, 5:00 PM CDT
    client = make_client(store, clock)
    out = {}

    def keep(name, response):
        out[name] = (response.status_code, response.get_json())
        return response.get_json()

    keep('ops_lightning_live', client.get('/api/sites/663/lightning'))
    keep('ops_replay_session', client.post('/api/replay/sessions', json={'speed': 10}))
    clock.set('2026-10-17T22:02:00+00:00')  # replay clock +20 minutes
    keep('ops_lightning_replay_hold', client.get('/api/sites/663/lightning?event_mode=replay'))
    keep('ops_lightning_holds', client.get('/api/lightning/holds?event_mode=replay'))
    session = client.get('/api/replay/session').get_json()
    lat, lon = offset_point(site(663)['latitude'], site(663)['longitude'], 2, 90)
    keep('ops_strike_ingest', client.post('/api/lightning/strikes', json={
        'event_id': 'demo-manual-001', 'source': 'simulated-replay', 'latitude': round(lat, 5), 'longitude': round(lon, 5),
        'occurred_at': session['replay_now'], 'event_mode': 'replay'}))
    site_form = {'site_id': '663', 'latitude': '29.7601', 'longitude': '-82.3861'}
    created = keep('ops_report_created', client.post('/api/reports', content_type='multipart/form-data', data=dict(
        site_form, category='wildlife', note='Alligator seen near the north culvert.', photo=(io.BytesIO(PNG), 'gator.png'))))
    clock.set('2026-10-17T22:03:00+00:00')
    mud = client.post('/api/reports', content_type='multipart/form-data',
                      data=dict(site_form, category='mud', note='Access road rutted at gate 2.')).get_json()['report']
    clock.set('2026-10-17T22:04:00+00:00')
    keep('ops_report_resolved', client.post(f"/api/reports/{mud['id']}/resolve"))
    keep('ops_reports', client.get('/api/reports?site_id=663'))
    clock.set('2026-10-17T22:08:00+00:00')  # replay clock +80 minutes: Deerhaven hold has ended
    keep('ops_briefing_generate', client.post('/api/briefings/generate', json={'site_id': 663, 'event_mode': 'replay'}))
    client.post('/api/briefings/generate', json={'site_id': 663, 'event_mode': 'live'})
    keep('ops_briefings', client.get('/api/briefings?site_id=663'))
    timeline = {
        'replay': keep('_timeline_replay', client.get('/api/sites/663/timeline?event_mode=replay')),
        'live': keep('_timeline_live', client.get('/api/sites/663/timeline')),
        'empty': keep('_timeline_empty', client.get('/api/sites/6051/timeline')),
    }
    out['ops_timeline'] = (200, {'examples': timeline})
    errors = {
        'invalid_input_400': client.get('/api/sites/663/lightning?event_mode=demo'),
        'not_found_404': client.get('/api/reports?site_id=9999999'),
        'live_briefing_not_due_409': None,
        'photo_too_large_413': client.post('/api/reports', content_type='multipart/form-data', data=dict(
            site_form, category='other', photo=(io.BytesIO(b'\xff\xd8\xff' + b'\x00' * (5 * 1024 * 1024)), 'big.jpg'))),
    }
    clock.set('2026-10-17T22:30:00+00:00')  # 5:30 PM CDT
    errors['live_briefing_not_due_409'] = client.post('/api/briefings/generate', json={'site_id': 6072, 'event_mode': 'live'})
    out['ops_errors'] = (200, {name: {'status': r.status_code, 'body': r.get_json()} for name, r in errors.items()})
    out['ops_errors'][1]['database_unavailable_503'] = {
        'status': 503, 'body': {'error': 'DATABASE_URL is not configured. Add your Tiger Data URI to .env.', 'code': 'database_unavailable'}}
    return out


def write_fixtures(responses):
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, (status, body) in responses.items():
        if name.startswith('_'):
            continue
        doc = {'fixture': True, 'http_status': status, **body}
        (FIXTURES / f'{name}.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
    import os
    os.environ.pop('DATABASE_URL', None)
    import backend.app
    backend.app.load_dotenv = lambda *a, **kw: None

    def make(store, clock):
        app = backend.app.create_app()
        app.config.update(OPS_STORE=store, OPS_CLOCK=clock)
        return app.test_client()

    write_fixtures(build_responses(make))
    print('Wrote', ', '.join(sorted(p.name for p in FIXTURES.glob('ops_*.json'))))
