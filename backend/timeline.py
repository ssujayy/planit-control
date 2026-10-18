"""Per-site chronological evidence timeline, derived from the canonical records.

- Hold started/extended: ops_events rows, each referencing its lightning_events row.
- Hold expired: computed from those events and the current lightning_holds.hold_until.
- Report created/resolved: read from crew_reports (always event_mode "live").
- Briefing delivered: read from briefings.
Live queries return only live records. Replay queries return replay records plus live
crew reports (which keep event_mode "live"); replay records never appear in live queries.
"""
from .briefings import HOLD_TYPES
from .ops_common import iso, mode_label, parse_iso

EXPIRED_SUMMARY = ('Lightning hold countdown ended. Only the lightning hold is lifted; other hazards '
                   'and lightning feed coverage are unchanged.')
EMPTY_NOTE = 'No operational events recorded for this site. This does not mean there is no hazard.'


def _at(value):
    return parse_iso(value, 'timestamp') if isinstance(value, str) else value


def derive_expirations(hold_events, now, current_hold_until=None):
    """Expiry times at the end of each hold episode whose hold_until has passed."""
    expired, current = [], None
    for event in sorted(hold_events, key=lambda e: (e['occurred_at'], e['id'])):
        if event['type'] == 'lightning_hold_started' and current is not None and current <= event['occurred_at']:
            expired.append(current)
        until = _at(event['details']['hold_until'])
        current = until if current is None else max(current, until)
    if current is not None and current_hold_until is not None:
        current = max(current, current_hold_until)  # lightning_holds is the source of truth for the latest value
    if current is not None and current <= now:
        expired.append(current)
    return expired


def _event(event_id, site_id, kind, occurred_at, source, event_mode, summary, ref_table, ref_key, details):
    return {'id': event_id, 'site_id': site_id, 'type': kind, 'occurred_at': occurred_at, 'source': source,
            'event_mode': event_mode, 'summary': summary, 'ref_table': ref_table, 'ref_key': ref_key, 'details': details}


def _hold_events(store, site, event_mode, now):
    stored = [e for e in store.list_events(site['id'], event_mode) if e['type'] in HOLD_TYPES and e['occurred_at'] <= now]
    hold = store.get_hold(site['id'], event_mode)
    prefix = 'Simulated replay: ' if event_mode == 'replay' else ''
    expired = [_event(f"{event_mode}:hold-expired:{site['id']}:{iso(until)}", site['id'], 'lightning_hold_expired', until,
                      'planit-control (computed from hold_until)', event_mode, prefix + EXPIRED_SUMMARY, 'lightning_holds',
                      {'site_id': site['id'], 'event_mode': event_mode}, {'hold_until': iso(until), 'clears_only': 'lightning_hold'})
               for until in derive_expirations(stored, now, hold['hold_until'] if hold else None)]
    return stored + expired


def _report_events(store, site, now):
    events = []
    for report in store.list_reports(site['id'], 'live'):
        ref = {'id': report['id']}
        details = {'report_id': report['id'], 'category': report['category'], 'has_photo': True}
        if report['created_at'] <= now:
            events.append(_event(f"live:report:{report['id']}:created", site['id'], 'report_created', report['created_at'],
                                 'crew_report', 'live', f"Crew report ({report['category']}) with photo: {report['note'][:80]}",
                                 'crew_reports', ref, details))
        if report['resolved_at'] and report['resolved_at'] <= now:
            events.append(_event(f"live:report:{report['id']}:resolved", site['id'], 'report_resolved', report['resolved_at'],
                                 'crew_report', 'live', f"Crew report ({report['category']}) marked resolved; it stays in site history.",
                                 'crew_reports', ref, details))
    return events


def _briefing_events(store, site, event_mode, now):
    events = []
    prefix = 'Simulated replay: ' if event_mode == 'replay' else ''
    for briefing in store.list_briefings(site['id'], event_mode):
        delivered = _at(briefing['delivered_at'])
        if delivered <= now:
            events.append(_event(f"{event_mode}:briefing:{briefing['id']}", site['id'], 'briefing_delivered', delivered,
                                 'planit-control briefing generator', event_mode,
                                 f"{prefix}Next-day briefing delivered for {briefing['forecast_target_date']} (forecast target date).",
                                 'briefings', {'id': briefing['id']},
                                 {'briefing_id': briefing['id'], 'delivery_local_date': briefing['delivery_local_date'],
                                  'forecast_target_date': briefing['forecast_target_date'], 'trigger': briefing['trigger'],
                                  'missing_inputs': briefing['missing_inputs']}))
    return events


def event_view(event):
    return {**event, 'occurred_at': iso(event['occurred_at'])}


def site_timeline(store, site, event_mode, now):
    events = _hold_events(store, site, event_mode, now) + _report_events(store, site, now) + _briefing_events(store, site, event_mode, now)
    events.sort(key=lambda e: (e['occurred_at'], e['id']))
    includes = ['live events only'] if event_mode == 'live' else ['simulated replay events', 'live crew reports (event_mode "live")']
    return {'site_id': site['id'], 'event_mode': event_mode, 'label': mode_label(event_mode), 'as_of': iso(now),
            'includes': includes, 'events': [event_view(e) for e in events], 'count': len(events),
            'note': EMPTY_NOTE if not events else None}
