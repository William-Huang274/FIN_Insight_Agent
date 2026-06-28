# R39 Product-KPI / CustomerDeployment / Capital Depth Repair

## Prompt

继续修第二层、第三层剩余缺口，按 Product-KPI parser/filing gap、CustomerDeployment gap、Capital gap 的顺序做；能修能提权的做完，剩下的必须是公开源边界、公司未披露、商业 tracker gap 或明确的 source-specific parser debt。

## Decision

本轮不把 ordinary revenue、business segment revenue、macro bridge、财务三表行、attempt row 或表格邻近行拿来填 CustomerDeployment / Product-KPI / Capital gap。Product-KPI 中“公开披露存在但不能提权”的行必须从 true parser/schema gap 中拆开，否则后续会继续浪费时间修不可修的 parser。

## Work Completed

- 修复 `scripts/data_expansion/build_industry_operating_metric_slot_rows.py`：
  - 新增 forbidden operating context gate，拒绝 cash-flow investing/financing rows、expense table、tax/non-GAAP bridge、FX/acquisition/divestiture bridge、production payment obligation。
  - business-segment revenue 增加 fiscal period / column binding gate，拒绝 `(dollars in millions)` 等单位列和错期列。
  - 新增 `marketplace_gross_order_value` operating slot，仅当 `row_label/product_or_segment/column_label` 本体命中 Marketplace GOV / GMV / gross order value 时提权。
  - 修复 DASH false positive：citation/table 中出现 Marketplace GOV 不能让 `Adjusted EBITDA`、`GAAP gross profit`、`Contribution Profit`、diluted shares 等邻近行提权。
- 修复 `src/sec_agent/layer_acceptance_gates.py`：
  - 将 `marketplace_gross_order_value` 加入 Product/Business-KPI depth 和 operating-footprint 识别白名单，保留 forbidden-claim boundary。
- 修复 `scripts/data_expansion/build_second_third_layer_depth_gap_action_plan.py`：
  - `value_unit_period` Product-KPI gap 现在区分：
    - `company_disclosure_value_candidate_absent_or_locator_gap`
    - `non_promotable_public_disclosure_boundary`
    - `source_specific_table_relation_parser_gap`
  - Segment Orders 行保留为 true parser/schema gap；geography、投资现金流、费用、税/FX/non-GAAP bridge、generic total/contract revenue、production payment obligation 归 public disclosure boundary。
- 更新 deterministic tests：
  - `tests/test_industry_operating_metric_slot_rows.py`
  - `tests/test_second_third_layer_depth_gap_action_plan.py`
  - `tests/test_second_third_layer_depth_parity_matrix.py`

## Results

- `industry_operating_metric_slot_rows_v0_1`：
  - `runtime_row_count=1,919`
  - `runtime_ticker_count=185`
  - `marketplace_gross_order_value=3`
  - `unclassified_rejection_count=0`
- `second_third_layer_depth_parity_summary_v0_1`：
  - ProductSpec/Profile `603/603`
  - Product/Business-KPI `441/603`
  - CustomerDeployment `531/603`
  - CapitalMarketDetail `601/603`
  - MarketLiquidity `603/603`
  - full five-dimension parity `398/603`
  - backfill queue `236`
- `second_third_layer_depth_parity_gap_action_plan_summary_v0_1`：
  - Product-KPI `162`
  - CustomerDeployment `72`
  - CapitalMarketDetail `2`
  - source gap types:
    - `source_specific_table_relation_parser_gap=2`
    - `non_promotable_public_disclosure_boundary=11`
    - `company_disclosure_value_candidate_absent_or_locator_gap=23`
    - `classified_public_boundary_or_deep_adapter_gap=122`
    - `classified_product_kpi_boundary_or_deep_adapter_gap=4`
    - `source_locator_or_materialization_gap=73`
    - `parser_or_join_gap=1`
- Remaining true Product-KPI parser/schema gaps:
  - `CME`: Other revenues / licensing fee table still needs source-specific column-group parser.
  - `IR`: Segment Orders has two segment values but lost segment label; needs segment dimension/schema repair.
- CustomerDeployment remaining `72`:
  - Every row has some nonpassing context, but only macro/FRED/EIA/OpenAlex, SEC financial statement rows, product revenue, business segment revenue, or generic official API bridge rows.
  - No accepted issuer-bound customer/order/deployment/channel adoption/regulated identity/contract liability/operating-footprint row exists.
- Capital remaining `2`:
  - `6723.T`: Renesas has only FY2025 revenue, gross profit, operating profit, net income rows; no BS/CF/debt/cash/capex/capital detail row.
  - `FDXF`: has FedEx Freight segment operating income and Form 4 metadata only; no standalone debt/credit/working-capital/capital detail row, and FDX parent capital structure is not inherited.

## Verification

- `python -m pytest tests/test_industry_operating_metric_slot_rows.py tests/test_second_third_layer_depth_gap_action_plan.py tests/test_second_third_layer_depth_parity_matrix.py -q` -> `38 passed`
- `python scripts\data_expansion\build_industry_operating_metric_slot_rows.py` -> `status=pass`
- `python scripts\data_expansion\build_second_third_layer_depth_parity_matrix.py` -> `status=pass`, `parity_status=fail`
- `python scripts\data_expansion\build_second_third_layer_real_source_readiness_gate.py` -> `status=pass`, `603/603`
- `python scripts\data_expansion\build_second_third_layer_depth_gap_action_plan.py` -> `status=pass`

## Follow-Up

- Do not spend another broad parser pass on the `11` non-promotable public disclosure boundary tickers unless a new source route appears.
- If continuing Product-KPI parser repair, target only `CME` and `IR` first.
- If continuing CustomerDeployment, do not broaden acceptance; add actual issuer-bound customer/order/deployment/channel/regulated/contract-liability/operating-footprint sources or expose public-source/commercial gaps.
- If continuing Capital, `6723.T` needs deeper Renesas annual securities report / local filing BS-CF-capital parser; `FDXF` needs standalone issuer/entity policy or explicit parent-child inheritance policy before any capital detail can be accepted.
