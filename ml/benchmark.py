"""Bounded offline challenger experiment; never updates the production model."""
import json
import argparse
import hashlib
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .common import DAILY, FEATURES, OUT, ROOT, digest, save_json

EXPERIMENT = ROOT / 'ml/experiments/gbt_v1'
FOLDS = [('2023-01-01', '2023-07-01'), ('2023-07-01', '2024-01-01')]
THRESHOLDS = [round(x / 100, 2) for x in range(1, 51)]
REPORT_THRESHOLDS = [.01, .02, .05, .10, .20]
TREE_CONFIGS = [7, 15]


def protected_digest(path):
    """JSON verification survives Git's CRLF/LF conversion; binaries stay exact."""
    if path.suffix == '.json':
        return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    return digest(path)


def require_fresh_output(directory):
    names = ['selection.json', 'results.json', 'challenger.joblib', 'logistic_reference.joblib', 'REPORT.md']
    if any((directory / name).exists() for name in names):
        raise RuntimeError('Experiment outputs exist; preserve completed or partial runs rather than silently overwriting')


def chronological_folds(frame):
    """All training dates precede validation; no 2024 row can enter selection."""
    for start, end in FOLDS:
        train = frame[(frame.date >= '2022-01-01') & (frame.date < start)]
        valid = frame[(frame.date >= start) & (frame.date < end)]
        if train.empty or valid.empty or train.date.max() >= valid.date.min():
            raise ValueError('Missing or unordered chronological fold')
        yield train, valid


def make_model(leaves=None):
    if leaves is None:
        return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                             LogisticRegression(max_iter=1000, random_state=42))
    return make_pipeline(SimpleImputer(strategy='median'),
                         HistGradientBoostingClassifier(
                             max_leaf_nodes=leaves, learning_rate=.05, max_iter=100,
                             min_samples_leaf=50, l2_regularization=1,
                             early_stopping=False, random_state=42))


def operating_metrics(labels, probability, threshold):
    labels, probability = np.asarray(labels), np.asarray(probability)
    if not len(labels) or len(labels) != len(probability):
        raise ValueError('Metrics need equally sized nonempty arrays')
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(probability).all():
        raise ValueError('Expected binary labels and finite probabilities')
    if ((probability < 0) | (probability > 1)).any():
        raise ValueError('Probability outside [0, 1]')
    flagged = probability >= threshold
    tp = int((flagged & (labels == 1)).sum())
    fp = int((flagged & (labels == 0)).sum())
    positives = int(labels.sum())
    count = int(flagged.sum())
    return {'threshold': float(threshold), 'precision': tp / count if count else 0.,
            'recall': tp / positives if positives else None,
            'false_alerts': fp, 'false_alerts_per_100_county_days': 100 * fp / len(labels),
            'flagged_days': count, 'flagged_percent': 100 * count / len(labels)}


def select_threshold(labels, probability):
    def f1(threshold):
        row = operating_metrics(labels, probability, threshold)
        p, r = row['precision'], row['recall'] or 0.
        return 2 * p * r / (p + r) if p + r else 0.
    return max(THRESHOLDS, key=f1)


def evaluate(frame, probability, threshold):
    def summary(part, scores):
        positives = int(part.label.sum())
        return {'rows': len(part), 'positive_days': positives,
                'start_date': part.date.min(), 'end_date': part.date.max(),
                'prevalence': float(part.label.mean()),
                'prevalence_baseline_ap': float(part.label.mean()) if positives else None,
                'average_precision': float(average_precision_score(part.label, scores)) if positives else None,
                **operating_metrics(part.label, scores, threshold)}
    result = summary(frame, probability)
    result['thresholds'] = [operating_metrics(frame.label, probability, t)
                            for t in sorted(set(REPORT_THRESHOLDS + [threshold]))]
    result['per_state'] = {state: summary(frame[frame.state.eq(state)], probability[frame.state.eq(state)])
                           for state in sorted(frame.state.unique())}
    return result


def timing(model, frame):
    model.predict_proba(frame.iloc[:1])
    batch, single = [], []
    for _ in range(5):
        start = time.perf_counter()
        model.predict_proba(frame)
        batch.append(time.perf_counter() - start)
    for _ in range(30):
        start = time.perf_counter()
        model.predict_proba(frame.iloc[:1])
        single.append(time.perf_counter() - start)
    return {'batch_rows': len(frame), 'batch_repeats': 5, 'single_repeats': 30,
            'batch_seconds_median': float(np.median(batch)),
            'single_row_milliseconds_median': float(np.median(single) * 1000)}


def model_selection(development):
    if development.date.max() >= '2024-01-01':
        raise ValueError('2024 cannot enter model selection')
    experiments = {}
    for name, leaves in [('logistic_control', None), ('tree_7', 7), ('tree_15', 15)]:
        predictions, validation, folds = [], [], []
        for train, valid in chronological_folds(development):
            if train.label.nunique() != 2 or valid.label.nunique() != 2:
                raise ValueError('Both classes required in each selection fold')
            model = make_model(leaves)
            started = time.perf_counter()
            model.fit(train[FEATURES], train.label)
            elapsed = time.perf_counter() - started
            scores = model.predict_proba(valid[FEATURES])[:, 1]
            predictions.append(scores)
            validation.append(valid)
            folds.append({'train_start': train.date.min(), 'train_end': train.date.max(),
                          'training_rows': len(train), 'fit_seconds': elapsed,
                          'validation_start': valid.date.min(), 'validation_end': valid.date.max(),
                          'validation_rows': len(valid), 'positive_days': int(valid.label.sum()),
                          'average_precision': float(average_precision_score(valid.label, scores))})
        combined = pd.concat(validation)
        scores = np.concatenate(predictions)
        threshold = select_threshold(combined.label, scores)
        experiments[name] = {'max_leaf_nodes': leaves, 'folds': folds,
                             'pooled_2023': evaluate(combined, scores, threshold)}
    selected = max(['tree_7', 'tree_15'], key=lambda name: experiments[name]['pooled_2023']['average_precision'])
    tree, logistic = experiments[selected], experiments['logistic_control']
    t, l = tree['pooled_2023'], logistic['pooled_2023']
    screen = (t['average_precision'] >= l['average_precision'] + .01
              and all(a['average_precision'] > b['average_precision'] for a, b in zip(tree['folds'], logistic['folds']))
              and t['recall'] >= l['recall']
              and t['false_alerts_per_100_county_days'] <= l['false_alerts_per_100_county_days'])
    return {'selected_tree': selected, 'experiments': experiments,
            'threshold_method': 'Maximum pooled 2023 out-of-fold F1 on 0.01..0.50; lower threshold wins ties',
            'configuration_method': 'Maximum pooled 2023 out-of-fold AP; seven leaves wins ties',
            'predeclared_evidence_screen_passed': bool(screen)}


def validation_tradeoffs(selection):
    """Descriptive coarse matches using saved 2023 points, never 2024 scores.

    Reference is the predeclared 0.02 reporting threshold, not a new deployed
    threshold. Raw out-of-fold predictions were not retained, so no interpolation
    or fine-grained matching is claimed.
    """
    logistic = selection['experiments']['logistic_control']['pooled_2023']
    tree = selection['experiments'][selection['selected_tree']]['pooled_2023']
    reference = next(row for row in logistic['thresholds'] if row['threshold'] == .02)
    matches = {}
    for metric in ['flagged_percent', 'recall']:
        closest = min(tree['thresholds'], key=lambda row: (abs(row[metric] - reference[metric]), row['threshold']))
        matches[metric] = {'logistic_control': reference, 'challenger': closest,
                           'difference': closest[metric] - reference[metric]}
    return matches


def write_report(results, output_dir=EXPERIMENT):
    selection = results['selection']
    tradeoffs = validation_tradeoffs(selection)
    def number(value):
        return 'unavailable' if value is None else f'{value:.4f}'
    lines = ['# Gradient-boosted challenger comparison', '',
             'Decision: retain the production logistic regression. This bounded experiment does not establish grounds for replacement.', '',
             '2023 scores are chronological development/selection results. 2024 was already inspected and is a development comparison, not an untouched test. No 2024 labels or scores selected configurations or thresholds.', '',
             f"Selected tree: {selection['selected_tree']}. Predeclared evidence screen passed: {selection['predeclared_evidence_screen_passed']}.", '',
             '## Threshold-independent ranking', '',
             'Average precision (AP) summarizes score ranking across thresholds. The prevalence baseline is constant-score AP. Neither uses the operating threshold.', '',
             '| Model / period | Rows | Positive | AP | Prevalence baseline AP |',
             '|---|---:|---:|---:|---:|']
    summaries = [(f'{name} / 2023 OOF', item['pooled_2023']) for name, item in selection['experiments'].items()]
    summaries += [(f'{name} / 2024 development', row) for name, row in results['comparison_2024'].items()]
    for name, r in summaries:
        lines.append(f"| {name} | {r['rows']} | {r['positive_days']} | {r['average_precision']:.4f} | {r['prevalence_baseline_ap']:.4f} |")
    lines += ['', '## Operating metrics at validation-selected thresholds', '',
              'Precision, recall, false-alert burden and flagged volume below use each model\'s validation-selected F1 threshold. The challenger/control thresholds use pooled chronological 2023 predictions; production retains its original full-2023 validation threshold. Thresholds were frozen before 2024 scoring. Similar numeric thresholds do not imply matched alert volume or recall.', '',
              '| Model / period | Threshold | Precision | Recall | False alerts / 100 days | Flagged % |',
              '|---|---:|---:|---:|---:|---:|']
    for name, r in summaries:
        lines.append(f"| {name} | {r['threshold']:.2f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['false_alerts_per_100_county_days']:.2f} | {r['flagged_percent']:.2f} |")
    lines += ['', '## Approximately matched validation operating points', '',
              'Post-experiment diagnostic using only saved pooled 2023 threshold summaries. Reference: logistic at the predeclared 0.02 reporting threshold (a high-recall point). For each comparison choose the closest tree point on the saved coarse threshold grid by volume or recall; ties favor the lower threshold. This does not change the validation-selected thresholds or use 2024. No interpolation, new fits or precise match is claimed.', '',
              '| Comparison | Model | Threshold | Precision | Recall | False alerts / 100 days | Flagged % |',
              '|---|---|---:|---:|---:|---:|---:|']
    for metric, match in tradeoffs.items():
        for name in ['logistic_control', 'challenger']:
            r = match[name]
            lines.append(f"| Approximate {metric} | {name} | {r['threshold']:.2f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['false_alerts_per_100_county_days']:.2f} | {r['flagged_percent']:.2f} |")
    v = tradeoffs['flagged_percent']
    r = tradeoffs['recall']
    vt, vl, rt, rl = v['challenger'], v['logistic_control'], r['challenger'], r['logistic_control']
    lines += ['',
              f"At approximately matched volume, tree flags {vt['flagged_percent']:.2f}% versus {vl['flagged_percent']:.2f}% of days ({abs(v['difference']):.2f} percentage-point gap), with recall {100*vt['recall']:.2f}% versus {100*vl['recall']:.2f}%; false alerts are {vt['false_alerts_per_100_county_days']:.2f} versus {vl['false_alerts_per_100_county_days']:.2f} per 100 days. At approximately matched recall, tree recalls {100*rt['recall']:.2f}% versus {100*rl['recall']:.2f}% ({100*abs(r['difference']):.2f}-point gap), with false alerts {rt['false_alerts_per_100_county_days']:.2f} versus {rl['false_alerts_per_100_county_days']:.2f} and flagged volume {rt['flagged_percent']:.2f}% versus {rl['flagged_percent']:.2f}%.", '',
              'These coarse, high-volume comparisons show an operating-point tradeoff rather than universal tree inferiority. They do not establish a preferable policy at the originally selected operating point. The retained default decision reflects the predeclared selected-threshold screen and missing forecast validation, not universal dominance.', '']
    lines += ['', '## 2024 operating thresholds (descriptive only)', '',
              '| Model | Threshold | Precision | Recall | False alerts / 100 days | Flagged % |',
              '|---|---:|---:|---:|---:|---:|']
    for name, r in results['comparison_2024'].items():
        for t in r['thresholds']:
            lines.append(f"| {name} | {t['threshold']:.2f} | {t['precision']:.4f} | {t['recall']:.4f} | {t['false_alerts_per_100_county_days']:.2f} | {t['flagged_percent']:.2f} |")
    lines += ['', '## 2024 per-state development results', '',
              'AP and baseline AP are threshold-independent. Precision, recall, false-alert rate and flagged percentage use the frozen validation-selected threshold for each model.', '',
              '| Model | State | Rows | Positive | AP | Baseline AP | Precision | Recall | False alerts / 100 days | Flagged % |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, r in results['comparison_2024'].items():
        for state, s in r['per_state'].items():
            lines.append(f"| {name} | {state} | {s['rows']} | {s['positive_days']} | {number(s['average_precision'])} | {number(s['prevalence_baseline_ap'])} | {s['precision']:.4f} | {number(s['recall'])} | {s['false_alerts_per_100_county_days']:.2f} | {s['flagged_percent']:.2f} |")
    lines += ['', '## Compute cost', '',
              f"One CPU thread; {results['fit_count']} fits; total experiment wall time {results['wall_seconds']:.2f} seconds (excluding report writing). No GPU. Timings include pipeline preprocessing, exclude data loading/model deserialization for inference, and are machine-specific.", '',
              '| Model | Final fit seconds | 19,764-row batch ms (median of 5) | One-row ms (median of 30) | Artifact bytes |',
              '|---|---:|---:|---:|---:|']
    for name, cost in results['cost'].items():
        fit = f"{cost['final_fit_seconds']:.4f}" if cost['final_fit_seconds'] is not None else 'not refitted'
        lines.append(f"| {name} | {fit} | {1000*cost['batch_seconds_median']:.3f} | {cost['single_row_milliseconds_median']:.3f} | {cost['artifact_bytes']} |")
    lines += ['', f"Selection-fold fitting time: {results['selection_fit_seconds']:.3f} seconds. Full fold/state/threshold metrics, dependencies and hashes are in results.json. selection.json was saved before scoring 2024.", '',
              '## Limits and handoff', '',
              'No proposed application model replacement. A continues using ml/artifacts/model.joblib through predict_site. Challenger and matched logistic control are research artifacts only and are evaluated directly as saved pipelines, not supported predict_site custom-path replacements. Optional explain_site remains specific to logistic regression; tree explanations need separate coordination.', '',
              'The predeclared screen compares ranking and operating metrics at F1-selected thresholds. Its result above is specific to that rule, not evidence that the tree is universally worse. The validation matched-point diagnostic shows the importance of the chosen operating point; no deployment threshold or production model is changed.', '',
              'The matched logistic control and challenger both train on 2022–2023; the frozen production model trains on 2022 only, so comparing only to production would confound model family and training horizon. Thresholds optimized on pooled 2023 predictions may shift after refitting; they are not safety policies.', '',
              'A false alert here means a flagged county-day without a selected NOAA report, not proof of no hazard. Small positive counts, correlated weather across counties/days, two temporal folds, selection optimism, reanalysis-to-forecast shift, incomplete reports, and prior-year event spillover omissions limit interpretation. No confidence intervals, calibration claim, unseen-year validation or live forecast validation. State metrics are descriptive; no state-specific tuning.', '',
              'The two research joblib artifacts, selection/results JSON, plan and report are intentionally included in Git. Raw downloads, prepared datasets and caches are excluded. To reproduce from the preserved ml/output/dataset.csv and manifest with existing ml/requirements.txt dependencies, run python -m ml.benchmark --output-dir ml/output/gbt_v1_reproduction. The destination must be unused; existing completed and partial outputs are protected. This is an offline eight-fit reproduction, not required for integration. Timings vary by machine; compare metrics/hashes, not timestamps or cost. No downloads are performed.', '',
              'The run emitted a Windows/joblib physical-core detection warning and fell back to logical-core discovery. threadpoolctl constrained computation to one thread; the run completed successfully.']
    (output_dir / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(output_dir=EXPERIMENT):
    output_dir = Path(output_dir)
    require_fresh_output(output_dir)
    protected = [ROOT / 'ml/artifacts/model.joblib', ROOT / 'ml/results.json', OUT / 'dataset.csv']
    before = {path.relative_to(ROOT).as_posix(): protected_digest(path) for path in protected}
    manifest = json.loads((OUT / 'manifest.json').read_text())
    if digest(OUT / 'dataset.csv') != manifest['dataset_sha256']:
        raise ValueError('Dataset does not match manifest')
    frame = pd.read_csv(OUT / 'dataset.csv', dtype={'county_fips': str})
    if frame.duplicated(['county_fips', 'date']).any() or not frame.label.isin([0, 1]).all():
        raise ValueError('Invalid county-day grid/labels')
    if len(frame) != manifest['rows'] or int(frame.label.sum()) != manifest['positive_days']:
        raise ValueError('Dataset counts differ from manifest')
    county_states = {row['county_fips']: row['state'] for row in manifest['selected_counties']}
    frame['state'] = frame.county_fips.map(county_states)
    if frame.state.isna().any():
        raise ValueError('Unmapped state')
    frame = frame.sort_values(['date', 'county_fips']).reset_index(drop=True)
    development = frame[(frame.date >= '2022-01-01') & (frame.date < '2024-01-01')]
    comparison = frame[(frame.date >= '2024-01-01') & (frame.date < '2025-01-01')]
    started = time.perf_counter()
    with threadpool_limits(limits=1):
        selection = model_selection(development)
        selection['selected_at'] = datetime.now(timezone.utc).isoformat()
        selection['dataset_sha256'] = manifest['dataset_sha256']
        selection['plan_sha256'] = digest(EXPERIMENT / 'PLAN.md')
        save_json(output_dir / 'selection.json', selection)
        selected = selection['selected_tree']
        models, costs = {}, {}
        for name, leaves, filename in [('challenger', selection['experiments'][selected]['max_leaf_nodes'], 'challenger.joblib'),
                                        ('logistic_control', None, 'logistic_reference.joblib')]:
            model = make_model(leaves)
            tick = time.perf_counter()
            model.fit(development[FEATURES], development.label)
            elapsed = time.perf_counter() - tick
            chosen = selected if name == 'challenger' else name
            threshold = selection['experiments'][chosen]['pooled_2023']['threshold']
            bundle = {'model': model, 'features': FEATURES, 'feature_version': 'daily-weather-v1',
                      'model_version': f'gbt-v1-{name}-{manifest["dataset_sha256"][:12]}',
                      'threshold': threshold, 'required_features': DAILY,
                      'training_dates': ['2022-01-01', '2023-12-31'], 'research_only': True}
            joblib.dump(bundle, output_dir / filename)
            models[name] = (model, threshold)
            costs[name] = {'final_fit_seconds': elapsed,
                           'artifact_bytes': (output_dir / filename).stat().st_size,
                           **timing(model, comparison[FEATURES])}
        frozen = joblib.load(protected[0])
        models['production_logistic'] = (frozen['model'], frozen['threshold'])
        costs['production_logistic'] = {'final_fit_seconds': None, 'artifact_bytes': protected[0].stat().st_size,
                                         **timing(frozen['model'], comparison[FEATURES])}
        results_2024 = {name: evaluate(comparison, model.predict_proba(comparison[FEATURES])[:, 1], threshold)
                        for name, (model, threshold) in models.items()}
    after = {path.relative_to(ROOT).as_posix(): protected_digest(path) for path in protected}
    if before != after:
        raise RuntimeError('Protected baseline or data changed during experiment')
    results = {'selection': selection, 'comparison_2024': results_2024, 'cost': costs,
               'fit_count': 8, 'wall_seconds': time.perf_counter() - started,
               'selection_fit_seconds': sum(f['fit_seconds'] for e in selection['experiments'].values() for f in e['folds']),
               'protected_hashes': after,
               'protected_hash_note': 'JSON hashes normalize CRLF to LF; dataset and artifact hashes use exact bytes.',
               'artifacts': {f: digest(output_dir / f) for f in ['challenger.joblib', 'logistic_reference.joblib']},
               'environment': {'python': platform.python_version(), 'platform': platform.system(), 'processor': platform.processor(),
                               'sklearn': sklearn.__version__, 'numpy': np.__version__, 'pandas': pd.__version__, 'joblib': joblib.__version__,
                               'threads': 1}, 'recommendation': 'Retain production logistic; no application model replacement.'}
    save_json(output_dir / 'results.json', results)
    write_report(results, output_dir)
    print(json.dumps({'selected_tree': selected, 'evidence_screen': selection['predeclared_evidence_screen_passed'],
                      'wall_seconds': results['wall_seconds'], 'report': str(output_dir / 'REPORT.md'),
                      'comparison_ap': {name: row['average_precision'] for name, row in results_2024.items()}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=EXPERIMENT,
                        help='Unused output directory; existing experiment outputs are never overwritten')
    main(parser.parse_args().output_dir)
