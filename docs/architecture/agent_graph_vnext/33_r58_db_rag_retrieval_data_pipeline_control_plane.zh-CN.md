# 33. R58 DB / RAG / Retrieval / Data Pipeline Control Plane

日期：2026-06-28

状态：framework draft。本文先冻结 R58 的问题边界和第一版技术框架；具体 demand tickets、schema migrations、runtime implementation 和 eval cases 等后续再拆。

## 1. 定位

R58 不是“再建一个 RAG”，而是把当前已经存在的数据库、RAG、Milvus、BM25/ObjectBM25、Graph Store、Gold Mart、Source Authority、ContextEngine 和 Runtime Audit 组织成一个可控、可审计、可优化的检索与数据管线控制层。

R58 承接：

- R24 / RD0-RD7：原始披露、parser ledger、Gold Fact / Signal Mart、Graph Store、Retrieval Index Registry、Agent Runtime Consumption Contract 和 Data Quality Release Gate。
- R56：RuntimeFacade、ToolGateway、durable graph、resource/model queue 和 Workbench/Java entrypoint。
- R57：GraphPack / SkillPack / MemoryPack、ContextEngine、ContextCompressionArtifact 和可 replay 的 ContextInjectionPlan。
- R60：eval、observability、failure/gold lifecycle、retrieval qrels、data quality gates 和 release readiness。

R58 解决的问题是：

```text
用户问题 / ResearchObjective
 -> retrieval intent
 -> route policy
 -> data / graph / index selection
 -> query rewrite / facet plan
 -> candidate generation
 -> rerank / fusion / quota
 -> ContextEngine compression / injection
 -> ClaimCard / GapLedger / JudgmentState
 -> run audit / eval / feedback
```

同时 R58 也要定义数据 ingestion 到 agent runtime 的存储规范和传递合同，避免未来继续出现“数据其实有，但 agent 不知道怎么查、查到了不知道能不能用、用错了又追不回原始来源”的问题。

## 2. 当前事实快照

当前底座已经不是玩具级别：

| 层 | 当前状态 |
| --- | --- |
| Raw / source | `data/raw_private` 包含 SEC、structured facts、global disclosures、company IR 等入口 |
| SEC structured facts | 588 家 CompanyFacts/submissions；financial fact rows 约 `2,790,261` |
| Financial runtime facts | `10,146` rows，覆盖 `587/603` |
| RD3 Gold Mart | `74,894` rows；exact authority `30,722`，bounded thesis driver `44,147` |
| RD4 Graph Store | `26,538` nodes / `100,145` edges / `113,199` support rows |
| RD5 Retrieval Registry | `22` index snapshots / `23` source lineage / `12,584,655` declared records |
| Milvus | local Milvus Lite available；`662,908` vectors；`581` indexed tickers；`narrative_chunk/table_chunk/paraphrase_context/relationship_context` |
| RD6 Runtime Contract | `603` company briefs / `3,618` role EvidencePacks / `80,656` selected refs |
| RD7 Data Gate | `47` gate rows；`42` pass / `5` warn / `0` fail；release allowed with recorded warnings |
| Run Audit DB | 已覆盖 run、node、artifact、retrieval、evidence、claim、gap、gate、model、resource、context、parsed input |

关键判断：

- 事实主库已经存在雏形，RAG index 不是事实库。
- Milvus 是 typed semantic recall supplement，不是 exact authority。
- BM25/ObjectBM25/SQLite FTS/Milvus 都必须回连 raw source、parser run、authority row。
- Research Lead 现在需要的是检索控制面和数据合同，而不是更多零散 rows。

## 3. R58 范围

### 3.1 本文覆盖

1. 检索召回策略：
   - retrieval intent taxonomy；
   - route policy matrix；
   - hybrid recall / graph recall / exact-first；
   - query rewrite / facet plan；
   - rerank / fusion / quota；
   - retrieval audit / qrels / eval。

2. 数据工程与数据管线：
   - raw -> bronze -> silver -> gold -> graph -> index -> runtime 的 pipeline contract；
   - ingestion storage convention；
   - parser/fetcher/locator/verifier/authority mapper 的数据合同；
   - incremental refresh、snapshot、idempotency、replay。

3. 数据库与性能：
   - SQL exact first；
   - SQLite / DuckDB / Postgres / MySQL / ObjectStore / Milvus 的边界；
   - index registry 与 retrieval cache；
   - 时间 / 空间复杂度；
   - 本地 / 云端资源策略。

4. Crawler / parser tooling surface：
   - 什么时候用 API；
   - 什么时候用 HTTP fetch；
   - 什么时候用 Playwright / browser rendering；
   - PDF / table / HTML / XBRL / image OCR / API response 的解析合同；
   - 不同工具输出如何进入统一 parser ledger。

### 3.2 暂不覆盖

- 不在 R58 内重新定义 GraphPack / SkillPack / MemoryPack；这些归 R57。
- 不在 R58 内重写 LangGraph / RuntimeFacade；这些归 R56。
- 不在 R58 内定义 memo / PPT / dashboard renderer；这些归 R55。
- 不在 R58 内定义二级市场数据源全景；source registry 归 R54，R58 只定义它们如何进入管线和检索。
- 不在 R58 内直接上生产数据库迁移；本文先定义结构，具体 migration 进入 demand tickets。

## 4. 目标架构

```text
RawSource / API / Web / PDF / Filing
 -> IngestionJob
 -> RawSourceDocument / FetchAttempt / SourceSnapshot
 -> ParserRun / ParsedChunk / ParsedTable / MetricCandidate / ClaimCandidate
 -> GoldFact / SignalAuthorityRow / ProductFact / CapitalFact / MarketFact
 -> ResearchGraphStore / ProductIntelligenceGraph / CapitalGraph / OwnershipGraph
 -> RetrievalIndexSnapshot: BM25 / ObjectBM25 / SQLite FTS / Milvus / Dense
 -> RetrievalStrategyPack
 -> RetrievalExecutionLedger
 -> ContextCompressionArtifact / ContextInjectionPlan
 -> RoleEvidencePack / ClaimCard / GapLedger / JudgmentState
 -> RunAudit / EvalStore / FeedbackLoop
```

R58 的核心 runtime 对象：

```text
RetrievalStrategyPack
RetrievalIntent
RoutePolicyMatrix
QueryRewriteAndFacetPlan
HybridRecallPlan
RerankPolicy
RetrievalExecutionLedger
RetrievalQrelsDataset
DataIngestionContract
ParserExecutionContract
StorageAndLineageContract
DatabasePerformanceProfile
```

## 5. Retrieval Intent Taxonomy

检索策略首先要识别问题类型，而不是直接把 query 扔进所有索引。

| Intent | 典型问题 | 首选路径 | 禁止事项 |
| --- | --- | --- | --- |
| `exact_financial_metric` | revenue、capex、cash、debt、inventory、AR/AP、CFO、FCF | Gold Mart / structured facts / ledger / ObjectBM25 table | 不先用 Milvus 找 exact value |
| `financial_statement_trend` | 三大表变动、同行可比、派生指标 | FundamentalStatementPack + structured facts + peer panel | 不只引用管理层叙述 |
| `product_profile` | 公司卖什么、产品线、服务线 | ProductIntelligenceGraph + company product slots | 不把 segment revenue 当 SKU revenue |
| `product_spec_architecture` | H100 vs MI300、Blackwell、CPU/GPU 参数 | ProductSpecPack + official product surface + trusted technical docs | 不把 benchmark/proxy 写成销量或收入 |
| `product_kpi_exact` | product revenue、shipment、ASP、backlog、subscribers、AUM、capacity | Product/Business-KPI exact rows + source-specific table parser | 不用产品页/新闻冒充 exact KPI |
| `customer_deployment_adoption` | 谁采用/部署/订单/渠道上架 | ProductRelationshipGraph + deployment/adoption rows + official customer/channel/procurement routes | 不把 adoption proxy 写成销售额 |
| `supply_chain_readthrough` | 上下游、供应瓶颈、capex 传导 | GraphStore + relationship_context + L2/L3 official/proxy rows | 不把 same-family candidate 当强竞争边 |
| `capital_funding_ownership` | 债务、回购、增发、13F、insider、credit | CapitalMacroPack + SEC forms + R54 packs | 不把价格走势当资本结构事实 |
| `market_liquidity_valuation` | price-in、估值、short interest、成交、波动 | MarketLiquidity + valuation + R54 secondary-market packs | 不把市场情绪当基本面事实 |
| `policy_macro_industry` | 利率、政策、周期、行业 beta | Macro/industry packs + FRED/EIA/BLS/Census/official sources | 不直接证明公司产品卖得好 |
| `relationship_graph_query` | 竞争、替代、互补、客户、供应商、读穿 | ResearchGraphStore / ProductRelationshipGraph / graph traversal | 不把图谱导航边当 evidence fact |
| `retrievable_gap_repair` | 应该有但没召回的数据 | LeadReviewCheckpoint + route audit + targeted repair | 不直接暴露 gap 而不查可得公开源 |

## 6. Route Policy Matrix

每个 intent 要有默认 route 顺序、预算和 stop condition。

示例：

| Intent | Route order | First-pass budget | Second-pass trigger |
| --- | --- | --- | --- |
| exact financial metric | SQL Gold Mart -> structured facts -> ObjectBM25 table -> filing text | 小而准 | exact not found but company/period/source exists |
| product spec | ProductSpecPack -> ProductIntelligenceGraph -> official product surface -> Milvus relationship/context | 中 | missing spec slot or stale generation |
| customer deployment | ProductRelationshipGraph -> official customer/deployment rows -> channel/procurement/public order -> web repair | 中到高 | adoption section empty or only generic rows |
| relationship graph | GraphStore traversal -> support edge lookup -> Milvus relationship_context -> source rows | 中 | graph edge unsupported / modelled-only |
| market / capital | R54 pack -> SEC forms -> market DB/API -> bounded gap | 中 | price-in section missing market data |

Route 输出必须有：

```text
RetrievalRouteDecision
- route_id
- intent_id
- route_name
- selected_index_snapshot_ids
- required_filters
- candidate_budget
- rerank_budget
- context_budget
- cost_tier
- authority_boundary
- stop_condition
- second_pass_condition
```

## 7. Query Rewrite / Facet Plan

R58 不允许只用用户原句作为唯一 query。Research Lead 应生成可审计的 facet plan：

```text
QueryRewriteAndFacetPlan
- original_query
- normalized_entities
- tickers
- periods
- product_families
- metrics
- source_roles
- intent_facets
- exact_lookup_queries
- lexical_queries
- semantic_queries
- graph_queries
- negative_queries
- forbidden_expansions
```

要求：

- exact lookup query 必须保留 ticker / period / metric / unit / concept。
- product query 必须保留 product family / SKU / generation / architecture。
- graph query 必须说明关系类型，如 competes_with、upstream_of、deployed_by、read_through_to。
- semantic query 只能补召回，不能覆盖 exact route。
- query rewrite 要写入 audit，供 R60 评测 query drift。
- 外源与内源必须消费同一个 typed facet authority，但生成不同 physical query：Web route 使用 owner／direction／period／source-family 搜索式与 provider filter；SQL／object route 使用 exact key 和 typed predicate；BM25 使用 lexical query；dense／Milvus 使用 semantic query；Graph 使用 typed relation query。禁止把同一 raw user string 无差别发送给全部 route。
- 模型只能返回 allowlisted `query atoms`，不得拥有 entity、period、relationship direction、source-role、forbidden expansion、route filter 或预算的最终解释权。所有模型原子必须经本地 compiler 再生成 physical query；模型辅助是否启用由 raw／deterministic／model-atoms-plus-deterministic 三路 eval 决定。
- 每个 facet plan 必须记录 `target_state`、route opportunity、candidate pool identity 和 plan digest。Gold URL／Evidence ID 只能在所有检索 terminal 后由 evaluator 加载，不能进入 planner 或 query compiler。
- current FIN 0.1.3 先完成 external official-first combined proof，再把同一 facet contract 接入 internal exact／BM25／dense／graph；这两个验收包连续但不混成一次 live。

## 8. Hybrid Recall / Rerank / Fusion

现有系统已有 BM25、ObjectBM25、SQLite FTS、dense/Milvus、Hybrid RRF、facet-aware RRF 和 BGE reranker 基础。R58 的目标是统一策略：

```text
CandidateGeneration
 -> route-scoped candidate pools
 -> source / period / company / product filters
 -> de-dup by source/citation/object id
 -> RRF / score normalization
 -> rerank
 -> authority-aware selection
 -> role-visible evidence bundle
```

Rerank 原则：

- ledger/exact rows 不进普通 BGE rerank；只做 exact verifier。
- narrative / paraphrase / relationship context 可进入 rerank。
- table rows 要用表格-aware preview，不把整表塞入 reranker。
- role-specific quota 要优先保证每个必答维度有证据，而不是全局 top-k 被一个 source family 吃光。
- second pass 只扩 retrievable gap 的 route，不重新全量开所有 route。

必须记录：

```text
RetrievalExecutionLedger
- run_id
- node_id
- intent_id
- route_id
- query_rewrite_id
- index_snapshot_ids
- filters
- candidate_count_pre_filter
- candidate_count_post_filter
- candidate_count_pre_rerank
- candidate_count_post_rerank
- selected_count
- dropped_count
- dropped_reasons
- target_in_candidates
- target_in_selected
- latency_ms
- cost_estimate
- authority_boundary
```

## 9. Data Engineering Pipeline Contract

数据管线按 Bronze / Silver / Gold / Graph / Index / Runtime 分层。

| Layer | 对象 | 目标 |
| --- | --- | --- |
| Bronze | RawSourceDocument、FetchAttempt、SourceSnapshot | 可复跑、可审计、可证明来源 |
| Silver | ParserRun、ParsedChunk、ParsedTable、MetricCandidate、ClaimCandidate、ParserRejection | 解析过程可追踪，候选不直接提权 |
| Gold | FinancialFact、ProductFact、CapitalFact、MarketFact、SignalAuthorityRow | 可进入 evidence bundle 的事实/信号主表 |
| Graph | GraphNode、GraphEdge、EvidenceSupportEdge | 公司、产品、客户、供应链、资本、市场关系 |
| Index | RetrievalIndexSnapshot、IndexSourceLineage、VectorRecord | 召回层快照与血缘 |
| Runtime | AgentDataBrief、RoleEvidencePack、ContextCompressionArtifact、ContextInjectionPlan | Agent 可消费对象 |

所有层必须遵守：

- stable id；
- content hash；
- schema version；
- source snapshot id；
- parser run id；
- as-of / effective time；
- authority boundary；
- tenant / permission；
- deletion / supersession policy。

## 10. Ingestion Storage Convention

新增数据不应长期只落散装 JSONL。每个 ingestion job 必须有：

```text
IngestionJob
- ingestion_job_id
- source_role
- source_route_id
- locator_version
- fetcher_version
- parser_version
- verifier_version
- authority_mapper_version
- input_scope
- output_artifact_refs
- row_counts
- error_counts
- retry_policy
- started_at
- completed_at
- status
```

存储约定：

- raw 原件 / 网页快照 / PDF / API response 进入 ObjectStore 或 raw lake，带 checksum。
- 小型 registry / summary / gate 可进 Git-tracked manifest。
- 大型 rows / ledgers / parser outputs 进 artifact store + SQL mirror。
- index 文件、Milvus DB、FAISS、embedding parquet 不进 Git；只登记 snapshot summary 和 path registry。
- 每个 runtime row 必须能追到 raw/source snapshot；不能追溯的只能 diagnostic-only 或 gap。

推荐路径形态：

```text
data/raw_private/<source_family>/<yyyy>/<issuer_or_route>/
data/staging/<pipeline>/<run_id>/
data/processed_private/<mart>/<version>/
data/workbench_private/research_data/*.sqlite
Z:/FIN_Insight_Agent_artifacts/<artifact_family>/<run_id>/
```

路径只是物理存储，逻辑主键以 DB / manifest registry 为准，避免 D/Z/local/cloud 迁移时断链。

## 11. Node Data Contract

agent 节点之间不能传散装 rows。R58 要把数据传递收敛成合同：

| Producer | Consumer | Contract |
| --- | --- | --- |
| Research Lead | Retrieval Operator | `RetrievalStrategyPack` + `QueryRewriteAndFacetPlan` |
| Retrieval Operator | ContextEngine | `RetrievalExecutionLedger` + selected refs |
| ContextEngine | Specialist | role-scoped compressed `RoleEvidencePack` |
| Specialist | LeadReview | `ClaimCardCandidate` + used refs + missing refs |
| LeadReview | Repair Operator | `TargetedRetrievalRepairPlan` |
| Gold/Graph DB | MemoLogicPlan | approved claim/gap/pack refs only |
| Composer | Deliverable Studio | `JudgmentState` + `MemoLogicPlan` + approved refs |

禁止：

- Memo Writer 直接读 raw retrieval rows。
- Specialist 私自把 gap-only row 写成 evidence。
- Web crawler 输出未 snapshot / 未 parser / 未 authority gate 的 snippet。
- graph candidate edge 直接当事实边。

## 12. Database Architecture And Efficiency

R58 需要明确数据库分工：

| Store | 用途 | 不适合 |
| --- | --- | --- |
| SQLite | 本地开发、artifact mirror、small/medium eval store、single-user workbench | 高并发写、多租户生产 |
| DuckDB | 大型 parquet/CSV analytic scan、batch materialization、offline eval | OLTP / 高频事务 |
| Postgres/MySQL | 生产级 task/run/context/eval/tenant/permission 主账本 | 大型向量、巨型原文 |
| ObjectStore / MinIO-compatible | raw files、PDF、HTML snapshot、large parser outputs、report artifacts | 结构化查询主路径 |
| Milvus | typed semantic vector recall | exact financial authority |
| Redis/MQ | queue、lease、heartbeat、short-lived coordination | 最终审计主账本 |

复杂度要求：

- lineage join 禁止 O(N²)，必须走 keyed index / SQL join / hash map。
- parser materialization 尽量 streaming / batch copy，不使用逐行慢写。
- large JSONL 读写要支持 chunk / iterator / predicate pushdown 或 SQL mirror。
- embedding 构建必须 batch，记录 GPU/CPU device、batch size、throughput。
- retrieval route 要先 filter 后 rerank，避免把 50k rows 丢给 BGE。
- context compression 前必须先 role-select，避免压缩无关上下文浪费 token。

R58 每个实现需求都要记录：

```text
DatabasePerformanceProfile
- row_count
- file_size
- index_count
- expected_query_pattern
- complexity_class
- batch_size
- memory_peak
- latency_p50_p95
- cache_policy
- incremental_refresh_policy
```

## 13. Crawler / Parser Tooling Surface

R58 需要讨论并落成工具层标准，不先绑定单一工具。

### 13.1 Fetcher 层

| Route | 适用 | 输出 |
| --- | --- | --- |
| official API client | SEC、FRED、EIA、openFDA、ClinicalTrials、NHTSA、USAspending 等 | API response snapshot + normalized rows |
| HTTP fetch | 静态公司 IR、产品页、PDF、JSON endpoint | raw HTML/PDF/JSON snapshot |
| Playwright / browser rendering | 需要 JS 渲染、表格分页、官方 store / channel 页面、动态 IR 页面 | rendered HTML / screenshot / network snapshot |
| manual / human supplied file | 用户上传 PDF/Excel/Word/PPT | uploaded artifact + parse job |

### 13.2 Parser 层

| Parser | 适用 | 输出 |
| --- | --- | --- |
| XBRL / SEC CompanyFacts parser | 财务 statement facts | structured facts |
| HTML section parser | 10-K/10-Q/8-K sections、IR pages | chunks / claim candidates |
| table parser | SEC/IR/local filing tables | ParsedTable / MetricCandidate |
| PDF parser | annual report、IR deck、prospectus | text chunks / tables / page locators |
| document parser | Word/PPT/Excel user input | ParsedInputArtifact |
| image/OCR parser | 扫描 PDF、图片表格 | OCR text + confidence |
| source-specific parser | App Store、ATS、official store、procurement、clinical/regulatory | source-role runtime rows |

Parser 输出不能直接进入 ClaimCard，必须先经过 verifier / authority mapper。

### 13.3 Tool Contract

```text
SourceToolExecution
- tool_call_id
- tool_name
- source_route_id
- input_scope
- output_artifact_ref
- output_snapshot_id
- parser_run_id
- row_count
- error_count
- blocked_reason
- retryable
- authority_mapper_status
- runtime_row_status
```

## 14. Eval / Gate

R58 必须和 R60 对接以下评测：

- target-in-candidates；
- target-in-selected；
- pre/post-rerank precision；
- source family diversity；
- role-visible coverage；
- exact-value no-Milvus gate；
- graph edge support gate；
- query rewrite drift；
- compression preservation；
- retrieval budget cap audit；
- data lineage completeness；
- parser / source-route debt attribution；
- latency / memory / GPU utilization；
- incremental refresh correctness。

R58 完成口径不是“case 最终答案好看”，而是：

```text
每个最终 ClaimCard / GapLedger / JudgmentState 都能追到：
query intent
 -> route decision
 -> index / DB / graph snapshot
 -> candidate set
 -> rerank / selection
 -> source row / graph edge / authority row
 -> compression artifact
 -> context injection plan
```

## 15. 外部参考台账与六个吸收设计

R58 需要维护一个可追溯的参考台账，而不是在聊天或一次性调研里临时引用外部平台。每个参考源都必须说明：它解决的企业级问题是什么、我们吸收哪一部分、为什么不全量套用、进入项目后用什么指标验证、后续新增/删除/降级的原因是什么。

### 15.1 Reference Source Ledger

```text
ReferenceSourceLedger
- reference_id
- platform_or_project
- source_url
- source_type: official_doc | github_repo | product_blog | architecture_note | vendor_doc
- reference_scope: ingestion | retrieval | permission | observability | workpaper | data_platform | agent_runtime
- observed_design_principle
- adopted_design_id
- adopted_into_r58_object
- reason_to_absorb
- reason_not_full_adopt
- status: active | watch | deprecated | rejected
- added_at
- last_reviewed_at
- reviewed_by
- removal_or_downgrade_condition
- project_performance_record_refs
```

### 15.2 Reference Change Ledger

```text
ReferenceChangeLedger
- change_id
- reference_id
- change_type: add | update | downgrade | delete | supersede
- reason
- affected_design_ids
- affected_runtime_contracts
- expected_project_impact
- observed_project_metrics_before
- observed_project_metrics_after
- decision
- decision_evidence_refs
```

### 15.3 已吸收的六个设计

| Design ID | 设计 | 参考来源 | 吸收到 R58 的位置 | 为什么吸收 | 为什么不全量套用 | 进入项目后的表现跟踪 |
| --- | --- | --- | --- | --- | --- | --- |
| `R58-REF-01-knowledge-pipeline` | Knowledge Pipeline：把 ingestion、processing、chunking、indexing、retrieval strategy 当成一条可编排管线 | Dify Knowledge Pipeline；RAGFlow dataset / KG pipeline | `DataIngestionContract`、Bronze/Silver/Gold/Graph/Index/Runtime、`ParserExecutionContract` | 解决“数据抓了但没有 parser / authority / runtime row 血缘”的问题 | Dify/RAGFlow 是通用知识库产品；我们的金融数据必须保留 SEC/IR/source authority、exact/bounded/gap 边界和 Workpaper 审计 | 记录 parser success rate、row lineage completeness、source snapshot coverage、data-pipeline qrels |
| `R58-REF-02-permission-aware-system-of-context` | Permission-aware Retrieval / System of Context：连接器、权限、组织上下文、知识源选择同时进入检索控制面 | Glean enterprise AI / system of context；Microsoft Copilot Studio knowledge sources；Onyx connectors/RBAC | `StorageAndLineageContract`、tenant/permission 字段、route source limit、Connector / ToolGateway 接口 | B 端必须保证用户只看到有权限的数据，且 Research Lead 能知道哪些源可查、哪些源禁止查 | Glean/Copilot/Onyx 是横向办公平台；我们不复制其通用连接器市场，先实现金融源、上传文件和企业私有库的权限合同 | 跟踪 permission-denied route、source visibility drift、tenant leakage test、knowledge-source selection precision |
| `R58-REF-03-hybrid-route-control` | Hybrid Route Control：SQL exact、BM25/ObjectBM25、graph traversal、Milvus semantic、web repair 分 intent 路由 | Haystack reusable pipeline components；Glean hybrid search；RAGFlow KG/RAPTOR；现有 RD5 Retrieval Registry | `RetrievalIntent`、`RoutePolicyMatrix`、`HybridRecallPlan`、`RerankPolicy` | 解决“一个 query 扔所有索引”导致 exact 被语义召回污染、预算被宽泛证据吃光的问题 | 通用 RAG 的 top-k/RRF 不能直接代表金融 authority；我们必须 exact-first、graph-guided、authority-aware | 跟踪 target-in-candidates、target-in-selected、route precision、source-family diversity、exact route violation |
| `R58-REF-04-document-intelligence` | Document Intelligence：PDF、表格、图表、Office 文档、复杂布局解析进入统一 parser ledger | LlamaParse complex document parsing；Palantir AIP Document Intelligence；RAGFlow PDF/parser options | `ParserExecutionContract`、`ParsedTable`、`MetricCandidate`、`SourceToolExecution`、uploaded artifact parser | 解决 IR deck、年报表格、PDF 附注、用户上传文档和网页表格不能稳定转成 facts/signals 的问题 | 商业 parser 可参考但不能作为唯一依赖；FIN 需要本地/可替换 parser，且每个 extracted row 必须有 citation/page/table locator | 跟踪 table extraction accuracy、early truncation、page locator completeness、metric parser rejection taxonomy |
| `R58-REF-05-retrieval-observability` | Retrieval Observability：trace、feedback、evaluation、monitoring 和 budget 进入每次检索与 agent run | LangSmith traces/monitoring/feedback；Databricks MLflow ResponsesAgent tracing/evaluation/monitoring；Snowflake Cortex Agents evaluations/monitoring | `RetrievalExecutionLedger`、`RetrievalQrelsDataset`、`DatabasePerformanceProfile`、R60 eval bridge | 解决以前追溯 recall/rerank/context cap 时缺运行记录的问题 | 外部 observability 可导出但不能替代本地 SQL run/eval 主账本；source authority、gap、claim、context injection 必须留在本地审计 | 跟踪 retrieval latency p50/p95、rerank drop reason、query drift、compression preservation、cost/token、failure lifecycle |
| `R58-REF-06-workpaper-matrix` | Workpaper / Matrix Surface：把研究过程做成可审计、可编辑、可协作的矩阵/底稿，而不是最终 memo 黑箱 | Hebbia Matrix transparent decomposition / collaborative grid；Palantir AIP ontology/app/workshop pattern；R51/R52 WorkpaperPack | R58 输出给 R52 `WorkpaperEvent` / `WorkpaperPack` 的 `approved_ref`、`gap_ref`、`source_ref`、`retrieval_trace_ref` | 解决“答案看似完整但不知道每段从哪里来、缺口怎么补、谁批准”的问题 | Hebbia/Palantir 是完整产品平台；我们只吸收透明底稿、ontology/graph-backed trace 和 editable projection，不照搬 UI/商业闭源架构 | 跟踪 Workpaper row drilldown parity、claim-to-source trace completeness、human review overwrite rate、gap closure delta |

### 15.4 参考来源初始清单

| Reference ID | 来源 | 当前状态 | 初始吸收点 |
| --- | --- | --- | --- |
| `ref-ragflow-kg` | https://ragflow.io/docs/construct_knowledge_graph | active | KG between extraction/indexing、entity resolution、KG/RAPTOR 成本边界 |
| `ref-dify-knowledge-pipeline` | https://docs.dify.ai/en/use-dify/knowledge/knowledge-pipeline/knowledge-pipeline-orchestration | active | ingestion-processing-chunking-indexing-retrieval pipeline orchestration |
| `ref-langgraph-persistence` | https://docs.langchain.com/oss/python/langgraph/persistence | active | checkpoint/store、resume、fault recovery 与 R56/R57/R58 bridge |
| `ref-langsmith-observability` | https://docs.langchain.com/langsmith/observability | active | trace、monitoring、feedback、online eval export pattern |
| `ref-haystack-components` | https://docs.haystack.deepset.ai/docs/intro | active | reusable pipeline components / retriever-parser-ranker composition |
| `ref-llamaparse` | https://www.llamaindex.ai/llamaparse | watch | complex document / table / chart parsing reference；不绑定商业依赖 |
| `ref-copilot-knowledge` | https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-copilot-studio | active | knowledge-source limit / source filtering / enterprise source governance |
| `ref-google-adk-agent-platform` | https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/adk | watch | ADK、Agent2Agent、RAG Engine、Skill Registry 作为 runtime ecosystem reference |
| `ref-snowflake-cortex-agents` | https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents | active | SQL/semantic/data-governance-oriented agents、evaluation/monitoring/multitenancy |
| `ref-databricks-agent-framework` | https://docs.databricks.com/aws/en/generative-ai/agent-framework/author-agent | active | ResponsesAgent wrapper、MCP tools、MLflow tracing/eval/monitoring、typed inputs/outputs |
| `ref-glean-enterprise-ai` | https://www.glean.com/enterprise-ai-software | active | enterprise graph、system of context、permissions、connectors、hybrid search |
| `ref-onyx-github` | https://github.com/onyx-dot-app/onyx | active | connector/RAG/job-worker/MinIO/Redis/RBAC/open-source implementation reference |
| `ref-palantir-aip` | https://www.palantir.com/docs/foundry/aip/overview | active | ontology/workshop/document-intelligence/governance reference |
| `ref-hebbia-matrix` | https://www.hebbia.com/blog/introducing-matrix-the-interface-to-agi | active | matrix/workpaper transparency、decomposition、collaborative evidence surface |

### 15.5 新增/删除参考源的门控

新增参考源必须满足：

- 解决 R58 的一个明确痛点，而不是“看起来先进”；
- 能映射到 R58 的 contract、gate、schema、tooling 或 eval；
- 说明不全量采用的原因；
- 有至少一个项目内指标可观测它是否有效。

删除或降级参考源必须记录：

- 该平台能力被我们自研或其他参考源覆盖；
- 其设计与金融 exact authority / permission / audit 边界冲突；
- 其工程成本、商业依赖、闭源限制或数据合规风险高于收益；
- 项目内指标证明吸收后没有改善，或造成复杂度/成本/延迟不可接受。

### 15.6 对当前 R58 的直接影响

六个参考设计不会改变 R58 的底层原则：`DB exact first + graph-guided retrieval + typed hybrid recall + authority-aware rerank + context compression bridge + data lineage audit + qrels/eval feedback`。它们的作用是把这些原则工程化：

- `Knowledge Pipeline` 要求所有外部源从 fetch 到 index 都有 job、snapshot、parser、authority mapper 和 runtime row。
- `Permission-aware System of Context` 要求 retrieval route 在召回前先过 tenant/source permission，而不是召回后过滤。
- `Hybrid Route Control` 要求 Research Lead 先选 intent 和 route，不允许所有索引一起 top-k。
- `Document Intelligence` 要求 PDF/table/Office/webpage 解析形成 parser ledger，不允许 snippet 直接进入 ClaimCard。
- `Retrieval Observability` 要求每次检索能复盘 query、candidate、rerank、drop、selected、latency、cost 和 gap。
- `Workpaper Matrix` 要求检索输出能投影为 Workpaper row / gap row / trace row，让人和 agent 都能继续协作，而不是只生成 memo。
- BGE／dense、fusion 和 rerank 是 candidate pool 下游。只有人工复核 qrels 证明 required target 能进入 pool 后才可准入；否则状态必须是 `not_admitted_upstream_candidate_ceiling`，不得用扩大 top-k、调 embedding 或 reranker 掩盖 query／route／index 缺口。
- 内源验收必须分开四个问题：exact／metadata filter 是否找到正确对象，BM25 是否覆盖 lexical facet，dense／BGE 是否补充语义召回，Graph 是否保持经济关系方向；之后才能比较 RRF／rerank 的增量。结果至少分 DELL／MU／NVDA、Evidence Slot、source role 和 hard-negative cohort，报告 target-in-pool、Recall@K、MRR／NDCG、false promotion、稳定性、延迟与资源成本。
- 排序通过仍不是产品完成；selected rows 必须通过 Evidence Gate，并在 Claim／Workpaper／报告中留下可见 utilization lineage。

## 16. Demand 草案

## P22 Current Status Reconciliation

状态口径：R58 已由 S3/P14/P16 落过合同、ledger、parser、lineage、ContextEngine bridge 和 reference governance。仍为 `partial` 的项不是未开始，而是需要更多 qrels、rerank、真实 crawler coverage 或 production SLA。

| Demand ID | 目标 | 当前状态 | 已有证据 | 边界 / 下一步 |
| --- | --- | --- | --- | --- |
| `R58-D01-retrieval-intent-taxonomy` | 定义 retrieval intent schema 和 classifier contract | done | S3、P14 | 代表性 intent 集合已建；新增 intent 必须版本化。 |
| `R58-D02-route-policy-matrix` | 定义 DB / graph / BM25 / ObjectBM25 / Milvus / web route 顺序和 budget | done | S3、P14 | 路由合同可用；仍需按 failure/gold 扩展 route quota。 |
| `R58-D03-query-rewrite-facet-plan` | 生成 exact / lexical / semantic / graph facet queries | compiler and internal route projection zero-call implemented | S3、P14、S1-08 Query Facet、internal projection proof | 36 个中英 plan 已合并为 18 个双语 bundle，并编译为 SQL／ObjectBM25／BM25／Milvus／Graph 各 18 个 typed request；真实 route execution 与 candidate ceiling 尚未证明。 |
| `R58-D04-hybrid-recall-rerank-policy` | candidate generation、fusion/rerank、role/source quota | upstream-blocked / not admitted | S3、P14、FIN 0.1.3 S1 progression plan | selected/dropped ledger 有，但外源与内源 candidate ceiling 尚未按统一 facet/qrels 通过；BGE/fusion/rerank 不得先调优。 |
| `R58-D05-retrieval-execution-ledger` | 记录 candidate、rerank、selected、dropped、latency、target-in-candidates | done | S3、P14 | 后续 full-chain 必须消费该 ledger。 |
| `R58-D06-retrieval-eval-qrels` | retrieval qrels / gold refs / negative cases | partial / expansion registered | S3、P16、DELL/MU/NVDA S1-08 matrix | 初始 qrels 偏小；需补 entity/period/relationship/source-role hard negatives，并分别测 external target-in-pool 与 internal route contribution。 |
| `R58-D07-data-ingestion-contract` | IngestionJob、RawSourceDocument、FetchAttempt、SourceSnapshot、ParserRun | done | P14 | 代表性 source modalities 已过；不是全 crawler coverage。 |
| `R58-D08-storage-lineage-convention` | raw/staging/processed/artifact/ObjectStore/SQL mirror 规范 | done | P14 | 新 ingestion 输出必须沿用该 lineage。 |
| `R58-D09-parser-tool-contract` | crawler/fetcher/parser/verifier/authority mapper 工具输出合同 | done | P14、P16 | source-specific coverage 仍是数据深度任务；raw snippet 不能直接提权。 |
| `R58-D10-database-performance-profile` | DB/index pipeline row count、complexity、latency、memory profile | partial | P14、P16 | 本地 profile 有；production p95/p99 SLA 未验收。 |
| `R58-D11-contextengine-retrieval-bridge` | RetrievalExecutionLedger 接入 ContextEngine | done | P14 | bridge ready；live graph nodes 仍需逐步迁移。 |
| `R58-D12-release-gate` | retrieval/data-pipeline release gate | partial | P14、P16、P21 | scope gates 通过；P21 仍阻断 broad full-chain 质量结论。 |
| `R58-D13-reference-source-ledger` | 外部参考源台账和变更台账 | done | P16 | 新增/删除/降级仍必须留痕。 |
| `R58-D14-reference-adoption-performance-gate` | reference adoption performance profile | done | P16 | 每次采用新参考设计后都要回填项目内表现。 |

FIN 0.1.3 当前实现补充：Query Facet compiler 以 evidence owner 自身披露为首要查询主体，并保留 subject、period、relationship direction、source family、date upper bound 和 no-relaxed-fallback filters。模型只可添加受控 metric／product／mechanism／synonym atoms；atom 会形成额外 lexical／semantic query，但不能改写 filters。源 proof 为 `36 plan / 60 intent / 72 exact / 72 lexical / 36 semantic / 36 graph`；内源 projection 又把 36 个中英 plan 合并为 18 个双语 bundle，并形成 `18 SQL + 18 ObjectBM25 + 18 BM25 + 18 Milvus + 18 Graph = 90` 个 candidate-only request。SQL 只消费 typed filters，ObjectBM25 消费 exact lookup，BM25 消费 lexical query，Milvus 消费 semantic query，Graph 只消费 typed relationship；内容路由按 evidence-owner ticker 过滤而不是按 case ticker。该 proof 的 retrieval／embedding／rerank 仍为 0，所以 D03 已达到 route-projection engineering pass，D04 继续 upstream-blocked。

### 16.1 内源候选池与排序准入补充（2026-08-09）

真实本地资产必须先作为各 route 的输入资格，而不是被一个总的“RAG 可用”标签覆盖：

- SQL／Gold：验证 company、period、metric family、source role 的 exact candidate ceiling；没有 current-quarter 权威行时返回 typed index/corpus gap，不用旧年度静默替代。
- ObjectBM25／BM25：分别验证结构化 object exact lookup 与文档 lexical facet；`TSM` 在当前两个 lexical index 缺失必须显式计为 index coverage gap。
- Graph：从 evidence owner 出发，按 subject-owner direction 和 allowlisted source role 验证一跳关系；禁止把“客户的客户”或“供应商的供应商”自动扩成当前关系。
- Milvus：先核对 collection、vector count、embedding model identity、filter fields 和本地模型 locator，再执行 semantic candidate 评测；资源不合格就是 route unavailable，不能悄悄跳过。
- BGE／fusion／rerank：仅在前四类候选池已有目标且 qrels review provenance 明确后准入。fusion 必须比较 facet-aware round robin／受控 RRF 等候选，不默认 naive RRF；reranker 不能创造候选或改变 Evidence 权威。

qrels 状态必须可机器区分 `historical_agent_authored_diagnostic`、`agent_curated_pending_owner_review` 与 `owner_reviewed`。当前阶段允许前两种用于暴露 candidate ceiling，但只有最后一种才能支撑正式“人工 qrels 通过”结论。候选池通过后仍须单独证明 selected candidate 经 Evidence Gate 进入 Claim、Workpaper 与报告，否则只是检索组件指标改善。

## 17. Acceptance Gates

R58 framework 完成标准：

- 每类 retrieval intent 都有 route policy、budget、authority boundary 和 second-pass trigger。
- 每次 retrieval run 都有 `RetrievalExecutionLedger`，能解释选了什么、丢了什么、为什么丢。
- Milvus route 必须带 vector kind / source tier / company / period / product filter，不得作为 exact route。
- exact financial / product KPI 查询优先 SQL/Gold/Object route，不允许直接语义召回提权。
- 每个 ingestion job 都能输出 raw/source snapshot、parser run、runtime row lineage。
- 每个 parser / crawler 工具都有 source snapshot、parser run、row count、error count 和 blocked reason。
- 大型数据处理需求必须有 `DatabasePerformanceProfile`，不能用 O(N²) 或逐行慢写隐藏性能债。
- R58 输出必须能接入 R57 ContextEngine 和 R60 Eval Store。
- R58 的外部参考源必须有 `ReferenceSourceLedger` 和 `ReferenceChangeLedger`，新增/删除/降级均能追溯原因。
- 每个吸收设计必须映射到 R58 对象和项目内表现指标，不能只作为“参考资料”堆在文档里。

## 18. 下一步讨论问题

后续需要继续展开：

1. 数据工程：哪些数据进入 Postgres/MySQL，哪些继续 SQLite/DuckDB，哪些只进 ObjectStore。
2. 数据管线：增量刷新、全量重建、snapshot、版本冻结、stale / supersession。
3. 数据治理：tenant、permission、source license、PII、robots、商业数据边界。
4. 数据库效率：600+ 公司、千万级 record、百万级 fact、百万级向量下的本地/云端分工。
5. ingestion 合同：每个 source adapter 如何统一输出 fetch/parser/verifier/authority rows。
6. 爬虫工具：API/HTTP/Playwright/browser rendering/上传文件解析/OCR 应该怎样分层接入。
7. parser 工具：HTML/PDF/table/XBRL/document/image/source-specific parser 的统一准入 gate。
8. eval：如何建立 retrieval qrels 和 data-pipeline qrels，避免只看最终 memo。
9. 参考源维护：哪些外部平台作为 active reference，哪些只是 watch，哪些因闭源/商业依赖/不适配金融场景而 rejected。

## 19. 当前结论

R58 的核心不是“把更多东西塞进向量库”，而是建立一个可靠的 retrieval / data-pipeline control plane：

```text
DB exact first
+ graph-guided retrieval
+ typed hybrid recall
+ authority-aware rerank
+ context compression bridge
+ data lineage audit
+ qrels/eval feedback
```

这样 Research Lead 才能稳定知道：该查哪层数据、为什么查、查不到是 source gap 还是 parser/index/budget gap、查到后能支撑什么等级的结论。
