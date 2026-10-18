"""Verified NWS point-alert integration. Never used directly by dashboard reads."""
from datetime import datetime, timezone
import json
import os
import urllib.parse
import urllib.request

from . import db
from .ingestion import selected_sites
from .providers import open_provider

FRESHNESS_SECONDS = 600


def fetch_official_alerts(site):
    query = urllib.parse.urlencode({'point': f"{site['latitude']},{site['longitude']}"})
    url = 'https://api.weather.gov/alerts/active?' + query
    request = urllib.request.Request(url, headers={
        'User-Agent': os.environ.get('NWS_USER_AGENT', 'PlanIT-Control/0.2 (utility-site environmental demonstration)'),
        'Accept': 'application/geo+json',
    })
    try:
        with open_provider(request, timeout=12) as response:
            raw = json.load(response)
        if raw.get('type') != 'FeatureCollection' or not isinstance(raw.get('features'), list):
            raise ValueError('Invalid official alert collection.')
        alerts = []
        for feature in raw['features']:
            properties = feature['properties']
            if properties['status'] != 'Actual' or properties.get('messageType') == 'Cancel':
                continue
            identifier = db.text(properties.get('id') or feature.get('id'), 1000)
            event = db.text(properties['event'], 300)
            expires = db.timestamp(properties['expires'])
            effective = db.timestamp(properties['effective'])
            ends = db.timestamp(properties['ends']) if properties.get('ends') else None
            alerts.append({
                'id': identifier, 'event': event, 'severity': properties['severity'],
                'certainty': properties.get('certainty'), 'urgency': properties.get('urgency'),
                'headline': properties.get('headline') or event,
                'description': properties.get('description'), 'instruction': properties.get('instruction'),
                'effective': effective.isoformat(), 'onset': properties.get('onset'),
                'expires': expires.isoformat(), 'ends': ends.isoformat() if ends else None,
                'area_description': properties.get('areaDesc'),
                'source': 'National Weather Service', 'evidence_type': 'official_warning',
            })
        return {'source': 'National Weather Service', 'source_url': url,
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'provider_updated': raw.get('updated'), 'alerts': alerts}
    except Exception:
        raise RuntimeError('Official alert provider unavailable or returned invalid data.') from None


def refresh_official_alerts(*, site_ids=None):
    sites = selected_sites(site_ids)
    succeeded, failed = 0, 0
    for site in sites:
        attempted_at = datetime.now(timezone.utc)
        try:
            payload = fetch_official_alerts(site)
        except RuntimeError:
            db.record_official_alert_failure(site['id'], attempted_at)
            failed += 1
        else:
            db.save_official_alerts(site['id'], payload, attempted_at)
            succeeded += 1
    return {'sites': len(sites), 'succeeded': succeeded, 'failed': failed}


class OfficialAlertRotation:
    def __init__(self, site_ids=None):
        self.site_ids = site_ids
        self.position = 0

    def __call__(self):
        sites = selected_sites(self.site_ids)
        site = sites[self.position % len(sites)]
        self.position += 1
        return refresh_official_alerts(site_ids=[site['id']])
