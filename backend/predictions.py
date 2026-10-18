"""Saved-model inference from complete provider DAILY forecasts; no safety fallback."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from zoneinfo import ZoneInfo

from . import db

UNITS = {'temperature_2m_max': '\u00b0C', 'precipitation_sum': 'mm', 'wind_gusts_10m_max': 'km/h'}
FRESHNESS_SECONDS = 1800


def daily_features(weather, site, target_date):
    if not weather or weather.get('daily_timezone') != site['timezone']:
        return None
    dates = weather.get('daily_dates', [])
    if dates.count(target_date) != 1:
        return None
    position = dates.index(target_date)
    daily, units = weather.get('daily', {}), weather.get('daily_units', {})
    if any(units.get(key) != unit or not isinstance(daily.get(key), list)
           or len(daily[key]) != len(dates) for key, unit in UNITS.items()):
        return None
    return {key: daily[key][position] for key in UNITS}


def training_geography(site):
    """Unknown until a verified crosswalk and training manifest are available."""
    path = db.ROOT / 'ml/output/manifest.json'
    mapping_path = db.ROOT / 'ml/output/site_counties.json'
    if not path.exists() or not mapping_path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        results = json.loads((db.ROOT / 'ml/results.json').read_text(encoding='utf-8'))
        if manifest['dataset_sha256'] != results['dataset_sha256']:
            return None
        mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
        matches = {row['county_fips'] for row in mapping
                   if row['state'] == site['state'] and row['county'] == site['county']}
        if len(matches) != 1:
            return None
        return next(iter(matches)) not in {row['county_fips'] for row in manifest['selected_counties']}
    except (ValueError, KeyError, TypeError):
        return None


def compute_prediction(site, record, target_date, now, predictor=None):
    weather = record.get('payload') or {}
    provenance = {'model_artifact': 'ml/artifacts/model.joblib', 'source': weather.get('source'),
                  'weather_fetched_at': weather.get('fetched_at'), 'input_kind': 'full_local_day_forecast',
                  'input_units': UNITS, 'timezone': site['timezone'], 'forecast_date': target_date,
                  'outside_training_counties': training_geography(site),
                  'note': 'Historical observed-weather evaluation does not establish forecast performance.'}
    result = {'status': 'unavailable', 'model_index': None, 'probability': None,
              'target_date': target_date, 'model_version': 'unavailable', 'feature_version': 'daily-weather-v1',
              'computed_at': now.isoformat(), 'outside_training_range': []}
    try:
        age = (now - db.timestamp(weather['fetched_at'])).total_seconds()
    except (KeyError, ValueError, TypeError):
        age = -1
    features = daily_features(weather, site, target_date)
    if not 0 <= age <= FRESHNESS_SECONDS or record.get('error_code'):
        result['reason'] = 'Forecast retrieval is unavailable, stale or its latest refresh failed.'
    elif features is None:
        result['reason'] = 'Complete site-local DAILY forecast inputs with compatible units are unavailable.'
    else:
        if predictor is None:
            try:
                from ml.predict import explain_site
                predictor = explain_site
            except ImportError:
                result['reason'] = 'Model dependencies unavailable; install ml/requirements.txt.'
        if predictor is not None:
            result = predictor(features, target_date=target_date)
            provenance['features'] = features
    artifact = db.ROOT / provenance['model_artifact']
    if artifact.exists():
        provenance['artifact_sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    provenance.update({key: result.get(key) for key in ('reason', 'model_contributions', 'outside_training_range')})
    return result, provenance


def refresh_predictions(*, now=None, site_ids=None, records=None):
    now = now or datetime.now(timezone.utc)
    sites = db.list_sites('live')
    records = db.latest_weather() if records is None else records
    succeeded = failed = 0
    for site in sites:
        if site_ids is not None and site['id'] not in site_ids:
            continue
        today = now.astimezone(ZoneInfo(site['timezone'])).date()
        for day in (today, today + timedelta(days=1)):
            result, provenance = compute_prediction(site, records.get(site['id'], {}), day.isoformat(), now)
            db.save_prediction(site_id=site['id'], valid_date=day, model_version=result.get('model_version') or 'unavailable',
                               feature_version=result['feature_version'], score=result['model_index'],
                               computed_at=now, provenance=provenance, mode='live', status=result['status'],
                               probability=result.get('probability'), outside_training_range=result.get('outside_training_range') or [],
                               outside_training_counties=provenance['outside_training_counties'])
            succeeded += result['status'] == 'available'
            failed += result['status'] != 'available'
    return {'succeeded': succeeded, 'failed': failed}


def refresh_weather_and_predictions(*, site_ids=None):
    """Persist each fresh snapshot and its two model scores before advancing sites."""
    from .ingestion import refresh_site_weather, selected_sites
    succeeded = failed = 0
    model_succeeded = model_failed = 0
    for site in selected_sites(site_ids):
        try:
            weather = refresh_site_weather(site)
        except db.DatabaseUnavailable:
            raise
        except RuntimeError:
            failed += 1
            continue
        stale = bool(weather.get('stale'))
        succeeded += not stale
        failed += stale
        result = refresh_predictions(site_ids=[site['id']], records={site['id']: {
            'payload': weather, 'error_code': 'weather_unavailable' if stale else None}})
        model_succeeded += result['succeeded']
        model_failed += result['failed']
    return {'succeeded': succeeded, 'failed': failed, 'predictions_succeeded': model_succeeded,
            'predictions_failed': model_failed}


class WeatherPredictionRotation:
    def __init__(self, site_ids=None):
        self.site_ids, self.position = site_ids, 0

    def __call__(self):
        from .ingestion import selected_sites
        sites = selected_sites(self.site_ids)
        site = sites[self.position % len(sites)]
        self.position += 1
        return refresh_weather_and_predictions(site_ids=[site['id']])


def worker_jobs():
    from .worker import Job
    return [Job('predictions', PredictionRotation(), 15)]


class PredictionRotation:
    """At most one site's two daily predictions per regular worker callback."""
    def __init__(self, site_ids=None):
        self.site_ids, self.position = site_ids, 0

    def __call__(self):
        from .ingestion import selected_sites
        sites = selected_sites(self.site_ids)
        site = sites[self.position % len(sites)]
        self.position += 1
        return refresh_predictions(site_ids=[site['id']])
