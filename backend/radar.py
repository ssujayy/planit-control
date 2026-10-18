"""RainViewer past radar: worker-refreshed metadata and bounded raster delivery."""
from collections import OrderedDict
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import re
from threading import Lock
import time
import urllib.request

from flask import Blueprint, Response, jsonify, request
from PIL import Image

from . import db
from .providers import open_provider

MANIFEST_URL = 'https://api.rainviewer.com/public/weather-maps.json'
TILE_HOST = 'https://tilecache.rainviewer.com'
FRAME_PATH = re.compile(r'^/v2/radar/([A-Za-z0-9_-]{1,80})$')
NOTE = ('Radar shows recent precipitation echoes, not a forecast or lightning detection. '
        'Frame time is generation time; pixels may represent different observation times. '
        'Blank areas may have no coverage, not necessarily no rain.')
radar_bp = Blueprint('radar', __name__)
_tiles = OrderedDict()
_tile_lock = Lock()
TILE_LIMIT = 256
TILE_TTL = 600


def utc_now():
    return datetime.now(timezone.utc)


def normalize_manifest(raw, retrieved_at):
    if not isinstance(raw, dict) or raw.get('host') != TILE_HOST:
        raise ValueError('Unexpected radar host')
    generated = raw.get('generated')
    if type(generated) is not int or generated <= 0 or generated > retrieved_at.timestamp() + 120:
        raise ValueError('Invalid radar generation time')
    radar = raw.get('radar')
    past = radar.get('past') if isinstance(radar, dict) else None
    if not isinstance(past, list) or not 1 <= len(past) <= 30:
        raise ValueError('Radar history unavailable')
    frames = []
    for frame in past:
        if not isinstance(frame, dict):
            raise ValueError('Invalid radar frame')
        at, path = frame.get('time'), frame.get('path')
        if type(at) is not int or at <= 0 or at > generated + 120 or not isinstance(path, str) or not FRAME_PATH.fullmatch(path):
            raise ValueError('Invalid radar frame')
        frames.append({'time': at, 'path': path})
    if len({f['time'] for f in frames}) != len(frames) or len({f['path'] for f in frames}) != len(frames):
        raise ValueError('Duplicate radar frames')
    frames.sort(key=lambda frame: frame['time'])
    return {'source': 'RainViewer', 'source_url': MANIFEST_URL, 'host': TILE_HOST,
            'generated': generated, 'retrieved_at': retrieved_at.isoformat(), 'frames': frames}


def fetch_manifest():
    req = urllib.request.Request(MANIFEST_URL, headers={'User-Agent': 'PlanIT-Control/0.3 (educational weather dashboard)'})
    try:
        with open_provider(req, timeout=12) as response:
            body = response.read(131073)
        if len(body) > 131072:
            raise ValueError('Oversized radar manifest')
        return normalize_manifest(json.loads(body), utc_now())
    except Exception:
        raise RuntimeError('Rain radar provider is unavailable or returned invalid data.') from None


def refresh_radar():
    attempted_at = utc_now()
    try:
        payload = fetch_manifest()
    except RuntimeError:
        db.record_radar_failure(attempted_at)
        return {'succeeded': 0, 'failed': 1}
    db.save_radar_feed(payload, attempted_at)
    return {'succeeded': 1, 'failed': 0, 'frames': len(payload['frames'])}


def radar_view(record, now):
    payload = (record or {}).get('payload')
    result = {'source': 'RainViewer', 'source_url': MANIFEST_URL, 'status': 'unavailable', 'stale': False,
              'retrieved_at': None, 'generated_at': None, 'frames': [], 'max_native_zoom': 7,
              'attribution_url': 'https://www.rainviewer.com/', 'note': NOTE}
    if not payload:
        result['reason'] = 'Rain radar is waiting for a successful worker update.'
        return result
    retrieved = db.timestamp(payload['retrieved_at'])
    frames = payload['frames']
    stale = (bool(record.get('error_code')) or not -120 <= (now - retrieved).total_seconds() <= 900
             or not -120 <= now.timestamp() - frames[-1]['time'] <= 1800)
    result.update(status='stale' if stale else 'available', stale=stale, retrieved_at=retrieved.isoformat(),
                  generated_at=datetime.fromtimestamp(payload['generated'], timezone.utc).isoformat(),
                  frames=[{'time': f['time'], 'frame_time': datetime.fromtimestamp(f['time'], timezone.utc).isoformat(),
                           'tile_url': '/api/radar/tiles/' + FRAME_PATH.fullmatch(f['path'])[1] + '/{z}/{x}/{y}.png'} for f in frames])
    if stale:
        result['reason'] = 'Radar needs an update; showing older frames.'
    return result


def tile_image(frame_id, z, x, y):
    if not (0 <= z <= 7 and 0 <= x < 2**z and 0 <= y < 2**z):
        return None
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', frame_id):
        return None
    # Only real frames in the persisted manifest can be requested; never proxy arbitrary URLs.
    record = db.latest_radar_feed()
    payload = (record or {}).get('payload') or {}
    path = '/v2/radar/' + frame_id
    if payload.get('host') != TILE_HOST or path not in {f['path'] for f in payload.get('frames', [])}:
        return None
    key = (frame_id, z, x, y)
    with _tile_lock:
        cached = _tiles.get(key)
        if cached and time.monotonic() - cached[0] < TILE_TTL:
            _tiles.move_to_end(key)
            return cached[1]
    req = urllib.request.Request(f'{TILE_HOST}{path}/256/{z}/{x}/{y}/2/1_0.png',
                                 headers={'User-Agent': 'PlanIT-Control/0.3 (educational weather dashboard)'})
    try:
        with open_provider(req, timeout=12) as response:
            body = response.read(524289)
        if len(body) > 524288 or not body.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid radar image')
        with Image.open(BytesIO(body)) as picture:
            if picture.format != 'PNG' or picture.size != (256, 256):
                raise ValueError('Invalid radar tile dimensions')
            picture.verify()
    except Exception:
        raise RuntimeError('Radar image unavailable for this area.') from None
    with _tile_lock:
        _tiles[key] = (time.monotonic(), body)
        _tiles.move_to_end(key)
        while len(_tiles) > TILE_LIMIT:
            _tiles.popitem(last=False)
    return body


@radar_bp.get('/api/radar')
def radar_metadata():
    mode = request.args.get('mode', 'live')
    if mode not in ('live', 'demo'):
        return jsonify({'error': 'mode must be live or demo'}), 400
    if mode == 'demo':
        return jsonify({**radar_view(None, utc_now()), 'reason': 'Rain radar is unavailable in file inventory mode.'})
    record = db.latest_radar_feed()
    if record and record.get('error_code') and not record.get('payload'):
        return jsonify({'error': 'Rain radar provider is unavailable.', 'code': 'radar_unavailable'}), 502
    return jsonify(radar_view(record, utc_now()))


@radar_bp.get('/api/radar/tiles/<frame_id>/<int:z>/<int:x>/<int:y>.png')
def radar_tile(frame_id, z, x, y):
    try:
        body = tile_image(frame_id, z, x, y)
    except RuntimeError as error:
        if isinstance(error, db.DatabaseUnavailable):
            raise
        return jsonify({'error': str(error), 'code': 'radar_tile_unavailable'}), 502
    if body is None:
        return jsonify({'error': 'Radar frame or tile not found'}), 404
    response = Response(body, mimetype='image/png')
    response.headers['Cache-Control'] = 'public, max-age=600'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.set_etag(hashlib.sha256(body).hexdigest())
    return response.make_conditional(request)
