# FIN 0.1.3 Dell Agentic Multi-Agent 完整纵切技术详设

文档状态：`DESIGN_FROZEN_REVISION_1_1 / OWNER_ADOPT_LANGSMITH_AGENT_SERVER / NO_RUNTIME_FALLBACK / FRESH_R7_ZERO_MODEL_LOCAL_CONTROL_PLANE_PARITY_PASS_BOUNDED_REMAINS_CURRENT / R8_LIVE_FIN_IDENTITY_ZERO_MODEL_GRAPH_IMPLEMENTATION_CANDIDATE / FRESH_R8_LIVE_QUALIFICATION_NOT_STARTED / A03_PAID_RUN_NOT_AUTHORIZED`

冻结日期：2026-09-03

适用分支：`codex/fin013-dell-s1-s2-product-bridge`

设计基线 commit：`355059686609067e304c27f6568860f16af855ae`

产品版本：`FIN 0.1.3`（本设计不创建新的产品版本、S-stage、R15 或 R16）

## 0. 结论先行

本设计把 Dell 单案例纵切从“固定 Planner 一次生成九个任务、宿主预取全部资料、九个一次性 Specialist、一次 Counter、一次 Lead”改成以下目标：

1. 一个稳定、可恢复、可人工干预的 LangGraph 外层运行时；
2. Research Lead 和专业 Agent 在授权范围内自主规划、按需调用工具、按需加载 Skill，并能根据新证据、错误和反证修订计划；
3. 动态 DAG 是受校验的 `ResearchPlan/PlanDelta` 数据，不是模型动态生成 Python 代码或任意修改执行引擎；
4. S1、S2、Reviewed Evidence、外源 Candidate 和计算器通过现有 MCP 数据面暴露，但模型只填写语义意图，case、as-of、权限、snapshot 和物理 selector 由 Runtime 可信注入；
5. 每轮只披露当前需要的 capability、data inventory、Skill 和 artifact；模型可申请下一层，Runtime 记录并验证 `DisclosureReceipt`；
6. 专业 Agent 的正文恢复为自由 Markdown，证据、数字、计算、推断和边界另存为 `ClaimLedger`；Harness 不再尝试用一个统一语言模板判定整篇自然语言是否合法；
7. 确定性 Validator 检查身份、期间、单位、权限、lineage、公式和引用存在性；Semantic Verifier 检查证据是否真正支撑命题、是否因果过度、是否遗漏反证；发现问题后路由回最早责任 Agent 修复；
8. 前端展示可审计的计划、动作、工具回执、证据、决策摘要、错误责任和修复链；provider 隐藏 chain-of-thought 不持久化、不向产品/审查面或其他接收方传输、不展示，仅允许在同一 provider ActionAttempt 内为协议连续性瞬时回传原 provider；
9. Dell 演示运行底座采用 LangSmith/LangGraph Agent Server；其部署态使用 PostgreSQL 和 Redis，FIN 领域事件仍写独立 PostgreSQL schema，Redis 只承担 Agent Server 所需的瞬时队列、通知与流式协调，不成为 Evidence、Fact、Claim 或 FIN SessionEvent 的真值；
10. A02 仍是不可变 `start_failed`。本设计和其零模型实现不创建、恢复或授权 A03；只有 RC-S3-105、运行时零模型门、独立审查和 Owner 新授权均通过后，才讨论新的付费 ResearchRun 及其首个 RunInvocation。

这是一套 Dell 单案例的“最终产品形态纵切”，不是全产品通用平台重写。凡是不直接帮助 Dell case 跑通、解释、干预、恢复或验收的通用能力，本轮均不扩建。

## 1. 当前事实与为何必须换路线

### 1.1 A02 的真实终态

当前唯一真实 A02 只执行了一个 Planner 模型调用：DeepSeek HTTP 200，输入/输出/总 tokens 为 `21,489 / 2,874 / 24,363`，之后在宿主 `EvidenceRequest` 校验失败。S1、S2、MCP、九个 Specialist、Counter、Lead、HITL 和报告均未运行。

A02 还证明了更深的问题：16 个本地请求把抽象 source-family、角色名和 ticker 当成真实 corpus selector；按当前 1,025-node inventory 复算，`16/16` 均为零命中。仅放松三个 validator 会把失败推迟成“检索为空”，并再次产出满篇边界说明。

活动 blocker 仍为：

`RC-S3-105-dell-A02-planner-capability-inventory-and-conditional-contract-mismatch`

### 1.2 已有地基不是废弃物

本设计复用而不重做以下资产：

| 已有资产 | 当前可证明的事实 | 在新纵切中的位置 |
|---|---|---|
| Structured S1 corpus | 1,025 个结构节点，metadata-prefilter BM25 已通过真实 FastMCP smoke | 本地 Candidate 检索与 answer-free inventory |
| Reviewed Evidence | 61 条当前证据对象 | 可直接支持 `ReportedFactClaim` 的权威来源 |
| S2 mart | 1,319 observations，typed exact-period 查询已有局部真实 smoke | `NumericFactClaim` 和确定性公式输入 |
| Frozen external pack | r12 共 12 条 exact-URL Candidate 路线 | 外源检索的已知官方起点，仍非 Evidence |
| Research calculation | 已允许对非 S2、但可定位输入做确定性计算，并明确 `numeric_fact_authority=false` | `CalculationReceipt`，带非权威提示 |
| MCP 2.1.1 | Knowledge、Evidence、Finance、external discovery/capture 均有 typed tool | 唯一数据/工具 wire protocol |
| LangGraph 1.2.11 | `StateGraph`、并行、`interrupt`、SQLite/Postgres saver 已接入 | 唯一 Agent orchestration/checkpoint 引擎 |
| Canonical runtime v1.0/v1.1 | AgentSession、FeedbackReceipt、PlanDelta、GraphDelta、ContextCheckpoint、StopDecision 与 digest-chain event | 新运行时的领域连续性基础 |
| FastAPI + React Workbench | 现有只读 Workspace、Operations、SQLite run log 与 SSE 雏形 | 新 Research Run API、live viewer 和 HITL 的承载面 |

### 1.3 本设计纠正的五个方向

1. MCP 只负责工具/资源协议；Runtime 负责权限、会话、上下文、调度和可信注入。
2. Harness 只做确定性完整性与安全校验；Semantic Verifier 独立做语义审查。
3. Agent 可在边界内自主规划，不再由宿主提前写死所有检索和推理步骤。
4. Verifier 和前端读取审计安全的推理制品，不读取隐藏 CoT。
5. Agent 可以怀疑工具或数据有问题、申请替代路径或补源，但不能自行修改权威层级，也不能把工具失败或空结果宣布成公开信息缺口。

## 2. 本轮范围、非目标与复杂度预算

### 2.1 本轮必须交付

- 一个 Dell 研究问题从用户输入到最终报告的完整多 Agent 纵切；
- 自主 Lead、动态任务计划、专业 Agent 的多轮 tool loop、Counter 定向反查、Verifier 责任路由、HITL 和运行后追问；
- 真实 S1/S2/MCP 数据消费；
- capability/data/Skill 渐进披露；
- 可恢复的上下文与 checkpoint；
- 自由正文与可审计 ClaimLedger；
- 可部署、可观察、可测量的后端与前端路径；
- 真实 case 最终验收时记录时延、tokens、调用数、失败、恢复、证据覆盖和人工干预。

### 2.2 本轮明确不做

- 任意公司、任意开放研究问题的通用产品；
- MU/NVDA 泛化；
- 全市场数据、估值、目标价或投资建议；
- GraphRAG 平台、4B/fine-tune、第二套 crawler、第二套 MCP、第二套 Agent framework；
- 多租户生产 SaaS、完整 IAM、多人协同光标；
- 让模型动态执行代码或生成图节点；
- 把原始 provider reasoning 当产品日志；
- 以 100% accuracy、固定 13 次调用或极低 token 上限作为完成条件；
- 在本设计门关闭前启动 A03 或任何新的付费 Dell `PaidFullChainExecution`。

### 2.3 复杂度停止规则

新增组件必须至少满足一项：

- 关闭 Dell 当前已证明的 blocker；
- 替代一块已经存在且过重的自研基础设施；
- 让 Agent 真实获得自主工具/Skill/上下文能力；
- 让运行可恢复、可干预、可追责；
- 直接提高最终报告可用性或可验证性。

若只是为了“以后可能扩展”而新增服务、数据库、队列、协议或 UI 框架，则本轮停止。

## 3. 技术栈冻结与采用边界

### 3.1 采用表

| 能力 | 冻结选择 | 决策 |
|---|---|---|
| Agent orchestration | LangGraph OSS `StateGraph / Send / Command / ToolNode / interrupt` | `ADOPT` |
| Provider adapter | legacy Dell 路径当前仍直接使用 `langchain-deepseek`；目标是在 Wave 2 前收敛到 `ModelRuntimePort` | `RETAIN_TRANSITIONALLY` |
| 通用高层 Agent framework | 不引入 Deep Agents、AutoGen、CrewAI 或第二套框架 | `REJECT_THIS_SLICE` |
| 数据/工具协议 | 官方 MCP Python SDK 2.1.1，同一个 server | `ADOPT` |
| 领域 schema | Pydantic 2 / JSON Schema，从同一 canonical model 投影 | `ADOPT` |
| 持久 checkpoint | Agent Server 管理的部署态持久化；SQLite/in-memory 只用于零模型测试 | `ADOPT_SERVER_OWNED` |
| 持久控制面 | Agent Server PostgreSQL + 独立 FIN 领域 schema；不读取或复制 server 内部表 | `ADOPT_FOR_PARITY` |
| Redis | Agent Server `local_parity` 的运行依赖；仅作瞬时队列、signal 和 stream 协调 | `ADOPT_AS_SERVER_DEPENDENCY` |
| 外层数据/评测编排 | 现有 Dagster | `RETAIN_OUTER_ONLY` |
| Web backend | 现有 FastAPI Workbench BFF | `RETAIN_AND_EXTEND` |
| 实时浏览器通道 | SSE；用户操作用 REST command | `ADOPT` |
| WebSocket | 多人/高频双向交互出现前不引入 | `HOLD` |
| Frontend | 现有 React 19/Vite；按需采用 TanStack Query/Virtual、Radix | `ADOPT_INCREMENTALLY` |
| DAG 可视化 | 首批用可访问列表；真实复杂度证明后再用 React Flow | `HOLD` |
| Observability | OpenTelemetry/OpenInference 风格 trace；业务事件另存 | `ADOPT_INCREMENTALLY` |
| LangSmith/LangGraph Agent Server | Dell 个人非商用、本地演示的唯一 serving/runtime 路径 | `ADOPT_OWNER_DECIDED` |
| Temporal/Celery/自写 Redis Streams queue | 当前不引入 | `HOLD` |

### 3.2 为什么仍有 LangChain

LangGraph 是执行引擎，`langchain-deepseek` 当前只承担 DeepSeek 模型和 tool-call transport 适配。FIN 的 Evidence、NumericFact、Claim、权限、checkpoint 语义和产品 API 不依赖 LangChain 对象。

本轮不会为了“清除 LangChain”而自行实现 provider tool loop；也不会让 LangChain 接管领域真值。`ModelRuntimePort` 是本设计要求的目标边界，不是当前仓库已经完成的事实；在它真正接住现有调用、usage、error 和 reasoning-content 连续轮之前，不得声称 provider 已被隔离。以后只有官方 OpenAI-compatible SDK 的真实 tool-call、reasoning-content 连续轮、usage 和错误语义 parity 通过后才切换。

### 3.3 LangSmith/LangGraph Agent Server 采用裁决

2026-09-03 Owner 明确选择：Dell 个人非商用、本地演示直接采用 LangSmith/LangGraph Agent Server，不实现也不保留自研 single-worker runtime fallback。许可、合法 API key、egress 和部署能力仍是必须如实验证的配置前置，不能因为“不商用”而虚构授权；但缺少 key 的处理是阻断部署验收并请求配置，不是转向自造运行时。

Wave 0B 已在 `a101292dfb42930502b0f970286d5e3a0acb5d37` 上完成第一段真实资格测试：`langgraph dev` 配置 per-worker concurrent-job cap=`4`，加载 4 个零模型 graph，共发生 69 次 HTTP/SSE 交换；thread 多 run 状态、interrupt/resume、同线程并发拒绝、图内和跨线程并发、cancel、非法输入拒绝及 live-process resumable SSE 均通过。执行窗口重叠证明了并发执行，但尚未证明 multi-worker deployment、worker failover 或 HA。实测同时发现并冻结两个边界：

- 原生流不得同时订阅 `updates + values`：两帧可能共享同一个 SSE ID，断线点会产生漏帧窗口。FIN 客户端只订阅单一 `updates`，完整状态另读 `GET /threads/{thread_id}/state`；探针必须用真实已接收 event ID 验证 exact-suffix resume；
- `langgraph dev` 的 in-memory runtime 在进程重启后恢复了 thread checkpoint 和 run records，但已完成 run 的 resumable SSE 帧返回空流。因此它只用于零模型开发/在线语义资格，不能冒充 Dell `local_parity` 部署证明。

采用后的强制边界是：

- Dell 最终演示前必须用 checked-in、digest-pinned Agent Server Compose、PostgreSQL 与 Redis 复跑真实 graph 的 restart、checkpoint、interrupt/resume、cancel、并行与 SSE replay；合法 LangSmith key 是配置前置；
- FIN `AgentSession ↔ Agent Server thread`，FIN `ResearchRun ↔ 一个或多个 server run 的领域 aggregate`，FIN `RunInvocation ↔ Agent Server run`，FIN `ActionAttempt ↔ FIN receipt`；业务代码不得因为两边都叫 run 而合并身份；
- Workbench 只实现 FIN 领域合同、权限、Evidence/Claim/SessionEvent 投影、snapshot-first 读取和薄 BFF，不复制 Agent Server 的 scheduler、queue、thread/run 状态机或 cancel/resume 实现；
- 不再设计 `REJECT_WITH_RECEIPT_AND_USE_OSS_SINGLE_WORKER` 分支，也不引入 Temporal、Celery、自写 Redis Streams queue 或第二套 Agent framework；
- checked-in Agent Server Compose 的真实 run/checkpoint/SSE/LangSmith trace 资格门未通过时，Wave 4/5 serving 与最终演示验收保持阻断；inventory/compiler/data-disclosure 零模型工作可并行继续，因为它不实现重叠 runtime。

## 4. 总体架构

```text
User / Workbench
        │  REST commands + SSE events
        ▼
FastAPI Research Run BFF
        │
        ├── Product control repository ── PostgreSQL (target) / SQLite (local-lite)
        │      Session / Run / Event / Command / Notebook / Artifact refs
        │
        ├── Runtime context & disclosure service
        │      trusted scope injection / catalog / skill / projection
        │
        └── LangSmith/LangGraph Agent Server runtime
               │
               ├── Research Lead agentic loop
               ├── dynamic ResearchPlan scheduler (`Send`)
               ├── generic Specialist agentic subgraphs × N
               ├── Counter agent
               ├── deterministic Validator
               ├── Semantic Verifier agent
               └── Writer / final HITL
                         │
                         ▼
                 Agent-facing tool views
                         │ trusted injection
                         ▼
                 Existing MCP Server 2.1.1
                   ├── S1 local knowledge
                   ├── Reviewed Evidence
                   ├── S2 financial facts
                   ├── deterministic calculator
                   └── external discovery/capture
```

### 4.1 四个责任平面

| 平面 | 拥有 | 禁止 |
|---|---|---|
| Data/Tool | capture、parser、corpus、retrieval、SQL、calculator、artifact lineage | 把工具失败解释成模型失败或 public gap |
| Runtime/Harness | session、权限、schema、selector compiler、checkpoint、budget、validation、feedback routing | 编写研究结论、静默改写模型判断 |
| Agent | 理解目标、形成假设、申请资料、研究、反思、修订计划、形成判断 | 创造 Evidence/NumericFact/权限/公开缺口权威 |
| Skill/Method | 专业方法、公式、问题拆解、反证提示 | 作为事实或证据，或自行授予工具权限 |

### 4.2 Canonical v1.2 compatibility decision

新纵切采用 canonical runtime `v1.2 successor`，而不是在 Dell 模块中另建第二套 Session/Event/Plan 真值。v1.0/v1.1 继续不可变；legacy 只有在来源制品、摘要和身份基数均可证明时才能经显式 adapter 映射，不能仅凭一个旧 `AgentSession` 猜出完整运行历史：

| 身份 | v1.2 基数与语义 | legacy 映射 |
|---|---|---|
| `AgentSession` | 一个稳定 case conversation / 顶层 LangGraph `thread_id`；一对多 ResearchRun | 通用 v1.0 adapter 只投影 session envelope，不证明 Run/Invocation/Action |
| `ResearchRun` | 一次完整研究生命周期；pause/resume 不创建新 Run；follow-up 创建带 parent 的 child Run | exact import bundle 必须给出原 run ID 与终态；付费执行标签不能冒充 run ID |
| `RunInvocation` | 一次 start/resume/recovery 的 worker 调度与 lease；同一 Run 可有多个，不改写旧 invocation | 仅在原始 start/resume/recovery 证据足够时映射；否则 fail closed |
| `ActionAttempt` | 一次 model/tool/capture/publish 副作用尝试；每次 retry/correction 使用新 ID | 仅由原 request/receipt digest、actor、时间和结果映射，不能由调用者自由填写 |

A02 使用一份 answer-free、content-addressed 的精确导入包，分别绑定原 `PaidFullChainExecution`、ResearchRun、首个 RunInvocation 和 Planner ActionAttempt；历史 `started/finished` 时间来自不可变来源，`imported_at` 只表示迁移发生时间。A01 在取得同等级来源包前拒绝完整身份迁移。A01/A02 都优先走 exact mapper，禁止落入通用 session adapter。v1.1 event adapter 只能接受已经校验并互相绑定的 `ResearchRun / RunInvocation / ActionAttempt` 对象；调用者不能再自由提交 run/invocation/action ID 来拼接历史。

`CanonicalSessionEventV1_2` 扩展 v1.1 的事件 union，保留旧 18 类事件及 digest-chain 语义，并新增 run/node/disclosure/admission/decision/finding/intervention/artifact/publish 等判别事件。canonical sequence 始终 `session-scoped`、从 1 连续递增，是唯一审计顺序。

面向某个 Run 的 SSE 使用派生的 `projection_sequence`，由该 run 对应的 canonical events 按 `(session_sequence, event_id)` 确定性编号；每个 RunEvent 必带 `source_session_sequence / source_event_id / source_event_digest / projection_policy_digest / authorization_view_digest / projection_digest`。它可以重建、删除后重算，不是第二份业务真值。`Last-Event-ID` 使用 projection sequence，因此过滤另一个 run 的 SessionEvent 不会制造假 gap；policy/ACL view 变化后旧 cursor 不兼容，必须返回 fresh authorized snapshot，不能在同一 cursor 下悄悄改变可见内容。

Wave 0A 必须先产出 v1.2 machine-readable contract、v1.0/v1.1 compatibility fixtures 与 migration table；当前 `canonical_runtime/session.py` 在 adapter 接入前仍可拒绝新事件，这是预期阻塞，禁止绕开旧 validator 另写无关联的 Dell ledger。

## 5. Dell 产品问题与 CoverageObligation

Q1–Q9 不再等价于九个固定 Agent，而成为必须被计划覆盖的验收义务：

| Obligation | 研究面 | 最低完成语义 |
|---|---|---|
| Q1 Issuer Truth | 最新 Dell 业绩、orders、backlog、revenue、guidance、分部 | 发行人事实与 S2/非 S2 权威分开 |
| Q2 Demand Quality | 具名客户、部署、订单质量、客户集中、pull-forward | 至少一组支持证据与一组反证/限制 |
| Q3 Units / ASP / PVM | 出货量、配置、ASP、价格/数量/组合 | 披露不足时只能做有界推断或标记缺口 |
| Q4 Architecture Ramp | GB300/Rubin 等架构量产、系统可用性、交付阶段 | 区分供应商 announcement、实际量产和 Dell 交付 |
| Q5 Supply and Price | GPU/HBM/DRAM/NAND/SSD、供货与涨价传导 | 供应事实、价格指标、Dell 利润/需求推断分层 |
| Q6 Model Compute Demand | 模型能力、OpenAI/Anthropic/hyperscaler 采购与 capex | 只能作为行业需求背景，禁止直接归因 Dell |
| Q7 Export Control / China | 美国限制、中国收入/客户/产品影响 | 规则事实、公司披露、推断分别绑定 |
| Q8 Competition / Value Pool | HPE、Supermicro、ODM、供应商议价与价值分配 | 至少有相对竞争证据和利润池判断 |
| Q9 Counterevidence / WWC | 主要反例、替代解释、什么会推翻结论 | 每个高材料性结论至少一个 counter surface |

Coverage 不再用一个“9/9”混写三种不同事实，而分成：

- `registered_obligations`：Q1–Q9 对象是否完整登记；零模型门要求 `9/9`；
- `plan_reachable_obligations`：accepted plan 中是否存在可执行、权限合法且依赖可达的 task；零模型门要求 `9/9`；
- `evidence_satisfaction`：真实研究后的 `uncovered / partial / covered / disputed`；零模型阶段不得声称 covered。

一个任务可以覆盖多个 obligation；Lead 可拆分、合并、增加或取消任务，但 Runtime 不允许无理由删除 material obligation。状态转换必须绑定 task、Evidence/Fact/Calculation、Counter、Finding 和 disposition receipts。`covered` 要求材料性要求已满足；`disputed` 必须绑定冲突证据、Lead disposition、WWC 和 Human acceptance；`partial/uncovered` 不能被 `stop_sufficient` 静默吞掉。每个 material obligation 只有 `covered`，或经明确人工接受的 `disputed/bounded_gap`，才是合法终态。

Coverage 之外另有 `MinimumRouteObligation / BaselineSourcePlan`。它逐 Q1–Q9 冻结 answer-free 的最低资料类别：required/optional 的 Reviewed Evidence、local Candidate、S2、external source-family 与 calculator，所需 authority、可替代条件、period/entity 边界和 route-plan digest。Planner 可以增加、收窄或以合法 `PlanDelta` 替代路线，但不得静默删除 required route。该计划不包含问题答案、gold passage 或结论。

## 6. 动态 DAG 与 Multi-Agent 执行模式

### 6.1 稳定外层图

```text
bind_case
  → lead_observe_and_plan
  → validate_plan
  → schedule_ready_tasks
  → Send(generic_specialist_subgraph × ready tasks)
  → collect_task_artifacts
  → lead_reflect
       ├─ PlanDelta → validate_plan
       ├─ more tasks → schedule_ready_tasks
       ├─ enough evidence → counter
       └─ pause/human → interrupt
  → counter
       ├─ targeted finding → responsible specialist
       └─ no material finding → lead_synthesis
  → lead_synthesis
  → deterministic_research_validate
       ├─ failure → earliest owner
       └─ pass → semantic_research_verifier
  → semantic_research_verifier
       ├─ finding → responsible agent / tool owner / human
       └─ pass → writer
  → writer
  → final_deterministic_validate
  → final_semantic_verifier
       ├─ wording-only finding → Writer repair → new artifact/ledger revision → final_deterministic_validate
       ├─ research/claim finding → earliest owner repair → lead_synthesis → research/final validators
       └─ pass → final_HITL
  → final_HITL
  → publish_demo_artifact
  → complete
```

外层图的代码固定；变化的是 `ResearchPlan`、任务数量、依赖、Agent 角色、披露和状态。

任何 final finding 都使旧 artifact digest、claim manifest 和未提交/已打开的 approval stale。修复必须生成新 revision，再经过 deterministic final validator、final semantic verifier 和 fresh HITL；不得复用旧 approval。若 finding 回到研究 owner，则还要重新经过 Lead synthesis、research validator/verifier 后才能回 Writer。

### 6.2 专业 Agent 内层图

每个专业 Agent 使用同一实现，不复制九套 runtime：

```text
observe projected context
  → model chooses one action
  → host validates action
       ├─ request disclosure
       ├─ call S1/S2/calculator/external tool
       ├─ submit/update BranchNotebook
       ├─ submit PlanDelta or EvidenceRequest
       ├─ submit NarrativeArtifact
       ├─ submit ClaimLedger
       └─ stop / pause / escalate
  → append receipt + event + checkpoint
  → observe again
```

角色差异仅来自 `RoleMethodPack + selected Skill + task objective + capability view + authority + evidence scope`。

### 6.3 `ResearchTaskSpec`

任务计划只表达研究意图，不含物理 route/lane：

```json
{
  "task_id": "task_supply_price_01",
  "owner_role": "supply_chain_analyst",
  "objective": "判断内存和企业 SSD 涨价如何影响 Dell AI server 价格、毛利和需求",
  "dependency_ids": ["task_issuer_fact_base_01"],
  "coverage_obligation_ids": ["Q5_SUPPLY_AND_PRICE", "Q9_COUNTEREVIDENCE_WWC"],
  "success_criteria": [
    "区分 supplier reported fact 与行业 indicator",
    "记录至少一个成本传导机制和一个相反机制",
    "所有 material number 绑定 fact 或 calculation receipt"
  ],
  "requested_capability_refs": ["cap:s1-search", "cap:external-search", "cap:calculator"],
  "materiality": "high",
  "status": "planned"
}
```

Runtime 对 `ResearchPlan/PlanDelta` 做 DAG 无环、依赖存在、角色/权限、coverage、budget、stale digest 和取消影响校验。

本设计不静默另造一个与 canonical v1.0 同名但不同义的 `PlanDelta`。Wave 0 实现版本化的 `AgenticPlanDeltaV1_2` adapter：

- 保留并显式映射 v1.0 的 `add_actions / modify_actions / defer_actions / cancel_actions`；
- 每项 action 绑定 target task/obligation、reason 与 Feedback refs、coverage-before/after、replacement 或 defer deadline、budget delta 和 authority impact；
- 取消 material obligation 必须有等价 replacement，或明确 Human/Verifier disposition；
- base plan digest、catalog/policy digest、accepted plan digest 和 resulting graph digest 全部冻结；
- CoverageGap 与 PlanDelta 校验必须在调用时通过 host repository/resolver 读取当前 verified-artifact registry，并校验 revision/tip；调用者携带的旧 snapshot 不能成为当前权威。纯领域层使用依赖注入端口，真实 backend composition root 必须把该端口固定到可信 repository，API/model 输入不得提交 resolver；
- accepted delta、canonical event 和 checkpoint 在同一 durable replay unit 中引用同一个新 plan digest，禁止只更新内存 active-plan 指针。

### 6.4 Lead、Counter、Verifier 的区别

- Lead：规划、分派、聚合、权衡和最终研究判断。
- Counter：主动寻找反证、替代机制和结论脆弱点，是研究角色。
- Verifier：审计 claim/evidence/decision/lineage，形成 findings 并路由，不直接重写报告。
- Writer：只在研究和 verifier 达到可交付状态后组织自由自然语言；缺支持时退回 Lead，不默认自由搜索。

## 7. MCP、Provider Tool View 与可信注入

### 7.1 三层契约

1. Canonical Domain Contract：Evidence、Fact、Calculation、Claim、Failure 等 FIN 对象。
2. MCP Wire Contract：完整 tool/resource 输入输出、`structuredContent`、`isError` 和 `_meta`。
3. Provider-visible AgentToolView：模型本轮真正能看到的精简语义工具。

三层从同一 canonical Pydantic model/adapter 生成或明确映射，禁止 schema、prompt 和 host validator 各写一份不同规则。

### 7.2 拆分小工具，消灭非法组合

Provider-visible 工具至少拆为：

- `request_local_evidence`
- `search_reviewed_evidence`
- `request_external_source`
- `query_financial_facts`
- `calculate_research_metric`
- `request_disclosure`
- `submit_plan_delta`
- `submit_narrative`
- `submit_claim_ledger`
- `request_pause_or_human_review`

本地和外源不再共用一个复杂 `EvidenceRequest` 条件对象。对 provider strict schema 的支持只能减少错误，host validation 仍是最终门。

### 7.3 模型参数与 Runtime 参数

模型可以填写：

- query / purpose；
- entity ref；
- period intent；
- semantic source-family refs；
- expected information gain；
- limit；
- requested metric/formula；
- why this capability/Skill is needed。

Runtime 必须注入且模型不可覆盖：

- case/session/research-run/run-invocation/action-attempt/agent/task identity；
- case version、as-of、snapshot digest；
- authority、permission、branch scope；
- canonical issuer selector；
- physical source role/route/lane；
- method/Skill digest；
- evidence promotion、S2 write 和 public-gap 权限；
- idempotency key、timeout、rate/cost boundary。

现有模型可见的完整 `run_scope` 必须退出 provider schema，改成 Runtime 内部对象或 sealed scope handle。

### 7.4 SourceFamilyCompiler

新增的薄领域编译器只负责把语义 source family 解析到当前 inventory：

```text
semantic source families + entity refs + period intent
        + frozen inventory snapshot + task authority
                    ↓
three non-interchangeable compiled targets
        + eligible object count/cardinality bounds + compilation receipt
```

三个 target 必须使用判别合同：

- `ReviewedEvidenceIntent`：只含 Reviewed Evidence 索引实际可比较的 entity/period/topic/authority 条件，不包含会抑制该 lane 的 local `route_ids`；
- `LocalCandidateRetrievalScope`：canonical issuer/source-role/route/lane/period selectors，只返回 Candidate；
- `ExternalSourceIntent`：topic/source-family/domain/time intent，不携带本地物理 selector。

`reviewed_first` 是 Runtime 的组合策略，不是把三种 selector 塞进一个对象：先独立检索 Reviewed Evidence，再按需要执行 local Candidate 检索；local `route_ids` 非空不得跳过、降格或替代已经存在的 Reviewed Evidence。

规则：

- 编译结果 `eligible_count > 0` 后才执行 local search；
- `eligible_count = 0` 返回 typed correction，不执行空 MCP call；
- 不能仅以“非零”通过；必须同时验证 issuer/period/source-role/route/branch/authority 一致、禁止集合交集为零、selector cardinality 未超过该 family 的冻结上限；
- 返回全库、忽略 period、ticker alias 错绑、跨 branch family、Reviewed/Local/External 串 lane 或 stale inventory digest 均 fail closed；
- 编译器不做 BM25、不写答案、不根据 query 特判某个 issuer；
- inventory 只含 answer-free metadata；
- receipt 保存 inventory digest、输入语义 refs、输出 selectors 和 eligible count；
- 模型通常只看简化结果和可选下一动作，不需要看全部物理 selector。

这同时是 RC-S3-105 的最早责任层修复。

验收使用 answer-free 正/负 selector fixture，不只数对象：正确 family/entity/period 必须落入允许子集；错误 issuer、错误期间、错误 authority、过宽全库 selector 和 lane 串接必须被拒绝。九分支门验证的是正确最低路线及其边界，不是九个 ID 在 JSON 中出现。

### 7.5 Reviewed Evidence v1.2 thin adapter

当前 MCP `search_reviewed_evidence(query, branch_id, run_scope, limit)` 是 query-only BM25，不能假装已经执行严格 entity/period/topic 过滤。Wave 0A/1 冻结 `ReviewedEvidenceIndexV1_2` 与 thin adapter，而不是另建第二个 Evidence store：

- index row 至少含 `case_key/entity_ids、target_id/topic binding、evidence_role、publication_date、source_reporting_period_end、source_type/tier、evidence_id、locator、item_digest、index_digest`；
- provider-visible `ReviewedEvidenceIntent` 只提交 query/purpose/semantic entity-period-topic intent；Runtime 注入 case/branch/run scope、authority 和 snapshot digest；
- 首版可以复用现有 MCP query search 并 overfetch，再由 host 对 MCP 返回的现有 metadata 做 exact post-filter，形成 `ReviewedEvidenceFilterReceipt`；随后再把同一 optional filters 薄扩展进原 MCP server，不能启第二个 server；
- 只有 output metadata 能证明 entity/case、period/as-of、topic/target、authority/evidence role 与 intent 相容时，才能满足 required reviewed route；
- legacy row 缺少可比 metadata 时返回 `legacy_query_only_locator / typed_metadata_insufficiency`，可以提示进一步读取，但不能独立满足 required reviewed route，也不能单独支持 `ReportedFactClaim`；
- local Candidate 查询始终独立执行；local `route_ids` 不传给 reviewed MCP，也不能令 Reviewed Evidence 被跳过或降格；
- 读 ID 后再次验证 item digest、locator、authority、period 和 index snapshot；search locator 本身仍不是引用正文。

必测三组反例：local route 非空仍能发现合格 Reviewed Evidence；query 附近但 entity/period/topic 不符的 legacy hit 不满足 strict intent；Evidence 与 Candidate 并存时两者并列保留各自 authority，Candidate 不替代/降格 Evidence。

## 8. 渐进式披露

### 8.1 每轮固定看到什么

每次模型调用前，Runtime 生成 `ModelVisibleContextManifest`，至少包含：

```text
Pinned governance summary
Current objective and task
Current plan slice / latest accepted PlanDelta
Latest observation and unresolved FeedbackReceipts
Compact L0 capability/data/Skill catalog
Already granted disclosure packs
AvailableActionMenu
Budget / stop / intervention status
```

case identity、as-of、authority 和安全规则来自版本化、机器可读且 content-addressed 的 `RuntimePolicySnapshot`，始终 pinned，不是模型可选择卸载的 Skill。Runtime policy 与 progressive-disclosure policy 是两个不同对象、两个不同 digest；RuntimePolicySnapshot 明确绑定当前 disclosure-policy digest，RuntimeScope 和授权回执同时绑定两者，不能要求一个 digest 同时代表两份不同内容。`AGENTS.md` 与 Project OS 是人类/工程设计输入；模型只能看到从 canonical policy 生成的非权威简要说明，Markdown 文案本身不能授予或撤销权限。若提示摘要与 host validator 冲突，以服务端 contract 为准；修改 Markdown 不得改变权限，修改任一 canonical policy 必须改变对应 digest 并让 stale projection fail closed。

`ModelVisibleContextManifest` 中的 objective 不是调用者可以自由替换的 prompt 文本。Host 必须从重新验证过的 current accepted `ResearchPlan` 中，以 `task_id` 唯一解析 `ResearchTaskSpec`，再签发 `RuntimeScopeAuthorizationRecord`；该记录同时绑定 `objective_digest / accepted_plan_digest / research_graph_digest / task_assignment_digest`，其中 task-assignment digest 还绑定 agent、role、task 和 task-kind。签发前必须验证 plan 的 case、runtime policy、authority matrix、`ResearchTaskSpec.owner_role == RuntimeScope.agent_role` 以及 task 所需 authority 均与 sealed scope 相容。角色身份先使用同一 canonical role ref 精确相等；未来若引入 alias，只能由 current authoritative role-mapping resolver 解析，不能由调用者自由声明。manifest 只能投影 current authorization 中的这些摘要，并重新计算 raw objective 的摘要；同一 scope 下只改 objective、换角色、使用 draft/stale plan 或提交不相干 graph 均 fail closed。调用者不能把 objective/graph digest 作为独立权威参数传入。

manifest 中的“当前运行事实”也不能由普通函数/API 参数提交。`latest_plan_delta_refs / observation_refs / unresolved_feedback_refs / available_next_actions / budget_status / stop_status / intervention_status / context_checkpoint_ref` 必须由 composition root 注入的 `CurrentModelContextResolver` 读取带 self-digest 的 host-current snapshot。只写 `issued_by=host` 或让 snapshot 自己重签不构成权威：snapshot ID、resolver ref、current store revision、上述字段和 Session/Run/Invocation/Action/Task identity 先确定性生成 `model_context_state_digest`，并在该 ActionAttempt 的 sealed `RuntimeScope` 签发时写入 scope；current scope authorization 与 canonical `action_intent_committed` event 已绑定整个 scope digest。manifest 消费时重新计算 snapshot state digest，并必须与这个先行 scope anchor 完全相等。因此调用者改写来源 revision、任何当前 refs、action menu 或 status 后即使同时重签 snapshot，也不能通过。snapshot 还绑定 current authorization、accepted plan/graph、canonical event-ledger snapshot/tip/revision，以及 runtime/disclosure 两份 policy；每次组装 manifest 都重新读取、重建并逐项核对。摘要相同只是第一层：`RuntimePolicySnapshot` 内部的 case、版本、as-of、data snapshot 还必须与 RuntimeScope 一致，data snapshot 同时与 catalog inventory 一致，catalog digest 与 current catalog 一致，disclosure-policy digest 与 current disclosure policy/scope 一致，scope branch/permission 必须是 runtime policy allowlist 的子集。`governance_summary` 只能由完成这些交叉验证的 canonical `RuntimePolicySnapshot` 确定性派生。manifest 额外携带 current-model-context snapshot digest，使 verifier 能证明该轮看到的是哪一个当前状态。调用者即使自签不存在的 PlanDelta/Observation/Feedback、伪称 intervention 已生效、预算已耗尽、研究已足够，或把 Dell scope 绑定到另一 case/未来 as-of 的自签 policy，也不能令 runtime 为其生成合法 manifest。

所有有 self-digest 的 current-state、identity、plan/evidence 和 recovery 对象都在消费边界重新结构化验证，不能依赖 Pydantic 对象“曾经构造成功”：disclosure catalog（包括嵌套 resource/capability 语义）、disclosure policy、DisclosureReceipt、RuntimePolicySnapshot、ModelNodeAuthorityMatrix（包括嵌套 node authority）、RuntimeScopeAuthorizationRecord、RuntimeScope、CanonicalEventLedgerSnapshot、ACL snapshot（包括嵌套 grant）、canonical event/projection、ContextCheckpoint 及其 Session/Run/Invocation/current-material snapshot、CurrentModelContextSnapshot、RecoveryDisposition 及其绑定的 Action/Invocation/Run、ResearchPlan/PlanDelta、current verified-artifact registry（包括嵌套 artifact）、CoverageGap 请求和 model-visible context，均须从其序列化内容重建并重算摘要。manifest 即使没有任何 grant，也必须无条件核对并显式携带 disclosure-policy digest；L1 answer-free、not-authorized node 的 provider binding、receipt token、ledger repository/events、policy budget、ACL issuer、checkpoint graph digest、model-current plan/ledger/policy binding、recovery decision、plan route proof 和 registry nested artifact 等字段经 `model_copy/model_construct` 修改而保留或重签摘要时必须立即拒绝。

### 8.2 统一披露层级

| 层 | Capability | Data | Skill |
|---|---|---|---|
| L0 | 名称、用途、authority、成本/时延级别 | 数据族、对象数、entity/period/source-family 覆盖 | name、description、version、digest |
| L1 | 语义输入输出、限制、常见错误 | answer-free inventory、字段与覆盖 | 完整 Skill 主体 |
| L2 | 详细 output/authority contract | 候选 metadata 和稳定 resource refs | 指定 reference/script/asset 索引 |
| L3 | 一般无需进一步展开 | 指定 Evidence/Fact/Artifact 正文或 bounded excerpt | 指定单一深层资源 |
| L4 | operator-only | restricted raw capture/diagnostics | operator-only debug resource |

L0/L1 不得包含能泄漏案例答案的数值、结论摘要或 gold label。

### 8.3 申请与回执

模型通过唯一入口 `request_disclosure` 申请：

```json
{
  "catalog_digest": "sha256:...",
  "kind": "capability",
  "ref": "cap:s1-local-search",
  "depth": "contract",
  "reason": "需要核实 Dell 最新季度 orders/backlog 的原始发行人表述",
  "expected_use": "决定需求增长是否存在 pull-forward 风险"
}
```

Runtime 验证 ref、role/task authority、catalog/snapshot digest、token budget、深度和递归，再返回 `DisclosureReceipt`：

```json
{
  "status": "granted",
  "ref": "cap:s1-local-search",
  "granted_depth": "contract",
  "resource_uri": "fin://capability/snapshot/cap:s1-local-search",
  "resource_digest": "sha256:...",
  "estimated_context_tokens": 860,
  "permitted_next_actions": ["request_local_evidence", "request_data_inventory"]
}
```

每次 list/load/read/invoke 形成独立 receipt；Skill 必须另有 selection、injection 和 consumption/non-consumption receipt。Skill 只能教方法，不能授予工具权限或成为证据。

### 8.4 MCP resources

在现有 MCP server 上增加稳定 resources/templates，不启动第二个 server：

```text
fin://catalog/{snapshot_id}/capabilities
fin://capability/{snapshot_id}/{capability_id}
fin://inventory/{snapshot_id}/{scope_id}
fin://skill/{skill_id}/{version}
fin://skill/{skill_id}/{version}/reference/{reference_id}
fin://evidence/{snapshot_id}/{evidence_id}
fin://artifact/{artifact_id}
```

模型申请，Runtime 授权并读取 resource，再在下一轮注入；模型不直接获得内部文件、数据库或 Redis 浏览权限。

### 8.5 每个结果都给出可执行下一步

每个 tool/disclosure/validator 结果都必须包含 `AvailableNextAction`，但只给当前合法选项，不把全系统说明重复塞给模型：

- 继续读取指定 Evidence；
- 请求更深 inventory；
- 改正 period/source family；
- 选择另一条已资格路线；
- 提交 PlanDelta；
- 请求人工；
- 暂停等待工具修复；
- 在真实 route 已耗尽后申请 GapEligibility。

## 9. Typed result、错误与自纠

### 9.1 三类结果

1. 正常领域结果，`isError=false`：found、empty、candidate rejected、typed conflict、insufficient authority、scope exhausted、gap eligible。`empty` 本身不是 public gap。
2. 模型可纠正的 tool error，`isError=true`：参数不合法、catalog stale、unknown source family、period 不完整、selector zero-match、scope/permission 不相容。
3. protocol/server integrity error：未知工具、transport 损坏、响应不符合 schema、内部状态不一致；由 Runtime 处理，不让模型盲目 retry。

### 9.2 `ToolFailureReceipt`

```json
{
  "failure_code": "NO_ELIGIBLE_SELECTOR",
  "category": "semantic_validation",
  "owning_plane": "runtime_data_binding",
  "owning_stage": "selector_compilation",
  "retryability": "correctable_with_new_information",
  "permitted_next_actions": [
    "request_data_inventory",
    "replace_source_family_ref",
    "submit_plan_delta",
    "pause"
  ],
  "forbidden_interpretations": [
    "不得据此认定公司未披露",
    "不得据此认定公开信息不存在"
  ],
  "public_gap_eligible": false,
  "diagnostic_ref": "artifact://diagnostic/..."
}
```

模型看到简洁说明；完整诊断放 MCP `_meta` 或 restricted artifact。适配器必须保留 `content / structuredContent / isError / _meta`，不能再把所有失败折叠成 `mcp_server_error`。

### 9.3 自纠与防循环

- 修正后的动作使用新 `action_id/action_attempt_id`；
- transport retry 与 semantic correction 分开记录；
- 同一 request digest 不允许无限重放；
- 单纯 schema malformed 最多一次同义纠正；
- 需要新信息时按 expected information gain 继续，不以固定 13 次调用作为质量目标；
- 连续无新 evidence/claim/coverage/plan state 的动作触发 no-progress feedback；
- 重复同一 no-progress signature 后进入 PlanDelta、替代路径或人工，而不是继续烧 token；
- 工具/数据故障由相应 owner 修，Agent 只能选择已资格替代路线或暂停。

### 9.4 `GapEligibilityReceipt`

`scope_exhausted` 只是当前授权范围内未找到结果，永远不是 public gap。按 material proposition 申请 public gap 时，Runtime 必须生成版本化 `GapEligibilityReceipt`，至少绑定：

- `EvidenceNeed / MaterialRequirementPlan` 与 obligation；
- local object/index/parser/SQL 检查 receipts；
- source-family compilation 与 inventory digest；
- required route discovery/capture/execution receipts；
- Candidate decision、Evidence admission/rejection receipts；
- transport retry/alternative-route disposition；
- budget、stop 与 unresolved owned-defect disposition；
- reviewer/authority 与 receipt digest。

只有所有 required route 有可验证终态、且不存在仍归属本地数据、检索、transport、admission 或权限配置的未修 defect，才可令 `public_gap_eligible=true`。单个 empty、selector miss、工具失败、预算耗尽或 scope exhausted 都不能作为唯一证明。

## 10. 上下文、记忆与 compaction

### 10.1 身份层次

- `AgentSession`：一次 Dell 用户研究会话的稳定 aggregate；冻结 case、as-of、snapshot、objective 和 authority；映射顶层 LangGraph `thread_id`；可包含多个 ResearchRun。
- `ResearchRun`：一次完整研究生命周期；pause/resume 保持同一 Run，终态后 follow-up 创建带 parent 的 child Run。
- `RunInvocation`：同一 ResearchRun 的一次 start/resume/recovery worker 调度与 lease；每次恢复生成新 ID。
- `ActionAttempt`：一次具体 model/tool/capture/publish 副作用调用；失败永不覆写，后续 correction/retry 使用新 ID。
- `BranchNotebook`：分支的专业工作状态，不是聊天全文或隐藏 CoT。
- `ContextProjection`：某一次模型调用实际看到的可复现 manifest。
- `ContextCheckpoint`：FIN 领域的材料性状态和 LangGraph checkpoint ref 的绑定。

没有限定词的“attempt”禁止出现在新 machine contract。历史已存在的 A01/A02 统一命名为 legacy `PaidFullChainExecution` label：A02 映射为一个失败 ResearchRun、一个初始 RunInvocation 和一个 Planner ActionAttempt，而不是单个 ActionAttempt。A03 当前不存在，不映射、不预留 placeholder；只有未来新的 `PaidExecutionOwnerDecision` 成立后，才同时分配新的 `PaidFullChainExecution` ID、ResearchRun ID 和首个 RunInvocation ID。

不得再以 `run_id` 代替长期 `thread_id`。

### 10.2 BranchNotebook

每个 revision 不可变，至少保存：

- hypothesis / counterhypothesis；
- accepted Evidence、NumericFact、Calculation refs；
- material Claims；
- open gaps/questions；
- last observation；
- unresolved FeedbackReceipts；
- disclosure/Skill/tool receipts；
- proposed next actions；
- notebook digest。

不同 Agent 之间交换 Notebook、Claim 和 Evidence refs，不传整个私有聊天。

### 10.3 专业 Agent 的多轮上下文

专业 Agent 在一个 task invocation 内可以多轮自主调用；并行 task 使用隔离 checkpoint namespace。Counter 或 Verifier 回派时，以旧 Notebook + exact feedback 创建新 ActionAttempt，并保留原 Agent 身份和 task lineage。

默认不为九个分支建立九套永久聊天。只有真实出现跨 turn 独立并发/长期记忆需求后，才升级成稳定 child thread。

### 10.4 ContextProjection

每次模型调用冻结：

- session event sequence；
- objective/plan/graph digest；
- branch notebook revision；
- included artifact/evidence/fact/feedback refs；
- omitted refs 与理由；
- granted disclosure/Skill/tool catalog digest；
- token budget basis；
-最终 prompt/messages digest；
- provider-visible tool schema digest。

Verifier 因此能判断“Agent 当时看到了什么”，不需要读取隐藏推理。

### 10.5 `ContextCheckpoint` successor 与恢复必需集合

现有 canonical v1.0/v1.1 checkpoint 继续作为兼容输入，但新纵切必须通过版本化 successor/adapter 显式保存：

- `coverage_state_refs`；
- `claim_ledger_refs`；
- `calculation_receipt_refs`；
- `disclosure_receipt_refs`；
- `skill_consumption_receipt_refs`；
- `active_stop_decision_ref` 与 `budget_state_ref`；
- `context_projection_ref`；
- unresolved verifier/intervention refs；
- LangGraph checkpoint ref 与最后 canonical event digest。

恢复所需集合由已绑定的 accepted plan、event ledger、notebook revision 和 open findings 自动推导，调用方不能用默认空集合绕过。漏 Claim、漏未关闭 finding、漏 minimum obligation、漏权限/stop/budget state 的 resume 或 compaction mutation 均必须 fail closed；不得把全部状态无类型地塞入 `agent_local_state_refs`。

Wave 0A 的实现性收紧是：checkpoint creator/validator 不再接受调用者提交的 `events`、`expected_notebook_refs`、`expected_open_finding_refs`、graph/coverage/minimum-route 或任何其他 current-authority/typed-material 字段，而只通过 composition root 注入的 `CurrentContextMaterialResolver` 读取一个带 self-digest 的 current snapshot。该 snapshot 同时绑定 accepted plan/graph、host canonical event-ledger snapshot、notebook revision、coverage/minimum-route、accepted Evidence、NumericFact、ClaimLedger、Calculation、disclosure/Skill receipt、open gap、unresolved feedback、counterevidence、open question/finding、pending intervention、authority、active stop、budget、context projection 与 LangGraph checkpoint。`notebook_refs` 由上述全部 typed current state 的并集确定性派生，不能由调用者另给一个较小集合；`finding_opened/finding_resolved` 的未关闭集合还须能从 snapshot 内的 canonical events 重建并与 repository view 一致。checkpoint 绑定 material-snapshot digest 与 event-ledger-snapshot digest，恢复时必须重新读取当前 snapshot；API/model 无权提交 resolver。这样既避免建设第二套 notebook/backend，也关闭“调用者传空 expected 集合或漏掉某类当前材料再自证通过”的语义权威漏洞。

### 10.6 Compaction

Compaction 不删除 event、artifact 或 checkpoint，只重建 model-visible projection：

- 保留 identity/as-of/objective/plan；
- 保留 accepted Evidence/Fact/Calculation、material claims、counterevidence；
- 保留 open gaps/questions/feedback、pending intervention、budget/stop state；
- 保留 tool/Skill/disclosure receipts；
- 近期 action/observation 可保留原文；较旧探索压成 `non_authoritative_summary`，绑定 event range/digests；
- summary 不得晋升为 Evidence。

软/硬水位先作为参数，以 Dell fixture 做 token 实测后确定；建议初始观察区间为上下文窗口约 60–70% 和 80%，不是产品真理。任何压缩若遗漏 material open state，必须 fail closed。

## 11. 自由正文、ClaimLedger 与报告

### 11.1 两步提交

1. Agent 提交自由 Markdown `NarrativeArtifact`；
2. Host 保存 immutable content/digest，确定性生成 block/sentence anchors；
3. 同一 Agent 提交只引用这些 anchors 的 `ClaimLedger`；
4. ledger 失败只修 ledger 或相关句子，不强迫整篇按统一 schema 重写；
5. Verifier 检查所有 material assertions 是否被 ledger 覆盖。

### 11.2 Claim 类型

- `ReportedFactClaim`：必须绑定 Reviewed Evidence。
- `NumericFactClaim`：必须绑定 S2 NumericFact，期间/单位/口径一致。
- `CalculationClaim`：必须绑定可复算 CalculationReceipt、输入 authority 和公式。
- `BoundedInferenceClaim`：必须绑定 premise claims、Evidence、假设、counterevidence 和 WWC。
- `HypothesisOrScenarioClaim`：显式标明非事实。
- `BoundaryClaim`：public information gap 必须绑定 GapEligibilityReceipt；否则只能写“当前证据不足/当前检索未确认”。

### 11.3 非权威指标

发行人 Exhibit、行业摘要或其他非 S2 数字可以进入确定性计算，但必须：

- 每个输入保留 source locator、period、unit 和 authority class；
- 输出标记 `numeric_fact_authority=false`；
- 报告紧邻标注“非权威/非标准化数据来源”；
-基于它的推断记录 premise 和不确定性；
- 不写回 S2，不冒充 GAAP/XBRL NumericFact；
- 不因 authority 较低而禁止模型做正常、有边界的研究判断。

### 11.4 确定性 Validator 与 Semantic Verifier

确定性层检查：

- schema、digest、identity、as-of、period、unit；
- ref 是否存在、authority 是否允许；
- Candidate 未被伪装成 Evidence；
- calculation 可复算；
- claim lineage 无环；
- citation 属于本报告 manifest；
- public gap 是否有 eligibility；
- permission、budget 和 exact-once/idempotency。

语义层检查：

- source 是否真正蕴含命题；
- 原文摘要是否夸大；
- 因果措辞是否过度；
-跨公司、跨期间、跨口径是否误归因；
- 是否遗漏重要反证；
- confidence/uncertainty 是否合理；
- 正文是否有未登记 material assertion；
- Agent 之间是否存在冲突。

Verifier 生成 `VerifierFinding`，不直接改写原文。Finding 按最早责任层路由到原 Agent、S1/S2/tool owner、Harness 或 Human；修复生成新 revision，旧失败和旧文本保留。

## 12. 持久化、Redis、队列与恢复

### 12.1 唯一职责

| 组件 | 唯一职责 | 不得承担 |
|---|---|---|
| PostgreSQL | Session/Run/Event/Command/Notebook/Projection/Intervention/Outbox 的持久真值；独立 schema 存 LangGraph saver | 大文本对象、隐藏 CoT、Redis fan-out 状态 |
| Object/artifact store | 原始 source、model public output、report、diagnostic 的 immutable blob + digest + ACL | 运行状态机 |
| Redis | 可丢失的 wakeup/fan-out、cancel signal、短 TTL cache/rate limit；成熟队列 broker（若采用） | Evidence、Fact、Claim、SessionEvent、checkpoint 真值 |
| SQLite | 单机/单进程 local-lite qualification | production、HA、多 worker durability |
| LangGraph checkpointer | 执行快照、pending writes、interrupt/resume | FIN 领域事件和 Claim authority |

Redis Pub/Sub 是 at-most-once；断线后必须按数据库 event sequence replay。即使使用 Streams，也只作为分发，不成为第二份业务真相。

### 12.2 PostgreSQL 逻辑表

目标 schema 至少包括：

```text
research_sessions
research_runs
research_run_invocations
research_action_attempts
research_session_events
research_commands
research_plan_revisions
research_branch_notebooks
research_context_projections
research_domain_checkpoints
research_interventions
research_artifact_refs
research_dispatch_outbox
```

LangGraph saver 使用独立 schema/tables；业务代码不通过跨表 trigger 或内部 saver 表查询来推导 FIN 状态。

### 12.3 幂等与“恰好一次”表述

系统不承诺网络世界的端到端 exactly-once，而提供：

`at-least-once dispatch + FIN side-effect effectively-once`

规则：

- 写命令有 Idempotency-Key 和 request hash；同 key/同 hash 返回原 receipt，同 key/不同 hash 返回 409；
- provider/tool 调用前写 intent/request digest；ActionAttempt 的进行态为 `INTENT_COMMITTED / DISPATCHED / RECEIPTED`，不可变终态为 `APPLIED / FAILED_BEFORE_DISPATCH / AMBIGUOUS_AFTER_DISPATCH / REJECTED_BEFORE_DISPATCH`；明确收到的 provider/tool failure 先形成 failure receipt，再以 `APPLIED` 表示该失败已被领域图消费；`RECOVERY_REQUIRED` 只属于 ResearchRun 控制状态，不与 ActionAttempt 状态混用；
- `DISPATCHED` 后没有 durable receipt 时一律视为“可能已执行/计费”，不能声称未调用，也不得自动 retry；有权人工若批准重试，必须创建新 ActionAttempt 并展示潜在重复费用；
- receipt、canonical domain event 与 outbox 在一个 PostgreSQL 事务内提交；graph state 只引用稳定 receipt ref，重放时以 receipt ref 幂等 apply；
- LangGraph saver 与业务数据库不假装跨库原子提交：receipt 已提交但 checkpoint 未引用时重放同一 receipt；checkpoint 已推进但 public projection 未完成时从 canonical event 重建 projection；
- 每个 ActionAttempt 只有一个 terminal event；
- LangGraph interrupt 恢复会从节点开头重跑，因此 interrupt 前副作用必须幂等，最好把 interrupt 放在副作用前。

必须覆盖下列 kill-point matrix：intent 前；intent 后/send 前；send 后/response 前；response 后/receipt 前；receipt 后/checkpoint 前；checkpoint 后/public projection 前。send 后无法证明外部执行结果时，ActionAttempt 以 `AMBIGUOUS_AFTER_DISPATCH` 不可变收口，所属 ResearchRun 进入 `RECOVERY_REQUIRED`；不得把模型费用或外部 transport 宣称为 exactly-once。`effectively-once` 只描述 FIN 能用 request/receipt/ref 去重的领域写入。

reconciliation 不改写旧 ActionAttempt，而创建不可变 `RecoveryDisposition`，绑定 ambiguous ActionAttempt、当时的 RunInvocation、调查 receipts、潜在重复费用、决策 authority 和后续动作。若继续执行，必须创建新 RunInvocation；若重新调用外部能力，还要创建新 ActionAttempt。

### 12.4 Queue 决策

- `langgraph dev` 只用于零模型单机资格和快速开发，不是产品运行 fallback；
- Dell `local_parity` 固定采用 Agent Server 的 queue/thread/run/stream/cancel/interrupt；
- PostgreSQL 和 Redis 按官方 Agent Server 拓扑运行，FIN 不自行实现第二套 dispatcher 或 scheduler；
- 不引入 Celery、Temporal、自写 Redis Streams 或 Postgres `SKIP LOCKED` scheduler。

## 13. 后端 API、事件与 HITL

### 13.1 产品 API

新建产品域 API，不继续把 Agent 产品能力塞入 `/api/operations`：

```text
POST /api/v1/research-sessions
GET  /api/v1/research-sessions/{session_id}
POST /api/v1/research-sessions/{session_id}/runs
POST /api/v1/research-sessions/{session_id}/follow-ups
GET  /api/v1/research-runs/{run_id}
GET  /api/v1/research-runs/{run_id}/events?after_sequence=
GET  /api/v1/research-runs/{run_id}/events/stream
POST /api/v1/research-runs/{run_id}/commands
GET  /api/v1/research-runs/{run_id}/plan-revisions
GET  /api/v1/research-runs/{run_id}/branch-notebooks
GET  /api/v1/research-runs/{run_id}/checkpoints
GET  /api/v1/research-runs/{run_id}/artifacts/{artifact_id}
GET  /api/v1/research-runs/{run_id}/claims/{claim_id}/support
GET  /api/v1/research-runs/{run_id}/verifier-findings
```

### 13.2 ResearchRun 状态机

```text
DRAFT → QUEUED → RUNNING
RUNNING → PAUSE_REQUESTED → PAUSED
RUNNING → AWAITING_HUMAN
PAUSED/AWAITING_HUMAN → RESUME_REQUESTED → RUNNING
RUNNING → VERIFYING → NEEDS_REPAIR → RUNNING
VERIFYING → AWAITING_FINAL_APPROVAL → REJECTED
AWAITING_FINAL_APPROVAL → APPROVED_FOR_PUBLICATION → PUBLISHING → COMPLETED
PUBLISHING → RECOVERY_REQUIRED
RECOVERY_REQUIRED → AWAITING_RECOVERY_DECISION
AWAITING_RECOVERY_DECISION → RESUME_REQUESTED → RUNNING
AWAITING_RECOVERY_DECISION → FAILED
{DRAFT, QUEUED, RUNNING, PAUSE_REQUESTED, PAUSED, AWAITING_HUMAN, VERIFYING, NEEDS_REPAIR, AWAITING_FINAL_APPROVAL} → CANCEL_REQUESTED → CANCELLED
execution state → FAILED | RECOVERY_REQUIRED
```

禁止存在 `AWAITING_FINAL_APPROVAL → COMPLETED` 的直接边；最终批准只进入 `APPROVED_FOR_PUBLICATION`，artifact 实际写入并保存 publication receipt 后才进入 `COMPLETED`。拒绝直接进入 `REJECTED`。

`APPROVED_FOR_PUBLICATION` 仅在 publication intent 尚未 durable commit 时允许通过专用 `revoke_publication_approval` 回到 `AWAITING_FINAL_APPROVAL`。intent 一旦 commit，`PUBLISHING` 不可 generic cancel；只能完成或进入 recovery reconciliation。若外部系统支持撤回，撤回是新的显式 ActionAttempt/receipt，绝不能用 cancel 假装自动回滚。任何已经产生外部 artifact 的 Run 不得无说明地终结为 `CANCELLED`。

前端必须区分“命令已接收”“等待安全暂停”“已经暂停”。暂停/取消不强杀正在进行的 provider call；在 node/tool safe boundary 收敛。operator emergency hard kill 后必须进入 recovery-required。

### 13.3 Command envelope

```json
{
  "command_id": "uuid",
  "type": "request_pause",
  "expected_run_version": 17,
  "expected_checkpoint_digest": "sha256:...",
  "expected_plan_revision": 3,
  "expected_action_digest": null,
  "expected_artifact_digest": null,
  "expected_claim_manifest_digest": null,
  "required_authority_class": "case_research_controller",
  "independence_requirement": "none",
  "authorization_basis_ref": "policy://...",
  "policy_snapshot_digest": "sha256:...",
  "model_node_authority_matrix_digest": "sha256:...",
  "target_refs": ["plan://...#Q5"],
  "reason": "先补供应链反证",
  "client_observed_at": "RFC3339"
}
```

实际 API 使用按 `type` 判别的 command union，而不是共享一个无约束 `payload`：计划修改、工具/action 审批、资料上传、repair、final approval 各自有合法字段。相关命令必须携带相应 exact digest；不适用字段必须为 null/不可出现。actor/tenant/role 和其 authority classes 从服务端已认证 session、OwnerDecision 与 policy snapshot 派生，客户端不能自报。

首批 command：

- request pause/resume/cancel；
- approve/reject exact action；
- submit clarification；
- submit plan instruction；
- attach source；
- request repair；
- approve/reject final artifact。

命令返回 receipt，不直接声称状态已完成。计划修改必须经过 `PlanDelta` validator；前端不能 PATCH LangGraph state 或发送任意 `Command(update/goto)`。

旧浏览器 tab、同 artifact ID 但 digest 已变化、同 checkpoint 但 plan revision 已变化、同 tool ref 但 action digest 已变化的审批全部返回 stale/409，不执行副作用。发布写入成功但 receipt 未确认时进入 `RECOVERY_REQUIRED`，由 publication idempotency/reconciliation 处理，不能提前标记 completed。

### 13.4 SessionEvent 与公共 RunEvent

Canonical SessionEvent 是审计真相；现有 `RunLogEvent(stream/message)` 只保留为运维日志。公共事件从 canonical event 做权限和脱敏 projection，至少含：

- run/plan/node status；
- disclosure requested/resolved；
- tool requested/started/completed/failed/rejected；
- candidate/evidence admission；
- decision artifact；
- feedback/finding routed/closed；
- checkpoint；
- intervention/command；
- artifact published；
- terminal state。

大正文和原始 model/tool payload 不进 SSE，只放 artifact ref、digest 和最小摘要。

### 13.5 SSE

```text
id: 281
event: run.event
data: {"projection_sequence":281,"source_session_sequence":412,"source_event_id":"evt_...","source_event_digest":"sha256:...","event_type":"tool.execution.completed",...}
```

- snapshot-first；
- 支持 `Last-Event-ID`；
- 网络传输允许 replay/live handoff 重复投递；客户端 canonical projection 按 `projection_sequence` 去重，最终必须无遗漏、无乱序终态，任何 gap 必须显式报警/重取 snapshot；
- DB replay 为真，Redis 仅 wakeup；
- cursor 同时绑定 projection policy 与 authorization-view digest；权限、redaction 或 event projection policy 变化时服务端拒绝旧 cursor并要求 snapshot recovery；
- heartbeat 用 `: ping` comment，不进入 canonical ledger；
- `Cache-Control: no-cache, no-transform`；
- 慢客户端、单事件大小和连接数有上限。

### 13.6 HITL

人工可以：

- 审批高风险/高成本工具；
- 暂停、恢复、取消；
- 回答 Agent 的澄清问题；
- 给计划补充约束；
- 上传或指定新 source；
- 要求某个 claim/branch repair；
- 审核 Evidence admission；
-批准/拒绝最终交付。

每个动作绑定 exact run version、checkpoint digest、plan revision、artifact/claim/tool refs 和 actor。上传只创建 SourceCandidate，经解析/权限/Evidence admission 后才进入上下文。

HITL authorization 不等于“登录用户可以点所有按钮”。v1.2 固定以下 authority classes：

| 动作 | required authority | independence |
|---|---|---|
| pause/resume/cancel/clarification/plan constraint | `case_research_controller` | none |
| Evidence admission/rejection | `qualified_evidence_reviewer` | 不得是产生该 Candidate 的 Agent；人类 reviewer 资格有独立 receipt |
| disputed/bounded-gap acceptance | `boundary_acceptance_reviewer` | 独立于原研究 Agent |
| already-authorized high-cost/high-risk action | `cost_action_approver` 或工具专用 authority | 必须匹配 exact action digest |
| final deliverable approval | `final_deliverable_approver` | 满足最终 rubric 的独立 reviewer |
| publication | `publication_approver` | 匹配 exact artifact/claim manifest digest |
| emergency hard kill/reconciliation | `operator_emergency` | 不能反向授予研究或付费 authority |

`approve_exact_action` 只能放行一个已经由 sealed RuntimePolicySnapshot、`ModelNodeAuthorityMatrix(status=authorized)` 和 matching OwnerDecision 预先授权的 action。普通 HITL command 永远不能创建、修改或提升 model/provider/paid-call authority，也不能改 policy/matrix/OwnerDecision。新的 paid ResearchRun/RunInvocation authority 只能由独立、不可变的 `PaidExecutionOwnerDecision` 在运行前授予；每次 ActionAttempt 仍要落在该 decision 的 node、budget、模型和停止范围内。authority decision 本身有 digest/receipt，不以 actor/role 字符串代替。

## 14. 前端产品面

### 14.1 页面归属

新页面：

`/workspace/cases/:caseId/runs/:runId`

`/operations` 继续负责配置、数据构建、eval 和基础设施作业；研究 case、Agent、证据、HITL 和交付留在 Workspace。

### 14.2 首批页面结构

1. `RunHeader`：状态、case/as-of、plan revision、checkpoint、时延/tokens/calls、Pause/Resume/Stop、stream health。
2. `AgentPlanList`：任务、owner Agent、依赖、coverage、状态、最近 evidence/gap/finding、revision diff。首批先做列表，不急着画图。
3. `WorkpaperPanel`：当前工作纸/报告 revision，claim-level 高亮。
4. `ProofInspector`：Evidence、Numeric、Calculation、Claims、Verifier、Context、Capability/Skill disclosure。
5. `ActivityTimeline`：谁做了什么、输入 refs、结果、validator、下一步、修复 owner。
6. `HumanInterventionDrawer`：系统请求和人工主动干预，提交前展示影响、stale 范围、预计新增调用和需重验内容。
7. `FollowUpComposer`：解释、重查、加证据、改假设、修订交付物；创建 child run。

### 14.3 “思维链”展示规则

UI 名称使用“研究路径”“决策摘要”“证据与修复链”，不宣称展示模型隐藏思维链。

可以展示的 `DecisionArtifact`：

- 当前 goal/task；
- 实际 observation/evidence/fact refs；
- chosen action 和简短 rationale；
- 被拒绝的主要替代路径及原因码；
- uncertainty/confidence；
- next action；
- validator/verifier receipt。

禁止进入公共数据库、SSE、DOM 或导出的内容：

- provider private reasoning/reasoning_content；
- 原始隐藏 prompt；
- secret/DSN/token；
- operator-only raw capture；
- 未脱敏 tool/model payload。

Verifier 能看到审计制品和 restricted refs 的授权投影，但仍不依赖隐藏 CoT。

`ModelRuntimePort` 必须复用并强化现有 transient reasoning continuity：隐藏 reasoning 只允许在同一次 provider ActionAttempt 的易失内存中，为满足 provider tool-loop 协议而瞬时回传给原 provider；它不进入 PostgreSQL、artifact、diagnostic、trace、SSE、DOM、export，也不通过 restricted ref 暴露给 Verifier。

持久化前统一执行 allowlist `sanitize_provider_envelope()`：只保留 call ID、finish reason、usage、公开 assistant/tool output、经 secret scrub 的 tool-call arguments、error code 和 digest；递归拒绝 `reasoning_content / reasoning / thinking / analysis` 及大小写、嵌套、编码变体，也拒绝原始 prompt、credential 和 secret fields。旧 `_audit_value(raw_response)` 不得越过这个 port 写入新纵切 artifact。

checkpoint 只能位于可由公开 assistant/tool messages、BranchNotebook 和 receipts 重建的安全边界。若进程在依赖私有 reasoning continuity 的 in-flight loop 中崩溃，旧 ActionAttempt 以 `AMBIGUOUS_AFTER_DISPATCH` 不可变收口；从 Notebook 创建新 ActionAttempt，不声称精确恢复旧私有 reasoning state，也不自动重发可能已经计费的调用。

### 14.4 成熟前端依赖

- `@tanstack/react-query`：server snapshot 和 command receipt；
- 自有很薄的 `useRunEventStream`：SSE sequence/reconnect/dedupe；
- `@tanstack/react-virtual`：长 timeline；
- Radix primitives：Dialog/AlertDialog/Tabs/Tooltip 的可访问性；
- `@xyflow/react`：仅在真实 DAG 复杂度出现后再引入。

首批不引入 Redux、XState、WebSocket 或完整新设计系统。

## 15. 运行后交互

终态 run 不可修改。用户追问创建 child turn/run，模式为：

- `explain`：解释现有 claim/decision，不改变 as-of；
- `recheck_current`：以当前外部时间重新检索；
- `add_evidence`：新增 Candidate → admission → repair；
- `change_assumption`：创建 scenario branch；
- `revise_deliverable`：在原 artifact/claim manifest 上形成新 revision。

Child run 保存 parent run、artifact refs、manifest digest、as-of policy、差异和 approval 失效规则。旧报告和旧审批不被覆盖。

## 16. 安全、权限与不可信输入

- case、tenant、role 和 artifact 权限由服务端得出；开发期浏览器 header 不得成为产品授权事实；
- 所有 snapshot、stream、artifact、command 做 exact-resource 权限检查；
- tool/web/model/upload 内容均为不可信 data，不得把其中的指令转成 runtime command；
- Markdown 禁止 raw HTML并做 sanitize；
- persistence 前做一次 redaction，公共 event/SSE projection 前再做 allowlist；
- sensitive command 使用 CSRF/Origin、真实 session、二次确认；
-高成本、外部写操作和 final publish 明确 HITL；
- Skill 的 tool allowance 只是建议，不是权限；
- OTel 只存 IDs、digests、tokens、cost、latency、status，不存 prompt、原文、secret 或 CoT。

安全门必须包含四类 adversarial fixture：external page、MCP `structuredContent/_meta`、uploaded source、Skill/reference。即使内容要求“忽略规则、提升权限、改 PlanDelta、晋升 Evidence、宣布 gap 或发布”，也只能作为 data；它不能改变 sealed `RuntimeScope`、`AvailableActionMenu`、tool permission、PlanDelta authority、Evidence admission、GapEligibility 或 publish command。拒绝形成 typed security receipt，不自动 retry/escalate。

## 17. 部署 profile

### 17.1 `local_lite`

- Windows native FastAPI + React；
- `langgraph dev` 或纯 LangGraph fixture；
- in-memory/SQLite 仅保存零模型测试材料；
- filesystem artifact store；
- 无 Redis；
- 用于零模型开发、HITL/UI/replay qualification；
- 不是 Dell 产品运行 fallback，不声称进程重启后 completed-stream replay、HA、多 worker 部署或生产能力。

### 17.2 `local_parity`（Dell 最终演示前必须通过）

- checked-in、digest-pinned Agent Server 本地 Compose 拓扑；
- Agent Server API/worker + PostgreSQL + Redis；
- PostgreSQL 16：Agent Server 持久化 + 独立 FIN 产品控制面 schema，FIN 不读取 server 内部表；
- filesystem 或 S3-compatible local object store；
- FastAPI 薄 BFF，不自建 Agent worker/queue；
- OpenTelemetry Collector；
- Redis 作为 Agent Server 的瞬时运行依赖，不作为 FIN 领域真值；
- 做进程/容器重启、checkpoint、SSE replay、HITL 和 idempotency failure injection。

### 17.3 `production`（本轮不宣称完成）

Dell vertical 已采用 Agent Server，但本轮只声明个人作品集/本地开发演示，不声明商业或生产部署资格。“非商用”不等于免除 key/license；若未来转为长期公网、真实用户或生产服务，必须重新完成许可、egress、数据驻留和运维评审。PostgreSQL HA/TLS/PITR、Redis HA、object store、OIDC、Kubernetes 和生产多 worker 属于后续生产门，不阻止 Dell `local_parity` 证明。

## 18. Token、调用数、时延与停止条件

### 18.1 原则

- 13 次是旧固定拓扑计数，不再是质量 KPI 或硬目标；
- 每个 model node/paid authority 都必须有 task-specific `TokenBudgetBasis`；
- budget 基于输入材料、输出需要、schema 负担、材料性、相似运行、reasoning profile 和 stop 行为；
- 成本和时延是二级约束，不能静默删除研究工作；
- emergency ceiling 只防循环，达到时进入 HITL，不输出伪“完成”。

Wave 0A 同时冻结 `ModelNodeAuthorityMatrix`，但它本身不授权调用。Lead、Specialist、Counter、Semantic Research Verifier、Writer、Final Semantic Verifier 以及任何 model-assisted repair node 必须逐项登记：node purpose、input scale、required outputs、schema burden、materiality/quality risk、comparable-run evidence、reasoning profile、stop/truncation behavior、repair/no-retry policy 和当前 authority。没有有效 matrix entry，或 entry 仍为 `not_authorized`，必须在 transport 前失败。当前所有条目均为 `not_authorized`，直到 Owner 对新 PaidFullChainExecution/ResearchRun 的 `PaidExecutionOwnerDecision` 明确授权，并逐 node 更新 matrix。

### 18.2 记录项

每个 Agent/Run 至少记录：

- model/tool call count；
- input/output/cached/reasoning tokens（provider 可见范围内）；
- wall-clock、queue wait、tool latency；
- context projection token estimate；
- disclosure/Skill token；
- accepted/rejected claims；
- retrieval/candidate/evidence counts；
- verifier findings 和 repair rounds；
- HITL wait time；
- cost estimate和未知费用边界。

### 18.3 停止

`stop_sufficient` 需要 material obligations、claims、counterevidence 和 verifier closeout；`budget exhausted`、tool failure、unsearched route、empty result 都不能改名为完成或 public gap。连续无信息增益进入 PlanDelta/alternative/HITL。

## 19. 迁移矩阵

| 当前模块/能力 | 决策 | 迁移动作 |
|---|---|---|
| `dell_reference_vertical_graph.py` | `REGRESSION_BASELINE` | 冻结 A02 路径，不继续堆补丁；新 agentic graph 并行建立 |
| `deepseek_structured_agents.py` | `WRAP/SHRINK` | Provider adapter 留在 `ModelRuntimePort`；一次性 Planner/Specialist schema 逐步退出 |
| `dell_reference_vertical_mcp_tools.py` | `RETAIN/ADAPT` | 保留 transport/domain ports；新增 trusted scope injection、typed error preservation |
| `research_foundation/mcp_server.py` | `RETAIN/EXTEND` | 保留同一 server；增加 resources/templates 和更小 agent-facing tool views |
| `planner_tool_capabilities.py` | `REPLACE_PROJECTION` | 由 CapabilityInventorySnapshot + SourceFamilyCompiler 取代只暴露抽象能力的投影 |
| `canonical_runtime/session.py` | `RETAIN/CONNECT` | 复用 artifacts/digest invariants，接持久 repository；不再只校验内存 Sequence |
| Workbench SQLite store | `LOCAL_LITE_ONLY` | 继续 ops/local；新 research domain store 单独实现，最终 parity 到 PostgreSQL |
| Operations SSE | `PATTERN_ONLY` | 不直接当产品事件；新 SSE 支持 `id`、Last-Event-ID、typed event、async replay |
| React ResearchWorkspace | `RETAIN/EXTEND` | 保留证据/检索视觉与 API；增加 run deep-link、timeline、proof、HITL |
| R3–R14/versioned parser chain | `HISTORICAL_REGRESSION` | 不再作为新 agentic runtime 的主动实现链 |
| RoleMethodPack | `RETAIN_AS_SKILL_SOURCE` | 转入版本化 metadata + progressive load，不全量注入 |

旧实现只有在新路径通过同一 Dell frozen inputs、真实 case、恢复/HITL 和质量验收后才可退役；不得先删后证明。

## 20. 实施波次与具体文件面

### Wave 0A：详设、ADR 与零模型领域合同（本轮立即开始）

目标：把五项修正、披露、事件、上下文、HITL 和部署边界变成可执行合同。

首批文件建议：

```text
configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_2.json
src/sec_agent/canonical_runtime/contracts_v1_2.py
src/sec_agent/agent_runtime/dell_agentic_contracts.py
src/sec_agent/agent_runtime/progressive_disclosure.py
tests/test_agent_runtime_v1_2_contracts.py
tests/test_dell_agentic_contracts.py
tests/test_dell_progressive_disclosure.py
```

首批只做：

- canonical v1.2 的 AgentSession/ResearchRun/RunInvocation/ActionAttempt/Event identity、v1.0/v1.1 adapter 与 session→run event projection mapping；
- `AgenticPlanDeltaV1_2 / ContextCheckpointV1_2`，required refs 自动派生，不复制一套无关联 runtime ledger；
- `CoverageObligation / MinimumRouteObligation / BaselineSourcePlan / ResearchTaskSpec / ResearchPlan`；
- `CapabilityDescriptor / DisclosureRequest / DisclosureReceipt / AvailableNextAction`；
- sealed `RuntimeScope` 与 provider-visible intent 分离；
- accepted-plan 派生的 `RuntimeScopeAuthorizationRecord`，显式绑定 objective/plan/graph/task assignment；
- `ModelVisibleContextManifest / DecisionArtifact / ToolFailureReceipt / GapEligibilityReceipt`；manifest 无 grant 时也绑定 disclosure policy；
- `RuntimePolicySnapshot / ModelNodeAuthorityMatrix` 与 provider envelope allowlist sanitizer；
- schema/digest/stale catalog/public-gap/authority/compatibility/CoT 的确定性验证。

不接模型、不接网络、不接 Redis、不创建 A03。

### Wave 0B：LangSmith/Agent Server 采用资格测试

目标：在写 Research Run BFF、领域投影和前端前，验证已经选定的 LangSmith/LangGraph Agent Server serving 路径，避免复制成熟 runtime。

- 先用 `langgraph dev`、fake graph 和 zero-model fixture 验证 API 与运行语义，再用 checked-in、digest-pinned Agent Server Compose 验证 PostgreSQL/Redis 部署态；
- 精确记录 package/image/version/license、LangSmith key/egress 要求、PostgreSQL/Redis 拓扑、thread/run/cancel/interrupt/resume/SSE 行为、资源占用和数据驻留；
- 验证 FIN `SessionEvent / Claim / Evidence / Intervention` 能否只做薄投影，而不修改或复制 Agent Server 内部状态机；
- 输出 FIN identity 与 server thread/run/assistant/cron/task 的 cardinality map、ID binding 和恢复映射，禁止因为两边都叫 run 就默认等价；
- 冻结唯一 ADR：`ADOPT_LANGSMITH_AGENT_SERVER_FOR_DELL_DEV_LOCAL_PARITY`；不再保留 OSS single-worker runtime fallback；
- 原生 resumable stream 只订阅单一 `updates`，完整状态走 `GET /threads/{thread_id}/state`；FIN BFF 的公开事件使用自己的 projection sequence，不把多 `stream_mode` frame 当领域事件协议；
- 裁决前禁止实现新的 dispatch queue、research-run persistence、product SSE replay 或通用恢复服务；现有 Operations 代码只作为事实源和回归基线，不继续扩写。

若 checked-in Agent Server Compose 因合法 key/license/egress 未配置而无法执行，应记录为部署验收 blocker 并等待合法配置；不得因此切换到自研 runtime。整个 Wave 0B 不调用模型，不创建付费 ResearchRun 或 PaidFullChainExecution。`langgraph dev` 在线通过不等于 `local_parity`、managed deployment 或 production 通过；fresh r7 的 bounded local control-plane pass 也不等于真实 graph/run/checkpoint/SSE 或产品通过。

### Wave 1：RC-S3-105 与数据披露

- 从 1,025 nodes、61 Evidence、S2、r12 生成 immutable capability/inventory snapshot；
- 从现有九分支 source plan 生成 answer-free `BaselineSourcePlan / MinimumRouteObligation`；
-实现 SourceFamilyCompiler；
- local/reviewed/external provider tool schema 拆分；
- MCP resources/templates；
- 重放 A02 payload，错误变 typed feedback 而非 host crash；
- `registered=9/9`、`plan_reachable=9/9`；所有 accepted local intent 同时满足 nonzero、cardinality、issuer/period/role/route/authority 正负约束，required minimum route 未被删除。

### Wave 2：单 Specialist agentic loop

- 一个 generic Specialist 使用真实 S1/S2 tools；
-多轮 observe/action/tool/feedback；
- BranchNotebook、ContextProjection、compaction；
- NarrativeArtifact + ClaimLedger；
- fake provider 和 deterministic fixtures 先通过；
- 本 Wave 只允许 fake provider 与保存响应重放；任何 DeepSeek、其他 provider、托管模型或付费 shadow 均不属于自动实施权限。

即使单 Specialist 的零模型门通过，真实 provider shadow 也必须另有 `PaidExecutionOwnerDecision`、clean pushed commit、专用 ResearchRun/RunInvocation/ActionAttempt IDs、task-specific `TokenBudgetBasis`、调用范围和停止条件；不得把它解释成“不是 full A03 所以可以先调用”。

### Wave 3：动态 Lead / Multi-Agent / Counter / Verifier

- `Send` 动态 fan-out；
- Lead PlanDelta；
- Counter 定向 reroute；
- Validator/Semantic Verifier 两层；
- finding 路由到原 owner；
-旧失败不覆盖，repair 新 revision。

### Wave 4：按 Wave 0B 裁决实现 Backend、SSE 与 HITL

- 复用 Agent Server 的 thread/run/queue/stream/cancel/interrupt，FIN 只实现 Research Session/Event/Command 的领域投影、权限与薄 BFF；
- typed FIN event projection 使用自己的单调 sequence 和 snapshot-first 恢复；它只投影业务语义，不复制 Agent Server 运行状态机；
- 仓库中只能有一个活动执行真值，不实现 SQLite/FastAPI runner fallback；
- pause/resume/cancel/final review；
- Workbench run page、timeline、proof inspector、intervention drawer；
- private reasoning zero-leak tests。

### Wave 5：PostgreSQL local-parity 与部署证明

- checked-in、digest-pinned Compose 的 Agent Server + PostgreSQL + Redis，以及独立 FIN product schema；
- restart/failure injection、idempotency、SSE replay；
- 执行 Wave 0B 已冻结的 Agent Server serving 路径，不在本阶段重新选型；
- Redis 作为 server 瞬时依赖做丢失/重连测试，不成为 FIN replay 真值；
- OTel trace、token/cost/latency dashboard；
- Docker Compose 可复现运行。

### Wave 6：真实 Dell full-chain

- 先关闭 RC-S3-105 和所有零模型/独立审查门；
- 新 `PaidExecutionOwnerDecision` 创建全新 immutable PaidFullChainExecution、ResearchRun 和首个 RunInvocation，绝不复用 A02；
-真实 DeepSeek 工具循环；
-到 HITL 停止，人工检查事实、机制、反证、可读性、成本和时延；
-修复后再生成最终演示报告；
-形成简历可写、可现场演示、可复盘的真实工程证据。

## 21. 验收矩阵

### 21.1 Zero-model 合同门

- canonical v1.2 对 v1.0/v1.1 有证据约束的 adapter：通用 v1.0 只投影 session envelope；A02 exact bundle 分开映射付费执行标签、ResearchRun、RunInvocation 和 Planner ActionAttempt，历史时间与导入时间分离；A01 缺 exact bundle 时 fail closed；v1.1 event 只能绑定已校验身份对象；全链不得被压成单个 ActionAttempt；
- provider-visible schema 的 local/external 非法字段组合不可表达；
- MCP/provider/host 三层映射来自同一 canonical source；
- stale catalog/snapshot/digest fail closed；
- A02 payload 重放不 crash；
- Q1–Q9 `registered=9/9`、`plan_reachable=9/9`，零模型结果不冒充 evidence covered；
- accepted local intent 同时满足 eligible object、cardinality ceiling、issuer/period/source-role/route/branch/authority 正负约束；全库 selector、忽略 period、错误 alias 和 lane 串接 fail；
- Reviewed Evidence intent 与 local scope 分离；local route 非空不抑制已有 Reviewed Evidence；
- required `MinimumRouteObligation` 不能被 PlanDelta 静默删除；
- empty/scope exhausted/tool failure 永不获得 public-gap authority；GapEligibility 缺任一 required proof receipt 即 fail；
- CalculationClaim 可复算；
-不存在的 claim/evidence/fact/anchor 被拒绝；
- raw CoT/secret 在 DB、artifact、diagnostic、trace、SSE、DOM、export 全部为零；
- adversarial page/MCP/upload/Skill 内容不能提升 authority 或生成 runtime command；
- 无有效 `ModelNodeAuthorityMatrix` 或状态为 `not_authorized` 的 model action 在 transport 前失败。

### 21.2 Runtime/HITL 门

- 动态 task 数、依赖和并行调度正确；
- 成对 fixture 只改变一个 observation 时，Lead 能产生不同 add/cancel/reprioritize delta；`Send` 来自 accepted plan，不来自 Q1–Q9 常量；
- 并行 Notebook 隔离，聚合顺序变化不改变 canonical digest；Counter finding 必须形成可观察 Plan/Claim/Evidence delta，或提交 source-bound `no_material_finding`；
- Specialist 可在同一 task 内多轮 tool/disclosure/Skill；
-进程重启后从官方 checkpoint 恢复；
-漏 Claim/minimum obligation/open finding/intervention/authority/budget/stop state 的 resume 或 compaction fail closed；
- kill-point matrix 每个位置均得到唯一合法的 immutable ActionAttempt outcome、ResearchRun recovery state 和 RecoveryDisposition；旧 ambiguous attempt 不被改写；
- interrupt 前 FIN 副作用不重复；provider `DISPATCHED` 无 receipt 不自动重试，也不宣称 exactly-once；
-同 Idempotency-Key 不重复可控 FIN external side effect；
- stale command/version 返回 409；
- stale plan/action/artifact/claim digest 的 HITL 返回 409；publication receipt 前不进入 COMPLETED；
- actor 仅登录但缺 required authority class、independence receipt 或 authorization basis 时命令被拒；普通 HITL 无法把 `not_authorized` model node 改为 authorized；
- publication intent commit 后 generic cancel 被拒；外部已写入但 receipt 不确定时进入 recovery，而非 CANCELLED；
- pause 只在 safe boundary 完成；
- cancel 后不再启动新 model/tool call；
- compaction mutation 若丢 material refs 即 fail；
- Verifier finding 能到原 owner 并以新 revision close。
- Writer 改强因果、删除 WWC、串公司/期间、引入未登记数字或把 Candidate 写成 Evidence 时，final deterministic/semantic verifier 必须拒绝。
- final finding 修复后必须生成新 artifact/claim revisions，重跑两层 final verifier 并取得 fresh HITL；旧 approval/digests 全部 stale。

### 21.3 SSE/UI 门

- 传输允许重复；`Last-Event-ID` 重连后的 canonical client projection 去重后无遗漏、无未报警 gap、终态一致；
- replay/live 同 sequence、frame 中断、过旧 cursor、Redis wakeup 丢失和 slow-client 均有恢复测试；
- projection policy 或 authorization view digest 变化时旧 cursor 被拒并重取授权 snapshot，不能继续同一增量视图；
- snapshot、stream、artifact、command 权限一致；
- UI 区分 accepted command / pausing / paused；
- A02 可作为真实失败链展示，但不显示为运行成功；
- private reasoning fixture 在 DB public projection、SSE、DOM、export 中为零；
-人工动作绑定 exact checkpoint/plan/artifact digest；
-终态 run 不可变，follow-up 创建 child run。

### 21.4 最终 Dell 产品门

- accepted plan 判为 required 的 capability 必须有消费 receipt；未使用 capability 有可审计 non-use reason，不做 ceremonial tool call；
- 所有 high-materiality claim 100% 通过 authority、locator、period/unit 和 semantic support；任何 unsupported high-materiality claim 都是 hard fail；
- 其余 factual material assertions 100% 进入 ClaimLedger，未通过者必须删除、修复或降为显式 Hypothesis/Boundary，不用低风险 claim 稀释；
-低权威指标和推断有邻近提示；
- Counter 和 Verifier 有真实输入、receipt 和可观察 delta/no-material disposition，不是角色名称；
-报告先回答商业问题，再说明边界；
- 独立 human rubric 对事实正确性、商业回答、反证、可读性、可追溯性、交互恢复六项按 0–4 评分，每项至少 3；串公司/期间、伪造 Evidence、隐藏重大失败或无法定位关键 claim 为 hard fail；
- 未关闭 P0/P1 finding 为 0；P2 必须不涉及 high-materiality factual correctness，并在演示边界中披露；
-时延、tokens、调用数、成本、failure/recovery 均有真实记录；
-不是通过隐藏错误、弱化 validator 或减少研究范围获得 PASS。

## 22. Gate、停止条件与待决项

### 22.1 当前允许

- 本文档、ADR、Project OS 和工作日志更新；
- 零模型 Pydantic 合同、progressive disclosure、SourceFamilyCompiler、fake runtime、SSE/HITL fixture；
-本地/隔离环境的成熟组件 qualification；
-不含 provider 的 deterministic tests 和独立审查。

### 22.2 当前禁止

- A02 retry/resume；
-创建或启动 A03；
-任何 DeepSeek、其他 provider、托管模型或付费 shadow/full-chain；只有 Owner 通过新 `PaidExecutionOwnerDecision` 对 exact PaidFullChainExecution/ResearchRun/node scope 明确授权后才可改变；
-把新代码称为 Dell 已跑通；
-把 Candidate 自动晋升 Evidence；
-把 local-lite 称为 production；
-为了前端效果伪造 Agent 运行；
-提前删除旧 graph、A02 artifacts 或历史失败。

### 22.3 已决方向与剩余资格门

| 事项 | 当前决定 | 剩余资格门/触发 |
|---|---|---|
| Agent Server 是否采用 | 已决：Dell 个人本地演示采用，不设 runtime fallback | fresh r7 零模型本地控制面 bounded qualification 已通过并仍是 current；r8 已编码 live FIN final binding、固定 Q1 零模型 graph/checkpoint/restart/SSE/LangSmith exact trace 候选，但 fresh live result 尚不存在，共享/production 鉴权仍待 |
| Redis 是否启用 | 已决：仅作为 Agent Server 部署依赖 | r7 空 thread 的 idle restart/readback 已通过；r8 只准备验证真实图在 Redis 进程重启后的 readback，不把该观察写成 Redis 持久真值；Redis loss/replacement recovery 仍不在本轮 |
| React Flow | 当前关闭 | 真实 DAG 列表已无法解释 |
| Provider adapter 切官方 SDK | 当前不切 | tool-loop/reasoning/usage parity |
| Specialist 永久 child thread | 当前不建 | 跨 turn 独立并发/长期记忆实证 |
| 首个付费 successor | 当前不存在 | 新 `PaidExecutionOwnerDecision` + task-specific `TokenBudgetBasis` + clean pushed commit；r8 即使通过也不关闭 durable pending/orphan/reconciled lifecycle、unknown-outcome 自动重试或 exactly-once。旧 paid-entry 门是否保留须由 Owner 在 r8 结果后明确裁决，不能由实现者静默放宽；RC-S3-105 只在零模型 data-composition scope 关闭，不自动授予 paid authority |

## 23. 本设计如何避免再次“埋头一天但真正工作没开始”

1. 本文冻结的是少量关键边界，不再为每次只读动作写一份新治理协议。
2. 设计完成后第一批立即落 Pydantic 合同和 progressive disclosure 代码，并用测试证明，而不是继续扩写 Phase 文档。
3. 每个 Wave 必须产出可运行代码、可复算测试或可见产品能力；只有文字没有实现不算完成。
4. 成熟组件优先：MCP、LangGraph、Pydantic、PostgreSQL、FastAPI、React、SSE、OTel；FIN 只写金融权威和薄适配。
5. 遇到不确定技术栈先做小 qualification spike，结果不佳就停，不把候选接进正式依赖。
6. 每次汇报必须同时说清“文档到哪、代码到哪、数据到哪、真实模型到哪、产品 UI 到哪”。

## 24. 官方与仓库依据

官方资料：

- [MCP Tools 规范](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP Resources 规范](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)
- [MCP Elicitation 规范](https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangChain Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangGraph Standalone Agent Server](https://docs.langchain.com/langsmith/deploy-standalone-server)
- [LangGraph CLI `dev` / `up`](https://docs.langchain.com/langsmith/cli)
- [LangSmith account and API key](https://docs.langchain.com/langsmith/create-account-api-key)
- [LangSmith platform setup](https://docs.langchain.com/langsmith/platform-setup)
- [Agent Server storage and privacy](https://docs.langchain.com/langsmith/data-storage-and-privacy)
- [Agent Server streaming](https://docs.langchain.com/langsmith/streaming)
- [Redis Pub/Sub delivery semantics](https://redis.io/docs/latest/develop/pubsub/)
- [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/)
- [WHATWG Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)

仓库事实源：

- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/senior_assistant_collaboration_policy.zh-CN.md`
- `docs/project_os/mature_stack_first_and_complexity_budget_policy.zh-CN.md`
- `docs/worklog/fin_0_1_3_s3/175_dell_reference_vertical_data_runtime_foundation_and_live_gate.md`
- `docs/worklog/fin_0_1_3_s3/176_dell_reference_vertical_external_source_reachability_gate.md`
- `docs/worklog/fin_0_1_3_s3/178_dell_reference_vertical_A02_immutable_planner_contract_failure.md`
- `configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_0.json`
- `configs/research/fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_1.json`
- `src/sec_agent/agent_runtime/dell_reference_vertical_graph.py`
- `src/sec_agent/agent_runtime/dell_reference_vertical_mcp_tools.py`
- `src/sec_agent/research_foundation/mcp_server.py`
- `src/sec_agent/canonical_runtime/session.py`
- `src/sec_agent/workbench/store.py`
- `apps/workbench/backend/api/operations.py`
- `apps/workbench/frontend/vite/src/app/ResearchWorkspace.tsx`

## 25. Freeze 声明

本文冻结以下设计方向：稳定外层图 + agentic 内层 loop；动态计划作为数据；MCP/Runtime/模型三层契约；可信 scope 注入；SourceFamilyCompiler；L0–L4 渐进披露；自由 Markdown + ClaimLedger；两层 verifier；隐藏 CoT 不持久化、不向产品/审查面或其他接收方传输、不展示，仅在同一 provider ActionAttempt 内为协议连续性瞬时回传原 provider；PostgreSQL 持久真值、Redis 瞬时辅助；SSE + REST command；终态 child-run follow-up；A03 必须另行授权。

2026-09-03 作者分离的三轮只读反证审查已经收口。审查先后发现并关闭：Agent Server 资格测试顺序和 provider shadow 授权漏洞；canonical v1.2 identity/sequence/Plan/Checkpoint 兼容；SourceFamily 过窄/过宽与 Reviewed Evidence precedence；Writer 后最终语义复核；provider/tool crash 双写裂缝；HITL authority 与 publication 竞态；GapEligibility、CoT allowlist、prompt injection、SSE projection 和 A03 phantom identity。该次结论 `PASS / P0=0 / P1=0` 只针对设计冻结。

随后 Wave 0A 实施证据继续修正了设计假设：RuntimePolicy 与 disclosure policy 必须使用不同 digest 并显式交叉绑定；runtime policy 的摘要绑定仍不够，其内部 case/version/as-of/data/catalog/disclosure-policy/allowlist 还必须与 current scope/catalog/policy 逐字段对齐；PlanDelta/Gap 校验必须重新读取当前 registry；legacy `AgentSession` 不足以无条件恢复四层身份，A02 必须 exact bundle、A01 当前必须 fail closed；A02 四层 ID 与 paid execution label 必须按字段面永久保留，不能跨 identity surface 复用；A02 离线回放还必须重新验证 host-resolved immutable source record，不能仅核对可由伪造对象自行重签的摘要；所有 canonical event、ACL、projection、checkpoint、recovery、plan、registry、policy、receipt、current ledger snapshot 和 current authorization 对象都必须在每次消费时重跑类型、嵌套语义与 self-digest 校验；checkpoint 的 plan/graph/event-ledger 及全部 typed current material 必须来自 host-owned current-material resolver，不能由调用者同时提供现状和 expected 值来自证；manifest 的 objective/plan/graph/task assignment 必须来自 current accepted plan authority，PlanDelta/observation/feedback/action menu/budget/stop/intervention/checkpoint 则必须来自 host-owned current-model-context resolver，并将整组当前状态摘要先行封入 sealed RuntimeScope，不能靠 resolver 名称或 snapshot 自签自证；governance summary 必须由已完成内部字段交叉验证的 current canonical runtime policy 派生，均不能由 caller 文本提供。上述修订替代原文中更宽松的兼容表述；它们仍不关闭 RC-S3-105，不创建 A03，不证明 provider、backend 或产品已跑通。

实现可以根据零模型测试和成熟组件 spike 修正字段名、表名、依赖版本和内部模块拆分，但若要改变上述方向、引入第二套框架、扩大产品范围、改变 Evidence/NumericFact/public-gap authority、强制上 Redis/云端或创建付费 successor，必须先更新本文并向 Owner 解释新证据和影响。

2026-09-03 Owner 进一步裁决并修订本冻结：Dell vertical 直接采用 LangSmith/LangGraph Agent Server，删除运行时 fallback。这个修订废止本文和历史工作记录中“Agent Server 拒绝后可实现 OSS single-worker runtime”的未来授权，但不改写那些记录在当时的事实。2026-09-04 的 current 采用状态已推进为 `ADOPT_DIRECTION_OWNER_APPROVED / OWNER_DATA_GATE_ACCEPTED / FRESH_R7_ZERO_MODEL_LOCAL_CONTROL_PLANE_PARITY_PASS_BOUNDED`；它不等于真实 Agent Server graph、model、Agent Server graph-initiated/live-external MCP、multi-agent、HITL、报告或产品已通过，也不创建 A03 或 paid authority。

### 25.1 r8 live graph 资格实现合同（执行前冻结）

下一段不另建 runtime。现有单一 `dell_reference_vertical` StateGraph 增加部署拥有的
`zero_model_control_plane_v1` 资格 profile：它只执行冻结 Q1 的真实 Evidence/Finance
MCP 两条 lane，生成 content-free summary，随后进入 LangGraph 原生 dynamic
interrupt；合法 resume 只完成资格状态，不重跑 MCP，也不生成 final report。基础
Compose 始终为 `product`，资格 profile 只能由显式 overlay 和独立 Compose project
启用；API 只发布 loopback，PostgreSQL/Redis 不发布 host port，DeepSeek key 不进入
容器，LangSmith input/output hiding 必须精确为字符串 `true`。

正式 `DellAgentServerClient` 负责 canonical FIN Session/ResearchRun/RunInvocation 与
server thread/run 绑定，并把 profile、concrete assistant UUID、三层身份 digest 与
launch digest 放入 remote metadata。create 前和不确定响应后只接受唯一精确匹配；
重复、身份冲突、assistant 冲突或不稳定分页一律拒绝；transport create 结果未知时
不得自动重发。服务端 entry 在打开数据/MCP 前反查 FIN durable final binding。此处是
bounded reconciliation，不是跨事务 exactly-once：SQL 尚无 durable
PENDING/ORPHAN/RECONCILED 生命周期，profile/launch digest 尚未冻结进 FIN row，2 秒
scheduled-start 只是本地缓冲，不是事务 happens-before。

checked-in r8 runner 只编排一条 fresh、clean-commit 现场验收：START 到 interrupt，
API restart readback，Redis process restart readback，同 project/同 volume stop-start
readback，ordinal 2 RESUME，START/RESUME exact replay，SSE full/suffix replay，最后查询
固定 LangSmith project。runner 只保存 ID、计数、大小与 digest，不落盘 graph state、
Evidence/NumericFact body、SSE payload 或原始 span；失败 attempt 不覆盖、不清理，且
不会用故障注入抢 2 秒窗口来伪造 live orphan recovery。LangSmith 是实际 outbound
observability egress；input/output 必须为空，但用于唯一关联的 bounded UUID/digest
metadata 仍会离开本机，不能写成全 metadata 本地驻留。

pre-live review 又把资格证明收紧为实际协议事实：AgentSession 的 as-of 直接取冻结
`2026-09-02`，data snapshot digest 绑定 Owner 数据门完整 self-digest，不能拿 research
foundation digest 代替；Agent Server 0.13.3 的 SSE 允许正常 EOF，若出现 `end` 则只能
位于末尾，断点必须从非末帧开始并得到非空 exact suffix；四个 interrupted readback
之间的 session/binding/FIN identity/remote run/SSE/state 必须逐项相等，resume 与 final
也必须 exact replay。LangSmith 必须先由 FIN PostgreSQL 取得两个 durable
`server_run_id`，再证明每个 root `id=trace_id=server_run_id`、metadata 身份一致、所有
span 已结束且在有间隔的两次查询中集合稳定，之后才可检查 input/output hiding、无 LLM
span、token/cost=0 与限定 secret/内部 locator 扫描。canonical digest 与落盘文件字节
SHA 分开记录，失败子进程的内容最小化 observation 和 typed phase failure 必须保留。

r8 PASS 也只允许声明：真实 Agent Server + FIN final binding + frozen local MCP +
interrupt/checkpoint/restart/resume/SSE + 本次 trace payload hiding。以下继续为 false：
distributed exactly-once、unknown outcome 自动重试、durable orphan lifecycle、Redis
丢失/替换、HA/DR、product multi-agent、任何模型/外源研究/付费调用、Evidence admission、
S2 write、Workbench HITL、最终 Dell 报告与 production security。是否申请第一条 paid
successor，必须在 r8 结果和这些剩余边界上重新做 Owner 决策，不能由 r8 自动授权。

## 26. 2026-09-04 实施证据与当前剩余门

本节是冻结设计的 implementation-evidence successor，不改变产品范围、Agent Server/LangSmith 单一路径或 A03 必须另行授权的设计。实现提交为 `f0de87e024686660db4f5c0bfdcf85bddce1f120`。

Owner 数据门已接受；answer-free 的真实组合得到 Reviewed=`56`、S2=`1,319`、external routes=`12`、local candidates=`890`。官方 MCP client 已在本进程内实际调用冻结的 Evidence/Finance tools；model/live-external/network/paid=`0`。这使 `RC-S3-105` 可以在零模型 inventory/compiler/composition 范围关闭，但 A02 永久不重试，未来 paid successor 仍需新的独立 Owner authority。

fresh r6 在当时合同下真实成功，随后因其 admitted catalog projection fingerprint 未覆盖 role GUC、connection limit 与 valid-until 而被 review supersede；历史不删除。current fresh r7 image local ID 为 `sha256:c658b11a177cb14949ee92a13b674f930dd24fb77d8265f2a59430ebee94fba6`，040 source SHA 为 `dec88b731a59d696509c184cf45ea1344d5840d7aa0c07515b3902b3de9ddd00`，91-row admitted catalog projection SHA 为 `28c2bb8501d78ca3b43e1a490acae050df46b8226d2c2511a34b99a1723ec4a8`。fresh Agent Server/PostgreSQL/Redis healthy，API 只在 `127.0.0.1:18127`，现有卷 exact installer replay、五类事务回滚 drift 反例、独立 FIN identity `1/1/3`、官方 SDK 唯一 graph 的 6-input/3-context schema，以及固定空 thread 的 API/Redis/full-stack idle restart readback 均通过。040 精确绑定的是当前承认的 projection，不是 entire PostgreSQL catalog；其他 relkind、column ACL 与 global migrator default ACL hardening 保留为 P2。镜像仍为 root/writable，Compose 没有 cap-drop/no-new-privileges/resources，容器环境也不是 secret manager，所以 shared/production qualification 仍为 false。

LangSmith metadata HTTP 204 且 `n_runs=0` 只证明 key/project connectivity，不证明 run trace、span flush、UI 可见或 privacy。Docker 当前使用 `http.docker.internal:3128` 代理仍完成 build、启动和 metadata 请求，因此代理不是 current blocker；较早 TLS EOF 最多是 plausible transient proxy/VPN effect，不能作为确定根因。

当前 `ZERO_MODEL_LOCAL_CONTROL_PLANE_PARITY_PASS_BOUNDED` 已包含 local in-process frozen MCP client tool execution，但明确不含：live FIN↔server identity binding、remote-create→FIN-bind orphan reconciliation、真实 graph/run/checkpoint/resume、Agent Server graph-initiated MCP、live external MCP capture、Redis execution-state persistence、SSE restart replay、LangSmith run trace/privacy、DeepSeek/model、dynamic multi-agent、HITL、report、product、shared/production 或完整 image supply-chain qualification。下一实现门依次是 live identity ingress/binding 与 orphan reconciliation；server retry/idempotency；零模型真实 graph 的 checkpoint/restart/SSE/LangSmith trace/privacy。完成并 clean push 后，才可向 Owner 提交新的 paid execution 决策和 task-specific token budget。
