# R53-R60 统一需求单与单 Agent 执行顺序计划

日期：2026-06-29

状态：execution planning draft

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `27_r53_r60_engineering_execution_program.zh-CN.md`
- `28_r53_research_to_quant_lab_technical_plan.zh-CN.md`
- `29_r54_secondary_market_capital_feedback_technical_plan.zh-CN.md`
- `30_r55_deliverable_studio_dashboard_projection_technical_plan.zh-CN.md`
- `31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`
- `32_r57_graph_skill_memory_pack_operating_model.zh-CN.md`
- `33_r58_db_rag_retrieval_data_pipeline_control_plane.zh-CN.md`
- `34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md`
- `35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md`

## 0. 范围说明与企业级验收模型

### 0.1 R 系列范围

本文的执行范围是当前新一轮 `R53-R60` 工程化主线，不代表整个项目的 R 系列从 R53 才开始。

项目历史上的 R 系列大致分为三段：

| 范围 | 定位 | 当前处理方式 |
| --- | --- | --- |
| `R0-R49` | 数据扩容、Milvus / RAG、source lane、exact-slot、ProductIntelligenceGraph、runtime gate、AI/Semis product evidence 等历史实施阶段 | 作为已完成或已记录缺口的基础能力与前置依赖；不在本文逐项重拆，但 S0 需要引用其已实现合同和未完成缺口 |
| `R50-R52` | 产品定位、B 端 PRD、协作型 agent graph、WorkpaperEvent / Research Lead supervision 等产品和协作模式转向 | 作为 R53-R60 的产品与 agent 协作前置 |
| `R53-R60` | Research-to-Quant、Secondary Market / Capital Feedback、Deliverable Studio、runtime stack、graph/skill/memory、DB/RAG/data pipeline、backend/frontend、eval/observability 的工程化主线 | 本文的直接拆分范围 |

因此，36 文档不是覆盖所有历史 R0-R49 的“总历史清单”，而是把 R50-R52 之后的新产品方向和 R53-R60 技术框架转成单 agent 可执行 release slices。早期 R0-R49 中仍未闭环、但会影响 R53-R60 的事项，应在 S0 `U0-D02-r-demand-map` 中作为 baseline dependency、known gap 或 blocker 引入统一 backlog。

### 0.2 企业级通过条件模型

后续需求单不再以“脚本能跑 / 页面能打开 / 模型有输出”作为通过。`done` 只代表实现动作结束，不代表需求达到可依赖、可试用或可上线。

每条需求必须同时记录：

- intermediate gates
- `scope_l4_acceptance`
- `closeout_level`
- Product acceptance
- Engineering acceptance
- Quality acceptance
- Ops acceptance
- 证据：测试、eval、trace、artifact、review、release gate 或明确的 typed gap

四类 acceptance 的定义：

| 类别 | 判断问题 | 最低证据 |
| --- | --- | --- |
| Product acceptance | 是否解决真实金融研究 / 办公工作流问题，是否减少重复劳动，是否方便 senior 审阅和追责 | 真实任务或代表性 case 的用户流程证据、底稿 / 交付物可读性、review 记录 |
| Engineering acceptance | schema、API、DB、artifact、event、runtime contract 是否稳定，下游能否依赖 | deterministic tests、schema validation、DB / artifact parity、contract tests |
| Quality acceptance | 证据、结论、反证、gap、引用、输出质量和弱信号边界是否达标 | eval case、citation / authority audit、unsupported-claim gate、gap taxonomy |
| Ops acceptance | token、cost、latency、queue、incident、sandbox、fallback、rollback 是否可控 | trace / cost ledger、load / chaos smoke、incident runbook、rollback path |

五级 pass level：

| Pass level | 含义 | 允许用途 | 不允许误用 |
| --- | --- | --- | --- |
| `L0_smoke_pass` | 最小链路能跑，证明方向或接口没有完全断 | 本地 smoke、demo、diagnostic | 不得作为下游依赖或上线依据 |
| `L1_contract_pass` | 合同完整、字段稳定、失败边界可见，可被后续 slice 依赖 | 下游开发、联调、有限自动化测试 | 不得声称内部业务可用 |
| `L2_internal_dogfood_pass` | 内部真实任务可用，能减少重复劳动并保留追责 | 内部 dogfood、少量真实 case、人工 review | 不得直接给试点客户或生产用户 |
| `L3_release_candidate_pass` | 具备试点交付条件，有 release readiness、监控、回滚和已知风险 | 试点客户、受控试运行 | 不得当成正式多租户生产系统 |
| `L4_production_pass` | 企业级正式交付，多用户、长任务、权限、审计、监控、异常恢复和持续评测可用 | 生产环境 | 不得绕过变更、incident、eval 和安全门控 |

### 0.3 Slice Closeout 统一口径：`L4_scope_pass`

本文后续所有 release slice 的最终通过口径统一为 `L4_scope_pass`。

`L4_scope_pass` 不等于“每个 slice 都要证明整个系统已经 `L4_production_pass`”。它的含义是：该 slice 在自己的职责范围内达到 enterprise-grade / production-grade 标准，能够被下游长期依赖、审计、回放、回滚和持续评测。

因此：

| 概念 | 含义 | 用途 |
| --- | --- | --- |
| `L0_smoke_pass` / `L1_contract_pass` / `L2_internal_dogfood_pass` / `L3_release_candidate_pass` | 开发过程中的中间门控或阶段证据 | 证明某一类风险已经下降，但不代表 slice closeout |
| `L4_scope_pass` | 当前 slice 在自身职责范围内达到企业级生产要求 | 每个 S0-S10 slice 的最终 closeout 口径 |
| `L4_production_pass` | 全系统正式生产级通过 | 只适用于 S10 或全产品 release gate |

例子：

- S0 backlog/schema 不需要证明全系统多用户生产可用，但它的 backlog schema、gate matrix、R-demand map 和 release board contract 必须达到生产级：字段稳定、可机器读取、可回放、可追责、可被下游长期依赖。
- S1 runtime spine 必须达到生产级任务主账本标准：状态机、SQL audit、artifact refs、trace、resume/replay、失败边界、rollback 和数据一致性都稳定。
- S5 Workpaper / Lead Review 这类用户工作流 slice 必须证明真实内部任务下能产出可审阅、可追责、可复盘的底稿。
- S10 Enterprise Hardening / Release Candidate 才负责把多个 `L4_scope_pass` slice 串成全系统 `L4_production_pass` 候选。

换句话说，`L1_contract_pass` 和 `L2_internal_dogfood_pass` 以后只能作为中间检查点，不再作为“通过”。每个 slice 的 closeout 必须输出 `PassLevelDecision.closeout_level = L4_scope_pass`。如果达不到，只能记录为 `diagnostic` / `partial` / `blocked` / `exception_requested`，不得标记为 pass。

## 1. 目标

本文把 PRD 和 R53-R60 的框架文档转成下一阶段可执行需求单顺序。约束是：当前只有用户和一个 Codex agent，不开多 agent 开发模式，因此不能按能力域大规模并行拆给多人认领，而要按 dependency spine 做 release slice。

核心目标：

- 不再按 R53、R54、R55 编号机械串行；
- 不把上层 quant / deliverable / secondary market 做成孤立脚本；
- 先建立任务、事件、证据、trace、eval、artifact 的主账本；
- 每个 slice 都有中间门控、`L4_scope_pass` closeout 条件和四类 acceptance；
- 每个 slice 都能独立验收、提交、回滚。

## 2. 执行原则

1. 先做 spine，再做功能面。
   Runtime / event / SQL audit / trace / evidence refs / eval refs 是所有上层功能的脊柱。

2. 按 `L4_scope_pass` 推进，不用中间门控替代完成。
   `L1_contract_pass` 只适用于合同型底座需求，且必须有完整 schema/API/DB/artifact/event/eval 合同和确定性测试；凡是用户工作流、底稿、交付物、前端使用面、质量工程或 release candidate 相关 slice，必须达到对应 `L2_internal_dogfood_pass` 或 `L3_release_candidate_pass` 后才算该 slice 通过。

3. 先 Workpaper，再 Memo / PPT。
   B 端生产力价值在可审阅底稿，不在一次性聊天答案。

4. 先 retrieval / data trace，再调 writer。
   如果证据和检索链路不可审计，写作层优化会持续浪费 token。

5. 先本地 SQL/ObjectStore 主账本，再考虑外部 observability export。
   Langfuse / Phoenix / Datadog 等只做派生 export，不替代本地审计主账本。

6. 每个 slice 结束必须有：
   - demand list；
   - implementation diff；
   - deterministic tests；
   - `L4_scope_pass` closeout 判定；
   - Product / Engineering / Quality / Ops 四类 acceptance 证据；
   - 与 `L4_scope_pass` 和中间门控匹配的 smoke、dogfood、release-candidate 或 production gate；
   - updated worklog/checklist；
   - git closeout。

## 3. 总体依赖图

```text
S0 Unified Backlog / Gate Matrix
 -> S1 Runtime Task Spine
 -> S2 Tool / Sandbox / Trace Spine
 -> S3 Data / Retrieval / Evidence Spine
 -> S4 Context / Graph / Skill Registry
 -> S5 Workpaper / Lead Review Workflow
 -> S6 Workbench Frontdoor And Drilldown
 -> S7 Deliverable Studio And Dashboard Projection
 -> S8 Secondary Market / Capital Feedback Pack
 -> S9 Research-to-Quant Lab
 -> S10 Enterprise Hardening / Release Candidate
```

S8 / S9 可以在 S5 之后做局部 schema smoke，但不能进入可信业务闭环，直到 S1-S7 的主账本和 Workpaper 链路稳定。

## 4. Release Slices

### S0 Unified Backlog / Gate Matrix

目标：把 R53-R60 所有 open demand 合并为统一 backlog，避免“文档里有但没有需求单”的隐性任务。

中间门控：`L1_contract_pass`

Slice closeout：`L4_scope_pass`（backlog / schema / gate matrix 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U0-D01-backlog-schema` | 27 / R60 | 定义统一 demand ticket schema | 每条需求有 PRD trace、tech trace、domain、dependencies、acceptance、tests、intermediate gates、`scope_l4_acceptance`、`closeout_level` |
| `U0-D02-r-demand-map` | R53-R60 | 把 R53-R60 demand 映射到 unified backlog | 不存在 unmapped R-demand；每个 checklist open item 有 owner slice |
| `U0-D03-pass-level-gate-matrix` | PRD / 27 / R60 | 把中间门控、`L4_scope_pass` 和全产品 `L4_production_pass` 固化到 backlog | 每条需求标注 intermediate gates、`scope_l4_acceptance` 和 `closeout_level`；done 不替代 pass |
| `U0-D04-release-slice-board` | 27 | 生成单 agent 执行看板 | 每个 slice 有前置依赖、阻塞项、验收和 rollback |

S0 结束后才开始代码实现。

#### S0 v0.1 implementation closeout

2026-06-29 已把 S0 从规划文本落成 machine-readable backlog / gate artifacts，并达到 S0 范围内的 `L4_scope_pass`。

核心生成物：

- `configs/r53_r60/s0_unified_backlog_schema_v0_1.json`
- `data/manifests/r53_r60_r_document_inventory_v0_1.jsonl`
- `data/manifests/r53_r60_demand_map_v0_1.jsonl`
- `data/manifests/r53_r60_implementation_tasks_v0_1.jsonl`
- `data/manifests/r53_r60_pass_level_gate_matrix_v0_1.jsonl`
- `data/manifests/r53_r60_release_board_v0_1.jsonl`
- `data/manifests/r53_r60_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_unified_backlog_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_unified_backlog_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s0_unified_backlog_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- active source docs：`12/12` 存在；
- R0-R49 baseline inventory：`99` 条；
- demand tickets：`61` 条；
- implementation tasks：`183` 条；
- release slices：`11` 条；
- S0 gate rows：`12 pass / 0 fail`；
- closeout：`S0_L4_scope_pass`；
- next slice unlocked：`S1`。

边界：S0 只证明 backlog / schema / release board / pass-level matrix / gate artifact 在自身范围达到 enterprise-grade，可被 S1 依赖；不代表全产品达到 `L4_production_pass`。

### S1 Runtime Task Spine

目标：建立任务主账本，让所有后续功能都有统一 run state、event、artifact、trace anchor。

中间门控：核心合同 `L1_contract_pass`，1 条真实任务达到 `L2_internal_dogfood_pass`

Slice closeout：`L4_scope_pass`（runtime task spine 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U1-D01-runtime-facade-entrypoint` | R56-D01 / R59-D02 | 统一 CLI / Python / Java shell 的 create/resume/get-state contract | 同一 task_id 能从至少两个入口查询一致状态 |
| `U1-D02-task-run-state-machine` | R59-D03 | 定义 ResearchTask / TaskRun / TaskEvent / ProgressProjection | pending/running/paused/repairing/failed/succeeded/cancelled 状态可落 SQL |
| `U1-D03-sql-final-task-audit` | R59-D04 / R60-D02 | task/run/node/artifact/event 进入 SQL 主账本 | 不依赖 Redis 作最终审计；run_id 可查完整 event chain |
| `U1-D04-workpaper-event-ledger` | R52 / R55 / R59 | 建 append-only WorkpaperEvent | agent / human / verifier 修改都可追踪 |
| `U1-D05-checkpoint-resume-replay` | R56-D04/D06/D09 | checkpoint ref、pause/resume、replay gate | 任务中断后可恢复关键状态；replay 能重建 artifact refs |
| `U1-D06-run-trace-baseline` | R60-D02/D03 | model/tool/retrieval/parser 基础 trace/usage | 每个 node 有 trace span，至少记录 latency 和 token/cost placeholder |

#### S1 v0.1 implementation closeout

2026-06-29 已把 S1 从规划文本落成 SQL-final runtime task spine，并达到 S1 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_runtime_task_spine.py`
- `scripts/engineering/build_r53_r60_s1_runtime_task_spine.py`
- `tests/test_r53_r60_runtime_task_spine.py`
- `configs/r53_r60/s1_runtime_task_spine_schema_v0_1.json`
- `data/manifests/r53_r60_s1_runtime_task_spine_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s1_runtime_task_spine_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s1_runtime_task_spine_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- SQL-final tables：`research_tasks`、`task_runs`、`task_events`、`node_executions`、`artifact_refs`、`workpaper_events`、`checkpoint_refs`、`trace_spans`、`task_progress_projection`；
- dogfood / gateway compatibility tasks：`2`；
- task runs：`3`；
- task events：`16`；
- append-only WorkpaperEvent rows：`1`，且 update/delete trigger 均 blocked；
- node/artifact/checkpoint/trace rows：均有 runtime row；
- S1 gate rows：`10 pass / 0 fail`；
- closeout：`S1_L4_scope_pass`；
- next slice unlocked：`S2`。

边界：S1 只证明 runtime task spine 在自身范围达到 enterprise-grade，可被 S2-S10 依赖；不代表全产品达到 `L4_production_pass`。Java gateway / Workbench 后续应通过 S1 facade 或兼容导入写入该主账本，Redis / MQ 只做协作状态，不做最终审计源。

### S2 Tool / Sandbox / Trace Spine

目标：让工具调用变成受控企业能力，不是 agent 任意执行脚本。

中间门控：`L1_contract_pass`

Slice closeout：`L4_scope_pass`（tool / sandbox / trace 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U2-D01-actor-permission-policy` | R56-D02 / R59-D19 | actor -> tool -> permission policy | writer 禁止 retrieval/web；composer 只能 render；越权 fail closed |
| `U2-D02-tool-gateway-contract` | R56-D03 / R58-D09 | DB/RAG/web/parser/render/backtest 工具统一 schema | 每次 tool call 有 input digest、output artifact、policy decision |
| `U2-D03-sandbox-local-lightweight` | R59-D19/D20 | workspace path、domain allowlist、timeout、output limit | blocked call 可见，允许 call 可追踪 |
| `U2-D04-tool-invocation-ledger` | R59 / R60 | 工具调用账本 | tool_call_id 能回到 actor、policy、artifact、error |
| `U2-D05-sandbox-regression` | R60-D13 | 越权/合法工具 deterministic tests | 至少覆盖 forbidden writer fetch、credential/path/network escape |

#### S2 v0.1 implementation closeout

2026-06-29 已把 S2 落成 S1-native `ToolGateway / SandboxPolicy / ApprovalPolicy / ToolInvocationLedger`，并达到 S2 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_tool_sandbox_spine.py`
- `scripts/engineering/build_r53_r60_s2_tool_sandbox_trace_spine.py`
- `tests/test_r53_r60_tool_sandbox_spine.py`
- `configs/r53_r60/s2_tool_sandbox_trace_schema_v0_1.json`
- `data/manifests/r53_r60_s2_tool_sandbox_trace_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s2_tool_sandbox_trace_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s2_tool_sandbox_trace_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- S2 policy tables：`tool_gateway_metadata`、`tool_policy_bindings`、`sandbox_policies`、`approval_policies`、`approval_decisions`、`tool_invocations`；
- tool policy bindings：`6`；
- sandbox policies：`5`；
- approval policies：`6`；
- S2 dogfood tool invocations：`9`，其中 allowed / blocked 都进入 ledger；
- approval decisions：`1`；
- S2 gate rows：`12 pass / 0 fail`；
- closeout：`S2_L4_scope_pass`；
- next slice unlocked：`S3`。

本轮 gate 覆盖：

- writer 不能调用 retrieval / web；
- unknown tool fail closed；
- public web snapshot 必须 domain allowlist；
- filesystem path 必须 workspace / artifact scoped；
- credential-like arguments blocked and redacted；
- 高风险 local analysis / backtest 类工具必须 human approval；
- allowed tool call 必须产生 artifact ref；
- allowed / blocked tool call 都必须写入 S1 event / trace，并可被 progress projection 覆盖。

边界：S2 只证明工具权限、sandbox policy、approval gate 和 tool trace / ledger 在自身范围达到 enterprise-grade；本轮不执行真实 web crawling、document parsing、Python analysis 或 quant backtest。S3 后续把 DB/RAG/retrieval/data lineage 的真实工具接入该 ToolGateway。

### S3 Data / Retrieval / Evidence Spine

目标：把 DB exact、BM25/ObjectBM25、Milvus、graph、web repair、parser rows 变成可审计 retrieval plan，而不是散装查询。

中间门控：`L1_contract_pass`；核心研究 case 目标 `L2_internal_dogfood_pass`

Slice closeout：`L4_scope_pass`（data / retrieval / evidence spine 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U3-D01-retrieval-intent-taxonomy` | R58-D01 | 定义 retrieval intent schema 和 classifier | fundamental/product/capital/market/filing/web repair intent 可区分 |
| `U3-D02-route-policy-matrix` | R58-D02 | 定义 DB / graph / BM25 / Milvus / web route 顺序 | 不同 intent 有不同 route、budget、forbidden source boundary |
| `U3-D03-query-rewrite-facet-plan` | R58-D03 | exact/lexical/semantic/graph facet queries | query drift 有记录，不能盲目扩检 |
| `U3-D04-hybrid-recall-rerank-policy` | R58-D04 | role quota、source-family quota、fusion/rerank | 不提前 cap 掉 product/capital/market 强证据 |
| `U3-D05-retrieval-execution-ledger` | R58-D05 | 记录 candidate/rerank/selected/dropped | 每个 selected evidence 都能解释来源；dropped 有 reason |
| `U3-D06-retrieval-eval-qrels` | R58-D06 / R60 | 建 qrels / gold / negative cases | 重点 case 有 target-in-candidates 和 rerank audit |
| `U3-D07-data-lineage-contract` | R58-D07-D10 | Ingestion/Parser/Storage/DB performance profile | source -> parser -> row -> retrieval -> context 可回放 |

#### S3 v0.1 implementation closeout

2026-06-29 已把 S3 落成 S1 / S2 native 的 retrieval / evidence spine，并达到 S3 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_retrieval_evidence_spine.py`
- `scripts/engineering/build_r53_r60_s3_retrieval_evidence_spine.py`
- `tests/test_r53_r60_retrieval_evidence_spine.py`
- `configs/r53_r60/s3_retrieval_evidence_spine_schema_v0_1.json`
- `data/manifests/r53_r60_s3_retrieval_evidence_spine_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s3_retrieval_evidence_spine_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- S3 SQL tables：`retrieval_intent_registry`、`retrieval_route_policy_matrix`、`retrieval_plans`、`retrieval_route_executions`、`retrieval_candidates`、`retrieval_selected_evidence`、`retrieval_dropped_candidates`、`retrieval_gap_ledger`、`retrieval_eval_qrels`；
- required routes：`sql_exact`、`graph`、`bm25`、`object_bm25`、`milvus_semantic`、`web_repair`、`parser_row` 全部进入 `RoutePolicyMatrix` 和 route execution ledger；
- retrieval candidates：`49`；
- selected evidence：`15`，且只能来自 `exact_company_fact_authority` 或 `bounded_thesis_driver_authority`；
- dropped candidates：`34`，包括 `duplicate_evidence_ref`、`authority_not_promotable`、`route_budget_exceeded` 等 reason；
- qrels：`2`，证明 target refs 同时进入 candidates 和 selected evidence；
- S3 gate rows：`12 pass / 0 fail`；
- closeout：`S3_L4_scope_pass`；
- next slice unlocked：`S4`。

本轮 gate 覆盖：

- 上游 RD3 / RD5 / RD6 / RD7 / ResearchGraph / ProductIntelligenceGraph summary 必须存在且状态允许；
- route policy 必须覆盖 SQL exact、graph、BM25、ObjectBM25、Milvus semantic、web repair、parser row；
- retrieval plan 必须有 facets、query rewrite、route budget 和 typed-gap policy；
- route execution 必须写 SQL ledger，并链接 S1 trace；`sql_exact` 还必须链接 S2 `ToolInvocationLedger`；
- selected evidence 禁止 planning / gap-only / raw retrieval hit 进入；
- dropped candidates 必须有 reason；
- qrels 必须证明重点 target-in-candidates 和 target-in-selected；
- S3 任务可重复构建，不删除 S1 append-only `WorkpaperEvent`，而是通过 resume 新 run 重建 S3 自身表。

边界：S3 只证明 retrieval / evidence route ledger 在自身范围达到 enterprise-grade；本轮不做 full recall/rerank 调参、不重建 Milvus、不写 memo，也不把 raw retrieval hit 直接注入 Memo Writer。S4 后续负责 Context / Graph / Skill Registry，S5 后续把 selected evidence / typed gaps 组织成 Workpaper。

### S4 Context / Graph / Skill Registry

目标：让 Research Lead 和 specialist 使用可版本化能力资产，而不是靠 prompt 记忆。

中间门控：`L1_contract_pass`

Slice closeout：`L4_scope_pass`（context / graph / skill registry 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U4-D01-graph-capability-registry` | R57-D01 | GraphPack registry 和当前图谱 inventory | GraphPack 有 version、scope、authority、tenant status |
| `U4-D02-skillpack-registry` | R57-D02 | 现有专家 prompt/skill 结构化 | SkillPack 有 input/output contract、forbidden behavior、eval |
| `U4-D03-memorypack-registry` | R57-D03/D10 | memory tiers、TTL、staleness、supersession | 持久 memory 有 provenance、permission、promotion status |
| `U4-D04-contextengine-lifecycle` | R57-D09 | resolve/select/compress/inject/write/consolidate/invalidate | 每次注入生成 ContextInjectionPlan |
| `U4-D05-context-compression-artifact` | R57-D11-D13 | 压缩策略和质量 gate | exact facts 只引用不摘要；dropped refs 有 reason |
| `U4-D06-lead-graph-skill-selector` | R57-D04/D05 | Lead / specialist 必须声明消费哪些 packs | Specialist 输出中有 consumed pack refs |

#### S4 v0.1 implementation closeout

2026-06-29 已把 S4 落成 S1 / S3 native 的 Context / Graph / Skill Registry，并达到 S4 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_context_graph_skill_registry.py`
- `scripts/engineering/build_r53_r60_s4_context_graph_skill_registry.py`
- `tests/test_r53_r60_context_graph_skill_registry.py`
- `configs/r53_r60/s4_context_graph_skill_registry_schema_v0_1.json`
- `data/manifests/r53_r60_s4_context_graph_skill_registry_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s4_context_graph_skill_registry_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s4_context_graph_skill_registry_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- GraphPack registry：`6`，覆盖 retrieval evidence spine、DimensionEvidencePortfolio、ProductIntelligenceGraph、ProductRelationshipGraph、ResearchGraph、source authority mart；
- SkillPack registry：`16`，每个 skill pack 有 prompt digest、适用角色、输入/输出 contract、forbidden behavior 和 eval hooks；
- MemoryPack registry：`6`，覆盖 node scratch、run、project、company/watchlist、org/private、global playbook memory，均带 provenance、TTL、staleness、permission 和 promotion status；
- Context lifecycle events：`7`，覆盖 resolve/select/compress/inject/write/consolidate/invalidate；
- ContextInjectionPlan：`4`，覆盖 `research_lead`、`fundamental_analyst`、`product_technology_analyst`、`industry_supply_chain_analyst`；
- context pack selections：`61`；
- dropped context refs：`34`，均有 reason；
- S4 gate rows：`12 pass / 0 fail`；
- closeout：`S4_L4_scope_pass`；
- next slice unlocked：`S5`。

本轮 gate 覆盖：

- S4 必须读取 S3 selected evidence refs，不能直接消费 raw retrieval candidates；
- GraphPack / SkillPack / MemoryPack 必须进入 SQL registry，并携带版本、scope、authority/permission/lifecycle 约束；
- ContextEngine lifecycle 必须可 replay；
- exact company facts 在 compression artifact 中只能保留 ref，不允许被压缩摘要改写；
- dropped refs 必须有原因；
- Research Lead 和 specialists 必须声明 consumed graph / skill / memory / evidence pack refs；
- S4 任务可重复构建，不删除 S1 append-only `WorkpaperEvent`，而是 resume 新 run 并重建 S4 自身表。

边界：S4 只证明 context / graph / skill / memory registry 与 ContextInjectionPlan 在自身范围达到 enterprise-grade；本轮不写 Workpaper、不调用 LLM、不生成 Memo，也不证明最终研究质量。S5 后续负责把 S3 selected evidence 与 S4 context pack refs 组织成 Workpaper / Lead Review workflow。

### S5 Workpaper / Lead Review Workflow

目标：形成真正 B 端生产力闭环：Research Lead 常驻监督，specialist 输出先进底稿，senior 可审阅。

中间门控：`L2_internal_dogfood_pass`

Slice closeout：`L4_scope_pass`（Workpaper / Lead Review workflow 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U5-D01-research-objective-contract` | R52 / PRD | 任务目标、必答维度、最低证据要求 | 每个任务先生成可审计 objective contract |
| `U5-D02-dimension-evidence-portfolio` | R52 / R58 | 按维度汇总 evidence / claim / gap | fundamental/product/capital/market/risk 维度可见 |
| `U5-D03-lead-review-checkpoint` | R52 / R56 / R60 | Lead 审计是否满足目标 | unmet objective 能触发 targeted repair 或 typed gap |
| `U5-D04-specialist-workstreams` | R52 / R57 | specialist 输出 WorkpaperEvent，不直接写 memo | specialist outputs 有 evidence refs、gap refs、pack refs |
| `U5-D05-judgment-state` | R55 / R60 | thesis / counter-thesis / boundary | unsupported claim rate 可评测 |
| `U5-D06-workpaper-readability-gate` | PRD / R60 | 底稿按研究问题组织，不堆证据 | 1-2 个真实 case 通过人工 review |

#### S5 v0.1 implementation closeout

2026-06-29 已把 S5 落成 S1/S3/S4 native 的 Workpaper / Lead Review workflow，并达到 S5 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_workpaper_lead_review_workflow.py`
- `scripts/engineering/build_r53_r60_s5_workpaper_lead_review_workflow.py`
- `tests/test_r53_r60_workpaper_lead_review_workflow.py`
- `configs/r53_r60/s5_workpaper_lead_review_workflow_schema_v0_1.json`
- `data/manifests/r53_r60_s5_workpaper_lead_review_workflow_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s5_workpaper_lead_review_workflow_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- ResearchObjectiveContract：`1`；
- DimensionEvidencePortfolio rows：`6`，覆盖 fundamentals、product/production、industry/supply-chain、capital/financing、competition/market-position、risk/counterevidence；
- Specialist workstreams：`3`，均写入 append-only `WorkpaperEvent`；
- Workpaper sections：`6`；
- ClaimCards：`6`，全部带 evidence refs、authority boundary 和 source boundary；
- GapItems：`3`，覆盖 retrievable gap、bounded gap、commercial gap；
- TargetedRepairRequest：`1`；
- LeadReviewCheckpoint：`1`，状态 `review_ready_with_visible_gaps`；
- JudgmentState：`1`，状态 `ready_for_writer`，unsupported claim count `0`；
- HumanReviewQueue：`1`；
- S5 gate rows：`12 pass / 0 fail`；
- closeout：`S5_L4_scope_pass`；
- next slice unlocked：`S6`。

本轮 gate 覆盖：

- S5 必须读取 S3 selected evidence refs 和 S4 context / consumed pack refs，不能直接消费 raw retrieval candidates；
- 每个任务必须先生成 ResearchObjectiveContract；
- 每个 required dimension 必须有 claim refs 或 visible typed gaps；
- specialists 必须提交 WorkpaperEvent，而不是直接写 final memo；
- LeadReviewCheckpoint 必须审计 objective coverage、typed gaps、repair requests 和 writer guidance；
- JudgmentState 必须作为 writer 的主输入边界，unsupported claim count 必须可评测；
- ReadabilityGate 必须证明 Workpaper issue-first、不是 claim dump、没有内部字段泄漏、不是 gap-first opening；
- human reviewer 是正式 actor，review item 进入 queue。

边界：S5 只证明 Workpaper / Lead Review workflow 在自身范围达到 enterprise-grade；本轮不做 Workbench UI、不生成 Markdown/Word/PPT/Excel deliverables、不做 final memo、不调用 LLM、不跑 full-chain answer quality eval。S6 后续负责 Workbench frontdoor / drilldown，S7 后续负责 Deliverable Studio / Dashboard Projection。

### S6 Workbench Frontdoor And Drilldown

目标：让用户从工作台而不是命令行使用任务，并能追到 evidence、claim、gap、trace。

中间门控：`L2_internal_dogfood_pass`

Slice closeout：`L4_scope_pass`（Workbench frontdoor / drilldown 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U6-D01-api-boundary-contract` | R59-D02 | Java gateway / Python runtime API 边界 | create/get-state/resume/cancel/artifact API schema 稳定 |
| `U6-D02-task-center-ui` | R59-D03/D06 | Task Center + SSE/event replay | 前端断线重连可恢复任务状态 |
| `U6-D03-evidence-workbench-ui` | R59-D09 | evidence/claim/gap/gate/context/eval drilldown | 用户能从结论点到证据和失败原因 |
| `U6-D04-workpaper-builder-ui` | R59-D10 | Workpaper 分维度展示、评论、版本、退回 | senior 能 review、comment、return |
| `U6-D05-review-queue-ui` | R59-D11 | human question / approval / downgrade | human approval event 进入 ledger |
| `U6-D06-admin-ops-minimal` | R59-D14 / R60 | run、queue、cost、latency、incident 最小视图 | 失败和成本可见 |

#### S6 v0.1 implementation closeout

2026-06-29 已把 S6 落成 S1-S5 SQL-final runtime ledger 的 Workbench frontdoor / drilldown 投影，并达到 S6 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_workbench_frontdoor_drilldown.py`
- `scripts/engineering/build_r53_r60_s6_workbench_frontdoor_drilldown.py`
- `tests/test_r53_r60_workbench_frontdoor_drilldown.py`
- `apps/workbench/backend/app.py`
- `apps/workbench/frontend/vite/src/main.tsx`
- `apps/workbench/frontend/vite/src/workbench.css`
- `configs/r53_r60/s6_workbench_frontdoor_drilldown_schema_v0_1.json`
- `data/manifests/r53_r60_s6_workbench_frontdoor_drilldown_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json`
- `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `docs/internal/vnext_20260610/r53_r60_s6_workbench_frontdoor_drilldown_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- Workbench API contracts：`11`，覆盖 task list / detail / events / resume / cancel / artifacts / drilldown / review queue / review actions / ops / scope gate；
- Workbench SQL projection tables：`workbench_frontdoor_metadata`、`workbench_api_contracts_s6`、`workbench_task_projection_s6`、`workbench_drilldown_projection_s6`、`workbench_review_actions_s6`、`workbench_ops_projection_s6`；
- Task projection：`s5_scope_task_workpaper_lead_review`，status `succeeded`，progress `100`；
- drilldown：Workpaper sections `6`、ClaimCards `6`、typed gaps `3`、S1 events `12`、artifact refs `3`、gate rows `58`；
- LeadReview status：`review_ready_with_visible_gaps`；
- Judgment status：`ready_for_writer`；
- HumanReview status：`queued`；
- S6 gate rows：`8 pass / 0 fail`；
- closeout：`S6_L4_scope_pass`；
- next slice unlocked：`S7`。

本轮 gate 覆盖：

- S6 API contract 必须写入 SQL，而不是只存在于前端或 FastAPI handler；
- Task Center 必须从 S1 task/run/event 主账本投影 status、progress、trace、artifact、review 和 gate counts；
- drilldown 必须能追到 Workpaper sections、ClaimCards、typed gaps、LeadReview、JudgmentState、context refs、gate rows、artifact refs 和 task events；
- review action 必须追加 `WorkpaperEvent` 并进入 `workbench_review_actions_s6`，不能只存在于浏览器状态；
- ops projection 必须展示 queue、latency、cost、trace、incident 和 rollback ref；
- S6 projection 必须 deterministic、SQL-final，不调用 LLM，也不把 Redis / frontend state 当最终审计源。

本轮验证：

- `python -m py_compile src\sec_agent\r53_r60_workbench_frontdoor_drilldown.py scripts\engineering\build_r53_r60_s6_workbench_frontdoor_drilldown.py apps\workbench\backend\app.py`
- `python -m pytest tests/test_r53_r60_workbench_frontdoor_drilldown.py tests/test_workbench_backend.py -q`：`36 passed`
- Frontend build 使用 bundled Node：`node node_modules\typescript\bin\tsc -p tsconfig.json` + `node node_modules\vite\bin\vite.js build --config vite.config.ts`，通过。

边界：S6 只证明 Workbench task frontdoor、SQL-final drilldown、review action ledger 和 ops projection 在自身范围达到 enterprise-grade；本轮不生成 Markdown / Word / PPT / Excel deliverables，不做 dashboard projection 写回，不跑 full-chain answer quality eval，不证明多租户 / RBAC / 高并发生产 SLA。S7 后续负责 Deliverable Studio / Dashboard Projection，S10 后续负责全产品 release candidate。

### S7 Deliverable Studio And Dashboard Projection

目标：从 approved / review-ready Workpaper 生成多格式交付物和 dashboard projection。

中间门控：`L2_internal_dogfood_pass`，后续冲 `L3_release_candidate_pass`

Slice closeout：`L4_scope_pass`（Deliverable Studio / Dashboard Projection 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U7-D01-deliverable-plan` | R55 | DeliverablePlan / NarrativeSurfaceContract | 输出格式、受众、证据边界、内部/客户版明确 |
| `U7-D02-markdown-docx-renderer` | R55 / PRD | Markdown + Word renderer | citation、gap、appendix 不丢 |
| `U7-D03-excel-appendix-renderer` | R55 / PRD | 查数和 evidence appendix 导出 Excel | 表格数据可追溯 |
| `U7-D04-dashboard-projection-updater` | R55 / R59 | task/gap/review/artifact projection | UI 状态回到 SQL/artifact refs，无幽灵状态 |
| `U7-D05-composer-permission-gate` | R55 / R59 | Composer 工具边界 | Composer 不可 retrieval / DB / web |

#### S7 v0.1 implementation closeout

2026-06-29 已把 S7 落成 S5/S6 ledger-native 的 Deliverable Studio / Dashboard Projection，并达到 S7 范围内的 `L4_scope_pass`。

核心生成物：

- `src/sec_agent/r53_r60_deliverable_studio_dashboard.py`
- `scripts/engineering/build_r53_r60_s7_deliverable_studio_dashboard.py`
- `tests/test_r53_r60_deliverable_studio_dashboard.py`
- `apps/workbench/backend/app.py`
- `apps/workbench/frontend/vite/src/main.tsx`
- `apps/workbench/frontend/vite/src/workbench.css`
- `configs/r53_r60/s7_deliverable_studio_dashboard_schema_v0_1.json`
- `data/manifests/r53_r60_s7_deliverable_studio_dashboard_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s7_deliverable_studio_dashboard_l4_scope_pass.zh-CN.md`

本次真实构建结果：

- DeliverablePlan：`1`，绑定 `s5_scope_task_workpaper_lead_review` review-ready Workpaper；
- NarrativeSurfaceContract：`4`，覆盖 internal workpaper、client brief、evidence appendix、dashboard projection；
- RenderJob：`4`，覆盖 Markdown、Word、Excel appendix、dashboard JSON；
- DashboardProjection：`1`，SQL-backed，并回写 artifact refs；
- ComposerPermissionGate：`1`，禁止 retrieval / DB query / web / Milvus / parser fetch / source mutation；
- DeliverableQualityGate：`4 pass / 0 fail`，覆盖 citation、gap、appendix、artifact refs；
- S7 gate rows：`10 pass / 0 fail`；
- closeout：`S7_L4_scope_pass`；
- next slice unlocked：`S8`。

本轮 gate 覆盖：

- S7 必须消费 S5/S6 ledgered Workpaper / task projection，不能直接从 raw evidence 或 frontend state 拼交付物；
- DeliverablePlan 必须声明 audience、formats、source Workpaper、evidence boundary 和 dashboard panel；
- NarrativeSurfaceContract 必须明确每个输出面的用途、输入、禁止行为和 reviewer requirement；
- Markdown / DOCX / XLSX / dashboard JSON 必须有 render job、hash、byte size、artifact ref 和 SQL ledger；
- Composer 只允许 render/write projection，不允许 retrieval、DB query、web search、parser fetch 或 source mutation；
- dashboard projection 必须从 SQL/artifact refs 生成，不能成为前端幽灵状态；
- S6 Workbench drilldown 的 gate row 收集已补 slice 隔离测试，后续 S7+ gate artifact 不得污染 S6 projection。

边界：S7 只证明 deterministic Deliverable Studio / Dashboard Projection 在自身范围达到 enterprise-grade；本轮不证明客户可直接发布的编辑质量、不做 PPT 模板系统、不做 RBAC / tenant / SLA、不跑 full-chain answer quality eval，也不允许 Composer 自行找新证据。S8 后续负责 Secondary Market / Capital Feedback Pack，S10 后续负责全产品 release candidate。

### S8 Secondary Market / Capital Feedback Pack

目标：把二级市场资金面、持仓、信用、资本动作、估值 price-in、期权/期货等接入研究判断，但不冒充基本面事实。

中间门控：`L1_contract_pass`，重点 pack 追 `L2_internal_dogfood_pass`

Slice closeout：`L4_scope_pass`（Secondary Market / Capital Feedback Pack 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U8-D01-capital-feedback-source-registry` | R54 | source / pack living registry | 每个 source 有 authority、refresh、commercial boundary |
| `U8-D02-ownership-holder-pack` | R54 | 13F/13D/G/Form 3/4/5 等持仓动作 | 不把 delayed holder data 当实时资金流 |
| `U8-D03-credit-funding-pack` | R54 | debt、credit facility、convertible、rating、spread proxy | 能解释资本成本和融资窗口边界 |
| `U8-D04-liquidity-positioning-pack` | R54 | turnover、short interest、borrow proxy、ETF/factor flow | 只做 positioning signal，不冒充 fundamental |
| `U8-D05-valuation-price-in-pack` | R54 | valuation / implied growth / peer multiple | 与 fundamental/product thesis 分离但可联动 |
| `U8-D06-derivatives-market-signal-pack` | R54 | futures/options positioning proxy | 强制标注 delayed/proxy/commercial gap |

S8 closeout（2026-06-29）：`S8_L4_scope_pass`。

- runtime contract：新增 `SecondaryMarketSourceRegistry`、`CapitalFeedbackPack`、`CapitalFeedbackSignal`、`CapitalFeedbackGapItem`、`CapitalFeedbackGraphEdge`、`CapitalFeedbackQualityGate`，全部写入 S1 SQL 主账本。
- 真实构建：从 `market_liquidity_driver_context_rows_v0_1`、`capital_funding_ownership_context_rows_v0_1`、`sec_capital_market_event_context_rows_v0_1` 读取已物化 rows，生成 `603` 个 issuer pack、`13,107` 条 bounded signal、`2,443` 条 typed gap、`4,221` 条 graph edge。
- authority boundary：13F / holder 只能做 lagged positioning context；Yahoo chart 只能做 delayed market / liquidity context；SEC offering / insider / 13D/G / proxy metadata 只能证明 filing-event existence；debt / credit facility / working-capital rows 保留 filing / financial-statement exact 边界。
- 明确缺口：derivatives / options / futures、company bond spread / CDS / rating history、short-interest / borrow-cost、valuation denominator / peer multiple 目前进入 typed gap，不伪装成 runtime-ready 数据。
- 修复项：SEC event `all_tickers` 会带入 603 universe 外 ticker，本轮将 S8 issuer universe 锁定为 market snapshot 的 `603` 个 runtime issuer，并把 `6,655` 个 universe 外 SEC event ticker 记录为 scope-filtered 诊断计数，避免 pack 范围污染。
- 验证：S8 deterministic tests `4/4` pass；真实构建 gate `10 pass / 0 fail`；生成 `configs/r53_r60/s8_secondary_market_capital_feedback_schema_v0_1.json`、`data/manifests/r53_r60_s8_secondary_market_capital_feedback_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_s8_secondary_market_capital_feedback_l4_scope_pass.zh-CN.md`。
- next slice unlocked：`S9`。

边界：S8 只证明 Secondary Market / Capital Feedback Pack 在自身范围达到 enterprise-grade，可供 Research Lead / Workpaper / 后续 R53 使用；本轮不证明实时资金流、OPRA options feed、dealer gamma、live borrow cost、CDS、完整债券价格或正式投资建议能力。

### S9 Research-to-Quant Lab

目标：把 research thesis driver 转成候选因子，人工批准后进入 PIT 数据检查、回测和 paper trading monitor。

中间门控：第一阶段 `L1_contract_pass`，内部使用目标 `L2_internal_dogfood_pass`

Slice closeout：`L4_scope_pass`（Research-to-Quant Lab 范围）

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U9-D01-factor-hypothesis-schema` | R53 | FactorHypothesis / FeatureSpec / LabelSpec / UniverseSpec | 每个因子能回到 Workpaper / thesis / evidence |
| `U9-D02-human-approval-flow` | R53 / PRD | manual/assisted/auto candidate approval | dataset build / backtest / paper trading 前必须人工批准 |
| `U9-D03-pit-dataset-builder-gate` | R53 | publish time / available time / tradable-after | 无 PIT 信息不得进入回测 |
| `U9-D04-backtest-adapter` | R53 | deterministic backtest smoke | 至少 2 个 thesis driver 转 FactorHypothesis 并跑 smoke |
| `U9-D05-risk-attribution-factorcard` | R53 | 风险归因和 FactorCard | 回测结果能解释风险暴露、失效场景和 rejected reason |

S9 closeout（2026-06-29）：`S9_L4_scope_pass`。

- runtime contract：新增 `SignalObservation`、`FactorHypothesis`、`FeatureSpec`、`LabelSpec`、`UniverseSpec`、`HumanApprovalDecision`、`DatasetBuildPlan`、`PITDatasetRow`、`LeakageGuardResult`、`FactorAnalysisResult`、`BacktestResult`、`RiskAttribution`、`PaperTradingControl`、`FactorCard`、`ResearchExperienceRecord` 和 `ResearchToQuantQualityGate`，全部写入 S1 SQL 主账本。
- 真实构建：从 S8 `Secondary Market / Capital Feedback Pack` 消费 bounded signals，生成 `3` 个 signal observations / factor hypotheses，其中 `2` 个 human-approved thesis drivers 进入 PIT dataset + deterministic backtest smoke，`1` 个 derivatives/gamma candidate 因无 approved source / human approval 被 fail-closed 阻断。
- PIT / leakage：approved plans 生成 `24` 条 PIT dataset rows，每条都有 publish / available / tradable-after / label-window / source refs / provenance；未审批计划不产生 dataset rows，leakage guard 标为 `blocked_no_human_approval`。
- backtest / FactorCard：生成 `2` 个 factor analysis、`2` 个 no-investment-advice backtest result、`2` 个 risk attribution、`3` 个 FactorCard、`3` 个 ResearchExperienceRecord；paper trading 全部保持 `not_started_requires_separate_human_approval`。
- 验证：S9 deterministic tests `5/5` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/s9_research_to_quant_lab_schema_v0_1.json`、`data/manifests/r53_r60_s9_research_to_quant_lab_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_s9_research_to_quant_lab_l4_scope_pass.zh-CN.md`。
- next slice unlocked：`S10`。

边界：S9 只证明 Research-to-Quant Lab 在自身范围达到 enterprise-grade，可把研究证据转成可审计、可回放、需人工批准的量化验证对象；本轮不证明生产级 alpha、真实交易、对外投资建议、完整历史 security master、商业实时行情或正式 paper trading monitor。

### S10 Enterprise Hardening / Release Candidate

目标：从内部 dogfood 提升到可试点客户使用的 release candidate。

中间门控：`L3_release_candidate_pass`

Slice closeout：`L4_scope_pass`（Enterprise Hardening / Release Candidate 范围）；全产品 release gate 另行冲 `L4_production_pass`

需求单：

| ID | 来源 | 目标 | 通过条件 |
| --- | --- | --- | --- |
| `U10-D01-auth-tenant-rbac` | R59-D07 | 最小组织/项目/角色/权限 | 租户隔离和角色权限测试通过 |
| `U10-D02-load-chaos-sla` | R59-D16 / R60-D14 | 多任务、worker crash、provider timeout、SSE reconnect | p95、queue wait、recovery rate 有记录 |
| `U10-D03-incident-dashboard` | R60-D10 | incident dashboard | parser/retrieval/tool/model/frontend/cost incident 可见 |
| `U10-D04-release-readiness-report` | R60-D11 | release candidate 报告 | gates、known gaps、rollback、owner、user feedback 入口齐全 |
| `U10-D05-online-eval-feedback-loop` | R60-D06/D09 | production failure / reviewer feedback 进 regression | failure/gold lifecycle 可运行 |

S10 closeout（2026-06-29）：`S10_L4_scope_pass_release_candidate_ready`。

- runtime contract：新增 `Tenant`、`User`、`ProjectSpace`、`RoleAssignment`、`PermissionCheck`、`DemandAcceptanceRecord`、`LoadScenario`、`LoadTaskObservation`、`ChaosEvent`、`SLAObservation`、`IncidentRecord`、`IncidentDashboardProjection`、`OnlineEvalFeedbackItem`、`RegressionCaseRecord`、`GoldPromotionRecord`、`ReleaseReadinessReport` 和 `ReleaseGateResult`，全部进入 S1 SQL 主账本。
- 真实构建：S0-S9 dependency summaries `10/10` pass；租户/权限 rows 覆盖同租户 allow、跨租户 deny、analyst 不能 release publish 的 negative gate；20-task controlled load scenario 记录 queue wait、latency、token/cost、SSE reconnect；worker crash / provider timeout / SSE disconnect / artifact write retry 四类 chaos 均 recovered。
- incident / eval：parser、retrieval、tool、model、frontend、cost 六类 incident 全部可见；online eval feedback 生成 `2` 条 regression case 和 `1` 条 gold promotion record。
- release readiness：报告包含 gate refs、known gaps、rollback plan、owner、user feedback entry 和 pilot scope；`full_product_release_status=not_l4_production_pass`，不冒充全系统生产上线。
- 验证：S10 deterministic tests `5/5` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/s10_enterprise_release_candidate_schema_v0_1.json`、`data/manifests/r53_r60_s10_enterprise_release_candidate_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_s10_enterprise_release_candidate_l4_scope_pass.zh-CN.md`。

边界：S10 只证明 Enterprise Hardening / Release Candidate 在自身范围达到 enterprise-grade，可进入受控内部 pilot / dogfood 候选；本轮不证明正式 `L4_production_pass`，也不替代云端 SLA、on-call、审计留存、外部客户试点和长期 online eval 的生产证据。

## 4.1 Post-S10 Completion Gap Register

S10 完成后必须立即生成 post-S10 gap register，而不是直接把 release candidate 当作生产完成。

当前 register：`data/manifests/r53_r60_post_s10_completion_gap_register_v0_1.json`；可读报告：`docs/internal/vnext_20260610/r53_r60_post_s10_completion_gap_register.zh-CN.md`。

真实结果：

- S0-S10 dependency summaries：`11/11 pass`；
- covered scope items：`10`；
- remaining production gaps：`7`；
- suggested next release slices：`6`。

这些 remaining gaps 不是 S0-S10 的失败项，而是从 controlled internal release-candidate 走向真实生产级平台必须补齐的下一层证据：

1. `P-S10-001 production_sla_and_cloud_pilot`：云端/生产级 SLA、on-call、rollback、alert 和多用户试点证据；
2. `P-R56-001 durable_agent_runtime`：真实 graph execution 的 RuntimeFacade、checkpoint/resume、HIL、resource/model router 和 replay；
3. `P-R57-001 graph_skill_memory_lifecycle`：GraphPack / SkillPack / MemoryPack 的 staging、eval、approval、tenant overlay、canary 和 invalidation；
4. `P-R58-001 data_ingestion_retrieval_control_plane`：IngestionJob、RawSourceDocument、FetchAttempt、ParserRun、lineage、qrels、performance profile 和 retrieval-context bridge；
5. `P-R59-001 enterprise_backend_frontend_product_surface`：企业级 API boundary、artifact/review/deliverable APIs、Task Center、Evidence Workbench、Review Queue、Data Room 和 Admin/Ops Console；
6. `P-R60-001 full_eval_observability_quality_engineering`：EvalCase/EvalDataset/EvalRun、TokenCostLedger、node/full-chain gates、CI hooks、sandbox regression、BudgetExceededGate 和 eval dashboard；
7. `P-PRD-001 product_dogfood_and_user_acceptance`：真实 analyst / reviewer dogfood、缺陷闭环、token/cost ROI 和 accepted / rejected deliverables。

下一阶段建议按 P11-P16 推进：`P11 Production Pilot Readiness Gate`、`P12 Durable Runtime + HIL + Resource Router`、`P13 Graph/Skill/Memory Lifecycle`、`P14 Data Ingestion + Retrieval Control Plane`、`P15 Enterprise Workbench Product Surface`、`P16 Quality Engineering + Online Eval Platform`。

## 4.2 P11 Production Pilot Readiness Gate

P11 closeout（2026-06-30）：`P11_L4_scope_pass_pilot_ready_execution_pending`。

- runtime contract：新增 `PilotProgram`、`PilotCaseCatalog`、`PilotReviewerProtocol`、`PilotReviewerAssignment`、`PilotSlaTarget`、`PilotBaselineObservation`、`PilotFeedbackChannel`、`PilotDogfoodFeedbackRecord`、`PilotDefectLifecycleRecord`、`PilotRollbackRehearsal`、`PilotCostRoiRecord`、`PilotAcceptanceRecord`、`PilotReadinessReport` 和 `PilotGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：S10 summary 和 post-S10 register `2/2` dependency pass；pilot case catalog `6` 个，覆盖 AI infra full research、non-US disclosure repair、product competitive graph、secondary-market capital feedback、research-to-quant validation、data-room deliverable；reviewer protocols `5` 个，assignments `12` 个；SLA targets `8` 个，S10 baseline observations `6` 个。
- feedback / ops：feedback channels `4`、dogfood feedback records `4`、defect lifecycle records `6`、rollback rehearsals `3`、cost / ROI records `3`、demand acceptance records `5`。
- 验证：P11 deterministic tests `5/5` pass；真实构建 gate `10 pass / 0 fail`；生成 `configs/r53_r60/p11_production_pilot_readiness_schema_v0_1.json`、`data/manifests/r53_r60_p11_production_pilot_readiness_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p11_production_pilot_readiness_l4_scope_pass.zh-CN.md`。

边界：P11 只证明 pilot 已准备到可执行状态，`pilot_readiness_status=ready_for_controlled_internal_pilot`；真实多用户 dogfood 仍未执行，`pilot_execution_status=not_started_requires_real_internal_pilot`，`full_product_release_status=not_l4_production_pass`。后续必须用真实 pilot run 填充 accepted / rejected workpapers、SLA / cost / feedback rows 和 reviewer acceptance，才能继续冲全系统生产级判断。

## 4.3 P12 Durable Runtime + HIL + Resource Router

P12 closeout（2026-06-30）：`P12_L4_scope_pass_runtime_drill_ready`。

- runtime contract：新增 `DurableRuntimeMetadata`、`RuntimeFacadeBinding`、`GraphNodeRuntimeBinding`、`CheckpointBridgeRecord`、`HumanInterruptRecord`、`HumanApprovalDecision`、`ResourceModelRoutePolicy`、`ResourceQueueEvent`、`ModelBudgetLedger`、`RuntimeReplayAttempt`、`TraceExportRecord`、`RuntimeAcceptanceRecord`、`RuntimeReadinessReport` 和 `RuntimeGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P11 dependency summary pass；runtime drill task `p12_runtime_drill_task_ai_infra_hil_resource_route` 经过 `research_lead_objective_contract`、`retrieval_evidence_operator`、`product_specialist_pack`、`lead_review_checkpoint`、`memo_logic_plan` 五个节点；`lead_review_checkpoint` 前保存 checkpoint、触发 human interrupt、经 human approval 后 resume，再完成 replay 和 trace export。
- resource / budget：route policies `4` 个，覆盖 `lead_planning_high_reasoning`、`retrieval_embedding_gpu_queue`、`specialist_analysis_balanced`、`memo_render_cost_controlled`；queue events `5` 条，budget record `1` 条且 within budget。
- replay / observability：checkpoint bridge `2` 条、replay attempt `1` 条、trace exports `3` 条（OpenTelemetry / Langfuse / Phoenix-style derived export），SQL runtime ledger 仍是 final audit source，外部 trace 只作派生观察。
- 验证：P12 deterministic tests `5/5` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/p12_durable_runtime_hil_resource_router_schema_v0_1.json`、`data/manifests/r53_r60_p12_durable_runtime_hil_resource_router_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p12_durable_runtime_hil_resource_router_l4_scope_pass.zh-CN.md`。

边界：P12 只证明 `FinSightResearchRuntimeFacade`、checkpoint/resume、HIL approval、resource/model router、replay 和 trace export 这些 durable runtime contract 已能通过 deterministic runtime drill 达到自身范围内 enterprise-grade；`full_runtime_migration_status=partial_migration_runtime_drill_only`，不声明所有 production LangGraph nodes 已迁移，也不证明云端高并发 GPU queue pressure。P13/P14/P15 必须把真实 graph / ContextEngine / data plane / Workbench 产品流接到同一 SQL-final runtime ledger。

## 4.4 P13 Graph / Skill / Memory Lifecycle

P13 closeout（2026-06-30）：`P13_L4_scope_pass_graph_skill_memory_lifecycle_ready`。

- runtime contract：新增 `GraphSkillMemoryLifecycleMetadata`、`CapabilityAssetInventory`、`AssetPatchProposal`、`AssetPatchEvalResult`、`AssetHumanApprovalRecord`、`TenantOverlayRecord`、`AssetCanaryRun`、`AssetPromotionRecord`、`AssetActiveVersion`、`AssetInvalidationRecord`、`ContextEngineInjectionPolicyRecord`、`AssetLifecycleAcceptanceRecord`、`AssetLifecycleReadinessReport` 和 `AssetLifecycleGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P13 读取 S4 已有 `GraphPack` / `SkillPack` / `MemoryPack` registry，不重做资产定义；本轮 materialize `28` 条 baseline asset inventory，其中 graph `6`、skill `16`、memory `6`。
- 生命周期链路：staged patch proposal `4` 条，覆盖 graph / skill / memory；其中 `p13_patch_skill_auto_revenue_from_deployment_blocked` 被 deterministic eval 挡住，`blocked_negative_patch_count=1`，不能进入 approval/canary/promotion。
- HIL / tenant / canary：human approval records `4` 条（`3` approved、`1` rejected），tenant overlay `3` 条且 `mutates_global_asset=0`，internal canary `3` 条且 `fail_count=0`。
- promotion / invalidation：promotion records `3` 条，active-version rows `3` 条，invalidation rows `4` 条，其中 rejected unsafe patch 进入 `candidate_invalidated_no_activation`。
- ContextEngine policy：为 `research_lead`、`fundamental_analyst`、`product_technology_analyst`、`industry_supply_chain_analyst` 生成 `4` 条 injection policy rows，固定 `exact_ref_policy=preserve_exact_refs_not_summaries` 和 `memory_fact_authority=memory_not_fact_authority`。
- 验证：P13 deterministic tests `6/6` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/p13_graph_skill_memory_lifecycle_schema_v0_1.json`、`data/manifests/r53_r60_p13_graph_skill_memory_lifecycle_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p13_graph_skill_memory_lifecycle_l4_scope_pass.zh-CN.md`。

边界：P13 只证明 GraphPack / SkillPack / MemoryPack 的 lifecycle control plane 在自身范围达到 enterprise-grade：staging、eval、approval、tenant overlay、canary、promotion、active version、rollback/invalidation 和 ContextEngine policy 都可审计、可回放、可被下游依赖。`lifecycle_rollout_status=controlled_lifecycle_drill_only`，不声明真实多租户 canary traffic 已跑，不允许 production agent 自行修改并提权 graph/skill/memory，也不声明所有 live LangGraph nodes 已动态读取这些 lifecycle policies。P14/P15/P16 必须把 data plane、Workbench 产品流和 online eval 继续接到这些 active capability versions。

## 4.5 P14 Data Ingestion / Retrieval Control Plane

P14 closeout（2026-06-30）：`P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready`。

- runtime contract：新增 `DataIngestionControlPlaneMetadata`、`SourceSnapshotRegistry`、`IngestionJob`、`RawSourceDocument`、`FetchAttempt`、`ParserRun`、`ParsedObjectRecord`、`AuthorityMappingRecord`、`IndexRefreshRecord`、`RetrievalStrategyPack`、`RetrievalBudgetRecord`、`RetrievalContextBridgeRecord`、`RetrievalQualityProbeRecord`、`DataQualityObservation`、`DatabasePerformanceProfile`、`IngestionLineageEdge`、`DataPlaneAcceptanceRecord`、`DataPlaneReadinessReport` 和 `DataPlaneGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P14 消费 S3 retrieval evidence spine 和 P13 ContextEngine policy，materialize source snapshots `6`、ingestion jobs `6`、raw documents `7`、fetch attempts `7`、parser runs `6`、parsed objects `8`、authority mappings `9`。
- parser / authority 边界：`p14_raw_unparsed_web_snapshot_blocked` 因缺 source-specific parser 被 fail-closed，`p14_authority_blocked_raw_snapshot_no_parser` 不能进入 context / ClaimCard / exact ledger；accepted authority modes 覆盖 exact company fact、technical fact、deployment signal 和 macro context。
- retrieval control plane：index refresh rows `5`，覆盖 `sql_exact`、`object_bm25`、`bm25`、`milvus_semantic`、`graph`；strategy packs `5`，覆盖 exact financial metric、product spec / architecture、customer deployment / adoption、capital funding / ownership、retrievable gap repair；retrieval budgets `20`，全部带 candidate / rerank / context quota。
- ContextEngine bridge / performance：为 `research_lead`、`fundamental_analyst`、`product_technology_analyst`、`industry_supply_chain_analyst` 生成 retrieval-context bridge `4` 条，全部绑定 P13 policy，固定 `exact_ref_policy=preserve_exact_refs_not_summaries`；DB/index/parser/context performance profiles `5` 条，lineage edges `53` 条。
- 验证：P14 deterministic tests `6/6` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/p14_data_ingestion_retrieval_control_plane_schema_v0_1.json`、`data/manifests/r53_r60_p14_data_ingestion_retrieval_control_plane_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p14_data_ingestion_retrieval_control_plane_l4_scope_pass.zh-CN.md`。

边界：P14 只证明 data ingestion / retrieval control plane 在自身范围达到 enterprise-grade：source snapshot、fetch、parser、authority mapping、index refresh、retrieval strategy budget、ContextEngine bridge、quality probes、lineage 和 performance profile 都可审计、可回放、可被下游依赖。`not_full_crawler_or_production_refresh=true`，不声明所有公开源/所有公司已经全量刷新，不声明云端生产级 p95/p99 SLA，也不声明所有 live graph nodes 已经动态读取 P14 strategy。P15/P16 必须把 Workbench 产品流和 online eval / ops dashboard 接到这些 data-plane rows。

## 4.6 P15 Enterprise Workbench Product Surface

P15 closeout（2026-06-30）：`P15_L4_scope_pass_enterprise_workbench_product_surface_ready`。

- runtime contract：新增 `EnterpriseWorkbenchProductSurfaceMetadata`、`WorkbenchProductSurfaceRegistry`、`EnterpriseApiSurfaceContract`、`FrontendInformationArchitecture`、`TaskCenterWorkflowRecord`、`EvidenceWorkbenchPanelRecord`、`WorkpaperBuilderPanelRecord`、`ReviewQueuePanelRecord`、`ArtifactBrowserRecord`、`DeliverableStudioPanelRecord`、`DataRoomUploadContract`、`AdminOpsConsolePanelRecord`、`ProductActionLedger`、`RbacProductPermissionCheck`、`FrontendE2EJourneyRecord`、`WorkbenchProductAcceptanceRecord`、`WorkbenchProductReadinessReport` 和 `WorkbenchProductGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P15 消费 S6 Workbench drilldown、S7 Deliverable Studio / Dashboard Projection、P14 data-plane rows，materialize enterprise product surfaces `9` 个：Task Center、Evidence Workbench、Workpaper Builder、Review Queue、Artifact Browser、Deliverable Studio、Dashboard Projection、Data Room Upload、Admin/Ops Console。
- API / IA / workflow：API contracts `9` 条、frontend IA nodes `9` 条；Task Center / Evidence / Workpaper / Review / Artifact / Deliverable / Upload / Admin Ops panel 均有 SQL-final projection row，且 Workpaper Builder / Review Queue 已对齐 S5 当前真实表 `workpaper_claim_cards`、`judgment_states`、`human_review_queue`。
- RBAC / action / journey：permission checks `5` 条，包含 positive 和 negative cases；product action ledger `8` 条；deterministic E2E journeys `5` 条，覆盖 junior 创建可审底稿、senior 审核、artifact trace to source、data room upload to provenance gate、admin ops incident / quality trace。
- 验证：P15 deterministic tests `6/6` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/p15_enterprise_workbench_product_surface_schema_v0_1.json`、`data/manifests/r53_r60_p15_enterprise_workbench_product_surface_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p15_enterprise_workbench_product_surface_l4_scope_pass.zh-CN.md`。

边界：P15 只证明企业 Workbench 产品面合同在自身范围达到 enterprise-grade：surface registry、API boundary、frontend IA、SQL-final projections、RBAC 正反例、action ledger、E2E journey、data-room provenance gate 和 known gaps 都可审计、可回放、可被 P16 依赖。`polished_react_frontend_not_implemented`、`real_multi_user_product_pilot_not_run` 和 `production_backend_framework_not_replaced` 仍保留为显式 gap；P15 不声明最终 React 视觉体验、真实多用户 pilot 或 Java/Spring production gateway 已完成。

## 4.7 P16 Quality Engineering + Online Eval Platform

P16 closeout（2026-06-30）：`P16_L4_scope_pass_quality_engineering_online_eval_ready`。

- runtime contract：新增 `QualityEngineeringMetadata`、`EvalDataset`、`EvalCase`、`EvalRun`、`EvalMetricResult`、`EvalGateResult`、`TraceSpan`、`ModelCallMetric`、`TokenCostLedger`、`RetrievalMetric`、`ParserMetric`、`ToolMetric`、`NodeEvalGateRecord`、`FailureEvent`、`RegressionCaseRecord`、`GoldPromotionRecord`、`QAExecutionPlan`、`DefectRecord`、`DemandAcceptanceRecord`、`SandboxRegressionRecord`、`BudgetExceededGate`、`CIGateRecord`、`EvalDashboardProjection`、`IncidentRecord`、`ReferenceSourceLedger`、`ReferenceChangeLedger`、`ReferenceAdoptionPerformanceProfile`、`QualityReadinessReport` 和 `QualityEngineeringGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P16 消费 S10 release-candidate eval/incident 子集、P14 parser/retrieval/data-plane rows 和 P15 product surface action/RBAC/journey rows，materialize EvalDataset `1`、EvalCase `6`、EvalRun `1`、EvalMetricResult `13`、EvalGateResult `13`。
- 节点/链路评测：E0-E12 `13` 个 node eval gates 全部 pass，覆盖 data/source、parser/chunk/table、DB/Gold Mart、retrieval/rerank、ContextEngine、tool/sandbox、Research Lead、specialist、Judgment、Workpaper、Deliverable、full-chain、online eval。
- observability / cost：trace spans `12`、model call metrics `5`、TokenCostLedger `5`、retrieval metrics `5`、parser metrics `6`、tool metrics `8`；BudgetExceededGate `2` 条，其中超预算路径必须 `pause_for_human_approval_or_scope_reduction`，禁止 silent overrun。
- lifecycle / QA / governance：failure events `4`、regression cases `3`、gold records `2`、QA plans `3`、defects `4`、R60 demand acceptance `18/18 pass`、sandbox regression `4`、dashboard projections `4`、incidents `6`、reference source/change/performance ledgers各 `7`。
- 验证：P16 deterministic tests `6/6` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/p16_quality_engineering_online_eval_schema_v0_1.json`、`data/manifests/r53_r60_p16_quality_engineering_online_eval_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p16_quality_engineering_online_eval_l4_scope_pass.zh-CN.md`。

边界：P16 只证明质量工程和 online-eval runtime contract 在自身范围达到 enterprise-grade：eval registry、E0-E12 gates、trace/cost、failure/gold/regression、QA/defect、sandbox/budget、reference governance、dashboard projection 和 readiness report 都可审计、可回放、可被下一阶段 pilot / frontend / CI 工作依赖。`sustained_online_eval_window_not_run`、`ci_cd_provider_integration_not_enabled` 和 `frontend_eval_dashboard_visual_qa_not_run` 仍保留为显式 gap；P16 不声明长期生产监控窗口、CI/CD provider 集成或最终前端 eval dashboard 已完成。

## 4.8 P17 Controlled Internal Pilot Execution

P17 closeout（2026-06-30）：`P17_L4_scope_pass_controlled_internal_pilot_execution_ready`。

- runtime contract：新增 `ControlledPilotMetadata`、`PilotExecutionBatch`、`PilotCaseExecution`、`PilotCaseStageCheckpoint`、`PilotCaseWorkpaperOutput`、`PilotCaseReviewerAction`、`PilotCaseEvalSnapshot`、`PilotCaseFeedbackRecord`、`PilotCaseDefectRecord`、`PilotCaseCostLatencyRecord`、`PilotCaseArtifactLink`、`PilotCaseReleaseDecision`、`PilotExecutionReadinessReport` 和 `PilotExecutionGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P17 消费 P11-P16 summary release decision，确认 `6/6` dependency pass；把 P11 的 6 个 pilot cases 全部生成 case-level runtime task，而不是只在 P17 主任务下写静态 summary。
- case execution：6 个 case runtime tasks 全部 `succeeded`；每个 case 通过 intake、retrieval/evidence、workpaper、lead review、deliverable projection、quality eval、feedback closeout 7 个 stage，共 `42` 个 stage checkpoints。
- review / eval / lifecycle：ReviewerAction `18` 条，覆盖 research lead、QA reviewer、domain reviewer；EvalSnapshot `6` 条全部 pass；FeedbackRecord `6`、DefectRecord `6`、CostLatencyRecord `6`、ArtifactLink `6`、ReleaseDecision `6`。
- cost / latency：pilot drill 总成本 `2.42` USD，max case latency `210000ms`，所有 case 均 `within_case_budget`；超预算路径继续由 P16 BudgetExceededGate 控制，不允许 silent overrun。
- 验证：P17 deterministic tests `6/6` pass；真实构建 gate `12 pass / 0 fail`；生成 `configs/r53_r60/p17_controlled_internal_pilot_execution_schema_v0_1.json`、`data/manifests/r53_r60_p17_controlled_internal_pilot_execution_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p17_controlled_internal_pilot_execution_l4_scope_pass.zh-CN.md`。

边界：P17 只证明 P11-P16 合同能被一轮受控内部 deterministic pilot execution 消费，并形成可审计、可回放、可评测的 case-level ledger。它关闭了 P11 的 `pilot_execution_status=not_started_requires_real_internal_pilot` 在“受控内部演练”层面的缺口，但仍不声明外部客户生产、长期云端 SLA、正式 CI/CD、polished React 前端或全系统 `L4_production_pass`。P18 已承接 P17 产物，把 deterministic case execution 转成内部 reviewer dogfood window、Workbench dashboard API 和 defect / feedback regression bridge。

## 4.9 P18 Internal Reviewer Dogfood Window

P18 closeout（2026-06-30）：`P18_L4_scope_pass_internal_reviewer_dogfood_window_ready`。

- runtime contract：新增 `InternalReviewerDogfoodMetadata`、`DogfoodWindow`、`DogfoodCaseAssignment`、`ReviewerSessionRecord`、`ReviewerActionEvent`、`PilotDashboardTile`、`PilotDefectPromotion`、`PilotFeedbackToRegression`、`PilotWorkbenchApiContract`、`PilotDogfoodReadinessReport` 和 `PilotDogfoodGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P18 消费 P17 controlled pilot execution ledger，确认 P17 dependency pass；把 P17 的 6 个 case execution 全部转成内部 reviewer assignments、reviewer sessions、action events、defect promotions 和 dashboard tiles。
- Workbench bridge：新增 `/api/r53-r60/pilot/dashboard`、`/api/r53-r60/pilot/cases`、`/api/r53-r60/pilot/cases/{case_id}` 三个 P18 API contract，并在 Workbench R53-R60 面板新增 Pilot dogfood window 区块，用于查看 case assignment、reviewer session、defect promotion、gate 和 API 状态。
- review / defect lifecycle：ReviewerActionEvent `18` 条，保留 P17 append-only action ledger；DefectPromotion `6` 条全部进入 `queued_for_p16_regression_lifecycle`；FeedbackToRegression `6` 条把 P17 feedback / defect 接到 P16 regression lifecycle，而不是把缺陷藏在 memo 边界说明里。
- dashboard / boundary：DashboardTile `7` 条，覆盖 window status、case assignments、reviewer sessions、review actions、defect promotions、cost/latency 和 release boundary；`real_human_adoption_status=pending_actual_reviewer_actions`，不虚报真实多人 dogfood 已完成。
- 验证：P18 deterministic tests `5/5` pass；真实构建 gate `11 pass / 0 fail`；生成 `configs/r53_r60/p18_internal_reviewer_dogfood_window_schema_v0_1.json`、`data/manifests/r53_r60_p18_internal_reviewer_dogfood_window_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p18_internal_reviewer_dogfood_window_l4_scope_pass.zh-CN.md`。

边界：P18 只证明内部 reviewer dogfood window 在自身范围达到 enterprise-grade：P17 case 可分派、可审查、可进入 Workbench dashboard、可追 defect / feedback / regression lifecycle，并且 API / SQL / Workpaper event / artifact trace 可复盘。它不声明真实人工 reviewer 已完成多日使用，不声明外部客户试点，不声明正式 CI/CD 或全系统 `L4_production_pass`。P19 已承接 P18，把只读 dogfood window 升级为可提交 reviewer action、可写入 P16 regression lifecycle 的 action-capture 闭环。

## 4.10 P19 Internal Reviewer Action Capture

P19 closeout（2026-06-30）：`P19_L4_scope_pass_internal_reviewer_action_capture_ready`。

- runtime contract：新增 `InternalReviewerActionCaptureMetadata`、`LiveReviewerActionWindow`、`LiveReviewerAction`、`LiveReviewerFeedbackRecord`、`LiveDefectTriageRecord`、`LiveRegressionPromotion`、`LiveGoldCandidatePromotion`、`LivePilotCaseStatus`、`LiveReviewerWorkbenchApiContract`、`LiveReviewerActionReport` 和 `LiveReviewerGateResult`，全部进入 S1 runtime SQLite 主账本。
- 真实构建：P19 消费 P16 quality / online-eval lifecycle 和 P18 dogfood window，确认 `2/2` dependency pass；对 P18 的 6 个 pilot case 执行 deterministic reviewer input drill，生成 `6` 条 live reviewer actions、`6` 条 feedback records、`6` 条 defect triage records 和 `6` 条 case status rows。
- Workbench action bridge：新增 `/api/r53-r60/pilot/actions`、`/api/r53-r60/pilot/cases/{case_id}/actions`、`POST /api/r53-r60/pilot/cases/{case_id}/review-actions` 三个 P19 API contract；Workbench Pilot dogfood window 增加 case 选择、review comment、comment / request repair / approve action 按钮和 P19 case-status / regression-promotion 投影。
- P16 regression lifecycle：`request_repair`、`return_to_specialist`、`downgrade_claim` 这类 repair action 不只停留在 P19 表，而是实际写入 P16 `failure_events_p16` 和 `regression_case_records_p16`；本轮 deterministic drill 生成 `3` 条 P16 live failure rows 和 `3` 条 P16 live regression rows。
- gold / adoption boundary：`approve` action 只进入 `candidate_pending_second_review` 的 gold candidate，不直接变成 final gold；`real_multi_day_human_adoption_status=pending_multi_day_human_dogfood`，不把 deterministic input drill 伪装成真实多日人工采用。
- 验证：P19 deterministic/API tests `5/5` pass；真实构建 gate `11 pass / 0 fail`；生成 `configs/r53_r60/p19_internal_reviewer_action_capture_schema_v0_1.json`、`data/manifests/r53_r60_p19_internal_reviewer_action_capture_*_v0_1.*` 和 `docs/internal/vnext_20260610/r53_r60_p19_internal_reviewer_action_capture_l4_scope_pass.zh-CN.md`。

边界：P19 只证明内部 reviewer action-capture 在自身范围达到 enterprise-grade：case action 可提交、可审计、可追 Workpaper event、repair feedback 可进入 P16 regression lifecycle、approval 需要二次审查后才能变成 gold。它不声明真实多人多日 dogfood 已经完成，不声明外部客户 pilot，不声明正式 CI/CD / production SLA / 全系统 `L4_production_pass`。下一步应进入 P20：真实 reviewer 多轮 dogfood 会话、feedback acceptance / rejection、缺陷关闭验证和 token/cost ROI 记录；同时补 P18/P19 前端浏览器视觉 E2E。

## 4.11 P20 DeepSeek Real-LLM Dogfood And P20b Root-Cause Hardening

P20 closeout（2026-06-30）：`P20_L4_scope_pass_real_llm_dogfood_gate_repair_ready`，但只限于真实 DeepSeek dogfood 和 gate repair 范围。

- 真实模型验证：完成 DeepSeek health smoke、Research Lead activation 2-case、Specialist real-evidence 2-case、AI infra full-chain 1-case dogfood，并把真实模型暴露的问题写入 P20 worklog。
- 已完成的 owned repair：token 截断处理、industry/supply-chain source-family gate、memo 内部字段泄漏、peer/context fact contamination、product/capex dimension mixing、investment-quality gate aggregation。
- 验证：targeted deterministic regression `150 passed`，`python -m compileall -q src\sec_agent scripts\eval_multi_agent tests` pass。

边界修正（用户复核后生效）：P20 的 gate repair 不能被解释为所有上游质量根因都已闭环。以下问题必须进入 P20b，完成前不得以“gate 已拦住”为由继续把同类错误视为已解决：

| P20b item | 根因位置 | 必须修到哪里 | 通过条件 |
| --- | --- | --- | --- |
| `P20b-D01-ambiguous-currency-scale-root` | exact/reconciliation 层允许大额裸 `usd` 进入 approved fact | source-scale / ambiguous-scale candidate 在 reconciliation 阶段被排除或带明确 scale lineage 后才可进入 approved fact | `excluded_ambiguous_currency_scale` 单测通过，memo selector gate 只作为回归保险 |
| `P20b-D02-numeric-display-lineage` | numeric display 可能丢失 source unit / scale / period lineage | renderer / writer 只能显示已解析 scale 的金额，不能把 source-scale 裸值渲染成美元金额 | 真实或 fixture case 证明 `77658.0 usd` 类错误不进入 rendered memo |
| `P20b-D03-memo-logic-plan-quality-root` | investment-quality gate 能拦坏输出，但 MemoLogicPlan / evidence-to-thesis bridge 仍可能只给模板化、gap-first 计划 | Research Lead / Supervising Analyst 在写作前必须形成 answer-first、dimension-linked、citation-backed MemoLogicPlan | 不只 eval gate pass，还要检查 writer 主输入里已有 thesis/counter-thesis/decision-changing evidence |
| `P20b-D04-source-doc-status-correction` | checklist / source docs 可能把 diagnostic、smoke、gate containment 写成 complete | 36、R60、checklist、相关 worklog 必须同步 status / boundary / next repair | 不存在“最小合同即通过”“gate 兜底即修复”的 stale wording |

2026-06-30 hardening update：`P20b-D01` 已前移到 `src/sec_agent/reconciliation_ledger.py`，大额裸 `usd` / `$` / `dollar(s)` currency facts 在 reconciliation candidate 阶段标记为 `excluded_ambiguous_currency_scale`，并由 `tests/test_metric_product_ontology_reconciliation.py` 回归覆盖。随后 `P20b-D02` 在 `src/sec_agent/d_series_fact_selection.py` 前移到 pre-memo selection 层，`ambiguous_currency_scale_not_memo_display_eligible` 不再进入 `approved_facts`；`P20b-D03` 在 `src/sec_agent/memo_logic_plan.py` 和 `src/sec_agent/memo_llm.py` 补齐 `answer_first_outline` / `evidence_to_thesis_bridge` 并进入 writer compact payload。P20b 四项 root-cause hardening 当前均已关闭；P22 已关闭 source-doc status drift blocker。2026-07-01 P25/B05 closeout 后，P21 一度只剩 B04 阻塞；同日 product-owner acceptance 又关闭 B04，使 P21 broad full-chain gate 不再被这些五项 blocker 阻断。

P20b closeout 必须执行 root-cause-first 顺序：复现症状 -> 定位最早 faulty artifact -> 修 parser/normalizer/reconciliation/planner/writer 输入 -> 保留 gate 做回归保护 -> 加 deterministic regression -> 更新源文档和 checklist。若根因未找到，只能标记 `blocked_root_cause_unknown` 或 `partial_diagnostic`，不得升级为 `L4_scope_pass`。

## 4.12 PRD/R 系列源文档回扫审计（2026-06-30）

按更新后的 project-worklog 规则，S/P closeout 不能替代 PRD/R 源文档，也不能把 smoke、最小合同、diagnostic gate 或 gate containment 当作完成。本轮回扫 PRD、R53-R60、S0-S10、P11-P20/P20b 和 `data/manifests/r53_r60_*` 后，结论如下：

1. S0-S10/P11-P20 不是“没做”，它们已经留下 scope-level contracts、SQL rows、gate artifacts、Workbench/API contracts、eval/trace/control-plane rows。
2. 但当前仍不是 PRD-level product complete 或 full enterprise production pass；很多 slice 只是自身范围内的 `L4_scope_pass`，并保留真实生产/试点边界。
3. 最大源文档漏项是 machine-readable source-of-truth drift：`r53_r60_demand_map_v0_1.jsonl` 仍是 `planned=57 / ready_for_implementation=4`，`r53_r60_implementation_tasks_v0_1.jsonl` 仍是 `planned=171 / ready_for_implementation=12`，`r53_r60_release_board_v0_1.jsonl` 仍是 `blocked_by_dependencies=10 / ready_to_start=1`。这些不能直接给后续自动化当当前状态用。
4. P20b 的 `P20b-D02-numeric-display-lineage` 和 `P20b-D03-memo-logic-plan-quality-root` 已在 P21/P20b 后续修复中关闭；后续不能再把同类问题交给 renderer / eval gate 兜底，而应继续按 earliest faulty artifact 修。
5. R57/R58/R55/R59/R60 的 source-doc current-status / closeout reconciliation 已由 P22 补齐：源文档现在都有 `P22 Current Status Reconciliation`，并用机器可读 rows 映射 done / partial / boundary / next action；后续不再把这些源文档当作“未执行计划”，但 partial 行仍不能冒充产品级完成。

| Audit item | 当前判断 | 必须补的动作 |
| --- | --- | --- |
| `AUD-01-source-status-parity` | S0 machine-readable backlog/release board stale | 生成 current-status overlay 或重建 demand/release board，并加 parity test |
| `AUD-02-p20b-root-cause` | closed 2026-06-30 | 已修 numeric display lineage 和 MemoLogicPlan upstream quality；保留回归测试 |
| `AUD-03-source-doc-reconciliation` | closed by P22 2026-06-30 | 已对 R55/R57/R58/R59/R60 建 73 条 done/partial 映射、源文档 current-status section 和 gate summary；后续维护这些 rows，不再依赖旧 planned wording |
| `AUD-04-prd-product-acceptance` | P17-P19 是 controlled deterministic / reviewer-action drill，不是真实多人多日产品采用 | 跑真实 reviewer sessions、accepted/rejected deliverables、defect closure、token/cost ROI |
| `AUD-05-frontend-workbench-e2e` | P15 是 product surface contract/projection，不是 polished React release | 做浏览器视觉 E2E 和用户流验收 |
| `AUD-06-runtime-live-migration` | P12 是 runtime drill，不是全 graph 迁移 | 迁移真实 LangGraph execution paths，补 replay/resume/parity tests |
| `AUD-07-data-rag-live-refresh` | P14 是 control plane，不是 full crawler / production refresh | 接真实 refresh jobs、parser coverage、qrels、DB perf profile 和 source adapter coverage |
| `AUD-08-secondary-quant-deliverable-depth` | S8/S9/S7 是 bounded scope pass | 二级市场、量化实验、Deliverable Studio 继续按 typed gap 和 source authority 补深度 |

建议下一轮不要直接开新大功能，而是按以下顺序做：`P23-real-product-dogfood-and-frontend-e2e` -> `P24-runtime-data-live-integration` -> `P25-data-depth-and-secondary-market-closure`。P22 已完成 source-doc status reconciliation，只关闭源文档漂移，不代表真实产品 dogfood / data-depth / runtime live migration 完成。

详细审计记录见 `docs/worklog/product_strategy/046_prd_rseries_s_p_closeout_audit.md`。

## 4.13 P21 Pre-Full-Chain Blocker Gate（2026-06-30）

根据用户复核，4.12 的 5 条不能被解释成“后续深挖可选项”。在它们关闭前，20-50 个 broad full-chain case 只能做 orchestration / integration smoke，不能作为研报质量、产品验收或上线依据。

P21 已新增机器可读 blocker gate：

- schema：`configs/r53_r60/p21_pre_full_chain_blocker_gate_schema_v0_1.json`
- current status overlay：`data/manifests/r53_r60_current_status_overlay_v0_1.jsonl`
- current release board：`data/manifests/r53_r60_current_release_board_v0_1.jsonl`
- blocker rows：`data/manifests/r53_r60_p21_pre_full_chain_blockers_v0_1.jsonl`
- gate rows：`data/manifests/r53_r60_p21_pre_full_chain_blocker_gate_rows_v0_1.jsonl`
- summary：`data/manifests/r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json`
- report：`docs/internal/vnext_20260610/r53_r60_p21_pre_full_chain_blocker_gate.zh-CN.md`

真实构建结果：

| Field | Value |
| --- | --- |
| `status` | `pass` |
| `closeout_level` | `L4_scope_pass_for_blocker_registration_only` |
| `full_chain_broad_eval_allowed` | `false` |
| `blocker_count_open` | `1/5` latest after P25/B05 closeout |
| `allowed_while_blocked` | `deterministic_node_tests`, `pack_level_tests`, `targeted_full_chain_smoke_for_integration_only` |
| `not_allowed_while_blocked` | `20_50_case_full_chain_quality_claim`, `product_release_claim`, `automation_from_stale_release_board` |

注意：P21 的 pass 只代表“阻塞项登记、current status overlay 和 broad full-chain 禁止规则”达到了自身范围的 L4-grade。它关闭 `B01-machine-readable-backlog-status-parity`、`B02-p20b-owned-root-cause-open`，并在 P22 通过后关闭 `B03-r-source-doc-status-reconciliation`；2026-07-01 P25/B05 closeout 又关闭 `B05-depth-packs-before-broad-full-chain`。当前剩余 blocker 只有 `B04-prd-product-acceptance-not-met`，下一步仍应优先完成真实 reviewer acceptance / defect closeout，而不是把 broad full-chain 结果宣传为 full product pass。

## 4.14 P22 Source-Doc Status Reconciliation（2026-06-30）

P22 目标是关闭 `B03-r-source-doc-status-reconciliation`：把 R55/R57/R58/R59/R60 的源文档从“旧计划/旧缺口描述”更新成当前可审计状态。P22 不声明 Deliverable Studio、memory/context、RAG/data pipeline、backend/frontend 或 eval/observability 已达到全产品生产通过；它只声明这些源文档的 demand/status rows 已经可机器读取、可追责、可被后续 slice 依赖。

新增/更新 artifacts：

- schema：`configs/r53_r60/p22_source_doc_status_reconciliation_schema_v0_1.json`
- source status rows：`data/manifests/r53_r60_p22_source_doc_status_rows_v0_1.jsonl`
- gate rows：`data/manifests/r53_r60_p22_source_doc_status_gate_rows_v0_1.jsonl`
- summary：`data/manifests/r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json`
- report：`docs/internal/vnext_20260610/r53_r60_p22_source_doc_status_reconciliation_l4_scope_pass.zh-CN.md`
- builder：`scripts/engineering/build_r53_r60_p22_source_doc_status_reconciliation.py`
- tests：`tests/test_r53_r60_source_doc_status_reconciliation.py`

真实构建结果：

| Field | Value |
| --- | --- |
| `status` | `pass` |
| `closeout_level` | `L4_scope_pass_for_source_doc_reconciliation_only` |
| `source_doc_status` | `reconciled` |
| `row_count` | `73` |
| `status_counts` | `done=34`, `partial=39` |
| `open_source_doc_status_rows` | `0` |
| `gate_count` | `7 pass / 0 fail` |
| `full_chain_broad_eval_allowed` | `false` |
| `release_decision` | `P22_source_docs_reconciled_broad_full_chain_still_blocked` |

R-series source-doc current status 分布：

| Source doc | Done rows | Partial rows | P22 边界 |
| --- | ---: | ---: | --- |
| R55 Deliverable Studio / Dashboard Projection | 2 | 6 | artifact/render trace 已有；多格式导出、可视化、模板治理和真实产品验收仍属 P23/P24 |
| R57 Graph / Skill / Memory | 5 | 8 | registry/patch/memory gates 已有；selector、tenant overlay、ContextEngine lifecycle、compression artifact 仍 partial |
| R58 DB / RAG / Retrieval / Data Pipeline | 9 | 5 | SQL/Milvus/parity/control-plane 已有；qrels、rerank、crawler/adapter depth、SLA/perf 仍 partial |
| R59 Backend / Frontend / Workbench | 7 | 13 | task ledger/callback/SSE/projections 已有；polished UI、auth/RBAC、load/SLA、live migration、visual E2E 仍 partial |
| R60 Eval / Observability / Incident / Fallback | 11 | 7 | eval registry/gates/failure lifecycle 已有；online eval、release readiness、cost/SLA trends、dashboard product acceptance 仍 partial |

P22 通过后，P21 blocker summary 当时更新为 `blocker_count_open=2/5`。当时剩余 blocker 是：

- `B04-prd-product-acceptance-not-met`
- `B05-depth-packs-before-broad-full-chain`

2026-07-01 supersession：后续 P25/B05 root-cause closeout 已关闭 `B05-depth-packs-before-broad-full-chain`。在 B04 正式验收前，P21 summary 一度是 `blocker_count_open=1/5`，只剩 `B04-prd-product-acceptance-not-met`；同日 product-owner acceptance 写入 formal evidence ledger 后，最新 P21 summary 已更新为 `blocker_count_open=0/5`。

## 4.15 P23 Product Dogfood / Frontend E2E Readiness（2026-06-30）

P23 目标是推进 `B04-prd-product-acceptance-not-met` 中可自动化验证的产品链路部分：确认 Workbench 从 task center、drilldown、review queue、deliverables、dashboard projection 到 pilot dogfood/action ledger 的后端 API 和前端 route/component/build contract 真实可用。P23 不关闭真实人工 dogfood / 产品验收 blocker。

新增/更新 artifacts：

- schema：`configs/r53_r60/p23_product_dogfood_frontend_e2e_schema_v0_1.json`
- API journey rows：`data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_api_journey_rows_v0_1.jsonl`
- frontend check rows：`data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_frontend_check_rows_v0_1.jsonl`
- gate rows：`data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_gate_rows_v0_1.jsonl`
- summary：`data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json`
- report：`docs/internal/vnext_20260610/r53_r60_p23_product_dogfood_frontend_e2e_scope_pass_human_pending.zh-CN.md`
- builder：`scripts/engineering/build_r53_r60_p23_product_dogfood_frontend_e2e.py`
- tests：`tests/test_r53_r60_product_dogfood_frontend_e2e.py`

真实构建结果：

| Field | Value |
| --- | --- |
| `status` | `pass_with_human_acceptance_blocked` |
| `closeout_level` | `L4_scope_pass_for_automated_product_journey_only` |
| `release_decision` | `P23_automated_product_journey_pass_human_dogfood_pending` |
| `dependency_fail_count` | `0/5` |
| `api_journey_fail_count` | `0/14` |
| `frontend_fail_count` | `0/13` |
| `frontend_warn_count` | `0/13` |
| `gate_fail_count` | `0/7` |
| `product_acceptance_status` | `blocked_requires_real_human_review` |
| `b04_status_after_p23` | `open_product_acceptance_required` |
| `full_chain_broad_eval_allowed` | `false` |

P23 修复过一个真实入口问题：builder 脚本环境只把 `src` 放进 import path，导致 `apps.workbench.backend.app` 在真实运行中不可导入。该问题已在 P23 API journey 中修为显式 repo-root import path contract，并由 `tests/test_r53_r60_product_dogfood_frontend_e2e.py` 覆盖。

P23 自动化 API journey 会写入 `reviewer_role=automation_e2e` 的 action，用于证明 review action write path 可用；该 action 不计入真人 adoption。P21 已回读 P23 summary，当时仍保持 `blocker_count_open=2/5`。2026-07-01 后续 P25/B05 closeout 将 P21 更新为 `blocker_count_open=1/5`；随后 B04 通过真实 product-owner session evidence 关闭。

## 4.16 P24 / B04 Product Acceptance Gate（2026-06-30）

P24 目标是把 `B04-prd-product-acceptance-not-met` 中“产品验收底座”做成可审计运行面：真实浏览器 Workbench visual E2E、真实 reviewer 验收协议、human evidence requirement、defect closeout requirement、acceptance decision placeholder，以及 P21 对 P24 summary 的回读。P24 不关闭 B04；它只证明产品验收基础设施达到自身范围内的 `L4_scope_pass`。

新增/更新 artifacts：

- schema：`configs/r53_r60/p24_b04_product_acceptance_gate_schema_v0_1.json`
- protocol rows：`data/manifests/r53_r60_p24_b04_product_acceptance_protocol_rows_v0_1.jsonl`
- browser E2E rows：`data/manifests/r53_r60_p24_b04_browser_e2e_rows_v0_1.jsonl`
- human evidence rows：`data/manifests/r53_r60_p24_b04_human_evidence_requirements_v0_1.jsonl`
- defect closeout rows：`data/manifests/r53_r60_p24_b04_defect_closeout_requirements_v0_1.jsonl`
- decision rows：`data/manifests/r53_r60_p24_b04_acceptance_decision_rows_v0_1.jsonl`
- gate rows：`data/manifests/r53_r60_p24_b04_product_acceptance_gate_rows_v0_1.jsonl`
- summary：`data/manifests/r53_r60_p24_b04_product_acceptance_summary_v0_1.json`
- report：`docs/internal/vnext_20260610/r53_r60_p24_b04_product_acceptance_gate_human_pending.zh-CN.md`
- builder：`scripts/engineering/build_r53_r60_p24_b04_product_acceptance_gate.py`
- reviewer evidence CLI：`scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py`
- Workbench API：
  - `GET /api/r53-r60/product-acceptance/evidence`
  - `POST /api/r53-r60/product-acceptance/evidence`
- tests：`tests/test_r53_r60_product_acceptance_b04_gate.py`

真实构建结果：

| Field | Value |
| --- | --- |
| `status` | `pass_with_real_human_acceptance_blocked` |
| `closeout_level` | `L4_scope_pass_for_product_acceptance_infrastructure_only` |
| `release_decision` | `P24_b04_product_acceptance_infrastructure_ready_human_review_pending` |
| `browser_e2e_status` | `pass` |
| `browser_e2e_fail_count` | `0/10` |
| `gate_fail_count` | `0/7` |
| `gate_blocked_count` | `2/7` |
| `human_evidence_pending_count` | `5` |
| `defect_closeout_pending_count` | `8` |
| `product_acceptance_status` | `pending_real_human_acceptance` |
| `b04_status_after_p24` | `open_product_acceptance_required` |
| `full_chain_broad_eval_allowed` | `false` |

P24 期间修复/明确的真实入口问题：

1. Workbench backend 现在支持 `FINSIGHT_WORKBENCH_REPO_ROOT`，用于浏览器 E2E 在隔离 root 中跑真实 API；默认仓库路径不变。
2. P24 uvicorn 子进程显式注入 repo root 和 `src`，避免子进程找不到 `sec_agent`。
3. Playwright browser executable resolver 会优先使用 Playwright Chromium，缺失时使用系统 Chrome/Edge。
4. SPA visual E2E 改为 `domcontentloaded` + body label polling + desktop/mobile viewport resize，不再用容易卡住的 `networkidle`。
5. `/api/r53-r60/pilot/actions` 已经单独验证在 uvicorn 下约 26ms 返回；P24 API probe 前置到 browser visual 之前，避免 post-browser probe 对同一 server 造成测试性干扰。

P21 已回读 P24 summary，当时仍保持 `blocker_count_open=2/5`。2026-07-01 后续 P25/B05 closeout 后，P21 一度更新为 `blocker_count_open=1/5`。同日 B04 closing contract 又做了 root-cause hardening：B04 不能再只凭 P24 summary 字段关闭；P24 必须从 `r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl`、human evidence rows、defect closeout rows、decision rows 和 gate rows 派生 accepted 状态，P21 必须校验 `p24_manifest_acceptance.valid=true` 后才允许 `B04=closed_by_p24_real_human_product_acceptance`。该 hardening 后，正式 product-owner evidence 已写入并关闭 B04。

2026-07-01 follow-up：B04 不再要求 reviewer 手工改 JSONL。`src/sec_agent/r53_r60_product_acceptance_b04_gate.py` 新增 `validate_real_reviewer_acceptance_evidence` / `append_real_reviewer_acceptance_evidence` / `get_product_acceptance_evidence_status`，并接入 Workbench API 和 CLI。正式入口只接受 `action_source=real_human`、白名单 reviewer role、完整 `reviewer_session` / `deliverable_acceptance` / `defect_closeout` / `visual_acceptance` / `audit_replay` 行；automation 或不完整行会被拒绝。这个改动只补齐 B04 验收证据入口，不伪造真实验收，不关闭当前 B04。

2026-07-01 follow-up 2：`Product acceptance evidence` 已接入 R53-R60 Workbench 前端，并纳入 P24 browser label gate。当时 P24 browser E2E 为 `10/10`，`gate_fail_count=0/7`，P21 为 `blocker_count_open=1/5`，唯一剩余 blocker 是 `B04-prd-product-acceptance-not-met`。该 UI 入口只负责让真实 reviewer 记录证据，不能替代真实 reviewer dogfood / deliverable acceptance / defect closeout；后续正式 product-owner evidence 已经通过该合同关闭 B04。

2026-07-01 follow-up 3：新增 P27 B04 real-reviewer acceptance package，补齐真实 reviewer 的执行包而不是再补自动化兜底。`src/sec_agent/r53_r60_b04_reviewer_acceptance_package.py` 和 `scripts/engineering/build_r53_r60_p27_b04_reviewer_acceptance_package.py` 从 P24 human requirements / defect closeout rows / runtime task-artifact-trace refs 生成 reviewer step rows、template-only evidence rows、candidate refs 和人读报告。当前 P27 构建结果：`review_step_count=5`、`evidence_template_count=13`、`reviewer_candidate_ref_count=36`、`real_reviewer_evidence_row_count=0`、`does_not_close_b04=true`。因此 P27 只解决“真实 reviewer 怎么审”的操作问题，不关闭 B04，也不允许 broad full-chain product pass。

2026-07-01 follow-up 4：新增 P28 B04 acceptance session-readiness layer。`src/sec_agent/r53_r60_product_acceptance_b04_gate.py` 现在按 `session_id` 聚合真实 reviewer evidence，检查五类必需证据、accepted deliverable、P24 defect source id coverage，并在 `get_product_acceptance_evidence_status` 返回 `session_readiness.sessions` / `ready_sessions` / `ready_session_count`。同时 B04 closeout 被收紧为“同一 ready session 的 accepted deliverable 才能生成 acceptance decision”，不能用多个不同 session 的 evidence 混合关闭 B04。Workbench `Product acceptance evidence` 面板显示 Ready sessions 和 Session readiness 表格，避免 reviewer 提交部分 evidence 后不知道还缺什么。P28 只增强真实验收操作闭环，不写入真实 reviewer evidence，不关闭 B04。

2026-07-01 follow-up 5：新增 P29 B04 reviewer package Workbench surface。`src/sec_agent/r53_r60_b04_reviewer_acceptance_package.py` 现在提供 `get_b04_reviewer_acceptance_package`，Workbench 后端新增 `GET /api/r53-r60/product-acceptance/reviewer-package`，前端 `Product acceptance evidence` 面板展示 reviewer execution steps、template-only evidence rows、task/artifact/trace candidate refs、P27 report path 和 package status。这个入口只让真实 reviewer 能在产品验收面板里执行 P27 package，不把 package/template rows 计为真实验收 evidence；因此在 `real_reviewer_evidence_row_count=0` 的 P29 当时，B04 仍保持 open。后续正式 product-owner evidence 写入后，该 blocker 已关闭。

2026-07-01 follow-up 6：用户作为 product owner 明确认可 B04 closeout packet 后，正式验收证据写入 `data/manifests/r53_r60_p24_b04_real_reviewer_acceptance_evidence_v0_1.jsonl`，同一 session 覆盖 `reviewer_session` / `deliverable_acceptance` / `defect_closeout` / `visual_acceptance` / `audit_replay` 五类必需证据。重新构建后，P24 summary 为 `status=pass`、`b04_status_after_p24=closed_by_real_human_product_acceptance`、`human_evidence_pending_count=0`、`defect_closeout_pending_count=0`、`accepted_decision_count=1`、`full_chain_broad_eval_allowed=true`。P21 同步修复 release-decision 根因：当 `blocker_count_open=0` 时不再保留 stale blocked release decision；最新 P21 summary 为 `release_decision=P21_pre_full_chain_blockers_closed_broad_full_chain_allowed`。

## 4.16.1 P30 Workbench Product Surface Redesign（2026-07-01）

P30 目标是把 R53-R60 Workbench 从 raw gate / manifest / artifact 表格堆叠，推进到 analyst-facing 的产品工作台首版。这个 slice 不宣称完成最终 B 端设计系统，但必须消除“工程调试台”体验里最阻碍产品使用的结构问题。

实现内容：

- 前端 `R53R60WorkbenchPanel` 拆为 `Analyst` / `Review` / `Deliverables` / `Ops` 四个 surface。
- `Analyst` surface 提供 Task queue、Workpaper canvas、Evidence drawer，并把 Lead judgment、Judgment state、Workpaper outline、ClaimCards、Typed gaps、Review actions 组织到同一个研究任务视角下。
- `Review` surface 汇总 Product acceptance evidence、reviewer package、pilot dogfood window。
- `Deliverables` surface 汇总 Deliverable Studio、Dashboard Projection、quality gates 和 artifacts。
- `Ops` surface 汇总 Ops projection、gate rows、scope gate 和 trace/rollback 状态。
- 修复旧空态根因：当暂无 SQL-final task projection 时，旧代码提前返回“等待 S6 投影”，导致新工作台不可见；现在产品 shell 始终渲染，并在 task rail 内显示明确空态。

验收：

- TypeScript + Vite build pass。
- Playwright element-level QA pass：`Analyst` / `Review` / `Deliverables` / `Ops` 文本检查均通过。
- `等待 S6 投影` 旧空态从 P30 面板中移除。
- 截图保存到 `D:/temp/finsight_p30_qa/p30_panel_desktop_*.png` 和 `D:/temp/finsight_p30_qa/p30_panel_mobile_analyst.png`。

2026-07-02 P30 full-chain cost discipline update：P30 真实 AI/Semis case 暴露出 full-chain 回归过早、specialist 扇出过宽、specialist 输入过胖、claim yield 过低和缺少硬 token budget gate 五个执行问题。当前口径调整为：任何 paid full-chain 之前必须先通过 deterministic / node-level tests 和 token-budget preflight；`L0/L1` 级别问题不得靠 paid rerun 发现。实现侧已经新增 token-budget plan / `--token-budget-preflight-only` / `--allow-expensive-llm` / run-case-paid-call budget blocking，specialist 激活默认按 required item / explicit user intent / visible core evidence 精准触发，ProductSpecPack / CapitalMacroPack / FundamentalStatementPack / FundamentalPeerStatementPanel 进入 specialist prompt 前必须 role-specific compact。两条 AI/Semis case 的 no-paid preflight 当前为 `blocked_preflight_token_budget`：估算 `272000` tokens、`18` paid calls，超过默认 `180000` run budget 和 `8` paid-call cap。因此下一次 DeepSeek full-chain 不允许直接跑；必须先做 deterministic pruning / coalescing，或由用户显式批准 expensive-run override。

2026-07-02 product-level reclassification：上述问题被升级为 `Agent Information Economy`，不是单纯省 token。P30/P31 后续必须证明 agent 框架能把上下文、证据、工具调用和 specialist 协作转化为 WorkpaperEvent、ClaimCard、JudgmentState、MemoLogicPlan 和可读判断。高 token / 低 insight 是 agent planning、context selection、信息传输、specialist scope、repair loop 或 writer contract 的质量缺陷。后续需求单应新增或补齐 `AgentInformationEconomyLedger`、`InformationTransferQualityGate`、`SpecialistYieldGate`、`RepairLoopRootCauseGate` 和 Workbench token-to-insight projection；pass 条件不能只是 "under budget"，还必须证明低重复输入、高有效产出、低无效 repair 和高 required-item answer density。

2026-07-02 deterministic runtime update：`AgentInformationEconomyLedger` 首版已落到 `src/sec_agent/agent_information_economy.py`，并接入 `eval_multi_agent_real_llm_chain.py`。每次 real-chain eval 会在 `output_quality_audit` 后生成 `agent_information_economy_audit.json/.md`；preflight-only 也会生成 `agent_information_economy_preflight.json`，在付费模型调用前暴露高 token、paid-call fanout、specialist fanout 风险。该 ledger 目前复用已保存的 token stats、specialist stats、ClaimCard stats、quality flags 和 sidecar 摘要，能定位 `high_token_low_supported_claim_yield`、`high_token_low_rendered_claim_yield`、`overbroad_specialist_fanout`、`invalid_information_transfer_proxy`、`duplicate_evidence_ref_transfer_proxy`、`repair_loop_agent_failure_proxy` 等问题。随后把 case contract 拆成 `expected_specialist_agents`（研究覆盖期望）、`expected_paid_specialist_agents`（本轮付费激活期望）和 `expected_paid_specialist_priorities`（primary/supporting 输入预算），让 preflight 不再把所有质量覆盖 specialist 都直接计费。两条 AI/Semis case 仍保留 5 个研究覆盖 specialist，但 paid 清单剪掉非核心的 `market_valuation_analyst`，并把 `risk_counterevidence_analyst` 降为 supporting 输入包；两 case no-paid preflight 从 `272000` / `18` paid calls 降至 `239200` / `16` paid calls。单 case preflight 为 `119600` / `8` paid calls，已低于默认 `120000` per-case budget 且 AIE case gate pass；两 case 同批仍因 `180000` run budget 和 `8` paid-call cap blocked。runtime activation audit 也已修复：`market_snapshot` source tier 现在只触发 `market_operator`，不再自动升级为 `market_valuation_analyst`；两个真实 AI/Semis catalog case 的 deterministic active specialists 已与 `expected_paid_specialist_agents` 完全一致。因此下一次 DeepSeek 实测只能先单 case 跑，不能再合批两个 deep case。边界：精确跨 agent prompt-token overlap、Workbench UI 投影、真实 paid full-chain product closeout 尚未完成，不能替代下一步真实单 case 回归和输出质量审计。

2026-07-02 prompt-pack fingerprint update：AIE 继续向“信息传输质量”推进。`specialist_route_results` 现在记录 `input_pack_fingerprint`，只保存 component digest、known evidence refs、row count 和 approximate payload chars，不保存完整 prompt 文本。`AgentInformationEconomyLedger` 会消费这些 fingerprint，识别多个 specialist 拿到相同 component digest 或高重叠 evidence refs 的 `prompt_pack_overlap_proxy`，并把根因指向 `specialist_input_pack_deduplication_or_coalescing`。这解决了此前只能用全局 evidence-ref 重复作为弱 proxy 的问题；随后 `capital_macro_pack` prompt 输入从整包复制改为 role projection：fundamental 只看资本结构相关 section，industry 只看 macro / exposure / vertical official sections，risk 只看 debt / macro / rejected risk sections，避免三个 specialist 重复阅读同一 capital/macro 大包。Memo Writer 侧也新增 `memo_route_result.input_pack_fingerprint`，覆盖 pass、salvage 和 blocked route，只记录 digest、item/ref count、approx payload chars、memo profile 和 response language；Verifier 侧新增 `verifier_input_pack_fingerprint`，证明它只看 final memo / referenced ClaimCard projection、allowed refs、source-boundary notes 和 deterministic verification summary。Research Lead 侧新增 request scope / source inventory / context / loop budget / registry / route-choice policy 的 digest-only fingerprint；Universe Relationship 侧新增 activation plan / compact relationship lookup prompt view / known relationship refs / source-inventory summary 的 digest-only fingerprint。`langgraph_orchestrator` 将两者落入 state 和 `llm_routes`，eval runner 将两者带入 `agent_audit`。AIE markdown 现在显示 lead/universe/Memo/Verifier refs 和 payload chars，用于定位 planner、relationship、writer/verifier 输入是否过胖或证据引用过少。对应 no-paid regression 最新 `41 passed`。当前仍不保存完整 prompt 文本；如后续需要精确 duplicate-token overlap，只能做 opt-in token meter。

2026-07-02 token-budget estimator v0.2：预算门控不再使用完全静态的旧 deep-research 上界，而是标记为 `role_projected_compact_prompt_budget_v0_2`，反映 role-specific specialist pack projection 和 Memo Writer `writer_thesis_skeleton_first_compact_verified_inputs` 合同。单个 AI infra case 的 no-paid preflight 当前为 `allowed`，估算 `101400` tokens / `8` paid calls；两个 AI/Semis deep case 合批仍是 `blocked_preflight_token_budget`，估算 `202800` tokens / `16` paid calls，超过 run-level `180000` tokens 和 `8` paid-call cap。该估算仍不是实际 token meter；下一次有效单 case 后必须把实际模型调用 token、AIE ledger 和 data/script audit 对齐。

2026-07-02 data/script root-cause update：用户复核指出，P30 当前不能再把问题归结为“多跑 full-chain / 多加 gate”。本轮新增 `DataScriptQualityAudit`，把 full-chain 已保存 artifacts 作为离线输入，在不调模型、不检索、不联网的情况下审计项目自有链路是否能解释输出质量。该 audit 已接入 `eval_multi_agent_real_llm_chain.py`，每次真实 eval 会生成 `data_script_quality_audit.json/.md`，并在发现 owned data/script defect 时把 `data_script_quality_gate` 标为 fail。当前离线复盘 `20260702_p30_root_cause_repair_ai_semis_r2` 显示：AI infra case 有 `4` 个 required items 属于 `available_not_rendered`，不是公开源缺失；两个 AI/Semis case 都缺 `memo_logic_plan.json` artifact，导致 writer 为什么漏证据不可 replay；AI infra case 触发 `deterministic_salvage_used` 且最终只渲染一句 bounded answer；semicap case 仍有 `source_route_scope_false_gap_present` 和非美披露 parser/root-cause rows。这些均归为项目内 root-cause repair，不允许被 broad full-chain 或 paid rerun 掩盖。`langgraph_orchestrator` 已补 `memo_logic_plan` artifact ref，并修复 renderer 在 verifier fail 时直接吞掉可渲染 memo 的问题：如果 memo 已有 `direct_answer` / `memo_claims` / dimension rows，即使 gate 仍 fail，也会渲染 bounded memo 供审阅，而不是替换成一句固定失败语。后续 paid 单 case 之前必须先让离线 data/script audit 不再报 `memo_logic_plan_artifact_missing`、`required_item_available_not_rendered`、`memo_writer_deterministic_salvage_used`、`product_evidence_available_not_rendered`、`owned_parser_locator_gap_present` 或 `source_route_scope_false_gap_present` 等阻塞项。换言之：下一步不是立即跑 DeepSeek，而是先用 deterministic / artifact-level repair 修到 audit 解释链路闭合。

2026-07-02 data/script deterministic repair follow-up：在上述离线复盘后，P30 已先修 owned artifact/projection 问题，而不是直接付费 rerun。`memo_writer` 现在会在 writer 输出缺失时把 active `MemoLogicPlan` 嵌入 `memo_answer`；`memo_logic_plan.json` 持久化会按 `state.memo_logic_plan -> memo_answer.memo_logic_plan -> multi_agent_summary.memo_logic_plan` 顺序恢复，并记录 `artifact_persistence.source`，让后续审计能区分 standalone artifact persistence 缺陷和真正的 plan generation/state-loss。`DataScriptQualityAudit` 也已区分 `memo_logic_plan_standalone_artifact_persistence` 与 `memo_logic_plan_generation_or_state_loss`，并记录 `memo_answer_embedded_memo_logic_plan_present` / `summary_memo_logic_plan_present`；同时 source-route gap 计数改为只阻塞未解决 `not_in_manifest_for_mcp_route_scope`，若同一 ticker 已有 targeted-repair parser diagnosis（failure reason、parser status、next action 齐全），则作为 parser-boundary-diagnosed，不再误判为 source-route false gap。`memo_llm` 的 deterministic salvage 现在消费 `memo_logic_plan.required_item_answer_plan`，会把 required-item 证据投影成 bounded judgment / evidence bridge / counter-read / financial bridge 的 dimension rows；产品规格、架构、客户部署等非收入证据不再被写成 supplier revenue/order fact。验证：`tests/test_data_script_quality_audit.py` 最新 `8 passed`，其中新增 synthetic full-chain-shaped artifact proof 使用真实 `_write_memo_surface_artifacts` 写出 `memo_logic_plan.json` / `memo_answer.json` / `claim_cards.json` / rendered answer 后再跑 audit，确认 repaired artifact 形状能通过；writer/data/P30/AIE targeted regression `8 passed` 和 `14 passed`；ASML/FPI route/parser diagnosis tests `4 passed`；synthetic no-LLM AI infra P30 scorer 已通过 required-item coverage、answer-plan projection 和 economic-role checks。随后补充 specialist、Memo Writer、Verifier、Research Lead 和 Universe `input_pack_fingerprint` 后，最新 no-paid 回归覆盖 data/script audit、writer/verifier repair、upstream route fingerprint、P30 source-route diagnosis、AIE、output-quality audit、specialist fingerprint、Memo Writer input-pack audit 和 token-budget v0.2，共 `41 passed`，compileall / `git diff --check` / narrowed secret scan 通过。边界：历史 r2 artifacts 仍是 pre-repair failure sample；synthetic artifact-level proof 不等同真实 full-chain，新生成的真实 artifact 仍必须证明 `memo_logic_plan.json`、required-item projection 和 data/script audit 闭环，同时继续修 semicap source-route / non-US disclosure parser rows。付费 DeepSeek 单 case 仍需等 data/script audit 和 token preflight 双通过。

2026-07-02 stale-state root-cause update：继续离线复盘 R13 semicap artifact 后，发现部分 `owned_parser_locator_gap_present` 和经济角色错误是 audit 过宽导致的误判，而真正让最终输出变成一行 bounded answer 的根因是 runtime state drift：pre-memo deterministic facts / supported material 已经出现，但 `memo_constraints` 仍沿用早期 `unsupported_specialist_claims_without_supported_claims`，`specialist_verification` 也没有在 governance refresh / Lead repair 后重算，导致 Memo Writer 在看到 stale false 后直接短路。修复口径：`refresh_judgment_plan_after_governance_filter` 必须用当前 supported / unsupported / validation state 重算 `memo_constraints`；`langgraph_orchestrator` 必须在 selected judgment 和 targeted repair 后重新生成 `specialist_verification`；`build_multi_agent_memo_draft` / `route_memo_writer_llm` 必须区分 stale verification block 与当前 unsafe judgment。provider/runtime specialist 失败不能进入正文 claims，但也不能吞掉已经验证的 ClaimCards，只能作为 partial-scope caveat 暴露。同步修复：DataScriptQualityAudit 只把显式 parser / locator / adapter failure 算作 owned parser gap，不再因 repair 文案含 parser/source boundary 就误判；P30 economic-role audit 只在文本明确把 focus issuer 自身 capex 当作 customer demand 时才报 misuse，不再误报 supplier revenue 对 customer capex 的 read-through。验证：contracts / memo route / D-series / data-script / economic-role / langgraph targeted no-paid tests 分别通过 `4`、`31`、`9`、`3`、`37`、`55`、`2` 项相关回归。边界：历史已保存 memo_answer 如果已经丢掉 supported_claims 无法离线恢复，只能证明 blocker 清理；下一次生成的新 artifact 必须证明 state refresh 后不会再发生一行 blocked memo。

2026-07-03 Workbench budget hardening update：P30 信息经济门控从 CLI 扩展到 Workbench full-chain eval 入口。`src/sec_agent/workbench/job_runner.py` 对所有调用 `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py` 的 Workbench eval runner 显式传入 `--token-budget-total 180000`、`--token-budget-per-case 120000`、`--max-paid-calls 8`，且默认不传 `--allow-expensive-llm`。这意味着 G11、diagnostic probe、R12 successor、broader release、load mix 等入口即使从前端/后端启动，也会先写 token budget plan 并在超预算时 fail closed，不能绕过 CLI preflight。验证：Workbench backend 三个 eval runner contract tests 通过；no-paid preflight `p30_workbench_budget_preflight_gate_20260703` 证明两个 AI/Semis deep case 合批仍被 run-level budget 拦截（`202800` estimated tokens / `16` paid calls），单个 AI infra case `p30_workbench_budget_single_case_preflight_20260703` 仍可通过预算（`101400` / `8`）。边界：这只是入口硬化，不等同真实输出质量改善；下一次 paid test 仍只能先单 case，并且必须回填 actual token / AIE ledger / data-script audit。

2026-07-03 Workbench token-to-insight projection update：P30 AIE visibility 不再停留在 artifact 文件。新增 `src/sec_agent/workbench/agent_information_economy_projection.py` 和 `GET /api/evals/agent-information-economy`，从 compact `agent_information_economy_preflight.json` / `agent_information_economy_audit.json` 读取 run/case token plan、预算阻断、issue counts、root-cause candidates 和 artifact refs；前端在 eval 面板和 R53-R60 Ops 面板新增 `Agent Information Economy` 卡片，用户可以直接看到最新 run 是否 pass/fail、两 case batch 为什么被预算预检挡住、单 case 是否可跑，以及对应 JSON artifact 路径。验证：backend API contract test、TypeScript、Vite build 和 live projection quick check 均通过。边界：projection 只读 saved AIE JSON，不加载原始 prompt，不替代真实 paid 单 case 输出质量验收。

2026-07-03 token-budget scheduler advice update：预算门控不再只输出“blocked”。`token_budget_plan.json` 现在带 `scheduler_advice`，把超预算拆成 `case_budget_repair_required`（单 case 自身不合格，必须先修）和 `split_required`（case 单独合格，但合批会超 run/call budget）。AIE preflight JSON 和 Workbench projection 同步保留该字段。最新 no-paid AI/Semis 两 case preflight `p30_scheduler_advice_preflight_20260703b` 显示：两条 case 均为单 case 可执行预算形态，但合批需要拆成两个 paid batches，每批一个 case，分别约 `101400` tokens / `8` paid calls。边界：这只是防误跑和调度建议，不是付费输出质量证明。

2026-07-03 JudgmentCard / thesis-path root-cause update：围绕用户指出的 1-6 个核心问题，本轮继续按 deterministic / node-level 修复，不跑付费 full-chain。结论是：P30 的 token 问题不是简单省 token，而是 agent 信息传导质量问题；如果 Research Lead 只派单、ClaimCard 只是证据卡、MemoLogicPlan 没成为 writer 主输入、writer 又收到 evidence dump，那么换模型也只能部分缓解，不能稳定产出有洞察的投研判断。实现侧新增 `JudgmentCard` 和 `ThesisPath` 合同：ClaimCard 会被提升为带 `judgment`、`evidence_bridge`、`business_mechanism`、`financial_bridge`、`counter_read`、`what_would_change_view`、`authority_boundary` 的 writer-ready 判断卡；Research Lead / supervising aggregation 会把产品、财务、供应链、资本、风险维度组织成 `thesis_path`，显式表达 `product_to_financial_bridge`、`supply_chain_to_product_context`、`capital_structure_to_fundamental_bridge` 等机制边，而不是只把 specialist 输出拼接给 writer。`MemoLogicPlan` 现在投影并压缩 `judgment_cards` / `thesis_path`，writer skeleton 优先消费这些 judgment moves；compact payload 去掉重复的 required-item 详细提示，只保留计数和必要 id，避免同一材料多次传给模型。Memo Writer route 新增 digest-only `raw_output_audit`，记录 raw output hash、长度、parsed/normalized claim counts、deterministic gate error types 和 salvage trigger，但不保存原始模型文本；AIE 新增 `memo_writer_raw_gate_or_salvage_failure`，把 raw -> normalized -> salvage 的失败纳入 root-cause，而不是把 salvage 当作成功兜底。验证：`tests/test_multi_agent_contracts.py`、`tests/test_memo_logic_plan.py`、`tests/test_multi_agent_memo_llm_repair.py`、`tests/test_agent_information_economy.py` 全量相关回归 `128 passed`，compileall pass。边界：这是 P30 1-6 点的信息传导根因修复和 no-paid AI/Semis 样板级 deterministic proof；下一步 real single-case paid run 仍必须先通过 data/script audit、AIE preflight、route observability 和 token-budget gates，且输出要人工审阅 memo 是否真正形成产品/财务/供应链联动判断。

2026-07-03 role-specific prompt-overlap closeout：在 JudgmentCard / ThesisPath 修复之后，新生成的 no-paid semicap mock artifact 显示剩余阻塞点变为 `prompt_pack_overlap_proxy`，根因是 specialist prompt 输入仍未按职责严格分流：risk 读取普通财务行，product 与 industry 共享 product profile / deployment refs，且 product prompt `ProductSpecPack` 内部仍含 customer-deployment / supply-chain sections。修复后，`specialist_llm.py` 在 prompt ranking / fingerprinting 前执行 role-level row filter：product 只读产品画像、规格、KPI、channel/field-inquiry 和 commercial gap；industry 只读 industry / relationship / customer deployment / order / supply-chain / channel / upstream-downstream 信号；risk 只读 risk / constraint / counterevidence 行，移除宽泛 counterclaim-slot 兜回和 `process-control` -> `control` 误命中。Product prompt projection 也排除 `customer_deployment_signals` / `supply_chain_signals`，原始 pack 仍保留这些 sections 供审计和 industry lens。验证：`tests/test_multi_agent_specialist_llm.py`、`tests/test_product_spec_pack.py`、`tests/test_agent_information_economy.py` 相关回归 `69 passed`，runner / routing / MemoLogicPlan / contracts 回归 `131 passed`；no-paid artifact `p30_mock_semicap_role_specific_prompt_overlap_repair_20260703` 的 `agent_information_economy_audit.status=pass`、`issue_counts={}`、`prompt_pack_overlap.overlap_detected=false`、`duplicate_prompt_evidence_ref_count=0`、`data_script_quality_audit.status=pass`。边界：runner summary 仍因 mock backend 保持 `gate_status=fail` / `diagnostic_only=true`，所以这不是 paid memo-quality closeout；下一次 paid 单 case 仍必须先通过 data/script、AIE、real-evidence、route/fanout、role-overlap、exact token-budget preflight。

## 4.16.2 P31 Agent Self-Hardening / Project OS（2026-07-04）

P31 目标是解决长线程推进中的系统性问题：Codex 不能依赖不可控的聊天记忆、上下文压缩或越来越长的 skill 文本来保持项目全局视野。这个 slice 把“我该怎么做”和“项目事实是什么”分开：skill 只保存操作规则，repo 内 `docs/project_os/` 保存机器可读状态、root-cause issue、技术模式和金融研究方法，full-chain preflight guard 则阻止在已知 blocker 下继续烧 token。

新增 Project OS artifacts：

- skills：
  - `Z:/CodexHome/.codex/skills/fin-insight-global-stewardship/SKILL.md`
  - `Z:/CodexHome/.codex/skills/fin-insight-project-os/SKILL.md`
- repo context / ledgers：
  - `docs/project_os/current_context_pack.zh-CN.md`
  - `docs/project_os/capability_status_ledger.jsonl`
  - `docs/project_os/root_cause_issue_ledger.jsonl`
  - `docs/project_os/external_pattern_registry.jsonl`
  - `docs/project_os/financial_research_method_registry.jsonl`
  - `docs/project_os/full_chain_run_policy.zh-CN.md`
  - `docs/project_os/token_budget_policy.zh-CN.md`
  - `docs/project_os/done_definition_l4_scope_pass.zh-CN.md`
  - `docs/project_os/full_chain_preflight_checklist.json`
- runtime guard：
  - `src/sec_agent/project_os_preflight.py`
  - `scripts/eval_multi_agent/run_project_os_full_chain_preflight.py`
  - `eval_multi_agent_real_llm_chain.py` 接入 `--project-os-preflight-only` / `--skip-project-os-preflight` / `--project-os-preflight-allow-open-blockers`

当前规则：

- 每轮非平凡任务启动前读 `current_context_pack`、capability ledger 和 root-cause ledger，不靠聊天记忆判断项目状态。
- paid/full-chain 默认先跑 Project OS preflight；如果存在 `full_chain_blocker=true` 的 open root-cause issue，脚本 fail closed。
- `--skip-project-os-preflight` 只允许 deterministic unit test 或用户明确批准的诊断场景，不能用于产品质量 closeout。
- `L1_contract_pass` / smoke / mock 只能是中间检查点；slice closeout 必须达到自身范围的 `L4_scope_pass`。

首批 root-cause ledger 当前仍保留 `RC-P30-001` / `RC-P30-002` / `RC-P30-003` 为 open full-chain blockers，因此 P31 会阻止 broad/paid full-chain 直接继续推进。下一步如果要跑真实单 case，必须先明确这是诊断 override，或先关闭这些 blocker。

验收：

- Project OS required files 存在且 capability rows 可机器读取。
- `Project OS preflight` 能在无 blocker 时 pass，在 open full-chain blocker 时 fail closed，在显式 diagnostic override 下返回 `diagnostic_override`。
- full-chain real LLM runner 已接入 Project OS preflight，且 token/provider preflight 仍作为后续独立 gate。
- `tests/test_project_os_preflight.py` 覆盖 pass / blocker / diagnostic override / missing files。

边界：

- P31 不证明 memo 质量已经变好，也不关闭 P30 真实单 case artifact proof。
- P31 不替代 R57 ContextEngine、R58 RAG/data governance、R60 eval/observability 的完整实现；它是这些系统执行时的项目状态和禁跑纪律层。

## 4.16.3 P32 Method & Pattern Learning Gate（2026-07-04）

P32 目标是把“金融研究方法学习”和“agent 工程经验吸收”做成可审计的项目能力，而不是靠聊天记忆、泛泛搜索或长 skill 文本。券商长篇行业报告的方法论可以吸收其研究地图、信息范围和见解深度，但最终输出仍面向 B 端内部 analyst workbench 的 buyside-style memo / workpaper，不按 sell-side marketing report 格式交付。

新增 artifacts：

- `docs/internal/vnext_20260610/r53_r60_p32_method_pattern_learning_gate.zh-CN.md`
- `docs/project_os/financial_research_method_learning_ledger.jsonl`
- `docs/project_os/agent_engineering_pattern_learning_ledger.jsonl`
- `docs/worklog/product_strategy/073_p32_method_pattern_learning_gate.md`

Learning gate 固定为：

1. `P32-L0 Project Failure Inventory`：回读 P30/P31 blocker 和当前项目失败类型。
2. `P32-L1 Source Discovery & Qualification`：登记 source URL、source type、相关性、吸收项和不吸收项。
3. `P32-L2 Method / Pattern Extraction`：抽取方法、结构和机制，不摘抄长文。
4. `P32-L3 Contract Translation`：映射到 FIN 的 pack、agent、graph、tool、eval、Workbench 对象。
5. `P32-L4 AI/Semis No-Paid Deterministic Proof`：不调用 LLM，证明 playbook/pattern 能改变 Research Lead thesis path、required-item plan 和 writer input。
6. `P32-L5 Registry Promotion`：只有通过 deterministic proof 的方法才进入 active registry。
7. `P32-L6 Closeout Review`：更新 worklog、Project OS 和 source docs，明确剩余缺口。

当前状态：P32 达到 `in_progress_registry_promotion_gate_pass`。首批金融研究方法和 agent 工程模式已进入 learning ledger，并抽出候选 L2 rows：

- `docs/project_os/financial_research_method_extraction_ledger.jsonl`
- `docs/project_os/agent_engineering_pattern_extraction_ledger.jsonl`

同时新增 source snapshot / provenance 工具：

- `scripts/engineering/build_p32_learning_source_snapshots.py`
- `tests/test_p32_learning_source_snapshots.py`
- `data/manifests/p32_learning_source_snapshots_v0_1.jsonl`

2026-07-04 follow-up：根据用户确认的“双轨”口径，P32 新增：

- `docs/project_os/p32_l1_coverage_matrix.jsonl`：说明当前 L1 哪些域足够推进初始 L3，哪些域仍是 source gap；
- `docs/project_os/p32_l3_contract_translation_ledger.jsonl`：把 L2 extraction rows 翻译成 FIN runtime / agent / data / eval 合同。
- `scripts/engineering/validate_p32_learning_gate.py` / `tests/test_p32_learning_gate_validation.py`：检查 L1/L2/L3/coverage 引用闭环和合同必填字段。
- `data/manifests/p32_learning_gate_validation_v0_1.json`：当前校验 `status=pass`，`source_count=21`，`extraction_count=15`，`coverage_domain_count=15`，`contract_count=15`，`error_count=0`。

当前 L1 coverage matrix 已不再有 `gap_needs_l1`：capital/market feedback、research-to-quant、enterprise RAG/data pipeline、Workbench product surface、sandbox/resource scheduler 已补到 initial-L3 coverage。但这些新增域只允许进入 L3 contract translation，不允许直接进入 runtime 或 paid full-chain。

2026-07-04 L4 no-paid fixture update：

- 新增 `scripts/engineering/run_p32_l4_ai_semis_deterministic_fixture.py`
- 新增 `tests/test_p32_l4_ai_semis_deterministic_fixture.py`
- 新增 `data/manifests/p32_l4_ai_semis_deterministic_fixture_v0_1.json`
- 新增 `docs/internal/vnext_20260610/p32_l4_ai_semis_deterministic_fixture_report.zh-CN.md`
- 验证结果：`python -m pytest tests/test_p32_l4_ai_semis_deterministic_fixture.py -q` -> `4 passed`；fixture run -> `status=pass`，`case_count=2`，`passed_case_count=2`。

L4 fixture 证明范围：

- baseline evidence list 可被 L3 contracts 转成 thesis path、required-item answer plan、JudgmentCards 和 writer-ready judgment material；
- AI/Semis 产品规格/架构、客户部署、供应链/value-chain、财务桥、反证和 what-would-change 能进入同一判断路径；
- 没有 SKU revenue / shipment / booking exact 不再等同于产品层无法判断；
- LangGraph checkpoint、MCP/tool boundary、durable HIL、trace/AIE、ContextEngine 等已规划/部分实现能力被对齐为 case-level runtime alignment。

2026-07-04 registry promotion follow-up：

- 新增 `docs/project_os/p32_active_registry_promotion_ledger.jsonl`；
- 新增 `scripts/engineering/validate_p32_registry_promotion.py`；
- 新增 `tests/test_p32_registry_promotion_validation.py`；
- 新增 `data/manifests/p32_registry_promotion_validation_v0_1.json`；
- promotion validation：`status=pass`，`active_registry_ready_count=10`，`deferred_count=5`。

进入 `active_registry_ready` 的只有 P32-L4 fixture 覆盖的 10 个旧合同，且仅限 feature-flagged 或 runtime-alignment-only。新增 5 个合同（capital-market feedback、research-to-quant、enterprise RAG pipeline、Workbench artifact review、sandbox/resource scheduler）全部保持 `deferred_pending_l4_fixture`。

这仍不是 paid memo 质量改善或 full-chain 继续扩量的依据。它只证明 P32 的 method/pattern learning -> contract translation -> L4 fixture -> registry promotion 决策链条可审计、可回放、不会把新补 source 直接推 runtime。

边界：

- P32-L1 不允许直接改 runtime。
- 外部 source 不能因“看起来成熟”就进入 active registry；必须先通过 L2/L3/L4。
- 如果某个方法不能映射到 FIN 的 evidence authority、ThesisPath、JudgmentCard、ContextEngine、ToolGateway、Trace/Eval 或 Workbench，它只能留在 learning ledger，不进入执行主线。

## 4.17 P25 / B05 Pack Depth Gate（2026-06-30）

P25 目标是推进 `B05-depth-packs-before-broad-full-chain`：在进入 20-50 case broad full-chain quality eval 之前，把产品证据、二级市场/资本反馈、量化实验、交付物、检索/数据刷新等 pack 的真实深度状态统一落到机器可读 SQL / manifest / report。初始 P25 只登记 blocker，不补齐缺失数据，也不关闭 B05；2026-07-01 后续 root-cause closeout 已补齐 S8/S7/P14 的 owned gaps，并使 P25 达到 B05 范围内 `L4_scope_pass`。

新增/更新 artifacts：

- schema：`configs/r53_r60/p25_b05_pack_depth_gate_schema_v0_1.json`
- pack assessment rows：`data/manifests/r53_r60_p25_b05_pack_depth_assessment_rows_v0_1.jsonl`
- requirement rows：`data/manifests/r53_r60_p25_b05_pack_depth_requirement_rows_v0_1.jsonl`
- gate rows：`data/manifests/r53_r60_p25_b05_pack_depth_gate_rows_v0_1.jsonl`
- summary：`data/manifests/r53_r60_p25_b05_pack_depth_summary_v0_1.json`
- report：`docs/internal/vnext_20260610/r53_r60_p25_b05_pack_depth_gate_blocked.zh-CN.md`
- P26 product evidence schema：`configs/r53_r60/p26_product_evidence_all_universe_depth_schema_v0_1.json`
- P26 product evidence layer/gap/gate rows：`data/manifests/r53_r60_p26_product_evidence_all_universe_depth_*_v0_1.jsonl`
- P26 product evidence summary：`data/manifests/r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json`
- P26 product evidence report：`docs/internal/vnext_20260610/r53_r60_p26_product_evidence_all_universe_depth_gate.zh-CN.md`
- runtime SQL mirror：`data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- builder：`scripts/engineering/build_r53_r60_p25_b05_pack_depth_gate.py`
- P26 builder：`scripts/engineering/build_r53_r60_p26_product_evidence_all_universe_depth_gate.py`
- tests：`tests/test_r53_r60_pack_depth_b05_gate.py`、`tests/test_r53_r60_product_evidence_depth_p26_gate.py`

真实构建结果：

| Field | Value |
| --- | --- |
| `status` | `pass` |
| `closeout_level` | `L4_scope_pass_for_broad_full_chain_pack_depth` |
| `release_decision` | `P25_b05_pack_depth_ready_broad_full_chain_allowed` |
| `pack_count` | `6` |
| `ready_pack_count` | `6` |
| `blocked_pack_count` | `0` |
| `blocked_requirement_count` | `0` |
| `gate_fail_count` | `0/5` |
| `gate_blocked_count` | `0/5` |
| `b05_status_after_p25` | `closed_by_p25_pack_depth_ready` |
| `broad_full_chain_quality_eval_allowed` | `true` |

Pack readiness：

| Pack | Status | Reason |
| --- | --- | --- |
| `ai_semis_product_evidence_pack` | `ready` | AI/Semis `53/53` strict pass，`gap_queue_count=0` |
| `research_to_quant_lab_pack` | `ready` | S9 至少 2 个 approved factors、2 个 backtests，且 `no_live_trading=true` |
| `product_evidence_pack_all_universe` | `ready` | P26 root-cause repair 后 CustomerDeployment depth `603/603`；Product Profile/Spec/Relationship ready，Product-KPI exact `160` 只阻断 exact KPI claims |
| `secondary_market_capital_feedback_pack` | `ready` | S8 已补 credit funding、derivatives market signal、valuation price-in public context；实时/商业市场深度是后续增强项，不再阻断 B05 |
| `deliverable_studio_pack` | `ready` | S7 已改成 reader-facing Workpaper draft + evidence/gap appendix，并新增 `customer_ready_editorial_quality_pass=true` |
| `retrieval_data_refresh_pack` | `ready` | P14 已新增 manifest-backed current accepted universe refresh evidence，`current_universe_refresh_status=current_accepted_public_source_universe_ready` |

P26 ProductEvidence 分层 gate 的真实结果：

| Layer | Status | Boundary |
| --- | --- | --- |
| `product_profile_spec_graph` | `ready` | 603 公司 Product/Profile/Spec/PIG 可用，可支撑产品画像、规格、架构、关系导航 |
| `product_relationship_graph` | `ready` | 可支撑竞争、替代、上下游、部署、read-through 的 bounded thesis-driver |
| `product_kpi_exact_boundary` | `ready_with_typed_exact_kpi_gaps` | `160` 家缺 SKU/产品线 exact KPI，只阻断收入、出货、ASP、份额、backlog 等 exact claims |
| `customer_deployment_signal` | `blocked_customer_deployment_signal_gap` | `72` 家缺 issuer-bound customer/deployment/adoption/distribution/operating-footprint signal，仍阻断 ProductEvidence broad quality |
| `capital_market_detail_cross_pack_dependency` | `out_of_scope_for_product_pack` | `2` 家 capital detail gap 归入 capital/funding pack，不再阻断 ProductEvidencePack |

P26 的作用是修正 B05 ProductEvidence 的 blocker 归因：不是“没有 SKU 收入/出货量所以产品层失败”，而是“产品画像、规格、关系图谱已可用；exact KPI 缺口保留为 exact-claim boundary；CustomerDeployment signal 仍需继续补”。P25 现在优先读取 P26 summary；如果 P26 缺失才回退到旧的五维 depth parity 诊断路径。

P25 修复/明确的真实 gating 问题：

1. P21 B05 不能再只靠“P24/P25 规划存在”关闭；现在必须回读 P25 summary，且只有 `b05_status_after_p25=closed_by_p25_pack_depth_ready`、`broad_full_chain_quality_eval_allowed=true`、`blocked_pack_count=0`、`blocked_requirement_count=0`、`gate_fail_count=0` 时才关闭。
2. `pack-level tests` 和 `targeted_full_chain_smoke_for_integration_only` 仍允许；`20_50_case_full_chain_quality_claim`、`product_release_claim` 和从旧 release board 自动推进仍禁止。
3. P25 的通过只代表“pack-depth blocker registration”达到自身范围内 L4-grade；它不是数据补齐、不是产品验收、也不是全系统上线信号。

P21 已回读最新 P25 summary：B05 的 pack-depth closeout 条件已经满足，`B05-depth-packs-before-broad-full-chain=closed_by_p25_pack_depth_ready`。在 B04 正式验收前，P21 仍保持 `full_chain_broad_eval_allowed=false`；2026-07-01 product-owner acceptance 后，P21 已更新为 `full_chain_broad_eval_allowed=true`。后续 broad full-chain 可以进入 scoped quality-eval 设计，但仍需按 R60 质量标准逐项记录，不得把单次 case 成功宣传成完整产品上线。

## 5. 单 Agent 执行节奏

每个 slice 采用固定节奏，但最低接口可运行不等于推进条件：

1. 冻结本 slice demand ticket，明确每条需求的中间门控、`L4_scope_pass` closeout 条件、四类 acceptance、测试/eval/trace/artifact 证据和 rollback 条件；
2. 实现达到 `L4_scope_pass` 所需的完整合同、运行面、审计面和失败边界；
3. 加 deterministic tests、schema/API/DB/artifact/event parity checks，以及该 slice 必需的 eval / quality gates；
4. 跑与 `L4_scope_pass` 和中间门控匹配的真实验证：
   - `L0` 只能做 smoke / diagnostic，不能推进依赖；
   - `L1` 需要合同完整、失败边界可见、下游可依赖；
   - `L2` 需要内部真实任务 dogfood、Workpaper / UI / trace / review 可用；
   - `L3` 需要 release readiness、监控、回滚、已知风险和试点交付报告；
   - `L4` 需要生产级多用户、权限、审计、监控、异常恢复和持续评测。
5. 生成 `PassLevelDecision`：记录 achieved intermediate gates、`closeout_level`、目标差距、Product / Engineering / Quality / Ops 证据、失败项、typed gaps 和是否允许下游依赖；
6. 如果未达到 `L4_scope_pass`，只能标记 `blocked` / `partial_diagnostic` / `exception_requested`，并把 blocker 写入 backlog；不得把该 slice 当成完成，也不得让依赖 slice 继续把它当作通过；
7. 更新 checklist / worklog / release board；
8. 运行 `git diff --check`、secret scan、targeted tests 和本 slice 的 mandatory gates；
9. 精确 stage 和 commit；
10. 只有在 `PassLevelDecision.closeout_level = L4_scope_pass`，或用户明确批准带风险的 exception 且下游需求不依赖该缺口时，才进入下一主 slice。

当前单 agent 模式下不要同时推进超过 1 个主 slice。S8/S9 可以在 S5 后做局部 schema review 或 diagnostic smoke，但不能进入可信业务闭环，也不能被标记为 slice pass，直到对应 `L4_scope_pass` 被满足。

## 5.1 R 文档到可执行需求单的拆分办法

在进入任何代码实现前，必须先把涉及的 R 系列文档拆成更细的需求单。36 文档里的 S0-S10 只是 release-slice 编排层，不足以直接作为实现任务。

拆分流程：

1. `RDocumentInventory`
   - 输入：PRD、26、27、28-35、36，以及 R0-R49 中会影响当前 slice 的历史合同 / 已实现能力 / known gaps。
   - 输出：每个 R 文档的章节、对象、schema、API、runtime、data、frontend、eval、ops 要求清单。

2. `RDocumentDemandMap`
   - 把每条要求映射到 S0-S10、U0-U10、能力域和依赖关系。
   - 每行至少包含：`source_doc`、`source_section`、`requirement_summary`、`slice_id`、`demand_id`、`capability_domain`、`dependencies`、`blocked_by`、`scope_l4_acceptance`。

3. `DemandTicket`
   - 每个 demand ticket 必须小到可以独立 review、测试、回滚。
   - 每条 ticket 必须写明：问题 / 用户价值、输入输出、范围和 non-goals、受影响 schema/API/DB/artifact/UI/eval、实现文件或模块、四类 acceptance、`L4_scope_pass` 证据、rollback。

4. `ImplementationTask`
   - 每个 demand ticket 再拆成具体实现任务，例如 schema migration、runtime adapter、API endpoint、frontend view、deterministic test、eval case、trace dashboard、runbook。
   - 实现任务可以 commit，但不能替代 demand ticket 的 `L4_scope_pass`。

5. `GateArtifact`
   - 每个 slice closeout 必须留下可审计 gate artifact：`PassLevelDecision`、test/eval report、trace/cost summary、known gaps、exception log、rollback note。

执行约束：

- 不允许直接从 R53/R54/R55 等高层文档跳到写代码。
- 不允许把“已有文档规划”当成“已有需求单”。
- 不允许把单个 implementation task 的完成当作 demand ticket 完成。
- S0 的首要任务就是把上述对象先落成 machine-readable backlog / release board；S0 没有通过 `L4_scope_pass` 前，不进入 S1 主实现。

## 6. 第一批建议执行任务

下一轮建议从 S0 + S1 开始：

1. `U0-D01-backlog-schema`
2. `U0-D02-r-demand-map`
3. `U0-D03-pass-level-gate-matrix`
4. `U1-D01-runtime-facade-entrypoint`
5. `U1-D02-task-run-state-machine`
6. `U1-D03-sql-final-task-audit`
7. `U1-D04-workpaper-event-ledger`
8. `U1-D06-run-trace-baseline`

理由：

- 它们是所有后续 R55/R58/R59/R60 的共同前置；
- 不依赖复杂模型调用，适合先做工程底座；
- 做完后就能把后续任务从“跑脚本”提升为“可审计 ResearchTask”；
- 可以快速发现当前 Java / Python / Workbench / DB 的实际边界。

## 7. 当前结论

下一阶段不应先做更炫的 agent 行为或更多数据源，而应先把任务主账本、事件账本、证据账本、trace/eval 账本统一。只有 S1-S3 稳定后，Workpaper、Deliverable、secondary market、quant 才不会继续变成孤立功能。

用企业级 pass level 看，当前最务实的里程碑是：

- S0 达到 `L4_scope_pass`：产出可机器读取的 backlog schema、R-document inventory、R-demand map、pass-level gate matrix 和 release board；未覆盖 R0-R49 baseline dependency 不算通过；
- S1 达到 `L4_scope_pass`：task/run/event/artifact/trace 可回放，1 条真实研究任务达到内部 dogfood 证据，失败边界和 rollback 稳定；
- S2-S3 达到 `L4_scope_pass`：工具权限、sandbox、trace、检索、证据账本和核心研究 case 都可审计，才能启动 Workpaper dogfood；
- S5 以后所有面向用户工作流的 slice closeout 都必须达到自身范围内的 `L4_scope_pass`；S10 负责把各 slice 串成全产品 `L4_production_pass` 候选。
