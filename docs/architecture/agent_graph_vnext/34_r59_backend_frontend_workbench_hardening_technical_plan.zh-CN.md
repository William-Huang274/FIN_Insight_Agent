# 34. R59 Backend / Frontend Workbench Hardening 技术计划

日期：2026-06-28

状态：framework draft / living technical registry。本文先冻结 R59 的前后端产品化边界、当前实现复盘、外部参考设计、企业级后端/前端目标架构、容灾容错、异常监控、兜底策略和第一批 demand tickets。后续如果 Codex、Claude Code、LangGraph Agent Server、Temporal、Onyx、Glean、Palantir AIP、Hebbia、Dify、RAGFlow、Copilot Studio、Google Agent Platform 等平台更新关键能力，应在本文的参考台账和采用判断中追加记录。

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/architecture/agent_graph_vnext/30_r55_deliverable_studio_dashboard_projection_technical_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/32_r57_graph_skill_memory_pack_operating_model.zh-CN.md`
- `docs/architecture/agent_graph_vnext/33_r58_db_rag_retrieval_data_pipeline_control_plane.zh-CN.md`

## 1. R59 定位

R59 不是“给现有脚本加几个页面”，也不是“把 Java gateway 包成一个壳子”。它要把 FinSight 从当前的研发型 Workbench 推进到 B 端金融研究工作台的产品化前后端：

```text
Frontend Workbench / Enterprise Product Surface
 -> Java / API Gateway / Task Lifecycle / RBAC / Artifact APIs
 -> Python Research Runtime / LangGraph / ToolGateway / ContextEngine
 -> SQL Run Audit / ObjectStore / Retrieval DB / Eval Store
 -> Human Review / Deliverable / Dashboard / Incident / Release Gate
```

R59 的核心判断：

- Python Workbench backend 当前是功能最完整的研发入口，但不应长期作为企业产品 API 的唯一入口。
- Java Research Gateway 当前验证了 task / queue / callback / SSE / cancel / resume 的通路，但仍是轻量 JDK HTTP server，不是生产级企业后端。
- React/Vite frontend 当前能做 profile、source bundle、data build、run、session、eval、artifact 和 job console，但它更像工程调试台，不是 junior analyst 工作流工作台。
- R59 应该把 Java / Workbench / Python runtime 的职责边界定清楚，再把前端从“看 run”升级为“做研究任务、审证据、改底稿、批交付、追溯异常”。

R59 不做：

- 不重写 LangGraph research graph；这归 R56/R52。
- 不重新定义 GraphPack / SkillPack / MemoryPack；这归 R57。
- 不重写 DB/RAG/ingestion 控制面；这归 R58。
- 不定义所有 eval 指标；这归 R60。
- 不把通用 agent 平台整套引入；只吸收适配 FinSight 工作流的前后端设计。

## 2. 当前实现复盘

### 2.1 Java Research Gateway

当前文件：

- `apps/research_gateway/java/src/finsight/gateway/TaskGatewayServer.java`
- `apps/research_gateway/java/src/finsight/gateway/GatewayConfig.java`
- `apps/research_gateway/java/src/finsight/gateway/TaskStore.java`
- `apps/research_gateway/java/src/finsight/gateway/JdbcTaskStore.java`
- `apps/research_gateway/java/src/finsight/gateway/RedisTaskQueue.java`

已实现能力：

- `GET /api/health`
- `POST /api/research/tasks`
- `GET /api/research/tasks/{task_id}`
- `POST /api/research/tasks/{task_id}/worker-events`
- `GET /api/research/tasks/{task_id}/events`
- `POST /api/research/tasks/{task_id}/cancel`
- `POST /api/research/tasks/{task_id}/resume`
- file / JDBC store；
- file / Redis queue；
- worker callback；
- SSE event stream；
- cancel / resume smoke；
- optional worker token。

当前不足：

- 没有正式 auth / tenant / RBAC / org / project；
- 没有 Spring Boot / OpenAPI / migration / typed DTO versioning；
- 没有 production-grade retry、heartbeat、lease、stuck-run recovery、idempotency key；
- JDBC store 可用但未形成最终 SQL audit parity；
- Redis 主要做 queue/pubsub，尚未完整区分 transient state 与 SQL-final audit；
- artifact browser、review queue、deliverable API、dashboard projection API 尚未成型；
- 异常监控和 release gate 仍依赖脚本/工作日志，而不是后端产品对象。

### 2.2 Python Workbench Backend

当前文件：

- `apps/workbench/backend/app.py`
- `src/sec_agent/workbench/store.py`
- `src/sec_agent/workbench/job_runner.py`
- `src/sec_agent/workbench/artifacts.py`
- `src/sec_agent/runtime_bridge/task_worker.py`
- `src/sec_agent/run_audit_store.py`

已实现能力：

- profiles / source bundles；
- data build steps / preview / run；
- runs / run status / run events / SSE；
- sessions / turns；
- evals / eval dashboard；
- trace inspect；
- native checkpoint inspect / resume；
- run inspect / artifact report；
- smoke / ask / eval run；
- local job runner。

当前不足：

- product API、admin/debug API、runtime local runner 混在一个 FastAPI 应用里；
- 当前主要适合本地研发、单机/少用户调试，不适合直接暴露给 B 端组织用户；
- 没有组织空间、用户权限、审批、评论、版本、tenant isolation；
- 上传文件、data room、多格式 deliverable、dashboard projection 还没有正式 API contract；
- WorkpaperEvent / WorkpaperPack / JudgmentState / DeliverablePlan 还未成为一等后端对象；
- 异常状态、失败队列、quality queue、gold/failure lifecycle 需要和 R60 合并。

### 2.3 React/Vite Workbench Frontend

当前文件：

- `apps/workbench/frontend/vite/src/main.tsx`
- `apps/workbench/frontend/vite/src/workbench.css`
- `apps/workbench/frontend/static/app.js`
- `apps/workbench/frontend/static/styles.css`

已实现能力：

- health / system status；
- profile import / save / validate；
- source bundle import / save / validate；
- data build control；
- run list / run inspect；
- session turns；
- eval runner / eval dashboard；
- job console / cancel；
- artifact inspection / native checkpoint display；
- polling and run event display。

当前不足：

- 页面信息架构仍偏工程 console；
- 没有 PRD 定义的 Research Task Center、Evidence Workbench、Workpaper Builder、Graph Workspace、Review Queue、Deliverable Studio、Watchlist Dashboard；
- 缺少真正的任务生命周期视图：planned / collecting / specialist workstreams / lead review / repair / drafting / human review / approved / failed；
- 缺少 evidence -> claim -> gap -> gate -> context -> eval -> rendered deliverable 的单条 drilldown；
- 缺少 reviewer 批注、降权、退回、批准、版本对比；
- 缺少 B 端权限、组织空间、项目空间、客户版/内部版视图切换。

### 2.4 Runtime Bridge / Audit

当前文件：

- `scripts/runtime_bridge/smoke_java_python_bridge.py`
- `scripts/runtime_bridge/smoke_java_python_bridge_docker_backends.py`
- `tests/test_runtime_bridge_java_python_smoke.py`
- `tests/test_run_audit_store.py`

已验证：

- Java gateway -> queue -> Python worker -> callback -> final status；
- file / Redis queue smoke；
- file / JDBC store smoke；
- SSE / resume / cancel smoke；
- run audit store 可记录 run、node execution、artifact、evidence row、claim card、gap、gate result、model call。

未完成：

- real Docker MySQL/Postgres + Redis/MQ 的长链路 parity；
- retry/backoff、lease、heartbeat、stuck-run recovery；
- load/SLA 超过 smoke 的压力测试；
- Workbench frontend 对最新真实 run 的全链路 drilldown 产品级验收；
- ObjectStore / SQL-final / vector-graph / context-memory parity；
- R60 incident / observability / fallback 统一闭环。

## 3. R59 目标架构

R59 第一版建议分三层：

```text
Frontend Product Workbench
  - Dashboard / Task Center / Evidence Workbench / Workpaper Builder
  - Review Queue / Deliverable Studio / Watchlist / Admin

Enterprise Backend Gateway
  - Auth / Tenant / RBAC / Project / Task Lifecycle
  - Queue / SSE / Events / Artifact APIs / Review APIs
  - SQL-final run audit / ObjectStore / Eval projection

Python Research Runtime
  - LangGraph / RuntimeFacade / ToolGateway / ContextEngine
  - Retrieval / Parser / Specialist / Verifier / Composer
  - Worker callbacks / Checkpoints / Trace events
```

R59 的架构分工：

| 层 | 负责 | 不负责 |
| --- | --- | --- |
| Frontend Workbench | 用户工作流、证据审查、底稿编辑、审批、导出、看板 | 不直接查 DB/RAG，不直接补事实 |
| Java / Enterprise Gateway | 用户、权限、任务、事件、artifact、审批、API 合同、产品级状态 | 不执行 LangGraph，不直接解析 raw source |
| Python Workbench Backend | 研发调试、内部 admin、runtime helper，可逐步退到 internal service | 不作为最终 B 端 public API |
| Python Research Runtime | agent graph、检索、parser、ContextEngine、ToolGateway、eval hooks | 不管理 B 端用户/租户/审批 UI |
| SQL / ObjectStore | 最终审计、artifact、trace、run state、version | 不做 transient queue |
| Redis / MQ | queue、lease、pubsub、rate-limit、worker heartbeat | 不保存最终审计事实 |

## 4. 外部参考台账

| Reference | 来源 | 可吸收设计 | R59 采用判断 | last_reviewed |
| --- | --- | --- | --- | --- |
| LangGraph / LangSmith Agent Server | `https://docs.langchain.com/langsmith/agent-server` | graphs + persistence DB + task queue；API server 与 queue worker 分离；SSE/pubsub；run lifecycle；Postgres 主账本、Redis ephemeral | 吸收后端形态：API server 不执行 graph，worker 执行；SQL 是 run 主账本，Redis 只做 queue/pubsub；不全量套用其 API，因为 FinSight 有 Workpaper/Evidence/Authority 专属对象 | 2026-06-28 |
| Temporal HITL durable workflow | `https://learn.temporal.io/tutorials/ai/building-durable-ai-applications/human-in-the-loop/` | durable signals / queries；用户批准、修改、查询当前状态；失败恢复后不丢 human decision | 吸收 human approval / signal / state recovery 语义；第一阶段不强行引入 Temporal，先用 SQL event ledger + queue + checkpoint 实现最小 durable contract | 2026-06-28 |
| Codex hooks / approvals | `https://developers.openai.com/codex/hooks`；`https://developers.openai.com/codex/agent-approvals-security` | lifecycle hooks、pre/post tool gate、approval policy、sandbox/network controls、trust review | 吸收为 Workbench 后端 hook：task start/stop、tool use、artifact publish、deliverable export、human approval 都可插入 policy/eval；不照搬 coding workspace sandbox | 2026-06-28 |
| Claude Code / Agent SDK | `https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously` | status visibility、prompt history、subagents/hooks、checkpoint/rewind、long-running task confidence | 吸收前端任务可见性、checkpoint/rewind、subtask status；不复制代码 agent UI，因为 FinSight 产物是 Workpaper/Deliverable/Graph，不是 diff | 2026-06-28 |
| Microsoft Copilot Studio | `https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-generative-actions`；`https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-overview` | generative orchestration、activity map、analytics、agent/tool/knowledge source selection | 吸收 activity map / component analytics / tool-source descriptions；不把 orchestration 交给通用 generative selector，FinSight 必须由 ResearchObjectiveContract 和 authority gate 控制 | 2026-06-28 |
| Google Gemini Enterprise Agent Platform | `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale` | Agent Runtime、Agent Gateway、IAM identity、bidirectional streaming、sessions、monitoring/logging/tracing、Memory Bank | 吸收企业部署清单：identity、gateway、sessions、streaming、monitoring；不绑定 Google Cloud，先做可迁移接口 | 2026-06-28 |
| Onyx | `https://github.com/onyx-dot-app/onyx` | open-source enterprise AI app：RAG/web/code/file/artifacts/actions/MCP；Docker/K8s；background workers；Redis/MinIO；SSO/RBAC/analytics/query history | 吸收 self-hosted product backend 和 admin pattern：connector sync workers、artifact/action UI、RBAC/analytics；不直接复用其 chat-first IA | 2026-06-28 |
| Glean | `https://www.glean.com/connectors` | permissions-aware connectors、real-time sync、enterprise controls、HITL checkpoints、knowledge graph across enterprise data | 吸收权限继承、source visibility、action approval、enterprise graph / connector dashboard；不照搬其横向办公连接器市场 | 2026-06-28 |
| Palantir AIP | `https://www.palantir.com/docs/foundry/aip/overview` | Ontology-backed apps、access control、encryption、auditing、historical lineage、model management | 吸收 ontology/workflow/audit lineage 思路：前端围绕业务对象而不是聊天；不引入 Foundry/AIP 平台依赖 | 2026-06-28 |
| Hebbia Matrix | `https://www.hebbia.com/blog/introducing-matrix-the-interface-to-agi` | 复杂任务是 process，不是 prompt；透明 decomposition；grid/workpaper interface；collaborative edits；finance/professional workflow | 吸收 Evidence/Workpaper matrix UI 和可视化推理过程；不直接复制 Matrix，因为 FinSight 需要更严格 source authority、graph pack 和 eval gate | 2026-06-28 |
| Dify Knowledge Pipeline | `https://dify.ai/blog/introducing-knowledge-pipeline` | 可视化 data pipeline、source connector、parser/chunk/index observability | 吸收 data build / ingestion 前端节点视图；具体 data contract 归 R58 | 2026-06-28 |
| RAGFlow Knowledge Graph | `https://ragflow.io/docs/construct_knowledge_graph` | dataset-level graph construction、entity resolution、memory/token/cost 警示、graph toggle | 吸收图谱构建和成本可见性 UI；不让 LLM-generated KG 直接覆盖 FinSight authority graph | 2026-06-28 |

### 4.1 ReferenceSourceLedger 合同

R59 以后外部参考不能只写成“看过某平台”。每条参考必须进入可追溯台账，后续新增、删减、替换都要有原因和项目内表现记录。

```text
ReferenceSourceLedger
- reference_id
- platform_or_project
- source_type: official_doc | release_note | engineering_blog | open_source_repo | product_page | case_study
- source_url
- source_owner
- source_date_or_version
- last_reviewed_at
- reviewed_by
- applicable_scope: backend | frontend | workflow | sandbox | observability | eval | data_pipeline | context | deliverable
- adopted_design
- rejected_design
- adoption_reason
- non_adoption_reason
- mapped_finsight_object
- related_demands
- evidence_excerpt_ref
- status: active | watch | deprecated | removed
```

### 4.2 ReferenceChangeLedger 合同

每次外部参考发生变化，必须记录为什么改，而不是直接覆盖旧判断。

```text
ReferenceChangeLedger
- change_id
- reference_id
- change_type: add | update | downgrade | remove | supersede
- changed_at
- changed_by
- external_change_summary
- project_decision
- reason
- affected_docs
- affected_demands
- migration_or_rollback_note
- next_review_at
```

新增参考的通过条件：

1. 能映射到 FinSight 的业务对象、运行时对象或 eval gate。
2. 有官方文档、release note、工程博客、开源仓库或产品文档出处。
3. 说明“不采纳什么”，避免把通用平台不加选择地搬进项目。
4. 至少给一个项目内验收方式，例如 API gate、UI walkthrough、trace parity、load smoke 或 eval case。

删除或降级参考的触发条件：

1. 外部项目能力退化、停更或 license / deploy 约束不适合。
2. 项目内实测没有带来质量、效率、可审计性或用户体验提升。
3. 和 FinSight authority / permission / data boundary 冲突。
4. 被更成熟、可验证、成本更低的方案替代。

### 4.3 ReferenceAdoptionPerformanceProfile

参考来源进入项目后，要定期记录“是否真的有效”：

```text
ReferenceAdoptionPerformanceProfile
- reference_id
- adopted_capability
- finsight_release_slice
- before_problem
- expected_improvement
- measurement_method
- observed_result
- regressions_or_cost
- user_or_reviewer_feedback
- keep_adjust_remove_decision
```

R59 初始表现指标：

| 参考项 | 项目内衡量方式 | 预期改善 | 首轮状态 |
| --- | --- | --- | --- |
| LangGraph Agent Server 分层 | Java/Python task lifecycle、worker queue、SSE/event replay gate | API server 与 worker 解耦，长任务可恢复 | 待 R59-D03/D05/D06 实测 |
| Temporal HITL | ApprovalDecision / HumanQuestion durable event replay | 人工审批不中断、不丢状态 | 待 R59-D11/R56 HIL 实测 |
| Codex / Claude Code hooks + approval + sandbox | ToolPolicy、SandboxPolicy、PermissionRequest、hook trace | 工具调用可控，减少审批疲劳但不放开风险 | 待 R59-D17-D20 实测 |
| Copilot Studio / Google Agent Platform observability | activity map、agent trace、component analytics | 用户和 admin 能看清节点、工具、模型、错误 | 待 R59-D14/R60 实测 |
| Onyx / Glean connector admin | connector/source sync、permission inheritance、query/action history | 企业数据源接入和权限可审计 | 归 R58/R59 联合验证 |
| Palantir AIP ontology/audit | 业务对象视图、lineage、policy-bound workflow | 前端从聊天转为 workpaper/object graph | 待 R59-D09/D10 实测 |
| Hebbia Matrix workpaper/grid | process-first grid/workpaper UI | 复杂研究任务不再像一段聊天答案 | 待 R59-D10/R55 实测 |
| Dify/RAGFlow pipeline/KG visibility | parser/chunk/index/KG build trace | 数据管线出错时能定位到 source/parser/index | 归 R58/R60 联合验证 |

### 4.4 参考来源留痕规则

R59 的参考出处必须按下列方式维护：

- `source_url` 保留外部链接；如果是 release note，还要记录 review date。
- `evidence_excerpt_ref` 只记录短摘要或行号引用，不复制长篇内容。
- 每个参考项必须写入 `mapped_finsight_object`，例如 `TaskRun`、`WorkpaperEvent`、`ToolPolicy`、`ContextInjectionPlan`、`ArtifactRef`、`EvalGateResult`。
- 每个参考项必须说明“不采纳的部分”。例如不直接套用 Onyx chat-first IA，不让 RAGFlow LLM-generated KG 覆盖 authority graph。
- 后续如果新增或删除参考，要在本文追加 `ReferenceChangeLedger`，并在 worklog 记录原因。

### 4.5 Sandbox / Isolation 参考补充

Sandbox 相关参考单独进入安全治理台账：

| Reference | 来源 | 可吸收设计 | R59 采用判断 | last_reviewed |
| --- | --- | --- | --- | --- |
| Codex Sandbox / approvals | `https://developers.openai.com/codex/concepts/sandboxing`；`https://developers.openai.com/codex/agent-approvals-security` | sandbox 定义技术边界，approval policy 决定越界时是否人工批准；本地默认 workspace / network 限制，cloud 隔离容器和 setup/agent 两阶段 | 吸收为 FinSight `SandboxPolicy + ApprovalPolicy`：工具能做什么和何时问人分开；secrets 不进入 agent phase；network 默认 allowlist | 2026-06-29 |
| Claude Code sandboxing | `https://www.anthropic.com/engineering/claude-code-sandboxing` | filesystem isolation + network isolation；目录和域名 allowlist；MCP / subprocess 也受边界；云端隔离会话不持有高权限凭证 | 吸收为 crawler / parser / document render / code execution / MCP tool 的统一隔离模型；高风险工具走 scoped credential proxy | 2026-06-29 |
| Google Agent Gateway / Observability | `https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes` | Agent Gateway 统一治理 users/agents/tools/agents 间连接；observability 默认 tracing，支持 DAG trace 和大 payload 存储 | 吸收为 R59/R60 的 ToolGateway + trace export 方向；先自研接口，不绑定 Google Cloud | 2026-06-29 |

## 5. 为什么不全量套用外部平台

原因不是“外部平台不好”，而是 FinSight 的核心对象更垂直：

```text
ResearchObjectiveContract
WorkpaperEvent
EvidencePack
ProductIntelligenceGraph
CapitalFeedbackPack
ClaimCard / GapLedger / GateResult
JudgmentState / MemoLogicPlan
DeliverablePlan
FactorHypothesis / FactorCard
```

通用平台通常以 chat、agent、workflow、connector、document、tool 为中心。FinSight 必须以金融研究责任链为中心：

- evidence authority 比普通 RAG citation 更严格；
- public / commercial / bounded / exact / forbidden claim 边界必须产品可见；
- LeadReviewCheckpoint 和 human approval 是正式工作流节点；
- writer / composer 不能自己补事实；
- 用户需要底稿、图谱、表格、PPT、Word、Excel、dashboard，而不是单一聊天答案；
- run、context、retrieval、source、artifact、eval、cost 必须能被审计。

因此 R59 采用方式是：

```text
吸收成熟前后端模式
 -> 映射到 FinSight 业务对象
 -> 进入 API / UI / SQL / ObjectStore / Eval contract
 -> 用项目内 gate 验证是否提升
```

## 6. Backend Object Model

| Object | 作用 | 核心字段 |
| --- | --- | --- |
| `Tenant` | 组织隔离 | `tenant_id`、`name`、`plan`、`data_policy_id` |
| `User` | 用户身份 | `user_id`、`tenant_id`、`email`、`display_name`、`status` |
| `RoleAssignment` | 权限 | `user_id`、`project_id`、`role`、`permissions` |
| `ProjectSpace` | 研究项目空间 | `project_id`、`tenant_id`、`name`、`watchlist_refs`、`data_room_refs` |
| `ResearchTask` | 长程任务 | `task_id`、`project_id`、`objective_contract_ref`、`mode`、`status`、`budget` |
| `TaskRun` | 运行实例 | `run_id`、`task_id`、`runtime_run_id`、`status`、`current_stage`、`progress_projection` |
| `TaskEvent` | 事件流 | `event_id`、`run_id`、`event_type`、`actor`、`payload_ref`、`created_at` |
| `WorkpaperPackRef` | 底稿引用 | `workpaper_id`、`run_id`、`version`、`status`、`artifact_ref` |
| `EvidenceItemRef` | 证据引用 | `evidence_id`、`source_ref`、`authority`、`claim_scope`、`lineage_ref` |
| `GapCard` | 缺口 | `gap_id`、`gap_type`、`dimension`、`repair_status`、`boundary_reason` |
| `ReviewComment` | 人工批注 | `comment_id`、`target_ref`、`author_id`、`comment_type`、`resolution` |
| `ApprovalDecision` | 审批 | `approval_id`、`target_ref`、`decision`、`reason`、`actor_id` |
| `DeliverablePlan` | 交付计划 | `deliverable_id`、`format`、`audience`、`source_workpaper_ref`、`status` |
| `ArtifactRef` | 文件/产物 | `artifact_id`、`uri`、`mime_type`、`hash`、`producer`、`permission_scope` |
| `DashboardProjection` | 看板投影 | `projection_id`、`project_id`、`source_refs`、`visible_status`、`updated_at` |
| `IncidentRecord` | 异常 | `incident_id`、`run_id`、`severity`、`root_cause`、`recovery_action` |

## 7. API Surface 草案

### 7.1 Task / Run API

```text
POST   /api/research/tasks
GET    /api/research/tasks
GET    /api/research/tasks/{task_id}
POST   /api/research/tasks/{task_id}/start
POST   /api/research/tasks/{task_id}/cancel
POST   /api/research/tasks/{task_id}/resume
GET    /api/research/tasks/{task_id}/events
GET    /api/research/tasks/{task_id}/events/stream
GET    /api/research/tasks/{task_id}/progress
POST   /api/research/tasks/{task_id}/repair-requests
POST   /api/research/tasks/{task_id}/human-answers
```

### 7.2 Workpaper / Evidence / Review API

```text
GET    /api/workpapers/{workpaper_id}
GET    /api/workpapers/{workpaper_id}/events
GET    /api/workpapers/{workpaper_id}/evidence
GET    /api/workpapers/{workpaper_id}/gaps
POST   /api/workpapers/{workpaper_id}/comments
POST   /api/workpapers/{workpaper_id}/return-to-lead
POST   /api/workpapers/{workpaper_id}/approve
POST   /api/evidence/{evidence_id}/downgrade
POST   /api/gaps/{gap_id}/mark-not-material
POST   /api/gaps/{gap_id}/request-repair
```

### 7.3 Artifact / Deliverable / Dashboard API

```text
GET    /api/artifacts/{artifact_id}
GET    /api/artifacts/{artifact_id}/download
POST   /api/deliverables
GET    /api/deliverables/{deliverable_id}
POST   /api/deliverables/{deliverable_id}/render
GET    /api/dashboard/projects/{project_id}
POST   /api/dashboard/projections/{projection_id}/refresh
```

### 7.4 Admin / Ops API

```text
GET    /api/admin/runs
GET    /api/admin/incidents
GET    /api/admin/evals
GET    /api/admin/queues
GET    /api/admin/workers
GET    /api/admin/costs
POST   /api/admin/runs/{run_id}/retry
POST   /api/admin/runs/{run_id}/quarantine
POST   /api/admin/feature-flags/{flag}/toggle
```

### 7.5 API 原则

- 所有 mutation 必须带 idempotency key。
- 所有 response 必须带 `request_id` / `trace_id`。
- 长程任务不以 HTTP request lifetime 为准，创建后立即返回 `task_id` / `run_id`。
- 前端实时状态来自 SSE / event replay，不靠轮询拼状态。
- 所有 artifact API 返回 `ArtifactRef`，不直接暴露本地绝对路径。
- 所有 evidence / gap / claim / review 变更必须写 append-only event。

## 8. Frontend Workbench 目标信息架构

```text
Home / Dashboard
  - My Tasks
  - Watchlist / Portfolio
  - Alerts / Incidents / Pending Reviews

Research Task Center
  - Create Task
  - Objective Contract
  - Progress Timeline
  - Active Workstreams

Evidence Workbench
  - Evidence Matrix
  - Source / Citation Drilldown
  - ClaimCards
  - GapLedger
  - Gate Results

Workpaper Builder
  - Dimension Sections
  - Financial Statement Panel
  - Product / Customer / Supply Chain Graph
  - Capital / Market / Valuation Panel
  - Counter-thesis / Risk Panel

Review Queue
  - Comments
  - Downgrade / Return / Approve
  - Human Questions
  - Version Diff

Deliverable Studio
  - Markdown / Word / PPT / Excel / PDF
  - Internal vs Client Version
  - Appendix / Citation / Chart

Admin / Ops
  - Runs / Queues / Workers
  - Cost / Latency / Token / GPU
  - Eval / Incident / Failure-Gold Lifecycle
  - Source / Parser / Retrieval Health
```

## 9. 前端交互原则

1. 默认不是聊天页，而是任务工作台。
2. 聊天只作为创建任务、追问和局部编辑入口。
3. 每个复杂任务都必须有 progress projection，而不是只显示 spinner。
4. 每个核心判断都能 drill down 到 source / evidence / gap / gate / trace。
5. 证据、底稿、交付物、审批是不同视图，不混在一段 memo 里。
6. 内部字段不能污染正文；调试字段只出现在 trace/debug panel。
7. 用户可以一键要求 Lead repair，而不是自己猜该重跑哪个节点。
8. 失败状态必须显示可恢复、不可恢复、需要人工、需要商业源还是权限不足。
9. Deliverable Studio 只使用 approved / review-ready WorkpaperPack。
10. Admin 面板必须能显示 queue wait、worker heartbeat、provider latency、token/cost 和 error taxonomy。

## 10. 容灾、容错、异常监控和兜底

### 10.1 后端可靠性

| 场景 | 处理 |
| --- | --- |
| API server 重启 | task/run 主状态在 SQL；SSE 断开后可从 event replay 恢复 |
| worker 崩溃 | lease 超时后 run 进入 `failed_recoverable` 或 retry queue |
| Redis 丢数据 | Redis 只做 transient queue/pubsub；SQL event ledger 可恢复状态 |
| Python runtime 失败 | worker callback 写 node/tool/model failure，前端显示 root cause |
| LLM provider 超时 | retry/backoff + provider fallback policy，但不得隐藏质量降级 |
| ToolGateway 失败 | typed `ToolFailureEvent`，可重试/不可重试分类 |
| parser 失败 | `ParserFailureArtifact` + source gap，不伪装 evidence |
| artifact 写入失败 | run 阻断在 artifact publish gate，不允许 deliverable 发布 |
| human approval 丢失 | approval decision 是 durable event，不能只存在前端状态 |
| partial run | 可显示 partial Workpaper，但必须标 `draft / incomplete / blocked` |

### 10.2 异常类型

```text
IncidentType
- api_error
- queue_backlog
- worker_lost
- runtime_exception
- tool_timeout
- provider_rate_limit
- provider_quality_gate_fail
- retrieval_empty
- parser_failure
- permission_denied
- artifact_write_failure
- eval_regression
- unsupported_claim
- cost_budget_exceeded
- latency_sla_breach
```

### 10.3 兜底原则

- 不允许 fallback 隐藏事实缺口。
- 不允许 writer 用“保守话术”掩盖上游缺证据。
- 允许产品级 degraded mode，但必须显式标记：
  - `partial_workpaper`
  - `source_limited`
  - `parser_failed`
  - `commercial_gap`
  - `permission_blocked`
  - `provider_degraded`
- 允许 retry / alternative route，但必须写入 `RecoveryAttempt`。
- 任何自动恢复都不能改变 evidence authority boundary。

### 10.4 Sandbox / 沙盒隔离策略

R59 必须把 sandbox 纳入产品级安全设计。原因是 FinSight 不是只调用模型回答问题，而是会执行：

- 用户上传文件解析：PDF、DOCX、Excel、PPT、Markdown、图片、后续视频；
- 联网抓取和浏览器渲染：company IR、交易所、监管、官网、渠道、招聘、订单、技术文档；
- Python/JS 计算和渲染：Excel、图表、PPT/Word/PDF、量化回测；
- MCP-style tool 调用：数据库、RAG、对象存储、crawler、parser、external API；
- B 端多租户数据访问：组织私有文件、watchlist、内部经验库和投研底稿。

所以 sandbox 不是“可选安全优化”，而是企业级运行时的必要边界。R59 第一阶段不要求一次上完整 cloud microVM / gVisor，但必须先把策略合同、工具权限、审计行和本地隔离实现打通。

```text
SandboxPolicy
- sandbox_policy_id
- actor_role: lead | specialist | evidence_operator | parser | composer | verifier | quant_worker | admin
- tool_scope
- filesystem_scope: none | read_project | write_artifact_only | write_workspace_scoped
- network_scope: none | source_allowlist | browser_allowlist | unrestricted_admin_only
- credential_scope: none | scoped_runtime_token | setup_only_secret | user_delegated_token
- code_execution_scope: none | deterministic_script | sandboxed_python | sandboxed_browser | quant_backtest
- artifact_write_scope: none | temp_only | object_store_review | approved_deliverable
- approval_required_for
- max_runtime_seconds
- max_memory_mb
- max_output_bytes
- audit_required: true
```

工具分层：

| Tool class | 默认 sandbox | 允许写入 | 网络 | 人工批准 |
| --- | --- | --- | --- | --- |
| DB/RAG read | read-only service account | none | internal only | 权限越界时 |
| crawler / browser fetch | isolated browser profile | snapshot/object store | allowlisted source domains | 新域名、登录态、付费墙、批量抓取 |
| parser / document render | sandboxed local process | temp + artifact refs | none | 宏、外链、异常大文件 |
| Python analysis / chart / Excel | sandboxed Python | temp + reviewed artifact | none by default | 访问外网、读私有目录 |
| Deliverable Composer | render sandbox | approved deliverable artifact | none | 发布/外发 |
| Quant backtest | PIT data sandbox | model artifact + report | market data allowlist | paper trading / auto factor promotion |
| Admin ops | restricted admin shell | audited ops paths | internal only | production destructive action |

禁止事项：

- agent phase 不直接持有长期 API key、SSH key、Git token、数据库 root 密码。
- writer / composer 不能联网补事实，不能绕过 WorkpaperPack / approved refs。
- crawler 不能带用户真实浏览器 cookie 去不明站点；如果需要登录态，必须走 user-delegated scoped token 和审批。
- parser 不执行 Office macro，不执行上传文件内嵌脚本。
- quant worker 不接真实交易 API，不自动下单；paper trading 也必须有 human approval 和独立账户边界。

### 10.5 Sandbox 三阶段落地路线

#### Step 1: Contract first / 先做策略合同

目标：先让“谁能调用什么工具、能读写哪里、能不能联网、能不能拿凭证、什么时候需要人工批准”变成机器可校验合同，而不是散落在 prompt 或代码分支里。

要落的对象：

```text
SandboxPolicy
ApprovalPolicy
ToolInvocationLedger
PermissionRequest
SandboxRunProfile
CredentialLease
ToolPolicyBinding
```

核心规则：

- 所有 tool 必须在 `ToolRegistry` 里绑定 `sandbox_policy_id` 和 `approval_policy_id`。
- 所有 actor 必须有默认权限矩阵：`lead`、`specialist`、`evidence_operator`、`parser`、`composer`、`verifier`、`quant_worker`、`admin`。
- 默认策略是 deny-by-default：没声明的文件写入、网络访问、凭证读取、artifact 发布都不允许。
- `ApprovalPolicy` 和 `SandboxPolicy` 分开：sandbox 定义技术边界，approval 定义越界时是否能申请人工批准。
- `ToolInvocationLedger` 必须记录 `actor_id`、`tool_id`、`sandbox_policy_id`、`approval_decision_id`、`input_digest`、`output_digest`、`artifact_refs`、`blocked_reason`。
- `CredentialLease` 只允许短期、scoped、purpose-bound；禁止把长期 API key、SSH key、数据库 root 密码注入 agent phase。

与既有模块的关系：

| 模块 | 接入方式 |
| --- | --- |
| R56 ToolGateway | 执行工具前读取 `ToolPolicyBinding`，不合规就 fail closed |
| R57 ContextEngine | context injection 不得注入 actor 无权访问的 private memory / org data |
| R58 data pipeline | crawler / parser / ingestion contract 必须声明 sandbox class |
| R59 Java Gateway / Workbench | 暴露 permission request、approval decision、blocked reason、tool ledger |
| R60 eval / observability | 增加 forbidden tool-call、permission drift、policy bypass regression |

通过门控：

1. 100% registered tools 有 `sandbox_policy_id`、`approval_policy_id`、owner 和 risk class。
2. writer / composer / verifier 默认没有 retrieval / browser / DB write 权限。
3. parser / document render 默认无网络。
4. crawler / browser 默认只访问 allowlisted source domains。
5. 任一未注册工具调用必须被阻断并写入 `ToolInvocationLedger`。
6. Workbench 能显示工具被允许、阻断或等待审批的原因。

非目标：

- Step 1 不要求已经有 OS/container 级隔离。
- Step 1 不把所有现有脚本都重写，只先让权限合同覆盖入口和 tool registry。

#### Step 2: Local lightweight isolation / 本地轻量隔离

目标：在当前本地/单机资源下，把高风险工具先关进可控边界，能跑真实 smoke，而不是只停留在合同层。

本地实现范围：

| 工具类别 | 本地隔离做法 | 输出 |
| --- | --- | --- |
| DB/RAG read | read-only connection / read-only wrapper；禁止 SQL write | query digest、row refs、blocked write attempt |
| crawler / browser fetch | Playwright 独立 profile、无用户 cookie、domain allowlist、下载目录隔离 | source snapshot、HTML/PDF artifact、fetch attempt row |
| parser / document render | temp dir、macro disabled、no external link execution、subprocess timeout | ParserArtifact、parsed rows、failure artifact |
| Python analysis / chart / Excel | subprocess wrapper、环境变量 allowlist、默认 no network、temp output dir | chart/xlsx/report artifact refs |
| Deliverable Composer | 只读 approved WorkpaperPack；只写 deliverable artifact staging | RenderJob、ArtifactRef、publish gate |
| Quant backtest | point-in-time data path allowlist；禁止 broker/live-trading endpoint | BacktestRun、FactorCard draft、risk report |

本地安全边界：

- 文件：只能读 workspace / approved data roots / object-store refs；写入只能到 temp 或 artifact staging。
- 网络：默认关闭；crawler/browser 只能访问 source route allowlist；新域名触发 `PermissionRequest`。
- 凭证：本地只允许 scoped runtime token；日志只记录 credential lease id，不记录明文。
- 子进程：必须有 timeout、max output bytes、失败退出码、stderr capture 和 digest。
- 浏览器：使用独立 user-data-dir，不复用用户日常浏览器 cookie / session。
- artifact：发布前必须过 artifact publish gate，不能把本地绝对路径暴露给前端或 memo。

本地 smoke gate：

1. `path_escape_case`：工具尝试读写 workspace/object-store 之外路径时被阻断。
2. `network_escape_case`：无网络工具尝试联网时被阻断。
3. `new_domain_case`：browser/crawler 访问未登记域名时进入 approval，而不是直接访问。
4. `writer_fetch_case`：writer/composer 调 retrieval/browser 时 fail closed。
5. `malicious_upload_case`：含 macro / 外链 / 超大嵌套对象的文件不执行，只生成 parser failure 或 safe parse artifact。
6. `credential_redaction_case`：tool ledger、trace、frontend 均不出现 plaintext credential。
7. `artifact_path_leak_case`：前端只看到 `artifact_ref`，不暴露本地绝对路径。

非目标：

- Step 2 不承诺生产级多租户隔离。
- Step 2 不解决高并发容器调度，只确保本地真实链路的安全默认值可运行、可审计。

#### Step 3: Production / high-risk isolation / B 端生产或高风险工具升级

目标：当进入 B 端部署、多租户、上传私有文件、外部 MCP、批量浏览器抓取、量化 paper trading 或更高风险工具时，把 Step 2 的轻量隔离升级为生产隔离。

生产隔离选项：

| 风险等级 | 推荐隔离 | 适用场景 |
| --- | --- | --- |
| medium | container + read-only mounts + egress allowlist | parser、render、Python analysis、普通 crawler |
| high | gVisor / Kata / microVM + network policy | 上传私有文件、外部 MCP、高风险浏览器、第三方代码执行 |
| tenant-critical | Kubernetes namespace + per-tenant service account + object-store policy | B 端多租户、组织私有知识库、权限继承 |
| trading-sensitive | isolated quant worker + no live broker credential + human approval gate | backtest、paper trading、factor promotion |

生产组件：

- `SandboxOrchestrator`：按 `SandboxRunProfile` 选择 container / gVisor / microVM / namespace。
- `NetworkProxy`：统一做 domain allowlist、egress logging、rate limit、robots / source policy、approval enforcement。
- `CredentialBroker`：发放短期 scoped credential，绑定 purpose、actor、tool、tenant、expiry。
- `ArtifactProxy`：所有输出先进入 object store staging，再由 artifact publish gate 决定是否对用户可见。
- `PolicyAuditStore`：保存 tool execution、approval、network、credential、artifact、incident 的审计记录。
- `TenantBoundaryGate`：防止跨 tenant 读取 context、memory、uploaded file、workpaper 和 artifact。

生产 release gate：

1. 单租户和多租户隔离测试通过：tenant A 的 actor 不能读 tenant B 的 memory、artifact、upload 或 run。
2. credential lease 到期后不可复用，trace 中无明文凭证。
3. outbound network 只能通过 `NetworkProxy`，所有新域名都可审计。
4. worker crash / timeout 后 sandbox 环境清理干净，临时文件不残留到可读路径。
5. object-store artifact publish 需要权限和 gate；未通过 gate 的 artifact 只能 admin/debug 可见。
6. R60 sandbox regression 成为 release gate，而不是一次性 smoke。

非目标：

- Step 3 不要求一开始绑定某个云厂商；接口要可迁移。
- Step 3 不允许为了“方便调试”给 agent 直接开长期凭证或 unrestricted network。

## 11. R59 Demand 草案

## P22 Current Status Reconciliation

状态口径：R59 已由 S1/S2/S10/P12/P15/P16/P18/P19 做过 runtime、product-surface、review/action、ops/eval 合同实现。但前端视觉 E2E、真实 reviewer 多日采用、live migration 和 load/SLA 仍然是 product/ops blockers，不能被 partial 行冲掉。

| Demand ID | 名称 | 当前状态 | 已有证据 | 边界 / 下一步 |
| --- | --- | --- | --- | --- |
| `R59-D01-current-surface-inventory` | 当前前后端盘点 | done | P15 | surface inventory 已固化；后续 UI/API 变动要同步更新。 |
| `R59-D02-api-boundary-contract` | Java / Python API 边界 | partial | P12、P15 | 合同存在；full runtime migration 未完成。 |
| `R59-D03-task-run-state-machine` | 任务状态机 | done | S1、P12 | SQL-final task/run state 已有。 |
| `R59-D04-sql-final-task-audit` | SQL-final task audit | done | S1、P16 | SQL ledger 是最终审计源；Redis 不可作为最终审计源。 |
| `R59-D05-queue-worker-recovery` | Queue/worker recovery | partial | P12、S10 | recovery drill 有；真实 load/chaos SLA 待验收。 |
| `R59-D06-sse-event-replay` | SSE + event replay | partial | P15、P18 | projection 有；浏览器断线重连 E2E 未过。 |
| `R59-D07-auth-tenant-rbac` | Auth / tenant / RBAC | partial | P15、S10 | RBAC 正反例合同有；跨租户产品回归未完成。 |
| `R59-D08-artifact-browser` | Artifact Browser | done | P15 | artifact refs、trace、gate、source refs 已可追溯。 |
| `R59-D09-evidence-workbench-ui` | Evidence Workbench UI | partial | P15、P16 | API/projection 有；React 视觉 E2E 和用户流未验收。 |
| `R59-D10-workpaper-builder-ui` | Workpaper Builder UI | partial | P15、P19 | review/action capture 有；真实多日 human workflow 未完成。 |
| `R59-D11-review-queue-ui` | Review Queue UI | partial | P15、P18、P19 | append-only review actions 有；真实 reviewer adoption pending。 |
| `R59-D12-deliverable-studio-ui` | Deliverable Studio UI | partial | S7、P15 | contracts 有；renderer / UI 质量仍需视觉 QA。 |
| `R59-D13-dashboard-watchlist-projection` | Dashboard projection | partial | S7、P15、P18 | projection rows 有；dashboard 产品验收未完成。 |
| `R59-D14-admin-ops-console` | Admin/Ops console | partial | P15、P16 | ops rows/projection 有；持续 incident monitoring 未证明。 |
| `R59-D15-upload-data-room-input` | Upload/Data Room surface | partial | P14、P15 | contract 有；真实 upload -> parser -> evidence UI E2E 未完成。 |
| `R59-D16-load-and-chaos-gate` | Load/chaos gate | partial | S10、P16 | controlled chaos 有；p95/p99 SLA 和并发压测未完成。 |
| `R59-D17-reference-source-ledger` | Reference source ledger | done | P16 | 参考来源台账已落；新增/删除/降级必须继续留痕。 |
| `R59-D18-reference-change-performance-ledger` | Reference change/performance ledger | done | P16 | 采用后表现 profile 已落；后续参考变更必须复核。 |
| `R59-D19-sandbox-policy-contract` | Sandbox / approval policy contract | done | S2、P16 | sandbox policy 和 regression 已有。 |
| `R59-D20-sandbox-ui-and-regression-gate` | Sandbox UI / eval gate | partial | P15、P16 | regression 有；前端可见 allow/block reason 需 browser E2E。 |

## 12. Acceptance Gates

R59 framework 完成标准：

1. Java / Python / frontend 当前实现盘点清楚，未完成项进入 demand list。
2. Java enterprise gateway 与 Python research runtime 的职责边界明确。
3. 任务生命周期从 create 到 approved / failed / cancelled 可用状态机表达。
4. SSE / event replay / progress projection 形成前端主状态源。
5. WorkpaperPack、EvidencePack、GapLedger、DeliverablePlan、ReviewComment、ApprovalDecision 都有前端视图和后端对象位置。
6. Auth / tenant / RBAC 至少有最小 contract，不能继续假设单用户。
7. ArtifactRef 不暴露本地路径，支持权限、版本、下载/预览和 source refs。
8. Admin/Ops 能看到 queue、worker、incident、cost、latency、eval、failure-gold 状态。
9. 容灾容错不靠隐藏 fallback；所有恢复动作写入 RecoveryAttempt / IncidentRecord。
10. load/SLA、SSE reconnect、worker crash、provider timeout、artifact write failure 都有测试计划。
11. 外部参考来源有 `ReferenceSourceLedger`，新增/删除/降级有 `ReferenceChangeLedger`，进入项目后的表现有 `ReferenceAdoptionPerformanceProfile`。
12. Sandbox / Approval 被作为正式 runtime contract：至少覆盖 DB/RAG read、crawler/browser、parser/render、Python analysis、Composer、Quant worker、Admin ops 七类工具。
13. Workbench 能展示工具调用被允许或阻断的原因；禁止 writer/composer 绕过 approved Workpaper 取新事实。
14. sandbox regression 计划覆盖 network escape、path escape、credential injection、malicious upload、forbidden tool-call 和 artifact publish 越权。

## 13. R59 对现有项目的提升

| 当前问题 | R59 解决方式 |
| --- | --- |
| Java gateway 只是 smoke shell | 升级为 enterprise API boundary：task lifecycle、RBAC、event stream、artifact/review API |
| Python Workbench 过宽 | 收敛为 internal runtime/admin service，产品入口由 Java/API Gateway 承接 |
| 前端像调试台 | 升级为 Evidence Workbench / Workpaper Builder / Review Queue / Deliverable Studio |
| full-chain 失败难让用户理解 | IncidentRecord + ProgressProjection + event replay + root-cause panel |
| human-in-loop 只是口头设计 | ReviewComment / ApprovalDecision / HumanQuestion 变成正式产品对象 |
| writer 输出不可靠 | Deliverable Composer 只能从 WorkpaperPack / JudgmentState / approved refs 生成 |
| 状态无法复盘 | SQL-final TaskEvent / RunAudit / ArtifactRef / Eval rows 统一 drilldown |
| 长任务怕中断 | queue lease / heartbeat / checkpoint / replay / recovery attempt |
| B 端不能上线 | auth / tenant / RBAC / audit / artifact / admin ops / load gate 进入计划 |
| 外部参考越积越乱 | ReferenceSourceLedger / ChangeLedger / PerformanceProfile 让参考来源可审计、可删减、可复盘 |
| agent 工具权限过宽 | SandboxPolicy / ApprovalPolicy / ToolInvocationLedger 把文件、网络、凭证、artifact 写入和人工批准边界结构化 |

## 14. 当前开放问题

1. Java gateway 是继续轻量 JDK server 增强，还是进入 Spring Boot / Quarkus / Micronaut 生产框架。
2. Python Workbench backend 哪些 API 继续保留给 internal admin，哪些迁移到 Java gateway。
3. SQL 主账本优先选择 Postgres、MySQL，还是继续本地 SQLite + 云端 Postgres 双模式。
4. 前端第一版重点是 Evidence Workbench，还是 Workpaper Builder / Review Queue。
5. B 端 auth 第一版接本地账号、OIDC、还是先 mock tenant/RBAC contract。
6. ObjectStore 第一版用本地文件 + manifest，还是直接 MinIO-compatible。
7. 是否在 R59 第一阶段引入 OpenAPI schema generator 和 frontend typed client。
8. load/chaos gate 的本地资源上限如何设置，哪些必须等云端环境。
9. sandbox 第一阶段采用本地 OS/subprocess/Playwright profile 隔离，还是直接引入 container/gVisor/microVM；该选择要以上传文件、crawler、quant backtest 和 B 端多租户风险为依据。

## 15. 草案结论

R59 的方向是：

```text
把当前“能跑链路的研发 Workbench”
升级为
“围绕金融研究工作流的企业级前后端产品壳”
```

它应该吸收成熟平台的工程形态：

- LangGraph Agent Server 的 API server / queue worker / SQL persistence / Redis pubsub 分层；
- Temporal 的 durable human-in-the-loop 信号和恢复语义；
- Codex / Claude Code 的 long-running task、hooks、approval、checkpoint、状态可见；
- Onyx 的 self-hosted enterprise app、workers、artifact/action/RBAC/analytics；
- Glean / Palantir 的权限继承、组织数据、ontology/lineage/audit；
- Hebbia Matrix 的 process-first、workpaper/grid、透明协作界面；
- Dify/RAGFlow 的可视化 pipeline、知识图谱和成本/解析可见性。
- Codex / Claude Code 的 sandbox + approval 双层控制，以及 Google Agent Gateway 的连接治理和 observability 思路。

但最终不能变成通用 agent shell。R59 必须服务 PRD 中的 B 端金融研究工作流：任务、证据、底稿、审批、交付、看板、审计、异常恢复。
