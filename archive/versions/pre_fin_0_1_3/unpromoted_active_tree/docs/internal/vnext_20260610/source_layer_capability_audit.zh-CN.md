# Source Layer Capability Audit

- Generated at: `2026-06-23T19:48:04Z`
- Status: `pass`
- Source rows: `48`
- Runtime-ready rows: `17`
- Expected-but-missing rows: `4`

## Layer Summary

| Layer | Count | Runtime ready | Parser gate pending | Missing route |
| --- | ---: | ---: | ---: | ---: |
| L1 strong_fact_authority | 13 | 6 | 4 | 0 |
| L2 trusted_context_supplement | 18 | 3 | 0 | 2 |
| L3 market_proxy_signal | 13 | 8 | 0 | 1 |
| L4 weak_signal_or_exclusion | 4 | 0 | 0 | 1 |

## High Priority Gaps

| Source | Layer | Evidence graph status | Blocking reason | Next action |
| --- | --- | --- | --- | --- |
| `bls_public_api` | L2 | structured_not_promoted | feature_flagged_context_only_boundary_gate_pending | build_bls_series_allowlist_and_context_adapter |
| `clinicaltrials_api` | L2 | structured_not_promoted | feature_flagged_context_only_boundary_gate_pending | build_sponsor_product_condition_resolver |
| `company_ir_reports` | L1 | staging_parser_gate_pending | staging_only_parser_citation_boundary_gate_pending | build_pdf_html_parser_and_source_boundary_audit |
| `company_product_pages` | L2 | structured_not_promoted | staging_only_parser_citation_boundary_gate_pending | expand_official_domain_allowlist_and_build_product_page_parser |
| `company_reported_product_operating_metrics` | L1 | structured_not_promoted | candidate_only_value_unit_period_parser_gate_pending | promote_candidate_table_to_value_unit_period_product_parser |
| `fdic_bankfind_api` | L2 | structured_not_promoted | feature_flagged_context_only_boundary_gate_pending | build_bank_institution_subsidiary_to_listed_issuer_resolver |
| `fred_api` | L2 | structured_not_promoted | feature_flagged_context_only_boundary_gate_pending | prefer_fred_api_for_series_metadata_and_observations_keep_graph_csv_as_fallback |
| `gleif_api` | L3 | runtime_ready_context |  | add_alias_overrides_and_relationship_resolver |
| `openfda_api` | L2 | structured_not_promoted | feature_flagged_context_only_boundary_gate_pending | build_openfda_product_sponsor_endpoint_resolver |
| `openfigi_api` | L3 | runtime_ready_context |  | retry_failed_exchange_mappings_and_keep_resolver_only |
| `sec_financial_statement_data_sets` | L1 | structured_not_promoted | staging_only_structured_parser_or_parity_gate_pending | build_bulk_parser_compare_to_companyfacts_and_promote_if_better_than_document_extraction |
| `sec_ownership_and_13f` | L2 | structured_not_promoted | staging_only_structured_parser_or_parity_gate_pending | build_13f_parser_investment_graph_edges_and_lag_policy |
| `yahoo_chart` | L4 | structured_not_promoted | feature_flagged_context_only_boundary_gate_pending | keep_provisional_label_or_replace_with_approved_market_provider |
| `mainstream_financial_news` | L2 | runtime_ready_context |  | expand publisher coverage, entity/event matching, page variants, and persistent backfill |
| `industry_association_reports` | L2 | not_registered | expected_source_profile_not_registered_in_current_runtime | add source policy, acquisition route, parser contract, and source-boundary gate |
| `supplier_customer_official_news` | L2 | runtime_ready_context |  | expand official domain resolver, counterparty matching, page variants, and persistent backfill |
| `ecommerce_major_platforms` | L3 | not_registered | expected_source_profile_not_registered_in_current_runtime | add source policy, acquisition route, parser contract, and source-boundary gate |
| `app_store_rankings` | L3 | runtime_ready_context |  | expand app-to-issuer resolver coverage, add Google Play/major marketplace policy where legally accessible, and keep download/revenue claims blocked |
| `developer_ecosystem_github_npm_pypi_huggingface` | L3 | runtime_ready_context |  | expand issuer/project resolver coverage, refresh cadence, and source-boundary regression cases |
| `public_tenders_contracts_orders` | L3 | runtime_ready_context |  | expand jurisdiction/source coverage beyond USAspending, buyer/supplier resolver coverage, and no-backlog-revenue-promotion tests |
| `job_postings_hiring_signals` | L3 | runtime_ready_context |  | expand company ATS resolver coverage, role taxonomy mapping, refresh cadence, and no-headcount-demand-promotion tests |
| `channel_pricing_quotations` | L3 | runtime_ready_context |  | expand reseller/domain coverage beyond CDW and keep ASP, sell-through, inventory, sales, and share claims blocked |
| `platform_reviews_rankings_downloads` | L3 | runtime_ready_context |  | expand platform coverage, add timestamped ranking snapshots where available, and keep sales/revenue/share claims blocked |
| `official_social_accounts` | L2 | not_registered | expected_source_profile_not_registered_in_current_runtime | add source policy, acquisition route, parser contract, and source-boundary gate |

## Runtime Use Rule

- L1 rows can become exact facts only after parser, citation, period, unit, and authority gates.
- L2 rows should enter as trusted context/proxy when source and parser gates pass; they do not prove company sales, margin, share, or product revenue unless the source itself is company-disclosed and exact gates pass.
- L3 rows should enter as directional market/channel/developer signals; they cannot prove company exact facts.
- L4 rows are discovery/exclusion only and should not support core thesis.
