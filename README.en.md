# FinSight Agent — FIN 0.1.3

**A financial-research workspace from question to an inspectable report.** The current dynamic research implementation lives on the development branch linked below. Runtime code on `main` remains the historical fixed Evidence Pack baseline, with different capabilities and startup instructions.

[Current product and code](https://github.com/William-Huang274/FIN_Insight_Agent/tree/codex/fin013-dell-s1-s2-product-bridge) · [Architecture](https://github.com/William-Huang274/FIN_Insight_Agent/blob/codex/fin013-dell-s1-s2-product-bridge/docs/public/architecture.en.md) · [Run and test](https://github.com/William-Huang274/FIN_Insight_Agent/blob/codex/fin013-dell-s1-s2-product-bridge/docs/public/quickstart.en.md) · [中文](README.md)

The development implementation includes dynamic multi-agent research, MCP data and calculation tools, cross-review, report follow-up and revision, task uploads, and source-bound exports in four formats. A real UI-started Dell case covered nine research topics and produced a report candidate. Final content and full-product acceptance remain open; this is not an unassisted one-shot benchmark or a production release. See the [current evidence and limitations](https://github.com/William-Huang274/FIN_Insight_Agent/blob/codex/fin013-dell-s1-s2-product-bridge/docs/public/sharing-scope.md).

The historical `main` workspace binds company identity and research-as-of dates for DELL, MU and NVDA to immutable reviewed Evidence Packs. It exposes accepted/rejected evidence and source boundaries; those packs contain no structured numeric items. The commands below run this historical baseline only. Use the linked development branch and guide for dynamic research.

## Run the historical main baseline

```powershell
python -m pip install -r requirements.txt
cd apps/workbench/frontend
npm ci
npm run build
cd ../../..
python scripts/dev/run_workbench_backend.py --host 127.0.0.1 --port 8765
```

- Product: `http://127.0.0.1:8765/workspace`
- Operations: `http://127.0.0.1:8765/operations`
- Health: `http://127.0.0.1:8765/api/health`

The repository does not distribute the private reviewed-pack objects. Without a mount, the case catalog remains visible, detail buttons are disabled, and `/api/readiness` returns a typed HTTP 503. For full case review, set `FINSIGHT_DATA_ROOT` to a data root containing `workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects`. Keep all credentials in environment variables and out of Git.

## Verify the historical main baseline

```powershell
python scripts/engineering/verify_active_baseline.py --pretty
python scripts/engineering/build_archive_redirect_index.py --check
python -m pytest -q
```

See the [current code map](docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md) and [current context pack](docs/project_os/current_context_pack.zh-CN.md) for the exact product and repository boundary.
