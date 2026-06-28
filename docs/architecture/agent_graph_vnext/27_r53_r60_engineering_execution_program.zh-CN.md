# R53-R60 工程化执行总控计划

日期：2026-06-28

状态：program-level 技术执行计划草案。本文不替代 R53-R60 各自的技术方案，而是定义它们如何从 PRD / 架构文档转成需求单、排期、门控、联调和反馈闭环。

关联源文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/11_agent_eval_runtime_framework.zh-CN.md`
- `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`，仅作为归档参考。

## 1. 为什么需要总控计划

R53-R60 不是 8 个彼此独立的文档。它们共同把 FinSight 从“研究链路可跑”推进到“B 端金融研究工作台可上线级别”：

```text
PRD
 -> technical plan / RFC
 -> program roadmap
 -> epic / feature / story / task
 -> test plan / eval gate
 -> integration
 -> release candidate
 -> user / reviewer feedback
 -> backlog update
```

如果每个 R 文档各自拆需求单、各自实现，风险是：

- schema / event / API 无法互通；
- agent runtime、后端、前端、数据、eval 各做一套状态；
- R53 quant、R54 secondary market、R55 deliverable 等上层能力缺底座；
- 测试只覆盖局部功能，无法证明产品闭环；
- Git 和 artifact 管理继续变成长期脏工作树。

因此 R53-R60 以 program 方式管理：高层 R 文档是 epic，需求单按能力域和依赖关系拆分，不按文档编号机械串行。

## 2. R53-R60 Epic 边界

| Epic | 名称 | 核心问题 | 主要产物 |
| --- | --- | --- | --- |
| R53 | Research-to-Quant Lab | 投研观点如何转成可检验因子并通过人工批准、回测和模拟监控 | FactorHypothesis、FeatureSpec、DatasetBuildPlan、BacktestResult、FactorCard |
| R54 | Secondary Market / Capital Feedback | 二级市场资金面、持仓、信用、资本动作和预期如何进入研究判断 | Ownership、CreditFunding、CorporateAction、Liquidity、Valuation、Derivatives packs |
| R55 | Deliverable Studio & Dashboard Projection | Workpaper 如何投影成多格式交付物和工作台看板 | DeliverablePlan、renderer registry、dashboard projections |
| R56 | Agent Runtime Stack Hardening | LangGraph / harness / MCP / A2A / Hermes-style ContextEngine 如何工程化 | RuntimeFacade、durable graph、tool gateway、context injection audit |
| R57 | Memory & Context Lifecycle | 长短记忆如何支持任务、公司、项目、机构和 watchlist | Memory tier、promotion/invalidation gate、ContextEngine strategy |
| R58 | DB / RAG / Retrieval Optimization | 数据库、RAG、Milvus、BM25、graph retrieval 如何稳定服务研究链路 | retrieval planner、hybrid route、index registry、role-specific selector |
| R59 | Backend / Frontend Workbench Hardening | Java 后端、任务队列、权限、前端工作台如何产品化 | API、queue、SSE、RBAC、artifact browser、review UI |
| R60 | Eval / Observability / Incident / Fallback | 全链路质量、异常、成本、trace 和兜底如何可审计 | Eval registry、trace export、failure ledger、release gates |

## 3. 依赖关系

### 3.1 必须先稳定的底座

```text
R56 RuntimeFacade / durable graph
 + R57 ContextEngine / memory
 + R58 DB-RAG retrieval contracts
 + R60 eval / observability baseline
 -> R52 collaborative graph implementation
 -> R55 deliverable and dashboard product closure
 -> R54 secondary-market data expansion
 -> R53 quant validation layer
```

R53 可以先写技术方案和 schema，但不能在没有 R56/R57/R58/R60 最小底座前进入可信 backtest / paper trading。R54 可以并行做数据源和 pack 设计，但其结果必须进入 R58 的 retrieval / data contract 和 R60 的 source-authority eval。

### 3.2 可并行工作

- R56 / R57 / R60 可以并行拆合同，因为它们共同定义 runtime、context 和 eval 主账本。
- R55 可在 R52 WorkpaperEvent / WorkpaperPack contract 冻结后并行做前端和 renderer prototype。
- R54 数据源 adapter 可以先做 source inventory / parser contract，不等 R55。
- R53 可以先做 artifact schema、approval flow 和 dummy deterministic case，不跑真实回测。

## 4. 需求单标准

每个需求单必须有以下字段：

| 字段 | 要求 |
| --- | --- |
| Demand ID | 例如 `R56-D03-runtime-facade-entrypoint` |
| PRD Trace | 对应 PRD 章节和用户价值 |
| Tech Trace | 对应 R 文档章节、schema、API、event 或 eval |
| Capability Domain | agent runtime / data / backend / frontend / quant / eval / ops |
| Problem | 要解决的具体问题 |
| Scope | 本单做什么 |
| Non-goals | 本单明确不做什么 |
| Inputs | 上游依赖、数据、artifact、API |
| Outputs | schema、代码、文档、UI、eval、artifact |
| Acceptance | 产品验收和工程验收分别列出 |
| Tests | deterministic test、integration test、eval case、manual review |
| Failure Policy | 失败如何暴露，是否允许 retry / fallback |
| Rollback | 如何回滚或禁用 |
| Owner | 负责人占位，不在文档中强制指定真实人 |
| Status | planned / in_progress / blocked / review / done |

禁止事项：

- 不允许用 “脚本能跑” 替代产品验收；
- 不允许用 URL seed / route seed 计为 evidence coverage；
- 不允许用 fallback 隐藏 schema / parser / retrieval / permission 失败；
- 不允许 Composer / writer 自己查事实补洞；
- 不允许 quant backtest 使用未记录 publish time / available time 的特征。

## 5. 门控体系

### 5.1 Design Gate

通过条件：

- PRD trace 和 technical trace 明确；
- schema / API / event / artifact contract 草案冻结；
- 依赖关系和不做事项明确；
- human approval / compliance boundary 明确；
- 所有新增数据和工具都归入权限模型。

### 5.2 Data Contract Gate

通过条件：

- 数据源、表、artifact、graph edge、provenance 明确；
- source authority / parser / citation / timestamp 可追踪；
- gap 必须 typed：retrievable_gap、public_boundary、commercial_gap、not_applicable、forbidden_claim；
- 不得把 context-only row 当 exact fact。

### 5.3 Implementation Gate

通过条件：

- schema tests / unit tests 通过；
- permission tests 通过；
- no hidden fallback；
- run audit / event ledger 写入；
- `git diff --check` 通过。

### 5.4 Integration Gate

通过条件：

- Java / Workbench / Python runtime / DB / ObjectStore / frontend 至少一条路径联通；
- WorkpaperEvent、artifact refs、eval rows、trace ids 可串联；
- 失败可见并能回到需求单或 failure ledger；
- replay 能重建关键状态。

### 5.5 Eval Gate

通过条件：

- deterministic cases；
- bad / forbidden cases；
- regression cases；
- latency / token / cost / queue wait；
- retrieval recall / rerank / context injection audit；
- human review 或 approval case。

### 5.6 Release Gate

通过条件：

- 用户能从 UI 或 API 完成目标 workflow；
- 输出可审计、可引用、可复盘；
- known gaps 被记录，不隐藏；
- rollback / disable flag 明确；
- release note 和 worklog 完整。

## 6. Program 排期

### P0：计划与合同冻结

目标：把 R53-R60 全部拆成可执行技术方案和需求单。

需求：

- `R53` 技术方案；
- `R54` 技术方案；
- `R55` 技术方案；
- `R56` 技术方案；
- `R57` 技术方案；
- `R58` 技术方案；
- `R59` 技术方案；
- `R60` 技术方案；
- 统一 demand backlog；
- 统一 gate matrix。

通过条件：

- 每个 R 文档有 demand list；
- demand 之间的依赖关系可排序；
- checklist 中每个 open item 都能映射到某个 demand；
- 不存在“技术上要做但没有需求单”的隐性 backlog。

### P1：运行时和上下文底座

目标：先让协作型 agent runtime 可恢复、可审计、可暂停、可继续。

优先需求：

- R56 RuntimeFacade；
- R56 durable graph / checkpoint / interrupt / resume；
- R57 ContextEngine injection plan；
- R60 run/eval trace baseline；
- R52 WorkpaperEvent ledger 接入。

通过条件：

- 同一研究任务可从 CLI / Workbench / Java shell 入口创建并得到一致 run state；
- context injection plan 可 replay；
- forbidden tool / forbidden context tests 通过；
- human pause / resume smoke 通过。

### P2：数据、检索和证据底座

目标：把现有 600+ 公司数据、RAG、图谱和 secondary-market / capital feedback 入口接成可消费数据层。

优先需求：

- R58 retrieval planner；
- R58 SQL exact / BM25 / vector / graph route priority；
- R58 role-specific evidence selector；
- R54 source adapter / pack schema；
- R60 source-authority / retrieval eval。

通过条件：

- Evidence Workbench 能看到 exact fact、bounded thesis driver、gap、graph edge；
- role-specific selector 不再提前 cap 掉关键证据；
- L2/L3 / secondary-market rows 不冒充 fundamental exact fact；
- retrieval regression case 通过。

### P3：Workpaper 到交付闭环

目标：从 approved / review-ready Workpaper 生成多格式交付物和 dashboard projection。

优先需求：

- R55 DeliverablePlan；
- R55 Markdown / Word / PPT / Excel renderer；
- R55 DashboardProjectionUpdater；
- R59 frontend Workpaper / Deliverable / Review views；
- R60 deliverable quality eval。

通过条件：

- 同一 Workpaper 至少能生成 memo + Excel appendix 或 memo + deck outline；
- citation、appendix、gap disclosure 保留；
- Dashboard 能展示任务状态、gap、review、artifact 和 trace；
- Composer 不可调用 retrieval / DB / web。

### P4：Research-to-Quant 验证闭环

目标：从研究底稿生成候选因子并完成人工批准、PIT 数据检查、回测和 FactorCard。

优先需求：

- R53 quant artifact schema；
- R53 Quant Translator Specialist；
- R53 PIT data availability gate；
- R53 leakage / survivorship / liquidity / cost gate；
- R53 backtest adapter；
- R53 risk attribution；
- R53 paper trading monitor。

通过条件：

- 至少 2 个 research thesis driver 能转成 FactorHypothesis；
- 进入 dataset build / backtest 前必须 human approval；
- 特征都有 publish time、available time、tradable-after；
- 回测结果能解释风险暴露和失效场景；
- 不生成真实交易指令或外部投资建议。

### P5：企业级工作台硬化

目标：让系统成为可交付 B 端工作台，而不是研究脚本集合。

优先需求：

- R59 auth / RBAC / tenant；
- R59 task queue / SSE / cancel / resume；
- R59 artifact browser；
- R59 review queue；
- R60 incident dashboard；
- R60 release readiness report。

通过条件：

- 多任务状态可见；
- 失败原因可见；
- 用户能审批、退回、评论、导出；
- trace / eval / artifact refs 可审计；
- release gate 通过。

## 7. 团队认领方式

需求单不按 R 文档归单人独占，而按能力域认领：

| 能力域 | 典型需求 |
| --- | --- |
| Product / PM | PRD trace、用户验收、模板和工作流 |
| Agent Runtime | LangGraph、RuntimeFacade、WorkpaperEvent、tool permission |
| Data Engineering | source adapter、parser、SQL mirror、ObjectStore、provenance |
| Retrieval / RAG | BM25、Milvus、graph route、rerank、selector、retrieval eval |
| Backend | Java API、queue、SSE、auth、tenant、artifact API |
| Frontend | Dashboard、Evidence Workbench、Workpaper、Deliverable Studio |
| Quant | factor schema、PIT dataset、backtest、risk attribution |
| Eval / QA | eval registry、case catalog、failure/gold lifecycle、release gate |
| Ops / Git | branch、commit、artifact policy、release note、rollback |

## 8. Git 和版本管理要求

每个 release slice 应有清晰 Git 边界：

- 开始前记录 branch、dirty status、相关已有改动；
- 不用 `git add .`；
- 代码、文档、eval fixtures、generated artifacts 分开 stage；
- 大型 raw data / runtime output 不默认入库；
- 每个 commit 只承载一个可解释变更；
- commit 前对候选文件做 secret scan；
- 做完一组需求后更新 worklog、checklist 和 release note；
- release candidate 必须能从 commit、artifact version、eval run、workpaper event replay 复盘。

当前仓库已有大量历史脏工作树，因此 R53-R60 阶段开始前建议先做一次 Git hygiene closeout：把可提交代码/文档、需要忽略的临时产物、需要外部存储的数据和应删除但不能擅自删除的本地 scratch 明确分类。

## 9. 第一批文档拆分顺序

建议后续按以下顺序补文档：

1. `28_r53_research_to_quant_lab_technical_plan.zh-CN.md`
2. `29_r54_secondary_market_capital_feedback_technical_plan.zh-CN.md`
3. `30_r55_deliverable_studio_dashboard_projection_technical_plan.zh-CN.md`
4. `31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`
5. `32_r57_memory_context_lifecycle_technical_plan.zh-CN.md`
6. `33_r58_rag_database_retrieval_optimization_technical_plan.zh-CN.md`
7. `34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md`
8. `35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md`

拆文档时先写 demand list 和 gates，再写 implementation details。实现顺序以本文 P0-P5 依赖为准，不以文档编号机械排序。

## 10. 当前结论

- R53-R60 是 program，不是八个孤立技术文档。
- R56 / R57 / R58 / R60 是底座，R55 是产品闭环，R54 是二级市场和资本反馈数据扩展，R53 是研究到量化验证的专业扩展。
- 每个需求单都必须能回溯到 PRD 和技术文档，并有测试和反馈入口。
- Git、artifact、eval 和 release gate 必须和需求单一起管理，否则工程规模继续扩大后会不可控。
