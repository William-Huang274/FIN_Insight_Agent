# Industry Operating Metric Slot

- schema_version: `finsight_industry_operating_metric_slot_summary_v0_1`
- generated_at: `2026-06-25T15:20:33Z`
- status: `pass`
- runtime_row_count: `1923`
- runtime_ticker_count: `186`
- rejection_count: `7876`
- unclassified_rejection_count: `0`

## Slot Counts

| slot | rows |
| --- | ---: |
| `airline_tickets` | 1 |
| `aum` | 2 |
| `backlog_or_orders` | 22 |
| `business_segment_revenue` | 1730 |
| `capacity_utilization_or_production_volume` | 62 |
| `marketplace_gross_order_value` | 3 |
| `payment_transactions_per_active_account` | 5 |
| `rental_car_days` | 1 |
| `revenue_per_occupied_square_foot` | 2 |
| `room_nights` | 1 |
| `same_store_revenue_growth_component` | 8 |
| `same_store_sales_growth` | 22 |
| `segment_revenue_growth` | 34 |
| `shipments` | 11 |
| `tpv_mix_percent` | 8 |
| `unit_sales_or_deliveries` | 11 |

## Rejection Reasons

| reason | rows |
| --- | ---: |
| `arpu_unit_or_scale_ambiguous` | 30 |
| `backlog_metric_without_backlog_or_order_context` | 853 |
| `business_segment_metric_not_currency_revenue_or_generic_row` | 1184 |
| `business_segment_metric_without_exact_period_column_binding` | 593 |
| `cash_flow_table_not_industry_operating_slot` | 45 |
| `conflict_resolved_non_aggregate_sibling` | 314 |
| `conflicting_values_for_industry_operating_claim` | 1754 |
| `currency_or_acquisition_bridge_not_operating_slot` | 104 |
| `duplicate_industry_operating_claim` | 1968 |
| `expense_table_not_industry_operating_slot` | 112 |
| `mislabeled_operating_metric_without_exact_period_column_binding` | 3 |
| `non_positive_value` | 98 |
| `production_metric_without_capacity_or_throughput_context` | 441 |
| `production_payment_obligation_not_production_volume` | 2 |
| `region_only_not_industry_operating_slot` | 156 |
| `same_store_metric_without_comparable_store_context` | 59 |
| `shipment_metric_without_shipment_context` | 9 |
| `subscriber_metric_without_subscriber_arr_arpu_context` | 7 |
| `tax_or_non_gaap_bridge_not_industry_operating_slot` | 102 |
| `unit_sales_metric_without_unit_delivery_context` | 42 |

## Boundary

Industry operating metric exact slots are separate from Product-KPI exact. They may support business mix, capacity, backlog, deliveries, subscribers, ARPU/ARR/RPO, same-store growth, or financial-services operating metrics only when company-disclosed value/unit/period/citation are present.
