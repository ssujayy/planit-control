"""Offline coverage/artifact audit. Never downloads or modifies data."""
import json
from collections import defaultdict

import joblib
import numpy as np
import pandas as pd

from .common import ROOT, OUT, FEATURES, digest
from .predict import predict_site
from .train import metrics


def main():
    sites = json.loads((ROOT / 'data/sites.json').read_text())['sites']
    crosswalk = json.loads((OUT / 'site_counties.json').read_text())
    manifest = json.loads((OUT / 'manifest.json').read_text())
    results = json.loads((ROOT / 'ml/results.json').read_text())
    frame = pd.read_csv(OUT / 'dataset.csv', dtype={'county_fips': str})
    mapped = {row['id']: row for row in crosswalk}
    assert len(mapped) == len(crosswalk) == len(sites)
    assert set(mapped) == {site['id'] for site in sites}
    groups = defaultdict(list)
    for site in sites:
        row = mapped[site['id']]
        for key in ('state', 'county', 'latitude', 'longitude', 'timezone', 'source_plant_id'):
            assert row[key] == site[key], (site['id'], key)
        assert len(row['county_fips']) == 5 and row['county_fips'].isdigit()
        groups[(row['state'], row['county_fips'])].append({'id': site['id'], 'name': site['name'], 'county': site['county']})
    expected = {fips for state, fips in groups}
    actual = set(frame.county_fips)
    assert expected == actual == {row['county_fips'] for row in manifest['selected_counties']}
    dates = set(pd.date_range('2022-01-01', '2024-12-31').strftime('%Y-%m-%d'))
    assert not frame.duplicated(['county_fips', 'date']).any()
    assert all(set(part.date) == dates for _, part in frame.groupby('county_fips'))
    assert digest(OUT / 'dataset.csv') == manifest['dataset_sha256'] == results['dataset_sha256']
    artifact = ROOT / 'ml/artifacts/model.joblib'
    assert digest(artifact) == results['artifact_sha256']
    bundle = joblib.load(artifact)
    assert bundle['model_version'] == results['model_version']
    assert bundle['features'] == results['features'] == FEATURES
    assert bundle['threshold'] == results['threshold']
    for name, year in [('training', 2022), ('validation', 2023), ('test', 2024)]:
        part = frame[frame.date.str.startswith(str(year))]
        probability = bundle['model'].predict_proba(part[FEATURES])[:, list(bundle['model'].classes_).index(1)]
        for key, value in metrics(part.label, probability, results['threshold']).items():
            assert np.isclose(value, results[name][key]), (name, key)
    good = {'temperature_2m_max': 30, 'precipitation_sum': 10, 'wind_gusts_10m_max': 50}
    prediction = predict_site(good, '2026-10-18')
    assert prediction['status'] == 'available'
    failures = [predict_site(value, '2026-10-18') for value in (None, {}, {**good, 'precipitation_sum': -1})]
    failures.append(predict_site(good, '2026-10-18', ROOT / 'ml/artifacts/nonexistent.joblib'))
    assert all(row['status'] == 'unavailable' and row['model_index'] is None and row['probability'] is None for row in failures)
    print(json.dumps({'sites': len(sites), 'unique_source_ids': len({s['source_plant_id'] for s in sites}),
                      'state_county_pairs': len(groups), 'dataset_counties': len(actual),
                      'rows': len(frame), 'days_per_county': len(dates),
                      'shared_counties': [{'state': state, 'county_fips': fips, 'sites': rows} for (state, fips), rows in groups.items() if len(rows) > 1],
                      'excluded_sites': [], 'excluded_counties': [],
                      'artifact_sha256': digest(artifact), 'prediction': prediction,
                      'unavailable_checks': failures, 'saved_metrics_reproduced': True}, indent=2))


if __name__ == '__main__':
    main()
