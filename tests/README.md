# Testing FinSight Agent

FinSight v0.1.3 · [中文步骤](../docs/public/quickstart.zh-CN.md) · [English instructions](../docs/public/quickstart.en.md)

## Public checkout

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout --output-directory .local/public-check-01
```

Exercises attachments, delivery, Studio configuration and targeted revision, then exports clearly synthetic reports. No model credentials, private data or Docker. Existing output directories are rejected. The maintained exporter is `scripts.dev.export_synthetic_report`.

## Browser interactions

From `apps/workbench/frontend`, install dependencies and Chromium, then run `npm run test:public`. The public profile serves Vite with synthetic API responses. It covers navigation, source access, revision differences, configuration and replay at desktop/tablet/mobile widths. These are interaction checks, not live research-quality evidence.

The default `test:e2e` additionally launches the supported source-only BFF. CI runs both profiles.

## Full suite

The complete pytest suite needs the `control-plane` and `qualification` dependency extras in addition to the public-check extras. These dependency profiles do not restore retired experiment runners.

```bash
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery --extra control-plane --extra qualification
uv run --no-sync python -m pytest -q
uv run --no-sync python scripts/engineering/verify_active_baseline.py --pretty
```

Tests marked `local_data_integration` or `requires_local_data` skip by default. `--run-private-data` requires the original private mounts. Synthetic model adapters prove wiring and invariants, not financial judgment.

Synthetic tests check interfaces and invariants. Private-data tests require their original sources; model quality must be evaluated separately from these engineering checks.
