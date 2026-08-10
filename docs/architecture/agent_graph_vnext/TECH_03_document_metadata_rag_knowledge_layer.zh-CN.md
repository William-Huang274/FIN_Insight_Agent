# TECH_03：DocumentMetadataIndex / RAG / Knowledge Layer

日期：2026-07-09

状态：技术合同草案。本文定义 agentic 架构下 RAG / 知识库的角色：它是 evidence pipeline 组件，不是最终回答引擎。

## 0. 2026-07-10 准确定义与硬边界

TECH_03 是 FinSight-Agent 的证据地址层与研究记忆层。它负责将原始 source、文档版本、结构元素、chunk、table、graph pointer、历史 accepted evidence、review decision 和 repair cache 组织成可寻址、可版本化、可召回、可扩展上下文、可 freshness 检查的候选资料系统；它只向 TECH_02 输出 `CandidateBundle`，不直接做 evidence promotion、numeric audit、业务判断或写作。

硬边界：

- `TECH_03 returns candidates, not evidence.`
- `Chunk is a retrieval unit, not an evidence unit.`
- `Memory is a prior, not a substitute for current evidence.`
- `Metadata filtering precedes reranking.`
- `Tables are first-class objects, not text chunks.`
- `Repair cache records search history, not final truth.`
- `Freshness and revision checks are mandatory before reuse.`

这些边界必须向下约束 TECH_02 / TECH_04 / TECH_05：RAG hit、历史 memo、graph pointer、新闻线索、repair cache 命中，都不能绕过 Evidence Gate / NumericProgramTrace / domain cell projection。

## 1. 要解决的问题

P36 暴露的核心是“召回强，精度和提权弱”。因此：

- RAG hit 只能是 candidate；
- metadata 必须先进入 filter，再进入 reranker；
- 方法库不能被引用为事实；
- accepted research memory 必须保留 as-of、source revision 和 review status；
- repair cache 不能绕过本次 source freshness / authority 检查。

## 2. 知识库分层

| 层 | 内容 | 用途 | 边界 |
| --- | --- | --- | --- |
| Raw Source Library | filings、issuer IR、PDF、网页 snapshot、用户上传材料、market raw pull | SourceHunter / parser / reviewer 追原文 | 只有 source，不等于 evidence |
| Parsed Evidence Store | chunks、table candidates、exact rows、parser lineage、page/section/cell refs | Evidence Layer 做 row selection、sanity、promotion | 未过 gate 不能给 Writer |
| Accepted Research Memory | accepted evidence、DecisionSurfacePack、NumericProgramTrace、WorkpaperPack、review decisions | Lead 追问、复用判断、artifact consistency | 必须保留 as-of / revision / review status |
| Method / Playbook KB | 行业框架、估值方法、风险清单、output rubric | Lead / specialist planning | 只能作为方法，不能作为事实证据 |
| User / Institutional Context | 用户偏好、coverage universe、house style、历史反馈 | 调整工作流和表达 | 必须与事实证据隔离 |

## 3. DocumentMetadataIndex

必须进入 retrieval filter 的字段：

- `company`
- `ticker`
- `period`
- `doc_type`
- `source_authority`
- `source_role`
- `section`
- `table_lineage`
- `page`
- `as_of`
- `revision`
- `parser_status`
- `promotion_status`

不能只把这些字段作为 reranker feature。若 metadata filter 不能把错误公司、错误期间、错误 doc type 排除，reranker 分数没有意义。

## 4. RAG / KB 的角色

| 角色 | 作用 | 不能做什么 |
| --- | --- | --- |
| Candidate Generator | 召回 chunk、table、filing、news、history、graph node | 直接当事实 |
| Source Index | 告诉系统哪里可能有 source | 替代 official source / parser lineage |
| Metadata Filter | 先按 company/period/source/section/table lineage 过滤 | 只做 rerank feature |
| Artifact Router | 找历史 memo/PPT/Excel/dashboard 复用或审一致性 | 跳过 ArtifactConsistencyGraph |
| Institutional Memory | 保存 house view、review decisions、prior gaps | 作为当前事实引用 |
| Repair Cache | 记录过去 gap 怎么补、哪些 query/source/parser 失败过 | 绕过本次 freshness / authority |
| Context Router | 给 Lead / specialist 取最小上下文 | 污染 writer brief |
| Coverage Auditor | 发现长期缺 source/parser/commercial data 的 cells | 把缺口包装成结论 |

## 5. I/O 合同

输入：

- `EvidenceRequest`
- metadata filter constraints
- query intent
- source authority policy

输出：

- `RagCandidate`
- `TableCandidate`
- `GraphCandidate`
- `SourceCandidate`
- `ExternalSignalCandidate`
- `ArtifactCandidate`
- `RepairCacheHit`
- `CoverageGap`
- `CandidateBundle`

所有输出必须带：

- `knowledge_layer_type`
- `source_metadata`
- `as_of`
- `revision`
- `promotion_status`
- `authority_boundary`

## 6. 与其他 TECH 的边界

- `TECH_02` 调用 RAG / KB 作为 agentic search 工具；
- `TECH_04` 负责 parser / numeric promotion；
- `TECH_07` 负责 ContextEngine 如何注入 institutional / role context；
- `TECH_09` 负责 citation clickthrough 和 ArtifactConsistencyGraph；
- `TECH_10` 评估 context pollution、metadata precision 和 accepted-evidence conversion。

## 7. 第一批 fixture

1. Metadata filter fixture：错误 ticker / period / doc_type 必须被过滤。
2. RAG hit -> Evidence Gate conversion fixture。
3. Method KB 防事实引用 fixture。
4. Repair cache reuse fixture：可建议 route，但不能直接 accepted。
5. Accepted Research Memory follow-up fixture：Lead 能回答“为什么这么判断、哪里没证据、下一步查什么”。

## 8. 验收指标

- decision-cell candidate recall；
- metadata-filtered precision；
- RAG hit 到 accepted evidence conversion rate；
- rejected candidate explanation coverage；
- exact authority violation rate；
- citation clickthrough success rate；
- repair cache reuse rate；
- context pollution rate。

## 9. 2026-07-10 暂定修改方向：ChunkProfileRegistry / table-aware knowledge layer

本节是审计前的暂定方向，不表示现有知识库需要立刻全量重切，也不表示新解析工具已进入 runtime 主路径。

当前判断：

- SEC 主线 chunk 工程基本可用，既有 S0 审计证明年报 / 季报主线召回不是从零开始。
- 现有 `900 words / 150 overlap / min 80` 和 8-K `650 words / 100 overlap / min 40` 对 SEC 长文本 BM25 baseline 仍有价值。
- 但 table-aware extraction、unit / scale normalization、row selector、non-US / IR PDF / press table 尚未达到 `TECH_02` / `TECH_04` 要求的 Evidence Gate 级别。
- 固定长度切片不应继续作为唯一策略。vNext 应把它降级为 baseline / fallback，并新增 dynamic / structure-aware / table-object profile。

建议新增一等对象：

```text
TextChunkProfileRegistry
  -> source_type profile
  -> element_type profile
  -> retrieval profile
  -> numeric/table profile
```

第一版 profile 暂定：

| Source / Element | 暂定 profile | 边界 |
| --- | --- | --- |
| SEC narrative / MD&A / Risk Factors | 保留现有 900 words / 150 overlap 作为 BM25 baseline；新增 token-based profile，约 700-900 tokens、20-30% overlap | 用于 narrative recall，不直接支撑 exact numeric promotion |
| 8-K earnings release | 继续短于年报，约 500-700 tokens；保留 earnings section / guidance section 的 parent context | 财报表格和 guidance table 不靠普通 chunk 提权 |
| 表格 | 抽成 `TableObject`、`TableRowObject`、`TableCellObject` | 必须保留 header、unit、period、footnote、row / column lineage |
| IR PDF / 非美年报 / press release PDF | 使用 layout-aware parser profile，优先保留 heading、page、table、footnote | 不走纯文本固定长度切片作为唯一入口 |
| 产品规格 / 技术页面 | 小 chunk，约 300-600 tokens，按 heading / list / spec table 切 | 规格表仍需结构化 element / table context |
| 新闻 / 普通网页 | 按 heading / paragraph / article section 切，保留 publication metadata | 通常只能 `context_only`，除非 source authority 达标 |

## 10. Chunk / table / numeric 风险清单

现有固定切片对 SEC 主线不是错，但对以下问题不够：

- table header / footnote 被切断；
- embedding 可能被长 chunk 稀释，导致 dense retrieval 命中正确文档但错过关键句；
- dense retrieval 找到 chunk 但缺 neighbor / parent section / table context；
- 表格数字没有 row / column / unit / scale lineage；
- `usd_thousands`、`usd_millions`、百分比、delta、per-share、share-count 等被误当 headline number；
- table body 被召回但 header、period、unit 或 footnote 不在同一 chunk；
- non-US / IR PDF / press table 的 layout 信息丢失；
- 产品规格网页中的 list / spec table 被纯文本化后失去字段绑定。

因此 retrieval 层应采用 child-parent 策略：

- child chunks 用于召回；
- parent section / parent document / table context 用于 Evidence Gate；
- table object / numeric trace 用于 exact-value promotion；
- writer 不能直接引用普通 chunk 里的数字。

## 11. 现有 runtime 审计前置条件

具体如何落地要先做一次现有 runtime 对应环节审计。审计前，不启动 blind full reingestion，不替换默认 parser，不把新工具 PoC 结果写成 accepted runtime evidence。

审计对象：

- chunk profile：按 source_type / doc_type / element_type 统计 chunk size、overlap、chunk count、parent section coverage、neighbor linkage；
- retrieval：按 decision cell / evidence slot 测 candidate recall、metadata-filtered precision、rerank precision、neighbor recovery、source diversity；
- table extraction：统计 table marker 平衡、table length、header / unit / period / footnote presence、row / column lineage；
- SQL / runtime rows：核查 entity、ticker、period、unit、scale、currency、row label、statement type、segment binding；
- numeric sanity：重点检查 millions / thousands / percentage / delta / per-share / share-count / negative values / restatement；
- row selector：检查 false positive 和 forbidden substitutions，例如 total revenue 代替业务线收入、inventory / bank account 误当产品 KPI；
- source family：分别审 SEC filing、issuer IR PDF、non-US annual report、press release PDF、product page、news、market data；
- Evidence Gate：统计 candidate -> accepted / context_only / rejected / typed_gap / commercial_gap 的转化和拒绝原因。

审计输出应至少包括：

- `chunk_profile_audit_summary`
- `retrieval_precision_by_slot`
- `table_extraction_quality_summary`
- `numeric_scale_unit_audit`
- `row_selector_false_positive_report`
- `source_family_parser_gap_matrix`
- `evidence_gate_conversion_report`

只有在这些审计显示 v2 profile 能改善 retrieval precision、neighbor recovery、table lineage、unit / scale sanity 和 Evidence Gate promotion rate 后，才按 source family 分批迁移。

## 12. Core Object Model

TECH_03 必须把对象分层建模，不能把所有内容混成一个 `DocumentChunk` 表。

### 12.1 Source Layer

- `SourceDocument`：原始 source 的逻辑身份，例如 SEC filing、issuer IR PDF、official product page、government policy page、news article、market data snapshot。
- `DocumentRevision`：同一 source 的版本、发布日期、抓取时间、修订状态、restatement / amendment 关系。
- `SourceSnapshot`：可回放的本地或 API snapshot，包括 URL、checksum、fetch attempt、storage status、as-of。
- `SourceLicensePolicy`：访问方式、许可、robots / ToS / credential / commercial boundary / redistribution boundary。

### 12.2 Structure Layer

- `DocumentElement`：section、heading、paragraph、list、table、figure、footnote 等结构元素的统一父类。
- `ChunkObject`：用于 retrieval 的 text unit，必须保留 `parent_section_id`、`prev_chunk_id`、`next_chunk_id`、boundary、token/word span。
- `TableObject`：表格整体，保留 table title、header tree、page/section、footnote、unit、period。
- `TableRowObject`：表格行，保留 row label、statement type、segment、period binding、source row span。
- `TableCellObject`：单元格，保留 value、unit、scale、currency、period、column header、row header。
- `FigureObject`：图表/图片对象，默认 `context_only`，只有结构化解析和来源足够时才能进入候选。
- `FootnoteObject`：脚注、表注、单位说明、non-GAAP reconciliation 注释。

### 12.3 Candidate Layer

- `RagCandidate`：文本召回候选。
- `TableCandidate`：表格/行/单元格候选。
- `GraphCandidate`：ProductIntelligenceGraph、ProductRelationshipGraph、ResearchGraphStore、capital feedback graph 等 graph pointer 候选。
- `SourceCandidate`：需要 SourceHunter / fetch / parser 进一步处理的 source 候选。
- `ExternalSignalCandidate`：新闻、公开发言、政策、地缘政治、行业事件等外源信号候选。
- `CandidateBundle`：TECH_03 返回给 TECH_02 的唯一主对象，包含候选、metadata、lineage、source authority、freshness、repair history 和 expansion options。

### 12.4 Memory Layer

- `AcceptedMemoryEntry`：被 Evidence Gate 或 reviewer 接受过的事实/判断/pack 记忆的通用父对象。
- `AcceptedFactMemory`：已接受事实证据，复用前必须做 freshness / revision / source authority 检查。
- `AcceptedJudgmentMemory`：历史判断或 house view，只能作为 prior，不能替代当前 evidence。
- `ReviewerDecisionMemory`：accept / reject / supersede / needs_source / needs_parser 等 review action。
- `DecisionSurfacePackMemory`：历史 decision surface pack，用于追问、对比和 artifact consistency，不直接替代新任务证据。

### 12.5 Repair Layer

- `RepairCacheHit`：历史 query、source route、parser、tool fallback 成功/失败记录。
- `GapHistoryEntry`：长期缺口，如 parser gap、commercial gap、source unavailable、permission denied。
- `CoverageAuditRecord`：按 company / sector / decision cell / source family 记录覆盖、缺口和 stale 状态。

## 13. CandidateBundle Contract

`CandidateBundle` 是 TECH_03 给 TECH_02 的主输出。它必须避免让上游 caller 误把候选当证据。

必备字段：

- `bundle_id`
- `evidence_request_id`
- `decision_surface_id`
- `cell_id`
- `evidence_slot_id`
- `metadata_filter_applied`
- `source_policy`
- `freshness_policy`
- `rag_candidates`
- `table_candidates`
- `graph_candidates`
- `source_candidates`
- `external_signal_candidates`
- `artifact_candidates`
- `repair_cache_hits`
- `coverage_gap_refs`
- `neighbor_expansion_options`
- `table_context_options`
- `authority_boundary_summary`
- `cannot_support`

返回规则：

- 候选必须带 `candidate_status=candidate_only`，除非它引用的是已经接受过且 freshness check 通过的 `AcceptedFactMemory`。
- `CandidateBundle` 不包含 writer-ready text。
- `CandidateBundle` 不包含 final claim。
- `CandidateBundle` 可以建议 `NeighborChunkRequest`、`SectionExpansionRequest`、`TableContextRequest`、`SourceHunterRequest`，但不执行 promotion。

## 14. External Signal / News / Public Statement Layer

WorkBuddy-style deep research 常需要新闻、公开人物发言、政策事件、地缘政治冲突、行业事件和监管变化。TECH_03 必须把这类外源建模成候选，而不是让 specialist 或 writer 私下搜索。

新增对象：

- `NewsArticleSnapshot`：新闻正文、媒体、发布日期、作者、URL、snapshot、引用对象。
- `PublicStatementObject`：管理层、政府官员、行业协会、客户/供应商高管的公开发言。必须记录 speaker、affiliation、event、date、原始出处和是否官方渠道。
- `PolicyEventObject`：法律、监管、出口管制、制裁、政府补贴、招标政策等事件，优先绑定官方政府/监管 source。
- `GeoRiskEventObject`：地缘政治、贸易摩擦、战争/制裁/关税等 risk context。
- `EventCluster`：多篇报道或多份 source 指向同一事件时的去重聚合对象。
- `ExternalSignalCandidate`：上述对象进入 TECH_02 的候选包装。

Authority 边界：

- 公司官方博客、earnings call transcript、SEC filing、issuer presentation 中的管理层发言可作为 `company_authored_context` 候选。
- 政府/监管官网中的政策文本可作为 `official_policy_context` 候选。
- 新闻报道默认是 `event_lead` 或 `context_only`，不能直接支撑公司 exact fact。
- 媒体转述的黄仁勋或其他高管发言，必须回找 NVIDIA 官方材料、会议 transcript、SEC filing 或原始视频/文字记录；否则只能作为 `public_statement_lead`。
- 中美冲突、出口管制等，应优先找 BIS / Commerce / official government source；新闻只可做 discovery、market narrative 或 counter-thesis context。

允许支持：

- catalyst / what-changed；
- risk / counter-thesis；
- market narrative；
- policy exposure；
- event timeline；
- source discovery。

禁止支持：

- company-reported revenue / margin / order / backlog exact fact；
- verified customer / supplier relationship；
- product sales、market share、sell-through、channel inventory；
- management statement fact without primary source confirmation。

## 15. Data Foundation Source Map

vNext TECH_03 必须把现有数据基座纳入 source map，但不得把旧 R53/P14/S3 的 L4 closeout 误写成 vNext DecisionSurface runtime 已完成。

当前已存在或已登记的 source families 包括：

| Source group | 代表 sources / artifacts | 当前用途 | 边界 |
| --- | --- | --- | --- |
| SEC / US issuer disclosure | SEC EDGAR APIs、CompanyFacts、SEC financial statement datasets、SEC 8-K、SEC ownership / 13F | US issuer filing facts、structured facts、ownership / capital context | 仍需 parser / period / unit / citation gate；13F lagged |
| Company-authored material | Company IR reports、earnings releases、presentations、official product pages、company-reported product operating metrics | company-authored context、official product/spec、company-disclosed operating metric | IR/PDF/parser 对 non-US 与产品 metric 仍有 gap |
| Non-US public disclosure | KR DART、JP EDINET、TW MOPS、HKEXnews、CNINFO | non-US primary disclosure route | 多数仍是 auth / portal / parser validation gap |
| Market / capital | secondary market public context、Yahoo provisional chart、13F/ownership、capital events、OpenFIGI、GLEIF | price reaction、lagged ownership、capital structure、entity mapping | 不替代 commercial real-time market data、consensus、dealer positioning |
| Macro / industry | FRED、BLS、BEA、Census、EIA、FDIC、USITC / trade | macro / industry / demand proxy context | 不能推成 company-level revenue / margin / product adoption |
| Product / regulatory vertical | NHTSA、ClinicalTrials、openFDA、CMS | product identity、regulatory、healthcare/auto/utility context | 不证明 commercial uptake or product sales |
| Public web proxy | channel offer、app marketplace、careers / hiring、public contract / tender、developer ecosystem、official API exposure、product catalog / spec | bounded thesis driver、source lead、product / demand proxy | 不能推成 ASP、inventory、sell-through、sales、share |
| Technology / IP | OpenAlex、PatentsView | technology and research signal | 不证明 launch、sales、revenue、durable moat |
| News / discovery | GDELT、Common Crawl、Wikidata、trusted external family / industry association reports | event lead、source discovery、industry context | 默认 lead/context only，需要 primary source 验证 |
| Graph stores | ProductIntelligenceGraph、ProductRelationshipGraph、ResearchGraphStore、capital feedback graph | graph pointer、relationship/context candidate、decision-cell projection input | graph edge 不等于 exact fact；需要 TECH_05 投影和 Evidence Gate |

参考现有 manifests：

- `r18_source_route_registry_v2_summary.json`：记录 7,181 条 source-route / signal rows，其中 2,925 条 `exact_company_fact_authority`，4,256 条 `bounded_thesis_driver_authority`。
- `raw_source_provenance_summary_v0_1.json`：记录 27,720 个 source snapshots、71,004 条 runtime lineage rows。
- `retrieval_index_registry_summary_v0_1.json`：记录 22 个 index snapshots 和 retrieval source lineage；policy 明确 retrieval 只是 recall layer。
- `research_graph_summary_v0_1.json`：记录 100,145 条 graph edges 和 113,199 条 evidence support rows。
- `product_intelligence_graph_summary_v0_1.json`：记录 71,034 条 product-intelligence edges 和 603 个 company packs。

TECH_03 的工作是把这些 source / index / graph / memory 资产整理成 `CandidateBundle`，而不是直接宣称它们已经能支持 P36 five-chain report。

## 16. Method / Workpaper / Research Graph Memory Boundary

研报方法、底稿样例和研究知识图谱必须进入 TECH_03 的 memory/address layer，但必须保持事实证据隔离。

对象建议：

- `MethodMemory`：来自 `financial_research_method_registry.jsonl` 的 thesis path、product-to-financial bridge、peer panel、secondary-market feedback、customer-supplier readthrough 等方法。
- `WorkpaperExemplarMemory`：P33 humanmade gold case、research ruler、answer exemplar、rubric / negative cases。
- `ResearchGraphPointer`：ResearchGraphStore / ProductIntelligenceGraph / ProductRelationshipGraph 中可被 TECH_05 投影的 graph node / edge / support pointer。
- `SkillMemoryRef`：Research Lead、Memo Writer、Fundamental、Product、Industry、Market、Risk 等 prompt skill 的版本引用。

边界：

- `MethodMemory` 只能作为 planning prior，不能作为事实证据。
- `WorkpaperExemplarMemory` 只能作为 answer-shape / depth rubric / reviewer expectation，不能直接填充新 case 的事实。
- `ResearchGraphPointer` 只说明有图谱路径或 evidence support pointer，不能跳过 source authority / Evidence Gate。
- `SkillMemoryRef` 由 TECH_07 注入上下文，TECH_03 只保存可寻址引用和版本。

后续 TECH_05 必须把这些 memory 转成 domain operator 的 cell-level 输出；否则项目会停留在“有方法、有 skill、有图谱，但不会形成判断”的状态。

## 17. 2026-07-10 公开资本市场补源与 PIT 数据基座

P36 Node07 证明当前项目已有 603-company market snapshot、部分 valuation-enriched rows、13F / ownership / capital rows 和 capital-feedback fixture，但这些资产主要是当前或短窗口 snapshot，不能直接支持稳定的历史估值、显著性检验、完整 crowding 或长期因子验证。TECH_03 的补源目标不是继续堆同一时点字段，而是完成三次数据形态升级：

```text
current snapshot -> point-in-time historical panel
single price view -> market / ownership / credit / derivatives / event joint panel
US-centric route -> non-US official exchange / regulator / issuer routes
```

### 17.1 新增一等数据对象

- `SecurityMasterPIT`：issuer、security、ticker、CIK、ISIN、FIGI、share class、ADR、exchange、currency、listing/delisting、rename、merger、historical sector / peer membership。
- `CorporateActionRecord`：split、dividend、rights、spin-off、merger、ticker change、suspension、delisting，保留 effective / announced / available time。
- `MarketBarPIT`：raw / adjusted OHLCV、trading calendar、timezone、currency、halt、zero-volume、provider/source/license、as-of 和 ingestion vintage。
- `OwnershipPositionPIT`：13F、N-PORT、13D/G、Form 3/4/5、ETF official holdings，保留 report date、filed/available time、holder/security mapping 和 lag policy。
- `ShortLiquidityPIT`：short interest、short-sale volume、turnover、public float、abnormal volume、exchange/venue coverage；short-sale volume 与 short interest 必须分离。
- `CreditMarketPIT`：company debt instrument、TRACE trade/yield context、maturity、coupon、liquidity、rating/public spread context；交易价格不能伪装成完整 issuer curve 或 CDS。
- `DerivativesPublicContextPIT`：OCC daily open interest / volume、CFTC COT、public futures/options regime rows；无 quotes / dealer side 时不得推导 dealer gamma。
- `MacroVintagePIT`：FRED / ALFRED real-time periods、release/vintage/revision time，避免用修订后宏观值回测历史。
- `IssuerGuidanceEventPIT`：guidance、8-K、earnings release、investor day、product/policy/regulatory event 的 announced / filed / available / tradable-after 时间。
- `NonUSOfficialMarketPIT`：TWSE/MOPS、OpenDART/KRX、HKEX、EDINET、Euronext/当地监管与 issuer IR 的官方行情、财务、持仓、short / lending、corporate action 地址层。

### 17.2 公开源补充地图

| Source family | 目标数据 | 可支持 | 必须保留的边界 |
| --- | --- | --- | --- |
| SEC DERA / EDGAR | Financial Statement/Notes、13F、N-PORT、Insider Transactions、13D/G、filing accepted time | PIT fundamentals、lagged ownership、fund/insider behavior、capital events | filing lag、amendment、security mapping、13F/N-PORT 非实时 |
| FINRA | short interest、short-sale volume、TRACE public bond trades / EOD context | short pressure proxy、bond yield/liquidity、equity-credit divergence | short volume 不等于 short interest；TRACE 批量/商业使用受协议和费用约束 |
| OCC / CFTC / exchanges | daily option OI/volume、COT、delayed futures/options context | put/call、OI concentration、commodity/rate/FX positioning regime | 不等于 dealer positioning、real-time OPRA、borrow 或单股完整 IV surface |
| FRED / ALFRED / Treasury / official macro agencies | rates、credit regime、VIX、commodities、macro vintages | vintage-safe macro/regime feature | broad regime 不能推成 company exact fact |
| TWSE/MOPS、OpenDART/KRX、HKEX、EDINET 等 | non-US official market/disclosure/holder/short/corporate action | TSMC、SK hynix、Samsung、ASML 等本地资本市场与披露深度 | portal/auth/license/parser/locale/calendar 需 source-specific adapter |
| Issuer IR / official ETF holdings | guidance、events、daily fund holdings、buyback/issuance/debt actions | guidance revision、event study、lagged positioning | issuer authored，不等于 consensus 或完整 fund flow |

`OpenBB`、Yahoo、Stooq 等可以继续作为聚合、发现或 provisional market context，但不能取代 source authority、license policy、corporate-action audit 和 PIT lineage。公开可访问也不等于可批量再分发；`SourceLicensePolicy` 必须记录 personal/non-commercial/commercial、bulk download、redistribution、retention 和 citation 条件。

### 17.3 深度优先级

公开资本市场补源的优先顺序固定为：

1. 至少多年历史的可复权日线、corporate actions、交易日历与 historical universe / delisting。
2. filing accepted / available time、amendment / restatement vintage 和 PIT fundamentals。
3. 13F / N-PORT / insider / 13D-G 的历史变化与 security-holder mapping。
4. ALFRED macro vintage、issuer guidance/event timeline。
5. non-US official exchange / regulator / issuer source adapters。
6. FINRA short/TRACE、OCC/CFTC 等资本反馈深度。

这是一项 `documented / contract_draft` 方向，不代表上述数据已经进入 vNext runtime。后续必须分别通过 source reachability、license、history completeness、corporate-action adjustment、PIT timestamp、security mapping、missingness 和 revision audit，才能进入 TECH_04 derived feature 或 R53 factor validation。

## 18. 2026-07-10 Futures / Options / Other Derivatives Data Policy

衍生品数据应成为 TECH_03 的一等 PIT 数据对象，但不应成为所有研究任务默认注入的 payload。它的产品角色是基本面研究的 expectation、tail-risk、positioning、cost/transmission 和 macro-regime sensor，而不是独立交易终端。

### 18.1 三层采用策略

| Tier | 范围 | Runtime policy |
| --- | --- | --- |
| `tier_a_regime_core` | equity-index futures/options、VIX、rates futures/swaps aggregate、commodity futures、FX futures/proxy、CFTC COT | 形成小型 global regime pack；按 sector exposure 选择，不注入原始全量合约 |
| `tier_b_cell_activated` | single-stock options、issuer convertibles/warrants、issuer bond/credit context、sector ETF options | 只有 event/price-in/tail-risk/funding/crowding cell 明确需要时激活 |
| `tier_c_investigative_or_commercial` | real-time OPRA、full IV surface、dealer inventory/gamma、borrow/securities lending、single-name CDS/SBS、TRS/complex OTC/exotics | investigation-only 或 licensed commercial route；无源时保持 commercial gap |

### 18.2 核心对象

- `DerivativeInstrumentMaster`：exchange、asset class、underlying security/commodity/rate/index、contract symbol、expiry、strike、call/put、multiplier、tick size、currency、exercise/settlement style、first notice、last trade、adjusted-contract flag、source/license。
- `DerivativeObservationPIT`：trade/settlement date、observation/available time、preliminary/final status、OHLC/settlement、bid/ask/last、volume、open interest、implied volatility where sourced、contract metadata refs、provider delay。
- `FuturesCurveSnapshotPIT`：front/second/third/deferred contracts、curve nodes、roll calendar、continuous-contract policy、basis benchmark。
- `COTPositionPIT`：report date、release/available time、commercial/dealer/asset-manager/leveraged/managed-money/nonreportable categories、long/short/spread、OI share、classification version。
- `PublicSwapRegimePIT`：CFTC weekly swaps aggregate、rates/credit/FX/cross-currency asset class、notional/volume/ticket count、cleared status、maturity/currency/participant category。
- `IssuerDerivativeCapitalContext`：convertible、warrant、hedging derivative、issuer bond/credit/SBS investigative rows，绑定 filing/source/underlying/entity。

### 18.3 Source policy

- CME / ICE / exchange settlement、volume、OI 和 contract specification 是 futures 主候选；preliminary 与 final 必须分版本，reference-only web data 不能伪装成 licensed real-time feed。
- CFTC COT / Weekly Swaps Report 适合 weekly positioning/regime，必须使用 release time，不能按 report date 提前可得。
- OCC daily contract volume / OI 可支持 delayed single-stock/index option context；没有 quotes/side/participant identity 时不能推 dealer positioning。
- SEC security-based swap public dissemination 和 registered SDR public data可用于 investigation，但 capped notional、lifecycle event、anonymous counterparty、underlying mapping 和 corrections 必须先通过 parser/audit。
- TRACE bond、issuer filing、convertible/warrant terms 优先支持 issuer funding / dilution / equity-credit divergence；CDS 不是普通任务的默认替代。

### 18.4 Sector / cell activation

- energy/materials/transport：commodity curve、roll、COT、FX 优先；
- banks/insurance/REIT：rates curve、SOFR/Treasury futures、swap/credit regime 优先；
- semis/software/growth：rates、USD/local FX、NASDAQ/index volatility；single-stock options 只在 event/price-in cell 激活；
- healthcare/biotech：clinical/FDA event options context 可按事件激活；
- consumer/industrials：FX、energy、agriculture/metals cost exposure 按 business model 激活。

TECH_01/Lead 使用 `DerivativesExposureMap` 把 sector/company/cell 映射到必要 instruments；TECH_03 返回 bounded candidate pack，不把全市场 options chain / futures universe 直接发送给 specialist。

### 18.5 当前边界

本节为 `documented / contract_draft`。现有 runtime 仅有 broad-market volatility regime 和 derivatives gaps 的 fixture 级材料；没有 DerivativeInstrumentMaster、single-stock option PIT、futures curve store、COT runtime pack、swap parser、licensed OPRA、dealer gamma 或 Workbench derivatives review closeout。

## 19. 2026-07-10 External Source Foundation / Social Discourse Objects

P35/P36 supervisor supplement 证明，报告质量增量主要来自 issuer IR / earnings / official PDF、官方产品与客户部署材料、政府监管文件，而不是无差别增加普通新闻。TECH_03 因此把外源组织为可寻址的 source families，不建设“大而全网页仓库”。

### 19.1 值得进入项目的 source families

| Source family | Storage / retrieval policy | Evidence role | Boundary |
| --- | --- | --- | --- |
| issuer / exchange / filing primary disclosure | persistent snapshot + structured/PDF parser | exact fact、guidance、company-authored context | parser / period / unit / revision gate |
| government / regulator / legal instrument | persistent index + official document snapshot | policy、regulatory、sanction、approval、recall、risk event | informational page 与正式法律文本需分级 |
| official market / macro / procurement | PIT structured foundation | market、ownership、macro、award/deployment signal | 采购不等于收入确认；macro 不等于 company fact |
| official product / customer / deployment / benchmark | on-demand snapshot + selective memory | technical fact、availability、deployment、ecosystem validation | 不等于销量、收入、share、profitability |
| industry association / standards body | selective index / on-demand | methodology、standard、industry context | 不能替代 issuer exact fact |
| issuer-authorized wire mirror / trusted media | fallback snapshot / event cluster | issuer fallback、event、narrative、counterevidence | 默认不替代 primary source；遵守转载/引用许可 |
| patent / research / developer ecosystem | structured lead / selective snapshot | technology trajectory、developer adoption proxy | 不证明 durable moat 或 commercialization |
| RSS / GDELT / Common Crawl / search | discovery index only | source discovery、event clustering | 不直接成为 accepted fact |
| commercial / client-licensed source | adapter registry，不复制未授权内容 | consensus、real-time、flow、supply-chain/channel tracker | license / entitlement / redistribution gate |

### 19.2 Social source object model

新增对象：

- `SocialAccountIdentity`：platform、immutable account/channel id、handle history、display name、account owner、organization/person/public-office role、verification type、official-domain crosslink、organization affiliation、identity confidence、validity interval。
- `SocialSourceSnapshot`：canonical URL、post/video/live ID、published/retrieved time、content hash、text/media/transcript、language、reply/quote/repost parent、edit/delete status、source license 和 capture method。
- `SocialStatementClaim`：speaker、claim text、claim type、scope、tense、attribution status、underlying fact verification status、supports / cannot-support。
- `SocialEngagementSnapshot`：as-of time、views/likes/replies/reposts 等平台可见 engagement；只记录当时 snapshot，不推断总体民意。
- `SocialDiscourseSample`：platform、query、time window、sampling method、sample size、language/geo coverage、dedupe、bot/spam filter、ranking bias、missingness、rate-limit / deletion notes、weighted/unweighted result。
- `UserFeedbackTheme`：从评论、回复和公开用户反馈提取的 theme、代表样本、反例、frequency within observed sample 和 uncertainty。
- `ClaimConflictRecord`：statement claim 与 accepted fact / policy / product observation 的冲突类型、证据 refs、resolution status、review owner 和 artifact wording boundary。

账号认证只能提高 identity provenance，不能提高 underlying claim truth。[X profile labels](https://help.x.com/en/rules-and-policies/profile-labels) 当前说明普通 blue check 与 Premium subscription 绑定，gold/grey/affiliation 提供不同组织/政府身份信号；[YouTube verification badge](https://support.google.com/youtube/answer/3046484) 可以帮助区分官方频道，但平台也明确 verification 不是 endorsement。由于平台规则会变化，`verification_type` 必须版本化，不能只保存 `verified=true`。

官方账号、公众人物、CEO、产品负责人和项目成员的发言可以进入 `PublicStatementObject` / `SocialStatementClaim`，但 authority 必须受 speaker role 和 claim scope 限制。评论区高赞内容可以进入低权重 `UserFeedbackTheme` 或 `sentiment_sample_only`；没有抽样和覆盖审计时，不能升级成 representative public sentiment。

### 19.3 Social source freshness / integrity

社交内容可能被编辑、删除、断章转发或账号被盗。TECH_03 必须保留 post ID、账号 ID、parent context、snapshot hash、capture time、edit/delete status 和 media/transcript timestamp。只保存模型摘要、搜索 snippet 或脱离上下文的截图不满足 provenance。

本节为 `documented / contract_draft`。项目当前没有统一 X/微博/微信公众号/YouTube adapter、SocialSourceSnapshot store、舆情采样框架或 ClaimConflict runtime；已有新闻/GDELT/公开网页资产不能视为该能力已实现。

## 20. 2026-07-11 Data Room Intake / Document Governance

Data Room 不能从“用户给了一个文件路径”直接跳到 CandidateBundle。新增 `DataRoom`、`UploadSession`、`DocumentManifest`、`DocumentACL`、`IngestionJob`、`SecurityScanDecision`、`QuarantineDecision`、`ParsePlan`、`ExtractionReview`、`ReprocessRequest`、`RetentionDecision` 和 `DeletionTombstone`。

标准链路为 upload/fetch -> manifest/hash/type detection -> permission/license/security scan -> quarantine or immutable source snapshot -> parser profile selection -> structure/table/figure/OCR objects -> extraction review -> index publication。宏、可执行附件、外部链接、嵌入对象和异常压缩包默认隔离；parser 输出不得继承用户文件的 source authority，而应保留 `user_provided` 与 public/official evidence 的身份差异。

删除、forget、retention 到期、ACL 变化和 source replacement 必须向 chunk/table/index/memory/citation/artifact 发出 invalidation，不能只删除上传列表记录。R58/R59 的 uploaded-artifact/parser/API 设计作为实现来源，但必须适配本文 source/structure/candidate objects 和 TECH_06 durable events。

## 21. 2026-07-11 Ontology / Identifier Governance

新增 `OntologyVersion`、`OntologyTerm`、`MappingDecision`、`MappingConflict` 和 `OntologyMigration`，覆盖 entity/security/instrument、metric/unit、segment/product、source role、sector/cell archetype。每个 parsed fact、table row、graph edge、derived metric 和 memory entry 都要绑定使用时的 ontology/mapping version；模型只能建议 mapping，不能静默修改 canonical identity。ontology 更新触发可定位的 reindex/recompute/review，不得把历史 artifact 原地改写。

## 22. 2026-07-12 Institutional Memory Registry / PIT Reconstruction

根据 TECH_00/02，TECH_03 拥有 memory address、namespace、freshness、TTL、supersession、revocation、contradiction、dependency index 和 PIT reconstruction；它不拥有 Evidence/Judgment/Review 的业务裁决。

### 22.1 Memory Registry objects

- `MemoryWriteCandidate`：来自 TECH_02/04/05/09/11 的 immutable business truth ref 和 proposed indexing policy；
- `InstitutionalMemoryEntry`：被 registry 接受的 versioned address/index record；
- `InstitutionalMemoryRef`：供 Case/Context/Workbench 使用的稳定引用；
- `MemoryInvalidationEvent`：freshness、revision、permission、license、reviewer correction、contradiction 或 deletion 触发的状态变化；
- `PITReconstructionRequest/Result`：按 case/as-of/available-at/revision/policy 重建当时可见的 source、fact、judgment、review 和 artifact refs；
- `MemoryDependencyIndex`：memory ref 到 Case/Cell/Claim/Numeric/Artifact/ContextPlan 的影响边。

Memory lifecycle：

```text
candidate -> indexed_active -> stale / contradicted
 -> superseded / revoked / retention_tombstoned
```

Registry 只决定是否可寻址和在什么条件下可返回，不重新决定 fact 是否 accepted、judgment 是否 approved 或 artifact 是否 released。业务状态必须读取 source owner 的 exact version。

### 22.2 Memory classes and owner refs

| Memory class | Source business owner | TECH_03 responsibility |
| --- | --- | --- |
| Accepted/Rejected Evidence | TECH_02；numeric eligibility TECH_04 | address、freshness、negative reuse、revision impact |
| Numeric Fact/Program/Assumption | TECH_04 | program/input/version index、recompute dependency |
| Judgment/WWC | TECH_05 | historical prior、confidence/delta/supersession index |
| ReviewerDecision/Release | TECH_09 | actor/target/hash/supersession index |
| CaseControl/Workpaper | TECH_01 | case timeline、current/historical head lookup |
| Monitoring/ThesisDelta | TECH_11 | trigger/observation/refresh causation index |
| Method/Skill/Preference | TECH_03 address；TECH_07 injection policy | version/permission/retention，不得充当事实 |

### 22.3 TECH_07 boundary

TECH_03 返回 `MemoryCandidateBundle` 或 exact `InstitutionalMemoryRef`。TECH_07 负责 hard filter、selection、budget、compaction 和 InjectionPlan，不得创建第二套 memory lifecycle 或把一次未引用自动解释为 memory 无效。`MemoryWriteCandidate` promotion 必须调用本 registry，并保留 source business owner status。

### 22.4 Reviewer correction and longitudinal reuse

Reviewer correction 进入 memory 时必须保留 correction target、old/new owner refs、reason、scope、applicable entity/metric/period/source/parser、expiry 和 whether-generalizable。默认只影响当前 Case；只有通过 review/eval 的规则或 ontology change 才能升级为跨 Case negative/procedural memory。

Follow-up/refresh 读取 memory 时先执行：permission/license -> as-of/available-at -> source revision -> business-owner current status -> contradiction -> Case scope。任何失败返回 typed stale/revoked/conflict，不返回无条件“历史真相”。

### 22.5 Accountability and privacy index

TECH_03 可以索引 ActorSnapshot、AccountabilityEvent、DecisionAttestation 和 ArtifactProvenanceManifest refs，供 Cell/Claim responsibility graph 与 audit package 查询；不能修改事件、批准或责任语义。Raw prompt/response、private scratchpad 和敏感 payload 仍由 TECH_06 retention policy 管理，memory index 只保存允许检索的 ref/tombstone。

本节状态为 `documented / contract_draft`；现有 R57/context/method assets 不等于统一 registry 已实现。

## 23. FIN 0.1.3 Candidate-Ceiling、索引时效与排序准入（2026-08-08）

RAG/KB 的候选层必须先证明“应当找到的资料能进入 pool”，再证明“排序把它排到前面”。`CoverageAuditRecord` 与 `CandidateBundle` 至少新增或标准化以下字段：

- `provider_capability_state` 与 exact provider/policy version；
- `source_snapshot_as_of / indexed_at / source_revision`；
- `required_target_group_ref`（仅 evaluator 可见）与 `target_in_pool`；
- `required_slot_recall_before_ranking`；
- `route_attempted / locator_found / fetch_terminal / parser_terminal / qualification_terminal`；
- `unique_canonical_source_count / role_binding_count / local_snapshot_count`；
- `ranking_admission_status / ranking_not_admitted_reason`；
- `candidate_to_promotion / promotion_to_claim_utilization`。

排序与索引规则：

1. 旧索引规模、row 数或 lexical hit 不能证明 current coverage。FIN 0.1.3 审计中的旧 BM25 snapshot 虽有 `89,112` records，却缺 current DELL/NVDA annual，因此保持 non-authority，不能在 current source 前获得事实或排序提权。
2. evaluator Gold 的 locator/insight/ID 不得进入 query、source catalog、index build 或 reranker feature；只在运行结束后计算 target-in-pool 和 selected coverage。
3. target-in-pool 未过时，BGE/Milvus/NDCG/MRR 均 `not_admitted`。扩大 top-k、切 reranker 或把 historical accepted memory 混入 pool 不能修复 source acquisition 缺口。
4. `SourceDocument`、`CandidateBinding` 和本地 snapshot 分开存储与计数；canonical document 可以被多个 role 引用，但网络收益率只计一次。
5. rejected locator/date/relationship 与 failed route 要进入 negative/repair index，但不能因为被索引就变成 accepted Evidence；后续 reuse 仍重新检查 case/as-of/authority。

当前 FIN 0.1.3 只证明 v3 zero-call candidate/runtime 合同；最近 DELL live 只有 1 个 unique SEC source、四组 hidden target target-in-pool=0。故 TECH_03 的 current ranking/vector 质量仍未准入，本节不表示主索引刷新、三案 live candidate ceiling 或 RAG 产品验收完成。

## 24. FIN 0.1.3 金融研究内核、Evidence Slot 库与插件边界（2026-08-09）

### 24.1 为什么需要本节

三案例尸检确认，当前系统的问题不是单纯缺一个 embedding 或 reranker，而是此前把 source family、粗 Evidence Slot、query 和单候选 qrel 混成了近似同一个对象。结果是：候选排名看似可用，但多 facet 研究问题仍无法组成 Evidence Pack；同时 DELL／MU／NVDA 的别名、产品和关系细节开始渗入共享查询代码。继续逐案加条件会形成不可维护的案例迷宫。

本节不替换 TECH_03 既有 Source／Structure／Candidate／Memory 分层，也不新建第二套 DecisionSurface。它冻结上层金融语义如何复用这些对象，并与已有 `CellCompositionEngine`、`QueryFacetPlan`、`CandidateBundle` 和 Evidence Gate 对齐。

### 24.2 四层组合

| 层 | 可拥有 | 禁止拥有 |
| --- | --- | --- |
| `FinancialResearchKernel` | subject、evidence owner、relationship direction、period/as-of、source authority、candidate/evidence boundary、citation/lineage、coverage/conflict/gap | ticker、产品名、行业指标、Provider 特判、Gold locator |
| `Evidence Slot Library` | 通用问题、required/optional facets、最低独立来源族、允许 candidate role、typed gap code | 单案例答案、固定 URL、模型生成事实 |
| `FinancialResearchIndustryPack` | 行业 facet、metric、mechanism、query atoms、source role preference、forbidden substitution | 改写核心身份／期间／lineage／authority、直接 Evidence promotion |
| `CaseResearchProfile` | 公司别名、财年／截至日、关系端点、从 Pack 中选取的 facets | 新造 Pack 外 facet、核心代码分支、Gold target 或标准答案 URL |

现有四个外源 Evidence Slot 继续作为 source-discovery family，不再等同完整研究问题。它们分别映射到多个新 Slot：issuer results 可服务 operating performance、pricing/mix 和 cash conversion；customer demand 可服务 demand quality 与 relationship attribution；supply 可服务 capacity、relationship 和 counterevidence；regulatory 可服务 cash、policy 与 counterevidence。映射必须保留原始 family lineage。

### 24.3 稳定插件接口

第一版接口只冻结输入／输出和 authority，不指定实现：

```text
SourceAdapter.discover(SearchIntent) -> SourceLocator[]
ParserAdapter.parse(RawCaptureRef) -> FinancialDocumentObject[]
CandidateRetriever.search(TypedRetrievalRequest) -> FinancialCandidate[]
EvidencePackEvaluator.evaluate(CandidatePackInput) -> CandidatePackEvaluation
```

- `SourceAdapter` 只发现 locator；Provider 日期、snippet 和 score 不具事实权威。
- `ParserAdapter` 只解析已保存的 raw capture，不得修改 source identity、发布日期权威或 Evidence 状态。
- `CandidateRetriever` 只返回经过 typed identity／period／relationship filter 的 candidate；SQL、sparse、dense、graph 均实现同一接口但各自只消费适合的 query lane。
- `EvidencePackEvaluator` 聚合多个 candidate 的 facet 覆盖、canonical source diversity、冲突和 residual gap；它不能晋升 Evidence。

### 24.4 多候选 Evidence Pack evaluator

一个 qrel 或一个 chunk 只证明候选相关。Slot 完整性必须对多个候选取覆盖并同时检查：

1. case 与 subject 一致；
2. evidence owner 和 relationship direction 已由 Case profile 授权；
3. reporting period／as-of 合法；
4. facet 在通用 Slot 或选定 Industry Pack 内；
5. citation 与 raw/parser lineage 完整；
6. source diversity 按 canonical source family 计数，同文档多 role binding 不增益；
7. support／counter 对同一 semantic claim 冲突时保持 unresolved；
8. 未覆盖 facet 生成 typed residual gap；声明 gap 只能使执行终态化，不能把 incomplete Pack 变 complete。

evaluator 的最高输出只能是 `candidate_complete_pending_evidence_gate`。Evidence Gate、NumericProgram、reviewer 和后续 Judgment 继续拥有事实晋升、数值权威与研究结论。

### 24.5 Chunk／object 与索引重建关系

新合同先定义“研究要找什么”，再决定“什么对象值得入库”。DELL 纵切将逐 facet 检查现有 SourceDocument、Section、Q&A、Table、child claim、parent context 和 template filtering 是否够用；只有能改善真实 Evidence Pack coverage 的对象形状才进入下一版 sparse／dense。不得先把 410 个旧形状片段向量化，再用后端排序掩盖 source／chunk 缺口。

### 24.6 泛化证明

泛化不是“同一函数跑了三个 ticker”。最低证明顺序为：

1. DELL 作为开发纵切，允许修改通用内核、Industry Pack 和 DELL case config；
2. MU／NVDA transfer 期间，通用内核与插件实现 digest 必须不变，只允许 Pack／case config 和来源数据变化；
3. 三个 evaluator-blind 留出 archetype 覆盖美国非半导体、non-US 20-F／6-K／本币／PDF、披露稀疏与 honest-gap；
4. mutation 覆盖别名、财年／公历错位、同名实体、关系反转、跨案／未来期污染、多语言、PDF-only、重复 role binding、旧期和零结果；
5. 任何新案例需要修改核心 ticker 条件时，generalization gate 失败，问题回到 Pack／ontology／plugin 设计，不得静默放行。

机器合同：`configs/runtime/fin_ia_0_1_3_s0_s1_financial_research_generalization_contract_v1_0.json`。当前状态仅为 `contract_frozen_zero_call`，不表示 DELL 纵切、MU／NVDA 迁移、留出泛化、索引重建、外源补源、DeepSeek 研究或产品验收完成。

### 24.7 DELL 真实纵切后的 source/object 修正（2026-08-09）

DELL 纵切证明，金融 RAG 不能把一个检索命中等同于一个独立、完整、可引用的事实。当前正确对象边界为：

1. `SourceDocument` 持有 issuer、accession、URL、发布日期、报告期和原始正文 digest；
2. `Section/Table/Q&A` 持有局部语义，但必须保留 parent source 与表头／问题／回答上下文；
3. `Claim/Metric` 只用于精确定位和排序，不能独自承担 source authority；
4. `CandidateBundle` 将 parent source、child object、period binding、relationship direction、facet 与局限合并后，才进入 Pack evaluator；
5. 公开结果只保存 preview、capture/source ref 与 digest，完整 source 正文留在受限原始资产，不在每个 lane 重复物化。

真实 DELL 资料暴露四项当前对象缺陷：Q1 summary 被误标成 non-GAAP disclaimer；结果表错误继承 `Capital Return` subsection；metric child 只保留 `2026 | 16,132` 而丢失“DELL FY2027 Q1／AI-optimized server revenue”完整列语境；SQLite object store 缺少 direct object-id lookup。它们属于下一次 sparse／dense 入库前的对象重建输入，不能靠提高 top-k 或 rerank 权重掩盖。

期间权威必须同时保存三层，禁止互相覆盖：

- research as-of：本次研究允许看见资料的截止日；
- source reporting period：披露方自己的财年／季度；
- relationship valid-as-of：客户、供应商或行业 read-through 在何时可用于本案。

例如 Microsoft FY2026 的 AI 投入只能作为 Microsoft 自身需求 read-through；它不自动成为 Dell FY2027 Q1 的订单或收入。MU、NVIDIA、TSMC 的供给自述同理：可以证明行业供给机制，除非有明确分配证据，否则不能写成“向 Dell 供应了多少”。source diversity 也按经济披露主体／canonical source 计数，同一文档绑定多个 role 不增加独立来源数。

DELL R3 的 `23/23` 只代表预审 candidate 被当前本地检索召回；它不是 Evidence acceptance。required facet 若现有来源无法覆盖，必须以 typed residual gap 终态化。当前 gap 包括 AI server ASP／台数／产品利润与 price-volume-mix bridge、HBM／先进封装／容量释放、AI 营运资金归因、Dell 特定供应分配、pull-forward/digestion 和可观察失效阈值。只有这些 gap 才允许在后续阶段编译为外源补源请求；在 MU／NVDA transfer 和 held-out proof 前仍不得自动重建 dense 或调用模型。

### 24.8 MU／NVDA core-unchanged transfer 与 profile extension boundary（2026-08-09）

迁移 wrapper 在执行前后重算通用合同、核心模块与 DELL executor SHA，并独立核对 DELL reference digest。MU／NVDA 只能提供 Case profile、typed query lanes、reviewed candidate bindings、source inventory 和 residual gaps；任一 locked SHA 变化、跨案污染、wrong period、关系反转、目标遗漏、candidate rejection、漏报 gap 或重复 gap 都使迁移失败。

真实本地结果为 MU=`24 lanes / 256 rows / 24 of 24 qualified / 16 parents / 13 gaps`，NVDA=`26 lanes / 262 rows / 26 of 26 qualified / 13 parents / 13 gaps`，两案 contract rejection 均为 `0`，network／model／embedding／rerank／Evidence promotion 均为 `0`。这使已有三案的 case transfer 工程门通过，但并未改变任何 Candidate 的 Evidence 状态。

迁移暴露的共同对象重建要求为：publication date 与 reported period 分离；document segment 拆成带父节、表头、单位和期间的 table／metric／claim；补齐 current regulatory parent；关系对象区分行业 read-through 与 company-specific allocation。索引重建必须覆盖这些对象语义，不能只把现有粗片段重新向量化。

真正的新案例扩展必须走外部 profile registry／overlay：运行时把 profile 校验后投影给冻结 compiler，profile 不得新增 kernel authority、放宽 Industry Pack 或携带 Gold URL。若留出案例仍要求编辑冻结合同中的 ticker 列表，说明 extension interface 不成立，必须在 S1 修复后重做留出验证。

### 24.9 留出案例后的 CandidateBundle v2 要求（2026-08-09）

ORCL／ASML／ANET 的 Gold-blind 候选与业务复核表明，仅保存 child object 的文本、父 ID 和一个归一化数值单位不足以支撑金融研究。特别是 ASML 20-F 中，父表明确使用欧元，child metric 却标记为 `usd_millions`；另有经营现金流 child 错连到 remuneration 父段。此类对象若直接进入 dense index，会把解析错误放大为高置信召回。

下一版检索单位必须是不可拆散的 `FinancialCandidateBundleV2`：

```text
source authority
  + child object
  + parent block / section
  + table identity and header
  + row / column / footnote path
  + publication date
  + reported period
  + research as-of
  + currency / unit provenance
  + relationship direction
```

约束如下：

1. child 可以用于精确定位和排序，但 evaluator 与 Evidence Gate 必须同时看到 parent semantic context；
2. table／metric 没有表头、行列路径或单位来源时，只能返回 `object_context_gap`，不得当作可引用数值；
3. parent、table header、child 和 case profile 对 currency／unit 有冲突时，Candidate 阶段以 `currency_unit_conflict` fail closed，禁止通过默认 USD 或渲染层覆盖；
4. parent-child lineage 不能由相似文本推断，必须来自 parser 生成的稳定 object path 和 source digest；
5. `source_absent_gap` 与 `retrieval_quality_gap`／`object_context_gap` 分开。前者表示截至期没有合格源；后两者表示源已存在但对象化、查询或排序还不足；
6. 行业 read-through 与 company-specific attribution 必须是不同 relationship role，前者不能补齐后者的 required facet；
7. alias、多语言、ADR／local ticker 和 PDF-only 只通过 case-neutral resolver／parser plugin 扩展，不进入金融内核的 ticker 分支。

索引准入因此改成两道门：先对 DELL／MU／NVDA 和 ORCL／ASML／ANET 证明 bundle 语义、currency／unit、parent path 与 typed gap；再决定哪些 Source／Section／Table／Q&A／Claim／Metric 对象进入 sparse／dense。当前 held-out 结果状态为 `held_out_generalization_blocked_before_index_rebuild`，不能以 required Slot 均有候选或 top-k 数量代替该准入门。

### 24.10 CandidateBundle v2 六案投影结果（2026-08-09）

版本化 successor 已在不修改 v1 kernel／executor／result 的条件下，对 DELL／MU／NVDA／ORCL／ASML／ANET 共 1,179 条真实候选执行投影。DELL／MU／NVDA 分别为 `265/265`、`256/256`、`262/262` bundle；ORCL 为 `113 bundle + 17 typed rejection`，ASML 为 `104 + 8`，ANET 为 `139 + 15`。所有候选均终态，unsafe numeric admission 为 0。

该结果的含义不是“旧对象已经修好”，而是 v2 能识别并隔离旧对象缺陷。ASML 的三个 currency conflict、五个 invalid numeric cell、两个 unit-authority gap 和一个 table-path gap 都没有被默认币种或 renderer 覆盖。后续 current source 必须 capture-first，并由带 parent table marker／row／column／currency provenance 的 parser 投影；旧 child 只保留为失败证据。

当前 gate 仍为 `sparse_dense_rebuild_admitted=false`。原因是 ORCL／ASML／ANET 的截至期资料尚未进入本地 source inventory，且 PDF／多语言／ADR-local ticker mutation 尚未用新来源完成。只有这部分完成并经同一六案 gate 复证，才允许冻结新的 sparse／dense object manifest。

### 24.11 Current-source table reparse 与索引对象准入（2026-08-09）

ORCL FY2026 10-K、ASML Q2 2026 6-K exhibit 与 ANET Q2 2026 10-Q 已从不可变 response capture 使用同一 table-preserving parser 重建。该过程不读取目录声明的 MIME 作为唯一权威，而是联合 URL 后缀、实际 HTTP content-type 与正文签名；PDF 在没有 layout-preserving adapter 时必须返回 typed parser gap，禁止伪装成 HTML 成功。

多层财务表头必须编译为真实二维坐标。例如 Oracle 债务表的 `2026／2025 × Amount／Effective Interest Rate` 不能退化为一串年份，也不能因证券名称中含百分号而把 amount cell 标成 percent。Metric 的 Slot 路由只允许使用本行 label；父表 title、active group 和整表 context 可作为检索上下文，但不得替单元格决定经营、现金、资本、风险或关系语义。

本轮最终零调用结果为 ORCL `1,132 admitted／353 typed reject／27 bundles／8 Slots`，ASML `18／0／13／5`，ANET `470／238／27／7`，unsafe numeric admission=`0`，9 类 mutation 全通过。人工复核纠正了“债务利率→现金／风险”“有价证券到期回款→债务”“Customer relationships 无形资产→客户关系证据”和父期间污染 current-row 排序等问题。机器数量门与人工业务语义门必须同时通过。

该结果只准入下一次 sparse／dense **manifest 重定基**，不准许直接把全部 source objects 写入索引。特别是自动 narrative claims 仍可能包含安全港或法律套话；主索引只能消费显式选中的 CandidateBundle，未选对象留在 candidate／repair 层。clean archive 独立复证完成前，不得签发真实 embedding／Milvus build；索引完成也不等于 Evidence、研报质量或产品泛化通过。

### 24.12 表格语义坐标必须成为索引准入字段（2026-08-10）

R1 clean proof 后的 manifest 逐条审计证明，“可复现”不能替代“业务坐标正确”。同一个数值只有同时绑定行语义、列语义、期间和单位，才是可索引的金融 Metric。以下信息不得在 parser、CandidateBundle 和 index spec 之间丢失：

1. `metric_period` 与 `period_role`：年度、季度、时点、rollforward transaction 或 useful-life descriptor 必须明确；
2. `metric_unit`：货币及规模、percent、count、years／months／days、basis points、ratio 必须保持为不同维度；
3. `row_label`、`column_label` 与 `table_header`：索引文本可压缩，但验证器必须能重建原始二维坐标；
4. `currency_unit_authority`：表内显式单位优先于邻近叙述；含 `except` 的混合尺度表继续交给逐行规则，不能取第一个单位短路；
5. descriptor＋period 混合表头采用 exact logical cardinality；descriptor-only rollforward 由相邻 balance rows 推导交易期间；压缩期间行按冻结的 ordered candidate periods 绑定；任何不唯一情况 typed reject。

`period_role` 编译必须采用分层优先级：先识别行级明确经济语义（例如 `End-quarter`、carrying amount、remaining useful life），再识别完整列级期间，最后才使用 form/duration fallback。`Q1–Q4 + year` 只为没有时点标记的指标提供 `qtd`；独立自然日期列为 `instant`；`three/six/nine months ended` 分别编译为 `qtd/ytd`。因此同一张季度摘要表可以同时安全承载 flow 与 stock。

表头识别必须区分 `pure year row` 与 `grouped year/change row`。前者只在去除独立单位单元格后全部为年份时才允许跳过；后者允许年份与 Change 描述符组合，并须与上层 `Three Months Ended／Six Months Ended／Year Ended` 做笛卡尔坐标展开。单位前缀不得阻断 period group 恢复，普通数据行中的两个大数也不得被当成年份表头。

每次 parser 变更后的索引准入不能只比较 object count 或 digest。实现必须对冻结入选集执行 business-coordinate diff（case、row、column、raw value、unit、period、period role、lineage）；任何消失、新增或坐标退化先形成失败记录。只有差异为零或每一项有明确、审过的合法解释，才可更新 manifest binding。

本轮 R2、R3、R4 分别关闭非货币维度／表内币种、descriptor 列错位、rollforward／压缩行错期。三次均是同一 S1 owner 下的新零调用 Attempt，不是新产品版本。旧 R1 result/proof 保持不可变，但不能再授权索引；新的 sparse／dense manifest 必须绑定 R4 result 与其 clean proof，并对 `metric_period_missing`、`metric_unit_mismatch` fail closed。

R4 result=`924c656e32e5e279c12883a6374f53b7e424d5e3046c2ed18e6a4d2f11878ffc`，两个 clean Git archive／fresh process 已从提交 `25286d10...a4da` 完全复现，proof=`0d8531aa...36e4`；A1 tarfile 兼容失败与 A2 reporter 字段失败均单独保留。manifest 的新增 period-role 门又使 R4 的下游授权失效：R5–R7 分别保留销售额丢失、分组毛利率／现金角色错误、年度组标签退化的失败证据。R8 result=`6ca7ce22...f86b1` 已使 48 条入选对象与 R4 业务 identity 等价并将缺失 period role 降为 0；两个 clean Git archive／fresh process 已从提交 `7e49846c...bb41` 完全复现，proof=`e1565f9d...13342`。

R8-bound manifest R3 虽完成 93-spec、19 narrative quarantine、15 mutations 与 fake sparse／dense 物化，逐条业务审计仍发现四个 ORCL balance/exposure 对象被标为 annual。由此 validator 必须进一步验证 `row economic role -> explicit column duration -> table presentation axis -> form fallback` 的优先级；comparative date-axis debt/balance tables 不得因 10-K form 被归入 annual。R3 结果保留但无下游 authority；R9 同阶段 successor 通过业务 audit 和 clean proof 前不得再次物化 manifest，更不得签发真实 BGE／Milvus build。所有结果仍是 Candidate，不是 Evidence。

R9 result=`caee03a5...7f3e` 已在不改变 48 条业务 identity 的前提下只修正上述四个角色，分布=`18 instant／10 qtd／8 ytd／12 annual`；无 ticker 分支，9 source-object mutations 与四类新增 presentation-axis fixture 均通过。两个 clean archive／fresh process 已从提交 `aff1cc46...514e` 完全复现，proof=`5d46ca9d...0a7c`；R9 现可供 manifest R4 零调用重绑，但仍不是 physical index 或 Evidence。

manifest R4 working-tree result=`d84b7ef2...e7a1`：同一 manifest 同时驱动 fake ObjectBM25 与 fake BGE-M3/Milvus，93 specs／19 narrative quarantine／15 mutations 均通过；known-case 45 个 vector-text digest 不变，held-out roles=`18/10/8/12 instant/qtd/ytd/annual`。clean proof 必须在每个 archive 内先从 capture 重建 R9 私有对象，再重建 manifest，禁止直接信任主工作区私有 CAS。通过后只准入独立 real-build authority decision。

上述 clean proof 已从提交 `0db3c40a...ff37` 的两个 archive 完成：R9=`caee03a5...7f3e`、manifest R4=`d84b7ef2...e7a1` 均逐字节一致，proof=`47cdb6e8...6beb`。real-build executor 仍须另行绑定 Linux root filesystem、BGE-M3 模型 digest、Milvus 版本／collection、93-spec manifest digest、exact-once target、资源预算与 terminal receipts；proof 未加载模型或写索引。

### 24.13 共享物理索引发布合同（2026-08-10）

ObjectBM25 与 BGE-M3／Milvus 必须消费同一 93-spec manifest，且发布前后分别比较 spec population 与 `(vector_id, case_key, spec_digest)` identity digest。sparse record 使用 `object_id=vector_id`、`ticker=research case`、`source_evidence_id=source record`、`search_text=vector_text`，保留 slot／facet／source locator／Candidate state；这样现有 `ObjectBM25Retriever` 无需 ticker 分支即可读取。dense metadata 保存同一 identity、slot/facet JSON、期间、来源和 vector-text digest，不能在 index writer 中改写业务对象。

真实 executor 仅允许 Ubuntu-22.04 WSL2 的 Linux root filesystem。固定流程为 fresh working root → ObjectBM25 atomic files → offline local BGE-M3 → 12 个至多 8-row batches → fresh Milvus Lite DB/FLAT COSINE collection → double flush/count → close/reopen → one metadata identity query → private receipt → same-filesystem rename。历史库只读；失败 working root 不删除；任何 terminal failure 消费 R1 且不得自动 retry。

独立 runtime 当前绑定 Python `3.10.12`、Torch `2.10.0+cpu`、Transformers `5.2.0`、SentenceTransformers `5.2.3`、pymilvus `3.0.0`、milvus-lite `3.0`、rank-bm25 `0.2.2`、pip-freeze digest=`8c47414e...af00`。BGE 五文件 digest 与既有 authority 一致；milvus manifest source=`os.rename`／`59b45341...fcd6`，所以 Windows 仍禁止。full-fake proof=`99b7f66e...cfdc` 已证明 real sparse serialization、fake dense 93/93 和七类 fail-closed mutation，真实模型／Milvus调用为 0。

`physical index present`、`retrieval quality` 与 `product integration` 是三个不同状态。前者成功后仍须单独执行同 Query Facet／qrels 矩阵的 sparse、dense、fusion 对照；Windows Workbench 若不能稳定调用 WSL store，也不能标记 integrated。Evidence promotion、residual-gap external supplement、DeepSeek research 和 report acceptance 均继续在后续 gate。

clean/synced implementation=`566d5223...477e` 的 R1 authority=`0ca08fec...4260` 已签发未消费。authority 除 Git bindings 外还绑定当前 package-tree fingerprints、pip freeze、BGE model files、Milvus manifest source、fresh Linux targets 与 disk floor。worker 在执行前必须重新计算 `environment_identity` 并与 authority 相等；disk free 只检查 floor、不要求字节恒等。该 requalification 仍为 0 model load／0 index write，失败则在创建 working root 前终止。

### 24.14 Milvus directory-store artifact 与 terminal publication 更正（2026-08-10）

唯一 R1 证明当前 `milvus-lite==3.0` 的 URI 不是单文件 SQLite 语义：`milvus_lite.db` 是包含 `collections/<name>/manifest.json`、Parquet data、FLAT index、WAL 和 schema 的目录。R1 已完成 93 个 BGE 向量、12 批 insert，并在 close/reopen 后到达 publisher；但 publisher 的 `database_path.is_file()` 错误地把目录 store 判为缺失。该 Attempt 保持 `terminal_failed`，working root 不可复用。

后续物理发布合同必须新增 provider-neutral `PhysicalStoreArtifact`：

- `artifact_kind=file|directory` 由已指纹化 backend profile 声明，禁止从 `.db` 后缀推断；
- directory artifact 递归生成 canonical tree manifest，拒绝 symlink／越界路径，逐文件记录相对路径、字节和 SHA256，并绑定 tree digest；
- backend-level integrity 至少绑定 collection manifest version／current sequence、数据文件、index 文件、close-reopen count 与完整 identity digest；
- private receipt 同时记录 sparse metadata、dense artifact manifest、全部 writer counters 和最后 verified phase snapshot；失败 envelope 使用同一计数结构，不能丢失 flush／count／reopen／metadata-query；
- 原子发布的单位仍是整个 fresh working root，通过同一 Linux filesystem 的 rename 进入 fresh final root。目录 store 内部文件不得单独复制或从失败 root 晋升；
- fake 必须覆盖 file／directory 两种 artifact 和类型错配；真实 successor 前只允许独立 1-vector micro-canary 验证 directory close／reopen／count／metadata／tree digest／rename，不加载 BGE、不写 93 条业务对象。

上述更正属于 S1 Harness/存储发布层，不改变 CandidateBundle、金融时间／单位权威、Query Facet 或 Evidence 合同。更强模型不会消除该要求；它也不是 DeepSeek 适配问题。R2 只有在实现、mutation、micro-canary 和 clean proof 后才能另行签发。

v1.1 working-tree 已把该要求落到 Runtime：`inspect_physical_store_artifact()` 由 policy-bound profile 接收 `file|directory`；directory tree 按相对 POSIX 路径排序并绑定每个文件 SHA256，拒绝 symlink、特殊文件和 `..` manifest path；Milvus profile 继续核对 collection、`current_seq`、embedding dim、COSINE／FLAT、data 和 index。executor 在 private receipt 前检查一次，whole-root rename 后再检查一次并要求相同 artifact digest。`complete_observed_calls()` 被 success／failure 共用，phase receipt 保存最后已验证状态。

当前重新绑定的零调用 proof=`898a9aae...768f`：93 shared specs／12 fake dense batches、file 控制组、directory fixture 和 11 类 mutation 通过，其中 manifest 文件路径与 partition 名称越界分别 fail closed；proof 同时绑定 Windows issuer bootstrap 与 clean-proof normalized pytest count comparator。Windows 对 symlink 建立无权限时该单测可 skip；真实 Ubuntu microcanary 已自然证明 symlink fail closed。microcanary 与 R2 使用不同 policy、Attempt、working/final root 和 authority；任一失败均 0 retry，且 R1／clean A1 都不得进入 successor。

真实 Ubuntu microcanary 已按唯一 authority 成功：1 个 4 维 synthetic vector、1 insert、2 flush、2 count、1 metadata query、1 reopen；symlink mutation fail closed，published directory artifact=`6fd72c78...03ea`，working root 在 whole-root rename 后不存在，final root 只读复核一致，result=`b7042ceb...4e77`。BGE／business object／search／rerank／Evidence／network／provider／LLM 均为 0。该结果证明 backend publication profile，但仍需 two-clean-archive reproduction 才允许 R2 authority。

two-clean-archive A2 已通过，proof=`095e24ab...f9a9`：两份 commit `c0a4d3f3...` archive 分别重现 implementation proof=`898a9aae...768f`、proof file SHA=`a6fdc447...3a5`、`16 passed／1 skipped`、11 mutations 与相同 directory fixture digest，所有真实调用为 0；同时对已发布 microcanary 做只读复核，未再次写向量。A1 的 volatile-duration mismatch 保留为失败。该结果只允许另行签发 R2 authority，不等于 R2 已执行。
