# V8 Analyst Playbook: Retail / CPG / Restaurants / Travel

## Scope

- lane_id: `V8`
- industry_schema: `retail_cpg`
- subvertical: `retail_cpg_restaurants_travel`
- primary_ticker_count: `79`
- representative_tickers: `WMT, COST, TGT, HD, LOW, PG, KO, PEP, NKE, SBUX, MCD, BKNG, ABNB`
- primary_ticker_sample: `ABNB, ADM, APTV, BBY, BF-B, BG, BKNG, CAG, CASY, CCL, CHD, CL, CLX, COST, CPB, CVNA, DASH, DECK, DG, DHI, DLTR, DPZ, DRI, EBAY, EL, EXPE, GIS, GRMN, HAS, HD, HLT, HRL, HST, HSY, KDP, KHC, KMB, KO, KR, KVUE, LEN, LOW, LULU, LVS, MAR, MCD, MDLZ, MELI, MGM, MKC, MNST, MO, NCLH, NKE, NVR, PEP, PG, PHM, PM, POOL, RCL, RL, ROST, RUN, SBUX, SJM, STZ, SYY, TAP, TGT, TJX, TPR, TSCO, TSN, ULTA, WMT, WSM, WYNN, YUM`

## How This Lane Makes Money

This lane monetizes through retail categories, CPG brands, restaurant menu, travel marketplace, membership/loyalty. The analyst must connect those products or services to company-disclosed revenue/KPI/accounting lines first, then use L2/L3 rows only for mechanism, context, adoption/attention proxy, or gap repair.

## Product / Service Taxonomy

- store/channel
- category mix
- menu/SKU
- pricing/promotion
- traffic
- membership/loyalty
- travel inventory

## Financial Statement Focus

- comparable sales
- gross margin
- inventory
- traffic/ticket
- advertising/promotion
- working capital
- loyalty/membership

## Company-Disclosed KPI Focus

- same-store sales
- transactions/ticket
- store count
- membership
- bookings/room nights if disclosed

## Strong Facts

- Company filings, official annual/quarterly reports, SEC/FSD/company IR, and company-disclosed KPI rows are the only authority for issuer-level financial facts.
- Official product/service pages can support product existence, taxonomy, specs, pricing-page context, and product positioning, but not sales/share unless the company discloses it.

## Context / Proxy Signals

- ecommerce_major_platforms can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- app_store_rankings can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- platform_reviews_rankings_downloads can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- job_postings_hiring_signals can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- census_data_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- bls_public_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- fred_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.

## Typical Misreads To Block

- Using public proxy rows as if they were company revenue, sales volume, market share, ASP, or margin authority.
- Letting L4 search/forum/social leads enter ClaimCards or core thesis without L1/L2/L3 repair.
- Treating a commercial tracker gap as solved by a noisy public proxy.
- Ignoring the lane-specific financial statement focus and writing generic evidence summaries.
