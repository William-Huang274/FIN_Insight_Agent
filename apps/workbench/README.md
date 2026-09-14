# FinSight Workbench

React/Vite frontend and FastAPI BFF for FIN 0.1.3. [中文使用说明](../../docs/public/quickstart.zh-CN.md) · [English quickstart](../../docs/public/quickstart.en.md).

## Product entry points

| Area | Route / source |
| --- | --- |
| Start and project navigation | `/workspace` · `frontend/vite/src/app/ResearchStart.tsx`, `WorkspaceNavigation.tsx` |
| Project documents (0.1.4 development) | `/workspace/session?view=project&project=<id>` · `ProjectLibrary.tsx`, `backend/api/v1/projects.py` |
| Research methods and configuration | `/workspace?view=studio` · `ResearchStudio.tsx` |
| Report, map, sources, revisions, activity | `/workspace/session?thread=<id>` · `ResearchSession.tsx` |
| Research APIs | `backend/api/v1/report_sessions.py`, `research_studio.py` |
| Export | `backend/application/report_delivery.py` |
| App composition | `backend/app.py` |
| Runtime configuration contract | `../../src/sec_agent/agent_runtime/studio_configuration.py` |

The current product can create research, ask follow-up questions and request targeted revisions through a configured native LangGraph service. Reports remain versioned and subject to human review. Studio persists independent native Assistants snapshots. On the 0.1.4 development branch, project grouping/pins persist in the BFF's private SQLite store with revision checks. Old browser records remain available for explicit import into an empty server index. Project documents reuse existing parsers and support bounded literal text lookup. Selected files become independent research-task snapshots with project/document provenance, available through the existing research source tool. Uploads remain unverified; incomplete preparation blocks model startup. Snapshot revocation and live synchronization are not implemented.

The older fixed Evidence Pack view is available at `/workspace/evidence-packs`; its APIs and `/operations` remain compatibility surfaces. Their readiness failures or retired action routes do not describe the newer research-session product. The default `/workspace` opens the current question-first UI.

## Develop and verify

From this directory's `frontend/`:

```bash
npm ci
npm run typecheck
npm run build
npx playwright install chromium
npm run test:public
```

Public browser tests start Vite on 4183 with synthetic API fixtures; no BFF or model. The original `npm run test:e2e` also starts the historical BFF and covers legacy source-only behavior.

The isolated project slice uses `playwright.project.config.ts`, a new `FINSIGHT_LOCAL_STATE_ROOT` per attempt, and the existing Windows `.venv` Python. It starts the actual BFF with native draft metadata/configuration stubbed and run dispatch disabled, uses real project APIs/SQLite, and verifies desktop/mobile upload, selection, draft snapshots and browser reload. It uses free ports 8767 and the already-authorized development origin 5173; check availability first. No model requests. The separate specialist graph test uses the real graph/MCP with deterministic model decisions. See [E2 evidence and limits](../../docs/worklog/fin_0_1_4/011_e2_project_materials_into_research.md).

For actual research, build the frontend and start the BFF with `python -m scripts.deployment.research_workbench serve` from the repository root and the required settings. See the quickstart for complete arguments and data requirements. Vite development defaults to proxying the older 8765 BFF; use the built frontend on the research BFF for the documented live walkthrough.

## Compatibility and naming

The `research_workbench` CLI and runtime modules use functional names. Existing graph IDs, database identities and Compose volume names remain compatible with saved tasks.

Current evidence: local Dell research and targeted revision, bounded other-company questions, public synthetic interaction tests. This is a trusted local preview, without public multi-tenant authentication or unrestricted workflow-code editing.
