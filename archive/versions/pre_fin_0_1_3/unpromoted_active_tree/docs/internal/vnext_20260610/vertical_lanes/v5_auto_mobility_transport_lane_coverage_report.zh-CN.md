# V5 Auto / Mobility / Transport Platforms Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `17`
- inclusive_ticker_count: `17`
- product_kpi_ready_ticker_count: `6`
- official_product_surface_ticker_count: `17`
- commercial_gap_count: `85`

## Representative Cases

### v5_auto_mobility_transport_financial_product_bridge_001

- execution_mode: `deep_research`
- focus_tickers: `TSLA, GM`
- search_scope_tickers: `F, GM, LCID, RIVN, TM, TSLA, UBER`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, auto_product_identity_context, trusted_external_context, supply_chain_official_relationship, channel_offer_proxy, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `registration/VIO, model share, true used inventory, owner demographics, ride-level marketplace data`

### v5_auto_mobility_transport_external_source_repair_boundary_002

- execution_mode: `deep_research`
- focus_tickers: `F, RIVN, LCID`
- search_scope_tickers: `F, GM, LCID, RIVN, TM, TSLA, UBER`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, auto_product_identity_context, trusted_external_context, supply_chain_official_relationship, channel_offer_proxy, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `registration/VIO, model share, true used inventory, owner demographics, ride-level marketplace data`

### v5_auto_mobility_transport_proxy_no_promotion_003

- execution_mode: `standard_memo`
- focus_tickers: `TM, UBER`
- search_scope_tickers: `F, GM, LCID, RIVN, TM, TSLA, UBER`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, auto_product_identity_context, trusted_external_context, supply_chain_official_relationship, channel_offer_proxy, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `registration/VIO, model share, true used inventory, owner demographics, ride-level marketplace data`

## Boundary

This package makes V5 lane planning and deterministic eval cases runtime-ready. Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap.
