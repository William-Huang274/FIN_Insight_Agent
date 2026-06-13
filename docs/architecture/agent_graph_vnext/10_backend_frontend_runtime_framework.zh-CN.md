# 后端 / 前端 Runtime 升级框架

更新时间：2026-06-14

本文档作为 FinSight-Agent 下一阶段 Java 后端层 / 前端 / 企业级 Agent Runtime 讨论的起点。它吸收以下两份用户提供文档的可执行结论：

- `D:\finsight_agent_升级方案_20260610\后端\Finsight后端升级可参考路线.docx`
- `D:\finsight_agent_升级方案_20260610\后端\企业级rag、agent项目参考及经验总结——后端开发.docx`

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

和 09 文档连接：

- L6 `InferenceResourceScheduler` 可使用 Redis semaphore / queue。
- L7 `ModelRouter` 可通过 Redis rate limit / provider budget 读当前资源状态。
- Lead targeted repair 可把 repair tasks 入队，而不是直接同步执行。

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
5. Docker Compose 一键启动 API、worker、DB、Redis、Milvus、MinIO 可选。
6. 多 worker + LLM semaphore + BGE scheduler。
7. 失败重试、超时、取消、worker heartbeat。
8. 压测并写报告。
9. 前端补 run list、run detail、event timeline、evidence/claim/gap/report viewer。
10. 再补 Spring Boot API 版本或 Java shell。

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
