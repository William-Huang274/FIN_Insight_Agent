# V5 Source Playbook: Auto / Mobility / Transport Platforms

## L1 Required Facts

- deliveries
- ASP commentary if disclosed
- inventory
- warranty
- capex
- deferred revenue
- credits

## L2 Trusted / Official Sources

- charging_network_official_data
- company_ir_reports
- company_product_pages
- complaints
- mainstream_financial_news
- nhtsa_vpic_api
- official_model_pages
- recalls
- regulatory_filings
- supplier_customer_official_news

## L3 Proxy Sources

- used_new_listing_proxy
- app_store_rankings
- job_postings_hiring_signals
- public_tenders_contracts_orders

## L4 Discovery Boundary

- owner_forums_as_recall_or_service_bulletin_lead_only
- common_crawl_index

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- listings/app ranks/owner forums are proxy or discovery only, not sales, ASP, reliability rate, or profitability proof

## Expected Commercial Gaps

- registration/VIO
- model share
- true used inventory
- owner demographics
- ride-level marketplace data

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `9`
- gap_requirement_count: `2`
- fail_requirement_count: `0`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
