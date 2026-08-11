# 不使用商业 API 的公开数据源研报质量上限

## 状态

- 生成时间：`2026-06-11T12:28:57.974194+00:00`
- 策略：不采购商业 API；只使用公开、官方、免费 key、open-bulk 和已审计 no-key 来源。
- 数据源数量：`32`
- 当前 runtime 候选：`5` 个 source
- parser/gate 通过后可成为 claim evidence 的 source 候选：`11` 个

## 研报质量上限

- 当前已验证上限：`medium_high_for_us_filing_fundamentals_medium_for_context_low_for_consensus_and_private_supply_chain`
- 公开源 buildout 完成后的潜在上限：`high_for_disclosed_company_facts_medium_high_for_context_and_regulatory_research_still_low_for_consensus_realtime_and_undisclosed_company_kpis`

| 研究维度 | 当前上限 | 潜在上限 | 硬边界 |
| --- | --- | --- | --- |
| us_company_fundamental_analysis | high | high | Cannot replace sell-side estimates, management access, or undisclosed product/customer metrics. |
| non_us_primary_disclosure_analysis | low_medium | high | Until parser gates pass, metadata and locators cannot be cited as filing evidence. |
| company_reported_product_operating_metrics | low_medium | medium_high | No public source can infer undisclosed SKU-level sales, channel inventory, or product profitability. |
| macro_industry_context | medium | medium_high | Context rows cannot prove company-specific revenue, margin, customers, or product adoption. |
| healthcare_product_regulatory_research | low_medium | medium_high | They do not prove approval success, commercial uptake, sales, or adverse-event causality. |
| auto_product_identity_and_context | low | medium | It does not provide deliveries, revenue, margins, or quality causality. |
| banking_regulatory_context | low_medium | medium | FDIC institution rows are not consolidated listed-company financial statements. |
| investment_and_ownership_graph | low | medium | They cannot prove real-time positioning, intent, or non-filing private holdings. |
| supply_chain_and_customer_relationships | low_medium | medium | Public sources cannot replace paid supply-chain transaction databases or customs microdata. |
| market_valuation_and_consensus | low_medium | medium | No reliable no-commercial source covers analyst consensus, target prices, or stable real-time valuation feeds. |
| event_and_news_research | low | medium | Leads must be verified against official/company/regulatory sources before entering claims. |
| technology_and_ip_signal | low | medium | Signals cannot prove product launch, moat, sales, or profitability. |

## 信息强度矩阵

| 强度层级 | Source | 接入方式 | 当前可用度 | 当前贡献 | 潜在贡献 | 下一道 gate |
| --- | --- | --- | --- | --- | --- | --- |
| S5_primary_authority | cninfo_portal | primary_evidence_authority | profile_validation_pending | none | high_for_china_primary_disclosure | validate_security_code_org_id_category_and_download_parser |
| S5_primary_authority | company_ir_reports | primary_evidence_authority | parser_required | low_medium_limited_eu_smoke | high_for_non_us_primary_disclosure | build_pdf_html_parser_and_source_boundary_audit |
| S5_primary_authority | company_reported_product_operating_metrics | company_operating_metric_parser | ontology_candidate_table_materialized_parser_required | low_medium_via_candidate_table_without_value_unit_period_parser | medium_high_for_disclosed_product_kpis | promote_candidate_table_to_value_unit_period_product_parser |
| S5_primary_authority | hkexnews_portal | primary_evidence_authority | profile_validation_pending | none | high_for_hong_kong_primary_disclosure | validate_issuer_code_headline_category_date_filters_and_pdf_parser |
| S5_primary_authority | jp_edinet_api | primary_evidence_authority | blocked_credential | none | high_for_japanese_primary_disclosure | configure_edinet_api_key_and_build_document_parser |
| S5_primary_authority | kr_dart_openapi | primary_evidence_authority | identifier_ready_parser_blocked | low_locator_only | high_for_korean_primary_disclosure | build_dart_document_package_downloader_and_parser |
| S5_primary_authority | sec_edgar_apis | primary_evidence_authority | accepted_core | high_for_us_issuer_fundamentals | high | keep_core_and_extend_ownership_if_needed |
| S5_primary_authority | sec_financial_statement_data_sets | structured_fact_authority | bulk_download_materialized_parser_gate_pending | medium_as_official_bulk_structured_path_pending_parity | high_for_offline_ledger_and_companyfacts_parity | build_bulk_parser_compare_to_companyfacts_and_promote_if_better_than_document_extraction |
| S5_primary_authority | tw_mops_portal | primary_evidence_authority | profile_validation_pending | none | high_for_taiwan_primary_disclosure | validate_company_code_year_report_type_language_and_checksum |
| S4_company_authored_operating_context | company_product_pages | company_operating_metric_parser | official_page_sample_materialized_parser_gate_pending | low_as_bounded_official_product_page_staging | medium_for_product_existence_and_positioning | expand_official_domain_allowlist_and_build_product_page_parser |
| S3_official_regulatory_product_context | clinicaltrials_api | held_for_parser_or_mapping | downloaded_but_held | low_until_healthcare_resolver | medium_high_for_pipeline_context | build_sponsor_product_condition_resolver |
| S3_official_regulatory_product_context | nhtsa_vpic_api | held_for_parser_or_mapping | downloaded_but_held | low_until_resolver | medium_for_auto_product_identity | build_vehicle_make_model_year_to_issuer_resolver |
| S3_official_regulatory_product_context | openfda_api | held_for_parser_or_mapping | downloaded_but_held | low_until_product_resolver | medium_high_for_healthcare_regulatory_context | build_openfda_product_sponsor_endpoint_resolver |
| S3_official_regulatory_product_context | sec_ownership_and_13f | primary_evidence_authority | bulk_download_materialized_parser_gate_pending | low_as_13f_bulk_staging_without_issuer_graph | medium_for_lagged_ownership_and_investment_context | build_13f_parser_investment_graph_edges_and_lag_policy |
| S2_official_macro_industry_context | bea_data_api | context_snapshot | normalized_context_materialized_allowlist_pending | medium_for_gdp_pce_industry_accounts | medium_high | build_bea_dataset_table_allowlist |
| S2_official_macro_industry_context | bls_public_api | context_snapshot | normalized_context_materialized_allowlist_pending | medium_for_labor_cpi_ppi_context | medium_high | build_bls_series_allowlist_and_context_adapter |
| S2_official_macro_industry_context | census_data_api | context_snapshot | feature_flag_candidate | low_current_three_context_rows | medium_high_for_population_trade_and_business_context | add_census_dataset_geography_table_allowlist |
| S2_official_macro_industry_context | cms_public_data | context_snapshot | normalized_catalog_materialized_endpoint_selection_pending | low_as_public_catalog_staging | medium_for_healthcare_payer_and_utilization_context | select_cms_endpoints_and_product_or_procedure_mapping |
| S2_official_macro_industry_context | eia_open_data | context_snapshot | downloaded_but_held | low_until_route_allowlist | medium_high_for_energy_and_utility_context | add_eia_route_allowlist_and_asset_or_sector_mapping |
| S2_official_macro_industry_context | fdic_bankfind_api | context_snapshot | downloaded_but_held | low_until_resolver | medium_for_banking_context | build_bank_institution_subsidiary_to_listed_issuer_resolver |
| S2_official_macro_industry_context | fred_api | context_snapshot | normalized_context_materialized_preferred_path | medium_for_macro_context_with_series_metadata | medium_high | prefer_fred_api_for_series_metadata_and_observations_keep_graph_csv_as_fallback |
| S2_official_macro_industry_context | fred_graph_csv | context_snapshot | accepted_no_key_context_fallback | medium_for_macro_context_as_no_key_fallback | medium_high | keep_as_no_key_fallback_after_fred_api_preferred_path_passes |
| S2_official_macro_industry_context | usitc_dataweb_and_trade | context_snapshot | census_trade_api_materialized_hs_context_pending | low_as_bounded_hs_trade_context | medium_for_trade_and_manufacturing_context | validate_usitc_or_census_trade_endpoint_and_hs_mapping |
| S1_resolver_or_lead | common_crawl_index | lead_or_discovery | materialized_bounded_crawl_index_metadata_snapshot | low_for_official_page_discovery_after_bounded_snapshot | low_for_official_page_discovery | build_official_origin_filter_and_fetcher |
| S1_resolver_or_lead | gdelt | lead_or_discovery | materialized_bounded_public_index_snapshot | low_for_event_index_leads_after_bounded_snapshot | medium_for_event_discovery | build_event_lead_queue_and_verification_policy |
| S1_resolver_or_lead | gleif_api | resolver_registry | feature_flag_candidate_with_gaps | medium_for_lei_resolution | medium_for_entity_and_legal_relationship_context | add_alias_overrides_and_relationship_resolver |
| S1_resolver_or_lead | openalex_api | lead_or_discovery | materialized_bounded_research_work_snapshot | low_for_research_trend_leads_after_bounded_snapshot | medium_for_research_and_technology_signal | build_topic_institution_company_resolver |
| S1_resolver_or_lead | openfigi_api | resolver_registry | feature_flag_candidate | medium_for_security_identifier_resolution | medium | retry_failed_exchange_mappings_and_keep_resolver_only |
| S1_resolver_or_lead | patentsview_api | lead_or_discovery | migration_metadata_materialized_endpoint_validation_pending | low_as_api_migration_metadata_only | medium_for_ip_and_technology_signal | validate_current_uspto_open_data_portal_endpoint_and_materialize_patent_tables |
| S1_resolver_or_lead | wikidata | resolver_registry | materialized_bounded_alias_candidate_snapshot | low_for_alias_candidates_after_bounded_snapshot | low_for_alias_resolution | build_low_weight_alias_candidate_adapter |
| S0_deferred_or_unofficial | commercial_market_data_and_consensus | deferred_no_commercial_api | deferred_no_commercial_api | none | unavailable_without_policy_change | keep_deferred_until_user_changes_funding_policy |
| S0_deferred_or_unofficial | yahoo_chart | context_snapshot | materialized_bounded_provisional_context_only | low_medium_for_market_reaction_context | low_medium | keep_provisional_label_or_replace_with_approved_market_provider |

## 硬边界

- S5/S4 来源只有在 parser、citation、period、unit 和 source-boundary gate 通过后，才能支持公司级事实。
- S3 来源支持官方监管、产品状态、ownership 或 entity context，但不能证明商业采用、销售或盈利。
- S2 来源只能支持宏观/行业上下文，不能被改写为公司级收入、利润、客户或产品销量事实。
- S1 来源是 resolver、discovery、technology signal 或 event lead，进入 claim 前必须回到更高强度来源核验。
- S0 和 commercial-deferred 来源在当前 no-commercial policy 下只能作为显式 source gap 或 provisional context。
