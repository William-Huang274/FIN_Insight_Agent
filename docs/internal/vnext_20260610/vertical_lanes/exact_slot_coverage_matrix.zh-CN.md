# Exact Slot Coverage Matrix

- schema_version: `finsight_exact_slot_coverage_matrix_v0_1`
- generated_at: `2026-06-23T18:53:38Z`
- status: `gap`
- company_count: `603`
- all_required_exact_ready_company_count: `578`
- partial_exact_ready_company_count: `25`
- no_exact_ready_company_count: `0`
- exact_slot_gap_count: `25`

## Requirement Summary

| requirement | exact ready | gaps | rejected attempts |
| --- | ---: | ---: | ---: |
| app_rank_store_proxy | 56 | 0 | 0 |
| auto_product_identity_context | 12 | 0 | 22 |
| channel_offer_proxy | 62 | 0 | 0 |
| developer_ecosystem_proxy | 64 | 0 | 5 |
| energy_utility_context | 111 | 0 | 5 |
| financial_regulatory_context | 77 | 0 | 4 |
| hiring_capacity_proxy | 66 | 0 | 3 |
| macro_official_context | 249 | 0 | 12 |
| official_customer_order_or_deployment_event | 26 | 0 | 0 |
| official_product_surface | 559 | 0 | 1387 |
| platform_review_proxy | 58 | 0 | 2 |
| primary_company_disclosure | 603 | 0 | 0 |
| public_order_proxy | 134 | 25 | 10 |
| regulated_product_context | 60 | 0 | 0 |
| supply_chain_official_relationship | 21 | 0 | 0 |
| technology_research_proxy | 78 | 0 | 6 |
| trusted_external_context | 453 | 0 | 47 |

## Gap Class Summary

| gap_class | count |
| --- | ---: |
| source_gap | 25 |

## Boundary

A requirement passes this matrix only when at least one parser-backed exact slot row exists for the company and requirement. L2/L3 exact slots are exact snapshots/proxies and remain blocked from company revenue/share/shipment/sales promotion.
