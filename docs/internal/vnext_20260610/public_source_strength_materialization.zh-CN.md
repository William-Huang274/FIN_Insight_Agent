# S5-S0 公开源数据落地矩阵

- 生成时间：`2026-06-11T12:27:33.832507+00:00`
- 已落地 source：`30/32`
- 非美披露 downloaded rows：`47`
- 非美披露 cleaned chars：`24114298`
- SEC structured fact rows：`2790261`
- SEC annual staging chunks：`30600`
- Public normalized snapshot records：`404`
- Industry snapshot observations：`64529`
- Extended materialization records：`8399362`
- EDINET official gap rows：`30`

| Tier | Source | Materialization | Downloaded rows | Inventory rows | Normalized rows | Industry obs | Extended records | SEC fact rows | Official gaps | Runtime status |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| S5_primary_authority | cninfo_portal | materialized_clean_text_parser_gate_pending | 3 | 0 | 0 | 0 | 0 | 0 | 0 | staging_only_parser_citation_boundary_gate_pending |
| S5_primary_authority | company_ir_reports | materialized_clean_text_parser_gate_pending | 11 | 0 | 0 | 0 | 0 | 0 | 0 | staging_only_parser_citation_boundary_gate_pending |
| S5_primary_authority | company_reported_product_operating_metrics | materialized_candidate_metric_parser_gate_pending | 0 | 0 | 0 | 0 | 300 | 0 | 0 | candidate_only_value_unit_period_parser_gate_pending |
| S5_primary_authority | hkexnews_portal | materialized_clean_text_parser_gate_pending | 3 | 0 | 0 | 0 | 0 | 0 | 0 | staging_only_parser_citation_boundary_gate_pending |
| S5_primary_authority | jp_edinet_api | official_source_not_materialized | 0 | 0 | 0 | 0 | 0 | 0 | 30 | blocked_until_next_gate |
| S5_primary_authority | kr_dart_openapi | materialized_clean_text_parser_gate_pending | 18 | 3 | 1 | 0 | 0 | 0 | 0 | staging_only_parser_citation_boundary_gate_pending |
| S5_primary_authority | sec_edgar_apis | materialized_existing_core | 0 | 0 | 50 | 0 | 0 | 2790261 | 0 | runtime_available_through_existing_core_gates |
| S5_primary_authority | sec_financial_statement_data_sets | materialized_structured_bulk_parser_gate_pending | 0 | 0 | 0 | 0 | 4522052 | 0 | 0 | staging_only_structured_parser_or_parity_gate_pending |
| S5_primary_authority | tw_mops_portal | materialized_clean_text_parser_gate_pending | 12 | 0 | 0 | 0 | 0 | 0 | 0 | staging_only_parser_citation_boundary_gate_pending |
| S4_company_authored_operating_context | company_product_pages | materialized_clean_text_parser_gate_pending | 0 | 0 | 0 | 0 | 3 | 0 | 0 | staging_only_parser_citation_boundary_gate_pending |
| S3_official_regulatory_product_context | clinicaltrials_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 5 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S3_official_regulatory_product_context | nhtsa_vpic_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 8 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S3_official_regulatory_product_context | openfda_api | materialized_context_snapshot_gate_pending | 0 | 0 | 5 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S3_official_regulatory_product_context | sec_ownership_and_13f | materialized_structured_bulk_parser_gate_pending | 0 | 0 | 0 | 0 | 3877007 | 0 | 0 | staging_only_structured_parser_or_parity_gate_pending |
| S2_official_macro_industry_context | bea_data_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 50 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | bls_public_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 16 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | census_data_api | materialized_normalized_snapshot_gate_pending | 0 | 3 | 1 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | cms_public_data | materialized_context_snapshot_gate_pending | 0 | 0 | 50 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | eia_open_data | materialized_context_snapshot_gate_pending | 0 | 0 | 9 | 10332 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | fdic_bankfind_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 5 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | fred_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 12 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | fred_graph_csv | materialized_context_snapshot_gate_pending | 0 | 0 | 50 | 54197 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S2_official_macro_industry_context | usitc_dataweb_and_trade | materialized_normalized_snapshot_gate_pending | 0 | 0 | 50 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | common_crawl_index | materialized_normalized_snapshot_gate_pending | 0 | 0 | 50 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | gdelt | materialized_normalized_snapshot_gate_pending | 0 | 0 | 3 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | gleif_api | materialized_normalized_snapshot_gate_pending | 0 | 495 | 5 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | openalex_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 5 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | openfigi_api | materialized_normalized_snapshot_gate_pending | 0 | 14 | 1 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | patentsview_api | materialized_normalized_snapshot_gate_pending | 0 | 0 | 1 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S1_resolver_or_lead | wikidata | materialized_normalized_snapshot_gate_pending | 0 | 0 | 5 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |
| S0_deferred_or_unofficial | commercial_market_data_and_consensus | deferred_by_policy | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not_promoted |
| S0_deferred_or_unofficial | yahoo_chart | materialized_normalized_snapshot_gate_pending | 0 | 0 | 22 | 0 | 0 | 0 | 0 | feature_flagged_context_only_boundary_gate_pending |

## 使用边界

- `materialized_clean_text_parser_gate_pending` 只表示 raw/cleaned text 已落地，不表示可进入主线 evidence/vector/ledger。
- `materialized_inventory_or_resolver_only` 只允许 resolver/source inventory/context，用于 claim 前必须回到更高强度来源核验。
- `official_source_not_materialized` 不能用 fallback 当作监管/交易所原始披露；JP company IR fallback 单独计入 `company_ir_reports`。
