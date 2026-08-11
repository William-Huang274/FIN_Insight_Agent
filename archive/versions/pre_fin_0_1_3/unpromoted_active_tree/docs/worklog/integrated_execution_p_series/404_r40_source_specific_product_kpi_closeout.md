# R40 Source-Specific Product-KPI Closeout

## Prompt

继续收口 R39 剩余的 true Product-KPI parser/schema gaps，先修 `CME` / `IR`，再复核 CustomerDeployment 72 和 Capital 2 是否还有 gate 漏接或可公开补齐的数据。

## Decision

本轮不把旧的错列 verifier rows 直接放宽提权。`IR` 的 Segment Orders 和 `CME` 的 Cash Markets transaction fees 都必须回到 SEC 原文表验证 segment/title、year column、value scale 和 citation 后再生成 runtime rows；旧错误候选保留为 rejected 或 boundary rows。

## Work Completed

- `scripts/data_expansion/build_product_kpi_source_specific_verifier.py`
  - 新增 SEC source-specific backfill scanner，只在候选中出现明确表信号时抓同一 SEC HTML。
  - `IR`：从 SEC Segment Results 表抽出 `Industrial Technologies and Services`、`Precision and Science Technologies` 的 `Segment Orders`，修复原 verifier 丢 segment label 且把 2024 值误标 2025 的问题。
  - `CME`：从 Cash Markets Business table 抽出 `BrokerTec fixed income transaction fees` 和 `EBS foreign exchange transaction fees`，按 millions 缩放成 USD amount，避免原 verifier 把 `132.6` 误缩放到 billions。
  - 新 rows 带 `source_specific_parser`，旧 rows 不因同表 citation 自动提权。
- `scripts/data_expansion/build_company_disclosed_product_business_mix_runtime_rows.py`
  - 扩展 runtime projector：除 revenue-mix percent 外，也允许 verifier 已判定 `promotable_product_category_or_product_line_metric` 的 company-disclosed product/business-line revenue amount rows 进入 runtime。
  - claim boundary 明确禁止把 line-item revenue 写成 ASP、shipment volume、market share、sell-through、backlog、customer order value 或 commercial tracker proof。
- 新增/更新 deterministic tests：
  - `tests/test_product_kpi_source_specific_verifier.py`
  - `tests/test_company_disclosed_product_business_mix_runtime_rows.py`

## Results

- `product_kpi_source_specific_verifier_v0_1`：
  - `candidate_count=21,838`
  - `promotable_product_metric_count=12`
  - `unclassified_candidate_count=0`
  - 12 条 promotable rows 全部为 `CME` Cash Markets Business transaction-fee table 的 source-specific corrected rows。
- `company_disclosed_product_business_mix_runtime_rows_v0_1`：
  - `runtime_row_count=1,186`
  - `runtime_ticker_count=71`
  - `company_disclosed_product_business_mix_percent_fact=1,174`
  - `company_disclosed_product_business_revenue_amount_fact=12`
- `industry_operating_metric_slot_rows_v0_1`：
  - `runtime_row_count=1,923`
  - `runtime_ticker_count=186`
  - `backlog_or_orders=22`
  - `IR` now has 4 accepted Segment Orders rows: two segments x FY2024/FY2025.
- `second_third_layer_depth_parity_summary_v0_1`：
  - ProductSpec/Profile `603/603`
  - Product/Business-KPI `443/603`
  - CustomerDeployment `531/603`
  - CapitalMarketDetail `601/603`
  - MarketLiquidity `603/603`
  - full five-dimension parity `400/603`
  - backfill queue `234`
- `second_third_layer_depth_parity_gap_action_plan_summary_v0_1`：
  - `source_specific_table_relation_parser_gap=0`
  - Product-KPI remaining `160`
  - CustomerDeployment remaining `72`
  - CapitalMarketDetail remaining `2`

## Remaining Boundaries

- Product-KPI remaining `160`:
  - `official_product_surface_available_but_company_disclosed_product_kpi_absent=122`
  - `filings_taxonomy_available_but_value_unit_period_product_kpi_absent=34`
  - `non_product_metric_public_boundary=3`
  - `product_context_available_but_no_company_disclosed_product_kpi_exact_slot=1`
  - Source gap type split: `classified_public_boundary_or_deep_adapter_gap=122`, `company_disclosure_value_candidate_absent_or_locator_gap=23`, `non_promotable_public_disclosure_boundary=11`, `classified_product_kpi_boundary_or_deep_adapter_gap=4`.
- CustomerDeployment remaining `72`:
  - All 72 have some raw rows in customer row paths, but these are macro/FRED/EIA/OpenAlex, ordinary SEC financial statement rows, product revenue, or business segment rows.
  - None has accepted issuer-bound customer/order/deployment/channel adoption/regulated identity/contract-liability/operating-footprint row.
  - Current state should be treated as source locator/materialization gap or public-source boundary, not gate漏接.
- Capital remaining `2`:
  - `6723.T`: Renesas current local/non-US parser only produced revenue/profit rows, not BS/CF/debt/cash/capex/capital detail.
  - `FDXF`: standalone issuer has segment operating income and Form 4 metadata only; FDX parent capital structure is not inherited.

## Verification

- `python -m pytest tests/test_company_disclosed_product_business_mix_runtime_rows.py tests/test_product_kpi_source_specific_verifier.py tests/test_industry_operating_metric_slot_rows.py tests/test_second_third_layer_depth_gap_action_plan.py -q` -> `32 passed`
- `python scripts/data_expansion/build_product_kpi_source_specific_verifier.py` -> `status=pass`
- `python scripts/data_expansion/build_industry_operating_metric_slot_rows.py` -> `status=pass`
- `python scripts/data_expansion/build_company_disclosed_product_business_mix_runtime_rows.py` -> `status=pass`
- `python scripts/data_expansion/build_second_third_layer_depth_parity_matrix.py` -> `status=pass`, `parity_status=fail`
- `python scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py` -> `status=pass`, `603/603`
- `python scripts/data_expansion/build_second_third_layer_depth_gap_action_plan.py` -> `status=pass`

## Follow-Up

- Product-KPI no longer has broad source-specific table relation parser debt in the current action plan. Future gains require either new source routes / IR deck / local filing parsers, or acceptance that company-disclosed product KPI exact is not public for those tickers.
- CustomerDeployment can only move if actual issuer-bound customer/order/deployment/channel/adoption/regulatory/contract-liability/operating-footprint rows are found; ordinary financials and macro rows must remain rejected.
- Capital gap requires Renesas non-US BS/CF/capital parser and an explicit FDXF standalone/parent inheritance policy before any further promotion.
