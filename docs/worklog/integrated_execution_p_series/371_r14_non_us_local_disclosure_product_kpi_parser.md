# 371 R14 Non-US Local Disclosure Product-KPI Parser

Date: 2026-06-19

## Scope

This entry closes Step 3 in the user-defined 1-6 sequence:

1. Product-KPI source-specific verifier.
2. Industry operating metric slots.
3. Non-US local disclosure Product-KPI parser.

The goal was to repair `product_kpi_non_us_ir_local_exchange_parser` without weakening Product-KPI exact-slot authority. Rows must come from company/local-exchange/official disclosure paths and must carry `value`, `unit`, `period`, `product_or_segment`, and `citation`.

## Implementation

Added `scripts/data_expansion/build_non_us_product_kpi_local_disclosure_runtime_rows.py`.

The builder:

- reads target tickers from `company_gap_docket_v0_1`;
- merges existing non-US coverage manifests with manual official issuer reports;
- optionally downloads official reports/pages into the Z-drive staging area;
- parses DART, HKEX, CNINFO, TW MOPS, JP IR, EU annual report, and official company news rows;
- writes accepted L1 exact rows and rejected attempts separately;
- rejects percentage/mix-only, region-only, stale, text-only, and no-exact-table candidates.

Added tests in `tests/test_non_us_product_kpi_local_disclosure_runtime_rows.py`, including:

- SK hynix KR DART semiconductor segment revenue;
- Samsung major product/segment sales;
- BYD HKEX external segment revenue;
- CATL CNINFO product revenue and product gross margin;
- Infineon annual report segment revenue;
- Panasonic / Advantest segment sales;
- Wistron TW MOPS product volume/value rows;
- Quanta notebook shipments;
- DISCO shipment value;
- LG Energy Solution official ESS backlog and 46-Series new-contract rows, while refusing threshold-only `exceeds` language.

Updated downstream consumers:

- `scripts/data_expansion/build_exact_slot_coverage_matrix.py` now reads `non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl`.
- `scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py` now accepts multiple runtime row paths and treats repaired runtime rows as authoritative state before old closeout labels.
- `scripts/data_expansion/build_company_gap_docket.py` consumes the refreshed diagnostic output; no code change was needed after sequential rerun, but the diagnostic race was documented.

## Runtime Results

`python scripts\data_expansion\build_non_us_product_kpi_local_disclosure_runtime_rows.py --download-official-reports --strict`

- `target_ticker_count=15`
- `candidate_ticker_count=15`
- `runtime_row_count=70`
- `runtime_ticker_count=11`
- `covered_target_ticker_count=11`
- `uncovered_target_ticker_count=4`
- `unclassified_rejection_count=0`

Metric counts:

- `segment_revenue=26`
- `product_revenue=18`
- `product_gross_margin=8`
- `segment_sales=6`
- `shipments=9`
- `shipment_value=1`
- `backlog_or_orders=2`

The parser added LG Energy Solution official order/backlog rows from the issuer news release:

- ESS battery order backlog: `120 GWh`
- 46-Series cylindrical battery new contracts: `107 GWh`

Threshold-only language such as `exceeds 300GWh` is not promoted.

## Remaining Non-US Product-KPI Gaps

Only four target tickers remain in `product_kpi_non_us_ir_local_exchange_parser`:

- `2308.TW` Delta Electronics: current public disclosure exposes product/business mix percentages, but no direct product/segment exact value row. Derived `total revenue x mix` is not allowed.
- `2317.TW` Hon Hai Precision: company disclosures expose total revenue and product category mix percentages, but no direct product category revenue/shipment exact row.
- `6723.T` Renesas: official results pages and disclosures provide directional segment commentary, but no exact Automotive / Industrial / Infrastructure / IoT amount in the current parser scope.
- `8035.T` Tokyo Electron: current integrated report product-category net sales rows are dashes for the current year; older product tables are stale and rejected.

These are not silent crawler/parser misses in this tranche. They remain open only if a later IR table/local filing locator finds direct exact rows.

## Downstream State

`python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict`

- `product_family_exact_ready_ticker_count=133`
- `business_or_segment_exact_ready_ticker_count=83`
- `product_or_business_kpi_ready_ticker_count=216`
- `product_kpi_exact_gap=377`
- `non_us_local_or_ir_parser_required=4`
- `unclassified_count=0`

The lower product-family count versus the previous v0.5 summary is intentional: diagnostic now classifies by actual runtime row `product_node_type`, so business-line/segment rows are not counted as product-family exact.

`python scripts\data_expansion\build_company_gap_docket.py --strict`

- `docket_count=580`
- `source_role_gap_docket_count=203`
- `product_kpi_gap_docket_count=377`
- `product_kpi_non_us_ir_local_exchange_parser=4`
- `unclassified_docket_count=0`

## Verification

Passed:

- `python -m pytest tests\test_non_us_product_kpi_local_disclosure_runtime_rows.py -q`
- `python -m py_compile scripts\data_expansion\build_non_us_product_kpi_local_disclosure_runtime_rows.py`
- `python scripts\data_expansion\build_non_us_product_kpi_local_disclosure_runtime_rows.py --download-official-reports --strict`
- `python -m pytest tests\test_product_kpi_deep_gap_diagnostic.py tests\test_non_us_product_kpi_local_disclosure_runtime_rows.py -q`
- `python -m py_compile scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py scripts\data_expansion\build_non_us_product_kpi_local_disclosure_runtime_rows.py`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict`
- `python scripts\data_expansion\build_company_gap_docket.py --strict`
- `python -m pytest tests\test_non_us_product_kpi_local_disclosure_runtime_rows.py tests\test_non_us_l1_financial_statement_metric_runtime_rows.py tests\test_exact_slot_contracts.py tests\test_product_kpi_deep_gap_diagnostic.py tests\test_company_gap_docket.py -q`

## Next

Proceed to Step 4 only after this step remains clean under final `git diff --check`.

Step 4 target: channel / distributor family adapters, starting with semiconductor components through Digi-Key / Mouser / Arrow and consumer/retail routes through Amazon / JD / official stores, while preserving the boundary that channel offers do not prove ASP, sell-through, inventory, revenue, or market share.
