"""Live weather ingestion. Polling endpoints must not call these functions."""
from datetime import datetime, timezone

from . import db
from .weather import fetch_weather


def selected_sites(site_ids):
    sites = db.list_sites('live')
    if site_ids is not None:
        requested = set(site_ids)
        sites = [site for site in sites if site['id'] in requested]
        if {site['id'] for site in sites} != requested:
            raise ValueError('A requested site ID is not present in the database.')
    if not sites:
        raise ValueError('No database sites are available. Run scripts.seed_database first.')
    return sites


class WeatherRotation:
    """Bound each normal worker tick to one site so other jobs can run."""
    def __init__(self, site_ids=None):
        self.site_ids = site_ids
        self.position = 0

    def __call__(self):
        sites = selected_sites(self.site_ids)
        site = sites[self.position % len(sites)]
        self.position += 1
        return refresh_weather(site_ids=[site['id']])


def refresh_site_weather(site):
    attempted_at = datetime.now(timezone.utc)
    try:
        payload = fetch_weather(site)
    except RuntimeError:
        db.record_weather_failure(site['id'], attempted_at)
        raise
    if payload.get('stale'):
        db.record_weather_failure(site['id'], attempted_at)
    else:
        db.save_weather_snapshot(site['id'], payload, attempted_at)
    return payload


def refresh_weather(*, site_ids=None):
    """Continue after provider failures; database failures stop the job visibly."""
    sites = selected_sites(site_ids)
    succeeded, failed = 0, 0
    for site in sites:
        try:
            payload = refresh_site_weather(site)
        except db.DatabaseUnavailable:
            raise
        except RuntimeError:
            failed += 1
        else:
            if payload.get('stale'):
                failed += 1
            else:
                succeeded += 1
    return {'sites': len(sites), 'succeeded': succeeded, 'failed': failed}
