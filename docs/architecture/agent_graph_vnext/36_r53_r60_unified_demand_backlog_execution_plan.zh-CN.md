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
