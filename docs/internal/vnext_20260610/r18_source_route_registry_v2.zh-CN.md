# R18 SourceRouteRegistry v2 / SignalAuthorityMapper v0.2

生成时间：2026-06-23T19:48:23Z

## 摘要

- 状态：`pass`
- registry source roles：`28`
- signal matrix rows：`7181`
- evidence bundle allowed：`7156`
- planning / gap only：`25`

## Hard Gate

- `unregistered_source_role_count`：`0`
- `evidence_row_without_registry_count`：`0`
- `evidence_row_missing_required_fields_count`：`0`
- `non_evidence_row_marked_allowed_count`：`0`

## Authority Mode

- `bounded_thesis_driver_authority`：`4256`
- `exact_company_fact_authority`：`2925`

## Signal Authority Type

- `app_marketplace_signal`：`56`
- `auto_product_identity_signal`：`20`
- `beneficial_ownership_event_signal`：`247`
- `capital_market_event_signal`：`236`
- `capital_structure_fact`：`914`
- `channel_presence_signal`：`66`
- `company_disclosure_fact`：`837`
- `customer_deployment_signal`：`1`
- `customer_order_or_deployment_event_signal`：`26`
- `developer_ecosystem_signal`：`64`
- `energy_utility_signal`：`215`
- `financial_regulatory_signal`：`77`
- `hiring_capacity_signal`：`66`
- `insider_transaction_event_signal`：`246`
- `lagged_ownership_signal`：`409`
- `macro_driver_signal`：`374`
- `market_or_industry_context_signal`：`453`
- `platform_review_signal`：`58`
- `product_benchmark_signal`：`1`
- `product_generation_signal`：`1`
- `proxy_governance_event_signal`：`239`
- `public_order_signal`：`159`
- `regulatory_signal`：`72`
- `supply_chain_signal`：`25`
- `technical_fact`：`1067`
- `technology_research_signal`：`78`
- `working_capital_liquidity_fact`：`1174`

## Source Roles

- `app_rank_store_proxy`：app_marketplace_review_proxy / bounded_thesis_driver_authority / observed source ids `1`
- `auto_product_identity_context`：regulated_product_identity / bounded_thesis_driver_authority / observed source ids `2`
- `beneficial_ownership_filing_event`：capital_funding_ownership_market_liquidity / bounded_thesis_driver_authority / observed source ids `1`
- `capital_structure_disclosure`：capital_funding_ownership_market_liquidity / exact_company_fact_authority / observed source ids `2`
- `channel_offer_proxy`：channel_offer_availability_proxy / bounded_thesis_driver_authority / observed source ids `2`
- `customer_deployment_proxy`：official_customer_deployment_signal / bounded_thesis_driver_authority / observed source ids `1`
- `developer_ecosystem_proxy`：developer_ecosystem_proxy / bounded_thesis_driver_authority / observed source ids `1`
- `energy_utility_context`：macro_industry_driver / bounded_thesis_driver_authority / observed source ids `2`
- `financial_regulatory_context`：capital_funding_ownership_market_liquidity / bounded_thesis_driver_authority / observed source ids `1`
- `hiring_capacity_proxy`：hiring_capacity_proxy / bounded_thesis_driver_authority / observed source ids `1`
- `insider_transaction_filing_event`：capital_funding_ownership_market_liquidity / bounded_thesis_driver_authority / observed source ids `1`
- `lagged_ownership_context`：capital_funding_ownership_market_liquidity / bounded_thesis_driver_authority / observed source ids `1`
- `macro_official_context`：macro_industry_driver / bounded_thesis_driver_authority / observed source ids `2`
- `official_customer_order_or_deployment_event`：official_customer_order_deployment_event / bounded_thesis_driver_authority / observed source ids `1`
- `official_product_surface`：product_and_technology / bounded_thesis_driver_authority / observed source ids `3`
- `platform_review_proxy`：app_marketplace_review_proxy / bounded_thesis_driver_authority / observed source ids `1`
- `primary_company_disclosure`：fundamental_company_disclosure / exact_company_fact_authority / observed source ids `4`
- `product_benchmark_proxy`：product_spec_and_capability / bounded_thesis_driver_authority / observed source ids `1`
- `product_generation_edge`：product_spec_and_capability / bounded_thesis_driver_authority / observed source ids `1`
- `proxy_governance_filing_event`：capital_funding_ownership_market_liquidity / bounded_thesis_driver_authority / observed source ids `1`
- `public_order_proxy`：public_order_supply_chain_proxy / bounded_thesis_driver_authority / observed source ids `1`
- `regulated_product_context`：regulated_product_context / bounded_thesis_driver_authority / observed source ids `3`
- `securities_offering_filing_event`：capital_funding_ownership_market_liquidity / bounded_thesis_driver_authority / observed source ids `1`
- `supply_chain_official_relationship`：supply_chain_relationship / bounded_thesis_driver_authority / observed source ids `2`
- `technical_product_spec`：product_spec_and_capability / bounded_thesis_driver_authority / observed source ids `1`
- `technology_research_proxy`：technology_research_ip / bounded_thesis_driver_authority / observed source ids `2`
- `trusted_external_context`：industry_competition_market_context / bounded_thesis_driver_authority / observed source ids `1`
- `working_capital_liquidity`：capital_funding_ownership_market_liquidity / exact_company_fact_authority / observed source ids `2`

## 代表性 planning / gap rows

- `2317.TW` / `public_order_proxy` / `public_tenders_contracts_orders`：route_or_parser_debt；source_route_retry_required；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `2382.TW` / `public_order_proxy` / `public_tenders_contracts_orders`：route_or_parser_debt；source_route_retry_required；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `3231.TW` / `public_order_proxy` / `public_tenders_contracts_orders`：route_or_parser_debt；source_route_retry_required；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `8035.T` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `AEHR` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.
- `AMKR` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.
- `CRDO` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `PCAR` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.
- `BILL` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.
- `CSIQ` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `JKS` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `SEDG` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.
- `SHOP` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.
- `1211.HK` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `6752.T` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `CCJ` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `DNN` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `DQ` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `ENLT` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Keep this as a public-order gap unless a stable local exchange, regulator, procurement API, or official company contract disclosure exposes supplier-bound award rows.
- `ENPH` / `public_order_proxy` / `public_tenders_contracts_orders`：attempt_backed_public_boundary；attempt_backed_final_boundary；Add SAM/state/local/official customer-news adapters only where public endpoints expose recipient-bound rows; do not infer total orders/backlog.

## 使用边界

- 本 registry 是 source-role 合同，不是外部数据抓取结果。
- SignalAuthorityMapper v0.2 只允许 Data Source Admission Ledger 已准入的 rows 进入 evidence bundle。
- planning / gap rows 只能触发 targeted repair 或 gap ledger，不得被 ClaimCard / Memo 使用。
