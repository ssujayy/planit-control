# PlanIT Control repository instructions

Build Sperry's utility site safety prototype during SwampHacks XII. The team uses React with JavaScript, Flask, Tiger Data PostgreSQL and Python ML. Read README.md and docs/API_CONTRACT.md first.

- Keep edits within your owned module; coordinate schema and API changes with the team.
- Preserve visible distinctions among demo storage, live data, forecasts, cached data and replay.
- Never fabricate a model output, hazard score, credential, current operating status or successful integration.
- No source failure may produce an all-clear claim. Keep alert components independent.
- Keep secrets in .env and outside logs. Use parameterized SQL.
- The scheduler belongs in one separate worker, not a Flask request or reloader hook.
- Add focused checks for meaningful behavior changes; run the existing foundation tests and frontend build after integration.
- This starter is not the completed six-item Sperry submission. The remaining work is in docs/WORKSTREAMS.md.
- Credit AI tools, libraries and source datasets in the submission. Do not add dependencies or architecture without explaining their purpose to the team.

