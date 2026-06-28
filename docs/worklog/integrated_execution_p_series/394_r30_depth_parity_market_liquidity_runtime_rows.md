# R30/R31 第二/第三层深度 parity 与 market liquidity runtime rows

## 问题

用户要求继续推进“600+ 公司都有同等深度的产品 KPI / 产品规格 / 客户部署 / 资本市场细项 / 市场流动性数据”。此前 R26b 已证明第二层和第三层都有真实 parser-backed source rows，但这个口径仍偏宽：有一条 source row 不等于五类研究深度都可用。

## 决策

本轮把验收口径提高为逐公司五维 depth parity matrix：

- `product_kpi_depth`
- `product_spec_depth`
- `customer_deployment_depth`
- `capital_market_detail_depth`
- `market_liquidity_depth`

其中 `status=pass` 只代表审计矩阵能正常生成，不能替代 `full_depth_target_met`。普通产品页、catalog、URL、seed、attempt-only 或 metadata 不允许冒充强 technical spec、产品 KPI exact、订单 exact 或资本条款 exact。

## 完成工作

- 在 `src/sec_agent/layer_acceptance_gates.py` 新增 `build_second_third_layer_depth_parity_matrix`，把 audit status 和 parity status 分开，并输出 company rows / backfill queue。
- 新增 `scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`，从现有 L1/L2/L3 runtime rows 构建：
  - `data/manifests/second_third_layer_depth_parity_summary_v0_1.json`
  - `data/manifests/second_third_layer_depth_parity_matrix_v0_1.jsonl`
  - `data/manifests/second_third_layer_depth_parity_backfill_queue_v0_1.jsonl`
- 在 `src/sec_agent/market_snapshot.py` 新增 `build_market_liquidity_driver_context_rows`，把 market evidence pack 投影成 `market_liquidity_driver` runtime rows。
- 新增 `scripts/data_expansion/build_market_liquidity_driver_context_rows.py`。
- 修复 market snapshot normalizer，新增 `--per-ticker-as-of`，避免全量 Yahoo snapshot 中个别 ticker 的最新交易日与全局 as-of 不一致时被误判。
- 用 Yahoo chart 3M price/volume snapshot 为 603家公司生成 market liquidity rows；首次下载 `ARE` timeout，单 ticker retry 后合并修复。

## 结果

R30/R31 最新 summary：

- `company_count=603`
- `full_depth_target_met_company_count=0`
- `full_depth_target_gap_company_count=603`
- `market_liquidity_depth=603/603`
- `product_kpi_depth=234/603`
- `product_spec_depth=1/603`
- `customer_deployment_depth=158/603`
- `capital_market_detail_depth=247/603`
- `backfill_queue_count=1772`

Backfill gap 结构：

- `product_spec_depth::product_spec_parser_depth_gap=466`
- `product_spec_depth::product_spec_source_or_parser_gap=136`
- `customer_deployment_depth::customer_deployment_public_source_gap=445`
- `capital_market_detail_depth::capital_market_event_parser_or_coverage_gap=340`
- `capital_market_detail_depth::capital_market_detail_source_gap=16`
- `product_kpi_depth::official_product_surface_available_but_company_disclosed_product_kpi_absent=270`
- `product_kpi_depth::filings_taxonomy_available_but_value_unit_period_product_kpi_absent=97`
- `product_kpi_depth::product_context_available_but_no_company_disclosed_product_kpi_exact_slot=1`
- `product_kpi_depth::product_kpi_slot_without_value_unit_period_runtime_row=1`

市场流动性边界：

- 当前 `market_liquidity_driver` 只覆盖 Yahoo chart price/volume/volatility/relative return 基线。
- 不覆盖 short interest、options IV、ETF/factor flow、credit spread、fund flow、实时资金流或估值倍数。
- Yahoo chart 是免费公开非官方端点，作为 market liquidity context 可以入 evidence bundle，但不能证明经营事实、产品需求、资金流入或产品销量。

## 验证

- `python scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`
- `python scripts/data_expansion/build_market_liquidity_driver_context_rows.py --market-evidence data/processed_private/market/evidence_packs/20260624_market_yahoo_chart_603_3m_v1_3m_market_evidence.jsonl`
- `python -m pytest tests/test_second_third_layer_depth_parity_matrix.py tests/test_market_liquidity_driver_context_rows.py tests/test_market_snapshot_fixture.py -q`
- `python -m py_compile src/sec_agent/layer_acceptance_gates.py src/sec_agent/market_snapshot.py scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py scripts/data_expansion/build_market_liquidity_driver_context_rows.py scripts/market/10_normalize_market_snapshot_fixture.py`

## 后续

下一轮按缺口规模和对研报质量影响排序：

1. R32：补 `product_spec_depth`，先做 family-specific technical spec parsers。普通产品页不能算强规格。
2. R33：补 `customer_deployment_depth`，官方客户部署、订单、供应链官方关系、公开采购和 deployment proxy 分 route 接入。
3. R34：补 `capital_market_detail_depth`，offering / Form 3/4/5 / 13D/G / proxy / N-PORT / short interest / options / ETF / credit spread source-specific parsers。
4. R35：补 Product-KPI value parser；公开源不披露时继续暴露 public-source/commercial-tracker gap，不用 weak proxy 填平。
