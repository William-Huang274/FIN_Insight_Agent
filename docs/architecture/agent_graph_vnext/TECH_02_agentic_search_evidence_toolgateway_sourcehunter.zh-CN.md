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

### 1.1 2026-08-08 relationship-aware semantic control

Provider-neutral `SearchIntent` 与 Provider wire request 已分层。研究合同保留 subject、evidence owner、关系方向、期间、来源族和语言；adapter 只负责把它压缩成各服务可接受的请求，不得丢失这些原子，也不得把 Gold URL 塞进 query。

在国内 Provider 凭据暂不可安全使用时，Firecrawl 只作为查询编译质量控制组：固定执行 customer/supply 的 24 个 `semantic_open_web` 单元，不与 22 个 `precise_official_domain` 单元合并。其 exact-once runtime 顺序固定为：

```text
proof-bound query identity
 -> safe request capture
 -> one network attempt
 -> raw response or typed failure atomic capture
 -> per-call terminal
 -> 24 identities aggregate terminal
 -> evaluator-only target/source registry load
 -> useful@10 / target-in-pool / date / diversity / credits / latency
```

搜索响应在本阶段始终只是 locator candidate。即使控制组所有门通过，也不能自动进入正文抓取、Evidence、reranker、SourceHunter production 或 Agentic Research；它只证明该查询矩阵值得交给国内 Provider 做同合同对照。

该控制组的 live 结果为：24/24 terminal success、topical `133/240`、六个 case-slot exact target `5/6`。这使 relationship-aware compiler 获得 live support，但 Firecrawl lane 因 `0/235` 日期、DELL supply exact miss、中文 exact miss 和 p95 6.877 秒未通过。技术状态必须保留两条独立结论：

- `query_compiler_live_supported=true`；
- `provider_lane_qualified=false`。

不得因为 Provider 总门失败而回滚正确的 SearchIntent 修复，也不得因为 target recall 大幅改善而忽略日期、语言和延迟缺口。国内 Provider 后续复用相同 plan/evaluator；只有 transport adapter 和 credential 不同。

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

Runtime owner 为 `src/sec_agent/mcp_operational.py`、`src/sec_agent/mcp_server.py` 和版本化 `configs/mcp/sec_agent_mcp_runtime_profile_v0_1.json`。当前实现已通过 deterministic tests、stdio registry parity smoke 与 clean-commit cold/warm 本地资源 proof：SEC cold/warm=`13,750/104 ms`、Exact Ledger=`1,317 ms`、market=`3 ms`，missing reranker 在 handler 前 typed fail，worker close 后无 orphan。S1-06 状态为 `L4_scope_pass`。该结论不包含 S1-07 外部 source fetch/parser，也不包含 S1-08 排序质量。

## 19. S1-07 current-source fetch / capture / parser / promotion runtime

S1-03 已有 `CaptureFirstOfficialSourceClient`、官方来源 transport、HTML/PDF/JSON parser 与 content-addressed object store；S1-07 不再平行造爬虫，而是把这些底层件接入当前 MCP `web_evidence_snapshot`。当前合同必须满足：

1. 只允许 HTTPS、明确 allowlist 且 public-network 的 host；阻断 URL credential、localhost/private/link-local/reserved address、跨域 redirect，并把 redirect ceiling 固定为 3。
2. request capture 必须先于网络调用持久化；无论 HTTP、transport 或 parser 成败，response/failure capture 都先于解析/晋升落盘。Authorization、Cookie 和凭据不得进入 capture。
3. 原始 body 以 content-addressed base64 capture 保留；HTML/PDF/JSON parser 输出另存 parser capture，并绑定 response digest、parser adapter、text digest 和完整 lineage。
4. `company_ir_material` / `company_official_product_surface` 必须通过 verified company domain；`official_regulatory_page` / `government_dataset_endpoint` 才能在 parser 成功后晋升为 writer-citable parsed Evidence。news、commerce、developer、social 只可 context-only。
5. web parser 永远不获得 exact numeric authority；精确财务数字仍须 Numeric/SEC Ledger 或独立结构化 parser gate。URL metadata、search snippet、无法解析正文都不得冒充 Evidence。
6. timeout、body size、redirect、domain 与 source call 数均受预算约束；失败保留 attempt-backed typed gap，不以弱来源补齐。

Runtime owner 为 `src/sec_agent/web_evidence_runtime.py`，复用 `src/sec_agent/official_source_attempt_program.py`。当前 deterministic/mutation/broader tests=`82 passed`，真实网络尚未执行；S1-07 只有在 clean/synced commit 上完成一次 DELL/MU/NVDA 三官方来源 exact-once canary 后才可关闭。

首次 exact-once canary 发现当前 Codex 网络将三个公开 IR hostname 映射到 `198.18.0.0/15` synthetic benchmark network，通用 private-network guard 因而在 HTTP 前一致 false-positive。环境兼容只可由受控 runner 在确认所有目标均为显式 allowlist hostname、且所有解析地址均属于 `198.18.0.0/15` 时启用；不得由模型或普通 tool argument 任意打开。该模式仍要求 HTTPS hostname/certificate 验证，并继续阻断 literal IP、localhost、RFC1918、link-local、其他 private/reserved network。R1 capture 必须保留，新提交后只能新 admission 执行一次 R2。

SEC official routes 另有客户端身份合同：`sec.gov` 及其子域在真实 transport 前必须从受控运行环境获得格式有效的联系邮箱，否则 typed `official_source_sec_contact_required`，不得发送未声明自动化请求。联系邮箱只能通过 `FINSIGHT_SEC_CONTACT_EMAIL` 注入，不进入版本化配置、结果 JSON、admission 或普通 telemetry；capture-first 的本机受限原始 request 仍保留真实 User-Agent 以支持审计。不得由模型参数提供或编造联系身份。

最终 live proof 在 clean/synced `86779fd8` 上完成：MU official PDF、NVDA official IR HTML 和 Dell SEC official 10-K HTML 三条路径均完成真实 fetch、raw capture、parse 与 authority-gated promotion。Dell successor 仅发起 `1` 次网络请求，`14,027 ms` 完成，adapter=`official_source_html_text_v1`、Evidence=`1`、gap/retry/model/provider=`0/0/0/0`；contact 明文未进入版本化 result。S1-07 因此为 `L4_scope_pass`。这一状态只关闭 source-runtime 可执行性，不代表 S1-08 的 recall/ranking/currentness/diversity/utilization，也不代表 S3 研究综合或交付报告质量。

## 20. S1-08 Agentic Search quality 与 candidate-pool-first gate

S1-08 先判断必需 Gold Evidence 是否可能进入候选池，再评价排序。评估冻结于 2026-08-06 三案例 benchmark：10 source、33 Evidence、其中 32 mandatory、12 evaluator-only target groups。Planner 永远不可见 expected insight 或 evidence ID；evaluator 只在运行结束后用 digest-bound hidden objects 评分。

预注册 hard gates 为 `target_in_pool=1.0`、`required_slot_recall@8=1.0`、`NDCG@8>=0.85`、`MRR>=0.75`、currentness/diversity-or-typed-exception/reconciliation/selected-pack-coverage=`1.0`、false promotion=`0`。每 target group 最多两次有理由的 query revision，禁止 identical retry。若任一案例 target-in-pool 不足，停止 ranking/reranker；修 candidate generation，而不是调 BGE/Milvus 或扩大 top-k。

entry audit 的版本化产物只有 7 个 distinct active source URL，与 9 个 benchmark HTTP source 的 exact URL overlap 为 `0`；这是保守下界，不否定尚未证明的 equivalent authoritative source。更关键的是 current executable search 仍只有 FIN 0.1.2 合同，query revision runtime 不存在。因此 S1-08 当前为 `upstream_blocked_candidate_generation_before_ranking`。下一实现必须建立 provider-neutral current source catalog、Evidence Tool Planner revision loop、capture-first discovery/fetch/parser/candidate 分轨和 evaluator-only Gold matcher；不得把 benchmark source registry 直接注入 planner 作弊。

### 20.1 current source catalog 与 candidate-generation Runtime

current S1-08 catalog 只拥有 source discovery seed，不拥有答案：entity key、legal name、CIK、官方 landing pages、ecosystem roles、通用 evidence-role blueprints 和预算。Gold Evidence/target ID、expected insight、benchmark document URL 与 hidden scoring object 永远不进入 catalog、query 或 adapter input。客户/供应链扩展由 `cloud_operator / infrastructure_integrator / memory_supplier / foundry / compute_platform` 等角色生成，不通过复制 benchmark URL 生成。

Planner 将 current-case research objective 编译为 issuer results、regulatory reconciliation、customer demand、supply/counterevidence 和 market context 五类 target。每类首次失败最多两次 revision；每次必须改变 terms 或 routes，并保存 trigger、changed query、attempt count 和 stop reason。`subject` 只允许 current case；relationship role 才可扩展其他实体，避免跨案例污染。

Official discovery adapter 的顺序固定为：landing/SEC submissions request capture → raw response capture → locator discovery → source request/response capture → parser capture → candidate promotion。无日期、future、cross-case、unknown entity、缺任一 capture lineage、parser 失败或未晋升都不得进入 candidate pool。local market snapshot 也必须以受控本地 capture/parse receipt 进入，不能用路径占位冒充 Evidence。

Evaluator-only matcher 在 candidate generation 完成后才加载 hidden target groups，并按 normalized source locator、published date 与 authority 共同计算 target-in-pool 和 selected-pack coverage；旧 market snapshot 即使 locator 同名也不能冒充 current Gold。fixture 中 `12/12` target group 进入 pool 且 selected pack coverage=`1.0` 只证明合同上限；真实 canary 未通过前，ranking/NDCG/MRR/BGE/Milvus 仍不准入。Runtime owner 为 `src/sec_agent/s1_08_candidate_generation_runtime.py` 与 `src/sec_agent/s1_08_official_discovery_adapter.py`；历史 R1 policy 为 `v1_0`，当前质量优先 successor policy owner 为 `configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json`。

首次 DELL live canary 在 19 次网络调用、212 秒后以未包装的 `RemoteDisconnected` terminal；raw capture 保留 19 个 request、15 个 response、3 个 typed transport failure 和 13 个 parser object，但最后请求没有 failure capture，整案 partial candidate/gap 也未物化。capture 安全元数据同时证明通用 anchor scorer 会选择 Microsoft 导航/商店/Surface 链接，SEC locator 会优先 DELL 2022/2023 旧 filing。故当前缺口不是调高预算或 reranker，而是 transport exception taxonomy、source-family/path/date/currentness locator filter、partial terminalization 和 fetch 前质量筛选。下一实现必须先用 immutable capture replay 零调用证明这些结构，再另行决定 replacement canary；R1 不得重放或追认。

### 20.2 质量优先 SourceHunter 与 Capture Replay 一体化合同

Capture replay 不是 transport 修复后的附属测试，也不能被当作 live 检索质量证明。它是 SourceHunter 每一层质量决策的共同基线：Evidence Objective/Slot、provider route、fetch 前 locator qualification、fetch 后 content qualification、promotion、gap、预算和 terminal materialization 都必须能在同一条已捕获轨迹上解释。

统一数据面分两层：

- restricted exact manifest 只在 Git 中保存 content digest、脱敏 locator metadata、capture type 和 lineage ref；原始正文留在受限 content-addressed store；
- portable sanitized fixture 保存 navigation anchor、SEC form/date、connection termination 和 partial-terminal 结构，不包含 hidden Gold、expected insight、凭据、Cookie、runtime contact 或私有推理。

SourceHunter 必须先将 research question 编译为五类 Evidence Slot：issuer results、regulatory reconciliation、customer demand/deployment、supply/counterevidence、market context。每个 slot 绑定 entity role、source family、as-of window、required/optional、stop condition。query revision 必须由 missing slot 和 route failure 驱动，不得 identical retry。

Discovery 核心保持 provider-neutral，并以版本化 capability 声明以下路线是否可运行：SEC submissions/form/exhibit、issuer IR results/news/events/sitemap/RSS/structured endpoint、external/site search、customer/supplier official disclosure、government/industry source。没有运营 provider 或 credential 时返回 `route_unavailable`；不得把定向官方抓取宣称为 broad Web search。

fetch 前必须按 source family、path、title、entity、form、publication date、as-of fit、slot fit 和 canonical dedupe 判定；navigation/store/privacy/generic-product/footer link 不得消耗 document-fetch budget。fetch 后再按正文 entity/period/topic/source type/authority/evidence role/factual-vs-promotional 和 substantive duplicate 判定 candidate/promotion。Web 正文仍不拥有 exact numeric authority。

transport 必须把 `RemoteDisconnected`、connection reset/abort 等连接终止写成 typed failure capture，并在每个 step 后原子物化 partial attempt、candidate、rejection、receipt、gap 与真实调用计数。未知项目异常可以终止整案，但不能删除先前形式化状态。

统一 proof 必须同时通过：R1 全请求终态分类、已知导航噪声零 fetch、current eligible 存在时 stale filing 零选择、partial materialization 100%、三案例 full-fake/mutation、Gold/cross-case leakage=0、qualified-document yield 与 Evidence Slot coverage。DELL replacement live 的拟议 ceiling 为 16 network calls、0 model/provider/retry、每次 30 秒、全案 300 秒；是否签发仍需 clean proof 后独立决定。live target-in-pool 与 required-slot recall 未通过前，ranking/NDCG/MRR/BGE/Milvus 和 S3 继续阻断。

当前 v2 零调用实现已注入 Runtime：`s1_08_source_quality.py` 统一 locator/content quality，candidate runtime 编译五类 `EvidenceSlot` 并在每次 attempt 后调用 adapter checkpoint，official discovery adapter 在 fetch 前后分别做质量判定，official transport 将连接终止统一转为 typed failure。v2 catalog 公开 provider operational truth：SEC、普通 IR 与本地 market 可执行；structured IR 只有 route contract、尚无 feed/sitemap locator adapter，`external_site_search` 只有 provider-neutral 接口、尚无运营 Provider，二者必须返回 route unavailable。DELL R1 restricted store `19/19` request digest 审计、脱敏 replay、三案 fake/mutation与 focused/related `46 passed`；效率门按 discovery＋document fetch 同一网络调用口径计算为 `6/11=0.545455`，不允许 replay 用较窄分母虚高；v1 revision-one SEC widening保持可重放。当前状态仅为 `zero-call engineering pass / clean independent proof pending`，不是 live 或 L4 scope pass。

clean `ee5ebf3b...17925` 独立证明由两个 Git archive 与两个 fresh process 完成，每边 `46 passed`，19 个 restricted request object 全部按 digest 复验，proof SHA 与仓库一致。首次 archive 因 Windows CRLF/Git LF 导致 byte mismatch，materializer 固定 LF 后重新双复证通过。该结果将 A..G 提升为 `independently proven`，只允许进入 Q-H authority decision；不能据此声称 live source reachability、target-in-pool、ranking 或研究内容质量通过。

Q-H 已批准一份 DELL R2 replacement authority，但旧 R1 admission/runner 不是合法 successor：旧 output 已物化，且 authority envelope 未绑定 Q-H decision 和 independent proof。执行前必须用新 schema/namespace/result path 建立最小 successor binding，并在任何 network side effect 前用 shared ledger exact-once reserve；这属于 authority control，不是再次修改 SourceHunter 质量逻辑。

R2 successor 已完成零调用实现。authority v1.0 因把 engineering proof SHA 误标为 independent proof SHA 而在测试中 fail closed，未被消费；v1.1 分离两份 SHA。successor admission 绑定 decision/proof/catalog/R1 terminal/commit，并重算 R1 terminal body；runner 把 DNS resolution 留到 shared-ledger reserve 之后，transport 只允许 Codex synthetic range 而非任意 private IP；30 秒 per-call 外再加 300 秒 overall deadline。新 contract/namespace/result path 与 R1 完全分离。

clean successor proof 进一步成为 admission 的 mandatory binding，固定 Runtime/Runner SHA 并要求 fresh archive 的 53-test pass。Project OS run-scope 目前是显式 blocker-name 匹配，未知 scope 字符串可能不被自动拒绝；这是共享治理层缺口。当前 R2 通过 direct proof binding fail closed，通用 scope registry/unknown-scope policy 留给 S0/S5 统一修复，避免把 SourceHunter 阶段扩成控制面重构。

runner 的第一次 execution probe 另发现 core API/CLI projection 形状差异：核心 preflight 提供 blocker list，CLI compact 才增加 blocker count。successor 现以核心 list 为权威，并在 count 存在时交叉验证；v1.1 clean proof 绑定修复后的 source SHA。该 probe 位于 admission 前，未消耗 authority 或产生网络副作用。

DELL R2 证明控制面已能完整 terminalize，但 operational SourceHunter 质量仍未达标：16 network calls 只产生 2 个 role candidates/1 个 unique SEC source，qualified yield=0.125，三 role typed gap，Gold target-in-pool=0。大量 anchor 因 slot-fit、stale 或 publication-date unproven 被拒，且 structured IR/external search 仍 route-unavailable。后续改进应增加真实 provider/locator 能力并按 Evidence Slot 调度预算，不能靠放宽质量门、追加 retry 或先调 reranker掩盖 candidate pool 缺口。

### 20.3 R2 后官方域 Provider、关系方向与 Slot Budget 合同

R2 capture replay 进一步证明，失败不只是“少一个搜索 Provider”。16 次调用中 3 次是 landing discovery、13 次是 document fetch；12 个 document fetch 被 customer slot 独占，supply slot 在 ceiling 前没有一次真实网络调用。`document_ceiling_per_query=1` 在当前实现中限制 accepted candidate 数，不限制 document fetch 数；因此一个未通过的 slot 可以连续扫描文档并饿死后续 slot。另有 9 个 Microsoft `/customers/story/` 页面被粗略归为 `customer_official_disclosure`，但它们描述 Microsoft 的下游客户，不等于 Microsoft 自身基础设施需求；Evidence Slot 缺少经济关系方向。

下一合同版本必须同时修改 provider、metadata、slot 和 budget，不能只增加网址或调用数：

1. `SearchProviderCapability` 显式区分 `declared / configured / operational / replay_proven / live_proven`。`official_ir_feed_discovery` 消费官方 HTML alternate feed、RSS/Atom、robots/sitemap 与同域结构化 locator；`official_domain_bounded_search` 只在 allowlisted 官方域内构建并查询 URL index，不得宣称 broad Web search。没有实际运营 Provider 时，`external_site_search` 继续 `route_unavailable`。
2. SEC discovery 按实体和角色支持国内 `10-K/10-Q/8-K` 与 foreign issuer `20-F/6-K`，并可作为 customer/supply evidence owner 的官方候选路线；form 或 filing authority 仍不能绕过正文 Evidence Role gate。
3. `EvidenceSlot` 新增 `subject_entity / evidence_owner_entity / ecosystem_role / claim_direction / allowed_source_owner_roles / forbidden_nested_relationships`。customer-demand 必须是客户自身 capex、capacity、deployment 或 infrastructure disclosure；客户的客户案例不得支撑该经济边。supply slot 同理必须绑定供应商、foundry、memory 或 compute owner 自身的 capacity/supply/constraint 叙述。
4. publication metadata 输出 `date_value / date_kind / date_source / date_confidence / capture_ref / conflict_status`。优先 regulatory filing date、feed timestamp、JSON-LD、OpenGraph、semantic `time`、官方 release masthead 和 event/transcript heading；sitemap `lastmod`、HTTP `Last-Modified` 只能先成为 modified-date evidence。query as-of、URL 中的 fiscal period 和任意正文财务期间不得冒充 publication date，冲突必须 typed fail。
5. 调度改为 slot round-robin 与 reservation。全局 16 次上限在下一零调用包中保持不变：issuer＋regulatory 共享 4、customer 4、supply 5、market 0、所有网络 slot 至少获得一次机会后才释放 3 次 contingency。每 attempt 独立限制 `maximum_document_fetches=2` 与 `maximum_accepted_unique_documents=1`；route/local-source unavailable 只 terminal 一次，不做无效 revision。
6. canonical `SourceDocument` 与 role-specific binding 分离。同一 URL/capture 只抓取和物化一次，可被多个 role 引用；主效率指标为 `accepted unique canonical documents / actual network calls`，role coverage、source diversity、slot starvation 和重复 fetch 单列。R2 的两条 role candidate 因来自同一 8-K，unique-document yield 应记为 `1/16=0.0625`，不能继续用 role binding 数虚高。

机器处置为 `configs/releases/fin_ia_0_1_3_s1_08_post_r2_provider_candidate_coverage_disposition_v1_0.json`。下一项只实现并零调用证明上述 v3 合同；R2 capture 必须能证明 Microsoft 两份官方 release/event 页的 typed 日期恢复、9 个 nested-customer 页面关系方向拒绝、supply 不再 starvation、market unavailable 零 revision 和 canonical fetch 去重。DELL/MU/NVDA 还须覆盖 20-F/6-K、feed/sitemap malformed、date conflict、cross-domain、relationship reversal 与 quota permutation mutation。通过后另行决定 fresh live；本节不授权网络、模型、ranking 或 S3。

处置收尾的 Project OS negative probe 还证明，当前共享预检只把固定五种 `OPEN_BLOCKER_STATUSES` 视作开放阻断；新的描述性 `open_*` 状态会在 scope 匹配前被静默跳过。S1-08 不承担共享控制面重构，但 RC-P36-156 最新投影必须使用 canonical `open`、wildcard block 与本零调用 scope 显式 allowlist，作为临时 fail-closed。直到状态 schema 与 run-scope registry 在 S0/S5 修复，任何 fresh live 都不能只凭 Project OS 的 `pass`，仍须校验 exact runner/admission/source-SHA binding。

### 20.4 v3 成熟组件采用与零调用实现结果（2026-08-08）

v3 没有引入完整通用爬虫框架，而是在既有 capture-first 控制面内采用两个窄组件：`feedparser 6.0.12` 只解析已经保存的 RSS/Atom bytes；`Trafilatura 2.1.0` 只从已经保存的静态 HTML 生成正文和 metadata candidate。请求、域名 allowlist、budget、relationship direction、publication-date adjudication、candidate promotion、capture lineage 和 terminal result 仍由 FIN Runtime 所有。`Scrapy` 未进入当前调度主线；`Crawl4AI/Playwright` 仍是以后针对动态页单独准入的受预算 fallback，不能因技术文档列出就被视为现有能力。

真实 DELL R2 immutable capture bake-off 使用两份 Microsoft 官方页且网络/模型/Provider/retry 均为 `0`。Trafilatura 相对 BeautifulSoup baseline 将 earnings-event 页的已知导航词命中从 `14` 降为 `0`，press-release 页从 `14` 降为 `1`；但它把 press release 的 `2026-06-30` 报告期误判为发布日期，而页面 masthead 的真实发布日期是 `2026-07-29`。因此第三方 parser 的日期永远只能是低置信 candidate：本地 adjudicator 必须识别 reporting-period context，优先 JSON-LD/OpenGraph/semantic time/release masthead/event heading，并在只有 library-inferred date、modified date或高权威冲突时 fail closed。该回放最终正确恢复 event=`2026-07-29 / official_event_heading`、release=`2026-07-29 / official_release_masthead`，同时把 `2026-06-30` 记为 rejected `reporting_period_end`。

Runtime v3 同时落地：

1. 官方 HTML alternate feed、RSS/Atom、robots/sitemap 与同 host URL discovery；所有 parser 均消费 capture bytes，不自行联网；
2. SEC submissions 增加 `20-F/6-K`；
3. relationship-aware query/candidate binding，nested customer story 在 document fetch 前拒绝；
4. 五 slot round-robin，16 次总预算保持 `4/4/5/0 + 3 contingency`，每 attempt 最多 fetch `2`、接受 `1` 份 unique document；
5. candidate permutation 先确定性排序，同一 canonical locator/capture 跨 role 分别记录 binding、只计一份网络文档；本地 market snapshot 单列，不能进入网络文档收益率分子；
6. v1/v2 query 与 candidate serialization 不注入 v3 字段，历史回放保持兼容。

focused v3＋既有 S1-08 回归共 `48 passed`。DELL/MU/NVDA full-fake 均先按 issuer、regulatory、customer、supply、market 顺序完成首次轮转，slot starvation=`0`；关系、日期、feed/sitemap malformed、20-F/6-K、fetch ceiling、candidate permutation 和 duplicate-role mutation 均 fail closed。该结果只把本实现提升为 `zero-call engineering pass`：official feed/sitemap 与 bounded-domain route 仍只有 replay proof，`external_site_search` 仍 unavailable，且尚未证明新的 live target-in-pool、recall、ranking 或研究内容质量。fresh live 需独立复证和新 authority；本节不授权 R3、MU/NVDA live、ranking、DeepSeek 或 S3。

### 20.5 PRD / TECH / Runtime 互校准后的 S1-08 关闭合同（2026-08-08）

S1-08 不再被描述为“候选生成已实现、下一步直接做排序”。当前正式证明梯级为：

```text
provider capability truth
 -> route/locator live reachability
 -> capture/parser/date/relationship qualification
 -> required target-in-pool
 -> ranking/selection
 -> Evidence promotion
 -> downstream claim utilization
```

每层只可消费前一层的已证明结果：

1. `declared/configured` route 不能进入 live coverage 分母；`replay_proven` 不能冒充外网可达；`live_proven` 必须绑定 exact provider/version/as-of/capture。
2. target-in-pool 或 required-slot recall 未通过时，NDCG/MRR/reranker 状态是 `not_admitted`，不得以 0 分或绿色 fixture 排名替代。
3. `typed_gap` 必须区分 `route_unavailable`、`locator_not_found`、`fetch_failed`、`parser_rejected`、`publication_date_unproven`、`relationship_direction_rejected`、`budget_exhausted_after_fair_opportunity`、`commercial_gap`。slot starvation 或未尝试 route 不得写为 source exhaustion。
4. S1-08 产品关闭必须同时证明 DELL/MU/NVDA 三案 current required-slot candidate ceiling、来源多样性或明确例外、reconciliation、false promotion=0、selected coverage 和 canonical-source accounting。只有一个 issuer filing 的诚实 terminal 仍是失败，不是 bounded pass。
5. broad external search 如果仍无运营 Provider，必须由产品 owner 选择接入 Provider、启用受控动态/商业 fallback 或缩小 Internal Alpha source claim；TECH_02 不通过放宽 Evidence Gate 或增加盲目 retry 代替该决策。

更新后的执行顺序为：v3 clean independent zero-call proof；另行决定至多一次 DELL fresh-live；若 DELL ceiling 仍失败则停止并进入 provider/product-scope decision；DELL 通过后先关闭共享 RC-P36-156 typed blocker/run-scope 缺陷，再做 MU/NVDA transfer；三案候选池通过后才准入 ranking。RC-P36-156 属于共享 S0/S5 治理；在它关闭前，只有 exact runner/admission/source SHA 直接绑定的一次 DELL bounded successor 可被另行评估。本节不签发任何 live、model、ranking 或 S3 权限。

### 20.6 v3 clean independent proof 结果与下一权限边界（2026-08-08）

`S1_08_V3_MATURE_COMPONENT_RELATIONSHIP_BUDGET_CLEAN_INDEPENDENT_ZERO_CALL_PROOF` 已在 clean/synced commit `a3f15fa29f53a6e4537a04a96b9481d7a314b8ee` 通过。两个 Git archive、两个 disposable root 与两个 fresh Python process 分别执行完整 60 项 S1-08 合同；每边均无失败或 skip，normalized worker output 完全一致。复证显式绑定：

- `feedparser 6.0.12 / Trafilatura 2.1.0 / lxml 6.1.1`；
- R1 restricted request objects `19/19` 与 R2 Microsoft captures `2/2`，仅按 digest 只读注入，不输出 raw body/header；
- 两份 R2 页面都裁决为 `2026-07-29`，`2026-06-30` 报告期不得成为发布日期；
- DELL/MU/NVDA round-robin fake、关系/日期 mutation、nested-customer fetch 前拒绝和 document-fetch ceiling；
- network/model/provider/retry/admission/live=`0/0/0/0/0/0`。

第一次 A1 复证在 commit `2cdb09ce7fd62e01ae2994248298ad1347eec690` 以 `59 passed / 1 failed` 终止，因为 proof runner 只注入两份 R2 content objects，漏掉完整合同仍要求的 19 份 R1 request objects。该失败归 proof-input assembly；修复只扩充只读输入装配，没有修改 SourceHunter Runtime，也没有覆盖或追认 A1。

因此当前只把 v3 deterministic engineering 从 `engineering_pass` 提升为 `independently_proven`。以下事项仍不成立：fresh official feed/sitemap/bounded-domain reachability、DELL required target-in-pool、ranking admission、Evidence promotion、MU/NVDA transfer、DeepSeek research、内容质量或 release。下一项仅为零调用的 `S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION`；它必须重新核对旧 R2 terminal、新 proof、预算、provider availability、exact-once successor 和停止规则。decision 通过也只能允许另行签发的一次 DELL successor，不能在 decision 内自动执行。

### 20.7 DELL R3 fresh-live authority 与 successor 边界（2026-08-08）

`S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION` 的结论为 `approved_successor_entrypoint_required_before_issuance`。这是条件性权限，不是 admission：R2 已 exact-once 消费，其 runner、schema、namespace、result path 与 v2 catalog 都是不可变历史；新 v3 proof 不能挂接到旧 R2 runner 上冒充 live 证明。

一次 DELL R3 值得被评估，因为 R2 首因是 operational candidate ceiling，而 v3 已独立复证针对性修复 date/relationship/scheduler/fetch/accounting，并新增两条 `replay_proven/live_unproven` 的 official feed/sitemap 与 bounded-domain route。一次 `<=16` network 的 successor 是区分“新路线真实可达”与“仍缺运营 Provider”所需的最小实验。`external_site_search` 继续 `not configured / not operational`，所以 R3 不得宣称 broad Web search。

R3 successor 必须在零调用阶段建立独立 admission/terminal contract、namespace/result path，并绑定 decision、immutable R2 result/evaluation、v3 clean proof、v3 catalog、implementation source SHA 与 clean/synced commit；shared ledger 必须在 DNS/网络前 reserve，所有 request/response/parse/rejection/partial/terminal 均 capture-first。旧 R2 entrypoint、v2 catalog 和已存在 result 禁止复用。

拟议 authority 保持 `1 fresh admission / 1 exact-live / 16 network / 2 fetch per attempt / 1 unique accept per attempt / 0 model-provider-retry / 30s per call / 300s overall / no R4`，slot reservation 固定为 `4/4/5/0+3`。live hard gates 继续包括 required network slot first opportunity、starvation=0、canonical duplicate fetch=0、relationship false promotion=0、target-in-pool=`1.0`、required-slot recall@8=`1.0`、currentness/diversity-or-typed-exception/reconciliation/selected coverage=`1.0`、false promotion=`0`、qualified unique-document yield `>=0.5` 和 partial terminalization=`1.0`。本 R3 仍不执行或准入 BGE/Milvus ranking。

如果 successor binding、clean proof、source SHA 或 runtime SEC contact 失败，则不得签发。若 R3 运行后 candidate ceiling 或 target-in-pool 仍失败，立即停止 live retry，进入 `S1-08-P3` provider acquisition/product source-scope 决策；不能追加 R4、扩大预算、放宽 Evidence Gate 或先调 reranker。本 authority decision 本身的 network/model/provider/retry/admission/live 均为 `0`；当前下一项只是 `S1_08_V3_DELL_R3_SUCCESSOR_ENTRYPOINT_ZERO_CALL_IMPLEMENTATION`。

### 20.8 R3 successor entrypoint 零调用实现（2026-08-08）

R3 使用独立 `s1_08_r3_successor.py` 与 CLI runner，不修改 R2 module/runner。原因不是拒绝复用，而是 R2 source SHA 已进入 clean preflight 和 immutable terminal lineage；修改历史文件会让旧 proof 无法重算。R3 只复用未被 attempt identity 固化的稳定底层：v3 candidate Runtime、capture-first official adapter、canonical object store 和 shared admission ledger。

R3 admission 同时绑定：authority decision raw-file SHA/canonical digest、immutable R2 result/evaluation SHA/digest、v3 independent proof SHA/digest、v3 catalog SHA/digest、proof 内完整 implementation-file map、未来 clean preflight digest、R3 Runtime/Runner SHA、clean commit 与 issuance window。上述 authority object/SHA 在 R3 内统一封装为 typed `R3AuthorityInputs`，issue/require/execute 不得各自重新拼装一套参数；preflight 仍必须逐项回写 canonical/file bindings。实际执行的 catalog 还必须同时通过磁盘 byte SHA 与解析后 canonical object 核验，只传一个看似合法的 SHA、修改后的 object 或漂移文件均不能签发或 reserve。

执行前的纯本地检查顺序固定为 source/binding → runtime contact → shared-ledger path → live-transport type → canonical terminal store；这些条件全部通过后才 reserve。reserve 之后任何 source/candidate 异常都进入 capture-first partial/terminal 路径并 finalize shared receipt。实现初稿将 non-live transport 校验放在 reserve 后，零调用测试发现 admission 可能被无意义消费，现已前移并以 `ledger absent` 回归锁定。

R3 candidate contract 必须等于 `fin_0_1_3.S1_08.current_source_catalog_relationship_budget_candidate_generation:v3`，不允许 runner 静默回落 v2。budget 为 `16` 次网络、每 attempt `2` 次 document fetch/`1` 份 unique accept、`4/4/5/0+3` reservation、30 秒单次/300 秒全案、0 model/provider/retry、no R4。terminal 记录 authority/proof/R2/catalog/source/preflight lineage，ranking 始终 false。

focused successor=`7 passed`、全部 S1-08 contract=`70 passed`、compileall pass；fake transport 仅验证 contract/exact-once/round-robin/terminalization，没有访问外网或证明搜索质量。当前状态为 `zero_call_engineering_pass / clean_commit_preflight_pending`。下一项只能在 commit/push 后执行 `S1_08_V3_DELL_R3_SUCCESSOR_CLEAN_ZERO_CALL_PREFLIGHT`；clean proof 未通过前不得签发或 live。

### 20.9 Clean-preflight commit lineage（2026-08-08）

P2C 在 proof 前发现，若把 `preflight.source_commit` 强制等于未来执行时 `HEAD`，则 proof artifact 自身的提交会推进 HEAD 并让 proof 自我失效。禁止在 proof 生成后手改 commit 字段追认未证明提交。

R3 因此区分 `proven_source_commit` 与 `execution_commit`：前者是 clean Git archive 实际证明的提交，并继续作为 admission/terminal 的 `implementation_commit`；后者可以包含 proof artifact、Project OS 投影和 durable docs，但必须是前者的 Git 后代。runner 同时要求两提交间 `src/`、`scripts/`、`configs/runtime/`、`pyproject.toml`、`requirements*.txt` 零漂移，且所有既有 Runtime/Runner/v3 implementation/authority SHA 继续重算。任何 Runtime tree 变化都需要新 proof，不得沿用旧 preflight。

clean-preflight runner 复用既有 v3 proof 的 archive、restricted R1/R2 capture 注入和 credential-scrubbed fresh-process 组件，只新增 R3-specific compile、完整 S1-08 suite、commit/tree mutation、exact-once 和 result-absence 验证。该修复本身仍为零调用，clean proof、formal admission 与 exact-live 均未完成。

clean A1 进一步证明不能用 `pytest tests/contract -k s1_08` 表示“只运行 S1-08”：pytest collection 先导入全目录，clean archive 因缺少 144 组无关历史 runtime resources 而在结果前失败。proof runner 现显式列出 10 个 S1-08 contract 文件；不得复制无关 runtime 资源、加 skip 或吞掉 collection error 来制造绿色 proof。A1 与诊断重放均保留为 proof-harness input-selection failure，未触发 formal admission 或外部调用。

P2C-A2 随后在 clean/synced `d713eb6600150678618259dce9c00c052d018f52` 的 Git archive 与 fresh Python process 中通过：10 个显式文件=`70 passed / 0 failed / 0 skipped`，R1 request objects=`19`、R2 content objects=`2` 且 before/after digest 不变；compile、authority/source mutation、ancestry/Runtime-tree drift、exact-once 与 R3-result-absent 全部通过。formal admission/network/model/provider/retry/live=`0/0/0/0/0/0`。

因此 clean proof 已成立，但签发权限没有自动成立。下一边界是独立零调用 `S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AUTHORITY_PROJECTION_DECISION`；它只投影下一步权限，不能在同一任务中 issuance 或 live。任何 Runtime tree 漂移都使本 proof 失效并要求重新证明。

### 20.10 中段收口：Shared Governance 前置与最后一次 Candidate-Ceiling Live（2026-08-08）

P2C 已在 clean/synced `d713eb6600150678618259dce9c00c052d018f52` 完成 `70 passed / 0 failed / 0 skipped`，因此 v3 的 parser/date、relationship、slot fairness、fetch ceiling、canonical accounting、successor exact-once 和 lineage 不再需要新的 SourceHunter 零调用修补。剩余未知量只有 fresh operational route 能否把 evaluator target 送进候选池。

但 RC-P36-156 已证明 shared Project OS 对未知 state/scope 会 fail-open，且此前每个 successor 都依赖 append-only wildcard allowlist。该缺陷现在位于下一次真实 live 的权限路径上，所以执行顺序更正为：

1. 先由 TECH_06 的最小 `013-S0-04G` 实现 typed blocker state、versioned `RunScopeRegistry` 和 unknown state/scope fail-closed；
2. 再执行零调用 P2D，确认 P2C proof、Runtime tree、运行时联系身份仅 presence、16-call budget 与 no-R4 stop rule；
3. P2D 通过后，才可在独立 Attempt 中签发并执行一次 DELL R3；不得在同一决策任务中 issuance/live；
4. R3 通过 candidate ceiling 后，MU/NVDA 复用同一 provider/slot/capture/evaluator contract，只换公司身份与 source catalog，不再复制 DELL 的多轮 authority ladder；
5. R3 若再次 target-in-pool 失败，SourceHunter 阶段立即停止，不创建 R4。下一项只能在运营 broad/official-domain Provider、动态页 fallback、licensed source 或缩小 Internal Alpha source claim 之间做产品决策。

R3 的评价仍只到 SQ0–SQ2 与 promotion safety，不运行 DeepSeek，不计算 ranking 通过，不输出研报。`typed_gap` 也不能用来替代未运营 Provider 或未尝试 route。该边界减少的是重复 proof，不是降低 recall/currentness/diversity/false-promotion 标准。

### 20.11 DELL R3 自然拓扑失败、缓存污染与 proof 盲区（2026-08-08）

本节以 live 证据修正 20.10 的过早判断。20.10 所称“parser/date、relationship、slot fairness、fetch ceiling 等不再需要新的 SourceHunter 零调用修补”只对当时冻结的 deterministic fixture 成立，不能继续解释为自然运行时的 scheduler/document-fetch 不变量已经证明。

唯一 DELL R3 在 clean/synced `a5b5038c8835a1c56e5c4d3f2d3ca98b0e624e85` exact-once 完成：`15 network / 0 model-provider-retry / 13 query attempts / 0 accepted / 0 selected / 5 typed gaps`。terminal、capture、shared ledger、digest 与 secret 边界通过，slot starvation=`0`；但 adapter 记录 `229` 条 `locator_quality_pass` 后，document request capture 仍为 `0`。因此 qualified-document yield=`0.0<0.5`，target-in-pool、required-slot recall、selected coverage 和 ranking admission 全部失败。

代码路径显示两个项目内缺陷：

1. `candidate_generation_runtime` 为一次 slot attempt 编译一个 `network_call_allowance`，`OfficialDiscoveryAdapter.prepare_attempt()` 把它作为共享计数器。随后 `_discover_landing()`、`_discover_structured_endpoint()` 和 `_fetch_and_parse()` 都通过同一 `_fetch()` 消费该计数。多 landing／robots／sitemap／feed route 可以在 locator 已经合格后耗完 allowance，使合同中的 `maximum_document_fetches=2` 只有 ceiling、没有受保护的执行机会。
2. `_fetch_and_parse()` 对任何 `response is None` 都写入实例级 `_document_cache`。`slot_attempt_network_reservation_exhausted` 是本 attempt 的本地调度结果，不是远端文档事实；把它跨 attempt 缓存后，后续 regulatory/customer/supply slot 即使获得新 allowance，也会直接复用失败 tuple，不再执行 document request。

此前 proof 未发现该问题，是因为 fake 与真实 adapter 的调用拓扑不同：round-robin fake 每次网络计数后直接返回 candidate；document-ceiling fixture 使用单 landing route 和足够 allowance。它们证明了结果排序、总预算和表面公平，却没有证明 `discovery -> qualified locator -> document fetch` 的自然序列，也没有 mutation “attempt A 的本地 budget stop 不得污染 attempt B”。以后不得用这类一跳 fake 单独声称自然 fetch ceiling 已证明。

P3 若选择修复，候选合同至少必须同时覆盖以下不变量，但本节不构成实施授权：

- discovery budget 与 protected document-fetch reservation 分账；当某 slot 已产生合格 locator 时，仍须在总预算内保留至少一次正文抓取机会，或以明确的 `document_fetch_not_attempted_due_global_ceiling` 失败，不能把它写成 source exhaustion；
- `slot_attempt_network_reservation_exhausted`、local timeout-before-request、cancel-before-request 等本地停止不得进入跨 attempt document cache；只有绑定 request/response capture 的远端结果或具有明确生命周期的 canonical parse result 才可复用；
- cache key／receipt 必须区分 canonical document identity、attempt-local stop、remote transport failure 和 parser result，且任何 cache hit 都保留 originating attempt/capture lineage；
- 使用 R3 immutable captures 增加多 route、qualified-locator 后正文抓取、cross-slot negative-cache poisoning、allowance permutation 与总预算 mutation；fixture 必须走真实 adapter 拓扑，不能由直接返回 candidate 的 fake 代替；
- 运营 route 缺口仍单列：Dell/Micron IR landing failure、`external_site_search` unavailable 和 current market snapshot absent 不能因修复 scheduler/cache 自动视为解决。

R3 没有调用 DeepSeek，也没有进入 ranking，因此本失败不能进入 model capability ledger 或 reranker 质量归因。R3 immutable、no-R4 已生效；唯一下一 scope 为零调用 `S1_08_P3_POST_R3_OWNED_SCHEDULER_CACHE_AND_PROVIDER_PRODUCT_SCOPE_DISPOSITION_DECISION`。P3 必须同时比较 bounded owned repair、运营 Provider／动态页／licensed source 与产品 source claim；任何新 live 都需要另行改变 stop-rule 或产品范围，不能由本技术文档自动授权。

### 20.12 P3 repair-first 决策与 v4 protected-fetch/cache 合同（2026-08-08）

P3 选择先修项目自有不变量，再决定 Provider 与产品来源范围。理由不是默认公开源足够，而是当前零正文路径会污染所有外部能力判断：新 Provider 的 locator 仍会进入相同 scheduler/cache；此时采购、接入或缩减 source claim 都不能证明真实 residual ceiling。

唯一获准 scope 为 `S1_08_P3A_PROTECTED_DOCUMENT_FETCH_BUDGET_AND_ATTEMPT_LOCAL_CACHE_ZERO_CALL_IMPLEMENTATION_AND_PROOF`。它必须以 successor candidate execution policy v4 表达，不得改写 v3 或 R3：

1. 全局网络 ceiling 仍为 `16`。discovery/index 与 document fetch 可使用不同相位／保留语义，但每个真实请求都计入同一全局账本；
2. locator 通过质量门且全局仍有容量时，scheduler 必须给正文抓取一个受保护机会；若全局确已耗尽，必须记录 `document_fetch_not_attempted_due_global_ceiling`，不能伪装成 source exhaustion；
3. cancel-before-request、attempt reservation stop、local timeout-before-request 或 global stop 不进入跨 attempt document cache；它们只能是 attempt-local control receipt；
4. cache/receipt 明确区分 captured remote success、captured remote transport failure、canonical parser result 和 attempt-local stop；cache hit 必须携带 originating attempt 与 capture lineage；
5. proof 使用 R3 immutable request/response topology 驱动真实 adapter 路径，覆盖 landing→feed/sitemap/structured route→document、locator/allowance permutation 和 cross-slot negative-cache poisoning；一跳 fake 只能作为辅助，不能承担自然拓扑证明；
6. DELL/MU/NVDA full-fake 与 identity/currentness/relationship/numeric/lineage mutation 同包通过；R3 artifacts 必须 byte-stable；
7. P3A 的 network/model/provider/admission/live 均为 `0`，不得在实现包内购买 Provider、放宽门禁、增加预算或执行 replacement live。

若固定 16 次上限内不能证明 protected fetch 与 attempt-local cache 两个不变量，P3A 立即停止并回到 Provider／Internal Alpha source-claim 决策。若 P3A 通过，也只建立 deterministic engineering proof；另一个 owner decision 必须复核 residual operational gaps、产品来源承诺和是否明确修改 no-R4，才能命名、签发或执行任何新 DELL Attempt。

### 20.13 P3A A2 结果与 SearXNG diagnostic provider 合同（2026-08-08）

P3A 的 runner-only A2 已在 clean/synced `5e9726c2537386d2bc06a843ec43bfc5bf5d72fd` 上通过：两个 Git archive、两个 fresh process 各 `92 passed / 0 failed / 0 skipped`；R1/R2/R3 restricted objects=`19/2/39`，输入前后 byte-stable，外部调用为 0。A1 的 `90/1/1` 继续作为输入装配失败保留。该结果关闭 protected-fetch/cache 的 deterministic proof，不证明运营搜索覆盖。

Owner 批准在 production Provider 决策前增加一条低成本开源诊断路线。SearXNG 是聚合外部搜索服务的 metasearch，不是 FIN 自有 Web index，也不是金融来源权威。它在本阶段必须遵守以下合同：

1. provider lifecycle 固定为 `declared -> configured -> operational -> diagnostic_replay_proven -> diagnostic_live_measured`；禁止投影为 `production_live_proven`；
2. adapter 只接受预注册 query、language/time range/category、结果上限和调用预算；只调用固定 base origin 的 `/search?format=json`；
3. 原始 request、response、HTTP status、content type、engine participation 与 unresponsive engine 先 capture，再解析；403 JSON-disabled、429、timeout、invalid JSON、schema drift 与 body ceiling 都形成 typed terminal/partial result；
4. 规范化输出仅包含 canonical locator、title、snippet、可选 published date、engine list、rank/score candidate 和 capture lineage；SearXNG 的 score/date/snippet 均没有金融权威；
5. canonical duplicate 合并时保留全部 engine/rank lineage；不得因为多 engine 命中而把一份 URL 计成多份来源；
6. 所有 locator 初始 `promotion_status=diagnostic_locator_only`、`evidence_promotion_allowed=false`、`numeric_authority=none`。FIN 必须另行抓取原始来源并重新执行 entity/date/relationship/content/Evidence Gate；
7. 零调用 full-fake 必须覆盖成功、空结果、重复、cross-case/query mutation、403/429、timeout、invalid JSON、oversize、redirect/origin drift 和 engine failure；
8. 本地部署使用官方容器入口并固定 loopback exposure；Docker daemon 未运行时只允许报告 `deployment_not_operational`，不得改用任意公共实例冒充自建基线；
9. 未来付费 broad-search API 必须消费同一 query set、normalization schema、预算和 evaluator-only target，才能比较 locator recall、required-slot coverage、currentness metadata、duplicate rate、latency、错误率与成本。

首个本地部署又补充了一个必须长期保留的控制面边界：FIN 可精确限制的是 `FIN adapter -> SearXNG` query call；SearXNG 随后对多个 engine 的 HTTP fan-out 不是 adapter 能逐请求 exact-once 的表面。因此 diagnostic profile 固定 `bing/brave/duckduckgo/google` 四个 engine，保存 engine participation/unresponsive lineage，并明确 `upstream request count exactly known=false`。容器 healthcheck 只能访问本地首页，禁止调用 `/search`；首个错误 healthcheck 至少生成 6 次 `health` 搜索，已作为失败 Attempt 保留且不计正式 baseline。默认 engine set 也不得直接使用，避免启动期 engine init 网络请求漂移。

adapter v1.1 已在 clean `56e39f84` 上完成 `15 passed`、三案 full-fake、`9 captures / 0 network / 0 model / 0 promotion`，并证明非搜索式 healthcheck 合同。当前可单独签发 `S1_08_DIAGNOSTIC_BROAD_SEARCH_SEARXNG_BOUNDED_NETWORK_BASELINE`，最多 3 个 FIN query、0 retry；它仍不是 DELL R4、product-live、ranking 或 Evidence promotion。

### 20.14 SearXNG 有界 baseline 结果与 Provider capability compiler（2026-08-08）

唯一 baseline 已在 clean/synced `a5014c75e3ce9920cd83239d689aa262e04ee654` 上消费 admission。DELL/MU/NVDA 各一条预注册 query，FIN→SearXNG=`3`、adapter network=`3`、raw/normalized locator=`30/30`、canonical duplicate=`0`、capture=`9`、model/retry/document fetch/Evidence promotion=`0/0/0/0`，三案业务终态均已原子物化。结果与 runtime 副本 byte-identical，SHA-256=`cc42278862241ee65eabbf121bbc387d8837c8464ba32ad45023e26efcf912bf`。

运行结束后的可选控制台打印因 Windows GBK 无法编码 `U+2011` 返回进程码 1；该故障发生在两个 UTF-8 result 已原子写入之后。admission 已消费且没有重跑。修复只将控制台 JSON 改为 ASCII escape，未改变运行结果，并使当前 runner SHA 与已消费 authority 不再相等，从结构上阻止误复用。

质量评估为 `diagnostic_execution_pass_multi_engine_and_currentness_quality_fail`：

- 30 条 locator 全部来自 DuckDuckGo，Brave 三案均以 429／too-many-requests unresponsive；
- 运行实例实际只暴露 Bing、DuckDuckGo、Brave；镜像默认 Google 为 inactive；
- 实际 category 为 `general/web`，而请求含 `general/news`；SearXNG 记录 invalid category；
- 三案统一使用 `time_range=year`，但 Bing 声明不支持 time range，因而没有贡献结果；
- `published_on_candidate` 为 `0/30`；DELL/MU 有少量 issuer/Reuters locator，NVDA 前十没有 issuer/Reuters；所有 locator 仍不可引用、不可晋升。

这次失败拆成两类。项目内责任是 query compiler 没有在调用前读取 Provider operational capability，却把同一 category/time-range/engine 参数强加给不同上游；外部边界是免费 engine 的限流、inactive 状态和日期元数据缺失。前者必须进入 provider-neutral Runtime 修复，后者不能靠继续逐网址或扩大调用次数解决。

后续接口冻结为“语义同源、传输按能力编译”：

1. canonical `SearchIntent` 固定 case、as-of、Evidence Slot、query text、期望 currentness、domain/source preference、结果与成本预算；
2. 每个 `ProviderCapabilityProfile` 声明支持的 category、time range、domain filter、language、pagination、published date、engine visibility、rate/cost 和响应字段；
3. `ProviderQueryCompiler` 只生成被 profile 支持的参数。不支持的必要条件在调用前 typed fail；可选条件只能形成有记录的 degradation，不得静默删除；
4. evaluator 比较相同语义意图、候选 normalization 和 Gold-blind target，不要求 SearXNG 与商业 API 的 query string 字节相同；
5. healthcheck、FIN→Provider business call 和 Provider 内部 fan-out 分别记账；不能用 healthcheck 产生业务搜索，也不能把不可观测 fan-out 宣称 exact-count；
6. 候选付费 API 先完成离线 schema/fixture/secret-safe profile，再执行同三案有界 comparator；任何 Provider 在稳定性、日期、来源多样性、required-slot coverage、错误率、延迟和成本通过前都不是 production capability。

因此当前停止条件是：不重跑 SearXNG，不为免费 engine 继续加 URL 特例，不解锁 R4/ranking/S3。下一项等待候选付费 broad-search API 的 standalone HTTPS 调用、认证、JSON schema、过滤/分页、限流与价格资料；收到后先做零调用 input qualification，再决定是否发出新的 comparator authority。

### 20.15 腾讯云 WSA 候选 Provider 输入资格与单调用边界（2026-08-08）

用户提供腾讯云 AK/SK 后，项目没有直接把“元宝搜索”接入 SourceHunter，而是先对腾讯云官方文档与 SDK 做 provider-specific capability compile。冻结结果为 `SearchPro / 2025-05-08 / wsa.tencentcloudapi.com / HTTPS / API3 AK-SK`；必填仅 `Query`，`Mode/Site/FromTime/ToTime/Cnt/Industry/Freshness/Deeplinks` 为可选且部分依赖套餐。响应的 `Pages` 是 JSON 字符串数组，另有 `Query/Version/Msg/RequestId`。首个诊断禁止发送 `Cnt/Industry/Freshness/Deeplinks`，避免在未知套餐上把 tier incompatibility 误判成搜索质量。

候选 Provider profile 固定：

1. provider lifecycle 只到 `candidate_documented -> secret_safe_zero_call_proven -> single_call_diagnostic_measured`，不能自动进入 production；
2. 一个固定 DELL semantic query、`Mode=0`、一次 provider/network、0 retry/model/document/Evidence；
3. safe request 在 transport 前保存，但不得含 SecretId、SecretKey、Authorization 或签名；raw response/error 在 parse 前保存到 `.codex_runtime`，所有错误文本再次按实际 credential value 脱敏；
4. normalizer 只输出 canonical URL、title、raw date、passage、site、score、rank、domain 与 request lineage；所有项固定 `candidate_locator_diagnostic_only / evidence_promotion_allowed=false / numeric_authority=none`；
5. 成功只证明鉴权、服务可用、live schema 与一条 query 的 locator/date telemetry；失败只形成 typed terminal。两者都不能自动签发三案 comparator、接入 SourceHunter 或改变 no-R4；
6. 轻量／标准／尊享／旗舰文档按量价为 18／46／60／80 CNY/千次，因此本轮最高文档成本上限为 0.08 CNY；
7. 通用 AK/SK 已在聊天明文出现，诊断后必须轮换；生产候选应改用最小权限子账号或服务 API Key。

零调用实现首次发现 runner helper 引用与 wildcard S0 self-check 两个 pre-transport 缺陷；修复后 Project OS、authority/profile/runner binding、normalization、redaction 与 mutation=`19 passed`，真实 API 调用仍为 0。当前只消费已签发的 `S1_08_PAID_BROAD_SEARCH_TENCENT_WSA_SINGLE_CALL_DIAGNOSTIC`；不能在同一 authority 内追加 MU/NVDA 或 retry。

R1 随后在 clean/synced `0b4d2eb842100a545592c5c2457a54fd3b012a48` exact-once 消费：`1 provider/network / 0 retry/model/document/Evidence / 276 ms`，腾讯返回 `InvalidParameter / illegal Mode` 和 RequestId，未返回 Pages。离线 SDK 证明 request wire projection 确实含显式 integer `Mode=0`；官方 SearchPro 与服务 API Key 文档却均把 0 定义为 natural/default。因此本失败同时建立 external documentation/live drift 和 project compiler 显式 optional-default 缺陷，不能归因 DELL query、DeepSeek、RAG、reranker 或搜索质量。请求已越过通用签名错误表面并到达业务参数校验，但 service resource availability 仍未证明。

R1 不重试。任何 replacement 必须使用新 authority／Attempt，request body 只含 `Query`，并在轮换已暴露 AK/SK 后由 Owner 决定；仍只允许 1 call、0 retry。成功返回 Pages 前，provider quality、三案 comparator 和生产接入均无资格。

Owner 随后创建子账号 API Key 并批准该 replacement。实现没有改写 R1 runner，而是新增独立 successor：`compile_query_only_request()` 只接受 `request_body_fields=[Query] / optional_fields=[]`，并对 `Mode/Site/FromTime/ToTime/Cnt/Industry/Freshness/Deeplinks` 的任何 surface mutation fail closed；safe request、terminal 与 SDK request 共用同一编译对象。新 authority 绑定 immutable R1 result/assessment、provider profile、normalizer、support、runner 和 zero-call proof。scoped Project OS preflight=`pass`、targeted=`15 passed`、外部调用=`0`。该状态只表示 `issued_unconsumed`；必须先 clean commit，再以隐藏输入消费一次，结果不论成功失败都停止。

R2 随后在 clean `ff25e92fbf5d0813ea4ab6f0dde1def73e881c8b` exact-once 消费：safe capture 与 SDK request 均为唯一 `Query` 字段，腾讯以 `AuthFailure.SignatureFailure` 在 129 ms 拒绝，并返回 RequestId；provider/network=`1/1`，retry/model/document/Evidence=`0/0/0/0`。这证明 optional-default compiler 已不再是当前失败面，但没有证明 CAM、服务开通或 SearchPro 质量。successor 与 R1 使用相同官方 SDK `3.1.152`、endpoint、TC3 sign method、empty region 和 client profile，而 R1 使用前一组凭据曾到达业务参数校验，因此当前不把 R2 归为项目签名算法回归；优先怀疑截图中 case-sensitive credential 的转录歧义或无效／不匹配凭据对，但两者均未被第二次请求证明。

这里还必须区分两类密钥：截图是腾讯云标准 `SecretId/SecretKey`，走 `wsa.tencentcloudapi.com` 和 TC3；WSA 产品控制台还可签发独立 service API Key，走 `api.wsa.cloud.tencent.com/SearchPro` 与 `Authorization: Bearer ...`。二者不能混用，切换也不是 fallback，必须建立独立 ProviderCapabilityProfile、secret-safe transport、fixture 和 authority。R2 后 no-third-attempt 生效，先删除已暴露 Key，再由 Owner 选择认证路线。

Owner 随后以直接文本提供另一组 standard AK/SK 并明确批准一次新诊断，因此新增 R3 而不改写或重用 R2。R3 继续复用已证明的 Query-only compiler、official SDK/TC3 transport 与 safe normalizer，同时以新 schema/Attempt/result namespace 绑定 immutable R2 terminal。凭据仅在 TTY hidden input 进入进程，authority、capture、terminal 和 Git 均不得包含值；预算固定 `1 provider/network / 0 retry/model/document/Evidence`。零调用 focused=`21 passed`。R3 即使成功也只产生 non-promotable locator/date telemetry；任何终态都停止，R4、三案 comparator、SourceHunter integration 与 production promotion 必须另行决策。

R3 在 clean `b9dfa025` 成功返回 `Version=lite`、10 个 unique locator 和 10 个 date field，证明 exact-text standard AK/SK、TC3、WSA service、Query-only schema 与 normalizer 均可用。但内容层 8 条为 Dell driver/support/firmware/navigation，2 条为无关第三方排障，冻结 query 的 AI server demand/customer/supply-chain/earnings/industry intent useful count=`0`。因此 provider date 也不能获得金融日期权威。此结果把“transport 可用”和“研究检索可用”明确拆开：前者 pass，后者 fail。单 query 不能否定腾讯所有 tier，但足以禁止当前 lite path 直接接入 SourceHunter；中文 query、query rewrite、高阶 tier 或 Bearer service API Key 都必须作为新 provider/cost/eval 决策，而不是自动 retry/fallback。

Owner 随后将 subscription 切换 standard 并批准 R4。实验合同采用 same-query control：credential path、DELL query bytes、Query-only wire shape、endpoint、SDK、normalizer、result ceiling 全部冻结，唯一预期变量为 `Provider Version=standard`。R4 仍为 1 call/0 retry/no reranker/no document fetch；评估直接比较 useful@10、target-in-pool、date semantics、domain diversity、cost 和 latency。若仍失败，下一步不是继续单 query R5，而是先建立三案中英 query × Evidence Slot comparator；该设计必须先零调用 proof，live 与 integration 另行 gate。

### 20.16 Standard-tier R4 与 Gold-blind bilingual Evidence-Slot comparator（2026-08-08）

R4 在 clean `2e6fbf9f...7c17` 返回 standard 和 10 条 DELL AI-server 相关 locator，证明套餐层确实改变 topical recall；但 10 条均属于 `qq.com` 同一内容生态，冻结 DELL primary target 和 hidden target group 仍为 0，Provider date 没有一手校验。因此 Runtime 将 `topical useful@10` 与 `Evidence-eligible useful@10` 分开，前者 `10/10`、后者 `0/10`；不能把语义相关误写为金融证据可用。

后续 comparator 固定 24 个 Query-only 调用：DELL/MU/NVDA × issuer results、regulatory reconciliation、customer validation、supply-chain counterevidence × EN/ZH；market context 继续由本地 governed snapshot 提供。query plan 与 evaluator-only target manifest 物理分离，Gold 只在所有 Provider 调用 terminalize 后加载。每 query 先保存 safe request，再保存完整 raw response／typed failure，0 retry、0 document fetch、0 Evidence promotion。除 useful@10 外，还计算 case-slot 中英 union target-in-pool、带 local control 的 12-group recall、exact-target date accuracy、registrable-domain/publisher concentration、cost 与 p50/p95。只有全部预注册门通过才有资格进入独立 adapter integration decision；candidate gate 不通过时 NDCG/MRR/reranker 继续 `not_admitted`。

### 20.17 Bilingual comparator live 终态与 Provider admission 结论（2026-08-08）

唯一 comparator 在 clean `19943317...e2dc` exact-once 完成：24/24 Query-only 调用返回 standard，0 retry/model/document/Evidence；155 个 locator，文档价 1.104 元，p50/p95/max=`754/941/1052 ms`。传输、终态物化、成本和延迟均合格。

候选质量未合格：topical useful=`110/240`，Evidence-eligible=`0/240`；12 个 case-slot 的 EN/ZH union target-in-pool=`0/12`，带本地 market control 的 12 个 hidden target group recall=`0/12`。中文 case mean topical useful@10 为 DELL/MU/NVDA=`0.525/0.625/0.550`，英文为 `0.375/0.350/0.325`；语言改写改善泛相关召回，却没有召回冻结的一手目标。regulatory slot 是最明显缺口。155/155 locator 带 Provider date，但由于 exact target 命中为 0，matched-target date accuracy 没有样本，必须按硬门失败而非按 100% 日期准确处理。

每案例 registrable domain=`15/20/15`、最大单域占比=`0.372549/0.490566/0.558140`，说明表面域名分散不等于一手 target coverage。官方域结果也必须匹配 case、slot、期间和文档身份后才能晋升，不能只凭 issuer domain 通过 Evidence Gate。

终态固定为 `fail_diagnostic_only / remain_diagnostic_only_no_reranker_rescue`。Tencent adapter 不进入 SourceHunter，BGE/NDCG/MRR 继续 not admitted；不得追加 R5、逐 query patch、正文抓取或 reranker rescue。下一候选 broad-search Provider 必须复用同一 gold-blind comparator；全部 candidate/date/diversity/cost/latency 门通过后仍需独立 integration authority。若不引入其他 Provider，则产品层必须显式缩减 Internal Alpha source claim，而不是在 Runtime 中伪造覆盖。

### 20.18 Provider 市场扫描、Firecrawl keyless 试跑与双检索路线（2026-08-08）

对 Brave、Tavily、Exa、Valyu、You.com、Parallel、Linkup、DataForSEO、Serper、Perplexity Search、Kagi、Firecrawl 以及 SearXNG/DDGS/Crawl4AI/Jina 的官方能力做横向审查后，TECH_02 不再把“broad Web search”视为单一同质能力。至少要区分：

1. `precise_serp_or_official_domain`：已知证据 owner、官方域或 filing 身份时，以 official-domain、SEC/IR、Serper/DataForSEO 类 raw SERP 找到精确 locator；
2. `semantic_open_web_discovery`：事前不知道 URL 时，以 Exa、Brave、Perplexity Search、You Search、Firecrawl broad search 等发现行业、机制和反证材料；
3. `document_fetch_and_extract`：Crawl4AI、Trafilatura、Playwright、Firecrawl scrape 只消费已存在 locator，不得冒充 broad index；
4. `synthesized_finance_research`：Finance/deep-research API 只能作为 benchmark、source suggestion 或 supervisor supplement，不得绕过 FIN 的 Evidence Gate、研究轨迹和内容质量评价。

Firecrawl keyless 形成三组有效 capture-first diagnostic：issuer/regulatory A2=`6/6 terminal, exact target 3/6, 12 credits`；三个 miss 的 official-domain A3=`3/3 exact target, 6 credits`；customer/supply A4=`6/6 terminal, exact target 0/6, 12 credits`。A2 provider date field 为 0，再次证明 search response date 只能做候选 telemetry。任何 provider date 都必须在 document capture 后交 typed date adjudicator；不得因搜索结果显示日期就获得 financial publication-date authority。

最初 A1 批量探索在 response 返回后因 Windows console encoding 失败，且未先原子保存 raw response，因此整组 `invalid_not_counted`。这个失败不归 Firecrawl，也不能凭 stdout 记忆重建；它验证 capture-first 必须早于 console/display。

当前选择顺序为：先以 Firecrawl keyless 作为无需新凭据的 baseline；关系查询修复后执行一份完整 comparator；若需要第二家 Provider，Exa 优先补 semantic discovery，Serper/DataForSEO 随后提供 raw SERP control，Brave 用于独立索引多样性。该顺序只是采购/试验路线，不等于任何 adapter 已获 production admission。

### 20.19 Relationship-aware SearchIntent 与 typed source-equivalence 缺口（2026-08-08）

A4 的 0/6 不能只归因 Provider。当前 `compile_initial_queries()` 已从 `EvidenceSlot.entity_roles` 计算 `entity_keys`，但 provider-visible `query_text` 仍只由 `case_key + research_objective + generic role query_terms` 组成。结果是本地过滤器知道 customer/supplier evidence owner 可能是 Microsoft、TSMC、Micron、Dell 或 NVIDIA，外部搜索却只看见 subject company 和通用的 customer/supply 词。正式 bilingual plan 的 customer/supply query 也保留了相同弱点。

下一版本合同必须新增 `SearchIntent`：

```text
SearchIntent =
  subject_entity
  + evidence_owner_entity and aliases
  + relationship / claim direction
  + period and as-of
  + source family / form
  + language
  + route class
```

customer/supply slot 应按 evidence owner 做受预算约束的 fan-out；每条 query 只表达一个可归因关系，不把多个 counterpart 拼成一条长字符串。provider adapter 只负责编译能力字段与发送，不得重新解释经济关系。

Evaluator 同时拆分 `exact_locator_match` 与 `typed_source_equivalent_match`。后者只接受可审计身份：SEC accession、官方 canonical locator、已验证 redirect/canonical tag 或 byte/content identity。相同公司、相同季度、相同事件但内容不同的 press release、prepared remarks、transcript 和 filing 不自动等价。该规则用于减少 URL alias 假阴性，不能放宽 Gold target 或把近似资料伪装成目标资料。

当前下一项固定为 `S1_08_PROVIDER_NEUTRAL_RELATIONSHIP_AWARE_SEARCH_INTENT_COMPILER_AND_SOURCE_EQUIVALENCE_EVALUATOR_ZERO_CALL_IMPLEMENTATION`。它只修改 query/evaluator deterministic contract，并以三案 fake/mutation 验证；network/model/Provider/Evidence promotion 均为 0。通过后才可签发新的 Provider comparator；不得在修复前继续横测多家付费 Provider，也不得由 reranker 从 0 target candidate 中“救回”。本段的 implementation-pending 状态由 20.20 supersede。

### 20.20 Relationship-aware SearchIntent v1 零调用实现与国内 Provider 优先顺序（2026-08-08）

`fin_0_1_3.S1_08.relationship_aware_search_intent_and_source_equivalence:v1` 已以独立 successor 形式实现，没有修改历史 v1–v3 source catalog、Tencent 24-query plan 或已消费 Attempt。Runtime 从 v3 catalog 的 subject、entity role、alias、official landing、Evidence Slot 与 as-of，加上 case-scoped temporal profile，生成下列 closed object：

```text
SearchIntent =
  case + evidence_slot
  + subject_entity + subject_aliases
  + evidence_owner_entity + evidence_owner_aliases + owner_role
  + claim_direction
  + owner_period_terms + as_of
  + source_families
  + language
  + route_class + preferred_domains
  + research_objective_digest
  + provider_visible_query_text
```

customer/supply 不再把多个 owner 拼成一条 query。当前三案按 v3 role catalog 展开后，每案官方精确路线 12 条、语义开放网路线 8 条；合计 `36 precise_official_domain + 24 semantic_open_web = 60`。这不是擅自扩大调用预算：两个 lane 是两个独立的 query plan，当前 Provider/network authority 均为 0。旧 `3 case × 4 slot × 2 language=24` 只保留为 Tencent immutable historical contract；future comparator 若强行维持 24，就必然丢掉 counterpart fan-out，因此不得复用为 successor。

provider-visible query 不复制整段 research objective，也不泄漏 Gold URL、source ID 或 target ID。它只使用一个 owner、最多两个查询别名、owner reporting period、经济方向、slot 关键词、来源提示、subject research context 和 as-of。60 条 query 全部唯一，字符数 `76–268`，平均 `163.4`，上限 300。跨实体 query 使用 `evidence_owner_own_*` 方向，例如 Microsoft 只代表微软自身 capex/deployment disclosure，Dell 仅为 research context；不得据此推断微软是 Dell 客户或建立未经证据验证的商业边。

Source equivalence 与 query compiler 物理分离，只能在 raw capture/fetch 后运行。`exact_locator_match` 单列；`typed_source_equivalent_match` 只允许：

1. 相同 SEC accession；
2. capture 验证过的 canonical locator；
3. capture 验证过的 redirect final locator；
4. 双方已验证的内容 SHA-256 identity。

上述匹配还必须同时满足 case、evidence owner、source family、document kind、published date 与 authority。相同公司／季度／事件但 press release、prepared remarks、transcript、filing 不同，必须 `no_match`。Provider date 继续只是 telemetry，不能因为 source-equivalent 就自动取得金融日期权威。

三案 full-fake 使用 36 个 official reference，证明 `12 exact + 24 typed-equivalent + 0 no-match`；cross-case、wrong-direction、future date、alias collision、budget mismatch、permutation、unverified canonical、same-event different-document 与 wrong-owner mutation 均 fail closed。新增测试与既有 S1-08 全组为 `13 passed / 169 passed`，Project OS scoped preflight pass；network/provider/model/document/Evidence=`0/0/0/0/0`。

采购与运营便利现在正式进入 `ProviderCapabilityProfile`，但不渗入核心 SearchIntent：人民币结算、微信／支付宝／网银充值、发票、国内账号治理、凭据轮换、延迟和支持渠道可影响候选顺序，不能改变 Evidence Gate。下一项为 `S1_08_DOMESTIC_FIRST_PROVIDER_INPUT_QUALIFICATION_AND_RELATIONSHIP_AWARE_COMPARATOR_SCOPE_DECISION`：优先审查 Tencent SearchPro successor 与百度千帆独立 Web Search 的 raw locator/schema/过滤/成本能力；阿里百炼等 model-attached search 单列 synthesized/tool lane；火山引擎在拿到 standalone raw schema 前不计能力。Firecrawl 保留免费控制，Exa 只作可选国际 semantic benchmark。该决策不复用聊天暴露的旧 Key，也不自动授权 comparator live、SourceHunter integration、ranking 或 S3。

### 20.21 国内 Provider 输入资格与 wire projection 边界（2026-08-08）

官方合同复核确认 Tencent SearchPro 与百度千帆 `baidu_search_v2` 都能返回 raw locator candidate。Tencent `SearchPro/2025-05-08` 的请求字段包含 `Query/Site/FromTime/ToTime`，响应包含 `url/title/date/passage/site/score/RequestId/Version`；标准版公开价格为 46 元／千次，官方未披露 query 长度上限。百度 endpoint 为 `POST https://qianfan.baidubce.com/v2/ai_search/web_search`，支持网页 top-k 50、最多 100 个站点、明确日期范围和 recency，返回 `url/title/date/snippet/content/website/request_id`；每月 1,500 次免费，后付费目录价 0.036 元／次。

资格审查同时发现百度输入为硬边界：query 最多 72 个计量字符，中文按 2 计，超出后只取前 72。SearchIntent v1 的 60 条 canonical query 普通字符为 `76–268`，按该规则为 `122–268`，直接满足上限=`0/60`。不得让 Provider 静默截断，否则 evidence owner、period、claim direction 或 source family 可能丢失，之后的 target-in-pool 横评没有意义。

Runtime 因此新增但尚待实现的分层：

```text
SearchIntent(canonical, provider-neutral, complete)
 -> ProviderWireProjection(intent_ref + intent_digest + compact query + typed filters)
 -> provider request capture
 -> common CandidateBundle normalizer
 -> common hidden-target evaluator
```

`ProviderWireProjection` 只能做 transport compilation。百度 adapter 应将 preferred domain 与 date range 放入结构化字段，把 query 压缩至 72 weighted units，同时保留唯一 owner、期间、claim direction 和 source family；核心 SearchIntent 不因百度当前限制而缩短。Tencent 可接受 canonical 或同一 compact comparison query，但不得复用已在聊天暴露的 AK/SK。语义开放网 24-intent lane 在 transport 允许时保持逐字 query parity；官方精确 36-intent lane允许使用 provider-native site/date field，因为过滤能力本身是被测 capability，但 canonical intent 与 hidden target 不变。

阿里百炼 Web Search MCP 已与模型内置联网搜索分账：MCP endpoint 可作为返回 `pages` 的 search tool，前 2,000 次免费、之后 29 元／千次；只有 raw page locator 可以进入 comparator，千问联网检索 Agent 或 model-attached synthesized answer 不能按 useful@10 混评。Firecrawl 仍为无密钥控制，Exa 仅为可选国际 semantic benchmark。

零调用资格终态为 `pass_next_zero_call_wire_projection_required`。当前下一项固定为 `S1_08_DOMESTIC_PROVIDER_WIRE_PROJECTION_AND_FAIR_COMPARATOR_CONTRACT_ZERO_CALL_IMPLEMENTATION`；它不调用 Provider／模型／网络，不抓正文、不晋升 Evidence、不接 SourceHunter。proof 通过后仍需 provider-specific fresh credential、admission 与独立 36/24 live 选择，禁止把 60 intents 自动合并运行。

### 20.22 ProviderWireProjection v1 与 exact-payload execution unit（2026-08-08）

`fin_0_1_3.S1_08.domestic_provider_wire_projection_and_fair_comparator:v1` 已实现。每个 wire object 显式保存 canonical `intent_id/digest`、owner、claim direction、source families、route、compact query、structured filter mode、safe request body、payload digest、wire digest 与 `send_authorized=false`。核心 SearchIntent 未改，Provider profile 只拥有传输字段。

人工质量复核拒绝了第一版虽满足 72 units 但偏机器标签的短查询。正式 projector 使用实体／槽位相关主题：Microsoft=`Azure AI capex datacenter capacity`、Dell=`AI server backlog/demand`、Micron=`HBM revenue/capacity/outlook`、NVIDIA=`Blackwell datacenter/supply constraint`、TSMC=`CoWoS advanced packaging capacity`；issuer 与 regulatory 分别加 earnings 或 SEC filing。direction/source family 的完整枚举保留在 wire metadata，query 只放有召回价值的词。

四家均编译 60 个 logical wire object，query units=`37–66`，百度 `60/60` 通过明文 72-unit 上限；旧 canonical 长 query 仍为 `0/60` 直接兼容。24 条 semantic intent 在四家逐 intent query bytes 相同且不带 hidden domain/date filter。precise lane 使用公开原生字段：Tencent=`Site + FromTime/ToTime` 且不发送 `Mode/Cnt`；Baidu=`site[] + page_time range`；Firecrawl=`includeDomains` 且不 scrape；Alibaba MCP 仅保存 provisional `query/count`，完整 tool schema capture 前 admission 不合格。

进一步发现 36 个 precise intent 中存在三案共享的相同官方查询。Runtime 不再为凑 identity 数量重复发送，而按 `provider + route + exact request_payload_digest` 合并：

```text
60 canonical intent identities
 -> 36 precise wire identities + 24 semantic wire identities
 -> 22 precise execution units + 24 semantic execution units
 -> each capture lists 1..N consumer intent ids/digests
 -> per-consumer hidden-target evaluation and lineage
```

每家 combined ceiling 因此为 46 execution units，不是 60；仍不得自动执行两个 lane。合并只发生在 request bytes 完全相同且 route 相同的 precise payload，semantic 不跨案例合并。这样节约 14 次调用，同时保持每个案例的评估、typed gap 和 Evidence promotion 独立。

专项 `12 passed`、全部 S1-08 contract=`181 passed`。proof 中共有 `240 unique wire digests / 184 unique payload digests / 184 execution units`，Provider／network／model／document／Evidence 均为 0。当前下一项为 `S1_08_DOMESTIC_PROVIDER_CREDENTIAL_READINESS_AND_FIRECRAWL_CONTROL_COMPARATOR_AUTHORITY_DECISION`；它只能 secret-safe 判定国内凭据和选择一个 control lane，不授权 46-call combined live、SourceHunter、ranking 或 S3。

### 20.23 Firecrawl relationship-aware semantic control 终态

唯一 24-query control 在 clean `db427ee4` 完成 `24/24` Provider/network、0 retry/model/document/Evidence，返回 235 raw／176 global-unique locator。共同 evaluator 得到 topical useful=`133/240`、customer/supply case-slot target-in-pool=`5/6`；命中 Microsoft、Dell、TSMC 冻结一手来源，缺 DELL supply 的 Micron prepared remarks。该结果相对旧 generic A4 的 `0/6` 强力支持 owner/direction query compiler，但同时改变 query 数、语言和 evidence-owner fan-out，不能冒充单变量 A/B。

Firecrawl Provider 自身未通过：provider date=`0/235`，六个 exact target occurrence 均无日期，中文 exact target=0，四条 query useful@10<0.3，p95=`6877 ms`。因此 control 固定为 `fail_diagnostic_only`；不得 R2、逐 query patch、reranker rescue、precise lane 自动扩张或 SourceHunter integration。

### 20.24 Tencent relationship-aware same-matrix successor

新腾讯 AK/SK 只通过环境变量名称和 presence 进入资格判断，值不得打印、散列、写入 capture、terminal、Git 或工作日志。与历史腾讯 24-query comparator 不同，本 successor 首次消费 20.23 完全相同的 24 个 relationship-aware semantic intent/query text；旧腾讯结果保持 immutable。

零调用 successor 固定：

```text
immutable Firecrawl control plan (24 intent/query identities)
 -> recompile Tencent ProviderWireProjection
 -> assert 24/24 query-text parity
 -> Query-only SearchPro request
 -> safe request capture
 -> raw response or typed provider failure capture
 -> per-call terminal, systemic refusal stops later network attempts
 -> aggregate terminal for all 24 identities
 -> evaluator-only Gold load
 -> common useful@10/target/date/diversity/latency
 -> Tencent Version=standard and documented CNY cost gates
```

腾讯官方合同复核仍为 `SearchPro / 2025-05-08 / wsa.tencentcloudapi.com`；必填只有 `Query`，Pages 为 JSON 字符串数组并提供 title/date/url/passage/site/score，response 提供 Version/RequestId。标准版按量价 46 元／千次，因此 24-call ceiling 为 1.104 元。本 successor 不发送 Mode/Site/FromTime/ToTime/Cnt/Industry/Freshness/Deeplinks，不把 tier 参数差异混入 semantic recall 对照。

runner 只读 `TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY`。AuthFailure、UnauthorizedOperation、ResourceNotFound、ResourceUnavailable 或 RequestLimitExceeded 触发 systemic stop：当前 failure capture 后，其余 identity 以 no-network typed terminal 收口；禁止自动 retry。focused full-fake/mutation=`7 passed`，Provider/network/model/document/Evidence=0。当前下一项是 clean authority issuance；即使 live 所有 comparator 门通过，也只允许另行决定 SourceHunter adapter integration，不自动晋升 Evidence、ranking、Agentic Research 或 release。

### 20.25 Tencent same-matrix exact-live authority

clean/pushed implementation commit=`9a0040e1114f7f53943ed4a9889e99db949b9cd3`；S1-08 contract 回归=`199 passed`。唯一 admission=`fin-ia-013-s1-08-tencent-semantic-same-matrix-r1-20260808` 为 `issued_unconsumed`，绑定 runner/support/normalizer/Query-only compiler、24-query immutable control、scoring/proof/provider profile 与 Firecrawl terminal/assessment 的 SHA/digest。

authority 只允许 24 条 semantic Query-only 请求，provider/network=`<=24/<=24`，retry/model/document/Evidence=`0/0/0/0`。凭据仅由 runtime environment 注入；systemic refusal 后剩余 identity 不再联网。该 authority 不允许 precise/combined lane、ranking、SourceHunter 或生产晋升，且不允许任何 automatic retry/replacement attempt。

### 20.26 Tencent same-matrix live terminal 与 Provider 边界

唯一 live 在 clean `4545f453` 完成 24/24 standard 请求，0 retry/model/document/Evidence，成本 1.104 CNY，p95 1,330 ms。transport、entitlement、capture-first、terminalization、redaction 与成本/延迟控制均通过。

locator 质量没有通过：172 occurrence／126 unique URL、topical=`103/240`、case-slot frozen primary target=`0/6`；同矩阵 Firecrawl 为 `133/240`、`5/6`。腾讯 172/172 都返回 date，但 exact target=0，因此日期准确性没有可验证分母。主要 hostname 为腾讯聚合、GitHub、Sina 与 Toutiao；少量 official-domain result 是产品/support/technology 页面，不是要求的财报、业绩会或 IR release。

这证明 broad semantic locator 的低延迟和 metadata 完整不能替代 primary-source precision。Tencent 继续为 diagnostic-only；禁止在当前结果后增加 reranker/document fetch 以事后改变 Provider qualification，也禁止逐 query patch 或 replacement。下一项应零调用决定 SourceHunter 的 production portfolio：官方 precise adapter 负责一手来源，broad provider 只提供补充召回；若继续供应商评测，必须复用同一矩阵与 gate。
