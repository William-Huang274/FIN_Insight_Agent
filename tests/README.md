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

Tests use synthetic data and temporary directories. Platform-specific checks run only on their supported platforms. Model adapters prove wiring and invariants, not financial judgment.

Synthetic tests check interfaces and invariants. Model quality must be evaluated separately from these engineering checks.

## Optional runtime and research integration

Runtime probes are in `tests/integration/`; their Docker opt-in and isolated attempt-directory requirements are described in [the qualification guide](../deploy/qualification/README.md). They do not run model requests by default.

Tests marked `local_data_integration` require `--run-private-data` plus explicit environment paths. Configure the resource mounts documented by the research runtime and `FINSIGHT_RESEARCH_RESOURCES_ROOT` (containing `foundation.json`, `source-routes.json`, `reviewed-evidence.json`, and `access-policy.json`). Dataset digests are still validated by the application. Do not restore retired private fixtures into the public checkout. Paid probes additionally require their individual opt-in variables and task-specific budget basis.

`test_multisource_project.py` exercises a separately prepared manifest of public originals through the project BFF and native source tools, using a scripted model. It requires `FIN_MULTISOURCE_MANIFEST` and a new `FIN_MULTISOURCE_OUTPUT` directory, but no legacy reference dataset. Its opt-in cost counterpart consumes that prepared project and an explicit model/budget profile; a saved answer is an engineering result awaiting financial review, not an accepted research report.
