# V6 Banks / Financials / Capital Markets Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `77`
- inclusive_ticker_count: `77`
- product_kpi_ready_ticker_count: `25`
- official_product_surface_ticker_count: `1`
- commercial_gap_count: `5`

## Representative Cases

### v6_banks_financials_capital_markets_financial_product_bridge_001

- execution_mode: `deep_research`
- focus_tickers: `JPM, BAC`
- search_scope_tickers: `BAC, BLK, C, GS, JPM, MS, SCHW, WFC`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, financial_regulatory_context, trusted_external_context, macro_official_context`
- expected_commercial_gaps: `real-time flows, private deposit migration, advisor-channel detail, consensus revision`

### v6_banks_financials_capital_markets_external_source_repair_boundary_002

- execution_mode: `deep_research`
- focus_tickers: `WFC, C, GS`
- search_scope_tickers: `BAC, BLK, C, CBOE, GS, JPM, MS, SCHW, WFC`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, financial_regulatory_context, trusted_external_context, macro_official_context`
- expected_commercial_gaps: `real-time flows, private deposit migration, advisor-channel detail, consensus revision`

### v6_banks_financials_capital_markets_proxy_no_promotion_003

- execution_mode: `standard_memo`
- focus_tickers: `MS, BLK, SCHW`
- search_scope_tickers: `BAC, BLK, C, GS, JPM, MS, SCHW, WFC`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, financial_regulatory_context, trusted_external_context, macro_official_context`
- expected_commercial_gaps: `real-time flows, private deposit migration, advisor-channel detail, consensus revision`

## Boundary

This package makes V6 lane planning and deterministic eval cases runtime-ready. Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap.
