# 313 - Backend Context Management Absorption

Date: 2026-06-14

## Prompt

The user asked to extend the 10 backend / frontend runtime document with context management, using the previously discussed GitHub projects and Hermes-style enterprise agent context management as references, then align those lessons with FinSight's existing context handling.

## Source Review

Reviewed the existing FinSight context surfaces:

- `src/sec_agent/context_manager.py`: tenant / user / session scoped context snapshots, lossless fields, artifact state, resume cursor, source policy, recent-turn and candidate-session budgets.
- `src/sec_agent/specialist_llm.py`: `shared_specialist_context`, role-specific specialist request views, prompt row compaction, and specialist fanout barrier.
- `src/sec_agent/analyst_view_layer.py`: D11 analyst view / research memory entries, with the important policy that views are indexes and must drill down to claim / gap / derived refs.
- `docs/architecture/agent_graph_vnext/08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md`: D11 / D12 context reader, D-series memory materialization, and DB-default cross-run context.
- `docs/architecture/agent_graph_vnext/09_lead_supervised_closed_loop_research_framework.zh-CN.md`: Research Lead closed loop, LeadReviewCheckpoint, TargetedRepairPlan, JudgmentState, MemoLogicPlan, role-specific selectors, and context / resource scheduling.

Also reviewed public context / memory designs from RAGFlow, MaxKB, Flowise, and Hermes Agent documentation.

## Work Completed

- Updated `docs/architecture/agent_graph_vnext/10_backend_frontend_runtime_framework.zh-CN.md`.
  - Added external reference links for RAGFlow Memory, MaxKB long-term memory / workflow variables, Flowise memory backends, and Hermes ContextEngine / ContextCompressor docs.
  - Added a new `上下文管理与 Memory Runtime` section.
  - Defined FinSight context taxonomy: user session, run working context, shared agent context, role-private context, evidence context, analyst view memory, episodic run memory, semantic domain memory, artifact context, and resource context.
  - Defined a ContextEngine facade: resolver, selector, compressor, injection planner, writer, consolidator, invalidator, and retriever.
  - Defined per-node injection rules for Research Lead, evidence operators, specialists, LeadReviewCheckpoint, Memo Writer, and Verifier / Editor.
  - Added storage boundaries across SQL, Redis, object store, and Milvus.
  - Added memory status progression and governance rules so memory cannot bypass evidence gates.
  - Added context management acceptance gates: tenant isolation, injection audit, token budget, memory drilldown parity, evidence boundary, staleness, replay, and frontend visibility.
- Updated DB and Redis runtime draft in 10 doc with context tables / keys.
- Updated frontend direction with a `Context trace` viewer.
- Updated execution order so Context Runtime v0 lands before frontend deep trace and Spring Boot parity.
- Updated `docs/worklog/00_internal_master_checklist.md` with B9 / B10 / B11 backend context runtime tasks.

## Result

This is a docs-only architecture update. Runtime behavior is unchanged.

## Follow-up

Before implementing backend P0, decide whether B9-B11 should be built as:

- a Python worker-side ContextEngine first,
- a FastAPI service facade over the existing Python context manager,
- or a Spring Boot API shell that delegates context selection / compression to the Python worker.
