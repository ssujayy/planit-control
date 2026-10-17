"""Pure inference interface; no database, Flask, or worker ownership."""
import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path
from datetime import date, datetime, timezone

import joblib
import pandas as pd

from .common import ROOT, DAILY, FEATURES, season


def predict_site(features, target_date, artifact_path=None):
    """Daily local-time aggregates: Celsius, mm/day, km/h maximum gust.

    Only load trusted artifacts. Joblib/pickle files can execute code.
    """
    output = {'status': 'unavailable', 'model_index': None, 'probability': None,
              'target_date': target_date, 'model_version': None,
              'feature_version': 'daily-weather-v1',
              'computed_at': datetime.now(timezone.utc).isoformat()}
    try:
        day = date.fromisoformat(target_date)
    except (ValueError, TypeError):
        return {**output, 'reason': 'target_date must be YYYY-MM-DD'}
    if not isinstance(features, Mapping):
        return {**output, 'reason': 'features must be a mapping of daily numeric values'}
    cleaned = {}
    for key in DAILY:
        value = features.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return {**output, 'reason': f'Missing/nonfinite numeric feature: {key}'}
        cleaned[key] = float(value)
    if cleaned['precipitation_sum'] < 0 or cleaned['wind_gusts_10m_max'] < 0:
        return {**output, 'reason': 'Precipitation and gust must be nonnegative'}
    path = artifact_path or ROOT / 'ml/artifacts/model.joblib'
    if not Path(path).exists():
        return {**output, 'reason': 'Trained model artifact unavailable'}
    try:
        bundle = joblib.load(path)
        if (bundle['features'] != FEATURES
                or bundle['feature_version'] != output['feature_version']):
            return {**output, 'reason': 'Trained model feature contract is incompatible'}
        row = {**cleaned, **season(day)}
        probabilities = bundle['model'].predict_proba(pd.DataFrame([row])[bundle['features']])
        classes = list(bundle['model'].classes_)
        probability = float(probabilities[0, classes.index(1)])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            return {**output, 'reason': 'Trained model returned an invalid probability'}
        outside = [k for k in DAILY if not bundle['training_ranges'][k][0] <= cleaned[k] <= bundle['training_ranges'][k][1]]
    except Exception:
        # Artifact/version failures must remain unavailable, never become zero risk.
        # Do not expose local paths or serialized artifact contents to API callers.
        return {**output, 'reason': 'Trained model artifact could not be used; verify artifact and dependency versions'}
    return {**output, 'status': 'available', 'model_index': round(10*probability, 2),
            'probability': probability, 'model_version': bundle['model_version'],
            'outside_training_range': outside,
            'note': 'Experimental selected reported-event index; not injury probability or safety clearance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--features-json', required=True, help='Path to JSON with daily feature values')
    parser.add_argument('--target-date', required=True)
    args = parser.parse_args()
    print(json.dumps(predict_site(json.loads(Path(args.features_json).read_text()), args.target_date), indent=2))
