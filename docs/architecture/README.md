# 架构文档入口

这里放 FinSight-Agent 的公开架构文档。公开架构文档只讲当前系统如何工作、为什么这样设计、当前边界是什么；内部执行计划和实验推进历史不作为架构主入口。

## 推荐阅读顺序

1. [总体架构](fin_sight_agent_architecture.zh-CN.md)
2. [多智能体协作机制](multi_agent_orchestration.zh-CN.md)
3. [上下文与状态管理](context_and_state_management.zh-CN.md)
4. [数据与工具权限模型](data_and_tool_access_model.zh-CN.md)
5. [后端与评测运行时](backend_and_eval_runtime.zh-CN.md)

## 五篇专题说明

### 总体架构

[总体架构](fin_sight_agent_architecture.zh-CN.md) 说明用户问题如何进入研究链路，研究负责人、公司范围、证据执行、专家结论卡、判断提纲、备忘录、校验和呈现如何串起来。

### 多智能体协作机制

[多智能体协作机制](multi_agent_orchestration.zh-CN.md) 说明当前多智能体不是自由互聊，而是通过共享状态、任务卡、工具观察、专家结论卡和缺口请求协作。

### 上下文与状态管理

[上下文与状态管理](context_and_state_management.zh-CN.md) 说明多轮会话中如何保存研究范围、证据引用、运行产物和失效规则，避免旧公司、旧来源或旧假设污染新问题。

### 数据与工具权限模型

[数据与工具权限模型](data_and_tool_access_model.zh-CN.md) 说明不同来源能支持什么结论，各智能体能看什么、能调用什么、不能越过什么边界。

### 后端与评测运行时

[后端与评测运行时](backend_and_eval_runtime.zh-CN.md) 说明本地工作台、任务管理、运行产物、工具台账、模型调用量、耗时和评测报告如何支撑可观测开发。

## 相关公开文档

- [项目主文档](../../README.md)
- [文档地图](../README.md)
- [公开评测摘要](../eval/fin_agent_public_eval_summary.zh-CN.md)
- [投研质量评价体系](../eval/fin_agent_investment_research_quality_framework_v0_1.md)

## 历史执行文档

以下文档保留用于追溯阶段推进和内部设计，不作为公开架构主入口：

- [分层数据源扩容计划](layered_data_source_expansion_plan.zh-CN.md)
- [分层数据源扩容执行文档](layered_data_source_expansion_execution_plan.zh-CN.md)
- [扩容后检索与多智能体架构执行文档](expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md)

这些文档可能保留历史语境、旧路径或阶段性判断。当前公开状态以项目主文档、五篇架构专题和公开评测摘要为准。

## 写作口径

- 面向公开读者优先使用中文专用名词，例如“研究负责人”“证据执行器”“专家结论卡”“判断提纲”“校验器”“工具台账”。
- 保留 SEC、8-K、BM25、BGE、MCP、CLI 等通用技术或金融缩写。
- 代码字段、脚本参数和文件名保持原样。
- 不把工作日志里的运行编号、调试细节和临时云端路径搬进架构主文档。
