# V2 Consumer Electronics / Hardware Devices Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `9`
- inclusive_ticker_count: `12`
- product_kpi_ready_ticker_count: `3`
- official_product_surface_ticker_count: `9`
- commercial_gap_count: `45`

## Representative Cases

### v2_consumer_hardware_devices_financial_product_bridge_001

- execution_mode: `deep_research`
- focus_tickers: `AAPL, MSFT`
- search_scope_tickers: `AAPL, DELL, GOOGL, HPQ, MSFT, SONY`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, trusted_external_context, channel_offer_proxy, app_rank_store_proxy, platform_review_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `IDC/Canalys/Counterpoint device shipments/share, retailer POS/sell-through, channel inventory, ASP tracker`

### v2_consumer_hardware_devices_external_source_repair_boundary_002

- execution_mode: `deep_research`
- focus_tickers: `GOOGL, DELL, HPQ`
- search_scope_tickers: `AAPL, DELL, GOOGL, HPQ, MSFT, SONY`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, trusted_external_context, channel_offer_proxy, app_rank_store_proxy, platform_review_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `IDC/Canalys/Counterpoint device shipments/share, retailer POS/sell-through, channel inventory, ASP tracker`

### v2_consumer_hardware_devices_proxy_no_promotion_003

- execution_mode: `standard_memo`
- focus_tickers: `SONY`
- search_scope_tickers: `AAPL, DELL, GOOGL, HPQ, MSFT, SONY`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, trusted_external_context, channel_offer_proxy, app_rank_store_proxy, platform_review_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `IDC/Canalys/Counterpoint device shipments/share, retailer POS/sell-through, channel inventory, ASP tracker`

## Boundary

This package makes V2 lane planning and deterministic eval cases runtime-ready. Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap.
