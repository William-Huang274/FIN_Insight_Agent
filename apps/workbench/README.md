# FinSight Workbench

React/Vite frontend and FastAPI BFF for FIN 0.1.3. [中文使用说明](../../docs/public/quickstart.zh-CN.md) · [English quickstart](../../docs/public/quickstart.en.md).

## Product entry points

| Area | Route / source |
| --- | --- |
| Start and project navigation | `/workspace` · `frontend/vite/src/app/ResearchWorkspace.tsx` |
| Research methods and configuration | `/workspace?view=studio` · `ResearchStudio.tsx` |
| Report, map, sources, revisions, activity | `/workspace/session?thread=<id>` · `ResearchSession.tsx` |
| Research APIs | `backend/api/v1/report_sessions.py`, `research_studio.py` |
| Export | `backend/application/report_delivery.py` |
| App composition | `backend/app.py` |
| Runtime configuration contract | `../../src/sec_agent/agent_runtime/studio_configuration.py` |

The current product can create research, ask follow-up questions and request targeted revisions through a configured native LangGraph service. Reports remain versioned and subject to human review. Studio persists independent native Assistants snapshots; project grouping/pins remain browser-local.

The older fixed Evidence Pack APIs and `/operations` remain compatibility surfaces. Their readiness failures or retired action routes do not describe the newer research-session product.

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

For actual research, build the frontend and start the BFF with `python -m scripts.deployment.research_workbench serve` from the repository root and the required settings. See the quickstart for complete arguments and data requirements. Vite development defaults to proxying the older 8765 BFF; use the built frontend on the research BFF for the documented live walkthrough.

## Compatibility and naming

Public CLI and new session/configuration interfaces use research-oriented names. Older `dell_*` modules and the Compose identity are retained where renaming would affect imports, credentials, volumes or historical evidence. Their original names do not establish cross-company qualification, nor are they instructions to hardcode UI behavior to Dell.

Current evidence: local Dell research and targeted revision, bounded other-company questions, public synthetic interaction tests. This is a trusted local preview, without public multi-tenant authentication or unrestricted workflow-code editing.
