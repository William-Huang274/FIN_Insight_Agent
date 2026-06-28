# V8 Source Coverage Closeout

- lane_name: `Retail / CPG / Restaurants / Travel`
- industry_schema: `retail_cpg`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `pass`
- requirement_count: `7`
- pass_requirement_count: `7`
- source_gap_requirement_count: `0`
- commercial_gap_count: `10`
- observed_runtime_row_count: `921`
- observed_primary_ticker_count: `29` / `79`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 25 | 26 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| official_product_surface | pass | gap | pass | 25 | 26 | Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment. |
| trusted_external_context | pass | pass | pass | 4 | 4 | Use trusted publisher or official association routes before declaring external context unavailable. |
| channel_offer_proxy | pass | pass | pass | 1 | 1 | Route e-commerce/channel snapshots through offer parser and SKU/product resolver. |
| platform_review_proxy | pass | pass | pass | 1 | 1 | Parse platform ranking/review pages with timestamp and entity/product binding. |
| hiring_capacity_proxy | pass | pass | pass | 2 | 2 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 4 | 4 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V8_COMMERCIAL_GAP::EXPECTED::1`: Circana/NielsenIQ POS (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V8_COMMERCIAL_GAP::EXPECTED::2`: scanner/panel data (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V8_COMMERCIAL_GAP::EXPECTED::3`: traffic trackers (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V8_COMMERCIAL_GAP::EXPECTED::4`: private booking conversion (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V8_COMMERCIAL_GAP::EXPECTED::5`: promotion/channel inventory (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V8_COMMERCIAL_GAP::PRODUCT_GRAPH::Circana`: Circana appears in product evidence graph commercial gap ledger for 385 V8-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V8_COMMERCIAL_GAP::PRODUCT_GRAPH::NielsenIQ`: NielsenIQ appears in product evidence graph commercial gap ledger for 385 V8-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V8_COMMERCIAL_GAP::PRODUCT_GRAPH::Sensor Tower`: Sensor Tower appears in product evidence graph commercial gap ledger for 10 V8-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V8_COMMERCIAL_GAP::PRODUCT_GRAPH::Similarweb`: Similarweb appears in product evidence graph commercial gap ledger for 10 V8-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V8_COMMERCIAL_GAP::PRODUCT_GRAPH::data.ai`: data.ai appears in product evidence graph commercial gap ledger for 10 V8-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V8 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V8 ticker with parser-backed coverage for that requirement. It does not mean every V8 issuer or every product has complete coverage.
