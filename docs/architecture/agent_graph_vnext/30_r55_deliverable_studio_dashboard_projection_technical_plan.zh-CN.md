# R55 Deliverable Studio / Dashboard Projection 技术框架

日期：2026-06-28

状态：framework-level 技术草案。本文只冻结 Deliverable Studio 和 Dashboard Projection 的对象边界、权限边界、输入输出合同和 eval gate，不拆 v0.1 / v0.2 需求单，不进入实现。更细需求拆分需等 R56 runtime、R57 context、R58 DB/RAG、R59 backend/frontend 和 R60 eval/observability 底座一起定下来。

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/architecture/agent_graph_vnext/28_r53_research_to_quant_lab_technical_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/29_r54_secondary_market_capital_feedback_technical_plan.zh-CN.md`

## 1. 定位

R55 不是把 Memo Writer 换成 Word/PPT 渲染器。它的定位是：

```text
把 approved / review-ready WorkpaperPack、JudgmentState、FactorCard、CapitalFeedbackPack 和 Evidence Appendix，投影成可审阅、可追溯、可多格式导出的企业交付物与工作台看板。
```

它解决的问题是：

- 输出端不能只有长文本回答；
- 同一底稿要能生成内部 memo、客户 brief、PPT deck、Word/PDF、Excel appendix、图谱图、dashboard card；
- 交付物必须保留 citation、appendix、gap、authority boundary、human approval 和版本记录；
- dashboard 不是另一个分析系统，而是 WorkpaperEvent / run audit / evidence / gap / artifact 状态的投影；
- Composer 不能绕过 Research Lead 自己检索或补事实。

R55 不做：

- 事实补查；
- raw retrieval rows 直接写作；
- 绕过 Workpaper / JudgmentState 生成正式结论；
- 无人工批准的客户版外发；
- 替代 R59 前端工程或 R60 eval 体系。

## 2. 输入边界

Deliverable Composer 只能消费经过上游授权的结构化输入：

| 输入 | 来源 | 用途 |
| --- | --- | --- |
| `ResearchObjectiveContract` | R52 / Research Lead | 确认任务目的、受众、格式、审批要求 |
| `WorkpaperPack` | R52 / specialist workstreams | 正文结构、维度分析、反方、缺口、human comments |
| `JudgmentState` | Lead Review | 核心判断、反方、触发条件、边界 |
| `MemoLogicPlan` | Lead Review / Writer planning | 章节逻辑、论证顺序、引用选择 |
| `DimensionEvidencePortfolio` | R46 / R58 | 基本面、产品、行业、资本、市场、政策等维度 evidence refs |
| `ProductEvidencePack` | R43/R44 | 产品、规格、部署、关系图谱 |
| `SecondaryMarketCapitalFeedbackPack` | R54 | 资金面、持仓、信用、估值、衍生品、price-in |
| `FactorCard` | R53 | 量化验证摘要、有效性、风险和 appendix |
| `ArtifactRef[]` | ObjectStore / run audit | 图表、表格、PDF、DOCX、PPTX、XLSX、HTML、图片 |
| `ApprovalDecision[]` | Human review | 哪些内容可进入客户版、内部版或只做 appendix |

Composer 不允许直接调用：

- DB / SQL exact query；
- RAG / Milvus / BM25 retrieval；
- public web search；
- source adapter / parser；
- R53 backtest runner；
- R54 market data adapter。

## 3. 输出类型

R55 应支持的输出不是一次性全做，但对象模型必须能表达：

| 输出 | 典型受众 | 关键要求 |
| --- | --- | --- |
| Long answer / chat response | 内部快速问答 | 简洁、可追溯、无内部字段污染 |
| Markdown memo | analyst / PM | thesis-led、citation、gap、appendix refs |
| Word report | 内部或客户 | 目录、章节、图表、引用、审阅版/客户版 |
| PDF brief | 客户或会议 | 版式稳定、引用简短、边界可读 |
| PPT deck | 投委会、客户、管理层 | slide storyline、图表、notes、appendix |
| Excel appendix | analyst / data reviewer | 结构化表、公式/数据来源、as-of time |
| Graph / mind map / timeline | 研究复盘 | 公司/产品/供应链/资本/事件关系 |
| Dashboard card | Workbench 首页、watchlist、company page | 状态、告警、thesis change、gap、artifact drilldown |
| Watchlist update | 覆盖更新 | changed / unchanged、trigger、next action |
| Eval / audit package | reviewer / compliance | trace、evidence、gate、failure、cost、latency |

## 4. Object Model

### 4.1 主链路

```text
WorkpaperPack
 -> JudgmentState
 -> DeliverablePlan
 -> NarrativeSurfaceContract
 -> RenderJob
 -> ArtifactRef
 -> DashboardProjection
 -> HumanApprovalDecision
 -> PublishedDeliverable / InternalArtifact
```

### 4.2 核心对象

| 对象 | 作用 | 稳定字段 |
| --- | --- | --- |
| `DeliverablePlan` | 定义输出目标和受众 | `deliverable_id`、`task_id`、`audience`、`format`、`language`、`template_id`、`approval_policy`、`source_workpaper_id` |
| `NarrativeSurfaceContract` | 定义写作和展示约束 | `tone`、`section_order`、`required_sections`、`forbidden_sections`、`citation_policy`、`internal_field_policy`、`client_safe_policy` |
| `DeliverableSection` | 一个可审阅章节 | `section_id`、`title`、`source_judgment_refs`、`evidence_refs`、`gap_refs`、`author_actor`、`review_status` |
| `CitationPack` | 引用和 appendix 组织 | `citation_id`、`source_ref`、`short_label`、`appendix_ref`、`quote_policy`、`authority_class` |
| `VisualizationSpec` | 图表/图谱/时间线规范 | `viz_id`、`viz_type`、`data_refs`、`chart_spec`、`graph_edge_refs`、`render_constraints` |
| `RenderJob` | 渲染任务 | `job_id`、`format`、`renderer`、`input_artifacts`、`output_uri`、`status`、`error` |
| `ArtifactRef` | 输出文件或中间产物 | `artifact_id`、`uri`、`mime_type`、`hash`、`created_by`、`source_refs`、`version` |
| `DashboardProjection` | 看板投影 | `projection_id`、`surface`、`entity_scope`、`cards`、`source_event_ids`、`refresh_policy` |
| `ProjectionCard` | 看板卡片 | `card_id`、`card_type`、`title`、`state`、`metrics`、`drilldown_refs`、`staleness` |
| `DeliverableReviewState` | 交付物审阅状态 | `review_id`、`reviewer`、`comments`、`approval_decision`、`client_safe_decision` |

### 4.3 存储形态

| 层 | 存什么 | 用途 |
| --- | --- | --- |
| SQL store | DeliverablePlan、section、review、projection、render job 索引 | 审计、权限、状态流转 |
| ObjectStore | DOCX/PPTX/XLSX/PDF/HTML/PNG/Markdown | 大文件和版本化 artifact |
| Graph store | deliverable -> workpaper -> evidence -> source edges | trace 和 drilldown |
| Search index | deliverable summary、review comments、client-safe notes | 历史交付物检索和复用 |

## 5. Deliverable Studio

Deliverable Studio 是用户可编辑、可审批的交付物空间，不是隐藏后台 renderer。

应具备的产品状态：

```text
draft
 -> review_ready
 -> human_review
 -> revision_requested
 -> approved_internal
 -> approved_client_safe
 -> published / exported
 -> superseded / retired
```

关键能力：

- 从 WorkpaperPack 创建 DeliverablePlan；
- 支持内部版 / 客户版不同口径；
- 每个 section 可追溯到 judgment、evidence 和 gap；
- human reviewer 可评论、退回、批准；
- export artifact 可版本化；
- composer 不可私自补事实，只能请求返回 LeadReview / targeted repair。

## 6. Dashboard Projection

Dashboard Projection 不直接创造新分析结论。它把已存在的任务、底稿、证据、图谱、交付物、eval 和 watchlist 状态投影为 UI surfaces。

核心 projection：

| Projection | 来源 | 展示 |
| --- | --- | --- |
| `TaskStatusProjection` | ResearchTask / WorkpaperEvent | planning、collecting、analysis、review、drafting、approved、failed |
| `EvidenceCoverageProjection` | DimensionEvidencePortfolio / gap ledger | 哪些维度足够、哪些缺口可补、哪些是 public/commercial boundary |
| `DeliverableQueueProjection` | DeliverablePlan / RenderJob / ReviewState | 待生成、待审、待修改、已批准 |
| `WatchlistProjection` | Watchlist events / thesis changes | trigger、changed/unchanged、risk、next action |
| `CapitalFeedbackProjection` | R54 pack | price-in、positioning、credit、corporate action、derivatives boundary |
| `QuantValidationProjection` | R53 FactorCard | candidate、approved、rejected、paper monitor |
| `EvalAuditProjection` | R60 eval/run store | quality gate、failure queue、cost、latency、trace |

Projection 的验收重点是 parity：UI 看板展示的状态必须能回到同一组 SQL / artifact / event refs，不能有前端自己推断出的“幽灵状态”。

## 7. 工具权限

R55 Composer 可以使用：

- Markdown renderer；
- DOCX generator；
- PPTX generator；
- XLSX / CSV appendix generator；
- PDF renderer；
- chart / graph / timeline renderer；
- artifact packager；
- template resolver。

R55 Composer 不可以使用：

- retrieval / web / DB query；
- source parser；
- backtest runner；
- data mutation tool；
- credentialed external API。

如果输出缺证据，Composer 应写 `DeliverableBlocked` 或 `RepairRequested` event，交回 Research Lead，而不是自行补查。

## 8. 和 R53 / R54 / R56-R60 的关系

| 模块 | 对 R55 的影响 |
| --- | --- |
| R53 | FactorCard、quant charts、validation appendix 可进入 deliverable 和 dashboard |
| R54 | capital feedback / price-in / positioning 信号需要清晰渲染边界和滞后性 |
| R56 | 决定 Composer 如何作为 durable graph node、如何 interrupt / resume |
| R57 | 决定 Composer / renderer 可见哪些 context，如何防止 raw evidence 泄露 |
| R58 | 决定 evidence refs、artifact refs、graph refs 如何被 exact drilldown |
| R59 | 决定 Deliverable Studio、review queue、dashboard projection 的 API 和前端状态 |
| R60 | 决定 readability、citation、layout、unsupported claim、client-safe gate |

因此 R55 的具体需求单不应现在独立拆完；必须等 R56-R60 底座边界确定后，按 release slice 拆。

## 9. Eval Gates

R55 必须被 eval，而不是只看“文件能导出”。

| Gate | 检查 |
| --- | --- |
| `input_authority_gate` | deliverable 只消费 approved / review-ready Workpaper 和 refs |
| `no_raw_retrieval_gate` | Composer 输入中没有 raw retrieval rows 或 unauthorized context |
| `citation_integrity_gate` | 每个关键判断有 citation / appendix / evidence refs |
| `numeric_fidelity_gate` | 数字、期间、单位、ticker 不漂移 |
| `internal_field_leakage_gate` | 正文不出现 raw role id、ClaimCard 机械字段、未解释机制字段 |
| `surface_readability_gate` | 核心判断、投资含义、反方、触发条件自然可读 |
| `client_safe_gate` | 客户版不泄露内部推理、私有材料、未批准判断 |
| `artifact_reproducibility_gate` | 同一 DeliverablePlan 可重渲染并产生可追溯 artifact |
| `dashboard_projection_parity_gate` | dashboard 状态能回到 source events / SQL / artifact refs |
| `layout_smoke_gate` | Word/PPT/PDF/Excel 渲染不截断、不乱码、图表表格可读 |

## 10. 框架级实施层

本阶段只做到 framework layer：

1. 定义 R55 输入/输出边界；
2. 定义 DeliverablePlan / RenderJob / DashboardProjection / ArtifactRef 等对象；
3. 定义 Composer 工具权限；
4. 定义 dashboard projection 不创造新事实的原则；
5. 定义 R55 eval gates；
6. 将更细需求拆分延后到 R56-R60 确定后。

暂不拆：

- DOCX/PPTX/XLSX/PDF renderer 的具体库选型；
- 前端 Deliverable Studio 页面任务；
- dashboard API；
- template 管理；
- artifact store schema；
- 具体 release slice 和 story。

## 11. 当前开放问题

1. 第一版默认交付物是 Word memo、PPT deck、dashboard brief，还是 Markdown + PDF brief。
2. Deliverable Studio 是先做只读 export，还是一开始支持在线编辑和评论。
3. 模板是否按任务类型内置，还是支持机构自定义模板。
4. 图谱图、时间线、mind map 是由 R55 renderer 生成，还是由 Graph Workspace 生成后作为 artifact 输入。
5. 客户版和内部版的 client-safe policy 如何和权限系统/RBAC 绑定。
6. R55 renderer 是否统一走 Python document tools，还是由 Java 后端调度独立 rendering worker。
7. Dashboard Projection 是否先从 WorkpaperEvent 读，还是直接从 SQL materialized projection table 读。

## 12. 草案结论

R55 的核心不是“会生成文件”，而是把研究底稿、判断、证据、缺口、审批和图谱状态，投影为企业可用的交付物和工作台界面。

第一阶段必须保护四条边界：

1. Composer 只负责表达和格式化，不负责事实补查。
2. 所有交付物都必须能回到 Workpaper / JudgmentState / evidence refs / artifact refs。
3. Dashboard 是 projection，不是另一个不可审计的推理层。
4. 具体需求拆分要等 R56-R60 的 runtime、context、DB/RAG、backend/frontend 和 eval 底座一起确定。
