"""Bounded read-only live provider/model check. No database, worker or demo substitution."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

from backend import db
from backend.hydrology import fetch_context, overnight_advisory
from backend.official_alerts import fetch_official_alerts
from backend.predictions import compute_prediction
from backend.weather import fetch_weather


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-id', type=int, default=663)
    args = parser.parse_args()
    site = next(row for row in db.demo_sites() if row['id'] == args.site_id)
    now = datetime.now(timezone.utc)
    result = {'checked_at': now.isoformat(), 'site_id': site['id'], 'storage': 'not_used',
              'note': 'Actual provider requests; does not demonstrate Tiger Data persistence.'}
    weather = None
    context = {'monitoring': 'UNAVAILABLE'}
    for name, action in [('weather', lambda: fetch_weather(site)), ('hydrology', lambda: fetch_context(site)),
                         ('official_alerts', lambda: fetch_official_alerts(site))]:
        try:
            payload = action()
            result[name] = {'status': 'retrieved', 'source': payload.get('source')}
            if name == 'weather':
                weather = payload
                result[name].update(daily_dates=weather['daily_dates'], daily_units=weather['daily_units'],
                                    timezone=weather['daily_timezone'], hourly_count=len(weather['hourly']['time']))
            if name == 'hydrology':
                context = {**payload, 'monitoring': 'COMPLETE'}
                result[name].update(proximity_status=payload['status'], features=len(payload['features']))
            if name == 'official_alerts': result[name]['active_records'] = len(payload['alerts'])
        except RuntimeError:
            result[name] = {'status': 'unavailable'}
    now = datetime.now(timezone.utc)  # Retrievals completed after the initial probe time.
    tomorrow = now.astimezone(ZoneInfo(site['timezone'])).date() + timedelta(days=1)
    prediction, provenance = compute_prediction(site, {'payload': weather}, tomorrow.isoformat(), now)
    result['prediction'] = prediction
    result['prediction_provenance'] = provenance
    result['flood_advisory'] = overnight_advisory(site, weather, context, now)
    print(json.dumps(result, indent=2))
    return 0 if all(result[key]['status'] == 'retrieved' for key in ('weather', 'hydrology', 'official_alerts')) and prediction['status'] == 'available' else 1


if __name__ == '__main__':
    raise SystemExit(main())
