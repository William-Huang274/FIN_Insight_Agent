# FinSight Agent — FIN 0.1.3

FinSight Agent is currently a local, auditable financial-research workspace baseline. It binds the legal identity and research-as-of date of three reviewed cases—DELL, MU and NVDA—to immutable Evidence Packs, then exposes accepted evidence, rejected evidence, source boundaries and residual gaps through a real browser UI. The current packs contain no structured numeric items, so numeric-fact readiness is not claimed.

This release does not claim open-ended agentic research, realtime market data, autonomous report publication or production multitenancy. Those capabilities remain on the product roadmap and must pass their own research-quality acceptance before promotion.

## Run locally

```powershell
uv sync --locked
cd apps/workbench/frontend
npm ci
npm run build
cd ../../..
uv run --locked python scripts/dev/run_workbench_backend.py --host 127.0.0.1 --port 8765
```

Python dependencies are maintained only in `pyproject.toml` and pinned by the tracked `uv.lock`; do not add a second hand-maintained requirements file.

- Product: `http://127.0.0.1:8765/workspace`
- Operations: `http://127.0.0.1:8765/operations`
- Health: `http://127.0.0.1:8765/api/health`

The repository does not distribute the private reviewed-pack objects. Without a mount, the case catalog remains visible, detail buttons are disabled, and `/api/readiness` returns a typed HTTP 503. For full case review, set `FINSIGHT_DATA_ROOT` to a data root containing `workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects`. Keep all credentials in environment variables and out of Git.

## Verify the baseline

```powershell
uv run --locked python scripts/engineering/verify_active_baseline.py --pretty
uv run --locked python scripts/engineering/build_archive_redirect_index.py --check
uv run --locked python -m pytest -q
```

See the [current code map](docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md) and [current context pack](docs/project_os/current_context_pack.zh-CN.md) for the exact product and repository boundary.
