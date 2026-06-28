# R52 25 Reference Archival Absorption

日期：2026-06-28

## Prompt

用户要求回头审计 `25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md` 草稿，判断还有哪些内容需要吸收；如果没有，或本轮吸收完成，则将 25 文档归档。

## Decision

25 文档不再作为 active source of truth。它保留为外部参考和历史讨论出处；可执行主线迁移到：

- `26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- 10 / 11 / 12 / 13 后端、eval、执行计划文档
- 后续 R54 secondary-market capital-feedback 技术计划

本轮发现仍需吸收的内容主要是：

- `FinSightResearchRuntimeFacade` 的统一 runtime facade contract；
- ContextEngine 的 resolve/select/compress/inject/retrieve/invalidate contract；
- Observability / OpenTelemetry / Langfuse / Phoenix export 边界；
- 二级市场 / 资本反馈层的技术计划承接关系。

Public Evidence 数据工程方法、MCP/A2A 分工、Java/Python 分层、durable execution 已被 R48/R51/R52/RD/R/PIG 主线承接。

## Work Completed

- 更新 `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`：
  - 新增 `ContextEngine Contract`；
  - 新增 `FinSightResearchRuntimeFacade`；
  - 新增 `Observability / Export Boundary`；
  - 新增 `R52.7 Runtime Facade / ContextEngine`；
  - 新增 `R52.8 Observability Export`；
  - 新增二级市场 / 资本反馈层接口和 R54 拆分建议；
  - 新增 `25 文档吸收与归档映射`。
- 更新 `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`：
  - 状态改为已归档参考；
  - 新增归档映射表。
- 更新 `docs/architecture/agent_graph_vnext/README.zh-CN.md`：
  - 标明 25 已归档；
  - 把后续活跃锚点改为 26 / 10 / 11 / 12 / 13。
- 更新 `docs/worklog/00_internal_master_checklist.md`：
  - R47 增加 25 归档吸收说明；
  - 新增 R52.7、R52.8、R54 待办。
- 更新 `docs/worklog/README.md` 索引。

## Result And Evidence

25 文档现在只保留历史参考、外部参考出处和讨论脉络。后续不应再从 25 直接驱动实现；需要实现的事项已经进入 26 或 checklist。

## Verification

- `git diff --check` 已通过。
- 本轮未运行 runtime、agent graph、LLM、parser、DB、frontend 或 full-chain 测试，因为变更范围是文档吸收、索引和 checklist。

## Follow-up

后续实现顺序建议仍以 R52.0-R52.8 为主；R54 在 R52 协作底座与 R53 quant 技术计划之后拆二级市场 / 资本反馈数据源与 pack。
