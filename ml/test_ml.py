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


def test_verified_crosswalk_when_available():
    path = ROOT / 'ml/output/site_counties.json'
    if path.exists():
        rows = json.loads(path.read_text())
        assert len(rows) == 55
        assert next(r for r in rows if r['id'] == 663)['county_fips'] == '12001'
