# Gradient-boosted challenger comparison

Decision: retain the production logistic regression. This bounded experiment does not establish grounds for replacement.

2023 scores are chronological development/selection results. 2024 was already inspected and is a development comparison, not an untouched test. No 2024 labels or scores selected configurations or thresholds.

Selected tree: tree_7. Predeclared evidence screen passed: False.

## Threshold-independent ranking

Average precision (AP) summarizes score ranking across thresholds. The prevalence baseline is constant-score AP. Neither uses the operating threshold.

| Model / period | Rows | Positive | AP | Prevalence baseline AP |
|---|---:|---:|---:|---:|
| logistic_control / 2023 OOF | 19710 | 420 | 0.1060 | 0.0213 |
| tree_7 / 2023 OOF | 19710 | 420 | 0.1177 | 0.0213 |
| tree_15 / 2023 OOF | 19710 | 420 | 0.1137 | 0.0213 |
| challenger / 2024 development | 19764 | 312 | 0.1345 | 0.0158 |
| logistic_control / 2024 development | 19764 | 312 | 0.1230 | 0.0158 |
| production_logistic / 2024 development | 19764 | 312 | 0.1243 | 0.0158 |

## Operating metrics at validation-selected thresholds

Precision, recall, false-alert burden and flagged volume below use each model's validation-selected F1 threshold. The challenger/control thresholds use pooled chronological 2023 predictions; production retains its original full-2023 validation threshold. Thresholds were frozen before 2024 scoring. Similar numeric thresholds do not imply matched alert volume or recall.

| Model / period | Threshold | Precision | Recall | False alerts / 100 days | Flagged % |
|---|---:|---:|---:|---:|---:|
| logistic_control / 2023 OOF | 0.05 | 0.1245 | 0.3476 | 5.21 | 5.95 |
| tree_7 / 2023 OOF | 0.05 | 0.1191 | 0.5238 | 8.25 | 9.37 |
| tree_15 / 2023 OOF | 0.06 | 0.1210 | 0.4310 | 6.67 | 7.59 |
| challenger / 2024 development | 0.05 | 0.0987 | 0.6250 | 9.01 | 9.99 |
| logistic_control / 2024 development | 0.05 | 0.1148 | 0.4808 | 5.85 | 6.61 |
| production_logistic / 2024 development | 0.05 | 0.1380 | 0.4455 | 4.39 | 5.10 |

## Approximately matched validation operating points

Post-experiment diagnostic using only saved pooled 2023 threshold summaries. Reference: logistic at the predeclared 0.02 reporting threshold (a high-recall point). For each comparison choose the closest tree point on the saved coarse threshold grid by volume or recall; ties favor the lower threshold. This does not change the validation-selected thresholds or use 2024. No interpolation, new fits or precise match is claimed.

| Comparison | Model | Threshold | Precision | Recall | False alerts / 100 days | Flagged % |
|---|---|---:|---:|---:|---:|---:|
| Approximate flagged_percent | logistic_control | 0.02 | 0.0581 | 0.7310 | 25.23 | 26.79 |
| Approximate flagged_percent | challenger | 0.01 | 0.0653 | 0.8857 | 27.01 | 28.89 |
| Approximate recall | logistic_control | 0.02 | 0.0581 | 0.7310 | 25.23 | 26.79 |
| Approximate recall | challenger | 0.02 | 0.0806 | 0.7786 | 18.92 | 20.58 |

At approximately matched volume, tree flags 28.89% versus 26.79% of days (2.11 percentage-point gap), with recall 88.57% versus 73.10%; false alerts are 27.01 versus 25.23 per 100 days. At approximately matched recall, tree recalls 77.86% versus 73.10% (4.76-point gap), with false alerts 18.92 versus 25.23 and flagged volume 20.58% versus 26.79%.

These coarse, high-volume comparisons show an operating-point tradeoff rather than universal tree inferiority. They do not establish a preferable policy at the originally selected operating point. The retained default decision reflects the predeclared selected-threshold screen and missing forecast validation, not universal dominance.


## 2024 operating thresholds (descriptive only)

| Model | Threshold | Precision | Recall | False alerts / 100 days | Flagged % |
|---|---:|---:|---:|---:|---:|
| challenger | 0.01 | 0.0471 | 0.9551 | 30.50 | 32.01 |
| challenger | 0.02 | 0.0603 | 0.8494 | 20.90 | 22.24 |
| challenger | 0.05 | 0.0987 | 0.6250 | 9.01 | 9.99 |
| challenger | 0.10 | 0.1409 | 0.3622 | 3.49 | 4.06 |
| challenger | 0.20 | 0.2116 | 0.1282 | 0.75 | 0.96 |
| logistic_control | 0.01 | 0.0300 | 0.9423 | 48.04 | 49.52 |
| logistic_control | 0.02 | 0.0473 | 0.8077 | 25.69 | 26.97 |
| logistic_control | 0.05 | 0.1148 | 0.4808 | 5.85 | 6.61 |
| logistic_control | 0.10 | 0.1754 | 0.2692 | 2.00 | 2.42 |
| logistic_control | 0.20 | 0.2018 | 0.1474 | 0.92 | 1.15 |
| production_logistic | 0.01 | 0.0331 | 0.9359 | 43.14 | 44.62 |
| production_logistic | 0.02 | 0.0538 | 0.7500 | 20.83 | 22.01 |
| production_logistic | 0.05 | 0.1380 | 0.4455 | 4.39 | 5.10 |
| production_logistic | 0.10 | 0.1816 | 0.2340 | 1.66 | 2.03 |
| production_logistic | 0.20 | 0.2010 | 0.1282 | 0.80 | 1.01 |

## 2024 per-state development results

AP and baseline AP are threshold-independent. Precision, recall, false-alert rate and flagged percentage use the frozen validation-selected threshold for each model.

| Model | State | Rows | Positive | AP | Baseline AP | Precision | Recall | False alerts / 100 days | Flagged % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| challenger | AL | 4026 | 61 | 0.1024 | 0.0152 | 0.0940 | 0.5410 | 7.90 | 8.72 |
| challenger | FL | 4026 | 77 | 0.1837 | 0.0191 | 0.1063 | 0.6364 | 10.23 | 11.45 |
| challenger | GA | 4026 | 36 | 0.0785 | 0.0089 | 0.0492 | 0.5278 | 9.12 | 9.59 |
| challenger | LA | 4026 | 99 | 0.2376 | 0.0246 | 0.1549 | 0.6869 | 9.22 | 10.90 |
| challenger | MS | 3660 | 39 | 0.0753 | 0.0107 | 0.0769 | 0.6667 | 8.52 | 9.23 |
| logistic_control | AL | 4026 | 61 | 0.0957 | 0.0152 | 0.1000 | 0.3607 | 4.92 | 5.46 |
| logistic_control | FL | 4026 | 77 | 0.1327 | 0.0191 | 0.1127 | 0.5065 | 7.63 | 8.59 |
| logistic_control | GA | 4026 | 36 | 0.0878 | 0.0089 | 0.0783 | 0.4722 | 4.97 | 5.39 |
| logistic_control | LA | 4026 | 99 | 0.2434 | 0.0246 | 0.1831 | 0.5455 | 5.99 | 7.33 |
| logistic_control | MS | 3660 | 39 | 0.0631 | 0.0107 | 0.0786 | 0.4615 | 5.77 | 6.26 |
| production_logistic | AL | 4026 | 61 | 0.0979 | 0.0152 | 0.1166 | 0.3115 | 3.58 | 4.05 |
| production_logistic | FL | 4026 | 77 | 0.1351 | 0.0191 | 0.1418 | 0.4935 | 5.71 | 6.66 |
| production_logistic | GA | 4026 | 36 | 0.0869 | 0.0089 | 0.1076 | 0.4722 | 3.50 | 3.92 |
| production_logistic | LA | 4026 | 99 | 0.2429 | 0.0246 | 0.2105 | 0.4848 | 4.47 | 5.66 |
| production_logistic | MS | 3660 | 39 | 0.0650 | 0.0107 | 0.0895 | 0.4359 | 4.73 | 5.19 |

## Compute cost

One CPU thread; 8 fits; total experiment wall time 7.37 seconds (excluding report writing). No GPU. Timings include pipeline preprocessing, exclude data loading/model deserialization for inference, and are machine-specific.

| Model | Final fit seconds | 19,764-row batch ms (median of 5) | One-row ms (median of 30) | Artifact bytes |
|---|---:|---:|---:|---:|
| challenger | 0.5744 | 161.337 | 2.108 | 105811 |
| logistic_control | 0.0479 | 2.226 | 0.940 | 2488 |
| production_logistic | not refitted | 4.787 | 0.910 | 2516 |

Selection-fold fitting time: 4.340 seconds. Full fold/state/threshold metrics, dependencies and hashes are in results.json. selection.json was saved before scoring 2024.

## Limits and handoff

No proposed application model replacement. A continues using ml/artifacts/model.joblib through predict_site. Challenger and matched logistic control are research artifacts only and are evaluated directly as saved pipelines, not supported predict_site custom-path replacements. Optional explain_site remains specific to logistic regression; tree explanations need separate coordination.

The predeclared screen compares ranking and operating metrics at F1-selected thresholds. Its result above is specific to that rule, not evidence that the tree is universally worse. The validation matched-point diagnostic shows the importance of the chosen operating point; no deployment threshold or production model is changed.

The matched logistic control and challenger both train on 2022–2023; the frozen production model trains on 2022 only, so comparing only to production would confound model family and training horizon. Thresholds optimized on pooled 2023 predictions may shift after refitting; they are not safety policies.

A false alert here means a flagged county-day without a selected NOAA report, not proof of no hazard. Small positive counts, correlated weather across counties/days, two temporal folds, selection optimism, reanalysis-to-forecast shift, incomplete reports, and prior-year event spillover omissions limit interpretation. No confidence intervals, calibration claim, unseen-year validation or live forecast validation. State metrics are descriptive; no state-specific tuning.

The two research joblib artifacts, selection/results JSON, plan and report are intentionally included in Git. Raw downloads, prepared datasets and caches are excluded. To reproduce from the preserved ml/output/dataset.csv and manifest with existing ml/requirements.txt dependencies, run python -m ml.benchmark --output-dir ml/output/gbt_v1_reproduction. The destination must be unused; existing completed and partial outputs are protected. This is an offline eight-fit reproduction, not required for integration. Timings vary by machine; compare metrics/hashes, not timestamps or cost. No downloads are performed.

The run emitted a Windows/joblib physical-core detection warning and fell back to logical-core discovery. threadpoolctl constrained computation to one thread; the run completed successfully.
