# V4 Source Coverage Closeout

- lane_name: `Pharma / Biotech / Medtech`
- industry_schema: `healthcare_pharma_medtech`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `gap`
- requirement_count: `8`
- pass_requirement_count: `8`
- source_gap_requirement_count: `0`
- commercial_gap_count: `6`
- observed_runtime_row_count: `939`
- observed_primary_ticker_count: `28` / `68`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 24 | 24 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| official_product_surface | pass | gap | pass | 26 | 26 | Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment. |
| regulated_product_context | pass | gap | gap | 2 | 2 | Resolve sponsor/product/condition/application/procedure before promotion to healthcare context. |
| trusted_external_context | pass | pass | pass | 4 | 4 | Use trusted publisher or official association routes before declaring external context unavailable. |
| technology_research_proxy | pass | gap | pass | 3 | 3 | Resolve assignee/institution/topic to issuer/product and keep proxy boundary explicit. |
| public_order_proxy | pass | pass | pass | 2 | 2 | Parse jurisdiction portal awards/status and bind buyer/supplier/product. |
| hiring_capacity_proxy | pass | pass | pass | 1 | 1 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 3 | 3 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V4_COMMERCIAL_GAP::EXPECTED::1`: IQVIA/Symphony scripts (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V4_COMMERCIAL_GAP::EXPECTED::2`: prescription share (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V4_COMMERCIAL_GAP::EXPECTED::3`: procedure volumes (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V4_COMMERCIAL_GAP::EXPECTED::4`: hospital channel sell-through (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V4_COMMERCIAL_GAP::PRODUCT_GRAPH::IQVIA`: IQVIA appears in product evidence graph commercial gap ledger for 340 V4-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V4_COMMERCIAL_GAP::PRODUCT_GRAPH::Symphony`: Symphony appears in product evidence graph commercial gap ledger for 340 V4-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V4 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V4 ticker with parser-backed coverage for that requirement. It does not mean every V4 issuer or every product has complete coverage.
