# Product-KPI Deep Gap Diagnostic

- Generated at: `2026-06-25T03:11:08Z`
- Companies: `603`
- Product KPI statuses: `{"business_segment_metric_ready": 151, "geographic_or_non_product_metric_only": 148, "product_kpi_exact_gap": 175, "product_kpi_exact_ready": 129}`
- Coverage buckets: `{"business_or_segment_exact_ready": 151, "business_segment_candidates_not_product_family_kpi": 7, "candidate_exists_but_not_promotable": 1, "generic_total_or_non_product_rows_not_product_kpi": 6, "geographic_or_non_product_metric_not_product_kpi": 148, "mixed_segment_table_requires_column_group_schema": 4, "operating_metric_candidates_require_industry_slot": 17, "percentage_or_change_cells_not_level_revenue": 22, "period_or_restatement_conflict_requires_versioned_schema": 2, "product_family_or_product_line_exact_ready": 129, "region_geography_candidates_not_product_kpi": 7, "sentence_or_unstructured_candidate_needs_local_relation_verifier": 5, "surface_or_taxonomy_only_no_kpi_candidate": 104}`
- Product family exact ready tickers: `129`
- Business/segment exact ready tickers: `151`
- Product or business KPI ready tickers: `280`
- Gap diagnostic classes: `{"non_us_local_or_ir_parser_required": 4, "parser_candidate_found_but_not_runtime_promotable": 1, "product_surface_or_taxonomy_available_no_company_kpi_candidate": 100, "verifier_business_segment_column_group_required": 4, "verifier_business_segment_only_candidates": 7, "verifier_non_product_or_total_candidates": 6, "verifier_operating_metric_requires_industry_slot": 17, "verifier_percentage_or_change_only_candidates": 22, "verifier_period_or_version_conflict": 2, "verifier_region_or_geography_only_candidates": 7, "verifier_sentence_relation_insufficient": 5}`
- Strict-candidate gap tickers: `71`
- No-candidate gap tickers: `104`

## Boundary

This diagnostic separates company-disclosed product KPI coverage, rejected parser candidates, and public/commercial gaps. It does not promote any row by itself.
