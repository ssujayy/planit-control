# C coordination and handoff

Scope: historical county-day dataset, training/evaluation, and pure inference.
Owned changes: ml/predict.py, ml/train.py, ml/test_ml.py, ml/results.json,
ml/artifacts/model.joblib, docs/ML.md, and this log.

Contracts checked: AGENTS.md, docs/API_CONTRACT.md, docs/WORKSTREAMS.md,
docs/ML.md. The user assigns C to ML; WORKSTREAMS still assigns D to ML.
The latest explicit user assignment governs; shared ownership docs were not edited.
Existing uncommitted ml/common.py downloader changes are preserved untouched.

Actual mismatch: prepared data already contained 54 counties and 59,184 days,
while the saved model/evaluation described five counties. Trained on the existing
expanded data after checking manifest hash, unique county-days, binary labels,
counts, chronological splits, and required training-feature availability.
No downloads, worker launches, database changes, or dependency changes.

Interface unchanged: predict_site(features, target_date, artifact_path=None).
Inputs are full site-local daily Celsius maximum temperature, mm precipitation,
and km/h maximum gust. Malformed inputs and unusable artifacts return unavailable
with null model_index/probability; successful inference uses the saved classifier's
positive class. No new shared response fields or endpoints.

Evaluation: 2022 training / 2023 validation / 2024 test. Test AP 0.1243 versus
constant baseline 0.0158; precision 0.1380, recall 0.4455 at threshold 0.05.
All weather features have zero missing values. Evaluation uses historical
reanalysis, not operational forecasts. Model version county-weather-logreg-277e4566fcdb.

Verification: python -m ml.train completed successfully. Focused ML checks are
completed with 12 passing tests: python -m pytest ml/test_ml.py
tests/test_foundation.py -q -p no:cacheprovider. Process names/IDs inspected; CIM command-line
inspection was denied. Two Python processes exist; neither was restarted.

Next action for A: call the existing predict_site interface with complete tomorrow
local-day forecast aggregates, persist outputs keyed by site/date/model/feature
version, and register inference in the existing worker. D must consume actual
saved predictions as a daily experimental index, separate from hourly outlooks
and official alerts. No communication with other agents is claimed here.

## Final offline review

Coverage verified against current data/sites.json, ml/output/site_counties.json,
the dataset and manifest: 55 sites, 55 unique source plant IDs, 54 unique
(state, county FIPS) pairs, exactly 54 dataset counties. Each county has all
1,096 dates from 2022-01-01 through 2024-12-31, with unique county-day rows.
No excluded sites or counties and no failed county downloads identified.
Wildflower Solar, LLC (MS), site 66369, and TVA Southaven Combined Cycle,
site 55269, both map to Mississippi DeSoto County, FIPS 28033. They share one
county-day label/representative weather series rather than duplicate training
rows. Spelling differs (DeSoto/Desoto); normalization treats these equivalently.

Actual saved evaluation (threshold 0.05):

| Split | Inclusive dates | Rows | Positive days | Prevalence | AP | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| Train | 2022-01-01–2022-12-31 | 19,710 | 326 | 0.016540 | 0.131708 | 0.134021 | 0.398773 |
| Validation | 2023-01-01–2023-12-31 | 19,710 | 420 | 0.021309 | 0.109826 | 0.128476 | 0.319048 |
| Test | 2024-01-01–2024-12-31 | 19,764 | 312 | 0.015786 | 0.124284 | 0.138034 | 0.445513 |

Constant baseline predicts training prevalence 0.016540 for every test row:
test AP 0.015786, precision/recall 0 at 0.05, ROC-AUC 0.5. Always-negative
baseline has the same test AP/precision/recall. Preprocessing/classifier fit
only 2022; threshold maximizes 2023 validation F1 on the fixed 50-value
0.01–0.50 grid (first/lower threshold on ties). The test is held out of fitting
and selection, not unseen after evaluation. Five-county versus expanded results
are development comparisons, not a second independent final test or proof of
generalization. Review reran the unchanged deterministic training to record
missing train metrics and date bounds; artifact hash and test metrics stayed
identical. No tuning based on test results occurred in this review.

Artifact and results are both tracked, modified, and not ignored. They were
present in the tool's diff summary; the earlier prose handoff grouped them as
"artifact/results" rather than listing paths individually. This was reporting
compression, not missing files. ml/output/ is ignored by ml/.gitignore and the
prepared dataset must be preserved/transferred separately for offline reproduction.
Current model SHA-256:
ad0f5f4d03561885d0ead33a3f5e0e6b89c93869989a1a9e341d6a932955ccf2.
Dataset SHA-256:
277e4566fcdb420efdf51ac5194bdbd2f4bf51e857b4a93eba4c0ad488c41549.
The offline audit checks hashes, feature order, version, threshold, and all
recorded split metrics using the loaded saved classifier.

Exact Python interface:

```python
from ml.predict import predict_site
result = predict_site(
    features={"temperature_2m_max": 30.0,
              "precipitation_sum": 10.0,
              "wind_gusts_10m_max": 50.0},
    target_date="2026-10-18",
    artifact_path=None,  # defaults to ml/artifacts/model.joblib
)
```

These are illustrative full local-day inputs, not fetched forecasts. Units:
Celsius maximum temperature, mm/day total precipitation, km/h maximum gust.
Output from saved artifact: status available, model_index 0.21, probability
0.021059018632974606, target_date 2026-10-18, model_version
county-weather-logreg-277e4566fcdb, feature_version daily-weather-v1,
computed_at UTC timestamp, outside_training_range [], and experimental note.
Unavailable returns status unavailable, null model_index/probability/model_version,
target_date, feature_version, computed_at and reason. None, missing features,
nonfinite features, negative rain/gust, and missing/corrupt artifacts were checked.
The interface does not accept a site ID or validate the geography/timezone/units
itself; A must provide correctly keyed and aggregated inputs and persist results.

Dependencies verified in the training environment: Python 3.12.10,
scikit-learn 1.8.0, pandas 2.2.3, numpy 2.3.5, joblib 1.5.3. Existing
ml/requirements.txt pins these packages; no shared dependencies changed.
Only trusted joblib artifacts may be loaded.

Remaining limitations: reported-event negatives do not prove safety; county
labels use representative-plant reanalysis rather than county-wide observations;
NOAA date conventions can differ near midnight; prior-year event spillovers
are not imported; modern county crosswalk boundaries were not historically
validated. Forecast-input performance/calibration is unmeasured. This models
selected severe-weather reports, not every required hazard, injuries, or causal
effects. Geographic extrapolation outside these counties needs disclosure.
The artifact does not persist outputs or connect backend/frontend/worker jobs.

Review commands: python -m ml.train; python -m ml.verify; python -m pytest
ml/test_ml.py tests/test_foundation.py -q -p no:cacheprovider. Audit passed;
12 tests passed. Git status/diff and tracked/ignored checks inspected. No shared
backend, frontend, schema, API contract, or dependency files changed. No download,
commit, push, or merge. Additional owned files: ml/verify.py and ml/START_HERE.md.
