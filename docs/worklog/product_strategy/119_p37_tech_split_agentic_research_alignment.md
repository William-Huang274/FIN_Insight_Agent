# 119 - P37 TECH split / Agentic Research alignment

记录时间：2026-07-09

## 用户要求

用户指出：TECH_01-10 初版拆分里没有明显体现向 `agentic search`、`agentic research` 和 ReAct 模式的转变。要求把已对齐内容补进技术文档，并把剩余 TECH_02-10 对 PRD 和之前记录文档重新扫描，漏掉的拆分补上，重新整理 `TECH_xx` 划分。

## 本轮判断

PRD 已经明确写入：

- `Agentic Research Operating System`；
- bounded ReAct / tool-use loop；
- Agentic Search / Agentic Research 与 RAG / KB 角色；
- Tool Registry / Evidence Tool Planner / Evidence Gate；
- Agentic Research Harness；
- ContextEngine / subagents-as-tools / trace / eval / self-improvement。

P37 初版 TECH 拆分把这些内容分散在 TECH_02、TECH_06、TECH_08 和 TECH_10，但 `TECH_01` 仍像普通 DecisionSurface schema 文档，缺少“从 one-shot node graph 转向 plan-act-observe-classify-repair-stop agentic research loop”的总控合同。因此本轮不新增 `TECH_11`，而是把 `TECH_01` 升级为 agentic research 主干，把 `TECH_02` 明确为 agentic search 主干。

## 完成内容

新增技术文档：

- `docs/architecture/agent_graph_vnext/TECH_00_agentic_research_technical_index.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_01_agentic_research_loop_decision_surface_contract.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_04_numeric_program_trace_parser_promotion.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_06_durable_harness_runtime_permission_state.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_10_trajectory_eval_self_improvement.zh-CN.md`

更新现有文档：

- `docs/architecture/agent_graph_vnext/37_agentic_research_harness_codebase_audit_and_technical_doc_split.zh-CN.md`
- `docs/worklog/product_strategy/118_p37_git_hygiene_codebase_audit_prd_alignment.md`
- `docs/worklog/README.md`

## 修订后的划分

1. `TECH_01`：Agentic Research Loop + DecisionSurface 主干；
2. `TECH_02`：Agentic Search + Evidence ToolGateway + SourceHunter；
3. `TECH_03`：DocumentMetadataIndex / RAG / KB 分层；
4. `TECH_04`：Parser / NumericProgramTrace / fact promotion；
5. `TECH_05`：Domain evidence operator / five-chain projection；
6. `TECH_06`：durable harness runtime / permission / HITL / checkpoint；
7. `TECH_07`：ContextEngine / skills / compaction governance；
8. `TECH_08`：Subagents-as-tools / handoff；
9. `TECH_09`：Trace / provenance / Workbench cell review / ArtifactConsistencyGraph；
10. `TECH_10`：Trajectory eval / self-improvement。

## 边界

- 本轮只做技术文档和拆分校准；
- 未实现 runtime 代码；
- 未运行 paid LLM；
- 未运行 true runtime full-chain；
- 未运行 MCP server；
- 未运行 source ingestion；
- 未运行 parser promotion；
- 未运行 Workbench replay；
- 不表示 P36 blocker 已关闭。

## 2026-07-09 追加：T0 / T1 增补

用户要求把 T0 / T1 的架构转型声明补得更明确，尤其是 stable object graph、owner coverage、capability maturity、source-of-truth，以及 T1 中 task-level loop / cell-level loop、DecisionSurfaceCell 粒度、Lead repair 权限边界和 follow-up answerability。

已补入 `TECH_00`：

- `Stable Object Graph`：规定 `UserTask -> AgenticResearchLoop -> DecisionSurfaceContract -> DecisionSurfaceCell -> EvidenceRequest / SubagentTask -> ToolInvocation / Observation -> EvidenceCandidate / PromotionDecision -> SpecialistCellPack -> DecisionSurfacePack -> WriterBrief -> Artifact -> WorkbenchReviewAction -> Trace / Eval / RepairTicket` 的稳定对象链。
- `TECH Owner Coverage Matrix`：把 PRD / 117 / 118 中的 agentic research、agentic search、writer no-source、DocumentMetadataIndex、NumericProgramTrace、ArtifactConsistencyGraph、Workbench decision-cell review、trajectory eval 等要求映射到 `TECH_01` 到 `TECH_10`。
- `Capability Maturity Lifecycle`：新增 `documented -> contract_draft -> fixture_proven -> runtime_injected -> node_level_consumed -> paid_artifact_proven -> dogfood_accepted`，明确 TECH 文档默认只是 `contract_draft`，不能伪装为 runtime 已实现。
- `Supersession / Source-of-Truth`：明确 PRD、TECH、worklog、Project OS、旧 R53/S7/P36 文档的优先级和回写规则。
- `不新增 TECH_11` 的理由改成工程边界：只有出现无法归属到 stable object graph 的新运行时对象时才新增 TECH。

已补入 `TECH_01`：

- `task-level loop vs cell-level loop`：Lead 控制任务面，Evidence / SourceHunter / Parser / Numeric / Domain Operator 执行 cell-level loop。
- `RepairTicket` 路由原则：repair 默认回到造成 gap 的来源 agent 或最有权限 agent，Lead 不做万能补源。
- `DecisionSurfaceCell` 粒度规则：第一版 deep research case 控制在 10-20 个核心 cells；每个 cell 回答投资 / 经营判断问题，不是事实 lookup；使用 `cell_archetype_id + cell_instance_id` 支持跨 case / sector 泛化。
- `cell_status` 与 `next_action` 分离：一个描述证据状态，一个描述下一步控制动作。
- `Lead 权限边界`：Lead 可编译 / 修订 contract、分派任务、裁决 gap、生成 writer-allowed pack；不可绕过 Evidence Gate / Numeric Gate，也不可要求 writer 补源。
- `Follow-up Answerability Contract`：Lead 必须保留 CaseControlMemory、DecisionSurfacePack、EvidenceLedger、RepairTicketLedger、TraceSummary，以便回答用户追问。
- `ReAct Trace 不等于 CoT`：持久化可审计 trajectory，不保存 raw chain-of-thought。
- `AI infrastructure first-case cell set`：新增 15 个示例 cell，用于验证 10-20 cell 粒度。

仍未完成：

- 这些补充仍是 architecture / contract draft；
- 尚未实现 runtime schema、状态机、ToolGateway、MCP server、Workbench UI 或 eval；
- 尚未把 9 个 WorkBuddy case 系统化抽象成 sector cell packs；
- 尚未决定 `DecisionSurfaceCell` 应采用多少层 ontology，以及哪些行业先做默认 pack。

## 2026-07-10 追加：DecisionSurfaceCell 泛化策略

用户确认不应一次性把所有行业 cell 定死，也不应完全靠 case-by-case 随手增删。已补入 `TECH_01` 的三层策略：

```text
Universal Cell Archetype
  -> Sector Cell Pack
  -> Case Cell Instance
```

本轮决策：

- `Universal Cell Archetype` 负责跨行业稳定判断模板，例如 demand realness、revenue / profit capture、unit economics、competitive pressure、capital-market price-in、risk / counterevidence、what-would-change。
- `Sector Cell Pack` 负责行业适配，第一批候选行业包括 AI infrastructure、software、consumer、financials、healthcare、energy、industrials。
- `Case Cell Instance` 负责具体 company / sector / user question 的裁剪、实例化和少量特殊 cell，不直接污染 universal archetype。
- WorkBuddy 已跑的 9 个 case 作为第一批 calibration set：重复出现且有判断价值的 cell 可晋升为 sector pack 或 universal archetype；一次性事实查询降级为 evidence slot；过粗、无 owner、无 stop condition 的 cell 拆分或删除。
- cell 生命周期建议为 `case_proposed -> sector_candidate -> sector_pack_accepted -> universal_candidate -> universal_archetype_accepted -> deprecated / superseded`。

边界：

- 本轮只更新 TECH contract 和工作记录；
- 尚未建立 machine-readable cell ontology registry；
- 尚未抽取 WorkBuddy 9-case cell calibration fixture；
- 尚未实现 Lead runtime 对 universal archetype / sector pack / case instance 的选择逻辑。

## 2026-07-10 追加：TECH_02 Evidence Layer 工程边界

用户审阅 TECH_02 讨论后指出：`Parser / Numeric / Metadata Binding` 出现在 TECH_02 流程图中并不矛盾，但必须写清楚 TECH_02 不拥有 parser / numeric 实现。已吸收进 `TECH_02`：

- TECH_02 owns orchestration and promotion logic, not parsing implementation。
- TECH_02 拥有 Parser / NumericTrace 调用接口、metadata / numeric binding 需求声明、返回字段验收和 promotion 决策。
- TECH_02 不拥有 PDF 表格解析算法、XBRL exact row selector、数值复算程序、表格 lineage 构建。

本轮把 TECH_02 改成六个主要工程 section：

1. `EvidenceRequest Compilation`：从 `DecisionSurfaceCell` / `RepairTicket` 编译 evidence slot，不允许自由搜索词直接驱动；必须绑定 `cell_id`、`evidence_slot_id`、entity、period、source policy、forbidden substitutions 和 accepted evidence role。
2. `Tool Registry`：登记 tool capability、source authority、can_support / cannot_support、failure types、fallback、permission scope；用 `RelationshipGraphSearchToolV2` 示例说明 graph lead / shipment lead / verified direct edge 不能混用。
3. `Evidence Tool Planner State Machine`：定义 `INIT -> COMPILE_REQUEST -> SELECT_TOOL -> EXECUTE_TOOL -> OBSERVE_RESULT -> CLASSIFY_CANDIDATE -> NEED_MORE? -> FALLBACK_OR_STOP -> EVIDENCE_GATE -> BUILD_RESPONSE`，并加入 `max_tool_calls`、`max_fallback_depth`、`source_authority_stop_rule`、`commercial_gap_stop_rule`、`confidence_threshold` 等硬约束。
4. `SourceHunter Trigger Policy`：明确 internal KB 不足、official-first、Evidence Gate 拒绝但公开源可得、P36 supplement runtimeization、RepairTicket evidence_missing 等可触发；writer 私补源、specialist 私有搜索、低质量网页替代 commercial gap 等禁止。
5. `Evidence Gate Promotion Contract`：固定 `accepted`、`context_only`、`rejected`、`typed_gap`、`commercial_gap` 五类状态，并规定进入 DecisionSurfacePack / specialist / writer 的边界。
6. `P36 Supplement Runtimeization Fixture`：`supervisor_supplement_only -> SourceHunterRequest -> official-first attempts -> ToolUseLedger -> EvidenceGate -> accepted/context_only/typed_gap/commercial_gap`；如果 supplement 直接进入 writer，fixture 失败。

关于 Evidence Gate 的判定方式，本轮形成的设计判断：

- Evidence Gate 不应是纯 LLM 判断器，也不应是纯规则表。
- deterministic gate 负责硬约束：entity、ticker、period、unit、source authority、metadata、parser lineage、numeric trace、forbidden substitutions、permission。
- Evidence agent 可以给 `classification_suggestion`、`reasoning_summary`、`repair_suggestion`，但不能单独晋升证据。
- Lead 可以裁决 gap 是否披露给 writer，但不能 override deterministic hard fail。
- 高影响或歧义 evidence 可进入 Workbench / human review 做最终 accept / reject / supersede。

关于 topK / chunk 切断问题，本轮补入 `Retrieval / Reranking / Chunk Neighbor Policy`：

- topK 不应全局固定，应由 `EvidenceRequest.topk_policy` 分段控制：`candidate_top_k`、`rerank_top_k`、`evidence_candidate_top_k`、`neighbor_window`、`source_diversity_cap`。
- Reranker 只做 candidate ordering，不能决定 promotion。
- DocumentMetadataIndex 必须支持 `prev_chunk_id`、`next_chunk_id`、`parent_section_id`、`table_id`、`page_range`、`row_range`、`parse_boundary` 等 chunk lineage。
- 如果命中 chunk 位于边界、缺 table header / unit / period / footnote、同 section 存在邻居 chunk，runtime 不得直接判断“知识库没有”；必须先做 `NeighborChunkRequest`、`SectionExpansionRequest`、`TableContextRequest` 或 `MetadataFilteredRequery`。
- 只有 chunk / section / table context recovery 都失败后，才能升级为 `retrieval_exhausted`、`SourceHunterRequest` 或 attempt-backed `typed_gap`。

边界：

- 本轮只更新 TECH contract 和工作记录；
- 未实现 ToolGateway、Evidence Gate、chunk-neighbor retrieval、SourceHunterLoop、Parser/Numeric接口、Workbench review 或任何 runtime 代码；
- 未运行 paid LLM、full-chain、source ingestion、parser promotion、MCP server 或 reranker eval。

## 2026-07-10 追加：chunk / parser 工具吸收暂定方向与审计前置

用户指出：现有 SEC chunk 和表格抽取历史上有可用部分，但在 unit / scale、表格抽取、row selector 和 chunk precision 上仍有风险；新引入的文档解析 / 网页抓取 / 表格 fallback 工具是否吸收，不能直接拍板，必须先审计现有 runtime 对应环节。

已补入 `TECH_02`：

- 把 SEC CompanyFacts / XBRL 继续列为 official structured numeric fact 的最高优先级。
- 把 MarkItDown、pdfplumber、Camelot、Docling、MinerU 的角色写成分层 fallback：MarkItDown 做轻量 visibility，pdfplumber 做文本 PDF 表格第一层，Camelot 做规则表格 fallback，Docling 做复杂 PDF / layout / table lineage heavy fallback，MinerU 做扫描件 / 复杂研报 / 困难表格重型 fallback。
- 把 feedparser、GDELT、Trafilatura、Crawl4AI、Crawlee + Playwright、OpenBB 放入 source discovery / extraction / market context 的 Tool Registry 边界。
- 明确 Tool Planner 可以根据 observation 重新选工具，但 fallback 结果仍只是 candidate，最终 promotion 必须经过 Evidence Gate。
- 新增审计前置：在决定重切 chunk、重跑 parser 或替换表格抽取链路前，先审计 chunk profile、retrieval precision、table extraction、SQL exact rows、unit/scale、row selector false positive、Evidence Gate promotion rate 和失败类型分布。

已补入 `TECH_03`：

- 当前判断：SEC 主线 chunk 工程基本可用，既有 `900 words / 150 overlap / min 80` 和 8-K `650 words / 100 overlap / min 40` 可保留为 BM25 baseline，但不应继续作为唯一策略。
- 新增 `TextChunkProfileRegistry -> source_type profile -> element_type profile -> retrieval profile -> numeric/table profile` 暂定方向。
- Profile 暂定：
  - SEC narrative / MD&A / Risk Factors：保留固定 word baseline，同时新增 700-900 tokens、20-30% overlap 的 token-based profile；
  - 8-K earnings release：500-700 tokens，并保留 earnings / guidance parent context；
  - 表格：不按 word chunk 处理，抽成 `TableObject` / `TableRowObject` / `TableCellObject`；
  - IR PDF / 非美年报 / press release PDF：采用 layout-aware parser profile；
  - 产品规格 / 技术页面：300-600 tokens，按 heading / list / spec table 切；
  - 新闻 / 普通网页：按 article / paragraph / heading 切，通常只进入 context_only。
- 明确 child-parent 策略：child chunks 做 recall，parent section / table context 做 Evidence Gate，TableObject / NumericProgramTrace 做 exact promotion，writer 不得直接引用普通 chunk 内数字。
- 新增现有 runtime 审计输出清单：`chunk_profile_audit_summary`、`retrieval_precision_by_slot`、`table_extraction_quality_summary`、`numeric_scale_unit_audit`、`row_selector_false_positive_report`、`source_family_parser_gap_matrix`、`evidence_gate_conversion_report`。

边界：

- 本轮只更新 TECH contract 和工作记录；
- 未运行现有 runtime 审计；
- 未重建 chunk / vector index；
- 未重跑 parser / source ingestion；
- 未把新工具接入默认 runtime；
- 未运行 paid LLM、full-chain、MCP server、Workbench replay 或 reranker eval；
- 后续具体改造必须先由现有 runtime 审计决定，不做 blind full reingestion。

## 2026-07-10 追加：TECH_03 对象分层、外源信号、数据基座与 TECH_05 方法/图谱投影

用户确认 TECH_03 应正式定义为证据地址层与研究记忆层，并指出此前外源补充、数据基座、研报底稿 skill 和研究知识图谱的 TECH 归属仍不够清楚。

已补入 `TECH_03`：

- 新增准确定义：TECH_03 是证据地址层与研究记忆层，只向 TECH_02 输出 `CandidateBundle`，不做 evidence promotion、numeric audit、业务判断或写作。
- 新增硬边界：
  - `TECH_03 returns candidates, not evidence.`
  - `Chunk is a retrieval unit, not an evidence unit.`
  - `Memory is a prior, not a substitute for current evidence.`
  - `Metadata filtering precedes reranking.`
  - `Tables are first-class objects, not text chunks.`
  - `Repair cache records search history, not final truth.`
  - `Freshness and revision checks are mandatory before reuse.`
- 新增 Core Object Model 分层：
  - Source Layer：`SourceDocument`、`DocumentRevision`、`SourceSnapshot`、`SourceLicensePolicy`；
  - Structure Layer：`DocumentElement`、`ChunkObject`、`TableObject`、`TableRowObject`、`TableCellObject`、`FigureObject`、`FootnoteObject`；
  - Candidate Layer：`RagCandidate`、`TableCandidate`、`GraphCandidate`、`SourceCandidate`、`ExternalSignalCandidate`、`CandidateBundle`；
  - Memory Layer：`AcceptedMemoryEntry`、`AcceptedFactMemory`、`AcceptedJudgmentMemory`、`ReviewerDecisionMemory`、`DecisionSurfacePackMemory`；
  - Repair Layer：`RepairCacheHit`、`GapHistoryEntry`、`CoverageAuditRecord`。
- 新增 `CandidateBundle Contract`，规定 TECH_03 的主输出必须带 evidence_request / cell / slot / metadata / freshness / candidate / repair / authority boundary / cannot_support。
- 新增 `External Signal / News / Public Statement Layer`，把新闻、公开人物发言、政策、地缘政治事件、事件簇建模为 `ExternalSignalCandidate`，并明确新闻和转述默认只能做 lead/context，黄仁勋等管理层发言需要官方公司源或 transcript 才能升为 company-authored context，中美冲突 / 出口管制等需优先找 BIS / Commerce / official government source。
- 新增 `Data Foundation Source Map`，把现有数据基座分成 SEC/US issuer disclosure、company-authored material、non-US disclosure、market/capital、macro/industry、product/regulatory vertical、public web proxy、technology/IP、news/discovery、graph stores，并记录其用途和边界。
- 新增 `Method / Workpaper / Research Graph Memory Boundary`，规定 MethodMemory、WorkpaperExemplarMemory、ResearchGraphPointer、SkillMemoryRef 只能作为 planning prior / rubric / pointer / skill version，不能替代事实证据。

已补入 `TECH_05`：

- 在 projection 表中新增 `MethodToDomainOperatorProjection` 与 `ResearchGraphToThesisMechanismProjection`。
- 新增研报方法 / 底稿 skill / 研究知识图谱边界：方法和底稿样例生成 operator rubric、required judgment moves、cell checklist、what-would-change 模板；研究图谱生成 mechanism path、candidate relationship、value-capture hypothesis、risk-transmission hypothesis；prompt skill 约束输出结构和判断深度，但不能替代 accepted evidence。
- 新增 domain operator 输出要求：Fundamental、Product/Industry、Graph、Market/Capital、Risk 都必须输出 cell-level `SpecialistCellPack`，而不是 memolet。
- 新增外源信号在 TECH_05 的使用边界：官方公司/监管/政府源可进入对应 context；媒体报道或转述只能 `context_only` 或 `lead_only_needs_verification`；地缘政治 / 政策事件优先 official source。
- 新增 Method-to-Operator fixture 要求，覆盖 thesis path、product-to-financial bridge、three-statement peer panel、secondary-market feedback、customer-supplier readthrough 和 humanmade gold exemplars。

已补入 `TECH_00`：

- Owner coverage matrix 新增 `Data foundation source map`、`External news / public statements / policy events`、`Research methods / workpaper exemplars / research graph` 三类归属。

边界：

- 本轮只更新 TECH contract 和工作记录；
- 未实现 runtime schema、CandidateBundle、ExternalSignalCandidate、MethodToDomainOperatorProjection 或 ResearchGraphToThesisMechanismProjection；
- 未运行 source ingestion、parser、retrieval audit、reranker eval、MCP server、Workbench replay、paid LLM 或 full-chain；
- 现有 R53/P14/S3 L4 和 source manifests 仅作为数据基座事实引用，不代表 vNext DecisionSurface runtime 已完成。

## 2026-07-10 追加：公开资本市场补源、DerivedMetricRegistry 与 Research-to-Quant 对齐

用户在 TECH_04 讨论中追问两件事：第一，公开、低频、字段有限的资本市场数据还应补哪些维度和历史深度；第二，是否可以通过建模 derived 出显著因子，补强报告并弥补商业源不足。随后要求把公开补源、衍生指标计算和量化建模边界回写到对应 PRD / TECH / R53 文档。

本轮形成的核心判断：

- 当前最重要的补源不是继续增加同一 snapshot 的字段，而是 `current snapshot -> PIT historical panel`、`single price view -> market/ownership/credit/derivatives/event joint panel`、`US-centric -> non-US official sources`。
- 公开源优先补多年 adjusted OHLCV、corporate actions、historical universe/delisting、filing available time、amendment/restatement、13F/N-PORT/insider/13D-G、ALFRED vintage、issuer guidance/events、non-US exchange/regulator adapters，再补 FINRA short/TRACE、OCC/CFTC 等资本反馈。
- 公开可访问不等于可商业批量使用；SourceLicensePolicy 必须记录 bulk、redistribution、retention、commercial/non-commercial 和 citation 条件。
- Numeric Agent 不得自由发明指标。TECH_04 新增 `DerivedMetricRegistry` / `MetricDefinition` / `ComputeEligibilityAssessment`，由 DecisionSurfaceCell 提出 metric intent，registry 决定公式、输入、history、period/as-of/scope/currency/lag/missing/forbidden-substitution policy。
- derived output 固定区分 `deterministic_derived_exact`、`bounded_delayed_market_metric`、`assumption_based_estimate`、`diagnostic_score`、`unavailable_or_commercial_gap`。
- 当前短窗口 market pack 不能自动开放 6M/12M/beta/historical percentile；`return_ytd` 必须验证覆盖当年首个交易日，否则只能标 `available_window_return`。
- TECH_04 只生成 source-backed feature 和 NumericProgramTrace；现有 R53/S9 才负责 FactorHypothesis、PIT dataset、leakage/OOS/multiple-testing、factor analysis/backtest、RiskAttribution、FactorCard 和 human approval。
- 建模可以产生公开数据下的 proxy 和 quant corroboration/counterevidence，不能还原 consensus revision、real-time flow、dealer gamma、borrow cost、CDS、完整机构仓位或未披露业务线 economics。
- Factor lifecycle 固定为 `diagnostic_score -> research_factor_candidate -> in_sample_supported -> out_of_sample_supported -> paper_monitored_factor -> retired_or_failed`；只有 OOS-supported 及以上结果可作为 bounded quant validation，且仍不是投资建议。

本轮更新：

- `TECH_00_agentic_research_technical_index.zh-CN.md`：补充 public-market PIT、DerivedMetricRegistry 和 Research-to-Quant owner coverage。
- `TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`：新增公开资本市场补源、PIT 对象、官方 source map、license boundary 和深度优先级。
- `TECH_04_numeric_program_trace_parser_promotion.zh-CN.md`：升级为 Structured Numeric Fact Compiler，新增完整对象、三条 pipeline、bounded repair、DerivedMetricRegistry、market sufficiency、R53 边界、审计和 fixtures。
- `TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`：新增 QuantValidationDecisionSurfaceProjection 和 FactorCard 到 cell 的身份边界。
- `TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`：新增 FactorCard / Quant Validation lineage 与 Workbench review。
- `PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：在 Research-to-Quant Lab 下新增 dated product addendum，明确 public-data、derived metric、diagnostic score、validated factor 和 user-facing Decision Surface。
- `28_r53_research_to_quant_lab_technical_plan.zh-CN.md`：新增 vNext 对齐、数据最低合同、significance discipline 和当前状态修正。

边界：

- 本轮仅更新 product / architecture / worklog 文档；
- 未执行公开源 ingestion、market history backfill、security-master build、parser、feature materialization、模型训练、factor analysis、event study、backtest、paper trading、paid LLM、full-chain 或 Workbench replay；
- S9 / P33 Research-to-Quant 仍是 runtime-alignment / smoke 证据，不代表生产级 alpha 或新增因子已经显著；
- 下一轮继续讨论 futures / options / other derivatives 是否以及以什么层级进入产品和数据基座。

## 2026-07-10 追加：Futures / Options / Other Derivatives 分层策略

用户认可衍生品应加入项目，但要求明确每类数据的研究价值、字段、计算、runtime 激活方式和不值得投入的范围。

本轮固定的设计判断：

- 衍生品是一等 PIT 数据对象，但不是所有研究任务默认注入的 payload；通过 `DerivativesExposureMap` 按 sector/company/cell 激活。
- 优先顺序为 futures / COT / broad volatility regime > cell-activated single-stock options / convertibles / issuer credit > investigative/commercial OTC/CDS/TRS/exotics。
- TECH_03 新增 `DerivativeInstrumentMaster`、`DerivativeObservationPIT`、`FuturesCurveSnapshotPIT`、`COTPositionPIT`、`PublicSwapRegimePIT`、`IssuerDerivativeCapitalContext`。
- TECH_04 新增 `DerivativeMetricRegistry`：curve/roll/basis/OI/COT、put-call/IV/term/skew/event move、credit/swap/convertible metrics，并加入 roll/expiry/preliminary-final/OI lag/contract adjustment hard gates。
- TECH_05 新增 `DerivativesMarketSignalProjection`，只输出 regime、expectation、positioning proxy、tail risk、funding/dilution、equity-credit divergence 和 gap，不证明 fundamentals。
- 不新增常驻人格化 derivatives specialist；复杂衍生品任务才通过 TECH_08 激活 `DerivativesQuantOperator` subagent-as-tool。
- R53 只把 source-backed derivative metrics 作为 PIT feature/event/regime input；gamma/borrow/real-time OPRA/high-frequency/exotics 默认阻断或 commercial gap。

本轮更新：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`
- `TECH_04_numeric_program_trace_parser_promotion.zh-CN.md`
- `TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`
- `28_r53_research_to_quant_lab_technical_plan.zh-CN.md`
- `PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：

- 本轮仅更新 product / architecture / worklog 文档；
- 未接入 CME/OCC/CFTC/SDR/OPRA 数据，未建立 derivative instrument master，未计算 IV/Greeks/curve/COT factors，未运行 backtest、paid LLM、full-chain 或 Workbench replay；
- 现有 S8/P33 broad-market derivatives regime fixture 不能视为 single-stock options、dealer gamma、OTC 或完整 DerivativesMarketSignalPack runtime 能力。

## 2026-07-10 追加：External Source Admission、第一方社交发言与舆情监控

用户认可前一轮外源分层，但修正“社交媒体不值得正式吸收”的过度概括。用户指出 X/Twitter、微博、微信公众号、YouTube 上的官方认证账号、公众人物、CEO、产品负责人、发布直播和公开互动具有实际研究价值；高赞评论和用户回复也可作为低权重反馈与舆情监控输入。关键不是排除社交媒体，而是避免把人物发言、账号认证和 underlying fact truth 混为一体。

本轮固定的判断：

- 外源分四条 lane：`persistent_data_foundation`、`on_demand_sourcehunter`、`discovery_only`、`licensed_adapter`。
- P35/P36 已显示 issuer IR/official PDF、官方产品/客户部署和政府监管材料比无差别普通新闻更能增加 decision-cell 价值。
- 社交账号必须拆分 account authenticity、statement authenticity、underlying claim truth；认证或官方账号可以提高归因可信度，不能自动证明其事实主张。
- 平台 verification 语义不是统一布尔值。X 普通 blue check 可能只是 Premium；组织/政府 badge、官方域名反链、affiliation、账号 ID、handle history 和 snapshot 必须共同进入 identity provenance。
- 公众人物或高管发言可以支持 attributed statement、policy intent、product announcement、roadmap lead、event catalyst 和 market narrative；政策生效、产品交付/性能、销量、订单和财务贡献仍需更高权威事实。
- 高赞评论、回复和用户帖子可生成 `UserFeedbackTheme` / `ObservedDiscourseCard`，但必须披露平台、query、时间窗口、样本、排序、去重、bot/spam、语言/地区、missingness 和 representativeness；未审计样本只能叫 sentiment example。
- 发言与 accepted fact 冲突时生成 `ClaimConflictRecord`，区分 fact、intent/forecast、opinion/rhetoric 和 market-impact event。高权威事实控制事实判断，原发言仍保留为叙事、风险、谈判或市场影响信号。
- Writer 不能私自访问社交平台或自行裁定冲突，只能使用带 attribution、sample boundary 和 conflict status 的 DecisionSurface material。

本轮更新：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md`
- `TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md`
- `TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`
- `TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：

- 本轮仅更新产品和技术合同；
- 未接入 X、微博、微信公众号或 YouTube API/爬虫，未抓取社交内容，未建立舆情样本或人工 gold set；
- 未实现 SocialSourceSnapshot、SocialDiscourseSample、ClaimConflictRecord、ExternalSocialSignalDecisionSurfaceProjection 或 Workbench review surface；
- 未运行 ingestion、agent runtime、paid LLM、full-chain、舆情模型或跨平台 representativeness eval；
- 当前能力状态为 `documented / contract_draft`，不能描述为 runtime 已具备 social listening。

## 2026-07-10 追加：TECH_05 Domain Judgment Architecture 与 Active What-Would-Change

用户确认将 TECH_05 十项补强写入对应文档，并进一步提出：`what_would_change` 不应只是边界说明，而应展示 agent 如何识别决定性变量、提出正反方向、主动找数据、记录取证尝试、形成 directional assessment，并在找不到证据时如实返回 gap；该内容在输出中保持独立章节，不并入主结论，可视为 Risk / Counterevidence agent 的升级能力。

本轮固定：

- `SpecialistCellPack` 的循环命名拆为 `DomainOperatorTask + CellEvidencePack -> DomainCellJudgmentPack`。
- TECH_05 拆成 deterministic projection、LLM domain judgment、mixed Cell Adjudicator 三层。
- 每个 cell 区分 primary、contributor、challenger、evidence、repair ownership。
- Domain operator 支持 bounded loop、RepairTicket、checkpoint resume；durability 由 TECH_06 承担。
- judgment status 与多维 confidence vector 分离；新增 `CellDependencyEdge`、`SectorOperatorPack`、activation reason 和 cell-level budget/AIE。
- 新增 `WhatWouldChangeProgram`、`DecisionChangeCondition`、`CounterfactualTest`、`MonitoringTrigger`。
- Primary operator 提出 decisive variables，Risk / Counterevidence 是默认 challenger；Evidence/SourceHunter/Parser/Numeric 执行取证。
- What-Would-Change 研究可以触发新 cell version 和 re-adjudication，但不能静默覆盖主结论；产品中始终独立展示。
- 对外只展示 causal/action rationale、evidence sought、attempt/observation summary、directional assessment、gap 和 trigger，不展示 private CoT。

更新文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_01_agentic_research_loop_decision_surface_contract.zh-CN.md`
- `TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`
- `TECH_06_durable_harness_runtime_permission_state.zh-CN.md`
- `TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
- `TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`
- `TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：

- 本轮仅更新 product / technical contracts / worklog；
- 未实现 DomainOperatorTask、CellEvidencePack、DomainCellJudgmentPack、CellAdjudicator、WhatWouldChangeProgram、counterfactual tests、checkpoint resume 或 Workbench panel；
- 未执行 source retrieval、parser/numeric repair、model call、paid LLM、full-chain 或 Workbench replay；
- 当前状态仍是 `documented / contract_draft`。

## 2026-07-10 追加：TECH_06 Durable Harness 执行语义补强

用户确认将 TECH_06 的 12 项运行合同补入文档，并追加 EventEnvelope、deterministic replay boundary、dead-letter/poison WorkUnit、artifact immutability 和 PermissionSnapshot 五项要求。

本轮固定：

- `FinSightRuntimeFacade` 统一 Workbench/Java/CLI/API/worker 的 create/admit/start/pause/resume/cancel/retry/repair/replay/fork/review/state/event/artifact 操作。
- append-only RunEvent 是执行事实源；SQL current state、Workbench 和 metrics 是 projection；LangGraph checkpoint 不是企业审计主账本。
- EventEnvelope 记录 per-run sequence、occurred/recorded time、actor、causation、correlation、state before/after、payload ref/digest 和 schema version。
- TaskRun、WorkUnit、Attempt 分层状态机允许 waiting/partial/bounded/superseded/dead-letter 等金融研究正常状态。
- retry/resume/repair/replay/fork 具有不同版本和副作用语义；LLM/web/API 默认不在 replay 中重调。
- checkpoint 分 graph/cell/review/artifact；durable artifact immutable，以新版本 supersede 旧版。
- 第一版采用 at-least-once + idempotency + optimistic version check + transaction/outbox，不声称 exactly-once。
- queue 增加 lease/heartbeat/cancel/backpressure/stale-write；并发 operator 只提交 proposal，Cell Adjudicator 生成新 cell version。
- CapabilityGrant 和 PermissionSnapshot 记录当时有效授权，不保存 credential；历史 policy 变更不改写旧 allow/deny。
- BudgetLedger 使用 task/cell/operator/attempt 分层 reservation/actual/stop；耗尽后 bounded partial，不允许 Writer 假装完整。
- HITL approval 绑定具体 artifact/state/cell version，material version change 后自动 stale。
- SQL/ObjectStore/LangGraph/queue/ToolGateway/secret manager 边界固定；Temporal 保持 optional escalation。
- poison WorkUnit 超过 max attempts 或遇到 non-retryable error 后进入 dead-letter，只有 human/admin 能以新 version repair/requeue/fork。

修改文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_06_durable_harness_runtime_permission_state.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：

- 本轮仅更新 technical contract 和 worklog；
- 未实现 RuntimeFacade、event tables、state machines、queue worker、permission snapshot、artifact store、dead-letter 或 replay engine；
- 未执行 runtime migration、LangGraph replay、worker crash test、paid LLM、full-chain 或 Workbench replay；
- 当前状态为 `documented / contract_draft`。

## 2026-07-10 追加：TECH_07 ContextEngine / Memory / Compaction Governance 补强

用户确认将 TECH_07 的 14 项补强写入文档：ContextEngine API/ContextRequirement、context objects、role matrix、hard filter/utility/diversity/budget、progressive disclosure、structural/semantic compaction、self-compaction、memory taxonomy/lifecycle、freshness/invalidation、usage/AIE、permission/privacy/forget、follow-up/repair/What-Would-Change continuity、统一入口和 context eval。

本轮固定：

- ContextEngine 是 view compiler，不是事实库或聊天 memory dump；TECH_03 保存对象，TECH_06 保存 durable events。
- 新增 resolve/select/expand/compress/inject/observe/write-candidate/consolidate/invalidate/explain API 和 `ContextRequirement`。
- 新增 ContextCandidate/Snapshot/SelectionDecision/CompressionArtifact/InjectionPlan/UsageObservation/MemoryVersion/InvalidationEvent。
- context classes 扩为 governance、identity/scope、case control、cell working、role method、evidence artifact、institutional、preference 和 private working，并定义 Lead/Evidence/Domain/Risk/Writer/Verifier read-write boundary。
- selection 先 permission/scope/state/as-of/authority/version hard filter，再 utility/diversity/budget；embedding 只是一项 relevance feature。
- budget 预留 governance/task/evidence/counterevidence/numeric/method，不允许 optional background 挤占。
- skill/artifact 采用 metadata -> summary -> relevant section -> targeted exemplar/drilldown 渐进式披露。
- compaction 先 externalize/dedupe/structural，再 semantic；必须保留 ID、period/unit、authority、identity、negation、conflict、gap、forbidden claim 和 version。
- self-compaction 由 agent 请求、ContextEngine 执行，只生成新 plan/event，不改 source-of-truth。
- memory 分 semantic/episodic/judgment/procedural/preference/negative/accepted-fact-index，默认先 candidate，再 reviewed/active，后续可 stale/superseded/revoked/contradicted。
- invalidation 由 filing/parser/source-policy/reviewer/cell/permission/user/TTL 事件驱动，并生成 downstream reopen candidates。
- ContextUsageObservation 支持 AIE，但一次未引用不能自动删除 governance/counterevidence。
- PermissionSnapshot、tenant isolation、retention/forget、secret alias 和 external prompt-injection boundary 固定。
- follow-up 从 durable case state 重建；repair 只注入 delta；What-Would-Change 保留 decisive variables/attempts/gaps/triggers。
- ContextEngine 成为唯一 public runtime entry，现有 ContextManager/data view/SQL ContextInjectionPlan 逐步适配，避免多套截断/压缩逻辑。

修改文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：

- 本轮仅更新 technical contracts / eval contract / worklog；
- 未实现新 ContextEngine API、memory store、invalidation、self-compaction、usage feedback、forget 或 unified facade migration；
- 未运行 context migration、live-node injection、model call、paid LLM、full-chain 或 Workbench replay；
- 当前状态为 `documented / contract_draft`。

## 2026-07-10 追加：TECH_07 ContextSnapshot / SelectionDecision / Injection Replay 对象补充

用户补充 TECH_07 稳定对象清单，并特别要求 ContextSnapshot 冻结编译候选版本、ContextSelectionDecision 逐候选记录 selected/rejected/deduplicated/externalized 原因、ContextInjectionPlan 在相同 plan/artifact versions 下可重建相同模型输入。

本轮吸收：

- 稳定 ContextRequirement、ContextCandidate、ContextSnapshot、ContextSelectionDecision、ContextBlock、ContextInjectionPlan、ContextExpansionRequest、ContextUsageObservation、CompactionEvent、MemoryCandidate、MemoryEntry/Version、MemoryInvalidationEvent、RoleContextPolicy。
- ContextSnapshot 固定 source/artifact/memory/skill/permission/version 视图；编译中版本变化必须 fail/recompile。
- ContextSelectionDecision 每 candidate 记录 selected、permission/scope/stale/revoked/authority/version/budget reject、deduplicated 或 externalized，并保留 policy/utility/replacement refs。
- ContextBlock 固定 block type、message/section role、content/ref、must-preserve、token estimate、priority、order 和 digest。
- ContextInjectionPlan 固定 ordered blocks、所有依赖 versions、tokenizer/input-template/config、canonical serialization 和 input digest；相同版本重建 byte-stable canonical model input。
- Semantic compaction replay 复用冻结 compression artifact；重新压缩产生新 plan。
- ContextExpansionRequest 只能生成新 plan version，不原地修改运行中 attempt。
- RoleContextPolicy 版本化 read/write/budget/expansion/compaction/memory/private-context policy，并绑定每次 selection/injection。
- TECH_10 新增 input reconstruction 和 snapshot race eval。

修改文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：仅更新合同和 eval/worklog；未实现 snapshot transaction、selection ledger、ContextBlock builder、canonical input replay 或 ContextExpansionRequest runtime。

## 2026-07-10 追加：TECH_08 结构化通信与并行版本选择性失效

用户指出 TECH_08 仍缺两项关键合同：subagent/agent-as-tool 遇到问题时不能只返回 gap，需要携带可理解的前因后果；并行 agent 基于同一 pack 运行时，某一结果推进 pack version 后，其他 agent 不能无条件全停或无条件继续。

本轮固定：

- 新增 `Structured Coordination and Causal Message Contract`：跨 agent 发送 `CoordinationMessageEnvelope`，包含 routing、research scope、input versions、expected contract、observation/attempt summary、rejected substitutions、downstream impact、requested action 和 audit refs。
- 结构化 reasoning/action summary 不等于 raw CoT；大文档、row、trace 和 observation 留在 artifact store，通过 immutable refs drill down。
- 稳定 Clarification、Dependency、Evidence/Numeric Repair、Judgment Conflict、Permission Escalation、Version Advance、Writer Blocker 和 Bounded Gap 消息；所有消息由 Harness 路由并持久化，禁止 peer free chat 改状态。
- 新增 `Parallel Snapshot, Version Advance and Selective Invalidation Contract`：并行 WorkUnit 绑定 immutable snapshot，agent 只提交 proposal/delta，artifact owner 才能推进 head。
- `InputDependencyManifest` 记录 read/write/dependency set、versions、assumptions、policy 和 checkpoint；`PackChangeSet` 记录新 head 具体改变的 refs、identity、status、judgment 和 dependency scope。
- TECH_06 `VersionImpactCoordinator` 是状态迁移入口：规则判断 no-overlap 和 hard invalidation；Cell Adjudicator/Lead 对语义材料性给 suggestion；coordinator 结合 policy 输出 durable `WorkUnitVersionDecision`。
- 版本结果固定为 continue、continue-then-validate、rebase-at-checkpoint 和 cancel-and-supersede；不同 agent 可使用 pinned snapshot、refresh/interruption 或 latest-head policy。
- rebase 由 coordinator 生成 `ContextRebaseRequirement`，TECH_07 ContextEngine 保留有效 blocks、替换 stale refs、注入 delta/conflict/re-analysis questions 并生成新 plan；禁止运行中热替换 prompt。
- TECH_10 新增 coordination completeness/routing、parallel impact、semantic materiality、selective invalidation、context rebase 和 stale fan-in eval。
- 用户进一步指出“分类结果”仍缺 runtime 状态感知。本轮补充 `WorkUnitExecutionView` 三个正交状态面：execution state、input currency 和 output usability；head advance 先进入 `head_advanced_unassessed`，不直接假定 continue 或 stale。
- Worker 在 start、safe checkpoint、下一次 model/tool action、resume 和 result/fan-in commit 前校验 expected versions 与 event sequence；event 延迟仍由 optimistic commit gate 拦截。
- 新增 `MaterialityContract`：consumer 显式声明对 direction、magnitude/timing、confidence threshold、mechanism、evidence identity/status、counterevidence、What-Would-Change 和 claim scope 的敏感度，区分 citation-only 增量。
- `VersionImpactSuggestion` 使用明确 change dimensions；coordinator 结合 consumer triggers 决定 validate/rebase，不能只用“有没有推翻原结论”。
- Agent 只接收 `VersionControlDirective`；rebase 时 TECH_07 注入最小 `RuntimeStateBlock`，不暴露全局 state，也不允许 agent 自行更新状态。
- 不可中止的 atomic call 可以返回，但 observation 必须 quarantine；在版本未判定前不能开启下一次旧版决策或提交 current output。
- TECH_08 增加显式 T0-T5 状态迁移示例，覆盖 current、head-advanced-unassessed、checkpointing、material-rebase-required、recompiling 和新 WorkUnit resume。
- 固定 `PackChangeSet.change_dimensions ∩ MaterialityContract.consumer_sensitivity -> impacted triggers -> re-analysis scope -> WorkUnitVersionDecision`，避免仅凭“新材料没有推翻旧结论”判断是否继续。

修改文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_06_durable_harness_runtime_permission_state.zh-CN.md`
- `TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
- `TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：本轮仅更新技术合同、eval contract 和 worklog；未实现消息路由器、VersionImpactCoordinator、dependency manifest/change set、并行 scheduler、semantic impact assessor 或 context rebase runtime，状态仍为 `documented / contract_draft`。

## 2026-07-10 追加：TECH_09 Last-Mile Presentation / Provenance / Review / Release 补强

用户确认将 TECH_09 的 14 项补强写入技术文档。核心修正是：TECH_09 不再只是 trace viewer / artifact checklist，而是冻结研究真相到用户可见交付物之间的 truth-preserving projection、verification、Workbench review 和 release control plane；现有 R55 继续负责 renderer / RenderJob / format-specific generation。

本轮固定：

- TECH_09 与 R55、TECH_06/07/08/10、R59 的 owner 边界；renderer 失败不等于研究失败。
- `FrozenDecisionSurfaceSnapshot -> DeliverablePlan/WriterBrief -> NarrativeSurfaceContract -> CanonicalPresentationModel -> SurfaceClaim/Binding -> ArtifactVersion -> Verification/Review/Release` 对象链。
- Writer/Presentation Agent 只做受众、语言、故事线、表格图表和多格式表达的 bounded loop；禁止 DB/RAG/web/parser/numeric research，缺口返回 typed WriterBlocker。
- 新增 `SurfaceClaim` / `ClaimSurfaceMap`，允许多格式不同措辞，但共享 claim identity、strength、period/unit/scope、uncertainty 和 source/cell versions。
- WriterBlocker 分 storyline/evidence/numeric/judgment/provenance/disclosure/render/language，并路由对应 owner；presentation-only revision 不触发 research rerun。
- Provenance 同时支持 backward clickthrough 和 source/cell/version change 的 forward artifact/release invalidation。
- ArtifactConsistencyGraph 固定 node/edge 和 identity/numeric/semantic/evidence/version/visual/disclosure/completeness constraints。
- Verifier 分 deterministic、semantic、visual 和 human 四层；LLM 不能 override hard fail，Verifier 不补源。
- Memo/Word/PPT/Excel/PDF/dashboard 从同一 canonical model 投影，追求 semantic parity 而非文字相同；dashboard 不创造幽灵状态。
- Artifact revision/approval/release/supersession immutable/versioned，approval 绑定 exact versions，material upstream change 自动 stale。
- Workbench 固定 DecisionSurfaceMatrix、ClaimProvenanceDrawer、ArtifactConsistencyPanel、RepairAndReviewQueue、VersionReleaseTimeline 五类 surface。
- Human edit 分 presentation-only、claim-wording、research-truth 和 source-correction，分别走 artifact version、SurfaceClaim patch、cell adjudication 或 Evidence/Numeric gate。
- Internal/client-safe disclosure 不是简单隐藏 citation；不可披露 evidence 支撑的强 claim 必须删除、降级或 review。What-Would-Change 保持跨格式独立 canonical section。
- TECH_10 增加 canonical parity、claim boundary、writer no-source trajectory、bidirectional provenance、constraint graph、verifier boundary、multi-format、human edit、client-safe、release 和 Workbench/client-ready eval。

修改文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：本轮只更新 technical/eval contracts 和 worklog；未实现 CanonicalPresentationModel、SurfaceClaim、Writer state machine、bidirectional invalidation、constraint graph、four-layer verifier、Workbench surfaces、renderer、release service 或 client-safe gate。状态仍为 `documented / contract_draft`。

## 2026-07-11 追加：TECH_09 Staleness / Release / Interface / Metrics 细化

用户确认吸收 TECH_09 点评中尚未写细的部分。本轮不改变 Research-to-Delivery Control Plane 主方向，重点补齐可执行状态、接口和评测定义：

- 新增 ArtifactStalenessAssessment：current、partially stale、materially stale、superseded 和 withdrawal required，按 SurfaceClaim/projection dependency 做局部影响分析，不因无关 head advance 全量作废。
- artifact production、staleness、approval/release 三个状态面分开；明确 released、published、stale review required、superseded 和 withdrawn。
- Release Gate 绑定 material claims、numeric/citation/version、disclosure、required What-Would-Change、HumanApproval 和 exact hashes；审核、release candidate、实际 delivery hash 默认必须一致。
- WriterBlocker 增加 missing required cell/surface claim/citation/numeric、pack version conflict、claim boundary ambiguity、WWC missing 和 artifact projection conflict，并记录 partial draft 可保留范围。
- WhatWouldChangePanel 增加 condition、metric/operator/threshold、current value/as-of、last/next check、owner 和跨格式 version parity。
- visual constraints 增加 dual-axis、time-window、sorting、color semantics 和 legend。
- 人工 edit 细分 presentation language、translation/semantic paraphrase、material claim wording、research truth 和 source correction。
- TECH_08 增加 PresentationTask/WriterResultEnvelope/VerificationTask/ResultEnvelope；TECH_06 增加 presentation pipeline WorkUnits/ReleaseTransaction；TECH_07 增加 Presentation/Verification/HumanReview ContextRequirement。
- TECH_10 固定 material claim trace、cross-artifact consistency、stale leakage、numeric fidelity、disclosure leakage、edit routing、release escape 和 WWC parity 指标及分层规则。

修改文件：TECH_06、TECH_07、TECH_08、TECH_09、TECH_10 和 119 工作记录。

边界：仅更新 contract/eval/worklog；未实现 staleness engine、release transaction、hash gate、typed handoff、presentation context、metrics runner、renderer 或 Workbench UI，状态仍为 `documented / contract_draft`。

## 2026-07-11 追加：TECH_10 Quality and Learning Control Plane 重写

用户确认根据 TECH_10 点评重写技术合同。本轮不再继续按 TECH_01-09 模块逐节堆叠 eval 名称，而是建立统一、版本化、可复现、可归因、可阻断 runtime/config 错误发布的质量控制系统；原 social/domain/context/parallel/presentation eval 要求保留为 Module Eval Requirement Matrix。

本轮固定：

- TECH_10 是 Quality Evaluation / Failure Attribution / Runtime Release / Governed Improvement 合同；TECH_09 仍负责单份 artifact release，R60 仍负责 Eval Store/runner/observability/incident/fallback/release-readiness 实现。
- 新对象链：EvalProgram -> EvalDatasetVersion -> EvalCase -> EvalRunManifest/Run -> EvalSubject -> EvaluatorRun/EvalMetricResult -> QualityCard/FailureAttribution -> RuntimeReleaseGateDecision -> RegressionCase/ImprovementProposal。
- TECH_06 RunEvent Ledger 保存 eval execution facts；TECH_10 Quality Ledger 保存 evaluation facts。EvalMetricResult 不在同一 EvalRun 内覆盖；evaluator/input contract 变化创建新 run，坏结果进入 invalidated。
- EvalSubject 统一 tool/evidence/work-unit/trajectory/cell/pack/context/artifact/release/workflow/operations envelope，但 rubric 按 subject 分开。
- 注册 deterministic fixture、frozen replay、snapshot retrieval、live tool、model node、manual dogfood、shadow online、runtime release gate 模式，并声明 proof boundary 和 replayability level。
- Gold 是 required cells、frozen evidence/numeric、acceptable judgment range、counterevidence/gap/WWC、forbidden claim/action、repair/stop 和 artifact contract，不是标准 memo。
- Oracle 改为 `OracleRoutingPolicy`，按 subject/metric dimension 并行路由 deterministic/provenance/domain/human/LLM/abstain；不是串行层级。
- LLM Judge 自身进入 calibration eval，记录 prompt/rubric/input mapping/order/blinding/model/cost，并评 false accept/reject、稳定性、self preference 和 sector/language slices。
- `EvalMetricDefinition` 与 `EvalGatePolicy/EvalThresholdProfile` 分离，同一 eval metric 可按 L0-L4/task/slice 设不同 gate；并与 TECH_04 财务 `MetricDefinition` 分名；hard failure 不能被平均。
- QualityCard 分 Governance、Contract、Evidence/Numeric、Research、Delivery、Workflow/Product、Operational 七层。
- Trajectory 按 required checkpoints/invariants、allowed variants、forbidden transitions、repair/stop 和有效增量评，不复制 gold path。
- FailureAttributionGraph 使用受控 frozen counterfactual intervention，区分 confirmed/probable/contributing/correlated/unresolved，LLM 只提 root-cause hypothesis。
- 模型随机性进入 RepetitionPolicy，报告 pass@1、N-run、variance、worst slice、CI、flaky failure；禁止 rerun-until-pass 丢弃失败。
- Runtime release 必须同时满足 absolute threshold、candidate-vs-baseline non-regression、zero-tolerance hard gate 和 operational/security readiness；baseline 较差时“略有提升”不构成发布理由。
- Online traces 先经 privacy/permission/sampling/review 进入 candidate pool；不能自动 Gold、prompt/skill/memory/gate change。
- Human Eval Workbench 支持 blinded pairwise、role rubric、drilldown、confidence/disagreement/adjudication 和 reviewer calibration；human edit/rating 仍是 candidate label。
- Self-improvement 固定 failure -> cluster -> hypothesis -> fixture -> proposal -> sandbox -> human review -> staged rollout -> monitoring -> accept/rollback；不自动训练、合并、扩权、提权、改 disclosure/Gold/gate。
- 建立 R60 / legacy E0-E12 crosswalk，明确“已有 eval 资产”与“新 agentic runtime 已实际消费并通过”不是一回事。
- TECH_06 只承载 durable model/tool/replay/shadow eval，static/schema/unit CI evaluator 直接以 hashed envelope 回写 Quality Ledger；TECH_07 增加 Judge/Human Eval context；TECH_08 增加 EvaluatorAgent-as-Tool boundary。

修改文件：

- `TECH_00_agentic_research_technical_index.zh-CN.md`
- `TECH_06_durable_harness_runtime_permission_state.zh-CN.md`
- `TECH_07_context_engine_skills_compaction_governance.zh-CN.md`
- `TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`
- `TECH_10_trajectory_eval_self_improvement.zh-CN.md`
- `119_p37_tech_split_agentic_research_alignment.md`

边界：仅重写 technical/eval contract 和 worklog；未实现 Quality Ledger、EvalRunManifest、OracleRoutingPolicy、Metric/Gate registry、trajectory evaluator、counterfactual attribution、paired release gate、hidden holdout、Human Eval Workbench、online drift 或 staged self-improvement runtime。状态仍为 `documented / contract_draft`；未运行 paid LLM、full-chain、release eval 或生产发布。

## 2026-07-11 PRD / TECH / Runtime / Product Surface 全量覆盖审计

用户要求重新审视 PRD 与 TECH_01-10：既检查产品功能是否实际、可落地和充足，也建立 PRD -> TECH -> R52/R53/R55/R58/R59/R60 -> runtime -> product surface 覆盖矩阵。

本轮确认核心 Agentic Research 主链已经覆盖充分；主要缺口是产品级稳定对象和长期运行态没有完全进入 vNext owner graph，而不是检索、ReAct 或 specialist 数量不足。尤其：

- PRD 把 WorkpaperPack 定义为核心对象，旧 R52 也有较完整 WorkpaperEvent/Pack 设计，但 TECH_00 stable graph 曾跳过 Workpaper；
- TECH_05 只有 cell-level adjudication，缺 pack-level DecisionSurfaceAssembly、LeadReview 和 WriterAdmission；
- GapLedger、typed/commercial gap、RepairTicket 和 GapHistoryEntry 没有统一 GapRecord 生命周期；
- PRD 有五类 task mode，但没有 TaskModeRouter；
- R58/R59 有 Data Room parser/API 局部设计，但缺 upload/security/quarantine/reprocess/delete 的 vNext intake contract；
- valuation/price-in 缺 deterministic Forecast/Scenario/Valuation objects；
- 代码已有 agent_registry/llm_gateway，但缺 AgentDefinition/PromptBundle/ModelCapability/Selection 的统一版本合同；
- AIE 指标已在 PRD/代码出现，但缺统一 InformationEconomyLedger 和 TECH_10 metric ownership；
- Watchlist 拥有跨任务长期状态、cursor、incremental observation、alert/no-alert、dedupe/suppression、digest/notification，符合新增独立 TECH 的标准。

完成修改：

- 新增 `TECH_00A_prd_tech_runtime_product_surface_coverage_matrix.zh-CN.md`，逐项标记 `covered_contract / legacy_planned / runtime_partial / product_partial / owner_gap / new_contract_required`；
- 修订 TECH_00 stable object graph、owner matrix、R-series supersession 和新增 TECH 标准；
- 新增 `TECH_11_watchlist_monitoring_alert_runtime.zh-CN.md`。该文件不是重复拆 Agentic Search/Research，而是拥有持续监控运行态；
- TECH_01 新增 TaskModeDecision、GapRecord、WorkpaperPack、DecisionSurfaceAssembly、LeadReviewDecision 和 WriterAdmissionDecision；
- TECH_03 新增 Data Room intake/document governance 与 OntologyVersion；
- TECH_05 新增 deterministic valuation/forecast/scenario engine；
- TECH_06/08 新增 Agent/Prompt/Model registry owner 分工；
- TECH_09 固定 Workpaper projection，并把单一 CanonicalPresentationModel 修正为 shared canonical claims + audience-scoped presentation model；
- TECH_10 新增 InformationEconomyLedger 与 PRD AIE metric registry；
- PRD 新增可落地性/充分性审计、bounded product claims、缺失闭环和产品范围判断。

产品结论：功能广度已经足够，不应继续横向堆 agent persona 或 connector。公开源 deep research、常见 Data Room、可审 Workpaper、bounded monitoring、assisted quant 和 human-gated deliverable 都可落地；全行业同深度、全市场低延迟实时监控、代表性社交舆情、无人工 client-ready、无商业源的完整 consensus/flow/CDS 和自动投资建议均不得成为默认产品承诺。

边界：本轮只更新产品/技术合同和覆盖矩阵；没有实现新 schema/API/DB/runtime/UI，没有运行 paid LLM、full-chain、source ingestion、parser、eval 或产品 E2E。所有新增能力仍为 `documented / contract_draft`，P36 runtime blockers 未关闭。
