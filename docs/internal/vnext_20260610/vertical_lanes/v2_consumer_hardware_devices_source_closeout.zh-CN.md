# V2 Source Coverage Closeout

- lane_name: `Consumer Electronics / Hardware Devices`
- industry_schema: `consumer_electronics`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `pass`
- requirement_count: `8`
- pass_requirement_count: `8`
- source_gap_requirement_count: `0`
- commercial_gap_count: `16`
- observed_runtime_row_count: `250`
- observed_primary_ticker_count: `4` / `9`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 3 | 4 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| official_product_surface | pass | gap | pass | 3 | 5 | Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment. |
| trusted_external_context | pass | pass | pass | 3 | 3 | Use trusted publisher or official association routes before declaring external context unavailable. |
| channel_offer_proxy | pass | pass | pass | 2 | 4 | Route e-commerce/channel snapshots through offer parser and SKU/product resolver. |
| app_rank_store_proxy | pass | pass | pass | 1 | 3 | Resolve app-to-issuer mapping and snapshot ranking/review metadata. |
| platform_review_proxy | pass | pass | pass | 1 | 1 | Parse platform ranking/review pages with timestamp and entity/product binding. |
| hiring_capacity_proxy | pass | pass | pass | 1 | 1 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 3 | 3 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V2_COMMERCIAL_GAP::EXPECTED::1`: IDC/Canalys/Counterpoint device shipments/share (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V2_COMMERCIAL_GAP::EXPECTED::2`: retailer POS/sell-through (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V2_COMMERCIAL_GAP::EXPECTED::3`: channel inventory (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V2_COMMERCIAL_GAP::EXPECTED::4`: ASP tracker (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Circana`: Circana appears in product evidence graph commercial gap ledger for 5 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Counterpoint`: Counterpoint appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Gartner`: Gartner appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::IDC`: IDC appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::NielsenIQ`: NielsenIQ appears in product evidence graph commercial gap ledger for 5 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Omdia/Canalys`: Omdia/Canalys appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Rystad`: Rystad appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Commodity Insights`: S&P Global Commodity Insights appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Sensor Tower`: Sensor Tower appears in product evidence graph commercial gap ledger for 10 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Similarweb`: Similarweb appears in product evidence graph commercial gap ledger for 10 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::Wood Mackenzie`: Wood Mackenzie appears in product evidence graph commercial gap ledger for 15 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V2_COMMERCIAL_GAP::PRODUCT_GRAPH::data.ai`: data.ai appears in product evidence graph commercial gap ledger for 10 V2-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V2 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V2 ticker with parser-backed coverage for that requirement. It does not mean every V2 issuer or every product has complete coverage.
