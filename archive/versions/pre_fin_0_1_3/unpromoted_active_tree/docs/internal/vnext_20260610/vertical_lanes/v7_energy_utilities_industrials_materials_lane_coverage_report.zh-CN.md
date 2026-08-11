# V7 Energy / Utilities / Industrials Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `216`
- inclusive_ticker_count: `219`
- product_kpi_ready_ticker_count: `71`
- official_product_surface_ticker_count: `209`
- commercial_gap_count: `1037`

## Representative Cases

### v7_energy_utilities_industrials_materials_financial_product_bridge_001

- execution_mode: `deep_research`
- focus_tickers: `XOM, CVX`
- search_scope_tickers: `COP, CVX, DUK, NEE, SLB, SO, XEL, XOM`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, energy_utility_context, trusted_external_context, supply_chain_official_relationship, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `asset-level utilization where not disclosed, dealer sell-through, private project economics, equipment order pipeline`

### v7_energy_utilities_industrials_materials_external_source_repair_boundary_002

- execution_mode: `deep_research`
- focus_tickers: `COP, SLB, NEE`
- search_scope_tickers: `COP, CVX, DUK, ED, GE, NEE, SLB, SO, XEL, XOM`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, energy_utility_context, trusted_external_context, supply_chain_official_relationship, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `asset-level utilization where not disclosed, dealer sell-through, private project economics, equipment order pipeline`

### v7_energy_utilities_industrials_materials_proxy_no_promotion_003

- execution_mode: `standard_memo`
- focus_tickers: `DUK, SO, XEL`
- search_scope_tickers: `COP, CVX, DUK, NEE, SLB, SO, XEL, XOM`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, energy_utility_context, trusted_external_context, supply_chain_official_relationship, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `asset-level utilization where not disclosed, dealer sell-through, private project economics, equipment order pipeline`

## Boundary

This package makes V7 lane planning and deterministic eval cases runtime-ready. Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap.
