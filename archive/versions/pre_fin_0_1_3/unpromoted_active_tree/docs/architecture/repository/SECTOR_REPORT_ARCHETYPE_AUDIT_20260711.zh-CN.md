# 跨行业投研报告结构审计

日期：2026-07-11

状态：`pass`；来源 8 个，覆盖 8 个 sector/archetype groups。

## 核心结论

公开专业报告支持三层 DecisionSurface：通用 archetype + sector cell pack + case instance。行业差异不只体现在 metric 名称，还体现在经济机制、证据 authority、commercial gap 和估值方法。

报告类型与行业是两个正交轴。Initiation、earnings/event update、sector thematic 和 peer comparison 即使处于同一行业，也需要不同的 required surfaces。

## Sector Archetypes

| Sector | Decision mechanisms | Key metrics | Evidence families |
| --- | --- | --- | --- |
| banks_financials | asset_pricing_to_nim, capital_requirement_to_distribution, channel_growth_to_volume_margin_tradeoff, credit_cost_to_roe, funding_mix_to_nim | capital_ratio, credit_loss, deposit_mix, loan_growth, net_interest_margin, price_to_book, price_to_earnings, roe | bank_disclosure, central_bank, market_data, peer_financials, prudential_regulator |
| cross_sector | evidence_to_recommendation, risk_balanced_thesis, valuation_to_target_price | - | company_disclosure, industry_context, market_data |
| cross_sector_calibration | balance_sheet_rate_credit_capital, commodity_volume_unit_cost_capital_return, earnings_delta_expectation_gap, fundamental_vs_price_in, load_rate_base_financing_regulatory_return, orders_backlog_delivery_margin_cash, platform_adoption_arr_sales_efficiency, policy_supply_chain_cost_demand, regulatory_access_supply_adoption, subscription_platform_monetization, thesis_falsification, traffic_ticket_inventory_margin | arr, backlog, cet1, free_cash_flow, implied_expectations, inventory, nim, product_revenue, rate_base, rpo, same_store_sales, unit_cost | commercial_data_gap, company_disclosure, financial_search_tool, government_and_regulator, industry_secondary, market_aggregator, web_search |
| energy_utilities_industrials | auction_economics_to_order_quality, capacity_and_supply_chain_to_margin, installed_base_to_service_revenue, lcoe_to_demand, policy_to_project_pipeline | backlog, capacity, ebit_margin, free_cash_flow, lcoe, order_intake, roic, service_mix | auction_and_tender_data, company_disclosure, energy_agency, policy_and_regulator, supply_chain_context |
| healthcare_pharma_medtech | clinical_and_regulatory_status_to_addressable_market, patent_expiry_to_erosion, product_mix_to_margin, reimbursement_to_access, sales_channel_to_adoption | gross_margin, market_access, operating_margin, patent_expiry, pipeline_stage, product_revenue, rd_spend | commercial_tracker_gap, company_disclosure, drug_regulator, reimbursement_authority, scientific_publication, trial_registry |
| retail_consumer | inventory_to_markdown_risk, loyalty_credit_real_estate_to_ecosystem_value, price_mix_promotion_to_gross_margin, store_ramp_to_return, traffic_ticket_to_same_store_sales | gross_margin, inventory_turns, sales_per_store, same_store_sales, segment_value, store_count, ticket, traffic | channel_and_store_observation, company_disclosure, consumer_macro, peer_financials, retail_statistics |
| semiconductors_ai_infrastructure | accelerator_demand_to_hbm_and_packaging, capacity_bottleneck_to_rent_capture, hyperscaler_capex_to_demand_pool, power_constraint_to_deployment, semicap_orders_to_lagged_cycle, server_orders_to_oem_revenue_and_margin | accelerator_shipments, advanced_packaging_capacity, hbm_mix, hyperscaler_capex, oem_margin, power_capacity, semicap_orders, server_backlog, server_orders | commercial_tracker_gap, company_disclosure, government_policy, industry_news, official_product_surface, social_statement_context |
| technology_software_services | acquisition_to_growth_and_leverage, margin_assumption_to_fcf, mission_critical_moat_to_retention, product_adoption_to_monetization, recurring_mix_to_revenue_quality | backlog, free_cash_flow, net_debt, operating_margin, organic_growth, recurring_revenue_mix, roic | company_disclosure, customer_and_contract_context, market_data, official_product_surface, peer_financials |

## 需要进入设计的结论

1. 通用 cells 稳定 thesis、business model、financial quality、valuation/price-in、risk/counterevidence、what-would-change。
2. Sector pack 拥有本行业的 mechanism、metric ontology、source policy、forbidden substitutions 和 valuation method。
3. Case instance 只实例化、裁剪和增加少量事件特有 cell，不能随手改写 archetype。
4. Banks 必须 balance-sheet-first；Healthcare 必须分开 regulatory eligibility、reimbursement、adoption；Retail 必须拆 traffic/ticket/price/mix/inventory；Energy/Industrial 必须包含项目经济、物理产能和政策；Technology 必须连接 product adoption、monetization、recurring mix 和 capital allocation。
5. What-Would-Change 是独立研究表面，应包含 threshold、current state、所需 evidence 和未闭环 gap，不并入主结论冒充已证实判断。

## Sources

- WorkBuddy AI infrastructure local report sample set（`docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json`）：Useful for decision-surface, source-hunting and visual-delivery calibration; not an authority source for the facts inside the reports.
- WorkBuddy multi-sector 12-case calibration set（`data/manifests/workbuddy_multisector_calibration_audit_v0_1.json`）：Proves cross-sector bounded ReAct and report-surface variety; source authority, claim lineage, numeric promotion and repeatability remain calibration gaps.
- [CFA Institute Research Challenge Student Preparation](https://www.cfainstitute.org/insights/events/research-challenge/student-preparation)：General report skeleton only; it does not prove a sector-specific cell pack.
- [Commonwealth Bank of Australia Equity Research Report](https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2020-winning-report-university-of-sydney.pdf)：Banks require a balance-sheet-first ontology and equity valuation; generic EV/EBITDA is not the main frame.
- [Vestas Wind Systems Equity Research Report](https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2021-winning-report-bi-norwegian-business-school.pdf)：Project economics, policy, physical capacity and service installed base are first-class cells.
- [Canadian Tire Equity Research Report](https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2016-winning-rpt-univ-of-waterloo.pdf)：Retail needs operating decomposition; revenue growth alone cannot prove demand or margin quality.
- [Recordati Equity Research Report](https://cfasi.it/Assets/Store/1299_Report_Politecnico_di_Milano.pdf)：Regulatory eligibility, reimbursement and commercial adoption must remain separate decision cells.
- [Motorola Solutions Equity Research Report](https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2022-winning-written-report-northern-illinois-univ.pdf)：Technology reports still require product-to-monetization and capital allocation bridges, not a generic product summary.
