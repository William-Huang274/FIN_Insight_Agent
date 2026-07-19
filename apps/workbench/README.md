# FinSight Workbench

This directory contains the current FIN 0.1 product runtime.

## Active Runtime

- Backend entrypoint: `backend/app.py`
- Versioned API: `backend/api/v1/`
- Application services: `backend/application/`
- React/Vite source: `frontend/vite/src/`
- Dependency authority: `frontend/package.json` and `frontend/package-lock.json`
- Local operator scripts: `../../scripts/workbench/start_internal_alpha.ps1` and `stop_internal_alpha.ps1`

`/next` is the current internal-alpha product presentation. The older task/case routes remain available as rollback and compatibility surfaces; they are not a second release authority.

## Current Product Boundary

The active FIN 0.1 research preview is local, read-only and deterministic. It can project Case, DecisionSurface, local evidence candidates, numeric facts, repair decisions, Workpaper, Deliverable, Trace and Human Baseline surfaces. It does not prove paid-model execution, agentic search, exact Senior R2 acceptance, RG1, release admission or production readiness.

The backend still imports selected historical `sec_agent.workbench`, R53-R60 and checkpoint inspection APIs. Those imports are compatibility dependencies. The historical Multi-Agent LangGraph is not the execution engine behind the current FIN 0.1 local research service.

See `../../configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json` and `../../docs/architecture/repository/FIN_0_1_CODE_MAINLINE_ARCHIVE_AND_DISCONNECTION_AUDIT_20260719.zh-CN.md` for the authoritative path classification.
