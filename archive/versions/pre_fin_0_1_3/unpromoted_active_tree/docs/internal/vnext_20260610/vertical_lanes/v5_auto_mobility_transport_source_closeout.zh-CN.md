# V5 Source Coverage Closeout

- lane_name: `Auto / Mobility / Transport Platforms`
- industry_schema: `auto_mobility`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `gap`
- requirement_count: `9`
- pass_requirement_count: `9`
- source_gap_requirement_count: `0`
- commercial_gap_count: `15`
- observed_runtime_row_count: `376`
- observed_primary_ticker_count: `7` / `17`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 6 | 6 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| official_product_surface | pass | gap | pass | 6 | 6 | Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment. |
| auto_product_identity_context | pass | gap | gap | 1 | 1 | Resolve manufacturer/make/model-year to issuer/product. |
| trusted_external_context | pass | pass | pass | 3 | 3 | Use trusted publisher or official association routes before declaring external context unavailable. |
| supply_chain_official_relationship | pass | pass | pass | 3 | 3 | Fetch supplier/customer official news and public tender/order routes, then bind issuer/counterparty. |
| channel_offer_proxy | pass | pass | pass | 1 | 1 | Route e-commerce/channel snapshots through offer parser and SKU/product resolver. |
| public_order_proxy | pass | pass | pass | 3 | 3 | Parse jurisdiction portal awards/status and bind buyer/supplier/product. |
| hiring_capacity_proxy | pass | pass | pass | 1 | 1 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 4 | 4 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V5_COMMERCIAL_GAP::EXPECTED::1`: registration/VIO (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V5_COMMERCIAL_GAP::EXPECTED::2`: model share (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V5_COMMERCIAL_GAP::EXPECTED::3`: true used inventory (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V5_COMMERCIAL_GAP::EXPECTED::4`: owner demographics (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V5_COMMERCIAL_GAP::EXPECTED::5`: ride-level marketplace data (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::Circana`: Circana appears in product evidence graph commercial gap ledger for 10 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::NielsenIQ`: NielsenIQ appears in product evidence graph commercial gap ledger for 10 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::Rystad`: Rystad appears in product evidence graph commercial gap ledger for 10 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Commodity Insights`: S&P Global Commodity Insights appears in product evidence graph commercial gap ledger for 10 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Mobility`: S&P Global Mobility appears in product evidence graph commercial gap ledger for 60 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::Sensor Tower`: Sensor Tower appears in product evidence graph commercial gap ledger for 5 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::Similarweb`: Similarweb appears in product evidence graph commercial gap ledger for 5 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::Wood Mackenzie`: Wood Mackenzie appears in product evidence graph commercial gap ledger for 10 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::data.ai`: data.ai appears in product evidence graph commercial gap ledger for 5 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V5_COMMERCIAL_GAP::PRODUCT_GRAPH::national registration datasets`: national registration datasets appears in product evidence graph commercial gap ledger for 60 V5-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V5 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V5 ticker with parser-backed coverage for that requirement. It does not mean every V5 issuer or every product has complete coverage.
