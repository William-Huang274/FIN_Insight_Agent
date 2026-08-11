# V2 Source Playbook: Consumer Electronics / Hardware Devices

## L1 Required Facts

- segment revenue
- unit commentary if disclosed
- warranty
- inventory
- channel comments
- services attach where disclosed

## L2 Trusted / Official Sources

- company_ir_reports
- company_product_pages
- mainstream_financial_news
- official_product_specs
- regulatory_certification_where_available
- supplier_customer_official_news

## L3 Proxy Sources

- ecommerce_major_platforms
- channel_pricing_quotations
- app_store_rankings
- platform_reviews_rankings_downloads

## L4 Discovery Boundary

- common_crawl_index
- unverified_self_media_forums
- search_snippet

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- public channels can show price/configuration/availability but not ASP, sell-through, shipment share, or channel inventory

## Expected Commercial Gaps

- IDC/Canalys/Counterpoint device shipments/share
- retailer POS/sell-through
- channel inventory
- ASP tracker

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `8`
- gap_requirement_count: `1`
- fail_requirement_count: `0`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
