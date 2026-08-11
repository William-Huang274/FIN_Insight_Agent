# 019 R53-R60 Unified Demand Backlog Execution Plan

日期：2026-06-29

阶段：R53-R60 product strategy / engineering framework

状态：docs-only execution planning draft

## Prompt

用户要求提交当前文档，并重新回看 PRD 和 R 系列文档，给出接下来需求单的具体划分和单 agent 可执行顺序。

## Reasoning

当前 R53-R60 文档已经形成 PRD、runtime、graph/skill/memory、DB/RAG、backend/frontend、eval/observability 的框架，但如果按 R 文档编号继续推进，会导致上层 deliverable、secondary market、quant 功能先于主账本和 trace/eval 底座实现，形成孤立脚本。

当前只有用户和一个 Codex agent，因此更合适的执行方式是按 release slice 顺序推进，每个 slice 独立验收、提交、回滚。

## Work Completed

- 新增 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`。
- 回扫 PRD 和 R53-R60 文档后，把下一阶段拆成 S0-S10：
  - S0 Unified Backlog / Gate Matrix
  - S1 Runtime Task Spine
  - S2 Tool / Sandbox / Trace Spine
  - S3 Data / Retrieval / Evidence Spine
  - S4 Context / Graph / Skill Registry
  - S5 Workpaper / Lead Review Workflow
  - S6 Workbench Frontdoor And Drilldown
  - S7 Deliverable Studio And Dashboard Projection
  - S8 Secondary Market / Capital Feedback Pack
  - S9 Research-to-Quant Lab
  - S10 Enterprise Hardening / Release Candidate
- 新增 U0-U10 需求单分组，并明确第一批建议执行 U0/S0 + U1/S1。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`。
- 更新 `docs/worklog/00_internal_master_checklist.md`。

## Result

下一轮最优先不是继续加新功能，而是：

1. `U0-D01-backlog-schema`
2. `U0-D02-r-demand-map`
3. `U0-D03-pass-level-gate-matrix`
4. `U1-D01-runtime-facade-entrypoint`
5. `U1-D02-task-run-state-machine`
6. `U1-D03-sql-final-task-audit`
7. `U1-D04-workpaper-event-ledger`
8. `U1-D06-run-trace-baseline`

这些需求是后续 R55/R58/R59/R60 的共同前置。

## Verification

本次为文档更新，未运行 runtime、后端、前端或 eval case。

提交前需要运行：

- `git diff --check`
- 候选文档 secret scan
- 候选文档 conflict marker / trailing whitespace audit

## Follow-up

- 按 36 文档执行 S0，先物化统一 backlog schema 和 R-demand map。
- S0 完成后进入 S1 runtime task spine，实现任务状态机、SQL final audit、WorkpaperEvent ledger 和 trace baseline。
