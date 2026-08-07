# TECH_02：Agentic Search / Evidence ToolGateway / SourceHunter

日期：2026-07-09

状态：技术合同草案。本文承接 PRD 的 Tool Registry、Evidence Tool Planner、Evidence Gate、SourceHunterLoop 和 agentic search 要求；不表示工具已被 runtime 统一接入。

## 1. 要解决的问题

P36 的检索问题不是单纯 reranker 问题，而是：

- route selection 不一定按 decision cell；
- RAG / SQL / graph / market rows 只能成为 candidate；
- parser / numeric / source authority 未统一 gate；
- supervisor supplement ledger 还没有转成 runtime source-route attempts；
- specialist 不能私有化 DB/RAG/web/parser 工具。

TECH_02 的目标是把“查资料”改成 cell-level agentic search：从 `DecisionSurfaceCell` 的 evidence slot 出发，经过工具规划、候选召回、source acquisition、parser / numeric 接口、Evidence Gate，最后生成 `EvidenceResponse`。它定义的是从 cell 到 evidence 的可执行合同。

## 2. 2026-07-10 边界修订：orchestration and promotion, not parsing implementation

TECH_02 拥有：

- 调用 Parser / NumericTrace / Metadata binding 的接口；
- 声明当前 `EvidenceRequest` 需要哪些 metadata / numeric binding；
- 检查 parser / numeric trace 是否返回必要字段；
- 根据返回结果决定 `accepted` / `context_only` / `rejected` / `typed_gap` / `commercial_gap`；
- 维护 tool planning、tool ledger、source route attempt、promotion decision 和 repair route。

TECH_02 不拥有：

- PDF 表格解析算法；
- XBRL exact row selector；
- 数值复算程序；
- 表格 lineage 构建；
- 文档切分 / index 构建策略本身；
- 最终投资判断或 writer 成稿。

换句话说：`TECH_02 owns orchestration and promotion logic, not parsing implementation.` Parser、NumericProgramTrace、DocumentMetadataIndex 的实现分别归 `TECH_04` 和 `TECH_03`；TECH_02 只声明需要什么、调用什么、验收返回结果是否够用。

## 3. EvidenceRequest Compilation

`EvidenceRequest` 只能由 `DecisionSurfaceCell` / `RepairTicket` 编译而来，不能由自由搜索词直接驱动。

必备字段：

- `request_id`
- `decision_surface_id`
- `cell_id`
- `evidence_slot_id`
- `requester_role`
- `accepted_evidence_role`
- `evidence_domain`
- `target_entities`
- `target_periods`
- `metric_intent`
- `product_intent`
- `granularity`
- `unit`
- `source_policy`
- `metadata_binding_requirements`
- `numeric_binding_requirements`
- `acceptable_proxy`
- `forbidden_substitutions`
- `preferred_routes`
- `fallback_routes`
- `topk_policy`
- `budget`
- `stop_condition`

编译规则：

- 必须绑定 `cell_id` 和 `evidence_slot_id`。
- 必须声明 entity / period / source policy / accepted evidence role。
- 必须声明 forbidden substitutions，例如不能用 total revenue 代替 CoWoS capacity，不能用新闻线索代替 verified direct customer relationship。
- 必须说明 evidence 的角色：`fact`、`numeric_fact`、`official_commentary`、`context`、`proxy`、`counterevidence`、`gap_evidence`。
- 如果 request 需要 exact number，必须声明 `numeric_binding_requirements`，由 TECH_04 负责解析和复算。
- 如果 request 需要文档/section/table 绑定，必须声明 `metadata_binding_requirements`，由 TECH_03 / TECH_04 返回 lineage。

这一节决定系统不会“看到什么写什么”。

## 4. Tool Registry

Tool Registry 登记每个工具能查什么、不能查什么、输出可以支持什么 claim，以及失败后如何 fallback。

必备字段：

- `tool_id`
- `tool_name`
- `capability`
- `input_schema`
- `output_schema`
- `source_role`
- `source_authority`
- `can_support`
- `cannot_support`
- `cost_class`
- `latency_class`
- `failure_types`
- `fallback_tools`
- `permission_scope`
- `forbidden_claims`

示例：

```json
{
  "tool_name": "RelationshipGraphSearchToolV2",
  "capability": [
    "verified_relationship_edge",
    "relationship_lead",
    "sector_exposure"
  ],
  "source_authority": [
    "official_filing",
    "official_company",
    "press_release",
    "shipment_lead",
    "news_lead"
  ],
  "can_support": [
    "verified_customer_supplier_if_high_confidence",
    "partner_channel",
    "economic_exposure"
  ],
  "cannot_support": [
    "revenue_contribution_without_disclosure",
    "inferred_customer_as_fact"
  ],
  "failure_types": [
    "entity_resolution_gap",
    "source_gap",
    "relationship_direction_missing"
  ],
  "cost_class": "medium",
  "permission_scope": "runtime_read_only"
}
```

关系图谱里的新闻线索、运输线索、行业暴露不能和 verified direct edge 混在一起；只有高置信 direct / contractual evidence 才能写成客户或供应商事实。

## 5. Evidence Tool Planner State Machine

Evidence Tool Planner 可以由模型参与选择工具和解释观察结果，但它不能直接晋升证据。证据晋升必须交给 Evidence Gate。

状态机：

```text
INIT
 -> COMPILE_REQUEST
 -> SELECT_TOOL
 -> EXECUTE_TOOL
 -> OBSERVE_RESULT
 -> CLASSIFY_CANDIDATE
 -> NEED_MORE?
 -> FALLBACK_OR_STOP
 -> EVIDENCE_GATE
 -> BUILD_RESPONSE
```

每步必须记录：

- `planner_step_id`
- `request_id`
- `state`
- `selected_tool_id`
- `selection_rationale`
- `tool_invocation_ref`
- `observation_ref`
- `candidate_refs`
- `failure_type`
- `fallback_if_fail`
- `budget_before`
- `budget_after`
- `stop_reason`

防止无限搜索的硬约束：

- `max_tool_calls`
- `max_fallback_depth`
- `source_authority_stop_rule`
- `commercial_gap_stop_rule`
- `confidence_threshold`
- `duplicate_candidate_stop_rule`
- `route_exhaustion_stop_rule`

例：如果 official-first 连续失败，并且公开来源没有 exact capacity，则不要无限 web search，应生成 `commercial_gap` 或 attempt-backed `typed_gap`。

## 6. Retrieval / Reranking / Chunk Neighbor Policy

Reranker 只负责 candidate ordering，不能决定 evidence promotion。topK 也不应是全局固定值，而应由 `EvidenceRequest.topk_policy` 按 evidence slot、source policy 和成本预算决定。

建议第一版采用分段 topK：

- `candidate_top_k`：每条 route 初始候选，建议 20-50，用于 lexical / vector / metadata-filtered recall。
- `rerank_top_k`：进入 reranker 的候选，建议 8-20，视 request 复杂度和 source diversity 调整。
- `evidence_candidate_top_k`：送入 Evidence Gate 的候选，建议 1-5，必须带 metadata / source / lineage。
- `neighbor_window`：对命中 chunk 的上下文扩展，默认同 document / section 下前后 1-2 个 chunks。
- `source_diversity_cap`：同一 source / document 不应占满全部 candidate，除非 source policy 明确要求 single official source。

为避免 chunk 切断造成误判，DocumentMetadataIndex 必须支持：

- `doc_id`
- `source_id`
- `section_id`
- `table_id`
- `page_range`
- `row_range`
- `prev_chunk_id`
- `next_chunk_id`
- `parent_section_id`
- `chunking_method`
- `token_start`
- `token_end`
- `parse_boundary`

runtime 不应在以下情况下直接判断“知识库没有”：

- top hit 在 chunk 开头或结尾附近，句子明显被截断；
- chunk 引用了 “above / below / following table / prior period”；
- 命中 table body 但缺少 header、unit、period 或 footnote；
- metadata 命中了正确 document / section，但 reranker 没拿到相邻 chunk；
- 同一 `doc_id` / `section_id` 下存在相邻 chunk 或 parent section 可扩展；
- parser 返回 `metadata_binding_missing` 或 `table_context_missing`。

正确动作是先发起：

- `NeighborChunkRequest`
- `SectionExpansionRequest`
- `TableContextRequest`
- `MetadataFilteredRequery`

只有在 neighbor expansion、section/table context expansion 和 metadata-filtered requery 均失败后，才允许把问题升级为 `retrieval_exhausted`、`SourceHunterRequest` 或 attempt-backed `typed_gap`。

## 7. SourceHunter Trigger Policy

SourceHunter 只在内部 KB/RAG/DB 不足、官方源优先策略要求、或 supplement runtimeization 时触发。它必须单独记账，不得把补源伪装成既有知识库能力。

允许触发：

- internal KB / RAG / SQL 不足；
- `source_policy` 要求 official-first；
- Evidence Gate 拒绝候选但判断公开来源可能可得；
- P36 supervisor supplement 需要 runtime 化；
- RepairTicket 指向 `evidence_missing`、`metadata_missing`、`parser_gap`、`source_authority_gap`。

禁止触发：

- writer 私自补源；
- specialist 绕过 `EvidenceRequest` 私有搜索；
- source policy 禁止 third-party 时，用新闻补 official fact；
- commercial-data gap 被低质量网页强行替代；
- 未经 ToolRegistry / permission gate 登记的自由浏览。

## 8. Evidence Gate Promotion Contract

Evidence Gate 是 promotion 的唯一入口。它不是一个纯 LLM 判断器，也不是纯规则表；第一版应采用规则优先、agent 辅助、必要时人工复核的混合机制。

判定权归属：

- deterministic gate 负责硬约束：entity、ticker、period、unit、source authority、document metadata、parser lineage、numeric trace、forbidden substitutions、permission。
- Evidence agent 可以提出 `classification_suggestion`、`reasoning_summary`、`repair_suggestion`，但不能单独晋升证据。
- Lead 可以裁决是否把 gap 披露给 writer，但不能 override deterministic hard fail。
- Human reviewer / Workbench 可对高影响或歧义 evidence 做最终 accept / reject / supersede。

Promotion status 固定为：

- `accepted`
- `context_only`
- `rejected`
- `typed_gap`
- `commercial_gap`

### 8.1 accepted

可进入 `DecisionSurfacePack`，可被 specialist 用于 judgment，可被 writer 引用。

要求：

- source authority 达标；
- entity / period / unit / segment 绑定达标；
- claim scope 明确；
- citation ref 可用；
- 若涉及数字，numeric trace 满足要求；
- 未触犯 forbidden substitutions。

### 8.2 context_only

可作为背景或 proxy，不可单独支撑结论。

例：

- 媒体报道行业紧缺；
- 第三方预测 AI server demand；
- 行业报告称供应链紧张；
- graph lead 表明可能存在商业关系，但没有 direct/contractual proof。

### 8.3 rejected

不能进入 pack，只能留审计记录。

例：

- entity 错；
- period 错；
- source authority 不够；
- claim 越权；
- 用 total revenue 代替 CoWoS capacity；
- 用新闻线索写成 verified customer fact。

### 8.4 typed_gap

公开来源可能存在，但当前链路没拿到或没解析成功。

例：

- `fetch_fail`
- `parser_gap`
- `metadata_missing`
- `row_selector_gap`
- `entity_resolution_gap`
- `numeric_trace_missing`

### 8.5 commercial_gap

合理判断该信息需要付费数据、公司未披露或非公开渠道。

例：

- exact CoWoS capacity by customer；
- real-time HBM allocation；
- specific NVIDIA order allocation；
- customer-level AI server margin bridge。

不是所有 gap 都应该 repair。`commercial_gap` 和 attempt-backed `typed_gap` 可以直接进入 writer boundary，但不得被写成事实结论。

## 9. EvidenceResponse

EvidenceResponse 是 Evidence Layer 返回给 Lead / Specialist / DecisionSurfacePack 的唯一主对象。

必备字段：

- `response_id`
- `request_id`
- `cell_id`
- `evidence_slot_id`
- `promotion_status`
- `accepted_evidence_refs`
- `context_only_refs`
- `rejected_candidate_refs`
- `typed_gap_refs`
- `commercial_gap_refs`
- `tool_use_ledger_refs`
- `parser_request_refs`
- `numeric_trace_refs`
- `metadata_binding_summary`
- `claim_scope`
- `cannot_support`
- `repair_ticket_ref`
- `next_action`

Specialist 只能消费 `accepted` 和明确标注的 `context_only` / `gap`；writer 只能消费下游 `DecisionSurfacePack` 中允许的 material。

## 10. P36 Supplement Runtimeization Fixture

P36 supervisor supplement ledger 的正确用途：

```text
supervisor_supplement_only row
 -> SourceHunterRequest
 -> official-first route attempt
 -> fetch/crawl/parser candidate
 -> Evidence Gate
 -> accepted runtime row or typed gap / commercial_gap
```

fixture 示例：

```json
{
  "supplement_row_id": "sup_p36_tsmc_cowos_001",
  "cell_id": "ai_infra.foundry_packaging.cowos_capacity_rent",
  "supplement_claim": "TSMC CoWoS capacity is a bottleneck for AI accelerator supply.",
  "supplement_source_hint": "supervisor note / external article",
  "runtime_status": "not_runtime_evidence",
  "required_action": "sourcehunter_request",
  "promotion_required": true
}
```

系统必须输出：

```text
SourceHunterRequest
 -> official-first attempts
 -> ToolUseLedger
 -> EvidenceGate
 -> accepted evidence / context_only / typed_gap / commercial_gap
```

如果 fixture 直接进入 writer，测试失败。

## 11. 失败类型

第一版必须覆盖：

- `fetch_fail`
- `dynamic_render_gap`
- `parser_table_gap`
- `row_selector_gap`
- `metadata_binding_missing`
- `table_context_missing`
- `chunk_boundary_gap`
- `low_authority_source`
- `numeric_sanity_fail`
- `period_unit_mismatch`
- `entity_resolution_gap`
- `commercial_gap`
- `permission_denied`
- `budget_exhausted`
- `route_exhausted`

## 12. 工具采用边界

PRD 中已验证可作为设计输入的工具：

- SEC EDGAR APIs / CompanyFacts / Atom / RSS；
- feedparser；
- Crawl4AI；
- Trafilatura；
- pdfplumber；
- Camelot；
- MarkItDown；
- Docling；
- GDELT + Trafilatura；
- OpenBB minimal stack。

这些工具目前只是 PoC 通过或 fallback 可用，不是 FIN runtime 已集成能力。`Crawlee + Playwright`、`news-please`、`MinerU` 仍需单独 fixture 才能进入主路径或重型 fallback。

### 12.1 2026-07-10 暂定吸收方向：source / parser / table fallback 分层

本节是审计前的暂定修改方向，不表示已改 runtime，也不表示要立刻全量重建现有知识库。

第一版吸收原则：

- `SEC CompanyFacts / XBRL`：仍然优先级最高。能从官方结构化口径拿 exact numeric fact 时，不应使用 PDF 表格或网页 chunk 替代。
- `SEC EDGAR APIs / Atom / RSS / feedparser`：作为官方披露发现与增量监控主路径。
- `OpenBB`：用于公开市场 / 宏观 / 财务数据的 bounded context，不得绕过 source authority / numeric trace。
- `GDELT`：作为 discovery-only 新闻线索，不直接支撑公司事实或 exact numeric claim。
- `Trafilatura`：作为新闻 / 普通网页正文抽取主力候选。
- `Crawl4AI`：作为复杂网页 / 动态网页的 agentic crawling 候选。
- `Crawlee + Playwright`：作为复杂站点和动态渲染 heavy fallback，需 permission / cost gate。
- `MarkItDown`：轻量 Office / PDF / 杂文件文本 visibility fallback，适合快速判断 source 是否值得继续解析，不适合作为最终 table fact 来源。
- `pdfplumber`：可解析文本 PDF 的表格第一层主力候选。
- `Camelot`：规则表格 fallback，适合线框明显、表格型 PDF。
- `Docling`：heavy fallback，适合复杂 PDF、layout、table lineage，需要成本与吞吐审计。
- `MinerU`：扫描件、复杂研报、表格困难场景的重型 fallback，成本更高，不应默认全量跑。

Tool Planner 可以在同一个 `EvidenceRequest` 内根据 observation 重新选择工具，但 fallback 选择必须受 Tool Registry、permission gate、budget、source policy 和 Evidence Gate 约束。典型顺序：

```text
Official structured numeric:
  SEC CompanyFacts / XBRL -> issuer filing table parser -> typed_gap / commercial_gap

PDF text/table:
  MarkItDown visibility -> pdfplumber -> Camelot -> Docling -> MinerU

Web / news:
  requests / Trafilatura -> Crawl4AI -> Crawlee + Playwright -> typed_gap
```

所有 fallback 结果都只能成为 candidate。最终是否进入 `accepted`、`context_only`、`rejected`、`typed_gap` 或 `commercial_gap`，仍由 Evidence Gate 决定。

### 12.2 审计前置条件

在决定是否重切 chunk、重跑 parser 或替换表格抽取链路前，必须先完成现有 runtime 对应环节审计：

- 现有 chunk profile、chunk size、overlap、source_type 覆盖和每份材料 chunk 数分布；
- SEC / IR PDF / non-US annual report / press release / product page / news 的 retrieval precision 与 neighbor recovery；
- 表格抽取成功率、`TABLE_START/TABLE_END` 平衡、header / unit / period / footnote 绑定；
- SQL exact rows 与 runtime rows 的 entity / period / unit / scale / row-label sanity；
- `usd_thousands`、`usd_millions`、percent、delta、per-share、share-count 等 scale / unit 错误；
- row selector false positive，例如把 total revenue、bank accounts、inventory 或 percentage change 当成目标 KPI；
- Evidence Gate promotion rate：RAG hit / table row / parser row 从 candidate 到 accepted 的实际转化；
- 失败类型分布：`chunk_boundary_gap`、`metadata_binding_missing`、`table_context_missing`、`row_selector_gap`、`numeric_sanity_fail`。

审计完成前，不做 blind full reingestion，不把新工具替换成默认主路径，也不把 PoC 结果写成 runtime 能力。

## 13. 与其他 TECH 的边界

- `TECH_01` 定义 cell、evidence slot、EvidenceRequest 入口和 RepairTicket；
- `TECH_03` 提供 DocumentMetadataIndex / RAG candidate / chunk lineage / neighbor expansion；
- `TECH_04` 实现 parser、row selector、NumericProgramTrace 和 table lineage；
- `TECH_05` 消费 EvidenceResponse 做 domain judgment，不私有化检索工具；
- `TECH_06` 承接 tool permission、sandbox、durable ToolInvocation；
- `TECH_09` 记录 tool observation 到 claim/cell 的 provenance，并提供 Workbench evidence review；
- `TECH_10` 评估 tool trajectory、promotion accuracy、gap classification 和 chunk-neighbor recovery。

## 14. 第一批 fixture

1. AI infra cell-level EvidenceRequest -> ToolUseLedger fixture。
2. EvidenceRequest compilation fixture：从 `DecisionSurfaceCell` 编译 entity / period / source policy / forbidden substitutions。
3. ToolRegistry claim-boundary fixture：relationship graph lead 不得晋升为 verified customer fact。
4. EvidenceToolPlanner state-machine fixture：max tool calls / fallback depth / stop rule 生效。
5. Chunk-neighbor recovery fixture：命中截断 chunk 时先召回邻居 chunk / section / table context，而不是直接 SourceHunter。
6. Official dynamic page fallback：requests / Trafilatura -> Crawl4AI。
7. PDF fallback：MarkItDown / pdfplumber / Camelot -> Docling。
8. P36 supplement ledger -> SourceHunterRequest -> EvidenceGate -> typed result fixture。
9. EvidenceGate promotion fixture：accepted / context_only / rejected / typed_gap / commercial_gap 五类全覆盖。
10. Parser/Numeric boundary fixture：TECH_02 调用并验收 TECH_04 trace，但不实现 parser / row selector。

## 15. 验收标准

- 至少一个 EvidenceRequest 能产生多步 tool loop。
- 每步都有 observation summary、failure type、stop reason。
- `EvidenceRequest` 必须绑定 `cell_id`、`evidence_slot_id`、entity、period、source policy、forbidden substitutions。
- Reranker topK 结果不能绕过 Evidence Gate。
- chunk 命中截断时必须先尝试 neighbor / section / table context recovery。
- 未过 Evidence Gate 的 RAG hit / PDF table / news hit 不得进入 writer-allowed evidence。
- SourceHunter supplement rows 与 runtime accepted rows 分账。
- Specialist 不得绕过 Evidence Layer 私有化检索工具。
- TECH_02 不实现 parser / numeric trace，只调用、验收并根据结果 promotion。

## 16. 2026-07-10 External Source Admission / Social Source Gate

外源不能按“网站是否知名”统一接入。TECH_02 必须按 evidence role、authority、claim boundary、可追溯性、许可和增量决策价值执行 source admission。正式进入项目的外源分四条 lane：

1. `persistent_data_foundation`：SEC / non-US disclosure、政府监管、官方市场/宏观/采购等结构化、可版本化、可重复使用的数据。
2. `on_demand_sourcehunter`：issuer IR、官方产品页、客户部署、公开演讲、政策原文、行业标准、动态网页和 case-specific PDF。
3. `discovery_only`：RSS、GDELT、Common Crawl、搜索引擎、普通新闻索引，只产生 lead / event cluster / verification request。
4. `licensed_adapter`：consensus、revision、real-time market、完整 options、borrow、dealer positioning、commercial supply-chain/channel tracker；未授权时返回 `commercial_gap`。

Source admission pipeline 固定为：

```text
decision-cell / evidence-slot incremental value
 -> reachability / license / retention / redistribution check
 -> source identity / authority / claim-boundary registration
 -> snapshot / PIT / revision policy
 -> parser or structured adapter fixture
 -> entity / period / unit / speaker binding
 -> Evidence Gate
 -> specialist-consumption fixture
```

`ExternalSourcePolicy` 至少记录：`source_family`、`evidence_roles`、`authority_level`、`can_support`、`cannot_support`、`entity_period_unit_binding`、`pit_or_revision_support`、`license_policy`、`parser_profile`、`incremental_decision_value`、`maintenance_cost`、`fallback_route` 和 `onboarding_status`。

### 16.1 Social source 不是统一低信源

X/Twitter、微博、微信公众号、YouTube 等平台上的第一方账号可以是重要来源，但必须把以下身份拆开：

```text
account authenticity != statement authenticity != underlying claim truth
engagement != representativeness
announcement != implemented policy / delivered product / measured performance
```

Evidence Gate 对 social candidate 使用以下规则：

- 公司、政府机构、公众人物或产品团队的高可信第一方账号，可以证明“该账号在该时点发表了这段内容”，并可支持 attributed statement、policy intent、product announcement、roadmap lead、event catalyst 或 company-authored context。
- 平台 badge 不能单独作为身份凭据。必须结合 verification type、官方域名反链、组织 affiliation、历史 handle、账号 ID 和 source snapshot；特别是 X 的普通 blue check 可能来自 Premium subscription，不等同于旧式身份认证。
- 公众人物、CEO 或产品负责人的发言不能自动证明其描述的事实已发生。政策生效、产品可用性、性能、销量、订单、收入等仍需官方文件、产品文档、监管文本、可观测 runtime 或其他高权威证据。
- 高赞评论、回复和用户帖子可以进入 `user_feedback_signal` / `observed_platform_discourse`，但若没有采样窗口、query、去重、bot/spam 处理、平台覆盖和 representativeness audit，只能是 `sentiment_example`，不得写成“公众普遍认为”。
- 无 canonical post/channel URL、post ID、作者账号 ID、发布时间或可验证 snapshot 的截图，只能作为 lead；不得晋升。

Social candidate 的 promotion identity 固定为：

- `accepted_attribution_only`：可确认谁在何时说了什么；不确认 underlying fact。
- `company_or_official_authored_context`：在角色权限范围内可作为第一方上下文。
- `context_only_public_statement`：有归因但内容仍需事实核验。
- `sentiment_sample_only`：可展示为用户反馈样本，不代表总体舆情。
- `lead_only_needs_identity_or_fact_verification`：身份或事实链不足。
- `rejected_manipulated_or_untraceable`：伪造、断章取义、无法定位或 provenance 失败。

### 16.2 Statement / fact conflict gate

当公开人物或官方账号发言与 filing、监管文件、产品实测、历史事实或其他 accepted evidence 冲突时，系统不得让人物权威覆盖事实 gate。必须生成 `ClaimConflictRecord`，区分：

- `fact_claim_conflict`：高权威事实优先；发言保留为 attributed claim，并标记 contradicted / unsupported / stale。
- `intent_or_forecast_conflict`：保留为意图或预测，不能改写成已发生事实；进入 what-would-change / monitoring。
- `opinion_or_rhetoric`：只做叙事、谈判、风险或舆情信号；其中包含的可验证事实单独核验。
- `market_impact_despite_truth_uncertain`：即使内容未证实，发言本身可能成为价格或政策预期事件；可进入 event/catalyst cell，但必须保留 truth uncertainty。

Lead 可以决定是否继续 repair、是否披露冲突和如何呈现，但不能把 hard-failed fact 改成 accepted。Writer 只能消费带 attribution、claim identity 和 conflict status 的 DecisionSurface material。

## 17. 2026-07-12 Evidence Business Truth / Case and Memory Contract

根据 TECH_00 Owner Constitution，TECH_02 是 EvidenceRequest、Evidence Gate、PromotionDecision、Rejection 和 attempt-backed typed/commercial gap 的业务真相 writer。TECH_03 返回 candidate/address，TECH_04 返回 numeric hard-gate result，TECH_05 只消费 accepted/context/gap refs。

### 17.1 EvidenceRecord identity

每次 gate decision 生成 immutable `EvidenceRecordVersion`，至少包含 case/case-version、cell/slot、claim requirement、candidate/source snapshot、entity/metric/period/unit/scope、authority/role、parser/numeric refs、decision、reason codes、supports/cannot-support、actor/event refs、as-of/available-at、permission/license、supersession 和 downstream impact refs。

Promotion status 固定为 `accepted / context_only / rejected / typed_gap / commercial_gap`。`accepted` 也必须声明可支持的 claim strength/scope；不能把“已接受”理解为支持任意结论。

TECH_02 是 promotion head 的唯一 writer：

- TECH_03 不得因候选来自历史 AcceptedFactMemory 就自行推进当前 Case accepted；
- TECH_04 可 hard-reject numeric eligibility，但不能批准非 numeric claim 的语义充分性；
- Evidence Agent/LLM 只提交 classification suggestion；
- Lead 可以停止 repair或接受 bounded disclosure，不能把 hard fail 改成 accepted。

### 17.2 Definition conflict and rejection memory

新增 `EvidenceDefinitionConflict`：metric definition、entity/segment、period/vintage、unit/scale、source-role 或 claim-scope 不一致。它必须在 rerank 后、promotion 前显式处理，不能用相似度高掩盖定义错误。

所有 rejected candidate、forbidden substitution、failed route 和 promotion revocation 产生 `MemoryWriteCandidate`，写入 TECH_03 的 negative/repair index。该对象只携带 TECH_02 的 immutable decision ref、reason、scope、TTL/retention/permission 和 reuse policy；TECH_03 不重新裁决。

### 17.3 Case / refresh / supersession

EvidenceRequest 必须绑定 `case_id / case_version / cell_version / evidence_slot_id`。Follow-up 或 refresh 可以复用旧 observation，但必须重新检查 freshness、revision、permission 和 current claim requirement；历史 accepted 不自动变成本次 accepted。

Source revision、parser correction、numeric invalidation、license change 或 reviewer revoke 产生新的 PromotionDecision/revocation version，并向 TECH_01/03/05/09/11 发出 impact refs；不得静默改写旧 EvidenceRecord。

### 17.4 Provider-neutral search capability

`SearchProviderCapability` / `SourceProviderPolicyVersion` 至少声明 source families、authority roles、jurisdiction、license/redistribution、network/credential scope、freshness、cost/latency、structured output、failure taxonomy、fallback compatibility 和 data residency。Google/Tencent/general Web/internal KB/licensed provider 都只能输出统一 CandidateBundle；provider ranking 或 snippet 不获得 promotion 权。

模型可在 Evidence Tool Planner 的 budget/permission/stop rule 内选择 provider、观察失败和切换 fallback；切换 provider 生成新 ToolInvocation/Observation，并由 TECH_10 做 provider-swap non-regression eval。

### 17.5 Accountability events

EvidenceRequest created、provider selected、tool invoked、candidate classified、accepted/rejected/revoked 和 gap closed 都必须引用 TECH_06 ActorSnapshot/AccountabilityEvent。Supervisor supplement 保持 `not_runtime_evidence`，只有经过正式 SourceHunter/Evidence Gate 后才能产生新的 runtime EvidenceRecord。

本节状态为 `documented / contract_draft`；不表示现有 retrieval rows 已重新晋升。

## 18. FIN 0.1.3 S1-06 MCP Operational Truth（2026-08-07）

MCP 工具“写进 registry”不等于“stdio server 已暴露并能有界执行”。S1-06 把协议连接、资源绑定、handler 执行和研究质量拆开验收：

1. registry 的九个业务工具必须与 stdio server 业务工具面逐项一致；`list_sec_agent_tools` 只是发现工具，不计入业务工具数。
2. 本地 manifest、BM25/ObjectBM25、Exact-Value Ledger、market/industry snapshot 通过版本化 runtime profile 绑定；显式请求参数优先，其次环境变量，最后才使用 profile。缺失资源返回 typed binding failure，不进入 handler。
3. 每个 tool invocation 由独立可复用 worker 进程执行。cold start、warm reuse、resource binding、handler elapsed、typed failure、timeout 和 terminal 都写入 `McpOperationalReceipt`；timeout/cancel 必须终止 worker process tree，下一次调用以 fresh cold worker 恢复。
4. `sec_search_filings` 在 `rerank_budget=0` 时显式进入 `context_reranker=none / allow_bm25_only_pipeline=true`，不得仍加载 BGE；只有请求 rerank 时才要求已绑定的本地 reranker。没有 reranker 时 typed fail，不允许隐式访问错误的 Linux 路径或远程下载。
5. BM25-only 只证明 operational availability，不能作为 S1-08 recall、ranking 或 source-diversity 质量证据。BGE/Milvus、新外部来源抓取与 Evidence promotion 分别留给 S1-08、S1-07 和 Evidence Gate。

Runtime owner 为 `src/sec_agent/mcp_operational.py`、`src/sec_agent/mcp_server.py` 和版本化 `configs/mcp/sec_agent_mcp_runtime_profile_v0_1.json`。当前实现已通过 deterministic tests 与 stdio registry parity smoke；clean-commit cold/warm 本地资源 proof 仍是 S1-06 关闭前置，故状态暂为 `runtime_injected / deterministic_proven / clean_operational_proof_pending`。
