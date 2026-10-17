"""Focused checks for label geography and inference failure semantics."""
import json
import math

import joblib
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

from ml.common import ROOT, FEATURES, season
from ml.predict import predict_site, explain_site
from datetime import date
from ml.build_dataset import normalized


def test_county_normalization():
    assert normalized('St. John the Baptist Parish') == normalized('St John the Baptist')
    assert normalized('Miami-Dade') == normalized('Miami Dade')


def test_missing_features_are_unavailable():
    result = predict_site({}, '2026-10-18')
    assert result['status'] == 'unavailable'
    assert result['model_index'] is None


def test_invalid_inputs_are_unavailable():
    assert predict_site({}, 'invalid')['status'] == 'unavailable'
    good = {'temperature_2m_max': 30, 'precipitation_sum': 10, 'wind_gusts_10m_max': 50}
    assert predict_site({**good, 'precipitation_sum': -1}, '2026-10-18')['status'] == 'unavailable'
    assert predict_site({**good, 'temperature_2m_max': float('nan')}, '2026-10-18')['status'] == 'unavailable'
    assert predict_site(None, '2026-10-18')['status'] == 'unavailable'


def test_unusable_artifact_is_unavailable(tmp_path):
    good = {'temperature_2m_max': 30, 'precipitation_sum': 10, 'wind_gusts_10m_max': 50}
    artifact = tmp_path / 'broken.joblib'
    artifact.write_bytes(b'incomplete artifact')
    result = predict_site(good, '2026-10-18', artifact)
    assert result['status'] == 'unavailable'
    assert result['model_index'] is None


def test_saved_model_produces_real_bounded_prediction():
    good = {'temperature_2m_max': 30, 'precipitation_sum': 10, 'wind_gusts_10m_max': 50}
    result = predict_site(good, '2026-10-18')
    assert result['status'] == 'available'
    assert 0 <= result['probability'] <= 1
    assert result['model_index'] == round(10 * result['probability'], 2)
    assert result['model_version'] == json.loads((ROOT / 'ml/results.json').read_text())['model_version']


def test_verified_crosswalk_when_available():
    path = ROOT / 'ml/output/site_counties.json'
    if path.exists():
        rows = json.loads(path.read_text())
        assert len(rows) == 55
        assert next(r for r in rows if r['id'] == 663)['county_fips'] == '12001'


@pytest.mark.parametrize('day,weather', [
    ('2026-10-18', [30, 10, 50]),
    ('2024-02-29', [-10, 0, 5]),
    ('2026-07-01', [45, 200, 150]),
])
def test_model_contributions_reconstruct_saved_pipeline(day, weather):
    features = dict(zip(FEATURES[:3], weather))
    result = explain_site(features, day)
    plain = predict_site(features, day)
    assert 'model_contributions' not in plain
    for key in plain.keys() - {'computed_at'}:
        assert result[key] == plain[key]
    explanation = result['model_contributions']
    assert explanation['label'] == 'model contributions'
    assert explanation['units'] == 'model log-odds'
    assert len(explanation['features']) == len(FEATURES)
    pipeline = joblib.load(ROOT / 'ml/artifacts/model.joblib')['model']
    frame = pd.DataFrame([{**features, **season(date.fromisoformat(day))}])[FEATURES]
    transformed = pipeline[:-1].transform(frame)[0]
    for index, feature in enumerate(explanation['features']):
        assert feature['feature'] == FEATURES[index]
        assert feature['value'] == frame.iloc[0, index]
        assert feature['transformed_value'] == pytest.approx(transformed[index])
        assert feature['contribution'] == pytest.approx(transformed[index] * pipeline.steps[-1][1].coef_[0, index])
    assert explanation['intercept'] == float(pipeline.steps[-1][1].intercept_[0])
    total = explanation['intercept'] + math.fsum(item['contribution'] for item in explanation['features'])
    decision = float(pipeline.decision_function(frame)[0])
    probability = float(pipeline.predict_proba(frame)[0, 1])
    assert total == pytest.approx(decision, rel=0, abs=1e-10)
    assert explanation['decision_function'] == decision
    assert explanation['reconstructed_log_odds'] == pytest.approx(total, rel=0, abs=1e-10)
    assert 1 / (1 + math.exp(-total)) == pytest.approx(probability, rel=0, abs=1e-12)
    assert explanation['reconstructed_probability'] == pytest.approx(probability, rel=0, abs=1e-12)


@pytest.mark.parametrize('day,day_of_year', [('2026-01-01', 1), ('2024-02-29', 60),
                                            ('2024-12-31', 366)])
def test_contributions_derive_both_seasonal_features_from_target_date(day, day_of_year):
    # Caller-provided seasonal values must not override the daily date encoding.
    features = {**dict(zip(FEATURES[:3], [30, 10, 50])), 'season_sin': 99, 'season_cos': 99}
    result = explain_site(features, day)['model_contributions']
    values = {item['feature']: item['value'] for item in result['features']}
    angle = 2 * math.pi * (day_of_year - 1) / 365.25
    assert values['season_sin'] == pytest.approx(math.sin(angle), rel=0, abs=1e-15)
    assert values['season_cos'] == pytest.approx(math.cos(angle), rel=0, abs=1e-15)


@pytest.mark.parametrize('features,day', [(None, '2026-10-18'), ({}, '2026-10-18'),
                                        ({}, 'invalid')])
def test_explanation_preserves_unavailable_inputs(features, day):
    result = explain_site(features, day)
    assert result['status'] == 'unavailable'
    assert result['model_index'] is result['probability'] is result['model_contributions'] is None
    assert result['reason'] == predict_site(features, day)['reason']


@pytest.mark.parametrize('key,value', [('temperature_2m_max', float('nan')),
                                      ('temperature_2m_max', float('inf')),
                                      ('temperature_2m_max', True),
                                      ('temperature_2m_max', '30'),
                                      ('precipitation_sum', -1),
                                      ('wind_gusts_10m_max', -1)])
def test_explanation_preserves_invalid_feature_values(key, value):
    features = {**dict(zip(FEATURES[:3], [30, 10, 50])), key: value}
    result = explain_site(features, '2026-10-18')
    plain = predict_site(features, '2026-10-18')
    assert result['status'] == 'unavailable'
    assert result['model_index'] is result['probability'] is result['model_contributions'] is None
    assert result['reason'] == plain['reason']


def test_explanation_preserves_unavailable_artifacts(tmp_path):
    good = dict(zip(FEATURES[:3], [30, 10, 50]))
    path = tmp_path / 'artifact.joblib'
    for exists in (False, True):
        if exists:
            path.write_bytes(b'corrupt')
        result = explain_site(good, '2026-10-18', path)
        assert result['status'] == 'unavailable'
        assert result['model_contributions'] is None
        assert result['reason'] == predict_site(good, '2026-10-18', path)['reason']


def test_failed_reconstruction_preserves_prediction(monkeypatch):
    monkeypatch.setattr(Pipeline, 'decision_function', lambda self, frame: [123.0])
    result = explain_site(dict(zip(FEATURES[:3], [30, 10, 50])), '2026-10-18')
    assert result['status'] == 'available'
    assert result['model_index'] == 0.21
    assert result['model_contributions'] is None
    assert 'explanation_reason' in result


class ReverseFeatures(TransformerMixin, BaseEstimator):
    """Represent a future preprocessing change without fitting another model."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return X[:, ::-1]

    def get_feature_names_out(self, input_features=None):
        return list(input_features)[::-1]

    def __sklearn_is_fitted__(self):
        return True


def test_reordered_preprocessing_cannot_mislabel_contributions(tmp_path):
    bundle = joblib.load(ROOT / 'ml/artifacts/model.joblib')
    bundle['model'].steps.insert(-1, ('reverse_features', ReverseFeatures()))
    artifact = tmp_path / 'reordered.joblib'
    joblib.dump(bundle, artifact)
    features = dict(zip(FEATURES[:3], [30, 10, 50]))
    plain = predict_site(features, '2026-10-18', artifact)
    result = explain_site(features, '2026-10-18', artifact)
    assert plain['status'] == result['status'] == 'available'
    assert result['probability'] == plain['probability']
    assert result['model_contributions'] is None
    assert 'explanation_reason' in result
