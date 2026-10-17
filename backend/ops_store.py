"""Persistence for Workstream B behind one small interface.

PostgresStore is the shared, durable store used by the running app (tables in
backend/schema.sql under "Workstream B"). MemoryStore exists for tests only and
is never used as a silent fallback for a failed database.
"""
import copy
import threading
from contextlib import contextmanager, nullcontext
from typing import Protocol

import psycopg
from psycopg.types.json import Jsonb

from .db import DatabaseUnavailable, connection

QUERY_FAILED = ('Operational events query failed. The Workstream B tables may not be applied yet; '
                'the backend owner runs the schema step.')


class OpsStore(Protocol):
    def batch(self): ...
    def list_sites(self): ...
    def get_site(self, site_id): ...
    def insert_strike(self, strike): ...
    def get_hold(self, site_id, event_mode): ...
    def list_holds(self, event_mode): ...
    def extend_hold(self, site_id, event_mode, candidate_until, strike, distance_km, now): ...
    def record_feed(self, event_mode, source, received_at=None, checked_at=None): ...
    def get_feeds(self, event_mode): ...
    def start_replay_session(self, session): ...
    def get_replay_session(self): ...
    def reset_replay(self): ...
    def create_report(self, report, photo): ...
    def list_reports(self, site_id, event_mode): ...
    def get_report(self, report_id): ...
    def get_report_photo(self, report_id): ...
    def resolve_report(self, report_id, now): ...
    def insert_briefing(self, briefing): ...
    def get_briefing(self, site_id, delivery_local_date, event_mode): ...
    def list_briefings(self, site_id, event_mode): ...
    def add_event(self, event): ...
    def list_events(self, site_id, event_mode): ...


def _empty_data():
    return {'strikes': {}, 'holds': {}, 'feeds': {}, 'replay_sessions': {}, 'reports': {}, 'photos': {}, 'briefings': {}, 'events': {}}


class MemoryStore:
    """In-process store for tests. Pass data= from another instance to simulate a reconnect."""

    def __init__(self, sites, data=None):
        self.sites = {int(s['id']): dict(s) for s in sites}
        self.data = data if data is not None else _empty_data()

    def batch(self):
        return nullcontext()

    def list_sites(self):
        return [dict(s) for s in self.sites.values()]

    def get_site(self, site_id):
        site = self.sites.get(int(site_id))
        return dict(site) if site else None

    def insert_strike(self, strike):
        key = (strike['event_mode'], strike['source'], strike['event_id'])
        if key in self.data['strikes']:
            return False
        self.data['strikes'][key] = dict(strike)
        return True

    def get_hold(self, site_id, event_mode):
        hold = self.data['holds'].get((int(site_id), event_mode))
        return dict(hold) if hold else None

    def list_holds(self, event_mode):
        return [dict(h) for (_, mode), h in self.data['holds'].items() if mode == event_mode]

    def extend_hold(self, site_id, event_mode, candidate_until, strike, distance_km, now):
        key = (int(site_id), event_mode)
        existing = self.data['holds'].get(key)
        previous = existing['hold_until'] if existing else None
        if previous is not None and previous >= candidate_until:
            return previous, previous
        self.data['holds'][key] = {
            'site_id': int(site_id), 'event_mode': event_mode, 'hold_until': candidate_until,
            'last_strike_source': strike['source'], 'last_strike_event_id': strike['event_id'],
            'last_strike_at': strike['occurred_at'], 'last_strike_distance_km': distance_km, 'updated_at': now,
        }
        return previous, candidate_until

    def record_feed(self, event_mode, source, received_at=None, checked_at=None):
        feed = self.data['feeds'].setdefault((event_mode, source), {
            'event_mode': event_mode, 'source': source, 'last_event_received_at': None, 'last_feed_check_at': None})
        if received_at is not None:
            feed['last_event_received_at'] = max(filter(None, [feed['last_event_received_at'], received_at]))
        if checked_at is not None:
            feed['last_feed_check_at'] = max(filter(None, [feed['last_feed_check_at'], checked_at]))

    def get_feeds(self, event_mode):
        return [dict(f) for (mode, _), f in self.data['feeds'].items() if mode == event_mode]

    def start_replay_session(self, session):
        for existing in self.data['replay_sessions'].values():
            existing['active'] = False
        self.data['replay_sessions'][session['session_id']] = dict(session, active=True)

    def get_replay_session(self):
        active = [s for s in self.data['replay_sessions'].values() if s['active']]
        return dict(active[-1]) if active else None

    def reset_replay(self):
        for name in ('strikes', 'holds', 'feeds'):
            self.data[name] = {k: v for k, v in self.data[name].items() if k[0 if name != 'holds' else 1] != 'replay'}
        for name in ('briefings', 'events', 'reports'):
            self.data[name] = {k: v for k, v in self.data[name].items() if v['event_mode'] != 'replay'}
        for session in self.data['replay_sessions'].values():
            session['active'] = False

    def create_report(self, report, photo):
        self.data['reports'][report['id']] = dict(report)
        if photo is not None:
            self.data['photos'][report['id']] = photo

    def list_reports(self, site_id, event_mode):
        rows = [dict(r) for r in self.data['reports'].values() if r['site_id'] == int(site_id) and r['event_mode'] == event_mode]
        return sorted(rows, key=lambda r: (r['created_at'], r['id']), reverse=True)

    def get_report(self, report_id):
        report = self.data['reports'].get(report_id)
        return dict(report) if report else None

    def get_report_photo(self, report_id):
        return self.data['photos'].get(report_id)

    def resolve_report(self, report_id, now):
        report = self.data['reports'].get(report_id)
        if not report:
            return None
        if report['status'] != 'resolved':
            report['status'] = 'resolved'
            report['resolved_at'] = now
        return dict(report)

    def insert_briefing(self, briefing):
        key = (briefing['site_id'], briefing['delivery_local_date'], briefing['event_mode'])
        if key in self.data['briefings']:
            return False
        self.data['briefings'][key] = copy.deepcopy(briefing)
        return True

    def get_briefing(self, site_id, delivery_local_date, event_mode):
        found = self.data['briefings'].get((int(site_id), delivery_local_date, event_mode))
        return copy.deepcopy(found) if found else None

    def list_briefings(self, site_id, event_mode):
        rows = [copy.deepcopy(b) for b in self.data['briefings'].values()
                if b['event_mode'] == event_mode and (site_id is None or b['site_id'] == int(site_id))]
        return sorted(rows, key=lambda b: (b['delivery_local_date'], b['delivered_at']), reverse=True)

    def add_event(self, event):
        if event['id'] in self.data['events']:
            return False
        self.data['events'][event['id']] = copy.deepcopy(event)
        return True

    def list_events(self, site_id, event_mode):
        rows = [copy.deepcopy(e) for e in self.data['events'].values() if e['site_id'] == int(site_id) and e['event_mode'] == event_mode]
        return sorted(rows, key=lambda e: (e['occurred_at'], e['id']))


SITE_COLUMNS = 'id, source_plant_id, name, state, county, latitude, longitude, timezone, source_version'
REPORT_COLUMNS = ('id, site_id, event_mode, latitude, longitude, category, note, created_at, status, resolved_at, '
                  'distance_from_site_km, location_flag, photo_content_type, photo_size_bytes')
HOLD_COLUMNS = ('site_id, event_mode, hold_until, last_strike_source, last_strike_event_id, last_strike_at, '
                'last_strike_distance_km, updated_at')


class PostgresStore:
    """Shared Tiger Data store. Every query failure becomes DatabaseUnavailable (HTTP 503)."""

    def __init__(self):
        self._local = threading.local()

    @contextmanager
    def batch(self):
        """Use one connection and one transaction for a whole request or worker run."""
        if getattr(self._local, 'conn', None) is not None:
            yield
            return
        try:
            with connection() as conn:
                self._local.conn = conn
                try:
                    yield
                finally:
                    self._local.conn = None
        except psycopg.Error:
            raise DatabaseUnavailable(QUERY_FAILED) from None

    @contextmanager
    def _conn(self):
        conn = getattr(self._local, 'conn', None)
        try:
            if conn is not None:
                yield conn
            else:
                with connection() as fresh:
                    yield fresh
        except psycopg.Error:
            raise DatabaseUnavailable(QUERY_FAILED) from None

    def _all(self, sql, params=()):
        with self._conn() as conn:
            return conn.execute(sql, params).fetchall()

    def _one(self, sql, params=()):
        with self._conn() as conn:
            return conn.execute(sql, params).fetchone()

    def _run(self, *statements):
        with self._conn() as conn:
            for sql, params in statements:
                conn.execute(sql, params)

    def list_sites(self):
        return self._all(f'SELECT {SITE_COLUMNS} FROM sites ORDER BY state, name')

    def get_site(self, site_id):
        return self._one(f'SELECT {SITE_COLUMNS} FROM sites WHERE id = %s', (int(site_id),))

    def insert_strike(self, strike):
        row = self._one(
            '''INSERT INTO lightning_strikes (event_mode, source, event_id, occurred_at, received_at, latitude, longitude, replay_session_id)
               VALUES (%(event_mode)s, %(source)s, %(event_id)s, %(occurred_at)s, %(received_at)s, %(latitude)s, %(longitude)s, %(replay_session_id)s)
               ON CONFLICT (event_mode, source, event_id) DO NOTHING RETURNING event_id''', strike)
        return row is not None

    def get_hold(self, site_id, event_mode):
        return self._one(f'SELECT {HOLD_COLUMNS} FROM lightning_holds WHERE site_id = %s AND event_mode = %s', (int(site_id), event_mode))

    def list_holds(self, event_mode):
        return self._all(f'SELECT {HOLD_COLUMNS} FROM lightning_holds WHERE event_mode = %s', (event_mode,))

    def extend_hold(self, site_id, event_mode, candidate_until, strike, distance_km, now):
        with self._conn() as conn:
            row = conn.execute('SELECT hold_until FROM lightning_holds WHERE site_id = %s AND event_mode = %s FOR UPDATE',
                               (int(site_id), event_mode)).fetchone()
            previous = row['hold_until'] if row else None
            if previous is not None and previous >= candidate_until:
                return previous, previous
            conn.execute(
                '''INSERT INTO lightning_holds (site_id, event_mode, hold_until, last_strike_source, last_strike_event_id,
                       last_strike_at, last_strike_distance_km, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (site_id, event_mode) DO UPDATE SET hold_until = EXCLUDED.hold_until,
                       last_strike_source = EXCLUDED.last_strike_source, last_strike_event_id = EXCLUDED.last_strike_event_id,
                       last_strike_at = EXCLUDED.last_strike_at, last_strike_distance_km = EXCLUDED.last_strike_distance_km,
                       updated_at = EXCLUDED.updated_at
                   WHERE lightning_holds.hold_until < EXCLUDED.hold_until''',
                (int(site_id), event_mode, candidate_until, strike['source'], strike['event_id'],
                 strike['occurred_at'], distance_km, now))
            return previous, candidate_until

    def record_feed(self, event_mode, source, received_at=None, checked_at=None):
        self._run(('''INSERT INTO lightning_feed_status (event_mode, source, last_event_received_at, last_feed_check_at)
                      VALUES (%s, %s, %s, %s)
                      ON CONFLICT (event_mode, source) DO UPDATE SET
                          last_event_received_at = GREATEST(lightning_feed_status.last_event_received_at, EXCLUDED.last_event_received_at),
                          last_feed_check_at = GREATEST(lightning_feed_status.last_feed_check_at, EXCLUDED.last_feed_check_at)''',
                   (event_mode, source, received_at, checked_at)))

    def get_feeds(self, event_mode):
        return self._all('SELECT event_mode, source, last_event_received_at, last_feed_check_at FROM lightning_feed_status WHERE event_mode = %s',
                         (event_mode,))

    def start_replay_session(self, session):
        self._run(('UPDATE replay_sessions SET active = false WHERE active', ()),
                  ('INSERT INTO replay_sessions (session_id, started_at, replay_epoch, speed, active) VALUES (%s, %s, %s, %s, true)',
                   (session['session_id'], session['started_at'], session['replay_epoch'], session['speed'])))

    def get_replay_session(self):
        return self._one('SELECT session_id, started_at, replay_epoch, speed, active FROM replay_sessions '
                         'WHERE active ORDER BY started_at DESC LIMIT 1')

    def reset_replay(self):
        self._run(*[(f"DELETE FROM {table} WHERE event_mode = 'replay'", ()) for table in
                    ('ops_events', 'briefings', 'crew_reports', 'lightning_holds', 'lightning_strikes', 'lightning_feed_status')],
                  ('UPDATE replay_sessions SET active = false WHERE active', ()))

    def create_report(self, report, photo):
        params = dict(report, photo=photo['data'] if photo else None)
        self._run(('''INSERT INTO crew_reports (id, site_id, event_mode, latitude, longitude, category, note, created_at, status,
                          resolved_at, distance_from_site_km, location_flag, photo, photo_content_type, photo_size_bytes)
                      VALUES (%(id)s, %(site_id)s, %(event_mode)s, %(latitude)s, %(longitude)s, %(category)s, %(note)s, %(created_at)s,
                          %(status)s, %(resolved_at)s, %(distance_from_site_km)s, %(location_flag)s, %(photo)s,
                          %(photo_content_type)s, %(photo_size_bytes)s)''', params))

    def list_reports(self, site_id, event_mode):
        return self._all(f'SELECT {REPORT_COLUMNS} FROM crew_reports WHERE site_id = %s AND event_mode = %s ORDER BY created_at DESC, id DESC',
                         (int(site_id), event_mode))

    def get_report(self, report_id):
        return self._one(f'SELECT {REPORT_COLUMNS} FROM crew_reports WHERE id = %s', (report_id,))

    def get_report_photo(self, report_id):
        row = self._one('SELECT photo, photo_content_type FROM crew_reports WHERE id = %s AND photo IS NOT NULL', (report_id,))
        return {'data': bytes(row['photo']), 'content_type': row['photo_content_type']} if row else None

    def resolve_report(self, report_id, now):
        self._run(("UPDATE crew_reports SET status = 'resolved', resolved_at = %s WHERE id = %s AND status <> 'resolved'", (now, report_id)))
        return self.get_report(report_id)

    def insert_briefing(self, briefing):
        row = self._one(
            '''INSERT INTO briefings (id, site_id, delivery_local_date, forecast_target_date, event_mode, trigger, timezone,
                   delivered_at, generator, content, body_text)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (site_id, delivery_local_date, event_mode) DO NOTHING RETURNING id''',
            (briefing['id'], briefing['site_id'], briefing['delivery_local_date'], briefing['forecast_target_date'],
             briefing['event_mode'], briefing['trigger'], briefing['timezone'], briefing['delivered_at'],
             briefing['generator'], Jsonb(briefing), briefing['body_text']))
        return row is not None

    def get_briefing(self, site_id, delivery_local_date, event_mode):
        row = self._one('SELECT content FROM briefings WHERE site_id = %s AND delivery_local_date = %s AND event_mode = %s',
                        (int(site_id), delivery_local_date, event_mode))
        return row['content'] if row else None

    def list_briefings(self, site_id, event_mode):
        if site_id is None:
            rows = self._all('SELECT content FROM briefings WHERE event_mode = %s ORDER BY delivery_local_date DESC, delivered_at DESC LIMIT 200',
                             (event_mode,))
        else:
            rows = self._all('SELECT content FROM briefings WHERE site_id = %s AND event_mode = %s ORDER BY delivery_local_date DESC, delivered_at DESC',
                             (int(site_id), event_mode))
        return [r['content'] for r in rows]

    def add_event(self, event):
        row = self._one(
            '''INSERT INTO ops_events (id, site_id, event_mode, type, occurred_at, source, summary, details)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING RETURNING id''',
            (event['id'], event['site_id'], event['event_mode'], event['type'], event['occurred_at'],
             event['source'], event['summary'], Jsonb(event['details'])))
        return row is not None

    def list_events(self, site_id, event_mode):
        return self._all('SELECT id, site_id, type, occurred_at, source, event_mode, summary, details FROM ops_events '
                         'WHERE site_id = %s AND event_mode = %s ORDER BY occurred_at, id', (int(site_id), event_mode))
