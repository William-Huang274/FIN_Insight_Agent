# 020 R53-R60 Scope And Enterprise Gate Clarification

日期：2026-06-29

阶段：R53-R60 product strategy / engineering framework

状态：docs-only clarification

## Prompt

用户确认需要补强 36 文档：R 系列不是从 R53 开始；36 文档需要参照“通过条件上调为企业级验收模型，不再按能跑/有输出算通过”。

## Reasoning

36 文档原本已经把 R53-R60 拆成 S0-S10 release slices，并在需求单里引入 `target_pass_level`。但它没有显式说明历史 R0-R49 / R50-R52 / 当前 R53-R60 的范围关系，也没有把 L0-L4 企业级通过模型完整写入正文。

如果不补这层说明，后续执行时容易出现两个偏差：

- 把 R53-R60 误认为整个 R 系列的起点，忽略 R0-R49 的已实现数据/runtime/图谱基线和未完成缺口；
- 只看 36 文档时，把 `done` 或 smoke 输出误判成 enterprise pass。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md`：
  - 新增 `0. 范围说明与企业级验收模型`；
  - 明确 `R0-R49`、`R50-R52`、`R53-R60` 的关系；
  - 明确早期 R 系列未闭环事项应在 S0 作为 baseline dependency、known gap 或 blocker 引入；
  - 内嵌 Product / Engineering / Quality / Ops 四类 acceptance；
  - 内嵌 `L0_smoke_pass` 到 `L4_production_pass` 五级 pass level。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md` 的 36 文档索引说明。
- 更新 `docs/worklog/00_internal_master_checklist.md` 的 R53-R60 unified backlog 条目。

## Result

36 文档现在可以单独说明：

- R53-R60 是当前工程化主线，不是整个 R 系列起点；
- R0-R49 是历史基线和待回收缺口来源；
- R50-R52 是产品和协作型 agent graph 的前置；
- 后续所有需求单必须按企业级 pass level 和四类 acceptance 验收；
- `done` 不等于通过，`L0` smoke 不得作为下游依赖或上线依据。

## Verification

本次为文档更新，未运行 runtime、后端、前端或 eval case。

需要收尾检查：

- `git diff --check`
- 候选文档 secret scan
- 候选文档 conflict marker audit

## Follow-up

- S0 `U0-D01-backlog-schema` 必须把 `target_pass_level` 和四类 acceptance 变成实际 backlog schema 字段。
- S0 `U0-D02-r-demand-map` 需要回扫 R0-R49 的 baseline dependency / known gap，不能只映射 R53-R60。
- S0 `U0-D03-pass-level-gate-matrix` 需要把 36 中的 pass-level 文本落成 machine-readable gate matrix。
