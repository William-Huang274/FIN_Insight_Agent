# V6 Analyst Playbook: Banks / Financials / Capital Markets

## Scope

- lane_id: `V6`
- industry_schema: `financials_banks`
- subvertical: `banks_financials_capital_markets`
- primary_ticker_count: `77`
- representative_tickers: `JPM, BAC, WFC, C, GS, MS, BLK, SCHW, CBOE`
- primary_ticker_sample: `ACGL, AFL, AIG, AIZ, AJG, ALL, AMP, AON, APO, ARES, AXP, BAC, BEN, BK, BLK, BR, BRK-B, BRO, BX, C, CB, CBOE, CFG, CINF, CME, COF, COIN, CPAY, EG, ERIE, FDS, FIS, FISV, FITB, GL, GPN, GS, HBAN, HIG, HOOD, IBKR, ICE, IVZ, JKHY, JPM, KEY, KKR, L, MA, MCO, MET, MRSH, MS, MSCI, MTB, NDAQ, NTRS, PFG, PGR, PNC, PRU, PYPL, RF, RJF, SCHW, SPGI, STT, SYF, TFC, TROW, TRV, USB, V, WFC, WRB, WTW, XYZ`

## How This Lane Makes Money

This lane monetizes through banking, trading, wealth management, asset management, exchange data/transactions. The analyst must connect those products or services to company-disclosed revenue/KPI/accounting lines first, then use L2/L3 rows only for mechanism, context, adoption/attention proxy, or gap repair.

## Product / Service Taxonomy

- net interest income
- deposits
- loans
- trading
- wealth/AUM
- capital markets
- exchange volumes

## Financial Statement Focus

- net interest income
- deposit beta
- loan growth
- credit costs
- capital ratios
- AUM
- trading revenue

## Company-Disclosed KPI Focus

- deposits
- loans
- AUM/AUA
- trading metrics
- exchange volumes if disclosed

## Strong Facts

- Company filings, official annual/quarterly reports, SEC/FSD/company IR, and company-disclosed KPI rows are the only authority for issuer-level financial facts.
- Official product/service pages can support product existence, taxonomy, specs, pricing-page context, and product positioning, but not sales/share unless the company discloses it.

## Context / Proxy Signals

- app_store_rankings can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- market_reaction_context can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- fdic_bankfind_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- fred_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- call_reports can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- official_exchange_statistics can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.

## Typical Misreads To Block

- Using public proxy rows as if they were company revenue, sales volume, market share, ASP, or margin authority.
- Letting L4 search/forum/social leads enter ClaimCards or core thesis without L1/L2/L3 repair.
- Treating a commercial tracker gap as solved by a noisy public proxy.
- Ignoring the lane-specific financial statement focus and writing generic evidence summaries.
