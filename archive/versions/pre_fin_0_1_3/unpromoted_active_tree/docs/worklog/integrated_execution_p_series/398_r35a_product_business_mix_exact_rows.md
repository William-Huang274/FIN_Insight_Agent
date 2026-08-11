# 398 R35a Product Business Mix Exact Rows

## 问题

R32c 后 ProductSpec/Profile 已达到 `603/603`，但 Product/Business-KPI depth 仍只有 `400/603`。继续审计发现，很多被旧 verifier 拒绝的 percentage rows 其实不是增长率或 margin，而是公司披露的产品/业务收入结构占比，例如按 end market、business line、segment 披露的 `% of revenue`。这些信息不能证明绝对产品收入，但可以支持业务结构、产品组合和暴露方向判断。

同时，`product_kpi_exact_slot_closeout_v0_1` 存在一个 false-ready 问题：只要 `company_product_slots` 里有 `product_kpi_exact_slot`，即使没有 runtime value row，也会被标成 `product_kpi_exact_ready`。AMT 就是这种情况。

## 判断

收入结构占比应作为 bounded exact metric 进入 Product/Business-KPI depth，但必须有明确边界：

- 可以支持：公司披露的产品/业务 revenue mix percent。
- 不可以支持：绝对产品收入、ASP、销量、出货、市占率、sell-through、backlog、订单金额、commercial tracker estimates。

slot-only 不能成为 Product-KPI ready；必须有 value/unit/period/product/citation runtime row。

## 已完成

- 新增 `scripts/data_expansion/build_company_disclosed_product_business_mix_runtime_rows.py`。
- 新增 runtime rows：
  - `data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl`
  - `data/manifests/company_disclosed_product_business_mix_summary_v0_1.json`
- 修复 `scripts/data_expansion/build_product_kpi_source_specific_verifier.py`，保留 `product_link_method` / `product_link_score`，避免后续 projector 无法判断结构化产品绑定。
- 修复 `scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py`：
  - 只有 runtime exact rows 才能标记 `product_kpi_exact_ready`。
  - closeout 输入新增 `company_disclosed_product_business_mix_runtime_rows_v0_1` 和 `industry_operating_metric_slot_rows_v0_1`。
- 更新 `src/sec_agent/layer_acceptance_gates.py` 和 `build_second_third_layer_depth_parity_matrix.py`，让新 revenue-mix rows 进入 Product/Business-KPI depth。
- 更新 `build_second_third_layer_depth_gap_action_plan.py`，Product-KPI action rows 现在带 `product_kpi_verifier_candidate_count` 和 `product_kpi_verifier_top_reasons`，并区分：
  - `source_specific_table_relation_parser_gap`
  - `company_disclosure_value_candidate_absent_or_locator_gap`
  - `classified_public_boundary_or_deep_adapter_gap`
  - `classified_product_kpi_boundary_or_deep_adapter_gap`

## 结果

`company_disclosed_product_business_mix_summary_v0_1`：

- `runtime_row_count=1,174`
- `runtime_ticker_count=70`
- `structured_context_type=company_disclosed_product_business_mix_percent_fact`
- `source_role=company_disclosed_product_kpi`

`exact_slot_gap_closeout_summary_v0_1`：

- `runtime_product_kpi_ticker_count=428`
- `product_or_business_kpi_ready_ticker_count=280`
- `product_kpi_exact_ready=129`
- `business_segment_metric_ready=151`
- `geographic_or_non_product_metric_only=148`
- `product_kpi_exact_gap=175`
- `unclassified_closeout_count=0`

`second_third_layer_depth_parity_summary_v0_1`：

- `product_kpi_depth=428/603`
- `product_spec_depth=603/603`
- `customer_deployment_depth=158/603`
- `capital_market_detail_depth=247/603`
- `market_liquidity_depth=603/603`
- full five-dimension parity `53/603`
- backfill queue `976`

Product-KPI remaining gaps：

- `filings_taxonomy_available_but_value_unit_period_product_kpi_absent=45`
- `official_product_surface_available_but_company_disclosed_product_kpi_absent=129`
- `product_context_available_but_no_company_disclosed_product_kpi_exact_slot=1`

Action-plan source-gap split：

- `source_specific_table_relation_parser_gap=22`
- `company_disclosure_value_candidate_absent_or_locator_gap=23`
- `classified_public_boundary_or_deep_adapter_gap=129`
- `classified_product_kpi_boundary_or_deep_adapter_gap=1`

## 边界

本轮新增 rows 是 revenue-mix exact，不是 revenue exact。Memo / specialist 可写“公司披露某业务/产品占收入比例”，不得写成：

- 该产品绝对收入；
- 该产品销量或 ASP；
- 市占率；
- sell-through；
- backlog；
- 客户订单金额；
- 商业 tracker 估算。

剩余 `22` 个 source-specific table relation parser gap 需要更细的 table coordinate / column group / period parser。抽样显示 MTD、CME、CRL、DOC 等存在混表、列组、period 或 row-label 绑定问题，不能通过放宽 conflict gate 提权。

## 验收

- `python -m pytest tests/test_company_disclosed_product_business_mix_runtime_rows.py tests/test_product_kpi_source_specific_verifier.py tests/test_exact_slot_gap_closeout_ledger.py tests/test_second_third_layer_depth_gap_action_plan.py tests/test_second_third_layer_depth_parity_matrix.py -q`
- `python scripts/data_expansion/build_product_kpi_source_specific_verifier.py --strict`
- `python scripts/data_expansion/build_company_disclosed_product_business_mix_runtime_rows.py --strict`
- `python scripts/data_expansion/build_industry_operating_metric_slot_rows.py --strict`
- `python scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py --strict`
- `python scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py`
- `python scripts/data_expansion/build_second_third_layer_depth_gap_action_plan.py`

## 下一步

1. Product-KPI：针对 `22` 家 source-specific table relation parser gap 做 table coordinate / column group / period parser；对 `23` 家 candidate-absent gap 做 IR deck / annual report / local filing locator 复查。
2. CustomerDeployment：补 `445` 家官方客户部署、订单、供应链官方关系、公开采购或 deployment proxy。
3. CapitalMarketDetail：补 `356` 家 offering / ownership / insider / proxy / short interest / credit spread 等资本市场细项。
