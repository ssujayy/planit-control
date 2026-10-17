# GBT v1 experiment budget (declared before running)

Purpose: test one histogram gradient-boosted tree family with the existing
prepared county-day dataset and the same five features. No downloads, feature
engineering, class weighting, calibration, default-artifact replacement, or
application changes. 2024 has already been inspected and is a development
comparison only, never a fresh test or a selection period.

Budget: two tree configurations, two expanding chronological folds, eight fits
total including logistic references and final fits. One CPU thread. Fixed seed
42. No search expansion in response to results.

Folds:

1. Train 2022-01-01 through 2022-12-31; validate 2023-01-01 through 2023-06-30.
2. Train 2022-01-01 through 2023-06-30; validate 2023-07-01 through 2023-12-31.

Every fold fits its own median imputer using training rows only. Trees use no
scaling; logistic reference fits its scaler and classifier within each fold.
Trees: HistGradientBoostingClassifier, learning_rate=0.05, max_iter=100,
min_samples_leaf=50, l2_regularization=1, early_stopping=False. Only
max_leaf_nodes varies: 7 or 15. No random validation split inside training.

Select tree configuration by highest pooled out-of-fold 2023 average precision;
ties favor 7 leaves. Select each model's threshold by maximum pooled 2023 F1
over fixed 0.01 through 0.50 in steps of 0.01; ties favor the lower threshold.
Selection metrics are development metrics, with selection optimism disclosed.
Record configuration and thresholds before scoring 2024. Fit the selected tree
and a separate logistic control on all 2022–2023 data. The frozen production
logistic artifact is also evaluated, using its original 0.05 threshold, without
refitting or overwriting it. The matched logistic control separates extra
training-year effects from model-family differences.

Report AP, prevalence baseline, precision, recall, false positives per 100
county-days, flagged-day percentage, and state metrics with row/positive counts.
Report fixed thresholds 0.01, 0.02, 0.05, 0.10, 0.20 plus the selected threshold.
"False alert" here means a flagged county-day with no selected reported event,
not proof that the day was hazard-free. Record training time, five warmed batch
inference timings and 30 warmed one-row timings (model inference, excluding I/O).

Predeclared evidence screen: tree AP must exceed the matched logistic control
by at least 0.01 in pooled 2023 predictions and improve AP in both temporal
folds, with selected-threshold recall no lower and false alerts per 100 days no
higher. This screen can support further evaluation only. Replacement also needs
unseen forecast-based validation and operational acceptance, absent here. 2024
comparisons and state breakdowns are descriptive and cannot trigger retuning.

Separate outputs: challenger.joblib, logistic_reference.joblib, selection.json,
results.json and REPORT.md in this directory. Default artifact/results and
predict_site remain unchanged. The prepared data remain ignored.
