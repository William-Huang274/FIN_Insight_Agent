# P36 Node 03 Parser / Evidence Operator Manual Run

日期：2026-07-09

## 节点定位

节点：`node_03_parser_evidence_operator`

目标：检查 node 02 的 RAG / market / ownership / source-route 候选能否通过现有 parser、Exact-Value Ledger、exact slot、industry operating slot、product KPI verifier 或 promotion rule，晋升为 writer 可用的 cell-level bounded rows。

本节点不写最终报告，不补外源，不把 recall hit 直接当事实。它只回答一个工程问题：现有 parser/evidence operator 给不给后续 specialist 和 writer 足够、可信、可审计的结构化材料。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/ledger_store.py`
- `src/sec_agent/mcp_tool_registry.py`
- `src/sec_agent/mcp_contracts.py`
- `src/sec_agent/exact_slot_contracts.py`
- `data/processed_private/ledger/sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- `data/processed_private/ledger/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- `data/manifests/parser_run_ledger_v0_1.jsonl`
- `data/manifests/exact_slot_rows_v0_1.jsonl`
- `data/manifests/exact_slot_coverage_matrix_v0_1.json`
- `data/manifests/industry_operating_metric_slot_summary_v0_1.json`
- `data/manifests/industry_operating_metric_slot_rows_v0_1.jsonl`
- `data/manifests/product_kpi_source_specific_verifier_summary_v0_1.json`
- `data/manifests/product_kpi_source_specific_verifier_promotable_rows_v0_1.jsonl`

## 节点允许与禁止

允许：

- 调用本地 `sec_query_exact_value_ledger` / `query_ledger_facts`。
- 检查 exact slot / parser ledgers。
- 判断 RAG candidate 是否能变成 exact or bounded runtime row。
- 标记 parser false positive、单位冲突、row role 不足、promotion gap。

禁止：

- 不联网补源。
- 不运行 paid LLM。
- 不运行 true full-chain。
- 不把 market / ownership proxy 提权为基本面事实。
- 不把 parser 候选直接送给 writer，除非已通过 exact / slot / authority boundary。

## Evidence Operator 接口观察

`sec_query_exact_value_ledger` 的输入粒度是：

- `ledger_store_path`
- `tickers`
- `years`
- `filing_types`
- `source_tiers`
- `metric_families`
- `period_roles`
- `limit`

它能查出结构化数值行，但不是按用户问题的 decision cell 查。比如用户问的是 `server OEM margin dilution` 或 `HBM profit quality`，工具层只能查 `ticker + metric_family=margin/revenue`，无法直接保证返回的是 AI server margin、HBM margin、CoWoS pricing 或 semicap AI backlog。

## Exact-Value Ledger 探针

### `sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb`

| 查询 | 结果 | 判断 |
|---|---:|---|
| NVDA revenue / margin | 6 rows | 可召回，但出现语义风险：`Gross margin` 有 `1.0` / `-1.2` `usd_millions`，`Revenue` 有 `22%` / `62%`。这更像同比/变动百分比或表格局部值，不适合直接当 headline revenue / margin。 |
| DELL revenue / margin | 0 rows | 不可用。 |
| SMCI revenue / margin | 0 rows | 不可用。 |
| HPE revenue / margin | 0 rows | 不可用。 |
| MU revenue / margin | 6 rows | 可用。能召回 2026 10-Q / 8-K revenue and gross margin rows，但不是 HBM-only margin。 |
| AMAT revenue / margin | 6 rows | 可用。能召回 8-K revenue and gross profit rows。 |
| LRCX / KLAC / ASML / TSM | 0 rows | 不可用或未进入该 ledger。 |

### `sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`

| 查询 | 结果 | 判断 |
|---|---:|---|
| DELL revenue / margin | 6 rows | 可用。能召回 FY2026 8-K gross margin / non-GAAP gross margin / operating income rows，但不是 AI server gross margin bridge。 |
| SMCI revenue / margin | 6 rows | 可用。能召回 2026 10-Q / 8-K net sales rows，但存在 `usd_thousands` 与 `usd_millions` 同表重复，需要 numeric sanity。 |
| HPE revenue / margin | 6 rows | 可用。能召回 2026 8-K net revenue rows，但不等于 AI systems backlog or server-specific margin。 |
| MU revenue / margin | 6 rows | 可用。能召回 revenue / gross margin rows，但不是 HBM-only。 |
| AMAT revenue / margin | 6 rows | 可用。能召回 revenue / gross profit rows。 |
| LRCX revenue / margin | 6 rows | 可用。能召回 2026 10-Q revenue / gross margin rows。 |
| KLAC revenue / margin | 6 rows | 可用。能召回 total revenue rows，但也出现 deferred system revenue 等可能不适合作 headline 的行。 |
| ASML / TSM | 0 rows | 通过该 ledger tool 查不到，但 exact slot rows 另有 consolidated primary disclosure rows。 |

结论：

- 财报数据不是没有。尤其 server OEM、Micron、AMAT、LRCX、KLAC 的基础财务行可从 ledger 查出。
- 但 exact ledger 返回的是“metric family 候选”，不是“决策格答案”。很多行还需要 headline-selector、单位去重、period role 和 label sanity。
- 如果直接给 writer，writer 可能用错；如果不给 writer，writer 就只能写边界。

## Exact Slot / Parser Ledger 探针

### Product KPI verifier

`product_kpi_source_specific_verifier_summary_v0_1.json`：

- candidate count: `21,838`
- promote: `12`
- promotable product metric tickers: `1`

判断：这个 verifier 很严格，适合避免产品收入/销量乱提权，但它几乎不能覆盖 AI/Semis 本题需要的产品经济性。它不能给出 HBM revenue mix、CoWoS pricing、AI server gross margin 或 accelerator SKU economics。

### Industry operating metric slot

`industry_operating_metric_slot_summary_v0_1.json`：

- runtime rows: `1,923`
- runtime tickers: `186`
- rejection count: `7,876`
- 主要 slot 是 business segment revenue、capacity/utilization、backlog/orders、shipment 等。

命中本 case：

| ticker | rows |
|---|---:|
| ASML | 25 |
| DELL | 25 |
| LRCX | 5 |
| TSM | 24 |

但 ASML 样例暴露 false-positive 风险：`Inventories, gross`、`Inventories, net`、`Bank accounts`、`Finished products`、`Utilization of the reserve` 等被标成 `product revenue` 或 business/segment revenue 类 row。它们有边界声明，但如果下游只看 `metric_name=product revenue`，会误导。

判断：industry operating slot 有潜力，但在 AI/Semis 本题不能直接信任，需要 node-level verifier / reviewer surface 显示 row label、table title、source evidence 和 rejection/sanity 状态。

### Exact slot rows

`exact_slot_rows_v0_1.jsonl` 对本 case 覆盖较广：

| ticker | exact slot rows | 主要价值 |
|---|---:|---|
| AMD | 182 | consolidated fundamentals + product surface/context |
| HPE | 97 | consolidated fundamentals + product/context rows |
| ASML | 98 | consolidated fundamentals + official product surface/context |
| NVDA | 93 | consolidated fundamentals + product surface/context |
| AMAT | 85 | consolidated fundamentals + semicap context |
| DELL | 64 | consolidated fundamentals + relationship/order proxy |
| MU | 60 | consolidated fundamentals + product surface/context |
| SMCI | 57 | consolidated fundamentals + product/context rows |
| KLAC | 47 | consolidated fundamentals + product/context rows |
| Samsung `005930.KS` | 43 | primary disclosure + official product surface/context |
| LRCX | 34 | consolidated fundamentals + relationship/order proxy |
| TSM | 25 | primary disclosure + official product/context rows |
| SK hynix `000660.KS` | 23 | primary disclosure + official product surface/context |

关键边界：

- `primary_company_disclosure` rows 适合 consolidated revenue / gross profit / cash flow。
- `official_product_surface` 多数是 product identity/context，不能自动证明 sales, ASP, backlog, margin。
- `public_order_proxy` 和 `supply_chain_official_relationship` 只能做 relationship/order existence proxy。
- 对 HBM / CoWoS / AI server margin 这类问题，exact slot rows 有公司级财务和产品表面，但仍缺对应业务线经济性。

## Candidate Promotion Coverage

| required item | parser/evidence operator 结果 | 结论 |
|---|---|---|
| `req_accelerator_revenue_profit` | NVDA/AMD consolidated exact rows exist；NVDA ledger query has noisy headline risk | 可部分晋升。需要 headline selector / sanity。 |
| `req_server_oem_peer_panel` | DELL/SMCI/HPE revenue and margin rows exist in sector-depth ledger/exact slots | 可晋升基础财务 peer panel，但 AI server margin bridge 仍缺。 |
| `req_tsmc_foundry_packaging_bridge` | TSM exact slot primary disclosure exists；ledger tool 0 hit；CoWoS rows absent | 只能晋升 consolidated TSM facts，不能晋升 CoWoS monetization。 |
| `req_hbm_peer_panel` | SK hynix/Samsung/Micron exact slot rows exist at company level；MU ledger rows exist | 可晋升公司级财务，不能晋升 HBM-only revenue/margin/supply economics。 |
| `req_semicap_peer_panel` | AMAT/LRCX/KLAC ledger rows exist；ASML exact slot exists but ledger tool 0 hit | 可晋升部分 consolidated semicap peer financials；ASML/AI-specific bookings/China/WFE仍缺。 |
| `req_export_control_cross_risk` | NVDA row exists; ASML/TSM official risk rows not unified | 需要 source-hunter/government/issuer risk parser。 |
| `req_price_in_capital_market` | market / ownership rows exist outside exact ledger | 需要 price-in pack projection；不能晋升为 exact fundamentals。 |
| `req_source_grade_numeric_sanity` | exact slot rows have boundaries；ledger rows need unit/label sanity | 部分具备，但不是 per-cell automatic sanity。 |

## 质量判断

现有 parser/evidence operator 能生成一份基础财务面板：

- revenue
- gross profit / gross margin proxy
- operating income
- net income
- cash flow
- capex
- segment/product context where already verified

但它不足以生成用户题面需要的核心“高质量收入/利润捕获”答案：

- AI server gross margin / GPU pass-through economics 缺。
- HBM-only revenue / gross margin / capacity allocation 缺。
- TSMC CoWoS capacity / pricing / customer allocation 缺。
- Semicap AI-specific bookings / backlog / WFE / China exposure peer matrix 不完整。
- price-in / ownership / valuation rows 没被投射为 decision-surface rows。

因此，以现有 node 03 输入约束，我可以给后续 specialist 准备“基础财务 + 严格缺口”的材料，但还不能准备一份足以写完整高质量研究报告的 evidence pack。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | 能支持基础财务问题，不能支持完整 value-capture 问题。 |
| decision_surface_completeness | partial | 多数 decision cells 只能拿到 company-level proxy 或 gap。 |
| financial_and_operating_depth | partial | 基础财务行较多，但业务线经济性不足。 |
| capital_market_price_in_depth | partial | market/ownership rows 存在，但本节点不能把它们提权为 price-in conclusion。 |
| source_grade_and_lineage | pass | exact slot / ledger / market / ownership / context rows 边界可追溯。 |
| counter_thesis_and_turning_signals | partial | 可支撑 margin dilution / price-in / capex digestion 的部分 counter rows，但还不是 turning-signal matrix。 |
| writer_readiness | partial | 能给 writer 基础表和 gap，不足以给完整报告。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | 输入候选按工具/数据层组织，不按 decision cell 组织。 |
| output_contract_quality | partial | exact rows 可结构化，但没有统一 cell-level promotion result。 |
| tool_affordance_fit | partial | ledger/slot/parser 工具存在，但需要人工知道用哪个 store、哪个 artifact。 |
| observability | pass | parser run ledger、exact slot rows、ledger query output 和 boundaries 均可追溯。 |
| recoverability | partial | 可定位到 parser false positive / missing slot，但缺自动 repair loop。 |
| information_economy | partial | 大量候选需要人工筛选；错误行会增加 downstream caution。 |
| marginal_contribution | partial | 相比 single-agent，lineage 更强；相比研究目标，promotion path 仍弱。 |
| human_review_surface | partial | 缺 per-cell row label / unit / table title sanity review UI。 |
| product_value_over_single_agent | partial | 基础数据资产强，但没有转成自然可用的 analyst pack。 |

## Root-cause notes

- Exact-Value Ledger 是 metric-family 查询，不是 decision-cell promotion API。
- 不同 store 覆盖差异很大，导致同一 ticker/metric 在一个 ledger 0 hit，在另一个 ledger 有 rows。
- Headline selector / unit sanity 不足：NVDA、SMCI、KLAC 等样例显示同一 metric family 下可能返回百分比、delta、deferred revenue、thousands/millions重复值。
- Industry operating metric parser 有 false-positive 风险，ASML 样例把 inventory/bank accounts/reserve utilization 归入 product revenue 类。
- Product KPI verifier 太严格且覆盖太窄，不能支撑本题产品经济性。
- Exact slot rows 能支撑 consolidated financials，却不能自动回答 HBM/CoWoS/AI server margin 这类业务线经济性。
- Market/ownership rows 需要单独 price-in pack，不该混入 fundamental exact ledger。

## 下一节点输入

进入 `node_04_graph_relationship_value_capture` 前，可传递：

- `foundation_financial_rows`: exact slot / ledger 中较可信的 consolidated fundamentals。
- `promotion_candidates_requiring_sanity`: sector-depth ledger 的 DELL/SMCI/HPE/MU/AMAT/LRCX/KLAC rows。
- `unsafe_or_needs_review_rows`: NVDA noisy gross margin/revenue rows、ASML industry slot false positives、SMCI duplicated units。
- `business_line_gaps`: HBM-only、CoWoS、AI server margin bridge、semicap AI-specific bookings/backlog。
- `market_price_in_candidates`: market snapshot and ownership rows, bounded to price-action / lagged-holder context。

下一节点要回答：图谱能不能把这些 rows 组织成 value-capture relationship，而不是只告诉我们公司之间有关系。
