# V1 Semiconductors / AI Infrastructure Lane Coverage Report

- validation: `pass`
- source_coverage_gate: `gap`
- primary_ticker_count: `43`
- inclusive_ticker_count: `57`
- product_kpi_ready_ticker_count: `9`
- official_product_surface_ticker_count: `42`
- commercial_gap_count: `210`

## Representative Cases

### v1_ai_infra_demand_transmission_nvda_dell_hyperscaler_001

- execution_mode: `deep_research`
- focus_tickers: `NVDA, DELL`
- search_scope_tickers: `NVDA, DELL, ANET, VRT, SMCI, HPE, MSFT, AMZN, GOOGL`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- expected_commercial_gaps: `hyperscaler exact purchase orders, allocation, channel inventory, IDC/Counterpoint/Omdia/Gartner shipments/share/forecast`

### v1_semicap_nonus_local_filing_asml_tsm_amat_lrcx_002

- execution_mode: `deep_research`
- focus_tickers: `ASML, TSM`
- search_scope_tickers: `ASML, TSM, AMAT, LRCX, KLAC, NVDA, AMD`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- expected_commercial_gaps: `tool shipment/share tracker, customer-specific allocation, private order book detail`

### v1_ai_server_channel_proxy_boundary_dell_hpe_smci_anet_003

- execution_mode: `standard_memo`
- focus_tickers: `DELL, HPE`
- search_scope_tickers: `DELL, HPE, SMCI, ANET, NVDA`
- required_dimensions: `fundamentals, product_and_production, capital_and_financing, industry_supply_chain, competition_and_market_position, risk_and_counterevidence`
- expected_commercial_gaps: `sell-through, ASP, inventory, server shipment share`

## Boundary

This package makes V1 lane planning and deterministic eval cases runtime-ready. It does not claim all V1 L2/L3 source routes are complete; lane_source_coverage_gate remains authoritative.
