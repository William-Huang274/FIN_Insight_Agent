# 312 - Backend / Frontend Runtime Docs Absorption

Date: 2026-06-14

## Prompt

The user provided two DOCX documents and asked to start a new "10" document for backend / frontend discussions:

- `D:\finsight_agent_升级方案_20260610\后端\Finsight后端升级可参考路线.docx`
- `D:\finsight_agent_升级方案_20260610\后端\企业级rag、agent项目参考及经验总结——后端开发.docx`

## Source Reading

Used `python-docx` to extract paragraph and table text from both files. The extraction covered:

- backend concepts: API, async tasks, DB, Redis, worker, Docker;
- stage 1: Run Manager, API, Redis queue, worker, SSE, DB persistence, Docker Compose;
- stage 2: worker pool, queueing, rate limit, idempotency, timeout/cancel, retry/backoff, worker heartbeat, events, cache, index, observability, load testing;
- stage 3: Java / Spring Boot as optional enterprise API layer rather than a rewrite of Python/LangGraph runtime;
- RAGFlow / MaxKB / Flowise lessons for ingestion, enterprise knowledge base, workflow UI, tool/node config, and execution trace;
- direct FinSight retrofit checklist: run lifecycle, Redis runtime, DB schema, worker pool, SSE, Docker Compose, load testing.

No DOCX visual/layout review was performed because this task only needed content absorption, not editing or delivering a formatted DOCX.

## Work Completed

- Added `docs/architecture/agent_graph_vnext/10_backend_frontend_runtime_framework.zh-CN.md`.
  - Records the core direction: FinSight should become an auditable financial research Agent Runtime, not a Java rewrite.
  - Defines FastAPI / Spring Boot / Python worker boundary.
  - Absorbs RAGFlow / MaxKB / Flowise lessons without turning FinSight into a generic RAG platform.
  - Defines backend phases: run lifecycle, concurrency/stability/recovery/load testing, optional Java API shell.
  - Defines DB, Redis, frontend, harness, and execution-order contracts.
- Updated `docs/architecture/agent_graph_vnext/README.zh-CN.md` with the 10 document.
- Updated `docs/worklog/00_internal_master_checklist.md` with backend/frontend runtime productization tasks.
- Updated `docs/worklog/README.md` with this checkpoint.

## Result

This is a docs-only checkpoint. Runtime behavior is unchanged.

## Follow-up

Next backend discussion should edit `10_backend_frontend_runtime_framework.zh-CN.md` directly. Before implementation, decide B0:

- FastAPI first,
- Spring Boot shell + Python worker,
- or FastAPI first with later Spring Boot parity.
