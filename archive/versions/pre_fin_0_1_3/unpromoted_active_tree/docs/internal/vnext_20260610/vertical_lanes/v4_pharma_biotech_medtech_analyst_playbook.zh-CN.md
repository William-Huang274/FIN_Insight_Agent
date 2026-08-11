# V4 Analyst Playbook: Pharma / Biotech / Medtech

## Scope

- lane_id: `V4`
- industry_schema: `healthcare_pharma_medtech`
- subvertical: `pharma_biotech_medtech`
- primary_ticker_count: `68`
- representative_tickers: `LLY, NVO, PFE, AMGN, MRK, JNJ, ISRG, BSX, SYK, ZTS`
- primary_ticker_sample: `A, ABBV, ABT, ALGN, ALNY, AMGN, ARGX, AZN, BAX, BDX, BIIB, BMRN, BMY, BNTX, BSX, CAH, CI, CNC, COO, COR, CRL, CVS, DGX, DHR, DVA, DXCM, ELV, EW, GEHC, GILD, GSK, HCA, HSIC, HUM, IDXX, INCY, IQV, ISRG, JNJ, KRYS, LH, LLY, MCK, MDT, MRK, MRNA, MTD, NVO, PFE, PODD, REGN, RMD, RVTY, SNY, SOLV, STE, SYK, TECH, TMO, UHS, UNH, VEEV, VRTX, VTRS, WAT, WST, ZBH, ZTS`

## How This Lane Makes Money

This lane monetizes through approved products, pipeline programs, devices, procedures, animal health products. The analyst must connect those products or services to company-disclosed revenue/KPI/accounting lines first, then use L2/L3 rows only for mechanism, context, adoption/attention proxy, or gap repair.

## Product / Service Taxonomy

- approved drugs
- pipeline indications
- medical devices
- procedures
- clinical trials

## Financial Statement Focus

- product revenue
- R&D
- gross margin
- SG&A
- acquired IPR&D
- cash runway for biotech

## Company-Disclosed KPI Focus

- product sales
- procedure/device volumes if disclosed
- pipeline milestones

## Strong Facts

- Company filings, official annual/quarterly reports, SEC/FSD/company IR, and company-disclosed KPI rows are the only authority for issuer-level financial facts.
- Official product/service pages can support product existence, taxonomy, specs, pricing-page context, and product positioning, but not sales/share unless the company discloses it.

## Context / Proxy Signals

- public_tenders_contracts_orders can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- job_postings_hiring_signals can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- procedure_public_leads_where_available can support directional context only after issuer/product binding; it cannot prove sales, margin, share, or exact demand.
- clinicaltrials_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- openfda_api can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- cms_public_data can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- labels can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.
- advisory_committee_materials can support official/regulatory context within its scope; issuer financial conclusions still require L1/company disclosure.

## Typical Misreads To Block

- Using public proxy rows as if they were company revenue, sales volume, market share, ASP, or margin authority.
- Letting L4 search/forum/social leads enter ClaimCards or core thesis without L1/L2/L3 repair.
- Treating a commercial tracker gap as solved by a noisy public proxy.
- Ignoring the lane-specific financial statement focus and writing generic evidence summaries.
