import json
import os
import hashlib
import math
import uuid
from pathlib import Path
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
WORKER_LOCK = 726108496583291
MIGRATION_LOCK = 726108496583292


class DatabaseUnavailable(RuntimeError):
    pass


class WorkerAlreadyRunning(RuntimeError):
    pass


@contextmanager
def connection(*, autocommit=False):
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise DatabaseUnavailable('DATABASE_URL is not configured. Add your Tiger Data URI to .env.')
    try:
        conn = psycopg.connect(url, connect_timeout=5, row_factory=dict_row, autocommit=autocommit)
    except psycopg.Error:
        raise DatabaseUnavailable('Tiger Data connection failed. Check your URI, TLS settings, and network.') from None
    try:
        with conn:
            yield conn
    except psycopg.Error:
        raise DatabaseUnavailable('Tiger Data operation failed. Check database availability and run the migration/seed command.') from None
    finally:
        conn.close()


def check_database():
    with connection() as conn:
        conn.execute('SELECT 1')


def migrate():
    """Apply additive SQL files atomically, serializing concurrent startup."""
    applied = []
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(%s)', (MIGRATION_LOCK,))
        conn.execute((ROOT / 'backend/schema.sql').read_text(encoding='utf-8'))
        conn.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now())''')
        for path in sorted((ROOT / 'backend/migrations').glob('*.sql')):
            sql = path.read_text(encoding='utf-8')
            checksum = hashlib.sha256(sql.encode('utf-8')).hexdigest()
            previous = conn.execute('SELECT checksum FROM schema_migrations WHERE version = %s', (path.name,)).fetchone()
            if previous:
                if previous['checksum'] != checksum:
                    raise RuntimeError(f'Applied migration {path.name} has changed; restore it and add a new migration.')
                continue
            conn.execute(sql)
            conn.execute('INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)', (path.name, checksum))
            applied.append(path.name)
    return applied


def seed_sites():
    rows = demo_sites()
    if not rows:
        raise ValueError('data/sites.json is absent or empty. Run scripts.prepare_sites first.')
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany('''INSERT INTO sites (id, source_plant_id, name, state, county, latitude, longitude, timezone, source_version)
                VALUES (%(id)s, %(source_plant_id)s, %(name)s, %(state)s, %(county)s, %(latitude)s, %(longitude)s, %(timezone)s, %(source_version)s)
                ON CONFLICT (source_plant_id) DO UPDATE SET name=EXCLUDED.name, state=EXCLUDED.state, county=EXCLUDED.county,
                latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, timezone=EXCLUDED.timezone, source_version=EXCLUDED.source_version''', rows)
        return conn.execute('SELECT count(*) AS count FROM sites').fetchone()['count']


def demo_sites():
    path = ROOT / 'data' / 'sites.json'
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))['sites']


def list_sites(mode):
    if mode == 'demo':
        return demo_sites()
    if mode != 'live':
        raise ValueError('mode must be live or demo')
    try:
        with connection() as conn:
            return conn.execute('SELECT id, source_plant_id, name, state, county, latitude, longitude, timezone, source_version FROM sites ORDER BY state, name').fetchall()
    except psycopg.Error:
        raise DatabaseUnavailable('Site query failed. Run the schema and seed steps in the README.') from None


def save_weather_snapshot(site_id, payload, attempted_at):
    """Only live provider results enter this storage path; replay is separate."""
    stored = {key: value for key, value in payload.items() if key not in ('cached', 'stale', 'warning')}
    # Reject non-JSON values (including NaN) before opening a transaction.
    json.dumps(stored, allow_nan=False)
    fetched_at = datetime.fromisoformat(stored['fetched_at'])
    if fetched_at.tzinfo is None:
        raise ValueError('Weather retrieval timestamp must include a timezone.')
    with connection() as conn:
        conn.execute('''INSERT INTO weather_snapshots (site_id, event_mode, source, fetched_at, payload)
            VALUES (%s, 'live', %s, %s, %s)
            ON CONFLICT (site_id, event_mode, source, fetched_at) DO NOTHING''',
            (site_id, stored['source'], fetched_at, Jsonb(stored)))
        conn.execute('''INSERT INTO weather_ingestion (site_id, event_mode, last_attempt_at, last_success_at, error_code)
            VALUES (%s, 'live', %s, %s, NULL)
            ON CONFLICT (site_id, event_mode) DO UPDATE SET
                last_attempt_at = EXCLUDED.last_attempt_at,
                last_success_at = GREATEST(weather_ingestion.last_success_at, EXCLUDED.last_success_at),
                error_code = NULL
            WHERE weather_ingestion.last_attempt_at <= EXCLUDED.last_attempt_at''',
            (site_id, attempted_at, fetched_at))


def record_weather_failure(site_id, attempted_at):
    with connection() as conn:
        conn.execute('''INSERT INTO weather_ingestion (site_id, event_mode, last_attempt_at, error_code)
            VALUES (%s, 'live', %s, 'weather_unavailable')
            ON CONFLICT (site_id, event_mode) DO UPDATE SET
                last_attempt_at = EXCLUDED.last_attempt_at, error_code = EXCLUDED.error_code
            WHERE weather_ingestion.last_attempt_at <= EXCLUDED.last_attempt_at''', (site_id, attempted_at))


def latest_weather():
    """One stored-data query for every site; never fetch providers from polling."""
    with connection() as conn:
        rows = conn.execute('''SELECT s.id AS site_id, w.payload,
                i.last_attempt_at, i.last_success_at, i.error_code
            FROM sites s
            LEFT JOIN LATERAL (
                SELECT payload FROM weather_snapshots
                WHERE site_id = s.id AND event_mode = 'live'
                ORDER BY fetched_at DESC, id DESC LIMIT 1
            ) w ON TRUE
            LEFT JOIN weather_ingestion i ON i.site_id = s.id AND i.event_mode = 'live'
            ORDER BY s.id''').fetchall()
    return {row['site_id']: row for row in rows}


@contextmanager
def worker_lease():
    # Session lock survives commits; autocommit avoids a long idle transaction.
    with connection(autocommit=True) as conn:
        acquired = conn.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (WORKER_LOCK,)).fetchone()['acquired']
        if not acquired:
            raise WorkerAlreadyRunning('Another PlanIT worker holds the database lease. Stop it before starting a replacement.')
        try:
            yield conn
        finally:
            if not conn.closed:
                conn.execute('SELECT pg_advisory_unlock(%s)', (WORKER_LOCK,))


def start_job(conn, name):
    # Called on the lease connection: a disconnected worker cannot start jobs.
    return conn.execute('''INSERT INTO worker_runs (job_name, status)
        VALUES (%s, 'running') RETURNING id''', (name,)).fetchone()['id']


def recover_job_runs(conn):
    """Only call after acquiring the single worker lease."""
    return conn.execute('''UPDATE worker_runs SET status = 'failed', finished_at = now(),
        summary = %s WHERE status = 'running' ''',
        (Jsonb({'error_code': 'worker_interrupted'}),)).rowcount


def finish_job(conn, run_id, status, summary):
    conn.execute('''UPDATE worker_runs SET status = %s, finished_at = now(), summary = %s
        WHERE id = %s''', (status, Jsonb(summary), run_id))


def event_mode(value):
    if value not in ('live', 'replay'):
        raise ValueError('event_mode must be live or replay; it is separate from plant storage mode.')
    return value


def timestamp(value):
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Timestamps must include a timezone.')
    return result.astimezone(timezone.utc)


def text(value, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('A required text value is absent or too long.')
    return value.strip()


def save_official_alerts(site_id, payload, attempted_at):
    fetched_at = timestamp(payload['fetched_at'])
    with connection() as conn:
        conn.execute('''INSERT INTO official_alert_snapshots (site_id, event_mode, fetched_at, payload)
            VALUES (%s, 'live', %s, %s) ON CONFLICT (site_id, event_mode) DO UPDATE
            SET fetched_at = EXCLUDED.fetched_at, payload = EXCLUDED.payload
            WHERE official_alert_snapshots.fetched_at <= EXCLUDED.fetched_at''', (site_id, fetched_at, Jsonb(payload)))
        conn.execute('''INSERT INTO official_alert_ingestion (site_id, event_mode, last_attempt_at, error_code)
            VALUES (%s, 'live', %s, NULL) ON CONFLICT (site_id, event_mode) DO UPDATE
            SET last_attempt_at = EXCLUDED.last_attempt_at, error_code = NULL
            WHERE official_alert_ingestion.last_attempt_at <= EXCLUDED.last_attempt_at''', (site_id, attempted_at))


def record_official_alert_failure(site_id, attempted_at):
    with connection() as conn:
        conn.execute('''INSERT INTO official_alert_ingestion (site_id, event_mode, last_attempt_at, error_code)
            VALUES (%s, 'live', %s, 'official_alerts_unavailable')
            ON CONFLICT (site_id, event_mode) DO UPDATE SET
            last_attempt_at = EXCLUDED.last_attempt_at, error_code = EXCLUDED.error_code
            WHERE official_alert_ingestion.last_attempt_at <= EXCLUDED.last_attempt_at''', (site_id, attempted_at))


def latest_official_alerts():
    with connection() as conn:
        rows = conn.execute('''SELECT s.id AS site_id, a.payload, i.last_attempt_at, i.error_code
            FROM sites s LEFT JOIN official_alert_snapshots a ON a.site_id = s.id AND a.event_mode = 'live'
            LEFT JOIN official_alert_ingestion i ON i.site_id = s.id AND i.event_mode = 'live' ''').fetchall()
    return {row['site_id']: row for row in rows}


def store_lightning_event(*, source, event_id, occurred_at, latitude, longitude,
                          affected_site_ids, mode):
    """B validates strike age/provider and computes sites within ten miles first."""
    mode = event_mode(mode)
    source, event_id = text(source, 200), text(event_id, 500)
    strike_time = timestamp(occurred_at)
    if (not isinstance(latitude, (int, float)) or isinstance(latitude, bool)
            or not math.isfinite(latitude) or not -90 <= latitude <= 90
            or not isinstance(longitude, (int, float)) or isinstance(longitude, bool)
            or not math.isfinite(longitude) or not -180 <= longitude <= 180):
        raise ValueError('Strike coordinates are invalid.')
    sites = set(affected_site_ids)
    if any(not isinstance(site_id, int) or isinstance(site_id, bool) or site_id <= 0 for site_id in sites):
        raise ValueError('Affected sites must be positive integer plant IDs.')
    with connection() as conn:
        accepted = conn.execute('''INSERT INTO lightning_events
            (source, event_mode, event_id, occurred_at, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING event_id''',
            (source, mode, event_id, strike_time, latitude, longitude)).fetchone()
        if not accepted:
            return {'accepted': False, 'affected_sites': 0}
        for site_id in sites:
            conn.execute('''INSERT INTO lightning_holds (site_id, event_mode, hold_until, last_strike_at, source)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (site_id, event_mode) DO UPDATE SET
                hold_until = GREATEST(lightning_holds.hold_until, EXCLUDED.hold_until),
                last_strike_at = GREATEST(lightning_holds.last_strike_at, EXCLUDED.last_strike_at),
                source = CASE WHEN EXCLUDED.last_strike_at >= lightning_holds.last_strike_at
                    THEN EXCLUDED.source ELSE lightning_holds.source END''',
                (site_id, mode, strike_time + timedelta(minutes=30), strike_time, source))
    return {'accepted': True, 'affected_sites': len(sites)}


def get_lightning_holds(*, mode):
    with connection() as conn:
        rows = conn.execute('''SELECT site_id, hold_until, last_strike_at, source
            FROM lightning_holds WHERE event_mode = %s''', (event_mode(mode),)).fetchall()
    return {row['site_id']: row for row in rows}


def save_crew_report(*, site_id, latitude, longitude, category, note, observed_at,
                     photo, photo_content_type, mode):
    """B must verify actual image content before calling this repository."""
    if category not in ('wildlife', 'water', 'access', 'fire', 'other', 'heat', 'lightning', 'flooding', 'mud'):
        raise ValueError('Unknown crew report category.')
    if photo_content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise ValueError('Unsupported photo content type.')
    if not isinstance(photo, bytes) or not 0 < len(photo) <= 5 * 1024 * 1024:
        raise ValueError('A photo must contain between 1 byte and 5 MiB.')
    report_id = uuid.uuid4()
    with connection() as conn:
        conn.execute('''INSERT INTO crew_reports
            (id, site_id, event_mode, observed_at, latitude, longitude, category, note, photo, photo_content_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (report_id, site_id, event_mode(mode), timestamp(observed_at), latitude, longitude,
             category, text(note), photo, photo_content_type))
    return str(report_id)


def list_crew_reports(*, site_id=None, mode, unresolved_only=False):
    with connection() as conn:
        rows = conn.execute('''SELECT id, site_id, observed_at, created_at, latitude, longitude,
                category, note, photo_content_type, resolved_at
            FROM crew_reports WHERE event_mode = %s AND (%s::integer IS NULL OR site_id = %s)
                AND (NOT %s OR resolved_at IS NULL) ORDER BY observed_at DESC, id''',
            (event_mode(mode), site_id, site_id, unresolved_only)).fetchall()
    return [{**row, 'id': str(row['id'])} for row in rows]


def get_report_photo(report_id, *, mode):
    with connection() as conn:
        row = conn.execute('SELECT photo, photo_content_type FROM crew_reports WHERE id = %s AND event_mode = %s',
            (uuid.UUID(str(report_id)), event_mode(mode))).fetchone()
    return {'photo': bytes(row['photo']), 'photo_content_type': row['photo_content_type']} if row else None


def save_briefing(*, site_id, delivery_local_date, target_date, body, facts, mode):
    delivery = date.fromisoformat(delivery_local_date) if isinstance(delivery_local_date, str) else delivery_local_date
    target = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    if target != delivery + timedelta(days=1) or not isinstance(facts, dict):
        raise ValueError('A briefing needs a next-local-day target date and a facts dictionary.')
    with connection() as conn:
        row = conn.execute('''INSERT INTO briefings
            (id, site_id, event_mode, delivery_local_date, target_date, body, facts)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (site_id, event_mode, delivery_local_date) DO NOTHING RETURNING id''',
            (uuid.uuid4(), site_id, event_mode(mode), delivery, target, text(body, 30000), Jsonb(facts))).fetchone()
        if not row:
            row = conn.execute('''SELECT id FROM briefings
                WHERE site_id = %s AND event_mode = %s AND delivery_local_date = %s''',
                (site_id, mode, delivery)).fetchone()
    return str(row['id'])


def list_briefings(*, site_id=None, mode):
    with connection() as conn:
        rows = conn.execute('''SELECT id, site_id, delivery_local_date, target_date, generated_at, body, facts
            FROM briefings WHERE event_mode = %s AND (%s::integer IS NULL OR site_id = %s)
            ORDER BY delivery_local_date DESC, site_id''', (event_mode(mode), site_id, site_id)).fetchall()
    return [{**row, 'id': str(row['id'])} for row in rows]


def save_prediction(*, site_id, valid_date, model_version, feature_version, score, computed_at, provenance, mode,
                    status='available', probability=None, outside_training_range=None, outside_training_counties=None):
    if status not in ('available', 'unavailable') or (status == 'unavailable' and score is not None):
        raise ValueError('Invalid prediction availability.')
    if status == 'unavailable' and probability is not None:
        raise ValueError('Unavailable predictions cannot carry a probability.')
    if status == 'available' and (not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 10):
        raise ValueError('Experimental model score must be finite and between 0 and 10.')
    if probability is not None and (isinstance(probability, bool) or not isinstance(probability, (int, float))
                                    or not math.isfinite(probability) or not 0 <= probability <= 1):
        raise ValueError('Invalid prediction probability.')
    if outside_training_range is not None and (not isinstance(outside_training_range, list)
                                             or not all(isinstance(value, str) for value in outside_training_range)):
        raise ValueError('Range warnings must be a list of feature names.')
    if not isinstance(provenance, dict) or not provenance.get('model_artifact'):
        raise ValueError('Prediction provenance must identify the actual saved model artifact.')
    with connection() as conn:
        conn.execute('''INSERT INTO model_predictions
            (site_id, event_mode, valid_date, model_version, feature_version, score, computed_at, provenance,
             status, probability, outside_training_range, outside_training_counties)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (site_id, event_mode, valid_date, model_version, feature_version) DO UPDATE
            SET score = EXCLUDED.score, computed_at = EXCLUDED.computed_at, provenance = EXCLUDED.provenance,
                status = EXCLUDED.status, probability = EXCLUDED.probability,
                outside_training_range = EXCLUDED.outside_training_range,
                outside_training_counties = EXCLUDED.outside_training_counties
            WHERE model_predictions.computed_at <= EXCLUDED.computed_at''',
            (site_id, event_mode(mode), valid_date, text(model_version, 200), text(feature_version, 200),
             score, timestamp(computed_at), Jsonb(provenance), status, probability,
             Jsonb(outside_training_range or []), outside_training_counties))


def next_day_predictions(*, now, mode):
    return daily_predictions(now=now, mode=mode, day_offset=1)


def daily_predictions(*, now, mode, day_offset=0):
    if day_offset not in (0, 1):
        raise ValueError('Only today and tomorrow predictions are supported.')
    with connection() as conn:
        rows = conn.execute('''SELECT DISTINCT ON (p.site_id) p.site_id, p.valid_date,
                p.model_version, p.feature_version, p.score, p.computed_at, p.provenance,
                p.status, p.probability, p.outside_training_range, p.outside_training_counties
            FROM model_predictions p JOIN sites s ON s.id = p.site_id
            WHERE p.event_mode = %s AND p.valid_date = (%s::timestamptz AT TIME ZONE s.timezone)::date + %s
            ORDER BY p.site_id, p.computed_at DESC, p.model_version, p.feature_version''',
            (event_mode(mode), timestamp(now), day_offset)).fetchall()
    return {row['site_id']: row for row in rows}


def latest_hydrology():
    with connection() as conn:
        rows = conn.execute('SELECT site_id, fetched_at, attempted_at, error_code, payload FROM site_hydrology').fetchall()
    return {row['site_id']: row for row in rows}


def save_hydrology(site_id, now, payload):
    with connection() as conn:
        conn.execute('''INSERT INTO site_hydrology (site_id, fetched_at, attempted_at, error_code, payload)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (site_id) DO UPDATE SET
                attempted_at = EXCLUDED.attempted_at, error_code = EXCLUDED.error_code,
                fetched_at = COALESCE(EXCLUDED.fetched_at, site_hydrology.fetched_at),
                payload = COALESCE(EXCLUDED.payload, site_hydrology.payload)
            WHERE site_hydrology.attempted_at <= EXCLUDED.attempted_at''',
            (site_id, now if payload is not None else None, now,
             'hydrology_unavailable' if payload is None else None, Jsonb(payload) if payload is not None else None))



# ---------------------------------------------------------------------------
# Workstream B (operational events) additions. A's functions above are unchanged.
# Tables: lightning_feed_status, replay_sessions, ops_events (migration 003), plus
# row-level reads/updates on A's crew_reports, briefings, lightning_events and
# lightning_holds. No schema changes here.
# ---------------------------------------------------------------------------

def ops_record_feed(*, mode, source, received_at=None, checked_at=None):
    with connection() as conn:
        conn.execute('''INSERT INTO lightning_feed_status (event_mode, source, last_event_received_at, last_feed_check_at)
            VALUES (%s, %s, %s, %s) ON CONFLICT (event_mode, source) DO UPDATE SET
            last_event_received_at = GREATEST(lightning_feed_status.last_event_received_at, EXCLUDED.last_event_received_at),
            last_feed_check_at = GREATEST(lightning_feed_status.last_feed_check_at, EXCLUDED.last_feed_check_at)''',
            (event_mode(mode), text(source, 200), received_at, checked_at))


def ops_get_feeds(*, mode):
    with connection() as conn:
        return conn.execute('''SELECT event_mode, source, last_event_received_at, last_feed_check_at
            FROM lightning_feed_status WHERE event_mode = %s''', (event_mode(mode),)).fetchall()


def ops_start_replay_session(*, session_id, started_at, replay_epoch, speed):
    with connection() as conn:
        conn.execute('UPDATE replay_sessions SET active = false WHERE active')
        conn.execute('''INSERT INTO replay_sessions (session_id, started_at, replay_epoch, speed, active)
            VALUES (%s, %s, %s, %s, true)''', (session_id, started_at, replay_epoch, speed))


def ops_get_replay_session():
    with connection() as conn:
        return conn.execute('''SELECT session_id, started_at, replay_epoch, speed, active FROM replay_sessions
            WHERE active ORDER BY started_at DESC LIMIT 1''').fetchone()


def ops_reset_replay():
    """Deletes event_mode = 'replay' rows only. Live rows and lightning_strikes are never touched."""
    with connection() as conn:
        for table in ('ops_events', 'lightning_feed_status', 'lightning_holds', 'lightning_events', 'briefings', 'crew_reports'):
            conn.execute(f"DELETE FROM {table} WHERE event_mode = 'replay'")
        conn.execute('UPDATE replay_sessions SET active = false WHERE active')


def ops_add_event(*, event_id, site_id, mode, type, occurred_at, source, summary, ref_table, ref_key, details):
    with connection() as conn:
        row = conn.execute('''INSERT INTO ops_events
            (id, site_id, event_mode, type, occurred_at, source, summary, ref_table, ref_key, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING RETURNING id''',
            (event_id, site_id, event_mode(mode), type, timestamp(occurred_at), source, summary,
             ref_table, Jsonb(ref_key), Jsonb(details))).fetchone()
    return row is not None


def ops_list_events(*, site_id, mode):
    with connection() as conn:
        return conn.execute('''SELECT id, site_id, event_mode, type, occurred_at, source, summary, ref_table, ref_key, details
            FROM ops_events WHERE site_id = %s AND event_mode = %s ORDER BY occurred_at, id''',
            (site_id, event_mode(mode))).fetchall()


def ops_get_crew_report(report_id):
    try:
        key = uuid.UUID(str(report_id))
    except ValueError:
        return None
    with connection() as conn:
        row = conn.execute('''SELECT id, site_id, event_mode, observed_at, created_at, latitude, longitude,
                category, note, photo_content_type, resolved_at FROM crew_reports WHERE id = %s''', (key,)).fetchone()
    return {**row, 'id': str(row['id'])} if row else None


def ops_resolve_crew_report(report_id, *, resolved_at):
    """Sets resolved_at once; the report stays in history."""
    try:
        key = uuid.UUID(str(report_id))
    except ValueError:
        return None
    with connection() as conn:
        conn.execute('UPDATE crew_reports SET resolved_at = %s WHERE id = %s AND resolved_at IS NULL',
                     (timestamp(resolved_at), key))
    return ops_get_crew_report(report_id)


def ops_get_briefing(*, site_id, delivery_local_date, mode):
    with connection() as conn:
        row = conn.execute('''SELECT id, site_id, delivery_local_date, target_date, generated_at, body, facts
            FROM briefings WHERE site_id = %s AND event_mode = %s AND delivery_local_date = %s''',
            (site_id, event_mode(mode), delivery_local_date)).fetchone()
    return {**row, 'id': str(row['id'])} if row else None
