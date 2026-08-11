# Vertical Source Lane Registry

- schema_version: `finsight_vertical_source_lane_registry_v0_1`
- generated_at: `2026-06-23T08:18:28Z`
- status: `pass`
- company_count: `603`
- registry_digest: `edcea62d8cf15d04`

## Lane Summary

| lane | primary tickers | all tickers | product KPI ready | official surface ready | commercial gaps | coverage gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `V1` Semiconductors / AI Infrastructure | 43 | 57 | 12 | 43 | 210 | gap |
| `V2` Consumer Electronics / Hardware Devices | 9 | 12 | 3 | 9 | 45 | gap |
| `V3` SaaS / Cloud / Developer Products | 96 | 99 | 27 | 96 | 455 | gap |
| `V4` Pharma / Biotech / Medtech | 68 | 68 | 34 | 68 | 340 | gap |
| `V5` Auto / Mobility / Transport Platforms | 14 | 14 | 6 | 14 | 70 | gap |
| `V6` Banks / Financials / Capital Markets | 77 | 77 | 26 | 45 | 5 | gap |
| `V7` Energy / Utilities / Industrials | 215 | 218 | 74 | 215 | 1032 | gap |
| `V8` Retail / CPG / Restaurants / Travel | 81 | 82 | 32 | 81 | 405 | gap |

## Lane Details

### V1 Semiconductors / AI Infrastructure

- industry_schema: `semiconductors_hardware`
- primary_ticker_count: `43`
- secondary_inclusive_ticker_count: `57`
- representative_tickers: `NVDA, AMD, INTC, QCOM, AVGO, ASML, TSM, AMAT, LRCX, KLAC, DELL, SMCI, HPE, ANET, MRVL`
- product_taxonomy_scope: `GPU/accelerator, CPU, ASIC, NIC/networking, wafer fab/foundry, advanced packaging, lithography, deposition/etch/metrology, AI server/rack`
- public_data_ceiling: `public sources cannot prove vendor share, sell-through, allocation, channel inventory, or tracker forecasts without company disclosure`
- expected_commercial_gaps: `IDC/Counterpoint/Omdia/Gartner shipments/share/forecast; supply allocation; hyperscaler exact purchase orders; channel inventory`

- coverage_gate: `gap`; requirements=`10`; gaps=`2`; fail=`0`
- l1_required_facts: `segment/product revenue, inventory, purchase commitments, capex, gross margin, customer concentration, backlog/order commentary, 20-F/6-K/local filings for non-US issuers`
- l2_trusted_context_sources: `mainstream_financial_news, supplier_customer_official_news, industry_association_reports`
- l3_proxy_sources: `channel_pricing_quotations, public_tenders_contracts_orders, job_postings_hiring_signals, developer_ecosystem_github_npm_pypi_huggingface`
- l4_discovery_sources: `common_crawl_index, unverified_self_media_forums, yahoo_chart`

### V2 Consumer Electronics / Hardware Devices

- industry_schema: `consumer_electronics`
- primary_ticker_count: `9`
- secondary_inclusive_ticker_count: `12`
- representative_tickers: `AAPL, MSFT, GOOGL, DELL, HPQ, SONY`
- product_taxonomy_scope: `phones, tablets, PCs, wearables, gaming hardware, smart devices, device services ecosystem`
- public_data_ceiling: `public channels can show price/configuration/availability but not ASP, sell-through, shipment share, or channel inventory`
- expected_commercial_gaps: `IDC/Canalys/Counterpoint device shipments/share; retailer POS/sell-through; channel inventory; ASP tracker`

- coverage_gate: `gap`; requirements=`8`; gaps=`1`; fail=`0`
- l1_required_facts: `segment revenue, unit commentary if disclosed, warranty, inventory, channel comments, services attach where disclosed`
- l2_trusted_context_sources: `mainstream_financial_news, supplier_customer_official_news`
- l3_proxy_sources: `ecommerce_major_platforms, channel_pricing_quotations, app_store_rankings, platform_reviews_rankings_downloads`
- l4_discovery_sources: `common_crawl_index, unverified_self_media_forums, search_snippet`

### V3 SaaS / Cloud / Developer Products

- industry_schema: `software_saas`
- primary_ticker_count: `96`
- secondary_inclusive_ticker_count: `99`
- representative_tickers: `MSFT, AMZN, GOOGL, CRM, NOW, ADBE, SNOW, DDOG, NET, PLTR, MDB, TEAM`
- product_taxonomy_scope: `cloud infrastructure, AI services, observability, data platform, security, workflow, developer tools, marketplace apps`
- public_data_ceiling: `developer activity and public contracts are adoption/context proxies, not revenue, retention, or share proof`
- expected_commercial_gaps: `net retention benchmarks; third-party web traffic/commercial intent; private cloud usage; consensus revision`

- coverage_gate: `gap`; requirements=`9`; gaps=`1`; fail=`0`
- l1_required_facts: `segment revenue, RPO/cRPO/billings, deferred revenue, sales efficiency, capex/leases if infra-heavy`
- l2_trusted_context_sources: `mainstream_financial_news, supplier_customer_official_news`
- l3_proxy_sources: `developer_ecosystem_github_npm_pypi_huggingface, job_postings_hiring_signals, public_tenders_contracts_orders, app_store_rankings`
- l4_discovery_sources: `developer_forums_as_discovery_only, common_crawl_index, search_snippet`

### V4 Pharma / Biotech / Medtech

- industry_schema: `healthcare_pharma_medtech`
- primary_ticker_count: `68`
- secondary_inclusive_ticker_count: `68`
- representative_tickers: `LLY, NVO, PFE, AMGN, MRK, JNJ, ISRG, BSX, SYK, ZTS`
- product_taxonomy_scope: `approved drugs, pipeline indications, medical devices, procedures, clinical trials`
- public_data_ceiling: `ClinicalTrials/openFDA/CMS support R&D/regulatory/use context, not prescriptions, utilization share, or sales unless company/official source states it`
- expected_commercial_gaps: `IQVIA/Symphony scripts; prescription share; procedure volumes; hospital channel sell-through`

- coverage_gate: `gap`; requirements=`8`; gaps=`3`; fail=`0`
- l1_required_facts: `product sales if disclosed, pipeline table, R&D, acquired IPR&D, milestone obligations`
- l2_trusted_context_sources: `mainstream_financial_news, official_press_releases, medical_guidelines_where_public`
- l3_proxy_sources: `public_tenders_contracts_orders, job_postings_hiring_signals, procedure_public_leads_where_available`
- l4_discovery_sources: `patient_community_discussion_as_discovery_only, common_crawl_index`

### V5 Auto / Mobility / Transport Platforms

- industry_schema: `auto_mobility`
- primary_ticker_count: `14`
- secondary_inclusive_ticker_count: `14`
- representative_tickers: `TSLA, GM, F, RIVN, LCID, TM, UBER`
- product_taxonomy_scope: `vehicle model, platform, battery/charging, autonomy, mobility marketplace`
- public_data_ceiling: `listings/app ranks/owner forums are proxy or discovery only, not sales, ASP, reliability rate, or profitability proof`
- expected_commercial_gaps: `registration/VIO; model share; true used inventory; owner demographics; ride-level marketplace data`

- coverage_gate: `gap`; requirements=`9`; gaps=`2`; fail=`0`
- l1_required_facts: `deliveries, ASP commentary if disclosed, inventory, warranty, capex, deferred revenue, credits`
- l2_trusted_context_sources: `mainstream_financial_news, supplier_customer_official_news`
- l3_proxy_sources: `used_new_listing_proxy, app_store_rankings, job_postings_hiring_signals, public_tenders_contracts_orders`
- l4_discovery_sources: `owner_forums_as_recall_or_service_bulletin_lead_only, common_crawl_index`

### V6 Banks / Financials / Capital Markets

- industry_schema: `financials_banks`
- primary_ticker_count: `77`
- secondary_inclusive_ticker_count: `77`
- representative_tickers: `JPM, BAC, WFC, C, GS, MS, BLK, SCHW, CBOE`
- product_taxonomy_scope: `net interest income, deposits, loans, trading, wealth/AUM, capital markets, exchange volumes`
- public_data_ceiling: `FDIC/FRED and market data explain macro/regulatory context, not company revenue or real-time flows unless issuer/official statistics disclose it`
- expected_commercial_gaps: `real-time flows; private deposit migration; advisor-channel detail; consensus revision`

- coverage_gate: `gap`; requirements=`6`; gaps=`1`; fail=`0`
- l1_required_facts: `deposits, loans, NII, charge-offs, capital ratios, AUM, trading/capital markets revenue`
- l2_trusted_context_sources: `mainstream_financial_news, regulatory_releases`
- l3_proxy_sources: `app_store_rankings, market_reaction_context`
- l4_discovery_sources: `social_or_news_chatter_as_regulatory_event_discovery_only, common_crawl_index`

### V7 Energy / Utilities / Industrials

- industry_schema: `energy_utilities`
- primary_ticker_count: `215`
- secondary_inclusive_ticker_count: `218`
- representative_tickers: `XOM, CVX, COP, SLB, NEE, DUK, SO, XEL, ED, GE, CAT, DE`
- product_taxonomy_scope: `upstream/downstream, oilfield services, generation assets, regulated utility territories, industrial equipment, power/datacenter infrastructure`
- public_data_ceiling: `EIA/FRED/regulatory data are context/exposure bridges, not single-company revenue/margin proof unless the issuer discloses it`
- expected_commercial_gaps: `asset-level utilization where not disclosed; dealer sell-through; private project economics; equipment order pipeline`

- coverage_gate: `gap`; requirements=`7`; gaps=`1`; fail=`0`
- l1_required_facts: `production, reserves, capex, regulated rate base, fuel costs, backlog/order book if disclosed`
- l2_trusted_context_sources: `mainstream_financial_news, supplier_customer_official_news, industry_association_reports`
- l3_proxy_sources: `public_tenders_contracts_orders, job_postings_hiring_signals, dealer_channel_listings`
- l4_discovery_sources: `local_chatter_as_project_or_regulatory_filing_lead_only, common_crawl_index`

### V8 Retail / CPG / Restaurants / Travel

- industry_schema: `retail_cpg`
- primary_ticker_count: `81`
- secondary_inclusive_ticker_count: `82`
- representative_tickers: `WMT, COST, TGT, HD, LOW, PG, KO, PEP, NKE, SBUX, MCD, BKNG, ABNB`
- product_taxonomy_scope: `store/channel, category mix, menu/SKU, pricing/promotion, traffic, membership/loyalty, travel inventory`
- public_data_ceiling: `public listings/reviews/app ranks can support price/menu/attention context, not POS sell-through, product share, traffic, or channel inventory`
- expected_commercial_gaps: `Circana/NielsenIQ POS; scanner/panel data; traffic trackers; private booking conversion; promotion/channel inventory`

- coverage_gate: `gap`; requirements=`7`; gaps=`1`; fail=`0`
- l1_required_facts: `same-store sales, transactions, ticket, inventory, gross margin, advertising/promotional spend when disclosed`
- l2_trusted_context_sources: `mainstream_financial_news, company_official_news, census_retail_sales, bls_cpi`
- l3_proxy_sources: `ecommerce_major_platforms, app_store_rankings, platform_reviews_rankings_downloads, job_postings_hiring_signals`
- l4_discovery_sources: `consumer_chatter_as_discovery_only, common_crawl_index`
