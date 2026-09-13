# Contributing with an assistant

Read `README.md`, `docs/README.md` and the documentation for the component you change. Check the working tree first and preserve unrelated edits. Use an isolated worktree for concurrent tasks.

- Keep product behavior, engineering validation and research-quality results distinct. Passing a synthetic test is not evidence that a financial conclusion is correct.
- Prefer maintained infrastructure for workflow execution, queues, persistence, parsing and retrieval. FIN code owns research contracts, financial semantics and thin integrations.
- Preserve source, period, unit, revision and citation identity. Treat a missing tool result as an execution problem until source availability has been checked.
- Model calls require explicit task scope and a `TokenBudgetBasis`: purpose, input scale, required output, quality risk, reasoning profile, limits and stop behavior. Do not silently omit necessary research to meet a lower budget.
- Run the checks relevant to the change. Keep failed paid requests and unknown usage in the user's local records; do not automatically resubmit them.
- Store generated datasets, credentials, run history and personal work notes outside Git. Do not make installation or CI depend on a developer's machine paths or private records. Optional local instructions may exist in Git-ignored `docs/project_os/`; they are not installation prerequisites.
- Name modules and configurations by maintained function. Keep wire IDs and database identities compatible unless an explicit migration is part of the task.
- Update reader-facing documentation when behavior changes. Explain material scope, compatibility or cost issues promptly and substantiate claims with reproducible evidence.

Common checks from the repository root:

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery --extra control-plane --extra qualification
uv run --no-sync python -m pytest -q
uv run --no-sync python scripts/engineering/verify_active_baseline.py
uv run --no-sync python scripts/engineering/check_repository_secrets.py
```

Frontend checks and deployment requirements are in `docs/public/quickstart.en.md` and `docs/public/quickstart.zh-CN.md`.
