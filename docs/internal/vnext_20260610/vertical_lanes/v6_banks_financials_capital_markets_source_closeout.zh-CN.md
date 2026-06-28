# V6 Source Coverage Closeout

- lane_name: `Banks / Financials / Capital Markets`
- industry_schema: `financials_banks`
- status: `pass`
- registry_gate_status: `gap`
- runtime_gate_status: `pass`
- requirement_count: `4`
- pass_requirement_count: `4`
- source_gap_requirement_count: `0`
- commercial_gap_count: `7`
- observed_runtime_row_count: `632`
- observed_primary_ticker_count: `30` / `77`

## Requirement Closeouts

| requirement | closeout | registry | runtime | primary tickers | inclusive tickers | next action |
| --- | --- | --- | --- | ---: | ---: | --- |
| primary_company_disclosure | pass | pass | pass | 25 | 25 | Use SEC/FSD for US issuers and official IR/local filing route for non-US issuers before exposing a filing gap. |
| financial_regulatory_context | pass | gap | pass | 4 | 4 | Resolve FDIC institution/subsidiary to listed issuer and keep rate/credit context separated from company-reported facts. |
| trusted_external_context | pass | pass | pass | 4 | 4 | Use trusted publisher or official association routes before declaring external context unavailable. |
| macro_official_context | pass | pass | pass | 4 | 4 | Resolve industry driver/source mapping and keep company exposure bridge explicit. |

## Source Gap Ledger

- none

## Commercial Gap Ledger

- `V6_COMMERCIAL_GAP::EXPECTED::1`: real-time flows (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V6_COMMERCIAL_GAP::EXPECTED::2`: private deposit migration (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V6_COMMERCIAL_GAP::EXPECTED::3`: advisor-channel detail (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V6_COMMERCIAL_GAP::EXPECTED::4`: consensus revision (boundary=public sources cannot fill this as company sales/share/order/inventory authority)
- `V6_COMMERCIAL_GAP::PRODUCT_GRAPH::Rystad`: Rystad appears in product evidence graph commercial gap ledger for 5 V6-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V6_COMMERCIAL_GAP::PRODUCT_GRAPH::S&P Global Commodity Insights`: S&P Global Commodity Insights appears in product evidence graph commercial gap ledger for 5 V6-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)
- `V6_COMMERCIAL_GAP::PRODUCT_GRAPH::Wood Mackenzie`: Wood Mackenzie appears in product evidence graph commercial gap ledger for 5 V6-related missing product/market metrics. (boundary=must remain bounded/commercial gap unless licensed tracker data is added)

## Boundary

V6 source closeout resolves the registry/package ambiguity by checking real materialized rows. A pass means the lane has at least one primary V6 ticker with parser-backed coverage for that requirement. It does not mean every V6 issuer or every product has complete coverage.
