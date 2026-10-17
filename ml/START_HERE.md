# Install the C-only package

Copy the `ml` folder into the existing project root. Copy `docs/ML.md` into
the existing docs folder. Do not replace backend, frontend, .env, or other docs.
The package includes the real prepared five-county dataset and trained model;
raw provider downloads are excluded. output/ is gitignored to avoid accidentally
committing training data, but is included in this handoff for local reproduction.

From the project root in Windows PowerShell:

```powershell
git switch -c feature/ml
.\.venv\Scripts\python.exe -m pip install -r ml/requirements.txt
.\.venv\Scripts\python.exe -m pytest ml/test_ml.py -q
.\.venv\Scripts\python.exe -m ml.train
```

If the branch already exists, use `git switch feature/ml`.
The existing development requirements include pytest. If unavailable locally,
install requirements-dev.txt as documented by the starter.

Training uses the included prepared dataset. To independently recreate source
downloads and joins, run `python -m ml.build_dataset` with the venv Python.

Read docs/ML.md for the inference handoff to A. This package does not integrate
the model into Flask/Tiger Data or modify shared team contracts.

Commit only C's paths after reviewing git status:

```powershell
git add ml docs/ML.md
git commit -m "Add experimental county-day ML baseline and inference"
git push -u origin feature/ml
```

The trained artifact and results are tracked; intermediate output is ignored.
Keep the feature branch separate until A coordinates integration.
