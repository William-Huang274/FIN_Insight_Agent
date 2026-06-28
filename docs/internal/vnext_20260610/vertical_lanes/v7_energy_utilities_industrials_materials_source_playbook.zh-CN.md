# V7 Source Playbook: Energy / Utilities / Industrials

## L1 Required Facts

- production
- reserves
- capex
- regulated rate base
- fuel costs
- backlog/order book if disclosed

## L2 Trusted / Official Sources

- company_ir_reports
- company_product_pages
- eia_open_data
- environmental_regulatory_data
- ferc_state_utility_filings
- fred_api
- industry_association_reports
- mainstream_financial_news
- official_project_pages
- supplier_customer_official_news

## L3 Proxy Sources

- public_tenders_contracts_orders
- job_postings_hiring_signals
- dealer_channel_listings

## L4 Discovery Boundary

- local_chatter_as_project_or_regulatory_filing_lead_only
- common_crawl_index

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- EIA/FRED/regulatory data are context/exposure bridges, not single-company revenue/margin proof unless the issuer discloses it

## Expected Commercial Gaps

- asset-level utilization where not disclosed
- dealer sell-through
- private project economics
- equipment order pipeline

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `7`
- gap_requirement_count: `1`
- fail_requirement_count: `0`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
