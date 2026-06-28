# V4 Pharma / Biotech / Medtech Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `68`
- inclusive_ticker_count: `68`
- product_kpi_ready_ticker_count: `24`
- official_product_surface_ticker_count: `68`
- commercial_gap_count: `340`

## Representative Cases

### v4_pharma_biotech_medtech_financial_product_bridge_001

- execution_mode: `deep_research`
- focus_tickers: `LLY, NVO`
- search_scope_tickers: `AMGN, BSX, ISRG, JNJ, LLY, MRK, NVO, PFE`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, regulated_product_context, trusted_external_context, technology_research_proxy, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `IQVIA/Symphony scripts, prescription share, procedure volumes, hospital channel sell-through`

### v4_pharma_biotech_medtech_external_source_repair_boundary_002

- execution_mode: `deep_research`
- focus_tickers: `PFE, AMGN, MRK`
- search_scope_tickers: `AMGN, BSX, ISRG, JNJ, LLY, MRK, NVO, PFE, SYK, ZTS`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, regulated_product_context, trusted_external_context, technology_research_proxy, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `IQVIA/Symphony scripts, prescription share, procedure volumes, hospital channel sell-through`

### v4_pharma_biotech_medtech_proxy_no_promotion_003

- execution_mode: `standard_memo`
- focus_tickers: `JNJ, ISRG, BSX`
- search_scope_tickers: `AMGN, BSX, ISRG, JNJ, LLY, MRK, NVO, PFE`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- required_source_requirements: `primary_company_disclosure, official_product_surface, regulated_product_context, trusted_external_context, technology_research_proxy, public_order_proxy, hiring_capacity_proxy, macro_official_context`
- expected_commercial_gaps: `IQVIA/Symphony scripts, prescription share, procedure volumes, hospital channel sell-through`

## Boundary

This package makes V4 lane planning and deterministic eval cases runtime-ready. Runtime source closeout must still classify each missing route as pass, retrievable/parser gap, bounded public gap, or commercial gap.
