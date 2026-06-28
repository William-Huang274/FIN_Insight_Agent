# Non-US Product-KPI Local Disclosure Runtime Rows

- Generated at: `2026-06-20T17:57:39Z`
- Status: `pass`
- Target tickers: `15`
- Runtime rows: `70`
- Runtime ticker coverage: `11/15`
- Metric families: `{"backlog_or_orders": 2, "product_gross_margin": 8, "product_revenue": 18, "segment_revenue": 26, "segment_sales": 6, "shipment_value": 1, "shipments": 9}`
- Product node types: `{"business_line": 32, "product_family": 38}`
- Parser counts: `{"eu_annual_report_segment_revenue_table_parser_v0_1": 10, "hkex_operating_segment_external_revenue_table_parser_v0_1": 2, "jp_ir_disco_shipment_value_sentence_parser_v0_1": 1, "jp_ir_integrated_report_advantest_segment_sales_panel_parser_v0_1": 2, "jp_ir_integrated_report_segment_sales_panel_parser_v0_1": 4, "kr_dart_major_product_sales_table_parser_v0_1": 12, "kr_dart_semiconductor_business_segment_table_parser_v0_1": 2, "official_company_news_lges_product_order_backlog_parser_v0_1": 2, "szse_cninfo_product_revenue_cost_margin_table_parser_v0_1": 8, "szse_cninfo_product_revenue_table_parser_v0_1": 8, "tw_mops_product_sales_volume_value_table_parser_v0_1": 16, "tw_mops_quanta_notebook_shipment_sentence_parser_v0_1": 3}`
- Rejection reasons: `{"geographic_or_region_only_no_product_kpi": 10, "no_product_kpi_exact_table_pattern": 1, "percentage_or_mix_only_no_exact_product_value": 13, "product_or_segment_description_without_exact_value_row": 1, "stale_document_year_mismatch": 1}`
- Uncovered tickers: `["2308.TW", "2317.TW", "6723.T", "8035.T"]`

## Boundary

Rows are L1 company/local-exchange disclosed exact product or segment metrics. Percentage-only, region-only, stale document, and text-only product descriptions remain rejected attempts.
