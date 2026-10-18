"""Next-day safety briefings delivered at 6 PM in each site's local timezone.

Deterministic template first. Missing inputs are stated, never filled in.
delivery_local_date is the site-local date of the 6 PM delivery; forecast_target_date
is the next local day. One briefing per (site_id, delivery_local_date, event_mode).
"""
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

from .lightning import LiveSource, coverage
from .ops_common import iso, mode_label, parse_iso, utc_now
from .reports import report_view

DELIVERY_TIME = time(18, 0)
GENERATOR = 'template-v1'
HOLD_TYPES = ('lightning_hold_started', 'lightning_hold_extended')
FORECAST_LABELS = {
    'temperature_2m_max': 'Maximum air temperature',
    'temperature_2m_min': 'Minimum air temperature',
    'apparent_temperature_max': 'Maximum apparent temperature (modeled; not the NWS heat index)',
    'precipitation_sum': 'Total precipitation',
    'precipitation_probability_max': 'Maximum precipitation probability',
    'wind_gusts_10m_max': 'Maximum wind gust',
    'heat_index_max_f': 'Maximum heat index (derived from the modeled forecast with the NWS formula; not an official NWS value)',
    'precipitation_sum_mm': 'Total precipitation',
    'soil_moisture_max_m3_m3': 'Maximum shallow soil moisture (modeled; not a trafficability measurement)',
}
PLANNING_UNITS = {'heat_index_max_f': '°F', 'precipitation_sum_mm': 'mm', 'soil_moisture_max_m3_m3': 'm³/m³'}
NOTE = ('Generated from supplied facts only. Forecasts, official alerts, crew reports and the experimental '
        'model index are different kinds of evidence. Missing inputs are listed, not filled in.')


def site_local(site, now):
    return now.astimezone(ZoneInfo(site['timezone']))


def due_date(site, now):
    """Site-local delivery date if 6 PM local has arrived, else None (DST-safe via zoneinfo)."""
    local = site_local(site, now)
    return local.date() if local.time() >= DELIVERY_TIME else None


def _as_date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def _local_clock(site, value):
    return site_local(site, value).strftime('%H:%M')


def _forecast_section(inputs, target, missing):
    forecast = inputs.get('forecast')
    lines = []
    if forecast is None:
        missing.append('forecast')
        return {'key': 'forecast', 'title': "Tomorrow's forecast", 'evidence_type': 'forecast', 'available': False,
                'lines': ['Forecast unavailable: no stored next-day forecast for this site. No forecast values are shown.']}
    lines.append(f"Forecast from {forecast.get('source') or 'unknown source'}, valid for {forecast.get('valid_date')} "
                 f"(site-local day), retrieved {forecast.get('retrieved_at') or 'at an unknown time'}.")
    if forecast.get('stale'):
        missing.append('fresh forecast')
        lines.append('STALE forecast: retained values do not establish current forecast conditions.')
    if forecast.get('valid_date') != target:
        lines.append(f'Note: this forecast is not for the target date {target}.')
        missing.append('forecast for target date')
    for key, entry in (forecast.get('values') or {}).items():
        label = FORECAST_LABELS.get(key, key)
        if entry is None or entry.get('value') is None:
            lines.append(f'{label}: unavailable')
            missing.append(f'forecast {key}')
        else:
            lines.append(f"{label}: {entry['value']} {entry.get('unit') or ''}".rstrip())
    periods = forecast.get('hazardous_periods')
    if periods:
        lines.append('Illustrative forecast planning periods (not official warnings):')
        lines.extend(f"- {period['local_time']}: {', '.join(period['signals'])}." for period in periods)
    elif periods is not None:
        lines.append('No configured planning threshold exceeded in available hourly forecasts; other hazards may exist.')
    return {'key': 'forecast', 'title': "Tomorrow's forecast", 'evidence_type': 'forecast', 'available': True, 'lines': lines}


def _evidence_section(site, inputs, missing):
    lines = []
    alerts = inputs.get('active_alerts')
    if inputs.get('alerts_monitoring') == 'STALE':
        missing.append('fresh official alerts')
        lines.append('Official monitoring is STALE; retained warnings may be incomplete.')
    if alerts is None:
        missing.append('official alerts')
        lines.append('Official alerts: unavailable. The absence of alerts here is not evidence that no warnings exist.')
    elif not alerts:
        lines.append(f"Official alerts: none active in the ingested official alert data (monitoring {inputs.get('alerts_monitoring') or 'state unknown'}).")
    else:
        for alert in alerts:
            lines.append(f"Official alert: {alert.get('event')} ({alert.get('source') or 'official source'}), "
                         f"expires {alert.get('expires') or 'unknown'}.")
    advisory = inputs.get('flood_advisory') or {}
    if advisory.get('active'):
        lines.append('Illustrative rainfall/stream advisory: ' + advisory['reason'])
        lines.append(advisory['recommended_action'])
    for layer in inputs.get('unavailable_layers') or []:
        missing.append(layer)
    holds = inputs.get('lightning_today') or []
    if holds:
        started = sum(1 for e in holds if e['type'] == 'lightning_hold_started')
        last_until = max(e['details']['hold_until'] for e in holds)
        local_end = _local_clock(site, parse_iso(last_until, 'hold_until'))
        lines.append(f'Lightning holds today: {started} hold(s) started, {len(holds) - started} extension(s); '
                     f'latest hold end {local_end} site-local ({last_until}).')
    else:
        lines.append('Lightning holds today: none recorded.')
    cov = inputs.get('lightning_coverage') or {}
    if cov.get('status') != 'COMPLETE':
        missing.append('lightning feed')
        lines.append(f"Lightning monitoring coverage: {cov.get('status') or 'UNAVAILABLE'}. {cov.get('note') or ''}".rstrip())
    reports = inputs.get('unresolved_reports')
    source = ' (real crew reports, not simulated)' if inputs.get('reports_are_live_in_replay') else ''
    if reports is None:
        missing.append('crew reports')
        lines.append('Crew reports: unavailable.')
    elif not reports:
        lines.append(f'Unresolved crew reports{source}: none. No recent reports does not mean no hazard.')
    else:
        lines.append(f'Unresolved crew reports{source}: {len(reports)}.')
        for report in reports:
            note = f": {report['note']}" if report.get('note') else ''
            lines.append(f"- {report['category']}{note} (reported {report['created_at']})")
    return {'key': 'today_evidence', 'title': "Today's evidence", 'evidence_type': 'today_evidence', 'available': True, 'lines': lines}


def _model_section(inputs, target, missing):
    model = inputs.get('model')
    title = 'Experimental model index'
    if model is None:
        missing.append('model index')
        return {'key': 'model', 'title': title, 'evidence_type': 'experimental_model_index', 'available': False,
                'lines': ['Experimental model index: unavailable (no saved prediction for the target date).']}
    if model.get('model_index') is None:
        missing.append('model index')
        reason = model.get('reason') or model.get('note') or 'no reason given'
        return {'key': 'model', 'title': title, 'evidence_type': 'experimental_model_index', 'available': False,
                'lines': [f'Experimental model index: unavailable ({reason}).']}
    lines = [f"Experimental model index (0-10; not a probability or calibrated risk): {float(model['model_index']):.1f} "
             f"for {model.get('target_date')}.",
             'Daily model output for the whole local day, not an hourly forecast. It does not override official alerts.']
    if model.get('target_date') != target:
        lines.append(f'Note: the model output is not for the target date {target}.')
    if model.get('outside_training_counties') is True:
        lines.append('Outside training counties: this site is outside the counties the model was trained on (geographic extrapolation).')
    elif model.get('outside_training_counties') is None:
        lines.append('Training-county status: unknown.')
    if model.get('outside_training_range'):
        lines.append(f"Inputs outside the training range: {', '.join(model['outside_training_range'])}.")
    lines.append(f"Model version {model.get('model_version') or 'unknown'}.")
    lines.append('Historical observed-weather evaluation does not establish next-day forecast performance.')
    return {'key': 'model', 'title': title, 'evidence_type': 'experimental_model_index', 'available': True, 'lines': lines}


def generate_briefing(site, delivery_local_date, inputs, event_mode, now, trigger='scheduled', rewriter=None):
    """Pure: build one briefing from supplied inputs. No I/O except the optional rewriter."""
    delivery = _as_date(delivery_local_date)
    target = (delivery + timedelta(days=1)).isoformat()
    missing = []
    sections = [_forecast_section(inputs, target, missing), _evidence_section(site, inputs, missing), _model_section(inputs, target, missing)]
    sections.append({'key': 'precautions', 'title': 'Suggested planning precautions', 'evidence_type': 'planning_guidance',
                     'available': True, 'lines': ['Review active official instructions and the site supervisor’s work plan.',
                     'Plan heat breaks, water and shade under site procedures; inspect wet access routes and crew hazard pins.',
                     'Maintain any active lightning stop-work hold; verify missing monitoring before making work decisions.']})
    sections.append({'key': 'missing_data', 'title': 'Missing data', 'evidence_type': 'missing_data', 'available': True,
                     'lines': [f'Missing: {item}.' for item in missing] or ['No missing inputs among those this briefing uses.']})
    prefix = 'SIMULATED REPLAY. ' if event_mode == 'replay' else ''
    header = (f"{prefix}Next-day briefing for {site['name']} ({site['timezone']}). Delivery date {delivery.isoformat()} "
              f"at 6:00 PM site-local time; forecast target date {target}.")
    body = '\n\n'.join([header] + [s['title'] + '\n' + '\n'.join(s['lines']) for s in sections])
    rewritten, status = None, 'not_requested'
    if rewriter is not None:
        try:
            rewritten = rewriter(body) or None
            status = 'rewritten' if rewritten else 'failed_fallback_template'
        except Exception:
            status = 'failed_fallback_template'
    return {
        'id': f"{event_mode}:{site['id']}:{delivery.isoformat()}", 'site_id': site['id'], 'site_name': site['name'],
        'timezone': site['timezone'], 'event_mode': event_mode, 'label': mode_label(event_mode), 'trigger': trigger,
        'delivery_local_date': delivery.isoformat(), 'scheduled_local_time': DELIVERY_TIME.strftime('%H:%M'),
        'forecast_target_date': target, 'delivered_at': iso(now) if trigger != 'preview' else None,
        'delivered_local_time': site_local(site, now).isoformat() if trigger != 'preview' else None,
        'generator': GENERATOR, 'rewrite_status': status, 'sections': sections, 'missing_inputs': missing,
        'body_text': body, 'rewritten_text': rewritten, 'note': NOTE,
    }


def deliver_briefing(store, site, delivery_local_date, inputs, event_mode, now, trigger='scheduled', rewriter=None):
    """Idempotent: returns (briefing, created). The briefings table allows one row per site/mode/local date."""
    delivery = _as_date(delivery_local_date).isoformat()
    existing = store.get_briefing(site['id'], delivery, event_mode)
    if existing:
        return existing, False
    _, created = store.save_briefing(generate_briefing(site, delivery, inputs, event_mode, now, trigger, rewriter))
    return store.get_briefing(site['id'], delivery, event_mode), created


def _outlook_facts(row):
    """Map one A Outlook row (serialized) to briefing inputs. Absent values stay None (shown as unavailable)."""
    if row is None:
        return {}
    facts = {'unavailable_layers': row.get('unavailable_layers'), 'flood_advisory': row.get('flood_advisory')}
    planning, weather = row.get('planning_weather') or {}, row.get('weather') or {}
    if weather:
        facts['forecast'] = {
            'source': planning.get('source'), 'valid_date': planning.get('target_date'), 'retrieved_at': weather.get('fetched_at'),
            'stale': weather.get('stale', False), 'hazardous_periods': planning.get('hazardous_periods'),
            'values': {key: {'value': planning.get(key), 'unit': unit} for key, unit in PLANNING_UNITS.items()}}
    monitoring = (row.get('official_alerts_monitoring') or {}).get('state')
    if monitoring in ('COMPLETE', 'STALE') and row.get('alerts') is not None:
        facts['active_alerts'] = [{'event': a.get('event'), 'source': 'NWS', 'expires': a.get('expires')} for a in row['alerts']]
        facts['alerts_monitoring'] = monitoring
    prediction = row.get('prediction')
    if prediction:
        provenance = prediction.get('provenance') or {}
        facts['model'] = {'model_index': prediction.get('score'), 'target_date': prediction.get('valid_date'),
                          'model_version': prediction.get('model_version'),
                          'outside_training_range': prediction.get('outside_training_range') or provenance.get('outside_training_range') or [],
                          'outside_training_counties': prediction.get('outside_training_counties', provenance.get('outside_training_counties')),
                          'reason': provenance.get('reason') or ('Stored prediction is stale.' if prediction.get('stale') else None)}
    return facts


def store_inputs_provider(store, live_source=None, replay_session=None, outlook=None):
    """Lightning and reports from the shared store; forecast, official alerts and model from A's Outlook rows.

    outlook is a callable(now) returning build_outlook('live')-style rows, loaded at most once. Missing facts stay None.
    """
    cache = {}

    def outlook_row(site_id, now):
        if outlook is None:
            return None
        if 'rows' not in cache:
            result = outlook(now)
            cache['rows'] = {r['site']['id']: r for r in (result or {}).get('sites', [])}
        return cache['rows'].get(site_id)

    def provider(site, delivery_local_date, event_mode, now):
        day = _as_date(delivery_local_date)
        holds = [e for e in store.list_events(site['id'], event_mode)
                 if e['type'] in HOLD_TYPES and site_local(site, e['occurred_at']).date() == day]
        # Crew reports are always real (event_mode "live"); replay briefings read them without changing them.
        unresolved = [report_view(r, site) for r in store.list_reports(site['id'], 'live', unresolved_only=True)]
        inputs = {'forecast': None, 'active_alerts': None, 'model': None, 'lightning_today': holds,
                  'lightning_coverage': coverage(store, event_mode, now, live_source or LiveSource(), replay_session),
                  'unresolved_reports': unresolved, 'reports_are_live_in_replay': event_mode == 'replay'}
        inputs.update(_outlook_facts(outlook_row(site['id'], now)))
        return inputs
    return provider


def run_due_briefings(now, store, sites=None, inputs_provider=None, event_mode='live', rewriter=None):
    """For the single worker: deliver every briefing whose site-local 6 PM has arrived and that does not exist yet."""
    results = []
    with store.batch():
        sites = sites if sites is not None else store.list_sites()
        due = [(site, due_date(site, now)) for site in sites]
        due = [(site, day) for site, day in due if day is not None]
        if not due:
            return results
        existing = {(b['site_id'], b['delivery_local_date']) for b in store.list_briefings(None, event_mode)}
        provider = inputs_provider or store_inputs_provider(store)
        for site, day in due:
            if (site['id'], day.isoformat()) in existing:
                continue
            inputs = provider(site, day, event_mode, now)
            briefing, created = deliver_briefing(store, site, day, inputs, event_mode, now, 'scheduled', rewriter)
            results.append({'site_id': site['id'], 'delivery_local_date': briefing['delivery_local_date'], 'created': created})
    return results


def scheduled_briefings(*, site_ids=None):
    """Worker callback (no arguments): live briefings for every site whose local 6 PM has passed."""
    from .ops_store import PostgresStore
    from .outlook import build_outlook
    store, now = PostgresStore(), utc_now()
    provider = store_inputs_provider(store, outlook=lambda at: build_outlook('live', now=at))
    sites = None if site_ids is None else [site for site in store.list_sites() if site['id'] in site_ids]
    results = run_due_briefings(now, store, sites=sites, inputs_provider=provider)
    return {'created': sum(r['created'] for r in results), 'attempted': len(results)}


def worker_jobs():
    """Register with A's single worker: python -m backend.worker --job-module backend.briefings:worker_jobs"""
    from .worker import Job
    return [Job('briefings', scheduled_briefings, 30)]
