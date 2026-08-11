# Company Gap Docket

- schema_version: `finsight_company_gap_docket_summary_v0_1`
- generated_at: `2026-06-20T18:03:00Z`
- status: `pass`
- docket_count: `485`
- source_role_gap_docket_count: `108`
- product_kpi_gap_docket_count: `377`
- unique_gap_company_count: `407`
- unclassified_docket_count: `0`

## Adapter Cluster Queue

| cluster | priority | dockets | companies | state | ladder |
| --- | --- | ---: | ---: | --- | --- |
| public_order_local_tender_and_recipient_adapter | high | 19 | 19 | needs_jurisdiction_adapter_or_recipient_boundary_audit | usaspending -> sam_gov -> eu_ted -> uk_contracts_finder -> canada_buyandsell -> japan_geps -> hong_kong_tender -> taiwan_government_procurement |
| product_kpi_column_group_schema_verifier | high | 18 | 18 | needs_column_group_schema | segment_note_table -> 10k_10q_product_table -> ir_deck_table -> annual_report_pdf_table |
| developer_ecosystem_official_seed_locator | high | 13 | 13 | needs_verified_seed_locator | company_docs -> official_github_org -> npm_verified_scope -> pypi_verified_project -> huggingface_verified_org -> marketplace_verified_publisher |
| product_kpi_sentence_relation_verifier | high | 9 | 9 | needs_local_relation_verifier | filing_sentence_window -> local_table_neighborhood -> ir_deck_sentence_window |
| channel_offer_distributor_marketplace_adapter | high | 8 | 8 | needs_adapter_batch | official_store -> amazon -> jd -> digikey -> mouser -> arrow -> cdw |
| product_kpi_period_version_schema_verifier | high | 7 | 7 | needs_period_version_reconciliation | versioned_filing_table -> prior_year_column_group -> restatement_note |
| public_order_non_us_local_tender_adapter | high | 6 | 6 | attempt_backed_public_boundary_after_local_tender_attempt | usaspending -> sam_gov -> eu_ted -> uk_contracts_finder -> canada_buyandsell -> japan_geps -> hong_kong_tender -> taiwan_government_procurement |
| product_kpi_non_us_ir_local_exchange_parser | high | 4 | 4 | needs_non_us_disclosure_adapter | local_exchange_filing -> company_ir_annual_report -> 20f_6k -> annual_report_pdf_table -> ir_deck_table |
| supply_chain_official_relationship_resolver | high | 1 | 1 | needs_official_relationship_adapter_or_boundary_audit | company_official_news -> customer_supplier_official_news -> public_contract_awards -> regulatory_contract_disclosures |
| product_kpi_business_segment_boundary | medium | 107 | 107 | route_to_business_mix_or_remain_product_kpi_gap | segment_note_table -> 10k_10q_segment_table -> 20f_6k_segment_table |
| product_kpi_ir_deck_annual_report_locator | medium | 101 | 101 | needs_locator_before_final_gap | company_ir_presentation -> annual_report_pdf_table -> filing_segment_note -> earnings_deck_product_table |
| product_kpi_percentage_change_rejection_gate | medium | 72 | 72 | reject_or_pair_with_currency_level_value | product_table_parser -> local_table_coordinate_verifier |
| hiring_capacity_site_specific_public_jobs_adapter | medium | 36 | 36 | needs_site_specific_parser_or_boundary_audit | greenhouse -> lever -> ashby -> smartrecruiters -> workday -> jibe -> phenom -> successfactors -> official_careers_html |
| product_kpi_industry_operating_metric_slot_router | medium | 32 | 32 | needs_industry_operating_metric_slot_mapping | industry_operating_metric_table -> business_metric_table -> company_disclosed_kpi_table |
| technology_research_patents_assignee_resolver | medium | 17 | 17 | needs_adapter_batch | patentsview_assignee -> openalex_institution_topic -> official_technical_publications |
| app_marketplace_seller_alias_adapter | medium | 4 | 4 | needs_marketplace_alias_adapter_or_boundary_audit | apple_itunes_search -> apple_lookup -> google_play_listing -> official_app_page |
| platform_review_seller_alias_adapter | medium | 3 | 3 | needs_marketplace_alias_adapter_or_boundary_audit | apple_itunes_search -> apple_lookup -> google_play_listing -> official_app_page |
| product_kpi_region_dimension_or_rejection_gate | low | 15 | 15 | region_exposure_only_or_needs_product_table | geographic_revenue_table -> product_table_parser |
| product_kpi_non_product_total_rejection_gate | low | 12 | 12 | reject_or_find_product_family_table | product_table_parser -> segment_note_table |
| auto_product_identity_regulatory_boundary_audit | low | 1 | 1 | attempt_backed_public_boundary_or_make_alias_repair | nhtsa_vpic -> nhtsa_recalls -> company_vehicle_pages |

## Requirement Counts

| requirement | dockets |
| --- | ---: |
| `app_rank_store_proxy` | 4 |
| `auto_product_identity_context` | 1 |
| `channel_offer_proxy` | 8 |
| `developer_ecosystem_proxy` | 13 |
| `hiring_capacity_proxy` | 36 |
| `platform_review_proxy` | 3 |
| `product_kpi_exact_slot` | 377 |
| `public_order_proxy` | 25 |
| `supply_chain_official_relationship` | 1 |
| `technology_research_proxy` | 17 |

## Boundary

The docket operationalizes remaining company gaps. It does not promote evidence. A gap can become final only after its listed source ladder and pass condition are exhausted in an attempt ledger.
