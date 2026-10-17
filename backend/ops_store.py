"""Persistence for Workstream B behind one small interface.

PostgresStore is the shared, durable store used by the running app (tables in
backend/schema.sql under "Workstream B"). MemoryStore exists for tests only and
is never used as a silent fallback for a failed database.
"""
import copy
from contextlib import contextmanager, nullcontext
from typing import Protocol


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
