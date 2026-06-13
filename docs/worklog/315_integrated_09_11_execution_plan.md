# 315 - Integrated 09-11 Execution Plan

Date: 2026-06-14

## Prompt

The user asked to turn the 09 Research Lead framework, 10 backend/frontend runtime framework, and 11 eval runtime framework into a next-stage execution plan. The plan should not implement 09, 10, and 11 independently; it should organize work by functional slices, with sync/async dependencies, Python agent changes, backend/frontend changes, Java backend options, and eval gates for each step.

## Work Completed

- Added `docs/architecture/agent_graph_vnext/12_integrated_execution_plan.zh-CN.md`.
  - Defines the next stage as an integrated auditable research Agent Runtime rather than separate agent/backend/eval efforts.
  - Introduces P0-P10 functional slices:
    - P0 baseline / registry / backend route decision.
    - P1 run and audit foundation.
    - P2 eval store and failure/gold skeleton.
    - P3 context runtime.
    - P4 retrieval/rerank/role-visible ledgers and resource scheduler.
    - P5 Research Lead supervised loop.
    - P6 tool capability and document/multimodal input.
    - P7 judgment/memo/verifier surface.
    - P8 frontend trace and eval dashboard.
    - P9 concurrency/SLA/optional Java shell.
    - P10 full-chain regression and online eval governance.
  - Gives each slice Python agent work, backend/frontend work, eval gates, sync barriers, parallelizable work, pass criteria, and failure handling.
  - Explicitly recommends starting with Eval Registry, run/audit foundation, eval store, and retrieval/role-visible audit before large graph or memo-surface changes.
- Updated `docs/architecture/agent_graph_vnext/README.zh-CN.md` with the 12 document.
- Updated `docs/worklog/00_internal_master_checklist.md` with P0-P10 integrated execution tasks.
- Updated `docs/worklog/README.md` with this checkpoint.

## Result

This is a docs-only planning update. Runtime behavior is unchanged.

## Follow-up

Recommended implementation start:

1. P0: Eval Registry + B0 backend route decision.
2. P1: Run / Audit Foundation.
3. P2: Eval Store minimal adapters.
4. P4: Retrieval/rerank/role-visible evidence ledgers, because this is the highest-risk known root-cause area.
