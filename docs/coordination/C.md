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

## Integration readiness review after e4d57cf

The verified implementation was committed and pushed on feature/ml-expanded
as e4d57cfa42d56a3f51f2257fc8f2f00652768f88. Earlier modified-file/no-commit
statements describe the pre-commit review. This follow-up preserves the model,
results, dataset and downloader unchanged.

| C requirement | Current implementation | Remaining action |
|---|---|---|
| Historical real-data pipeline | County crosswalk, C-only NOAA records, full county-day grid, cached weather, manifest hashes | No new downloads needed |
| Plant coverage | All 55 plants represented by 54 deduplicated counties | A attaches site IDs to saved outputs |
| Training/evaluation | Saved preprocessing/model, chronological splits, baselines, validation-selected threshold | No retraining needed |
| Experimental 0–10 index | Saved-model probability times ten; null for unavailable | A invokes/persists; D displays experimental label |
| Missing data/provenance | Input checks, range flags, manifest, versions, timestamps | A retains forecast provenance and freshness |
| Explanation semantics | Existing note and outside_training_range; no causal contributions claimed | No new explanation fields proposed |
| App integration | Pure callable ready; checked-out backend returns model_index null | A owns persistence/API/worker; D owns consumption |

A mapping to existing agreed prediction fields; no shared interface changes:

| Callable output | Persistence field / handling |
|---|---|
| No site identifier in callable | A attaches the originating stable site id |
| target_date | valid_date, the site's local forecast calendar date |
| model_index | score; preserve null for unavailable |
| model_version | model_version; null on unavailable is not a successful versioned prediction |
| feature_version | feature_version |
| computed_at | computed_at in UTC |
| status / reason | Handle unavailability explicitly; schema/API representation requires A's contract decision |
| probability / outside_training_range / note | Existing metadata; new persistence columns or public fields require agreement |

Supply complete daily forecast aggregates in documented units. The existing UTC
hourly window does not guarantee tomorrow's complete local day. A should use
verified site-local provider daily fields or validate complete local-day coverage
before aggregation. Missing, stale, failed or incomplete forecasts must not become
zero or a successful current prediction. Provider valid/retrieval time and units
are input provenance; computed_at is inference time, not provider retrieval time.

Lightning/replay state, reports/photos, briefings, hazard ranking, Shift Outlook,
map, migrations and worker registration remain outside C's files. Daily ML
outputs must not override official alerts or appear as hourly predictions.
No A log or integrated prediction worker is present in this checkout. This is
a documented handoff, not a claim of A's acceptance or an agent conversation.
No new response/explanation fields added. START_HERE now distinguishes saved
inference from original reproduction steps and the audit's ignored-data needs.

## Proposed optional model contributions for A/D

Add a separate C-only function `explain_site(features, target_date,
artifact_path=None)` in ml.predict. `predict_site()` and all its fields remain
unchanged. No backend/API/storage changes are proposed or implemented here;
A/D must agree before exposing this optional object through their interfaces.
The explanation function returns the existing prediction fields plus:

```json
{
  "model_contributions": {
    "label": "model contributions",
    "units": "model log-odds",
    "intercept": -4.0,
    "features": [
      {"feature": "temperature_2m_max", "value": 30.0,
       "transformed_value": 0.5, "contribution": 0.2}
    ],
    "decision_function": -3.8,
    "reconstructed_log_odds": -3.8,
    "reconstructed_probability": 0.021881270936130476,
    "note": "Signed contributions are relative to the model intercept; not causal effects or percentage-point changes."
  }
}
```

Numbers above illustrate the shape only; successful output includes all five
features. Unavailable predictions retain their existing null fields/reason and
add `model_contributions: null`. If prediction works but explanation is
incompatible or fails reconstruction, preserve the prediction and return a null
object plus explanation_reason. Seasonal sine/cosine encode the target date's
position in the annual cycle using (day-of-year minus one)/365.25.
Values precede preprocessing; transformed_value follows the saved imputer and
scaler. Each contribution is transformed_value times its fitted coefficient.
The intercept is the classifier intercept in standardized feature space, not a
safe-weather baseline. Contributions describe model arithmetic, not causality.

### Implemented optional function and actual example for D

`from ml.predict import explain_site` is implemented with the proposed separate
signature. Existing predict_site remains unchanged. For 2026-10-18 with daily
inputs 30 Celsius, 10 mm and 50 km/h, the actual model_contributions object
(rounded below for readability) is:

```json
{
  "label": "model contributions",
  "units": "model log-odds",
  "intercept": -4.9856877948,
  "features": [
    {"feature": "temperature_2m_max", "value": 30.0, "transformed_value": 0.6422806542, "contribution": 0.6777153248},
    {"feature": "precipitation_sum", "value": 10.0, "transformed_value": 0.7252105764, "contribution": 0.3354359328},
    {"feature": "wind_gusts_10m_max", "value": 50.0, "transformed_value": 1.3293862766, "contribution": 0.7315716942},
    {"feature": "season_sin", "value": -0.9620675725, "transformed_value": -1.3601137967, "contribution": -0.5257241632},
    {"feature": "season_cos", "value": 0.2728112643, "transformed_value": 0.3869146694, "contribution": -0.0724534429}
  ],
  "decision_function": -3.8391424491,
  "reconstructed_log_odds": -3.8391424491,
  "reconstructed_probability": 0.021059018633,
  "note": "Signed contributions are relative to the model intercept; not causal effects or percentage-point changes."
}
```

The surrounding existing prediction fields include model_index 0.21,
probability 0.021059018632974606, and the unchanged model/feature versions.
The daily inputs above are illustrative, not live forecast measurements.
Seasonal sine and cosine are two coordinates of the same annual-date encoding,
not independent measured weather hazards. Both must remain in the arithmetic.

D visualization suggestion: a horizontal diverging bar chart titled **model
contributions** with a zero-centered log-odds axis. Positive bars extend right
(pushed this prediction upward); negative bars extend left (downward). Show
all five feature names, original values/units and contribution values in labels
or tooltips. Label season_sin/cos as annual date encoding (sine/cosine),
dimensionless. Display the intercept separately, followed by reconstructed
log-odds and final daily experimental index. These bars are relative to the
model intercept, not a safe-weather baseline. Never label bars percent risk
change, risk reduction, causal importance, or safety clearance. Do not place
the daily explanation on an hourly timeline as if it were an hourly forecast.

Checks: 20 ML/foundation tests passed with
`python -m pytest ml/test_ml.py tests/test_foundation.py -q -p no:cacheprovider`.
Three dates/weather profiles (including leap day and out-of-range weather)
independently check original values, saved preprocessing, coefficients, sum,
decision_function, and predict_proba. Missing/malformed inputs and missing/
corrupt artifacts preserve unavailable behavior. A deliberately inconsistent
decision_function yields null model_contributions and explanation_reason while
retaining the valid prediction. Existing predict_site has no explanation fields.
Runtime reconstruction uses log-odds tolerance 1e-10 and probability relative
tolerance 1e-10 / absolute tolerance 1e-12; it uses a stable sigmoid.

Limitations: this explanation supports the current binary logistic pipeline
with classes [0, 1] and existing feature order only. Future non-linear or
multiclass models need a separately reviewed explanation method. It describes
fitted arithmetic, not calibration, causality or real-world hazard mechanisms;
the same historical/forecast domain shift and range limitations still apply.
The optional function loads the trusted artifact twice (prediction, then
explanation); mismatched model versions or reconstructed probabilities disable
the explanation. The baseline prediction is retained on explanation errors.
No artifact or evaluation changes, retraining, downloads, shared-file edits,
commits or pushes performed for this optional feature. A/D integration remains
pending; this proposal does not claim their acceptance.

## Independent contributions and challenger branch

Branch: feature/ml-contributions-challenger, created from published baseline
3c552f40f240c72f846607452e4568dae23d8a2f while preserving the existing
uncommitted explanation changes. No push or merge. Owned files for this step:
ml/predict.py, ml/test_ml.py, ml/benchmark.py, ml/test_benchmark.py,
ml/experiments/gbt_v1/*, docs/ML.md and this log.

Actual internal review: a delegated C reviewer inspected/finished contribution
validation and tests, then reviewed the benchmark methodology read-only. The
review found that correctly reconstructed totals could still have mislabeled
features after a preprocessing reorder. explain_site now checks saved output
feature names/order and one-output-per-input shape. The reviewer also identified
partial-output overwrite and zero-positive-state report-formatting gaps in the
benchmark; both were fixed. No A/D conversation or approval is implied.

Priority 1: optional interface above is unchanged. Added strict reconstruction,
seasonal-date encoding (including leap day/year-end), unavailable numeric-input,
and reordered-preprocessing tests. predict_site is unchanged from the published
baseline, including its default behavior. No new application fields were wired.

Priority 2: PLAN.md was written before running the experiment. Two histogram
gradient-boosting configurations (7 or 15 leaves, 100 rounds, learning rate
0.05, no internal random early stopping) were compared on two expanding folds:
2022 -> Jan–Jun 2023, and 2022–Jun 2023 -> Jul–Dec 2023. Each fold owns its
imputer; the logistic control also owns its fitted scaler. Configuration chosen
by pooled 2023 AP; threshold chosen by pooled 2023 F1 on a fixed 0.01–0.50
grid. Both selections were saved before 2024 scoring. Six fold fits plus two
final 2022–2023 fits exhausted the eight-fit budget; no further tuning occurred.

Results: selected seven-leaf tree. Pooled 2023 AP 0.1177 versus logistic 0.1060
(prevalence baseline 0.0213); both folds improved AP. At selected threshold 0.05,
tree recall 0.5238 versus 0.3476, precision 0.1191 versus 0.1245, false alerts
8.25 versus 5.21 per 100 county-days. The predeclared evidence screen failed
because the tree increased false-alert burden.

2024 is an already-inspected development comparison. Tree AP 0.1345 versus
matched 2022–2023 logistic control 0.1230 and frozen production logistic 0.1243
(baseline 0.0158). Tree recall 0.6250, precision 0.0987, false alerts 9.01/100
and 9.99% flagged, compared with production recall 0.4455, precision 0.1380,
false alerts 4.39/100 and 5.10% flagged. No 2024 tuning or threshold selection.
Retain production logistic: higher AP/recall alone does not establish a suitable
operational tradeoff or forecast performance.

One-thread experiment wall time 7.37 seconds; final tree fit 0.574 seconds
versus matched logistic 0.048 seconds. Warm one-row pipeline inference medians
were 2.108 ms tree, 0.940 ms control, 0.910 ms production. These are local CPU
timings excluding artifact loading, not deployment latency guarantees. Windows
joblib warned that physical-core discovery failed and used logical cores; the
run completed under threadpoolctl's one-thread limit.

Compact comparison: ml/experiments/gbt_v1/REPORT.md. Full pooled/fold/state and
threshold metrics, counts, dependencies, timings and hashes: results.json and
selection.json there. Threshold tables cover 0.01, 0.02, 0.05, 0.10 and 0.20.
Artifacts challenger.joblib and logistic_reference.joblib are research-only,
evaluated directly as fitted pipelines; they are not predict_site replacements.
The production artifact SHA-256 remains
ad0f5f4d03561885d0ead33a3f5e0e6b89c93869989a1a9e341d6a932955ccf2.
Prepared data, production results, backend/frontend/schema/worker are preserved.

Verification: 39 focused ML/benchmark/foundation tests passed (one nonfatal
physical-core warning). Tests cover chronological 2024 exclusion, fold-local
preprocessing, F1 tie-breaking, denominator-correct false-alert rates, state
alignment, sparse-label handling, partial-run preservation, and saved research
artifact/hash/metric reproduction without retraining. The original offline audit
is also rerun for coverage and production-artifact consistency. Diff check passes.

A/D handoff: retain the existing predict_site and default artifact. The only
proposed application addition is optional model_contributions via explain_site,
pending your API/storage/display agreement. Use the example and horizontal-bar
guidance above; do not apply this linear decomposition to the tree. No model
switch, migration, dependency change or worker change is proposed. Limits include
reported-event negatives, spatial/temporal correlation, selection optimism,
small state positive counts, historical reanalysis/forecast shift, and absence
of calibration or untouched future-year evidence. False alerts mean no selected
reported event, not proof that the day lacked hazards.

## Final publication handoff

The report now separates threshold-independent AP/prevalence baseline from
precision/recall/false-alert/flagged-volume metrics at validation-selected
thresholds. It explicitly marks all 2024 comparisons as already-inspected
development evidence. Added a post-experiment diagnostic using only saved 2023
threshold summaries: at roughly matched recall (tree 77.86%, logistic 73.10%),
tree false alerts are 18.92 versus 25.23 per 100 days. At roughly matched volume
(28.89% versus 26.79% flagged), tree recall is 88.57% versus 73.10%, with
27.01 versus 25.23 false alerts/100. These coarse high-recall comparisons expose
an operating-point tradeoff, not universal tree inferiority. Gaps are explicit;
no interpolation, additional fits, threshold updates or 2024 tuning occurred.
The original predeclared screen/retained production model decision stands.

Exact executable A/D invocation and units: ml/CONTRIBUTIONS.md.
Full captured example JSON: ml/examples/contributions.json. Optional invocation
is explain_site(features, target_date, artifact_path=None); default predict_site
is unchanged. The intercept is zero transformed input (training-feature means),
not a safe-weather baseline. The seasonal sine/cosine pair encodes calendar date;
signed contributions are model log-odds, not probability-point changes.

Intentionally include in this C commit: contribution implementation/tests/docs
and example; offline benchmark/tests; experiments/gbt_v1 PLAN.md, REPORT.md,
selection.json, results.json, challenger.joblib and logistic_reference.joblib.
Exclude ignored ml/output, data/raw, caches, environment files and secrets.
No production artifact/results, default inference body, or shared application
files changed. Research artifact binaries and selection metrics remain intact.
Experimental metadata now uses portable slash paths and normalizes JSON line
endings for protected-file hashes, so Git CRLF conversion does not break audits.

Reproduction without overwriting this experiment (prepared data required):

```powershell
.\.venv\Scripts\python.exe -m ml.benchmark --output-dir ml/output/gbt_v1_reproduction
```

The destination must be unused. This command performs the declared eight fits
using existing dependencies/data, with no downloads, and saves separate outputs.
It was documented but not run during finalization: all report edits use saved
metrics. For verification without fitting, run the benchmark/ML tests and
python -m ml.verify. Dataset/manifest remain ignored and require separate local
transfer for offline reproduction; application inference only needs the tracked
published model. Saved-model hashes are exact for binaries, LF-normalized for
protected JSON. Timings/timestamps are machine/run-specific.

Final checks: 41 focused ML/benchmark/foundation tests passed, with the documented
nonfatal Windows core-discovery warning. Offline ml.verify passed and benchmark
--help confirmed the reproduction option; no experiment rerun was performed.
Independent read-only review confirmed the published predict_site AST and
production artifact are unchanged, reviewed matched-point interpretation, and
checked artifact/selection hashes. Production results match Git content (checkout
line endings aside). Shared files and credentials were not edited. Full example
JSON was captured from the saved logistic artifact. Final report narratives are
generated from saved metrics so reproductions cannot silently reuse stale values.
