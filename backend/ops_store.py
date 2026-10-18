"""Persistence for Workstream B behind one small interface.

PostgresStore delegates to the shared adapter backend/db.py: A's repositories for
lightning_events/lightning_holds, crew_reports and briefings, plus B's ops_* functions
for lightning_feed_status, replay_sessions and ops_events (migration 003).
MemoryStore mirrors those shapes for offline tests; it is never a fallback for a
failed database.
"""
import copy
import uuid
from contextlib import nullcontext
from datetime import timedelta
from typing import Protocol

from . import db

HOLD = timedelta(minutes=30)


class OpsStore(Protocol):
    def batch(self): ...
    def list_sites(self): ...
    def get_site(self, site_id): ...
    def store_strike(self, strike, affected_site_ids): ...
    def get_hold(self, site_id, event_mode): ...
    def list_holds(self, event_mode): ...
    def record_feed(self, event_mode, source, received_at=None, checked_at=None): ...
    def get_feeds(self, event_mode): ...
    def start_replay_session(self, session): ...
    def get_replay_session(self): ...
    def reset_replay(self): ...
    def create_report(self, fields): ...
    def list_reports(self, site_id, event_mode, unresolved_only=False): ...
    def get_report(self, report_id): ...
    def get_report_photo(self, report_id): ...
    def resolve_report(self, report_id, now): ...
    def save_briefing(self, briefing): ...
    def get_briefing(self, site_id, delivery_local_date, event_mode): ...
    def list_briefings(self, site_id, event_mode): ...
    def add_event(self, event): ...
    def list_events(self, site_id, event_mode): ...


REPORT_KEYS = ('id', 'site_id', 'event_mode', 'observed_at', 'created_at', 'latitude', 'longitude',
               'category', 'note', 'photo_content_type', 'resolved_at')


def _empty_data():
    return {'lightning_events': {}, 'holds': {}, 'feeds': {}, 'replay_sessions': {}, 'reports': {},
            'briefings': {}, 'events': {}}


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

    def store_strike(self, strike, affected_site_ids):
        """Same semantics as db.store_lightning_event: dedupe, then GREATEST hold_until/last_strike_at."""
        key = (strike['event_mode'], strike['source'], strike['event_id'])
        if key in self.data['lightning_events']:
            return False
        self.data['lightning_events'][key] = dict(strike)
        until, at = strike['occurred_at'] + HOLD, strike['occurred_at']
        for site_id in set(affected_site_ids):
            hold = self.data['holds'].get((site_id, strike['event_mode']))
            if hold is None:
                self.data['holds'][(site_id, strike['event_mode'])] = {
                    'site_id': site_id, 'hold_until': until, 'last_strike_at': at, 'source': strike['source']}
                continue
            if at >= hold['last_strike_at']:
                hold['source'] = strike['source']
            hold['hold_until'] = max(hold['hold_until'], until)
            hold['last_strike_at'] = max(hold['last_strike_at'], at)
        return True

    def get_hold(self, site_id, event_mode):
        hold = self.data['holds'].get((int(site_id), event_mode))
        return dict(hold) if hold else None

    def list_holds(self, event_mode):
        return [dict(h) for (_, mode), h in self.data['holds'].items() if mode == event_mode]

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
        self.data['lightning_events'] = {k: v for k, v in self.data['lightning_events'].items() if k[0] != 'replay'}
        self.data['holds'] = {k: v for k, v in self.data['holds'].items() if k[1] != 'replay'}
        self.data['feeds'] = {k: v for k, v in self.data['feeds'].items() if k[0] != 'replay'}
        for name in ('briefings', 'events', 'reports'):
            self.data[name] = {k: v for k, v in self.data[name].items() if v['event_mode'] != 'replay'}
        for session in self.data['replay_sessions'].values():
            session['active'] = False

    def create_report(self, fields):
        report_id = str(uuid.uuid4())
        row = {k: fields.get(k) for k in REPORT_KEYS}
        row.update(id=report_id, created_at=fields['observed_at'], resolved_at=None, photo=fields['photo'])
        self.data['reports'][report_id] = row
        return report_id

    def _report(self, row):
        return {k: row[k] for k in REPORT_KEYS}

    def list_reports(self, site_id, event_mode, unresolved_only=False):
        rows = [self._report(r) for r in self.data['reports'].values()
                if r['site_id'] == int(site_id) and r['event_mode'] == event_mode
                and not (unresolved_only and r['resolved_at'] is not None)]
        return sorted(rows, key=lambda r: (r['observed_at'], r['id']), reverse=True)

    def get_report(self, report_id):
        row = self.data['reports'].get(str(report_id))
        return self._report(row) if row else None

    def get_report_photo(self, report_id):
        row = self.data['reports'].get(str(report_id))
        return {'data': row['photo'], 'content_type': row['photo_content_type']} if row else None

    def resolve_report(self, report_id, now):
        row = self.data['reports'].get(str(report_id))
        if not row:
            return None
        if row['resolved_at'] is None:
            row['resolved_at'] = now
        return self._report(row)

    def save_briefing(self, briefing):
        """Returns (id, created). Unique on (site_id, delivery_local_date, event_mode)."""
        key = (briefing['site_id'], briefing['delivery_local_date'], briefing['event_mode'])
        if key in self.data['briefings']:
            return self.data['briefings'][key]['id'], False
        stored = copy.deepcopy(briefing)
        stored['id'] = str(uuid.uuid4())
        self.data['briefings'][key] = stored
        return stored['id'], True

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


class PostgresStore:
    """Shared Tiger Data store; every method delegates to backend/db.py. Failures raise db.DatabaseUnavailable (503)."""

    def batch(self):
        return nullcontext()  # db.py functions each manage their own connection and transaction.

    def list_sites(self):
        return db.list_sites('live')

    def get_site(self, site_id):
        return next((s for s in db.list_sites('live') if s['id'] == int(site_id)), None)

    def store_strike(self, strike, affected_site_ids):
        return db.store_lightning_event(
            source=strike['source'], event_id=strike['event_id'], occurred_at=strike['occurred_at'],
            latitude=strike['latitude'], longitude=strike['longitude'],
            affected_site_ids=list(affected_site_ids), mode=strike['event_mode'])['accepted']

    def get_hold(self, site_id, event_mode):
        return db.get_lightning_holds(mode=event_mode).get(int(site_id))

    def list_holds(self, event_mode):
        return list(db.get_lightning_holds(mode=event_mode).values())

    def record_feed(self, event_mode, source, received_at=None, checked_at=None):
        db.ops_record_feed(mode=event_mode, source=source, received_at=received_at, checked_at=checked_at)

    def get_feeds(self, event_mode):
        return db.ops_get_feeds(mode=event_mode)

    def start_replay_session(self, session):
        db.ops_start_replay_session(session_id=session['session_id'], started_at=session['started_at'],
                                    replay_epoch=session['replay_epoch'], speed=session['speed'])

    def get_replay_session(self):
        return db.ops_get_replay_session()

    def reset_replay(self):
        db.ops_reset_replay()

    def create_report(self, fields):
        return db.save_crew_report(
            site_id=fields['site_id'], latitude=fields['latitude'], longitude=fields['longitude'],
            category=fields['category'], note=fields['note'], observed_at=fields['observed_at'],
            photo=fields['photo'], photo_content_type=fields['photo_content_type'], mode=fields['event_mode'])

    def list_reports(self, site_id, event_mode, unresolved_only=False):
        return [dict(r, event_mode=event_mode)
                for r in db.list_crew_reports(site_id=int(site_id), mode=event_mode, unresolved_only=unresolved_only)]

    def get_report(self, report_id):
        return db.ops_get_crew_report(report_id)

    def get_report_photo(self, report_id):
        try:
            row = db.get_report_photo(report_id, mode='live')
        except ValueError:
            return None
        return {'data': row['photo'], 'content_type': row['photo_content_type']} if row else None

    def resolve_report(self, report_id, now):
        return db.ops_resolve_crew_report(report_id, resolved_at=now)

    def save_briefing(self, briefing):
        existing = self.get_briefing(briefing['site_id'], briefing['delivery_local_date'], briefing['event_mode'])
        if existing:
            return existing['id'], False
        briefing_id = db.save_briefing(
            site_id=briefing['site_id'], delivery_local_date=briefing['delivery_local_date'],
            target_date=briefing['forecast_target_date'], body=briefing['body_text'], facts=briefing,
            mode=briefing['event_mode'])
        return briefing_id, True

    @staticmethod
    def _briefing(row):
        return dict(row['facts'], id=row['id']) if row else None

    def get_briefing(self, site_id, delivery_local_date, event_mode):
        return self._briefing(db.ops_get_briefing(site_id=int(site_id), delivery_local_date=delivery_local_date, mode=event_mode))

    def list_briefings(self, site_id, event_mode):
        return [self._briefing(r) for r in db.list_briefings(site_id=site_id, mode=event_mode)]

    def add_event(self, event):
        return db.ops_add_event(
            event_id=event['id'], site_id=event['site_id'], mode=event['event_mode'], type=event['type'],
            occurred_at=event['occurred_at'], source=event['source'], summary=event['summary'],
            ref_table=event['ref_table'], ref_key=event['ref_key'], details=event['details'])

    def list_events(self, site_id, event_mode):
        return db.ops_list_events(site_id=int(site_id), mode=event_mode)
