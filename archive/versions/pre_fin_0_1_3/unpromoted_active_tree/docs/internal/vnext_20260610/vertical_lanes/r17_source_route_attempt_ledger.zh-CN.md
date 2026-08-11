# R17 Source Route Attempt Ledger

- schema_version: `finsight_source_route_attempt_ledger_summary_v0_1`
- generated_at: `2026-06-22T15:31:35Z`
- status: `action_required`
- row_count: `718`
- action_required_count: `303`
- final_boundary_blocked_count: `303`
- known_public_current_contract_failure_count: `0`
- known_public_new_contract_required_count: `0`

## Gate Status Counts

```json
{
  "attempt_backed_public_boundary": 73,
  "canary_covered": 7,
  "not_applicable_or_source_gap": 1,
  "not_product_kpi_boundary": 109,
  "ready": 135,
  "ready_but_not_product_kpi": 90,
  "reroute_required": 139,
  "route_or_parser_debt": 160,
  "source_route_retry_required": 4
}
```

## Top Action Required Reasons

```json
{
  "Closeout includes retryable fetch/parser status: fetch_failed": 3,
  "Closeout includes retryable fetch/parser status: unusable_response": 1,
  "Closeout still requires route/parser/resolver repair: no_verified_project_to_issuer_product_resolver_for_broad_developer_artifacts": 13,
  "Closeout still requires route/parser/resolver repair: patentsview_api_key_missing_or_patentsearch_unavailable": 17,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_business_segment_metric:business_segment_candidate_without_source_specific_segment_table_context": 89,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_business_segment_metric:business_segment_candidate_without_source_specific_segment_table_context;final_quality_gate:sentence_local_verifier_local_product_value_relation_not_verified": 5,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_business_segment_metric:company_disclosed_business_segment_revenue_candidate": 8,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_operating_metric_defer_step2:business_segment_candidate_without_source_specific_segment_table_context": 4,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_operating_metric_defer_step2:metric_family_backlog_or_orders_requires_industry_operating_metric_slot": 9,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_operating_metric_defer_step2:metric_family_production_or_throughput_requires_industry_operating_metric_slot": 11,
  "Fact is useful but must be rerouted outside Product-KPI exact: source_specific_verifier_operating_metric_defer_step2:metric_family_same_store_sales_requires_industry_operating_metric_slot": 3,
  "Product KPI source route/parser debt remains: product_taxonomy_or_official_surface_exists_but_current_disclosure_scan_found_no_product_kpi_candidate": 104,
  "Product KPI source route/parser debt remains: source_specific_verifier_business_segment_mixed_table_needs_column_group:segment_table_contains_mixed_financial_columns": 8,
  "Product KPI source route/parser debt remains: source_specific_verifier_period_or_version_conflict:period_after_fiscal_year": 4,
  "Product KPI source route/parser debt remains: source_specific_verifier_sentence_relation_insufficient:missing_table_coordinates_or_exact_row_binding": 5
}
```

## Policy

R17 ledger is an audit/control artifact. Rows with parser/source-route debt must be repaired or explicitly closed before they are treated as final public-source boundaries. Known-public canaries prevent disclosed facts from being hidden behind generic gap labels.
