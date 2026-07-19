# P36 Node 02 Retrieval / RAG / SQL / Source Route Manual Run

日期：2026-07-09

## 节点定位

节点：`node_02_retrieval_rag_sql_source_route`

目标：在不让 writer 自行补源的前提下，模拟 evidence operator / retrieval layer 应该完成的事情：按 node 01 的 required items 查找项目内已有 source-route rows、RAG/ObjectBM25 rows、market snapshot rows、ownership rows 和 typed gaps，判断它们是否足以支撑后续 parser、specialist、aggregate 和 writer。

本节点不是最终报告，不做投资结论，也不把 Codex supervisor 后续补源伪装成 runtime 能力。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/agent_registry.py`
- `src/sec_agent/agent_contracts.py`
- `src/sec_agent/mcp_tool_registry.py`
- `src/sec_agent/mcp_contracts.py`
- `src/sec_agent/market_snapshot.py`
- `src/sec_agent/p34_lane_quality_runtime.py`
- `src/retrieval/object_bm25_retriever.py`
- `docs/project_os/p34_ai_semis_source_route_plan_v0_1.json`
- `docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json`
- `docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json`
- `docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json`
- `docs/project_os/p35_ai_infra_source_supplement_ledger_v0_1.json`
- `data/indexes/bm25/sec_investment_coverage_mixed_with_8k_fy2023_2027_objects`
- `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects`
- `data/processed_private/market/evidence_packs/20260624_market_yahoo_chart_603_3m_v1_3m_market_evidence.jsonl`
- `data/processed_private/market/evidence_packs/20260528_market_yahoo_chart_full78_3m_fmp_valuation_v1_3m_market_evidence.jsonl`
- `Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters/capital_macro_source_adapter_v0_1/capital_ownership_rows.jsonl`

## 节点允许与禁止

允许：

- 使用项目已有 source-route / runtime rows / typed gaps。
- 使用项目本地 ObjectBM25 索引做 RAG recall 探针。
- 使用项目本地 market snapshot 和 ownership rows 做 price-in / positioning 探针。
- 记录候选证据是否能成为 downstream bounded rows。
- 记录工具是否好用、入口是否清晰、是否比手工公开源慢。

禁止：

- 不调用 paid LLM API。
- 不运行 true runtime full-chain。
- 不联网补源。
- 不把 ObjectBM25 recall hit 直接升格为 accepted runtime fact。
- 不把 market / ownership proxy 说成实时资金流、完整 crowdedness 或公司经营事实。
- 不让 writer 在后续阶段自己补源。

## Runtime 入口观察

现有 agent registry 的权限设计是正确但很刚性的：

- `research_lead` 是 `request_only`，不能检索。
- `sec_operator` 可以调用 `sec_search_filings`、`sec_milvus_semantic_search`、`sec_query_exact_value_ledger`。
- `market_operator` 可以调用 `market_get_snapshot`。
- `industry_operator` 可以调用 `industry_get_snapshot`。
- `web_evidence_operator` 可以调用 `web_evidence_snapshot`。
- `fundamental_analyst`、`industry_supply_chain_analyst`、`market_valuation_analyst`、`risk_counterevidence_analyst` 都是 `inspect_only`。
- writer / verifier 不能拥有检索权限。

这个边界意味着：如果 node 02 没把用户问题所需的 decision cells 取齐，后续 specialist 和 writer 没有合理路径补齐，只能写缺口。

## 项目内 P34 runtime rows 复核

P34 live route attempt report 当前状态：

| 项目 | 结果 |
|---|---:|
| evidence slots | 20 |
| route attempts | 21 |
| accepted runtime rows | 21 |
| accepted slots | 20 |
| typed gaps | 2 |
| network attempts | 15 |
| network ok | 15 |

可用 runtime rows 覆盖：

- Accelerator: NVDA Data Center revenue context、AMD MI300X / MI355X spec and performance proxy、Google TPU / GB200 deployment context。
- Server OEM: Dell AI orders / shipments / backlog、Dell ISG baseline、Dell PowerEdge / GB200 product path。
- Hyperscaler demand pool: MSFT / GOOGL / META / AMZN capex or cloud context。
- Foundry / semicap context: TSM advanced node / HPC context、ASML lithography context、AMAT segment mix、LRCX HBM process-intensity context。
- Market context: one AI/Semis basket price-in fixture row。
- Counter-thesis: derived bounded counter-thesis context。

P34 的两条 typed gaps：

- `dell_ai_server_margin_bridge_quality_gap`：Dell public rows can support AI server revenue visibility and ISG baseline, but not AI server gross margin, GPU pass-through economics, or backlog conversion margin。
- `market_price_in_exact_positioning_gap`：public delayed/context rows can support price-in discussion, but not real-time fund flow, gamma exposure, complete options positioning, borrow cost or institutional flow。

判断：P34 rows 不是没价值。它们的问题是按旧 20 个 evidence slots 组织，不是按用户当前 5 条产业链 x 风险/质量维度的 decision surface 组织。

## ObjectBM25 / RAG 探针

我先用 `sec_investment_coverage_mixed_with_8k_fy2023_2027_objects`，再用 `sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects` 做本地 RAG 探针。

### SEC investment object index

索引记录数：`1,118,234`

| 查询 | filter | 命中 | 质量判断 |
|---|---|---:|---|
| NVIDIA data center revenue / gross margin / China export control | `NVDA` | 3 | 可用。召回 NVDA 10-K gross margin claim、FY2027 Q1 8-K China Data Center revenue assumption、Data Center AI platform context。 |
| Dell AI server margin / ISG / GPU pass-through | `DELL` | 0 | 不可用。该索引未覆盖或过滤后未命中 Dell server OEM 关键行。 |
| SMCI AI server revenue / gross margin | `SMCI` | 0 | 不可用。 |
| HPE AI server revenue / backlog / margin | `HPE` | 0 | 不可用。 |
| Micron HBM revenue / margin | `MU` | 3 | 部分可用。能召回 HBM / data center demand context，但还不是 SK hynix / Samsung / Micron peer panel。 |
| TSMC CoWoS / advanced packaging | `TSM` | 0 | 不可用。 |
| ASML bookings / backlog / China / EUV | `ASML` | 0 | 不可用。 |
| AMAT HBM / DRAM / semiconductor systems | `AMAT` | 3 | 可用。召回 DRAM mix metric。 |
| LRCX HBM / WFE / China | `LRCX` | 0 | 不可用。 |
| KLAC process control / advanced packaging | `KLAC` | 0 | 不可用。 |
| MSFT AI infrastructure capex | `MSFT` | 3 | 可用。召回 cloud / AI infrastructure capex disclosure。 |
| META AI infrastructure capex | `META` | 3 | 部分可用。召回 capex / data center context，但更像风险/expense context。 |

### Sector-depth full238 object index

索引记录数：`3,035,688`

| 查询 | filter | 命中 | 质量判断 |
|---|---|---:|---|
| Dell AI server margin / ISG / GPU pass-through | `DELL` | 2 | 部分可用。能召回 gross margin / ISG product gross margin context，但不是 AI server gross margin bridge。 |
| SMCI AI server revenue / gross margin | `SMCI` | 2 | 可用。召回 2026 10-Q and 2025 10-K gross margin tables，适合 parser/evidence operator 深挖。 |
| HPE AI server revenue / backlog / margin | `HPE` | 2 | 部分可用。召回 gross profit margin table and margin risk context，不足以覆盖 AI systems backlog。 |
| TSMC CoWoS / advanced packaging | `TSM` | 0 | 不可用。 |
| ASML bookings / backlog / China / EUV | `ASML` | 0 | 不可用。 |
| LRCX HBM / WFE / China | `LRCX` | 2 | 部分可用。召回 revenue disaggregation / leading-edge market table。 |
| KLAC process control / advanced packaging | `KLAC` | 2 | 部分可用。召回 advanced packaging process control business description，不是 bookings/backlog/China exposure。 |

RAG 结论：

- 项目本地 RAG 不是没用。它可以很快找到 NVDA、MU、AMAT、MSFT、META、SMCI、DELL、HPE、LRCX、KLAC 的官方 filing 片段。
- 但 RAG 结果没有按 decision surface 自动聚合，也没有自动把 recall hits 推到 parser/exact-value ledger / source-route attempt / typed gap。
- 非美/IR/PDF/press-release 口径仍弱，尤其 TSMC CoWoS、ASML quarterly PDF、SK hynix / Samsung HBM、TSMC platform chart。
- 同一问题换一个 index 结果差异很大，说明当前工具入口对 agent 不够友好：operator 需要知道该选 `sec_investment` 还是 `sector_depth_full238`，否则会误判为“没数据”。

## Market snapshot / ownership 探针

### Market snapshot

`20260624_market_yahoo_chart_603_3m_v1_3m_market_evidence.jsonl`：

- 相关 ticker 命中：13 行，覆盖 `NVDA`、`AMD`、`DELL`、`SMCI`、`HPE`、`MU`、`TSM`、`ASML`、`AMAT`、`LRCX`、`KLAC`、`000660.KS`、`005930.KS`。
- 可用字段：1D / 5D / 1M / YTD return、3M volatility、max drawdown、close price。
- 字段缺口：`104` 个 field gaps，主要是 `market_cap`、`enterprise_value`、`pe_ttm`、`ev_sales_ttm`、`ev_ebitda_ttm`。

样例信号：

- `MU`: YTD return about `162.8%`, 1M return about `38.3%`, 3M volatility about `100.5%`。
- `DELL`: YTD return about `145.4%`, 1M return about `46.6%`, 3M volatility about `96.3%`。
- `SMCI`: YTD return about `48.6%`, 1M return about `-7.2%`, 3M volatility about `115.3%`。
- `000660.KS`: YTD return about `159.2%`, 1M return about `31.7%`, 3M volatility about `94.4%`。

`20260528_market_yahoo_chart_full78_3m_fmp_valuation_v1_3m_market_evidence.jsonl`：

- 相关 ticker 命中：4 行，覆盖 `NVDA`、`AMD`、`AMAT`、`MU`。
- `NVDA` 与 `AMD` 有 `pe_ttm` / `ev_sales_ttm`，但 `AMAT` / `MU` 仍缺 valuation fields。
- 覆盖面不足以形成五链条 peer valuation matrix。

判断：项目可以做 price action / volatility / partial valuation，但当前 P34 payload 只给了 basket-level bounded fixture，没有生成 ticker-level price-in 表。用户会感知为“没有资本市场分析”，而不是“有严谨边界”。

### Ownership / 13F

`capital_ownership_rows.jsonl` 有 `7,956` 行，命中本 case 相关 US / ADR ticker：

| ticker | ownership rows |
|---|---:|
| NVDA | 59 |
| AMD | 23 |
| MU | 17 |
| KLAC | 16 |
| DELL | 10 |
| AMAT | 9 |
| SMCI | 6 |
| ASML | 5 |
| HPE | 5 |
| LRCX | 4 |

边界：

- `claim_scope=lagged_ownership_context_only`
- `not_realtime_flag=true`
- 常见 `lag_days` 为 59 天或更长
- 不能解释为实时资金流或主动买卖意图

判断：ownership 数据存在，适合做“滞后持仓/拥挤度 proxy 的边界表”，但当前 AI/Semis runtime 没把它接入 price-in decision cell。

## Required Items 覆盖判断

| required item | 当前项目内支持 | 缺口 |
|---|---|---|
| `req_decision_surface_cells` | P35 framework / gap audit 可用，但不是 runtime contract | 没有作为检索 key 驱动 node 02 |
| `req_hyperscaler_capex_pool` | P34 rows + ObjectBM25 可召回 MSFT/META/AMZN/GOOGL context | 仍缺 capex/revenue ratio、digestion numeric sanity |
| `req_accelerator_revenue_profit` | NVDA / AMD rows 可用，NVDA 官方 row 较强 | 仍缺完整 AMD/NVDA peer financial bridge and price-in |
| `req_server_oem_peer_panel` | P34 Dell rows + sector-depth RAG for SMCI/HPE | SMCI/HPE 未进入 accepted runtime rows；AI server margin bridge 缺 |
| `req_tsmc_foundry_packaging_bridge` | P34 TSM advanced node context | CoWoS capacity/pricing/allocation 未入 runtime；TSM ObjectBM25 探针 0 命中 |
| `req_hbm_peer_panel` | MU filing HBM context + market rows for SK hynix/Samsung/MU | SK hynix / Samsung / Micron HBM revenue and margin peer panel 未入 runtime |
| `req_semicap_peer_panel` | AMAT/LRCX/KLAC/ASML 部分 filing/context rows | ASML/TSM 非美或 IR PDF rows 未由 RAG 表现出来；bookings/backlog/China/WFE peer matrix 不完整 |
| `req_export_control_cross_risk` | NVDA 8-K China assumption, ASML context row | 需要政府/issuer official rows 统一成 cross-risk matrix |
| `req_price_in_capital_market` | market snapshot + 13F ownership rows 存在 | 没进 runtime payload；valuation/positioning coverage incomplete |
| `req_counter_thesis` | P34 derived counter pack 可用 | 需要按五链条生成 falsifier / turning signal matrix |
| `req_source_grade_numeric_sanity` | P34 source authority / typed gaps 做得较好 | numeric sanity 没按每格固化 |
| `req_writer_decision_surface_first` | P35 报告里有目标形态 | writer runtime 仍未原生接 cell-level payload |

## Node 02 输出

可以交给下游的内容应分三层：

1. `accepted_runtime_rows`
   - 只能使用 P34 accepted runtime rows 和 typed gaps。
   - 这些可以进入 specialist / writer。

2. `project_native_recall_candidates_not_promoted`
   - ObjectBM25 对 NVDA/MU/AMAT/MSFT/META/DELL/SMCI/HPE/LRCX/KLAC 的召回结果。
   - market snapshot 对 13 个 ticker 的 price action rows。
   - ownership / 13F 对 10 个 US / ADR ticker 的 lagged holder rows。
   - 这些是 source-hunter/parser/evidence-operator repair candidates，不能直接给 writer 当 runtime facts。

3. `supervisor_supplement_only`
   - P35 source supplement ledger 的 15 条 official/high-grade public sources。
   - 这些解释为什么 Codex supervisor 能写出更完整报告，但它们仍不是 agent runtime accepted rows。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | node 02 找到了可支撑答案的若干数据，但不能直接回答完整五链条问题。 |
| decision_surface_completeness | partial | P35 decision surface 存在，但检索不是 cell-driven。 |
| financial_and_operating_depth | partial | 有 NVDA/MU/AMAT/SMCI/DELL/HPE 等 filing hits，但 HBM/CoWoS/semicap peer panel 不完整。 |
| capital_market_price_in_depth | partial | market/ownership 数据存在，但 valuation coverage 不完整，且未接入 P34 payload。 |
| source_grade_and_lineage | pass | source-route rows、RAG hits、market rows、ownership rows、supervisor supplement 区分清楚。 |
| counter_thesis_and_turning_signals | partial | P34 有 bounded counter pack，但不是五链条 falsifier matrix。 |
| writer_readiness | partial | accepted rows 可写 scoped memo，但不足以写用户要求的完整 AI infra report。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | node 01 required items 清楚，但不是 runtime 原生 DecisionSurfaceContract。 |
| output_contract_quality | partial | P34 output 有 rows/gaps，但没有按 decision cells 输出 retrieval coverage map。 |
| tool_affordance_fit | partial | ObjectBM25/market/ownership 都能用，但入口分散，index 选择依赖人工经验。 |
| observability | pass | P34 attempts、accepted rows、typed gaps、market/ownership probes 都可追溯。 |
| recoverability | partial | 可以通过 source-hunter/parser repair 补，但当前没有自动 second-pass loop。 |
| information_economy | partial | RAG 能找到候选，但还需人工筛选 index 和 promotion path。 |
| marginal_contribution | partial | 相比 single-agent，项目强在 lineage/gap；弱在 front-office narrative completeness。 |
| human_review_surface | partial | 目前缺 cell-level review surface，只能看 rows/gaps。 |
| product_value_over_single_agent | partial | 数据资产有潜力，但还没转成自动优于 WorkBuddy 的体验。 |

## Root-cause notes

- `DecisionSurfaceContract` 仍不是 retrieval 的一等输入。检索层没有按 `segment x dimension` 逐格找证据。
- Source-route replay 和 RAG recall 是两条线，当前 P34 scoped case 使用前者，不是完整 SQL/RAG/Milvus discovery pass。
- RAG index 选择不透明。同一个问题在 `sec_investment` index 下 0 命中，在 `sector_depth_full238` 下有命中，agent 很容易误判。
- Market snapshot 与 13F/ownership 数据已经存在，但没有被 case-wired 到 price-in / positioning decision cell。
- 非美和 IR/PDF/press-release 表格仍是主要缺口：SK hynix、Samsung、TSMC、ASML 的官方 rows 不能稳定进入 parser-backed runtime rows。
- 当前 writer 禁止补源是正确边界，但系统缺少 writer 前的 SourceHunterLoop，所以边界会挤占主要输出。

## 下一节点输入

进入 `node_03_parser_evidence_operator` 时，应把候选材料分成：

- 已 accepted 的 P34 runtime rows and typed gaps。
- ObjectBM25 recall candidates requiring parser / exact-value promotion。
- Market snapshot / ownership rows requiring price-in pack projection。
- P35 supervisor supplement rows requiring source-route ingestion rather than direct writer use。

下一节点要回答：现有 parser/evidence operator 能否把这些候选变成 `value/unit/period/source/cannot_infer` 清楚的 cell-level ledger；如果不能，问题是在 parser、source route、row schema、promotion rule 还是缺少 source-hunter orchestration。
