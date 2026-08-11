# 018 R53-R60 Enterprise Pass-Level Gate Model

日期：2026-06-29

阶段：R53-R60 product strategy / engineering framework

状态：docs-only gate model update

## Prompt

用户指出当前通过条件仍可能偏向“刚过线 / 能用就行”，而项目定位应是企业级生产力项目。需要重新定义需求单通过条件，避免后续把 smoke 或 demo 级结果误当成上线级。

## Decision

R53-R60 后续需求单统一采用四类验收和五级通过状态。

四类验收：

- Product acceptance：是否完成真实用户工作流、减少 analyst 重复劳动、让 senior 能审阅和追责。
- Engineering acceptance：schema / API / DB / artifact / event / runtime contract 是否稳定。
- Quality acceptance：证据、结论、反证、gap、输出质量、弱信号边界是否达标。
- Ops acceptance：token/cost/latency、queue、incident、fallback、sandbox、rollback、release readiness 是否可控。

五级通过状态：

- `L0_smoke_pass`：只证明最小链路能跑。
- `L1_contract_pass`：合同完整，可被下游依赖。
- `L2_internal_dogfood_pass`：内部真实任务可用，能减少重复劳动并保留追责。
- `L3_release_candidate_pass`：可给试点用户，具备 release readiness。
- `L4_production_pass`：企业级正式交付，多用户、长任务、权限、审计、监控、异常恢复和持续评测可用。

`done` 只代表实现结束，不代表生产级通过。

## Work Completed

- 更新 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`，在用户验收标准前新增 `9.0 验收级别`。
- 更新 `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`，把需求单 Acceptance 字段改为 Product / Engineering / Quality / Ops 四类验收，并新增企业级通过条件分层。
- 更新 `docs/architecture/agent_graph_vnext/35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md`，在 Release Gates 中加入 `pass_level` 判定矩阵。
- 更新 `docs/worklog/00_internal_master_checklist.md`，记录 pass-level 标准调整。

## Result

后续需求单不能再只写“脚本能跑”“页面能打开”“case 有输出”。每个需求必须说明目标 `pass_level`，并给出到达该级别所需的产品、工程、质量、运维证据。

## Verification

本次为文档更新，未运行 runtime、后端、前端或 eval case。

收尾检查应覆盖：

- `git diff --check`
- 候选文档 secret scan
- 候选文档 conflict marker / trailing whitespace audit

## Follow-up

- 后续 Slice 0 统一 backlog 时，所有 demand 必须补 `target_pass_level` 和四类 acceptance。
- R60 后续 schema 实现时，`DemandAcceptanceRecord` 和 `ReleaseGateResult` 必须包含 `pass_level`。
- Workbench / Admin Ops 前端后续应能按 pass level 过滤需求、case、release candidate 和 production blockers。
