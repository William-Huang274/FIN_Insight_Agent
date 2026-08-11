# V7 Source Coverage Closeout

- lane_name: `Energy / Utilities / Industrials`
- industry_schema: `energy_utilities`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `pass`
- requirement_count: `7`
- pass_requirement_count: `7`
- source_gap_requirement_count: `0`
- commercial_gap_count: `16`
- observed_runtime_row_count: `2514`
- observed_primary_ticker_count: `77` / `216`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 71 | 71 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| energy_utility_context | pass | gap | pass | 5 | 5 | Resolve route/series/asset mapping and company exposure bridge before using EIA/FRED context. |
| trusted_external_context | pass | pass | pass | 4 | 4 | Use trusted publisher or official association routes before declaring external context unavailable. |
| supply_chain_official_relationship | pass | pass | pass | 1 | 1 | Fetch supplier/customer official news and public tender/order routes, then bind issuer/counterparty. |
| public_order_proxy | pass | pass | pass | 1 | 1 | Parse jurisdiction portal awards/status and bind buyer/supplier/product. |
| hiring_capacity_proxy | pass | pass | pass | 1 | 1 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 5 | 5 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V7_COMMERCIAL_GAP::EXPECTED::1`: asset-level utilization where not disclosed (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V7_COMMERCIAL_GAP::EXPECTED::2`: dealer sell-through (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V7_COMMERCIAL_GAP::EXPECTED::3`: private project economics (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V7_COMMERCIAL_GAP::EXPECTED::4`: equipment order pipeline (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Counterpoint`: Counterpoint appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Gartner`: Gartner appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::IDC`: IDC appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Omdia/Canalys`: Omdia/Canalys appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Rystad`: Rystad appears in product evidence graph commercial gap ledger for 972 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Commodity Insights`: S&P Global Commodity Insights appears in product evidence graph commercial gap ledger for 972 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Mobility`: S&P Global Mobility appears in product evidence graph commercial gap ledger for 15 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Sensor Tower`: Sensor Tower appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Similarweb`: Similarweb appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::Wood Mackenzie`: Wood Mackenzie appears in product evidence graph commercial gap ledger for 972 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::data.ai`: data.ai appears in product evidence graph commercial gap ledger for 20 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V7_COMMERCIAL_GAP::PRODUCT_GRAPH::national registration datasets`: national registration datasets appears in product evidence graph commercial gap ledger for 15 V7-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V7 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V7 ticker with parser-backed coverage for that requirement. It does not mean every V7 issuer or every product has complete coverage.
