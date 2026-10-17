"""Focused leakage, metric and selection checks; no production model fitting."""
import numpy as np
import pandas as pd
import pytest
import json
import joblib
from threadpoolctl import threadpool_limits

from ml.benchmark import EXPERIMENT, chronological_folds, evaluate, make_model, model_selection, operating_metrics, select_threshold, require_fresh_output, validation_tradeoffs, protected_digest
from ml.common import FEATURES, OUT, ROOT, digest


def test_chronological_folds_exclude_2024_and_future_training_rows():
    frame = pd.DataFrame({'date': ['2022-01-01', '2022-12-31', '2023-01-01',
                                   '2023-06-30', '2023-07-01', '2023-12-31', '2024-01-01']})
    folds = list(chronological_folds(frame))
    assert [len(train) for train, _ in folds] == [2, 4]
    assert [len(valid) for _, valid in folds] == [2, 2]
    for train, valid in folds:
        assert train.date.max() < valid.date.min()
        assert valid.date.max() < '2024-01-01'
    with pytest.raises(ValueError, match='2024'):
        model_selection(frame)


def test_false_alert_rate_and_flagged_percent_use_all_county_days():
    result = operating_metrics([1, 0, 0, 1], [.8, .7, .1, .2], .5)
    assert result['precision'] == .5
    assert result['recall'] == .5
    assert result['false_alerts_per_100_county_days'] == 25
    assert result['flagged_percent'] == 50


def test_state_metrics_are_aligned_with_rows_and_sparse_labels():
    frame = pd.DataFrame({'date': ['2024-01-01'] * 4, 'state': ['FL', 'AL', 'FL', 'AL'],
                          'label': [1, 0, 0, 0]})
    result = evaluate(frame, np.array([.8, .7, .1, .2]), .5)
    assert result['prevalence_baseline_ap'] == .25
    assert result['per_state']['FL']['positive_days'] == 1
    assert result['per_state']['FL']['precision'] == 1
    assert result['per_state']['AL']['positive_days'] == 0
    assert result['per_state']['AL']['recall'] is None
    assert result['per_state']['AL']['average_precision'] is None
    assert result['per_state']['AL']['false_alerts_per_100_county_days'] == 50


def test_threshold_uses_f1_and_lower_threshold_tie_break():
    assert select_threshold([0, 1], [.02, .08]) == .03
    assert select_threshold([0, 1], [0, 0]) == .01


@pytest.mark.parametrize('leaves', [None, 7, 15])
def test_each_model_has_its_own_training_only_preprocessing(leaves):
    train = pd.DataFrame([[1.] * 5, [3.] * 5, [np.nan] * 5], columns=FEATURES)
    valid = pd.DataFrame([[10000.] * 5], columns=FEATURES)
    first, second = make_model(leaves), make_model(leaves)
    assert first.steps[0][1] is not second.steps[0][1]
    preprocessing = first[:-1]
    preprocessing.fit(train)
    before = preprocessing.steps[0][1].statistics_.copy()
    preprocessing.transform(valid)
    assert before == pytest.approx([2.] * 5)
    assert preprocessing.steps[0][1].statistics_ == pytest.approx(before)
    if leaves is not None:
        assert first.steps[-1][1].early_stopping is False


def test_partial_experiment_outputs_cannot_be_overwritten(tmp_path):
    require_fresh_output(tmp_path)
    (tmp_path / 'selection.json').write_text('{}')
    with pytest.raises(RuntimeError, match='partial'):
        require_fresh_output(tmp_path)


def test_protected_json_hash_survives_checkout_line_endings(tmp_path):
    path = tmp_path / 'results.json'
    path.write_bytes(b'{\r\n  "score": 0.2\r\n}\r\n')
    windows_hash = protected_digest(path)
    path.write_bytes(b'{\n  "score": 0.2\n}\n')
    assert protected_digest(path) == windows_hash
    path.write_bytes(b'{\n  "score": 0.3\n}\n')
    assert protected_digest(path) != windows_hash


def test_validation_matching_uses_only_saved_2023_points():
    selection = json.loads((EXPERIMENT / 'selection.json').read_text())
    original = json.dumps(selection, sort_keys=True)
    matches = validation_tradeoffs(selection)
    assert matches['recall']['logistic_control']['threshold'] == .02
    assert matches['recall']['challenger']['threshold'] == .02
    assert matches['recall']['difference'] == pytest.approx(20 / 420)
    assert matches['flagged_percent']['challenger']['threshold'] == .01
    assert matches['flagged_percent']['difference'] == pytest.approx(100 * (5695 - 5280) / 19710)
    assert matches['recall']['challenger']['false_alerts'] == 3729
    assert matches['recall']['logistic_control']['false_alerts'] == 4973
    assert json.dumps(selection, sort_keys=True) == original


def test_saved_challenger_reproduces_development_results():
    if not (EXPERIMENT / 'results.json').exists() or not (OUT / 'dataset.csv').exists():
        pytest.skip('Offline experiment/data unavailable in this checkout')
    results = json.loads((EXPERIMENT / 'results.json').read_text())
    for path, expected in results['protected_hashes'].items():
        assert '\\' not in path
        assert protected_digest(ROOT / path) == expected
    for path, expected in results['artifacts'].items():
        assert digest(EXPERIMENT / path) == expected
    frame = pd.read_csv(OUT / 'dataset.csv', dtype={'county_fips': str})
    manifest = json.loads((OUT / 'manifest.json').read_text())
    frame['state'] = frame.county_fips.map({row['county_fips']: row['state'] for row in manifest['selected_counties']})
    frame = frame[frame.date.str.startswith('2024')]
    with threadpool_limits(limits=1):
        for name, filename in [('challenger', 'challenger.joblib'), ('logistic_control', 'logistic_reference.joblib')]:
            artifact = joblib.load(EXPERIMENT / filename)
            scores = artifact['model'].predict_proba(frame[FEATURES])[:, 1]
            actual = evaluate(frame, scores, artifact['threshold'])
            expected = results['comparison_2024'][name]
            for key in ['average_precision', 'precision', 'recall', 'false_alerts_per_100_county_days', 'flagged_percent']:
                assert actual[key] == pytest.approx(expected[key], rel=0, abs=1e-12)
            assert artifact['training_dates'] == ['2022-01-01', '2023-12-31']
            assert actual['per_state'] == expected['per_state']
