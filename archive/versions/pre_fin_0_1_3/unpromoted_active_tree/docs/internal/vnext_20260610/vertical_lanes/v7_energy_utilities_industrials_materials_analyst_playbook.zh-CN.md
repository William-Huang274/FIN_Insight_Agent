# V7 Analyst Playbook: Energy / Utilities / Industrials

## Scope

- lane_id: `V7`
- industry_schema: `energy_utilities`
- subvertical: `energy_utilities_industrials_materials`
- primary_ticker_count: `216`
- representative_tickers: `XOM, CVX, COP, SLB, NEE, DUK, SO, XEL, ED, GE, CAT, DE`
- primary_ticker_sample: `2308.TW, 300750.SZ, 373220.KS, 6752.T, AEE, AEP, AES, ALB, ALLE, AMCR, AME, AMT, AOS, APA, APD, ARE, ARRY, ATO, AVB, AVY, AWK, AXON, BA, BALL, BE, BHP, BKR, BLDR, BWXT, BXP, CARR, CAT, CBRE, CCI, CCJ, CE, CEG, CF, CHRW, CMI, CMS, CNP, COP, CPRT, CPT, CRH, CSGP, CSX, CTAS, CTRA, CTVA, CVX, D, DAL, DD, DE, DLR, DNN, DOC, DOV, DOW, DQ, DTE, DUK, DVN, ECL, ED, EFX, EIX, EME, EMR, ENLT, ENPH, EOG, EQIX, EQR, EQT, ES, ESS, ETN, ETR, EVRG, EXC, EXE, EXPD, EXR, FANG, FAST, FCX, FDX, FDXF, FE, FIX, FLNC, FRT, FTV, GD, GE, GEV, GNRC`

## How This Lane Makes Money

This lane monetizes through oil/gas production, utility rate base, industrial equipment, power equipment, services/backlog. The analyst must connect those products or services to company-disclosed revenue/KPI/accounting lines first, then use L2/L3 rows only for mechanism, context, adoption/attention proxy, or gap repair.

## Product / Service Taxonomy

- upstream/downstream
- oilfield services
- generation assets
- regulated utility territories
- industrial equipment
- power/datacenter infrastructure

## Financial Statement Focus

- capex
- asset base
- debt/liquidity
- working capital
- regulated returns
- backlog/orders
- commodity sensitivity

## Company-Disclosed KPI Focus

- production
- rate base
- backlog/orders
- equipment deliveries
- capacity/utilization if disclosed

## Strong Facts

- Company filings, official annual/quarterly reports, SEC/FSD/company IR, and company-disclosed KPI rows are the only authority for issuer-level financial facts.
- Official product/service pages can support product existence, taxonomy, specs, pricing-page context, and product positioning, but not sales/share unless the company discloses it.

## Context / Proxy Signals

- public_tenders_contracts_orders can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- job_postings_hiring_signals can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- dealer_channel_listings can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- eia_open_data can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- ferc_state_utility_filings can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- environmental_regulatory_data can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- fred_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.

## Typical Misreads To Block

- Using public proxy rows as if they were company revenue, sales volume, market share, ASP, or margin authority.
- Letting L4 search/forum/social leads enter ClaimCards or core thesis without L1/L2/L3 repair.
- Treating a commercial tracker gap as solved by a noisy public proxy.
- Ignoring the lane-specific financial statement focus and writing generic evidence summaries.
