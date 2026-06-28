# R16 Product-KPI / Source Adapter Deep Repair

- schema_version: `finsight_r16_product_kpi_deep_repair_summary_v0_1`
- generated_at: `2026-06-20T19:26:29Z`
- status: `pass`
- runtime_row_count: `76`
- runtime_ticker_count: `8`
- product_kpi_exact_repair_row_count: `52`
- business_segment_metric_repair_row_count: `12`
- operating_metric_repair_row_count: `12`
- attempt_row_count: `1088`

## Runtime Actions

| action | count |
| --- | ---: |
| `promote_product_kpi_exact` | 52 |
| `reroute_business_segment_metric` | 12 |
| `reroute_operating_metric` | 12 |

## Attempt Status

| status | count |
| --- | ---: |
| `business_segment_metric_rerouted` | 51 |
| `column_group_boundary` | 337 |
| `credential_bound_gap` | 17 |
| `currency_or_unit_mismatch` | 16 |
| `future_obligation_or_backlog_metric` | 24 |
| `geographic_only` | 48 |
| `non_product_or_total` | 352 |
| `non_us_disclosure_parsed_no_promotable_exact_product_kpi` | 4 |
| `percentage_or_change` | 58 |
| `period_version_boundary` | 79 |
| `product_line_metric_promoted` | 95 |
| `structured_field_gap` | 7 |

## Boundary Reasons

| reason | count |
| --- | ---: |
| `citation_currency_conflicts_with_normalized_unit` | 16 |
| `company_disclosed_business_segment_or_service_line_value_unit_period_verified` | 51 |
| `company_disclosed_product_or_product_line_value_unit_period_verified` | 95 |
| `future_or_versioned_period_not_current_product_kpi` | 79 |
| `future_period_column_is_operating_obligation_not_current_product_revenue` | 24 |
| `geographic_row_not_product_or_business_metric` | 48 |
| `missing_value_unit_period_product_or_citation` | 7 |
| `mixed_table_column_group_not_safely_promotable` | 337 |
| `patentsview_api_key_not_configured` | 17 |
| `percentage_change_or_margin_cell_not_level_fact` | 58 |
| `public_report_has_geographic_rows_but_no_product_kpi` | 2 |
| `public_report_has_mix_or_percentage_but_no_exact_product_value` | 2 |
| `total_non_product_or_non_operating_row` | 352 |

## Boundary

R16 rows are parser-backed company-disclosed exact rows only when value/unit/period/product/citation relation is verified. Business segment and operating rows are routed as company-disclosed operating facts, not SKU/product-family proof. Boundary attempts are not evidence.
