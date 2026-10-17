import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from .db import ROOT, DatabaseUnavailable, connection, list_sites
from .weather import fetch_weather


def create_app():
    load_dotenv(ROOT / '.env')
    app = Flask(__name__, static_folder=None)

    @app.get('/api/health')
    def health():
        state = 'not_configured'
        if os.environ.get('DATABASE_URL'):
            try:
                with connection() as conn:
                    conn.execute('SELECT 1')
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

    @app.get('/api/sites/<int:site_id>/weather')
    def weather(site_id):
        value = mode()
        if value is None:
            return jsonify({'error': 'mode must be live or demo'}), 400
        found = next((s for s in list_sites(value) if s['id'] == site_id), None)
        if not found:
            return jsonify({'error': 'Site not found'}), 404
        try:
            return jsonify({'site_id': site_id, 'site_mode': value, 'weather': fetch_weather(found)})
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

