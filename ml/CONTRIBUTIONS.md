# Optional logistic model contributions: A/D handoff

Default application call remains `predict_site(features, target_date)`.
After agreeing how to expose the optional metadata, A can call:

```python
import json
from ml.predict import explain_site

result = explain_site(
    features={
        "temperature_2m_max": 30.0,  # Celsius, full local-day maximum
        "precipitation_sum": 10.0,  # mm, full local-day total
        "wind_gusts_10m_max": 50.0,  # km/h, full local-day maximum
    },
    target_date="2026-10-18",
    artifact_path=None,  # published logistic artifact
)
print(json.dumps(result, indent=2, allow_nan=False))
```

These inputs are illustrative, not a retrieved forecast. The exact captured
JSON response is [examples/contributions.json](examples/contributions.json),
including the five feature entries and existing prediction fields. computed_at
changes with each call. This example gives probability 0.021059018632974606,
model_index 0.21, intercept -4.98568779481381, total log-odds
-3.839142449107648 and reconstructed probability 0.021059018632974616.

Each feature entry contains its original `value`, saved-preprocessing
`transformed_value`, and signed `contribution` to **model log-odds**.
Contribution = standardized value times the fitted logistic coefficient.
The intercept plus all contributions reconstructs decision_function; the logistic
function of that sum reconstructs predict_proba. Contributions are not
probability-point changes, calibrated risks, or causal effects.

The intercept corresponds to zero in the model's transformed feature space.
With the saved scaler, this means training means of the imputed features; it
is not a safe-weather baseline or necessarily a realizable weather/date profile.
season_sin and season_cos are dimensionless encodings of the target calendar
date: sin/cos of 2*pi*(day-of-year minus one)/365.25. They jointly represent
annual position; both are included, even on leap days. Caller-provided seasonal
values are ignored in favor of this shared date encoding.

D can render a horizontal diverging chart titled **model contributions**:
positive log-odds bars to the right, negative to the left, with a zero line.
Show the intercept separately, original feature values/units, and final daily
experimental index. Label seasonal bars "annual date encoding (sine/cosine)".
Interpret bars relative to the fitted intercept, not a safety threshold.

For invalid inputs or unusable artifacts, all existing unavailable fields/reason
are preserved and model_contributions is null. If only the explanation fails,
the valid prediction is preserved with model_contributions null and
explanation_reason. No field is added to predict_site itself. This implementation
supports the saved binary logistic pipeline with its named, unchanged feature
order; it is not a tree explanation API.

Only ml/predict.py needs application integration. ml/test_ml.py and this document
support that integration. No backend/frontend/storage/worker change is included.
Model contribution exposure remains an additive A/D interface proposal.

The separate ml/benchmark.py, ml/test_benchmark.py and experiments/gbt_v1 files
are offline research. The research artifacts are intentionally committed but
must not be substituted for the published artifact. See the experiment REPORT.md
for validation tradeoffs, preservation of the default model, and reproduction.
