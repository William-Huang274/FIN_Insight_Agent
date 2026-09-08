# Testing FinSight Agent

[中文测试步骤](../docs/public/quickstart.zh-CN.md) · [English instructions](../docs/public/quickstart.en.md)

## Public checkout check

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout --output-directory .local/public-check-01
```

Runs the bounded attachment, report delivery, Studio configuration and targeted revision tests, then exports clearly synthetic reports. No model credentials, private data or Docker. Existing output directories are rejected. Current result: 34 passed, four report formats exported.

## Browser interactions

From `apps/workbench/frontend`, install dependencies and Chromium, then run `npm run test:public`. The Playwright public profile serves Vite only and intercepts research APIs. Thirteen tests cover report/source navigation, target isolation, expandable diffs, configuration save/apply, project organization and historical replay across desktop/tablet/mobile widths. These are synthetic interaction checks, not live backend or research-quality evidence.

The default `test:e2e` additionally launches the old source-only BFF. CI runs both the default profile and the independent public profile.

## Full suite and private evidence

The complete pytest suite needs the `control-plane` and `qualification` extras in addition to the public-check extras. Tests marked `local_data_integration` or `requires_local_data` skip by default. `--run-private-data` requires the original private mounts and does not turn missing inputs into a pass.

Live model calls are separate, explicitly scoped operations. They are not launched by these public commands. Native graph tests may execute synthetic model adapters; that proves wiring and invariants, not financial judgment quality.

Historical code and tests under `archive/versions/` are excluded from normal discovery. Some current governance tests verify historical Git blobs and need full history. Do not combine public passes, skipped private tests and paid case evidence into one accuracy score.
