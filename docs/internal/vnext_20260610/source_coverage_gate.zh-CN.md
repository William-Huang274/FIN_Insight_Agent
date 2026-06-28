# Source Coverage Gate Report

- schema_version: `finsight_source_coverage_matrix_v0_1`
- generated_at: `2026-06-17T10:36:16Z`
- phase: `registry`
- status: `gap`

| industry | status | requirements | gap | fail | exact authority violations |
| --- | --- | ---: | ---: | ---: | ---: |
| auto_mobility | gap | 9 | 2 | 0 | 0 |
| consumer_electronics | gap | 8 | 1 | 0 | 0 |
| energy_utilities | gap | 7 | 1 | 0 | 0 |
| financials_banks | gap | 4 | 1 | 0 | 0 |
| generic_public_research | gap | 4 | 1 | 0 | 0 |
| healthcare_pharma_medtech | gap | 8 | 3 | 0 | 0 |
| retail_cpg | gap | 7 | 1 | 0 | 0 |
| semiconductors_hardware | gap | 10 | 2 | 0 | 0 |
| software_saas | gap | 9 | 1 | 0 | 0 |

## Requirement Gaps

### auto_mobility

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.
- `auto_product_identity_context`: `source_parser_or_mapping_not_runtime_ready`; sources=nhtsa_vpic_api; next=Resolve manufacturer/make/model-year to issuer/product.

### consumer_electronics

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.

### energy_utilities

- `energy_utility_context`: `source_parser_or_mapping_not_runtime_ready`; sources=eia_open_data, fred_api, fred_graph_csv; next=Resolve route/series/asset mapping and company exposure bridge before using EIA/FRED context.

### financials_banks

- `financial_regulatory_context`: `source_parser_or_mapping_not_runtime_ready`; sources=fdic_bankfind_api, fred_api, fred_graph_csv; next=Resolve FDIC institution/subsidiary to listed issuer and keep rate/credit context separated from company-reported facts.

### generic_public_research

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.

### healthcare_pharma_medtech

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.
- `regulated_product_context`: `source_parser_or_mapping_not_runtime_ready`; sources=clinicaltrials_api, openfda_api, cms_public_data; next=Resolve sponsor/product/condition/application/procedure before promotion to healthcare context.
- `technology_research_proxy`: `source_parser_or_mapping_not_runtime_ready`; sources=openalex_api, patentsview_api; next=Resolve assignee/institution/topic to issuer/product and keep proxy boundary explicit.

### retail_cpg

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.

### semiconductors_hardware

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.
- `technology_research_proxy`: `source_parser_or_mapping_not_runtime_ready`; sources=openalex_api, patentsview_api; next=Resolve assignee/institution/topic to issuer/product and keep proxy boundary explicit.

### software_saas

- `official_product_surface`: `source_parser_or_mapping_not_runtime_ready`; sources=company_product_pages, company_reported_product_operating_metrics; next=Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment.
