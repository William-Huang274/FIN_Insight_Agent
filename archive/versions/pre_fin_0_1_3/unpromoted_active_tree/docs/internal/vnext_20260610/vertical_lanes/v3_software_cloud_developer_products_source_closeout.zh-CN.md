# V3 Source Coverage Closeout

- lane_name: `SaaS / Cloud / Developer Products`
- industry_schema: `software_saas`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `pass`
- requirement_count: `9`
- pass_requirement_count: `9`
- source_gap_requirement_count: `0`
- commercial_gap_count: `16`
- observed_runtime_row_count: `687`
- observed_primary_ticker_count: `31` / `94`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 23 | 25 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| official_product_surface | pass | gap | pass | 24 | 26 | Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment. |
| trusted_external_context | pass | pass | pass | 4 | 4 | Use trusted publisher or official association routes before declaring external context unavailable. |
| developer_ecosystem_proxy | pass | pass | pass | 4 | 4 | Route GitHub/npm/PyPI/HuggingFace through source-specific parser and project-to-issuer resolver. |
| public_order_proxy | pass | pass | pass | 5 | 5 | Parse jurisdiction portal awards/status and bind buyer/supplier/product. |
| app_rank_store_proxy | pass | pass | pass | 4 | 5 | Resolve app-to-issuer mapping and snapshot ranking/review metadata. |
| platform_review_proxy | pass | pass | pass | 1 | 1 | Parse platform ranking/review pages with timestamp and entity/product binding. |
| hiring_capacity_proxy | pass | pass | pass | 3 | 4 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 4 | 4 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V3_COMMERCIAL_GAP::EXPECTED::1`: net retention benchmarks (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V3_COMMERCIAL_GAP::EXPECTED::2`: third-party web traffic/commercial intent (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V3_COMMERCIAL_GAP::EXPECTED::3`: private cloud usage (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V3_COMMERCIAL_GAP::EXPECTED::4`: consensus revision (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Counterpoint`: Counterpoint appears in product evidence graph commercial gap ledger for 35 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Gartner`: Gartner appears in product evidence graph commercial gap ledger for 35 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::IDC`: IDC appears in product evidence graph commercial gap ledger for 35 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Omdia/Canalys`: Omdia/Canalys appears in product evidence graph commercial gap ledger for 35 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Rystad`: Rystad appears in product evidence graph commercial gap ledger for 55 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Commodity Insights`: S&P Global Commodity Insights appears in product evidence graph commercial gap ledger for 55 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Mobility`: S&P Global Mobility appears in product evidence graph commercial gap ledger for 40 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Sensor Tower`: Sensor Tower appears in product evidence graph commercial gap ledger for 315 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Similarweb`: Similarweb appears in product evidence graph commercial gap ledger for 315 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::Wood Mackenzie`: Wood Mackenzie appears in product evidence graph commercial gap ledger for 55 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::data.ai`: data.ai appears in product evidence graph commercial gap ledger for 315 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V3_COMMERCIAL_GAP::PRODUCT_GRAPH::national registration datasets`: national registration datasets appears in product evidence graph commercial gap ledger for 40 V3-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V3 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V3 ticker with parser-backed coverage for that requirement. It does not mean every V3 issuer or every product has complete coverage.
