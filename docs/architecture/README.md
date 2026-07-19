# 架构文档入口

这个目录用于放 FinSight-Agent 的公开架构文档。这里要讲的是当前系统怎么工作，而不是每一轮实验怎么演进。实验过程、失败记录和具体运行编号放在 `docs/worklog/`。

## Point 01 冻结实施合同（2026-07-12）

- `agent_graph_vnext/SCHEMA_01_point01_canonical_object_registry.zh-CN.md`
- `agent_graph_vnext/DB_01_point01_canonical_store_transaction_boundary.zh-CN.md`
- `agent_graph_vnext/API_01_point01_runtime_command_event_contract.zh-CN.md`
- `agent_graph_vnext/MIGRATION_01_point01_legacy_canonical_cutover.zh-CN.md`
- Freeze manifest：`configs/engineering_handoff/point01_prerequisite_contract_freeze_manifest_v1_0.json`

这些文档冻结 M0-M2 的 schema/store/API/migration prerequisites，不表示 runtime、migration 或 cutover 已执行。

## 后续三篇主文档

### `fin_sight_agent_architecture.zh-CN.md`

讲整体系统架构。读者看完应该知道：

- 用户问题如何进入研究链路。
- 图运行器、工具执行层、上下文管理器分别负责什么。
- SEC / 8-K / 市场快照 / 行业 / 关系数据怎么进入证据上下文。
- 数值台账、覆盖检查、专家结论卡、论证提纲、备忘录和校验结果之间怎么传递。
- 已保存运行产物如何被检查和复用。

### `multi_agent_orchestration.zh-CN.md`

讲多智能体调度。读者看完应该知道：

- 研究负责人如何判断问题类型和研究深度。
- 为什么不是每个问题都启动所有专家。
- 主力智能体、辅助智能体、条件启动智能体和禁止启动智能体怎么区分。
- 精确查询、单公司分析、标准投研备忘录、行业深度研究、市场反应、多轮追问分别走什么激活策略。
- 多轮会话里哪些产物可以复用，哪些因为研究范围变化必须失效重跑。
- 修复循环在哪里发生，什么时候必须停止。

### `data_and_tool_access_model.zh-CN.md`

讲工具和数据权限。读者看完应该知道：

- 每类智能体能看哪些输入，不能看哪些输入。
- 谁能调用 SEC 检索、ObjectBM25、BGE、市场快照、行业和关系查询。
- 专家智能体为什么只能消费限定证据，不能自己检索。
- 备忘录写作器为什么不能读取原始证据，只能读取已验证论证包。
- SEC、8-K、市场、行业、关系数据分别能支持什么结论，不能支持什么结论。
- 运行时工具台账如何帮助检查是否越权、重复调用或浪费预算。

## 当前公开入口

在三篇主文档补齐前，可以先从这些文档理解系统：

- [根目录 README](../../README.md)
- [文档地图](../README.md)
- [分层数据源扩容计划](layered_data_source_expansion_plan.zh-CN.md)
- [分层数据源扩容执行文档](layered_data_source_expansion_execution_plan.zh-CN.md)
- [扩容后检索与多智能体架构执行文档](expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md)
- [Agent Graph vNext 框架与分功能执行文档](agent_graph_vnext/README.zh-CN.md)
- [投研质量评价体系](../eval/fin_agent_investment_research_quality_framework_v0_1.md)
- [分层质量门控执行文档](../eval/fin_agent_layered_quality_execution_plan_v0_1.md)
- [脚本发布面](../../scripts/README.md)
- [仓库架构图与持续审计](repository/README.md)
- [2026-07-11 项目深度审计](repository/REPOSITORY_DEEP_AUDIT_20260711.zh-CN.md)

## 内部规划指针

- [2026-06-10 vNext 规划吸收与公开数据源覆盖审计](../internal/vnext_20260610/README.md)：记录下一阶段 Skill / Playbook / Eval Gate、Agent Graph 和公开数据源覆盖边界。该目录是内部规划，不代表当前公开能力。
- [公开源 S5-S0 物化状态](../internal/vnext_20260610/public_source_strength_materialization.zh-CN.md)：记录 32 个公开源在 no-commercial 约束下的 materialized / parser-pending / blocked 状态，供后续 Agent Graph 和 Skill 边界设计引用。

## 写作口径

- 面向用户的说明优先使用中文专用名词，例如“研究负责人”“证据执行器”“专家结论卡”“论证提纲”“校验器”。
- 保留 SEC、API、BM25、BGE、MCP、RAG、8-K、CLI、Workbench 等通用技术或金融名词。
- 代码字段、脚本参数和文件名保持原样，不翻译。
- 不把工作日志里的运行编号、调用成本和调试细节搬进架构主文档；这些内容只在需要证明当前状态时用摘要引用。
