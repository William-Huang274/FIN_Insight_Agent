# R15 Product-KPI Exhaustion Attempts

- generated_at: `2026-06-20T18:04:26Z`
- status: `pass`
- row_count: `139`
- terminal_boundary_row_count: `139`
- pending_without_boundary_count: `0`

## By Cluster

| cluster | count |
| --- | ---: |
| `product_kpi_column_group_schema_verifier` | 18 |
| `product_kpi_ir_deck_annual_report_locator` | 101 |
| `product_kpi_non_us_ir_local_exchange_parser` | 4 |
| `product_kpi_period_version_schema_verifier` | 7 |
| `product_kpi_sentence_relation_verifier` | 9 |

## By Status

| status | count |
| --- | ---: |
| `local_exchange_or_ir_reports_parsed_no_promotable_product_kpi` | 4 |
| `local_product_value_relation_not_verified` | 9 |
| `mixed_segment_table_column_group_not_promotable_to_product_kpi_exact` | 18 |
| `no_company_disclosed_product_kpi_candidate_after_public_disclosure_scan` | 101 |
| `period_or_version_conflict_not_promotable` | 7 |

## By Diagnostic Class

| diagnostic_class | count |
| --- | ---: |
| `non_us_local_or_ir_parser_required` | 4 |
| `product_surface_or_taxonomy_available_no_company_kpi_candidate` | 101 |
| `verifier_business_segment_column_group_required` | 18 |
| `verifier_period_or_version_conflict` | 7 |
| `verifier_sentence_relation_insufficient` | 9 |
