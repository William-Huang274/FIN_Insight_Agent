# V1 Source Coverage Closeout

- lane_name: `Semiconductors / AI Infrastructure`
- industry_schema: `semiconductors_hardware`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `pass`
- requirement_count: `10`
- pass_requirement_count: `10`
- source_gap_requirement_count: `0`
- commercial_gap_count: `15`
- observed_runtime_row_count: `475`
- observed_primary_ticker_count: `15` / `43`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 9 | 11 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| official_product_surface | pass | gap | pass | 12 | 15 | Fetch official product/IR pages, parse product/spec rows, and bind issuer/product before product section judgment. |
| trusted_external_context | pass | pass | pass | 10 | 10 | Use trusted publisher or official association routes before declaring external context unavailable. |
| supply_chain_official_relationship | pass | pass | pass | 6 | 9 | Fetch supplier/customer official news and public tender/order routes, then bind issuer/counterparty. |
| developer_ecosystem_proxy | pass | pass | pass | 1 | 4 | Route GitHub/npm/PyPI/HuggingFace through source-specific parser and project-to-issuer resolver. |
| channel_offer_proxy | pass | pass | pass | 2 | 3 | Route e-commerce/channel snapshots through offer parser and SKU/product resolver. |
| public_order_proxy | pass | pass | pass | 6 | 9 | Parse jurisdiction portal awards/status and bind buyer/supplier/product. |
| hiring_capacity_proxy | pass | pass | pass | 2 | 2 | Parse company/job-board postings and role taxonomy; bind issuer/product/geography. |
| macro_official_context | pass | pass | pass | 10 | 10 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |
| technology_research_proxy | pass | gap | pass | 5 | 5 | Resolve assignee/institution/topic to issuer/product and keep proxy boundary explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V1_COMMERCIAL_GAP::EXPECTED::1`: IDC/Counterpoint/Omdia/Gartner shipments/share/forecast (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V1_COMMERCIAL_GAP::EXPECTED::2`: supply allocation (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V1_COMMERCIAL_GAP::EXPECTED::3`: hyperscaler exact purchase orders (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V1_COMMERCIAL_GAP::EXPECTED::4`: channel inventory (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::Circana`: Circana appears in product evidence graph commercial gap ledger for 5 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::Counterpoint`: Counterpoint appears in product evidence graph commercial gap ledger for 190 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::Gartner`: Gartner appears in product evidence graph commercial gap ledger for 190 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::IDC`: IDC appears in product evidence graph commercial gap ledger for 190 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::NielsenIQ`: NielsenIQ appears in product evidence graph commercial gap ledger for 5 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::Omdia/Canalys`: Omdia/Canalys appears in product evidence graph commercial gap ledger for 190 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Mobility`: S&P Global Mobility appears in product evidence graph commercial gap ledger for 10 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::Sensor Tower`: Sensor Tower appears in product evidence graph commercial gap ledger for 5 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::Similarweb`: Similarweb appears in product evidence graph commercial gap ledger for 5 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::data.ai`: data.ai appears in product evidence graph commercial gap ledger for 5 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V1_COMMERCIAL_GAP::PRODUCT_GRAPH::national registration datasets`: national registration datasets appears in product evidence graph commercial gap ledger for 10 V1-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V1 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V1 ticker with parser-backed coverage for that requirement. It does not mean every V1 issuer or every product has complete coverage.
