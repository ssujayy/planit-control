"""Focused checks for label geography and inference failure semantics."""
import json

from ml.common import ROOT
from ml.predict import predict_site
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
