# 后端 / 前端 Runtime 升级框架

更新时间：2026-06-14

本文档作为 FinSight-Agent 下一阶段 Java 后端层 / 前端 / 企业级 Agent Runtime 讨论的起点。它吸收以下两份用户提供文档的可执行结论：

- `D:\finsight_agent_升级方案_20260610\后端\Finsight后端升级可参考路线.docx`
- `D:\finsight_agent_升级方案_20260610\后端\企业级rag、agent项目参考及经验总结——后端开发.docx`

并补充参考以下企业级 RAG / Agent 项目的上下文管理做法：

- RAGFlow Memory：保存 raw conversation / agent run logs，并进一步抽取 semantic / episodic / working memory。
- MaxKB：支持历史聊天记录、按轮次或时间生成长期记忆，并通过 `{memory}` 注入系统提示词或上下文；高级智能体还把 `history_context`、`chat_id`、上传文件和节点变量作为 workflow context。
- Flowise：将 chat message、memory type、session id、source documents、used tools、agent reasoning 等作为可查询 API 对象；memory 节点覆盖 buffer、window、summary、Redis、Zep 等不同上下文策略。
- Hermes Agent：把 ContextEngine 抽象成可插拔接口，默认 ContextCompressor 只是其中一种实现；Context Engine 应拥有压缩 / 选择 / 阈值策略，gateway 或 API 层不应依赖某个 compressor 的私有方法。

参考来源：

- RAGFlow Memory: `https://ragflow.io/docs/use_memory`
- RAGFlow HTTP Memory API: `https://ragflow.io/docs/http_api_reference`
- MaxKB 简易智能体长期记忆: `https://maxkb.cn/docs/v2/user_manual/app/simple_app/`
- MaxKB 高级智能体全局变量: `https://maxkb.cn/docs/v2/user_manual/app/workflow_app/`
- Flowise Memory: `https://docs.flowiseai.com/integrations/langchain/memory`
- Flowise Conversation Summary / Buffer Memory: `https://docs.flowiseai.com/integrations/langchain/memory/conversation-summary-memory`
- Flowise Zep Memory: `https://docs.flowiseai.com/integrations/langchain/memory/zep-memory`
- Hermes Context Engine Plugin: `https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-engine-plugin.md`
- Hermes Context Compression and Caching: `https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/context-compression-and-caching.md`

本轮仅做文本吸收和工程框架整理；未做 DOCX 视觉版式复核，也未改 runtime。

## 核心判断

FinSight-Agent 下一阶段不应理解为“把 Agent 改成 Java”，而应理解为：

```text
把本地可跑的金融研报 Agent
升级成可部署、可并发、可观测、可恢复、可限流、可审计、可前端交互的投研 Agent Runtime。
```

Java / Spring Boot 是企业后端表达和就业场景加分项，但不是核心 agent runtime 的替代品。当前最现实的工程路径是：

```text
Python / LangGraph / parser / evidence gate / worker runtime 继续承担研究执行
FastAPI 或 Spring Boot 承担 API、用户、任务、权限、队列、事件流、结果持久化和前端集成
```

先把后端主链路跑通，再做并发稳定性，最后再决定是否补 Java / Spring Boot API 版本。

## 从企业级 RAG / Agent 项目吸收什么

### RAGFlow

可吸收：

- 文档上传 / 解析 / chunk / index 的 ingestion pipeline。
- 多类型文档处理：PDF、Word、Excel、图片、网页。
- grounded citation、chunk 可视化、多路召回、rerank。
- 自托管和 Docker Compose 组织方式。

不应照搬：

- 不要把 FinSight 做成通用知识库问答。
- 不要用普通 chunk 检索替代 SEC exact-value ledger、产品 KPI fact layer、source-boundary gate 和 ClaimCard。

### MaxKB

可吸收：

- 企业知识库后台结构：workspace、user、application、model provider。
- 文档 -> 知识库 -> 应用发布的产品抽象。
- workflow engine、MCP tool-use、第三方系统集成。
- PostgreSQL / pgvector 类工程组织。

不应照搬：

- MaxKB 偏通用企业知识库 / Agent 平台；FinSight 的核心是垂直金融投研 runtime，不应弱化行业 evidence graph 和 claim/gap/gate。

### Flowise

可吸收：

- 节点式 workflow UI。
- Node 输入、输出、配置、credential 抽象。
- workflow graph 序列化。
- execution trace 和 human-in-the-loop 产品表达。
- 每个节点如何暴露成 API。

不应照搬：

- workflow UI 不是核心壁垒；FinSight 的壁垒仍是 financial research workflow + evidence graph + exact-value verification + gap exposure + specialist adjudication。

## 总体系统图

```text
Frontend / Workbench
 -> API Gateway / Backend Service
 -> Run Manager
 -> DB: research_runs / evidence / claims / gaps / gates / reports / audit
 -> Redis: queue / status / event stream / locks / rate limit / semaphores
 -> Worker Pool
 -> LangGraph Research Runtime
 -> SEC / FRED / public source / Milvus / parser / gates / web / document tools
 -> Report / Artifact Store
 -> Frontend realtime progress + report viewer + evidence drilldown
```

这条链路需要和 09 文档的 Research Lead closed-loop graph 对齐：

```text
ResearchObjectiveContract
 -> async retrieval
 -> role-specific evidence selector
 -> LeadReviewCheckpoint
 -> TargetedRepairPlan
 -> JudgmentState
 -> MemoLogicPlan
 -> Memo Writer / Renderer
 -> Verifier
```

后端负责把这条 agent graph 变成可管理的长任务和可审计的产品流程。

## 阶段 1：后端主链路

目标：把当前本地脚本 / Workbench eval 形态升级为可通过 API 调用的后台任务系统。

最小流程：

```text
用户提交研报任务
 -> API 创建 run_id
 -> 写入 research_runs
 -> 放入 Redis queue
 -> Worker 取任务
 -> 执行 LangGraph
 -> 运行中写 run events / node events / tool events
 -> 最终 report / artifacts 写回 DB 或 object store
 -> 前端通过 SSE / API 查看进度和结果
```

最小接口：

- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/report`
- `POST /api/runs/{run_id}/cancel`

核心模块：

- Run Manager：创建、更新、取消、恢复 research run。
- API service：接收请求、参数校验、权限校验、返回 run_id。
- Redis queue：长任务排队。
- Research Worker：执行 LangGraph / Agent Runtime。
- SSE event stream：前端实时进度。
- DB store：保存 run、tool call、evidence、claim、gap、gate、reflection、report。
- Docker Compose：一键启动 API、worker、DB、Redis、Milvus、MinIO 可选组件。

阶段 1 完成条件：

- 能通过 API 创建研报任务并返回 `run_id`。
- 任务能进入 Redis queue。
- Worker 能取任务并执行当前 LangGraph runtime。
- 运行过程能输出标准化事件。
- 最终报告、核心 artifacts 和错误能持久化。
- 前端能看到任务状态、事件流和报告。
- Docker Compose 能启动最小服务栈。

## 阶段 2：并发、稳定性、恢复、压测

目标：多人同时使用时系统不被 LLM、数据库、Milvus、外部 API 或 worker 资源打爆。

重要判断：

```text
上万在线用户 != 上万个 deep research 同时跑。
真实系统应拆成：
online users -> active users -> concurrent short requests -> limited concurrent deep research runs -> queue
```

必须实现：

- Worker pool：多个 worker 横向处理任务。
- Queue position：排队状态可见。
- LLM semaphore：全局模型调用并发控制。
- User / tenant rate limit：防单用户刷爆。
- Idempotency key：防重复提交。
- Timeout / cancel：长任务可超时和取消。
- Retry / backoff：只重试网络、限流、临时超时；不重试 source boundary / commercial gap / parser schema fail 这类确定性失败。
- Worker heartbeat：worker 崩溃后任务可回收或从 checkpoint 恢复。
- Event standardization：进度事件可审计、可前端稳定展示。
- Cache：CIK、SEC metadata、FRED、产品 alias、rerank、artifact 等分层缓存。
- DB index：常用查询字段建索引。
- Observability：日志、指标、trace、run audit。
- Load testing：区分 exact value、focused memo、deep research 的 p95 latency、queue wait、success rate、error rate、token cost。

标准事件类型建议：

- `RUN_QUEUED`
- `RUN_STARTED`
- `NODE_STARTED`
- `NODE_COMPLETED`
- `TOOL_STARTED`
- `TOOL_COMPLETED`
- `EVIDENCE_FOUND`
- `GAP_DETECTED`
- `GATE_PASSED`
- `GATE_FAILED`
- `REFLECTION_TRIGGERED`
- `REPAIR_STARTED`
- `MEMO_DRAFTED`
- `VERIFICATION_PASSED`
- `RUN_COMPLETED`
- `RUN_FAILED`
- `RUN_CANCELLED`

阶段 2 完成条件：

- 多 worker 并行跑任务。
- 同一用户和全局 deep research 有并发限制。
- LLM 调用有全局 semaphore 和 provider rate limit。
- 支持取消、超时、失败重试和 worker 卡死回收。
- 事件流标准化。
- DB 有基础索引。
- 有一份压测报告，记录 p95 latency、queue wait、error rate、success rate、token / LLM call concurrency。

## 阶段 3：Java / Spring Boot API 层

目标：补企业后端技术栈表达，尤其面向国内大厂 AI 应用后端 / Agent 平台工程场景。

不建议：

- 不要把 LangGraph、parser、evidence gate、Milvus retrieval、financial data pipeline 全部重写成 Java。
- 不要一开始就上 Spring Cloud、Kafka、K8s、服务网格、复杂微服务。
- 不要为了学 Java 放弃 Python agent 主线。

建议：

- 先用 FastAPI 打通完整 runtime。
- 再做一个 Spring Boot API shell 或替代 API service。
- Python worker 继续执行 LangGraph。
- Java 负责 API、用户、权限、任务、Redis、MySQL、SSE、限流、线程池、任务调度。

Spring Boot 最小接口可对齐阶段 1：

- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/resume`
- `GET /api/runs/{run_id}/report`
- `GET /api/runs/{run_id}/evidence`
- `GET /api/runs/{run_id}/gaps`

Java 学习够用标准：

- 能写 REST API。
- 能连 MySQL/PostgreSQL。
- 能做基本表设计、事务和索引。
- 能操作 Redis。
- 能理解线程池和任务队列。
- 能做简单限流。
- 能用 Docker 部署。
- 能解释为什么高并发 Agent 系统需要队列、缓存、限流、异步、checkpoint、worker pool。

## 数据库主表草案

阶段 1 / 2 建议优先落以下表，和已有 D-series governance store 对齐：

- `users`
- `tenants`
- `research_runs`
- `graph_checkpoints`
- `retrieval_tasks`
- `tool_calls`
- `evidence_items`
- `claim_cards`
- `gap_cards`
- `gate_results`
- `reflection_events`
- `repair_tasks`
- `reports`
- `report_artifacts`
- `audit_logs`
- `uploaded_files`
- `parsed_input_artifacts`
- `model_calls`
- `resource_usage`
- `context_snapshots`
- `context_events`
- `context_injection_plans`
- `context_artifact_refs`
- `research_memory_entries`
- `analyst_view_index`
- `memory_consolidation_jobs`
- `prompt_packs`

关键原则：

- MySQL/PostgreSQL 是业务主库和审计主库。
- Redis 是队列、状态、event stream、锁、限流和 semaphore。
- Milvus 继续做 typed semantic recall supplement。
- MinIO / object store 用于原始文件、解析产物、报告文件和大 artifacts。
- D-series SQLite store 可作为本地/测试阶段 governance store；生产后端需要迁移或同步到业务主库。

## Redis Runtime 草案

Redis 用途：

- `research_queue`：任务队列。
- `run:{run_id}:status`：当前状态 cache。
- `run:{run_id}:events`：Redis Stream / SSE buffer。
- `run:{run_id}:cancel_requested`：取消标记。
- `worker:{worker_id}:heartbeat`：worker 心跳。
- `user:{user_id}:rate_limit:*`：限流计数。
- `llm:{provider}:semaphore`：LLM provider 并发控制。
- `bge:cuda:semaphore`：BGE / rerank CUDA 并发控制。
- `rerank:{digest}`：rerank cache。
- `context:{session_id}`：短期会话上下文 cache。
- `context:{run_id}:working_set`：当前 run 的工作上下文索引，只存 digest / refs / 小摘要。
- `context:{run_id}:injection_plan`：节点级上下文注入计划 cache。
- `memory:{tenant_id}:{user_id}:active`：用户级长期记忆注入摘要 cache。
- `context_compression:{run_id}:lock`：避免多个 worker 同时压缩同一 run context。

和 09 文档连接：

- L6 `InferenceResourceScheduler` 可使用 Redis semaphore / queue。
- L7 `ModelRouter` 可通过 Redis rate limit / provider budget 读当前资源状态。
- Lead targeted repair 可把 repair tasks 入队，而不是直接同步执行。

## 上下文管理与 Memory Runtime

10 文档的后端升级必须把“上下文管理”作为 runtime 能力，而不是把它理解为简单聊天记录拼接。企业级 agent 项目的共同经验是：

```text
context window 不是 memory；
memory 不是所有历史；
可注入上下文必须经过选择、压缩、权限、时效、来源边界和审计。
```

FinSight 的上下文管理比通用客服 / 助手更严格，因为研报结论需要可追溯到 evidence rows、ClaimCards、GapLedger、gate results 和 source boundary。任何 memory 都不能绕过 evidence gate。

### 外部项目可吸收点

RAGFlow 的 Memory 思路可吸收为三层：

- raw log：保留用户、模型、工具、agent 工作过程的原始轨迹。
- extracted memory：从原始轨迹提炼 semantic / episodic / working memory。
- re-injection：后续 run 可把被选中的 memory 重新作为上下文输入。

FinSight 不能直接照搬“记住用户说过什么”，而应改造成：

- raw run log：`run_events`、`tool_calls`、`model_calls`、`node_execution`、`artifact_refs`。
- episodic research memory：某次研究如何规划、查到了什么、哪些 gate fail、哪些 repair 成功、最后哪些 thesis 被支持或否定。
- semantic research memory：公司业务结构、产品 taxonomy、指标口径、source capability、稳定 gap、常用 peer set 等可跨 run 复用的结构化知识。
- working memory：当前 run 中 ResearchObjectiveContract、retrieval plan、role evidence bundle、ClaimCards、JudgmentState、MemoLogicPlan。

MaxKB 的 `{memory}` 和 `history_context` 机制可吸收为产品配置能力：

- 支持管理员决定哪些 memory class 可注入系统提示词、用户提示词或节点输入。
- 支持按轮次 / 时间 / run completion 触发 memory consolidation。
- 支持会话变量、用户输入、上传文件和 workflow 节点输出在同一次 run 内流转。
- 但 FinSight 必须把 `{memory}` 变量替换成 typed `ContextPack`，不能把自由文本 memory 直接塞给研究 agent。

Flowise 的可吸收点在产品和 API 层：

- chat message / session id / memory type / source documents / used tools / agent reasoning 应可查询。
- 前端应能查看某次回答到底注入了哪些 context，而不是只看最终答案。
- 不同 memory backend 可并存：DB history、Redis short-term、vector memory、external long-term memory service。

Hermes 的可吸收点在工程边界：

- 设计 `ContextEngine` 接口，不要把上下文压缩硬编码在 gateway、controller 或某个 writer 里。
- context engine 的选择应 config-driven，例如 `structured_evidence_context`、`lossless_dag_context`、`summary_buffer_context`。
- API / gateway 只能调用公开接口，如 `select_context()`、`compress_context()`、`write_memory()`、`invalidate_context()`，不能调用某个 compressor 私有方法。
- context engine 应拥有 threshold / budget / compression policy，模型路由器或 gateway 不能静默覆盖。

### 当前 FinSight 已有上下文能力

已有能力需要被纳入后端 runtime，而不是重做：

- `SecAgentContextManager`：已有 tenant / user / session scoped context snapshot，保留 active scope、artifact state、resume cursor、source policy 等 lossless fields，并对 recent turns / candidate sessions 做预算压缩。
- `shared_specialist_context`：specialist fanout 前会构建 common task coverage、source boundary、relationship context 和 prompt policy；每个 specialist 只拿自己的 role data view。
- `artifact_refs` / `langgraph_node_checkpoints`：当前 graph 已经把中间 artifacts、checkpoint summary、resume 状态暴露出来。
- D-series `read_d_series_research_context`：已经能读取 entity、source provenance、vintage、reconciliation、ontology、source policy、derived metrics、analyst memory 的跨 run context。
- D11 `analyst_view_research_memory`：已有 company profile、segment model、product KPI、earnings change、risk factor、bull-bear、thesis tracker 等 analyst view；但 view 只是索引，不是事实来源，必须 drill down 到 claim / gap / derived refs。
- 09 文档的 Research Lead closed loop：LeadReviewCheckpoint 会读取目标合同、retrieval audit、ClaimCards、GapLedger、JudgmentState 等结构化上下文来决定 targeted repair。

### FinSight Context Taxonomy

后端应把上下文分成可审计的 typed context，而不是一条 prompt string：

- `UserSessionContext`：tenant、user、session、active run、recent turns、用户偏好、用户上传文件、权限边界。
- `RunWorkingContext`：当前 run 的 query、source policy、mode、ResearchObjectiveContract、retrieval plan、node state、event cursor。
- `AgentSharedContext`：所有 specialist 共享的任务目标、source boundary、coverage summary、relationship summary 和 forbidden claims。
- `RolePrivateContext`：每个 specialist 的 role-specific evidence bundle、task card、claim slots、input budget。
- `EvidenceContext`：D1-D10 的 evidence rows、resolved facts、derived metrics、reconciliation、source provenance、vintage；这是 claim 的唯一事实底座。
- `AnalystViewMemory`：D11 的 analyst views / research memory entries；只用于召回和导航，不能直接支撑结论。
- `EpisodicRunMemory`：历史 run 的目标、工具调用、repair、gate、最终 judgment 和用户反馈，用于 Research Lead 规划与避免重复错误。
- `SemanticDomainMemory`：公司、产品、segment、metric ontology、source capability、常见 gap、行业 playbook、peer set。
- `ArtifactContext`：上传文档、解析结果、chunk、页码、表格、图片 OCR、视频 transcript、报告文件。
- `ResourceContext`：LLM provider 状态、BGE CUDA queue、token budget、rate limit、模型路由和成本预算。

### Context Engine 合同

后端应新增一个 context runtime facade，可先在 Python worker 内实现，后续再由 FastAPI / Spring Boot API 调用：

```text
ContextResolver
 -> ContextSelector
 -> ContextCompressor
 -> ContextInjectionPlanner
 -> ContextWriter
 -> MemoryConsolidator
 -> ContextInvalidator
```

最小接口：

- `resolve_user_session(tenant_id, user_id, session_id, run_id)`
- `select_context(run_id, node_id, agent_id, objective_contract, allowed_context_classes)`
- `build_injection_plan(run_id, node_id, model_profile, token_budget)`
- `compress_context(context_pack, strategy, target_tokens)`
- `write_context_event(run_id, node_id, context_pack_digest, decision)`
- `write_memory_candidate(run_id, memory_type, refs, status)`
- `consolidate_run_memory(run_id)`
- `invalidate_context(refs, reason)`
- `retrieve_memory(query, namespace, memory_types, as_of, limit)`

所有接口必须返回：

- `context_pack_id`
- `context_pack_digest`
- `source_refs`
- `allowed_claim_scope`
- `injection_budget`
- `dropped_items`
- `compression_strategy`
- `staleness_status`
- `permission_scope`

### 注入规则

每个节点都不应该看到全量上下文。默认规则：

- Research Lead 第一轮：
  - 可见 user query、用户授权上传文件摘要、source policy、历史 analyst view memory 索引、source capability、行业 playbook、可用数据矩阵。
  - 不直接注入大段 raw evidence，除非需要复盘 saved run。
- Evidence Operators：
  - 只拿 retrieval plan、source route、query terms、entity mapping、source policy。
  - 不拿用户长期偏好，不拿 MemoLogicPlan。
- Specialist Agents：
  - 只拿 `AgentSharedContext` + `RolePrivateContext` + role evidence bundle。
  - 产品 agent 拿 ProductSpecPack / product evidence；fundamental agent 拿 FundamentalStatementPack；capital agent 拿 CapitalMacroExposurePack。
- LeadReviewCheckpoint：
  - 可读 tool_call_ledger、retrieval budget audit、bounded evidence rows、ClaimCards、GapLedger、JudgmentState、AnalystViewMemory。
  - 可以 drill down 到 artifact / DB，但必须记录 context read event。
- Memo Writer：
  - 只拿 MemoLogicPlan、JudgmentState、verified ClaimCards、BoundedGapRegister、格式要求。
  - 不允许自行检索、不允许写入事实 memory。
- Verifier / Editor：
  - 可读最终 memo、ClaimCards、source refs、gate results、context injection plan。
  - 如果发现 unsupported thesis，回 Lead Review，而不是自己补事实。

### 存储边界

生产后端建议这样分配：

- SQL 主库：
  - `context_snapshots`：每次 node 前实际注入的 typed context 摘要。
  - `context_events`：select / compress / inject / drop / invalidate / write / retrieve 的事件。
  - `context_injection_plans`：每个 node 的 context pack、预算、dropped items、压缩策略。
  - `research_memory_entries` / `analyst_view_index`：D11 memory 的数据库化版本。
  - `memory_consolidation_jobs`：按 run completion / 时间 / 轮次触发的 consolidation 任务。
  - `prompt_packs`：实际发给模型的 prompt digest、context refs、token count、model id。
- Redis：
  - 当前 run working set、event stream、短期会话 cache、context compression lock、LLM / BGE semaphore。
  - 只做高速状态和调度，不作为最终审计源。
- Object store：
  - 原始上传文件、解析产物、大 prompt payload、长 trace、报告文件。
  - SQL 只存 URI、checksum、parser version、permission scope。
- Milvus / vector store：
  - 只做 semantic recall supplement。
  - 向量命中必须返回 SQL/object-store refs，再 drill down 到 D-series rows；不得直接把 vector snippet 当事实。

### Memory 写入和提权规则

FinSight 的 memory 必须有状态机：

```text
candidate -> reviewed -> active -> stale -> superseded / revoked
```

写入规则：

- 从用户聊天中抽到的偏好，只能进入 `UserSessionContext`，不能影响事实结论。
- 从 analyst view 生成的 memory，初始只能是 `run_scoped_candidate`。
- 跨 run 复用前必须有 drilldown parity：memory entry -> analyst view -> claim/gap/derived refs -> evidence/provenance/vintage。
- 如果新 filing、amendment、restatement、parser version 或 source policy 改变，相关 memory 必须标记 stale 或 superseded。
- bounded gap / commercial gap 可以形成长期 gap memory，但不能被当成 resolved fact。
- 用户反馈可以写入 episodic memory，但不能直接覆盖 source-of-truth rows。

### 通过条件

上下文管理进入后端主线前，至少需要这些 gates：

- Context isolation gate：不同 tenant / user / session 的 context 不串。
- Context injection audit gate：每个 model call 都能追溯注入了哪些 context pack、为什么注入、哪些被丢弃。
- Token budget gate：每个节点的 context pack 有 token 预算、压缩策略和超限处理。
- Memory drilldown gate：任何长期 memory 被用于研究规划时，都能反查到 source refs 或明确标记为 user preference / episodic hint / index only。
- Evidence boundary gate：memory / analyst view / vector snippet 不能直接支持 financial claim。
- Staleness gate：as-of、vintage、filing amendment、parser version 改变后，旧 memory 不得静默注入为 active。
- Replay gate：给定 `run_id` 和 data snapshot，能重建当时 Research Lead、specialist、Memo Writer 各自看到的 context digest。
- Frontend visibility gate：前端能展示某个结论背后的 injected context、claim/gap/gate 和 memory 状态。

## 前端 / Workbench 升级方向

前端不是只展示最终答案，而是要把研究过程产品化：

- Run list：历史任务、状态、模式、创建时间、耗时、成本。
- Run detail：query、tickers、mode、source policy、当前节点、进度。
- Event timeline：节点、工具、gap、gate、repair、memo、verifier。
- Evidence viewer：evidence rows、source、citation、provenance、as-of。
- ClaimCard viewer：按维度展示 claim、evidence、status、materiality。
- Gap viewer：bounded / commercial / retrievable gap。
- Report viewer：Markdown / HTML / PDF / DOCX / Excel / PPT 下载。
- Graph trace：Agent Graph / node trace / repair loop / source-family flow。
- Context trace：展示每个节点实际注入的 context pack、memory refs、dropped items、compression strategy、token budget。
- Upload center：PDF/DOCX/Excel/图片/视频输入，显示解析状态和引用定位。
- Admin / config：model provider、source policy、rate limit、worker status、queue status。

前端应借鉴 Flowise 的 execution trace 和 graph 可视化，但不要做成通用低代码平台。FinSight 的前端重点是：

```text
让用户看懂研究任务如何产生结论、哪些证据支持、哪些缺口存在、哪些数据源被禁止提权。
```

## Harness 与后端的关系

当前 `SecAgentToolHarness` 仍有价值，但它是早期 session-aware controller facade，不是新后端的完整 runtime。

后续有两种路线：

1. 保留并升级 harness：
   - 将它作为 Python worker 内部的 Tool Orchestration Facade。
   - 扩展到 L1-L9：ResearchObjectiveContract、LeadReviewCheckpoint、input parsing、report export、artifact inspect。
   - 后端 API 调用 harness 或其拆分后的 service。

2. 新建 backend-native orchestration facade：
   - Java / FastAPI API 只调用稳定 worker RPC / queue payload。
   - harness 保留为兼容 CLI / eval_context / session replay 工具。
   - 新 facade 直接围绕 run store、tool registry、document parser 和 graph runtime 设计。

当前建议：

- 短期不要删 harness。
- 后端 P0 可以继续复用 harness 的 `start_memo_analysis` / `inspect_coverage` / `explain_evidence` / `resume_analysis` 思路。
- 中期需要把 harness 的旧 SEC-only 抽象升级为 FinSight Research Runtime facade，否则它会继续落后于 G/D/K/L 系列 graph。

## 最现实执行顺序

1. FastAPI + Redis + DB 跑通 run lifecycle。
2. Worker 执行当前 LangGraph / Workbench runtime。
3. SSE 输出标准事件流。
4. DB 保存 evidence / claim / gap / gate / report。
5. 补 Context Runtime v0：context snapshots、context events、injection plans、prompt packs、research memory entries。
6. Docker Compose 一键启动 API、worker、DB、Redis、Milvus、MinIO 可选。
7. 多 worker + LLM semaphore + BGE scheduler。
8. 失败重试、超时、取消、worker heartbeat。
9. 压测并写报告。
10. 前端补 run list、run detail、event timeline、context/evidence/claim/gap/report viewer。
11. 再补 Spring Boot API 版本或 Java shell。

## 对外表达

项目不应只表达为：

```text
一个 multi-agent 金融研报系统
```

更准确的表达是：

```text
一个可审计的金融投研 Agent Runtime。
系统把一次研报任务抽象为 research run，通过 API 创建任务，Redis 队列异步调度 worker，LangGraph 执行多 agent 工作流，运行过程通过 SSE 返回进度，并把 evidence、claim、gap、gate、reflection、repair 和 final report 持久化到数据库。为了支持并发，系统加入 worker pool、LLM semaphore、任务限流、失败重试、超时取消、checkpoint 恢复和压测记录。
```

这比“用了 LangGraph / RAG / multi-agent”更接近企业级后端能力。
