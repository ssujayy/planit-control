# C — experimental county-day weather model

## Scope

Predict whether a selected NOAA severe-weather event was reported in a county
on a local calendar day. This is not an injury model, complete hazard index,
calibrated operational probability, or safety clearance. Official warnings and
lightning holds remain independent.

Initial events: Thunderstorm Wind, Hail, Tornado, Flash Flood. Only CZ_TYPE=C
records are used. Negatives mean no selected event reported, not proven absence.

## Run from repository root (Windows PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-data.txt
.\.venv\Scripts\python.exe -m ml.build_dataset
.\.venv\Scripts\python.exe -m ml.train
.\.venv\Scripts\python.exe -m pytest ml/test_ml.py -q
```

Builder default: five counties, geographically selected one per state, 2022–2024.
Do not select counties based on final-test performance. To expand after proving
the pipeline, use `--limit 0` (all 54 unique counties); this makes more provider calls and
requires retraining/evaluation. Do not change geography just to improve scores.

The current saved artifact uses the already expanded local dataset: 54 unique
counties covering the 55 plant locations, 59,184 county-days during 2022–2024,
1,058 positive days, and no missing weather features. The dataset hash is recorded
in ml/results.json and checked against the source manifest before training.
2024 test average precision is 0.1243 versus the constant baseline's 0.0158;
precision is 0.1380 and recall 0.4455 at the validation-selected threshold 0.05.
These are retrospective reported-event metrics, not operational forecast accuracy.

Raw downloads are cached under gitignored data/raw/ml. Prepared dataset,
crosswalk, event examples, and source hashes are under ignored ml/output.
The model is ml/artifacts/model.joblib; evaluation is ml/results.json.
Only load trusted joblib artifacts. Pin/record the training dependency versions
when sharing an artifact; incompatible sklearn versions may fail to load.

## Data construction

1. Read existing EIA plants; never modify their source file.
2. Match state/county name to official NWS county FIPS. Require a unique match.
   The zone-county file has repeated county rows; collapse FIPS matches, not zones.
   Never use its zone centroid as a county centroid.
3. Deduplicate counties and select deterministically across states.
4. Discover NOAA annual details archives and cache full files with hashes.
5. Restrict geography and event types, deduplicate event IDs, expand begin/end
   local calendar dates. Mark each county-day with 0 or 1.
6. Retrieve Open-Meteo archive daily summaries at the representative plant,
   using its local timezone and explicit units.
7. Build the complete date grid, including days without reports. Fail on missing
   or reordered dates, unexpected units, ambiguous counties, or duplicate rows.
8. Save dataset and manifest with prevalence, missingness, sources, and hashes.

## Model/evaluation

2022 training, 2023 validation, 2024 final test. All counties use the same time
boundary. Median imputation, scaling, and logistic regression are fitted only
on training rows. No class weighting or probability calibration is claimed.
Choose a threshold by validation F1 over a predeclared fixed grid. Final test
reports average precision, precision/recall, ROC-AUC where defined, and constant/
always-negative baselines. Training refuses splits missing either class.

Features: temperature_2m_max (Celsius), precipitation_sum (mm/day),
wind_gusts_10m_max (km/h), and seasonal sine/cosine derived from target date.
Inference rejects missing/nonfinite daily inputs even though training has an
imputer. Inputs must be full local-day aggregates, not current readings.

## Handoff to A

```python
from ml.predict import predict_site

prediction = predict_site(
    {'temperature_2m_max': 30.0,
     'precipitation_sum': 12.0,
     'wind_gusts_10m_max': 55.0},
    target_date='2026-10-18',
)
```

These input numbers are illustrative, not live forecast data. A must aggregate
or request tomorrow's full site-local forecast day in the specified units.
The existing two-UTC-day hourly response may not include the entire next local
day: request sufficient coverage or provider daily values with site timezone.

Available result: status, model_index (10 times raw probability), probability,
target_date, model_version, feature_version, computed_at, and range warnings.
Unavailable result: null score/probability plus reason. Persist the output using
the shared agreed database schema; C does not change schema or register jobs.

The saved model is trained on the 54 plant counties, so predicting other counties
is geographic extrapolation. A/D must label that scope. Out-of-training-range
weather is flagged. Do not rank above official warnings based on this index.

## Limitations

- Representative-plant reanalysis weather is not county-wide observed weather.
- Reported events are incomplete and depend on reporting practices.
- NOAA local event dates and weather civil dates can differ near midnight.
- Events are expanded across touched dates, but previous-year spillover is not
  imported into the next year's archive processing.
- Modern county crosswalk is used for 2022–2024; relevant boundary changes would
  require historical validation before operational use.
- Same-day observed/reanalysis evaluation does not measure next-day forecast
  performance. Forecast-input domain shift is not quantified.
- Small sample and spatially correlated days limit statistical confidence.

## Official sources

- https://www.weather.gov/gis/ZoneCounty
- https://www.weather.gov/source/gis/Shapefiles/County/bp16ap26.dbx
- https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/
- https://open-meteo.com/en/docs/historical-weather-api

OpenAI ChatGPT/Codex assisted with this implementation. Source data are not
fabricated. Check ml/results.json and the manifest for actual executed results.
