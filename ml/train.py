"""Chronological train/validation/test baseline; never tune on final test."""
import argparse
import json
import platform
from datetime import datetime, timezone

import joblib
import sklearn
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .common import ROOT, OUT, FEATURES, DAILY, digest, save_json


def metrics(y, probability, threshold):
    positive = int(y.sum())
    return {'rows': len(y), 'positive_days': positive, 'prevalence': float(y.mean()),
            'average_precision': float(average_precision_score(y, probability)) if positive else None,
            'roc_auc': float(roc_auc_score(y, probability)) if 0 < positive < len(y) else None,
            'precision': float(precision_score(y, probability >= threshold, zero_division=0)),
            'recall': float(recall_score(y, probability >= threshold, zero_division=0)),
            'predicted_positive_days': int((probability >= threshold).sum())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validation-year', type=int, default=2023)
    parser.add_argument('--test-year', type=int, default=2024)
    args = parser.parse_args()
    frame = pd.read_csv(OUT / 'dataset.csv', dtype={'county_fips': str})
    frame['year'] = pd.to_datetime(frame.date).dt.year
    train = frame[frame.year < args.validation_year]
    valid = frame[frame.year.eq(args.validation_year)]
    test = frame[frame.year.eq(args.test_year)]
    if args.validation_year >= args.test_year or any(part.empty for part in (train, valid, test)):
        raise ValueError('Need nonempty ordered train, validation, and test periods')
    if train.label.nunique() != 2 or valid.label.nunique() != 2 or test.label.nunique() != 2:
        raise ValueError('Each split needs both classes for this evaluation; inspect data, do not invent examples')
    model = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                          LogisticRegression(max_iter=1000, random_state=42))
    model.fit(train[FEATURES], train.label)
    vp = model.predict_proba(valid[FEATURES])[:, 1]
    # Predeclared validation F1 selection over a small fixed threshold grid.
    candidates = np.linspace(.01, .5, 50)
    def f1(t):
        p = precision_score(valid.label, vp >= t, zero_division=0)
        r = recall_score(valid.label, vp >= t, zero_division=0)
        return 2*p*r/(p+r) if p+r else 0
    threshold = float(max(candidates, key=f1))
    tp = model.predict_proba(test[FEATURES])[:, 1]
    version = 'county-weather-logreg-' + digest(OUT / 'dataset.csv')[:12]
    bundle = {'model': model, 'features': FEATURES, 'model_version': version,
              'feature_version': 'daily-weather-v1', 'threshold': threshold,
              'required_features': DAILY,
              'training_ranges': {k: [float(train[k].min()), float(train[k].max())] for k in DAILY}}
    artifact = ROOT / 'ml/artifacts/model.joblib'
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, artifact)
    baseline = np.full(len(test), train.label.mean())
    results = {'model_version': version, 'computed_at': datetime.now(timezone.utc).isoformat(),
               'dependencies': {'python': platform.python_version(), 'scikit-learn': sklearn.__version__,
                                'pandas': pd.__version__, 'numpy': np.__version__, 'joblib': joblib.__version__},
               'features': FEATURES, 'threshold': threshold,
               'threshold_selection': 'Maximum validation F1 over fixed 0.01..0.50 grid; test untouched.',
               'train_years': sorted(int(y) for y in train.year.unique()),
               'validation_year': args.validation_year, 'test_year': args.test_year,
               'training_rows': len(train), 'training_prevalence': float(train.label.mean()),
               'validation': metrics(valid.label, vp, threshold),
               'test': metrics(test.label, tp, threshold),
               'constant_baseline': metrics(test.label, baseline, threshold),
               'always_negative_baseline': metrics(test.label, np.zeros(len(test)), threshold),
               'artifact_sha256': digest(artifact),
               'limitations': json.loads((OUT / 'manifest.json').read_text())['limitations']}
    save_json(ROOT / 'ml/results.json', results)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
