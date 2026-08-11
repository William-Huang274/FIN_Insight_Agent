# V8 Source Playbook: Retail / CPG / Restaurants / Travel

## L1 Required Facts

- same-store sales
- transactions
- ticket
- inventory
- gross margin
- advertising/promotional spend when disclosed

## L2 Trusted / Official Sources

- bls_cpi
- bls_public_api
- census_data_api
- census_retail_sales
- company_ir_reports
- company_official_news
- company_product_pages
- fred_api
- mainstream_financial_news
- official_menu_store_pages

## L3 Proxy Sources

- ecommerce_major_platforms
- app_store_rankings
- platform_reviews_rankings_downloads
- job_postings_hiring_signals

## L4 Discovery Boundary

- consumer_chatter_as_discovery_only
- common_crawl_index

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- public listings/reviews/app ranks can support price/menu/attention context, not POS sell-through, product share, traffic, or channel inventory

## Expected Commercial Gaps

- Circana/NielsenIQ POS
- scanner/panel data
- traffic trackers
- private booking conversion
- promotion/channel inventory

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `7`
- gap_requirement_count: `1`
- fail_requirement_count: `0`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
