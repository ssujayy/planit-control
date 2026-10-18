# C integration entry point

The verified implementation was pushed on feature/ml-expanded as commit
e4d57cfa42d56a3f51f2257fc8f2f00652768f88. For A: use the tracked artifact
and pinned ml/requirements.txt; inference requires no downloads, prepared data,
or retraining. See docs/coordination/C.md for the persistence field mapping.

The commands below describe the original local package/reproduction workflow,
not required integration steps. Do not switch branches, retrain, or copy folders
over existing work to integrate the saved model. ml/output is ignored and is
not shipped by Git; the full offline audit requires that preserved local data.
Run `python -m ml.verify` only where those prepared files exist.

## Original package reproduction notes

Copy the `ml` folder into the existing project root. Copy `docs/ML.md` into
the existing docs folder. Do not replace backend, frontend, .env, or other docs.
The current local package contains a prepared 54-county dataset and trained model;
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
```

The trained artifact and results are tracked; intermediate output is ignored.
Keep the feature branch separate until A coordinates integration. Commit, push,
or merge only when the human owner authorizes it. The current working branch is
feature/ml-expanded; do not switch away from another owner's uncommitted work.
