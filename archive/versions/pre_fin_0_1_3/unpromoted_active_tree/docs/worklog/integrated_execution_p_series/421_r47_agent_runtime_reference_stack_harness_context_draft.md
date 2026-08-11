# 421 R47 Agent Runtime Reference Stack / Harness / Context Draft

日期：2026-06-27

## Prompt

用户要求把刚刚讨论、吸收的图方向、框架、harness、Hermes、ContextEngine、MCP/A2A、durable execution、observability/eval、Java 后端技术栈先记录下来，并记录参考出处，作为继续讨论的草案。

## Reasoning And Decision

当前项目已经完成 Research Lead supervised graph、RD0-RD7 数据底座、ProductIntelligenceGraph、DimensionEvidencePortfolio、Java gateway / Python worker / run-eval store 等基础件。下一步讨论不能只停留在 agent graph 形状，需要把企业级 agent runtime 的边界写清楚：

- graph 是投研业务工作流，不是泛化 autonomous swarm。
- harness 应升级成 runtime facade，而不是废弃的旧多轮工具。
- ContextEngine 应成为上下文选择、压缩、注入、memory governance 的统一入口。
- MCP 适合作为工具 / 数据源标准接口；A2A 适合未来对外 agent interoperability，不适合当前内部 specialist graph。
- durable execution 需要 SQL run/eval store、LangGraph checkpoint、ObjectStore artifact refs 和 Redis/MQ 共同承担。
- observability/eval 以本地 SQL 审计主账本为准，外部 Langfuse/Phoenix/OpenTelemetry 只做 export/debug 辅助。
- Java 后端应承接 API、task、queue、SSE、auth、trace、eval dashboard，不重写 Python research runtime。

## Work Completed

- 新增架构草案：
  - `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`
- 更新索引：
  - `docs/architecture/agent_graph_vnext/README.zh-CN.md`
  - `docs/worklog/README.md`
  - `docs/worklog/00_internal_master_checklist.md`

## Reference Sources Recorded

草案记录了以下参考方向和出处：

- LangGraph persistence / interrupt / memory / graph runtime。
- Microsoft Agent Framework。
- Google ADK。
- Spring AI effective agents 与 MCP。
- Hermes ContextEngine plugin。
- Code as Agent Harness / Agentic Harness Engineering。
- MCP official docs/spec。
- A2A protocol。
- OpenAI Agents / tools / tracing / eval docs track。
- Langfuse、Phoenix、Ragas、OpenTelemetry GenAI。
- 本地 `SecAgentToolHarness`、`ContextEngine`、`mcp_tool_registry`、Java runtime bridge。

## Verification

- 本轮为 docs-only，没有改 runtime。
- 未跑模型、pipeline 或 full-chain。
- 已运行 markdown diff check。

## Follow-up

下一步可基于 25 草案讨论：

1. `SecAgentToolHarness` 是原地升级还是新增 `FinSightResearchRuntimeFacade`。
2. ContextEngine 插件化和 SQL/object-store 持久化的优先级。
3. Spring Boot 后端升级顺序。
4. MCP 工具权限 profile。
5. OTel/Langfuse/Phoenix export 是否进入近期计划。
6. A2A 是否只保留 future note，还是先写 Agent Card schema draft。
