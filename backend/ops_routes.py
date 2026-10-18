"""HTTP routes for Workstream B. Contract: docs/API_CONTRACT.md, "Operational events (proposed, Workstream B)".

No SQL here; persistence goes through the OpsStore. app.config['OPS_STORE'] and
app.config['OPS_CLOCK'] may be injected (tests); otherwise the shared PostgresStore
and the server clock are used. A missing database returns 503 via the app handler.
"""
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from . import replay
from .briefings import deliver_briefing, due_date, site_local, store_inputs_provider
from .lightning import HOLD_MINUTES, RADIUS_MILES, STATUS_NOTE, LiveSource, coverage, hold_view, lightning_status, parse_strike, process_strike
from .ops_common import REPLAY_LABEL, ValidationError, iso, mode_label, parse_event_mode, utc_now
from .ops_store import PostgresStore
from .reports import PHOTO_LIMIT, PhotoTooLarge, create_report, resolve_report, site_history
from .timeline import site_timeline

ops_bp = Blueprint('ops', __name__)


def _store():
    store = current_app.config.get('OPS_STORE')
    if store is None:
        store = current_app.config['OPS_STORE'] = PostgresStore()
    return store


def _now():
    clock = current_app.config.get('OPS_CLOCK')
    return clock() if clock else utc_now()


def _live_source():
    return current_app.config.get('OPS_LIVE_SOURCE') or LiveSource()


def with_store(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        store = _store()
        with store.batch():
            return view(store, *args, **kwargs)
    return wrapper


def _not_found(what):
    return jsonify({'error': f'{what} not found', 'code': 'not_found'}), 404


def _event_mode():
    return parse_event_mode(request.args.get('event_mode'))


def _clock_for(store, event_mode):
    """Server clock for live; the single replay clock (after syncing scripted strikes) for replay."""
    wall = _now()
    if event_mode != 'replay':
        return wall, None
    session, now = replay.sync(store, wall, store.list_sites())
    return (now, session) if session else (wall, None)


def _site_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError('site_id must be an integer') from None


@ops_bp.errorhandler(ValidationError)
def invalid_input(error):
    if isinstance(error, PhotoTooLarge):
        return jsonify({'error': str(error), 'code': 'photo_too_large'}), 413
    return jsonify({'error': str(error), 'code': 'invalid_input'}), 400


@ops_bp.errorhandler(RequestEntityTooLarge)
def too_large(error):
    return jsonify({'error': 'photo must be 5 MB or smaller', 'code': 'photo_too_large'}), 413


# Lightning

@ops_bp.get('/api/sites/<int:site_id>/lightning')
@with_store
def site_lightning(store, site_id):
    event_mode = _event_mode()
    site = store.get_site(site_id)
    if not site:
        return _not_found('Site')
    now, session = _clock_for(store, event_mode)
    return jsonify(lightning_status(store, site, event_mode, now, _live_source(), session))


@ops_bp.get('/api/lightning/holds')
@with_store
def active_holds(store):
    event_mode = _event_mode()
    now, session = _clock_for(store, event_mode)
    sites = {s['id']: s for s in store.list_sites()}
    holds = [hold_view(h, now, sites.get(h['site_id'])) for h in store.list_holds(event_mode) if h['hold_until'] > now]
    holds.sort(key=lambda h: h['hold_until'], reverse=True)
    return jsonify({'event_mode': event_mode, 'label': mode_label(event_mode), 'as_of': iso(now),
                    'coverage': coverage(store, event_mode, now, _live_source(), session),
                    'radius_miles': RADIUS_MILES, 'hold_minutes': HOLD_MINUTES, 'holds': holds, 'count': len(holds),
                    'note': STATUS_NOTE})


@ops_bp.post('/api/lightning/strikes')
@with_store
def ingest_strike(store):
    strike = parse_strike(request.get_json(silent=True))
    if strike['event_mode'] != 'replay':
        raise ValidationError('Only event_mode "replay" strikes can be posted over HTTP. Live strikes come only from a configured live feed.')
    now, session = _clock_for(store, 'replay')
    if session is None:
        raise ValidationError('No simulated replay session is running. POST /api/replay/sessions first.')
    strike['replay_session_id'] = session['session_id']
    return jsonify(process_strike(store, strike, store.list_sites(), now))


# Replay

@ops_bp.post('/api/replay/sessions')
@with_store
def start_replay(store):
    body = request.get_json(silent=True) or {}
    wall = _now()
    replay.start_session(store, wall, body.get('speed'))
    session, _ = replay.sync(store, wall, store.list_sites())
    return jsonify(replay.session_view(session, wall)), 201


@ops_bp.get('/api/replay/session')
@with_store
def current_replay(store):
    wall = _now()
    session, _ = replay.sync(store, wall, store.list_sites())
    return jsonify(replay.session_view(session, wall))


@ops_bp.post('/api/replay/reset')
@with_store
def reset_replay(store):
    store.reset_replay()
    return jsonify({'reset': True, 'active': False, 'label': REPLAY_LABEL,
                    'note': 'All simulated replay holds, events and briefings were removed. Live data was not touched.'})


# Crew reports

@ops_bp.post('/api/reports')
@with_store
def post_report(store):
    request.max_content_length = PHOTO_LIMIT + 256 * 1024
    form = request.form
    site = store.get_site(_site_id(form.get('site_id')))
    if not site:
        return _not_found('Site')
    upload = request.files.get('photo')
    photo_bytes = None
    if upload is not None:
        photo_bytes = upload.stream.read(PHOTO_LIMIT + 1)
        if not photo_bytes and not upload.filename:
            photo_bytes = None  # empty file input: no photo chosen
    report = create_report(store, site, form, photo_bytes, _now())
    return jsonify({'report': report}), 201


@ops_bp.get('/api/reports')
@with_store
def list_reports(store):
    site_id = _site_id(request.args.get('site_id'))
    if not store.get_site(site_id):
        return _not_found('Site')
    return jsonify(site_history(store, site_id, _now()))


@ops_bp.get('/api/reports/<report_id>/photo')
@with_store
def report_photo(store, report_id):
    photo = store.get_report_photo(report_id)
    if not photo:
        return _not_found('Photo')
    response = current_app.response_class(photo['data'], mimetype=photo['content_type'])
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@ops_bp.post('/api/reports/<report_id>/resolve')
@with_store
def resolve(store, report_id):
    report = resolve_report(store, report_id, _now())
    if report is None:
        return _not_found('Report')
    return jsonify({'report': report})


# Briefings

@ops_bp.get('/api/briefings')
@with_store
def list_briefings(store):
    event_mode = _event_mode()
    raw = request.args.get('site_id')
    site_id = _site_id(raw) if raw not in (None, '') else None
    if site_id is not None and not store.get_site(site_id):
        return _not_found('Site')
    rows = store.list_briefings(site_id, event_mode)
    return jsonify({'site_id': site_id, 'event_mode': event_mode, 'label': mode_label(event_mode),
                    'briefings': rows, 'count': len(rows), 'as_of': iso(_now())})


@ops_bp.post('/api/briefings/generate')
@with_store
def generate_briefing_now(store):
    body = request.get_json(silent=True) or {}
    event_mode = parse_event_mode(body.get('event_mode'), default='replay')
    site = store.get_site(_site_id(body.get('site_id')))
    if not site:
        return _not_found('Site')
    now, session = _clock_for(store, event_mode)
    if event_mode == 'live':
        delivery = due_date(site, now)
        if delivery is None:
            return jsonify({'error': f"Live briefings for this site are delivered at 6 PM {site['timezone']} time; it is "
                                     f"{site_local(site, now).strftime('%H:%M')} there. Use event_mode \"replay\" to demonstrate.",
                            'code': 'not_due'}), 409
    else:
        delivery = site_local(site, now).date()
    inputs = store_inputs_provider(store, _live_source(), session)(site, delivery, event_mode, now)
    briefing, created = deliver_briefing(store, site, delivery, inputs, event_mode, now, trigger='manual')
    return jsonify({'created': created, 'briefing': briefing}), 201 if created else 200


# Evidence timeline

@ops_bp.get('/api/sites/<int:site_id>/timeline')
@with_store
def timeline(store, site_id):
    event_mode = _event_mode()
    site = store.get_site(site_id)
    if not site:
        return _not_found('Site')
    now, _ = _clock_for(store, event_mode)
    return jsonify(site_timeline(store, site, event_mode, now))
