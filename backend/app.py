import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from .db import ROOT, DatabaseUnavailable, check_database, list_sites
from .ingestion import refresh_site_weather
from .outlook import build_outlook
from .weather import fetch_weather


def create_app():
    load_dotenv(ROOT / '.env')
    app = Flask(__name__, static_folder=None)

    @app.get('/api/health')
    def health():
        state = 'not_configured'
        if os.environ.get('DATABASE_URL'):
            try:
                check_database()
                state = 'connected'
            except DatabaseUnavailable:
                state = 'unavailable'
        return jsonify({'application': 'ready', 'database': state, 'as_of': datetime.now(timezone.utc).isoformat()})

    def mode():
        value = request.args.get('mode', 'live')
        return value if value in ('live', 'demo') else None

    @app.errorhandler(DatabaseUnavailable)
    def database_error(error):
        return jsonify({'error': str(error), 'code': 'database_unavailable'}), 503

    @app.get('/api/sites')
    def sites():
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        rows = list_sites(value)
        return jsonify({'mode': value, 'sites': rows, 'count': len(rows), 'risk_status': 'not_implemented', 'as_of': datetime.now(timezone.utc).isoformat()})

    @app.get('/api/sites/<int:site_id>')
    def site(site_id):
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        found = next((s for s in list_sites(value) if s['id'] == site_id), None)
        if not found:
            return jsonify({'error': 'Site not found'}), 404
        return jsonify({'mode': value, 'site': found, 'alerts': None, 'model_index': None, 'implementation': 'foundation'})

    @app.get('/api/outlook')
    def outlook():
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        return jsonify(build_outlook(value))

    @app.get('/api/sites/<int:site_id>/evidence')
    def site_evidence(site_id):
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        result = build_outlook(value)
        found = next((row for row in result['sites'] if row['site']['id'] == site_id), None)
        if found is None:
            return jsonify({'error': 'Site not found'}), 404
        return jsonify({'storage_mode': value, 'event_mode': 'live', 'as_of': result['as_of'], 'evidence': found})

    @app.get('/api/readiness')
    def readiness():
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        result = build_outlook(value)
        rows = result['sites']
        return jsonify({
            'storage_mode': value, 'event_mode': 'live', 'as_of': result['as_of'],
            'plant_count': len(rows), 'requirements_complete': False,
            'weather_fresh_sites': sum(row['weather_monitoring']['state'] == 'COMPLETE' for row in rows),
            'official_alerts_fresh_sites': sum(row['official_alerts_monitoring']['state'] == 'COMPLETE' for row in rows),
            'lightning': {'storage_ready': True, 'live_feed_connected': False},
            'reports': {'storage_ready': True, 'upload_api_implemented': False},
            'briefings': {'storage_ready': True, 'scheduled_delivery_implemented': False},
            'model': {'storage_ready': True, 'saved_next_day_predictions': sum(row['prediction'] is not None for row in rows)},
            'limitations': ['No verified river proximity or river gauge feed.',
                            'Fire-weather warnings are not active-fire detections.',
                            'Official alerts are polled; there is no live strike provider yet.'],
        })

    @app.get('/api/sites/<int:site_id>/weather')
    def weather(site_id):
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        found = next((s for s in list_sites(value) if s['id'] == site_id), None)
        if not found:
            return jsonify({'error': 'Site not found'}), 404
        try:
            payload = refresh_site_weather(found) if value == 'live' else fetch_weather(found)
            return jsonify({'site_id': site_id, 'site_mode': value, 'weather': payload})
        except DatabaseUnavailable:
            raise
        except RuntimeError as error:
            return jsonify({'error': str(error), 'code': 'weather_unavailable'}), 502

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path='index.html'):
        dist = ROOT / 'frontend' / 'dist'
        if path.startswith('api/'):
            return jsonify({'error': 'Endpoint not implemented'}), 404
        if not (dist / 'index.html').exists():
            return jsonify({'application': 'ready', 'frontend': 'Run npm run dev in frontend or build the frontend first.'})
        target = (dist / path).resolve()
        if not target.is_relative_to(dist.resolve()):
            return jsonify({'error': 'Invalid path'}), 400
        return send_from_directory(dist, path if target.is_file() else 'index.html')

    return app

