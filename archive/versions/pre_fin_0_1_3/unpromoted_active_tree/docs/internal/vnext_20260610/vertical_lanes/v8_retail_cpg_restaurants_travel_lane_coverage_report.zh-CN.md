# V8 Retail / CPG / Restaurants / Travel Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `79`
- inclusive_ticker_count: `80`
- product_kpi_ready_ticker_count: `25`
- official_product_surface_ticker_count: `79`
- commercial_gap_count: `395`

## Representative Cases

### v8_retail_cpg_restaurants_travel_financial_product_bridge_001

- execution_mode: `deep_research`
- focus_tickers: `WMT, COST`
- search_scope_tickers: `COST, HD, KO, LOW, PEP, PG, TGT, WMT`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, trusted_external_context, channel_offer_proxy, platform_review_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `Circana/NielsenIQ POS, scanner/panel data, traffic trackers, private booking conversion, promotion/channel inventory`

### v8_retail_cpg_restaurants_travel_external_source_repair_boundary_002

- execution_mode: `deep_research`
- focus_tickers: `TGT, HD, LOW`
- search_scope_tickers: `COST, HD, KO, LOW, NKE, PEP, PG, SBUX, TGT, WMT`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, trusted_external_context, channel_offer_proxy, platform_review_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `Circana/NielsenIQ POS, scanner/panel data, traffic trackers, private booking conversion, promotion/channel inventory`

### v8_retail_cpg_restaurants_travel_proxy_no_promotion_003

- execution_mode: `standard_memo`
- focus_tickers: `PG, KO, PEP`
- search_scope_tickers: `COST, HD, KO, LOW, PEP, PG, TGT, WMT`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, trusted_external_context, channel_offer_proxy, platform_review_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `Circana/NielsenIQ POS, scanner/panel data, traffic trackers, private booking conversion, promotion/channel inventory`

## Boundary

This package makes V8 lane planning and deterministic eval cases runtime-ready. Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap.
