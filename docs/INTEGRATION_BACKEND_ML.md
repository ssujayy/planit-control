# Backend and ML merge handoff

The local `integration/backend-ml` branch combines `ad-backend` at `470241f`
and `feature/ml-contributions-challenger` at `340e323`, including their common
`main` ancestor. Git applied the merge without conflicts. Both owners' source
files and model artifacts are preserved.

## Included

- Backend migrations, stored weather/NWS ingestion, evidence ranking and the
  existing repositories for predictions, lightning, reports and briefings.
- Saved logistic model, evaluation, inference and optional model contributions.
- Separate offline tree-comparison code, results and research artifacts. The
  logistic artifact at `ml/artifacts/model.joblib` remains the default.

Install both environments' Python dependencies from the repository root:

```bash
python -m pip install -r requirements-dev.txt -r ml/requirements.txt
python -m pytest -q -rs
```

Use the existing `frontend/` directory for `npm ci`, `npm run dev` and
`npm run build`; Flask serves `frontend/dist`. The additional root-level
`src/`, package files and Vite config arrived on `ad-backend` and are preserved,
but the documented frontend startup path remains `frontend/`.

## Remaining connections

The merge does not register an inference job or populate predictions. Connect
full site-local daily forecast summaries to `ml.predict.predict_site`, persist
available results through `backend.db.save_prediction`, and register a bounded
job with the existing worker. Follow [the API contract](API_CONTRACT.md),
[the backend handoff](BACKEND_HANDOFF.md) and [the model handoff](ML.md).
Keep missing model results unavailable and official warnings independent.

The existing frontend still needs to consume the ranked Outlook and saved model
outputs. Live strike ingestion, report upload APIs and briefing scheduling also
remain unfinished. Prepared historical data under `ml/output` are ignored by
Git; full training-data audits and tree-result reproduction require those files.
The saved model can perform inference without downloading or retraining.

## Verification on October 17, 2026

- Installed `requirements-dev.txt` and `ml/requirements.txt` together in `.venv`.
- `python -B -m pytest -q -rs`: 70 passed, 12 skipped. Eleven skips require a
  configured PostgreSQL connection; one requires ignored offline experiment
  data. `DATABASE_URL` is not configured in this clone.
- `npm ci` and `npm run build` in `frontend/`: passed.
- The sandbox blocked Vite's subprocess and some pytest temporary-file
  operations; the successful build and test runs used approved execution
  outside the sandbox. No live database or provider refresh was performed.
