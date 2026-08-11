# R56 Agent Runtime Stack Hardening 技术计划

日期：2026-06-28

状态：framework-level / living technical registry。本文是 R56 的 active source of truth，用于持续维护 agent runtime、harness、framework reference、ContextEngine、tool gateway、durable execution、observability、enterprise workflow frontdoor 的设计原则和后续落地切片。后续如果 Dify、RAGFlow、LangGraph、ADK、Hermes、MCP、Codex、Claude Code、飞书、钉钉等平台更新关键能力，应在本文的参考台账和采用判断中追加记录。

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/architecture/agent_graph_vnext/30_r55_deliverable_studio_dashboard_projection_technical_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`，归档参考。

## 1. R56 定位

R56 不是选一个通用 agent framework 重写 FinSight。它要解决的是：

```text
把当前 Python / LangGraph research runtime、Java backend / Workbench、tool harness、ContextEngine、MCP tools、SQL run/eval store、ObjectStore artifacts、eval gates 和 human-in-the-loop workflow，收敛成一个可恢复、可审计、可权限控制、可复盘、可被企业产品入口调用的 agent runtime stack。
```

因此更合理的架构不是：

```text
Dify / RAGFlow / LangGraph / ADK 直接覆盖业务 runtime
```

而是：

```text
自研 FinSightRuntimeFacade
 + LangGraph 作为 research graph
 + MCP-style ToolGateway
 + Hermes-style ContextEngine interface
 + Temporal-style durable workflow optional
 + OpenTelemetry / Langfuse / Phoenix-style trace/eval export
 + Java backend / Workbench 承接企业产品层
```

R56 的工程目标：

- 统一入口：Java / Workbench / CLI / future API 都通过同一个 runtime facade 创建、恢复、取消、重放任务。
- 统一权限：每个 actor、node、tool、context、artifact 都有权限和边界。
- 统一状态：LangGraph checkpoint、SQL run/eval store、ObjectStore artifact refs、WorkpaperEvent ledger 能互相追溯。
- 统一上下文：ContextEngine 负责上下文选择、压缩、注入和审计，不让各节点随意拼 prompt。
- 统一工具：MCP-style ToolGateway 管住 DB/RAG/web/parser/render/backtest 等工具，工具返回 typed artifact / row / event，不返回无界文本。
- 统一观测：node execution、model call、tool call、gate result、context digest、artifact refs、human approval 和 cost/latency 都进入 trace/eval 主账本。

R56 不做：

- 不把内部 specialist 协作改成自由 agent chat；
- 不让外部框架绕过 FinSight 的 source authority / evidence gate；
- 不让 Composer / writer 获得检索、DB、web 或 parser 权限；
- 不把 Dify/RAGFlow 这类平台作为核心 runtime；
- 不在 R56 里实现 R57 memory、R58 retrieval、R59 frontend、R60 eval 的全部功能，只冻结接口和协作边界。

## 2. 外部参考台账

此表是 living registry。后续平台更新、替换或弃用时，应更新 `last_reviewed`、`adoption_decision` 和 `notes`。

| Reference | 参考来源 | 可借鉴能力 | R56 采用判断 | last_reviewed |
| --- | --- | --- | --- | --- |
| Codex / Claude Code-style coding agent harness | OpenAI Codex hooks / approvals / sandbox；Claude Agent SDK overview / hooks | workspace-scoped execution、sandbox / approval、hooks、工具前后置拦截、可复盘操作链 | 借鉴为 FinSight runtime harness：工具调用前后 hook、权限审批、workspace/artifact scoped execution、diff/test/eval closeout | 2026-06-28 |
| LangGraph | persistence、checkpointer/store、interrupt、time travel | stateful graph、checkpoint、interrupt/resume、time-travel replay、human-in-the-loop | 继续作为 Python research graph，不替代 Java 产品层；checkpoint 必须与 SQL run/eval store 和 WorkpaperEvent 对齐 | 2026-06-28 |
| Temporal-style durable execution | Temporal durable execution for AI agents | long-running workflow、crash recovery、workflow history、human signal、activity retry | 暂不强行引入 Temporal；先用 SQL checkpoint + queue + ObjectStore + LangGraph checkpoint 实现最小 durable contract。若进入长时间异步多租户或云端分布式 worker，再评估 Temporal | 2026-06-28 |
| Hermes Agent / ContextEngine | Hermes ContextEngine plugin docs、configuration docs | ContextEngine 抽象、config-driven active engine、插件化上下文策略 | 借鉴接口形态：FinSight ContextEngine 统一上下文选择/压缩/注入；具体策略由 R57 定义 | 2026-06-28 |
| MCP | MCP 2025-06-18 specification、tools/resources/prompts | 标准化工具、资源、prompt、client/server 边界 | R56 采用 MCP-style ToolGateway；内部工具也必须有 schema、permission、artifact output、source boundary | 2026-06-28 |
| OpenAI Agents SDK | Agents SDK guide、handoffs、guardrails、tracing | agent definitions、handoffs、guardrails、run result/state、tracing | 借鉴 guardrails / handoff / tracing 设计，不绑定 OpenAI provider；FinSight 自己的 evidence authority 优先级高于 SDK guardrail | 2026-06-28 |
| Microsoft Agent Framework | Microsoft Learn overview、GitHub repo | typed contracts、middleware、session state、telemetry、multi-agent workflow、Python/.NET production agent | 借鉴企业级 typed middleware / telemetry / session state 思路；不迁移到 .NET，不重写研究图 | 2026-06-28 |
| Google ADK | ADK docs / Google Cloud ADK docs | code-first agent、multi-agent orchestration、workflow、eval、deployment、MCP | 借鉴 agent/workflow packaging、本地调试 UI、Java/Python 企业部署模式；不替代 FinSight 垂直 evidence graph | 2026-06-28 |
| Dify | Dify Agent node docs、platform site / repo | workflow UI、agent node、tool registry、LLMOps、dataset/prompt iteration | 借鉴 workflow UI、运营面板和低代码编排体验；不作为核心投研 runtime，因为 FinSight 需要自定义 evidence authority / WorkpaperEvent / graph pack | 2026-06-28 |
| RAGFlow | RAGFlow docs / repo | RAG ingestion、hybrid search、rerank、workflow UI、agent/RAG 结合 | 借鉴 RAG ingestion、hybrid search、可视化 workflow 和企业知识库体验；R58 决定是否吸收组件或只借鉴设计 | 2026-06-28 |
| Feishu / DingTalk AI workflow | 飞书 AI Agent workflow docs、钉钉 AI 助理 / workflow docs | 企业工作流入口、审批、通知、组织空间、知识库、表格/文档协作 | 借鉴产品嵌入方式：任务卡、审批、通知、组织权限、知识库/文档表格集成；不替代 FinSight Workbench | 2026-06-28 |
| OpenTelemetry / Langfuse / Phoenix-style observability | OTel GenAI semantic conventions、Langfuse/Phoenix docs，25 归档参考已记录 | trace spans、model/tool/retrieval spans、latency/cost、eval dataset、human annotation | R56 只定义 export contract；R60 决定具体实现。SQL run/eval store 仍是审计主账本 | 2026-06-28 |

参考链接：

- LangGraph persistence: `https://docs.langchain.com/oss/python/langgraph/persistence`
- LangGraph interrupts: `https://docs.langchain.com/oss/python/langgraph/interrupts`
- LangGraph time travel: `https://docs.langchain.com/oss/python/langgraph/use-time-travel`
- Hermes ContextEngine plugin: `https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-engine-plugin.md`
- Hermes plugins: `https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins`
- MCP specification: `https://modelcontextprotocol.io/specification/2025-06-18`
- MCP tools: `https://modelcontextprotocol.io/specification/2025-06-18/server/tools`
- Temporal durable execution for AI agents: `https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai`
- OpenAI Agents SDK: `https://developers.openai.com/api/docs/guides/agents`
- OpenAI Agents SDK tracing: `https://openai.github.io/openai-agents-python/tracing/`
- OpenAI Agents SDK guardrails: `https://openai.github.io/openai-agents-python/guardrails/`
- OpenAI Codex hooks: `https://developers.openai.com/codex/hooks`
- OpenAI Codex approvals / security: `https://developers.openai.com/codex/agent-approvals-security`
- Claude Agent SDK overview: `https://code.claude.com/docs/en/agent-sdk/overview`
- Claude Agent SDK hooks: `https://code.claude.com/docs/en/agent-sdk/hooks`
- Microsoft Agent Framework overview: `https://learn.microsoft.com/en-us/agent-framework/overview/`
- Microsoft Agent Framework repo: `https://github.com/microsoft/agent-framework`
- Google ADK: `https://adk.dev/`
- Google Cloud ADK: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/adk`
- ADK MCP: `https://adk.dev/mcp/`
- Dify: `https://dify.ai/`
- Dify Agent node: `https://docs.dify.ai/en/use-dify/nodes/agent`
- RAGFlow: `https://ragflow.io/`
- RAGFlow agent introduction: `https://ragflow.io/docs/agent_introduction`
- Feishu AI Agent workflow: `https://www.feishu.cn/hc/en-US/articles/643175485940-use-the-ai-agent-node-in-workflow`
- Feishu AI overview: `https://www.feishu.cn/hc/en-US/articles/257240089464-get-started-with-feishu-ai`
- DingTalk AI assistant overview: `https://open.dingtalk.com/document/aipass/ai-assistant-overview`
- DingTalk AI assistant workflow: `https://open.dingtalk.com/document/aipass/create-an-ai-assistant-workflow-1`

## 3. 设计原则

### 3.1 自研 facade，不被通用框架反客为主

FinSight 的核心差异是金融证据治理、source authority、WorkpaperEvent、Product/Capital/Market graph、human review、quant validation 和 B 端审计链。通用框架可以帮我们组织 graph、tools、context、trace，但不能决定：

- 哪些数据能提权为 exact fact；
- 哪些信号只能做 bounded thesis driver；
- 哪些缺口是 retrievable / public boundary / commercial gap；
- 哪些 actor 能调用哪些工具；
- 哪些输出能进入客户版。

因此 R56 的中心对象必须是 `FinSightRuntimeFacade`，不是某个框架的 `Agent`。

### 3.2 LangGraph 是 research graph，不是全产品 runtime

LangGraph 保留为 Python research graph，负责：

- Research Lead / specialist / verifier / composer 的节点执行；
- checkpoint / interrupt / resume；
- graph state 和 targeted repair loop；
- node-level deterministic tests。

但产品任务、用户权限、组织空间、队列、SSE、artifact browser、review queue、dashboard projection 应由 Java / Workbench / SQL 主账本承接。

### 3.3 Harness 是运行时契约，不是 legacy 脚本

项目里的 harness 后续要升级为 runtime facade 的一部分：

```text
request
 -> actor profile
 -> context injection plan
 -> graph execution
 -> tool gateway
 -> checkpoint / artifact / trace
 -> eval gate
 -> replay / resume / cancel
```

它要解决过去的问题：

- 多个入口各跑一套逻辑，run 难复现；
- full-chain case 烧 token 后无法定位哪个节点失效；
- 工具调用散落在节点里，没有统一权限和 trace；
- second pass / targeted repair 难审计；
- 同一任务在 Workbench / CLI / Java gateway 看到的状态不一致。

### 3.4 ContextEngine 是 R57 的接口前置

R56 只定义 ContextEngine 接口和审计字段，R57 再决定 memory tier、promotion、staleness、compression、retrieval selection。

R56 必须先保证所有节点的上下文都通过：

```text
ContextRequest
 -> ContextPolicy
 -> ContextInjectionPlan
 -> ContextDigest
 -> ContextAuditEvent
```

不能让 Research Lead、specialist、writer 各自拼接无限上下文。

### 3.5 MCP-style ToolGateway 统一工具标准

MCP 的价值不是“让模型随便调更多工具”，而是把工具变成标准化、可授权、可记录、可复盘的接口。

FinSight 工具必须带：

- `tool_name`
- `tool_version`
- `actor_allowed`
- `input_schema`
- `output_schema`
- `artifact_output_policy`
- `source_authority_boundary`
- `credential_scope`
- `timeout_retry_policy`
- `forbidden_claim_policy`

工具输出必须是 typed object / artifact ref / evidence row / gap row / event，不是无界自然语言。

### 3.6 Durable execution 先本地合同，后续再评估 Temporal

Temporal-style 的 durable workflow 对长时间、多 worker、云端、多租户场景很适合，但当前不应先引入重依赖。R56 第一阶段先用：

- Java task SQL state；
- Redis / queue transient state；
- LangGraph checkpoint；
- SQL run/eval store；
- ObjectStore artifact refs；
- WorkpaperEvent append-only ledger。

如果后续出现以下情况，再评估 Temporal：

- 单个任务持续多小时或跨天；
- worker 容易中断但任务不能丢；
- 多租户并发、重试、补偿、human signal 复杂；
- 本地 SQL + checkpoint 难以保证恢复语义；
- replay / workflow history 需求超出当前实现。

### 3.7 Observability export 不能替代本地审计主账本

OpenTelemetry / Langfuse / Phoenix-style trace 可以提升可视化和排障，但 FinSight 的审计主账本仍然是本地 SQL / ObjectStore / WorkpaperEvent：

- 外部 trace 丢了，任务仍可复盘；
- 外部 trace 不应保存敏感原文或凭证；
- source authority、gap、claim、artifact refs 不能被压成不可解释 span；
- R60 决定 eval dashboard / external export 的具体实现。

### 3.8 企业工作流入口借鉴飞书/钉钉，不等于把产品塞进聊天框

Feishu / DingTalk 的价值是工作流嵌入：

- 组织空间；
- 知识库 / 文档 / 表格；
- 审批；
- 通知；
- 自动化触发；
- 任务卡和人机协作。

FinSight Workbench 要借鉴这种嵌入方式：用户不只是“问一句话”，而是在 dashboard、watchlist、data room、workpaper、review queue、deliverable studio 里推进任务。

### 3.9 Codex-like 长程任务执行，不等于一次 fanout

R56 必须把复杂研究任务建模成 long-running task runner。它和 Codex / Claude Code 类 coding agent 的相似点是：

- 先规划；
- 持续拆分子任务；
- 边执行边更新状态；
- 遇到缺口触发 repair；
- 中途可暂停、恢复、取消；
- 每个操作有 trace 和 artifact；
- 完成前做验证；
- 最终给出可交付结果。

不同点在于，coding agent 的核心产物通常是：

```text
code diff + test result + commit / PR
```

FinSight 的核心产物是：

```text
ResearchTask
 -> ResearchObjectiveContract
 -> WorkpaperEvent ledger
 -> EvidencePack / GraphPack / GapLedger
 -> WorkpaperPack
 -> JudgmentState / MemoLogicPlan
 -> DeliverablePlan / FactorHypothesis
 -> EvalTrace / ApprovalDecision
```

因此 R56 的 runtime 不能只支持 `run_graph_once()`。它必须支持：

- `create_run`：创建任务和 objective contract；
- `append_event`：写入 WorkpaperEvent / tool event / review event；
- `get_current_view`：从 append-only events 投影当前底稿、缺口、状态和交付物；
- `pause_for_human`：在证据不足、审批、回测、客户版输出等节点暂停；
- `resume_run`：带 human decision 或 repair output 恢复；
- `repair_subgraph`：只重跑可修缺口相关节点，而不是全链路重跑；
- `replay_run`：根据 run_id 重建关键状态；
- `export_deliverable`：从 approved / review-ready state 生成交付物。

这也是 R56 和旧 fixed fanout 最大区别：

```text
旧结构：
Lead plan -> specialists parallel -> second pass -> writer -> answer

R56 目标结构：
ResearchTask -> event stream -> specialist workstreams -> Lead checkpoints
 -> targeted repair / human question / rework -> judgment state
 -> deliverable / dashboard / quant validation projection
```

Lead 在整个 run 生命周期中多次出现，而不是第一轮派单后消失。

## 4. R56 Runtime Object Model

| Object | 作用 | 稳定字段 |
| --- | --- | --- |
| `FinSightRuntimeFacade` | 统一入口 | `create_run`、`resume_run`、`cancel_run`、`replay_run`、`get_run_state`、`list_artifacts` |
| `RuntimeActorProfile` | 定义 actor 身份和权限 | `actor_id`、`actor_type`、`role`、`tenant_id`、`tool_policy_id`、`context_policy_id` |
| `RuntimeTaskEnvelope` | 任务请求封装 | `task_id`、`case_id`、`user_query`、`workflow_type`、`objective_contract_ref`、`input_artifact_refs` |
| `GraphExecutionState` | 图执行状态 | `graph_run_id`、`checkpoint_ref`、`current_nodes`、`blocked_nodes`、`pending_interrupts`、`status` |
| `NodeExecution` | 节点执行记录 | `node_execution_id`、`node_name`、`actor_profile`、`input_digest`、`output_digest`、`status`、`latency_ms` |
| `ToolPermissionPolicy` | 工具权限策略 | `policy_id`、`allowed_tools`、`forbidden_tools`、`approval_required_tools`、`credential_scope` |
| `ToolInvocationLedger` | 工具调用账本 | `tool_call_id`、`tool_name`、`actor_id`、`input_hash`、`output_ref`、`source_boundary`、`status` |
| `ContextInjectionPlan` | 上下文注入计划 | `plan_id`、`node_name`、`context_sources`、`included_refs`、`excluded_refs`、`token_budget`、`digest` |
| `CheckpointRef` | checkpoint 引用 | `checkpoint_id`、`backend`、`graph_run_id`、`node_name`、`created_at`、`restore_policy` |
| `InterruptRequest` | human-in-the-loop 暂停请求 | `interrupt_id`、`reason`、`required_actor`、`question`、`state_ref`、`deadline` |
| `ResumeRequest` | 恢复请求 | `resume_id`、`interrupt_id`、`approval_decision_ref`、`resume_payload` |
| `RuntimeTraceEvent` | trace 事件 | `event_id`、`run_id`、`event_type`、`actor_id`、`node`、`artifact_refs`、`cost`、`latency` |
| `ModelRoutingDecision` | 模型路由决策 | `decision_id`、`node`、`model_provider`、`model_name`、`reason`、`budget_class` |
| `ResourceQueueState` | 资源队列状态 | `queue_id`、`resource_type`、`resident_model_count`、`wait_ms`、`spillover_reason` |
| `ArtifactRef` | 运行产物引用 | `artifact_id`、`uri`、`mime_type`、`hash`、`producer_node`、`source_refs` |
| `TaskProgressProjection` | 产品层任务进度投影 | `task_id`、`visible_status`、`completed_dimensions`、`active_workstreams`、`open_gaps`、`pending_human_actions`、`latest_events` |

### 4.1 Runtime 状态机

R56 应冻结复杂研究任务的运行状态机，供 R59 前端和 R60 eval 使用：

```text
created
 -> planning
 -> collecting
 -> specialist_workstreams
 -> lead_review_checkpoint
 -> repair_or_rework
 -> judgment_ready
 -> deliverable_drafting
 -> human_review
 -> approved / published
 -> superseded / retired
```

异常和暂停状态：

```text
blocked_waiting_human
blocked_retrievable_gap
blocked_public_boundary
blocked_commercial_gap
failed_recoverable
failed_terminal
cancelled
```

关键规则：

- `repair_or_rework` 只能由 LeadReviewCheckpoint、Verifier 或 HumanReview 触发。
- `deliverable_drafting` 只能消费 `judgment_ready` 或 `review_ready` 状态。
- `approved / published` 必须有 human approval 或预设自动发布策略。
- `failed_recoverable` 必须能显示失败节点、失败工具、失败 context digest 和可重试范围。

## 5. Actor 与工具权限

R56 必须把工具权限从“节点代码里想调就调”改成 runtime policy。

| Actor | 可用工具 | 禁止工具 | 说明 |
| --- | --- | --- | --- |
| Research Lead | inventory / pack lookup、gap audit、targeted repair request、有限 tool call via policy | 直接写正式 memo、无边界 web search、backtest runner | Lead 可以审计缺口和请求修复，但不能绕过 source gate |
| Fundamental Specialist | financial fact packs、statement panel、peer panel、approved source rows | web search、source parser、deliverable renderer | 第一轮默认只消费 bundle；repair 时由 Lead 指派工具 |
| Product Specialist | ProductIntelligencePack、ProductEvidencePack、spec/deployment/proxy packs | raw web、DB arbitrary query、writer renderer | 产品图谱优先，缺口走 Lead repair |
| Market / Capital Specialist | R54 packs、market/liquidity/ownership/credit artifacts | 产品 parser、deliverable renderer | 二级市场信号不能冒充基本面 fact |
| Verifier | claim/gap/gate auditor、numeric/conflict checker | 新检索、新 source fetch、写作器 | Verifier 不补事实，只审查 |
| Deliverable Composer | markdown/docx/pptx/xlsx/pdf/chart/graph render tools | DB/RAG/web/parser/backtest | Composer 只表达和格式化，不补洞 |
| Quant Translator | approved Workpaper / FactorCandidate builder | 真实交易接口、无批准 backtest、raw web | 进入 backtest 前必须 human approval |
| Human Reviewer | approval/comment/downgrade/return-to-lead | 自动事实修改 | human decision 是正式 event |

## 6. R56 和 R52-R60 的关系

| 模块 | R56 需要提供什么 |
| --- | --- |
| R52 collaborative graph | RuntimeFacade、event-driven graph execution、interrupt/resume、actor permission、WorkpaperEvent bridge |
| R53 Research-to-Quant | human approval checkpoint、FactorHypothesis artifact lifecycle、backtest tool permission、trace/cost |
| R54 capital feedback | source pack adapter permission、market-data tool boundary、delayed/realtime/commercial boundary |
| R55 deliverable studio | Composer actor profile、renderer-only tools、artifact versioning、dashboard projection source events |
| R57 memory/context | ContextEngine interface、ContextInjectionPlan audit、memory read/write permission |
| R58 DB/RAG/retrieval | Retrieval tool descriptors、SQL exact tool policy、Milvus/BM25/graph route trace |
| R59 backend/frontend | Java API -> RuntimeFacade contract、SSE status、cancel/resume、artifact browser, review queue |
| R60 eval/observability | trace export contract、node execution ledger、tool call ledger、cost/latency/resource metrics |

## 7. R56 后续需求切片草案

本文先冻结框架层，具体需求单需和 R57-R60 一起排期。初步切片如下：

| Demand ID | 名称 | 目标 | 前置 |
| --- | --- | --- | --- |
| `R56-D01-runtime-facade-contract` | RuntimeFacade 合同 | Java / Workbench / CLI 共用 create/resume/cancel/replay/get-state 接口 | R52 schema |
| `R56-D02-actor-permission-policy` | Actor 工具权限 | 所有节点工具调用必须经过 actor profile + policy | R52 actor model |
| `R56-D03-tool-gateway-mcp-style` | MCP-style ToolGateway | 把 DB/RAG/web/parser/render/backtest 工具统一成 schema + ledger + artifact 输出 | R58 tool inventory |
| `R56-D04-langgraph-checkpoint-bridge` | LangGraph checkpoint bridge | checkpoint ref 写入 SQL run store，可 resume/replay | R52 event ledger |
| `R56-D05-contextengine-interface` | ContextEngine 接口 | 生成 ContextInjectionPlan、ContextDigest、ContextAuditEvent | R57 |
| `R56-D06-human-interrupt-resume` | HIL interrupt/resume | Lead/human approval 可暂停并恢复 graph | R59 review API |
| `R56-D07-resource-and-model-router-ledger` | 资源/模型路由账本 | 记录 BGE/GPU/CPU/model provider queue、cost、latency | R60 metric schema |
| `R56-D08-trace-export-adapter` | Trace export adapter | SQL trace 可导出 OTel/Langfuse/Phoenix-style spans | R60 |
| `R56-D09-runtime-replay-gate` | Replay gate | 从 run_id 重建关键状态、artifact refs、tool calls、context digest | D01-D06 |

## 8. Acceptance Gates

R56 通过标准：

1. 同一个 research task 可以从 Java / Workbench / CLI 任一入口创建，并落到同一 `FinSightRuntimeFacade` contract。
2. 任意 node execution 都能追到 actor、context injection plan、tool calls、model routing、checkpoint、artifact refs、eval/gate rows。
3. Actor permission fail-closed：Composer 不能调用 retrieval/DB/web/parser；Verifier 不能新增事实；Specialist 默认不能越权 fetch。
4. Human interrupt / resume smoke 通过，恢复后 graph state 和 WorkpaperEvent 不分叉。
5. ToolGateway 返回 typed artifact/evidence/gap rows，不允许返回无法审计的自由文本作为正式证据。
6. ContextInjectionPlan 可 replay，且能解释为什么包含/排除了某类 context。
7. Resource/model routing 记录 queue wait、resident model count、CPU spillover、provider latency、token/cost。
8. Trace export 是派生视图；本地 SQL/ObjectStore/WorkpaperEvent 仍可独立复盘。
9. `TaskProgressProjection` 能从同一 run/event ledger 投影出当前计划、active workstreams、completed dimensions、open gaps、pending human actions 和 latest events。
10. `repair_subgraph` 或等价机制能证明只重跑可修缺口相关节点，而不是每次 full-chain 重跑。
11. `git diff --check`、相关 deterministic tests、permission tests、runtime smoke、secret scan 通过后才能进入实现完成态。

## 9. R56 能解决当前项目的哪些问题

| 当前问题 | R56 对应解决 |
| --- | --- |
| full-chain 跑完后难复盘哪个节点出错 | NodeExecution + ToolInvocationLedger + ContextInjectionPlan + RuntimeTraceEvent |
| Research Lead 只像第一轮派单器 | Lead 变成常驻 supervising actor，可在 checkpoint 读取 run/evidence/gap/tool ledger 并触发 targeted repair |
| second pass 像简单二次调用 | interrupt/review/retrievable-gap-driven targeted repair，且每次 repair 有 plan、tool calls、delta audit |
| writer / renderer 可能自行补洞 | Actor permission policy 禁止 Composer 调 retrieval/DB/web/parser |
| 多入口状态不一致 | RuntimeFacade 统一 Java / Workbench / CLI / future API 入口 |
| 上下文注入随 prompt 漂移 | ContextEngine 接口把上下文选择、压缩、注入、排除、token budget 都审计化 |
| 工具调用返回一段文本难提权 | MCP-style ToolGateway 强制 schema output、artifact refs、source boundary、forbidden claim policy |
| 长任务中断后只能重跑 | LangGraph checkpoint + SQL run state + ObjectStore artifact refs + optional Temporal-style escalation |
| CUDA / BGE / model provider 调度不可见 | ResourceQueueState + ModelRoutingDecision 记录 queue wait、spillover、cost、latency |
| eval / observability 和 runtime 脱节 | R60 可直接消费 R56 trace/event/tool/model/context ledger |

## 10. 当前开放问题

1. R56 第一版 RuntimeFacade 先落 Python facade，还是 Java facade + Python worker 双端合同同时落。
2. LangGraph checkpoint 存储是否继续沿用当前机制，还是新增 SQL checkpoint mirror。
3. ToolGateway 是否先包现有 Python tools，还是同步生成 MCP server descriptors。
4. ContextEngine D05 是否只写接口，还是实现一个最小 policy-based selector。
5. trace export 先做 OpenTelemetry schema mapping，还是先做本地 SQL dashboard。
6. Temporal-style durable workflow 是明确 deferred，还是先做 one-run experimental branch。
7. Feishu / DingTalk 入口是否只作为产品参考，还是 R59 后做企业通知/审批 connector。

## 11. 草案结论

R56 的核心是把 FinSight 从“多个能跑的 agent / script / backend 入口”推进到“统一、可审计、可恢复、可权限控制的企业 agent runtime”。

采用策略：

```text
自研 runtime facade 保业务语义
LangGraph 保研究执行图
MCP-style gateway 保工具标准
Hermes-style ContextEngine 保上下文治理
Temporal-style durable workflow 作为可升级路线
OTel/Langfuse/Phoenix-style export 保外部观测兼容
Java backend / Workbench 保企业产品入口
```

R56 做完后，R53/R54/R55 才能进入更细需求拆分：因为 quant、secondary market、deliverable/dashboard 都依赖统一 runtime、上下文、工具权限、artifact refs、trace/eval 和 human approval。
