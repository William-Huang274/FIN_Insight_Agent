# 314 - Agent Eval Runtime Framework

Date: 2026-06-14

## Prompt

The user asked to close the final architecture loop with a separate 11 document for the evaluation system. The requested direction was to move from ad-hoc eval additions to a systematic agent eval system that supports auditability, replay, node-level and chain-level evaluation, failure sample accumulation, gold set promotion, and iterative dataset governance.

## Current System Audit

Reviewed the current FinSight eval and observability surfaces:

- `docs/eval/fin_agent_investment_research_quality_framework_v0_1.md`
- `docs/eval/fin_agent_layered_quality_execution_plan_v0_1.md`
- `docs/eval/fin_agent_full_chain_multiturn_eval_plan_v0_1.md`
- `docs/eval/sec_agent_resume_closeout_eval_v1.md`
- `docs/eval/sec_benchmark_v2_generalization_plan.md`
- `configs/fin_agent_quality_rubric_v0_1.json`
- `scripts/eval_multi_agent/*`
- `scripts/eval_retrieval/*`
- `scripts/eval_sec_benchmark/*`
- `scripts/eval_context/*`
- `tests/fixtures/*_cases_*.jsonl`
- `eval_sets/*.jsonl`
- `reports/model_runs/model_run_index.md`
- `src/sec_agent/run_audit_store.py`
- `src/sec_agent/llm_gateway.py`
- `src/sec_agent/langgraph_orchestrator.py`

Key finding: the project already has strong pieces: S0-S10 layered gates, SEC benchmark gold/pipeline/post-gate discipline, run audit tables, node checkpoints, model-call token/latency records, and model run ledgers. The gap is systemization: no single Eval Registry, no unified eval SQL schema, no stable failure/gold lifecycle, no default retrieval/rerank/role-visible audit for every run, and no 09/10-specific eval matrix for Research Lead review, targeted repair, context injection, model routing, and backend SLA.

## External References

Reviewed mature eval patterns from:

- LangSmith Evaluation
- OpenAI Evals
- Phoenix LLM Evals
- Ragas

The absorbed pattern is not generic RAG scoring. It is the governance loop: dataset + evaluator + experiment + trace + feedback + failure/gold lifecycle + dashboard.

## Work Completed

- Added `docs/architecture/agent_graph_vnext/11_agent_eval_runtime_framework.zh-CN.md`.
  - Audits the current eval system.
  - Defines unified Eval Runtime architecture.
  - Defines E0-E12 eval layers from data assets through online monitoring.
  - Defines eval SQL table draft.
  - Defines case, failure, and gold lifecycle state machines.
  - Defines failure taxonomy v0.1.
  - Defines required eval artifacts for every run.
  - Defines LLM-as-judge usage boundaries and audit requirements.
  - Defines frontend eval dashboard requirements.
  - Defines A0-A6 implementation sequence and first eval packs to add.
- Updated `docs/architecture/agent_graph_vnext/README.zh-CN.md` with the 11 document.
- Updated `docs/worklog/00_internal_master_checklist.md` with EV0-EV8 tasks.
- Updated `docs/worklog/README.md` with this checkpoint.

## Result

This is a docs-only architecture update. Runtime behavior is unchanged.

## Follow-up

Recommended next implementation step is EV1: build the Eval Registry catalog first, without changing existing runners. That gives the project a single inventory of current / superseded / diagnostic-only / deprecated eval packs before adding new SQL stores or dashboards.
