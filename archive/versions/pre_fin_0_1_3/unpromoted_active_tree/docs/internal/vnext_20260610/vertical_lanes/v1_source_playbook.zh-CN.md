# V1 Source Playbook: Semiconductors / AI Infrastructure

## L1 Required Facts

- segment/product revenue
- inventory
- purchase commitments
- capex
- gross margin
- customer concentration
- backlog/order commentary
- 20-F/6-K/local filings for non-US issuers

## L2 Trusted / Official Sources

- company_ir_reports
- company_product_pages
- export_control_regulators
- industry_association_reports
- mainstream_financial_news
- official_product_specs
- official_trade_statistics
- openalex_api
- patentsview_api
- supplier_customer_official_news

## L3 Proxy Sources

- channel_pricing_quotations
- public_tenders_contracts_orders
- job_postings_hiring_signals
- developer_ecosystem_github_npm_pypi_huggingface

## L4 Discovery Boundary

- common_crawl_index
- unverified_self_media_forums
- yahoo_chart

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- public sources cannot prove vendor share, sell-through, allocation, channel inventory, or tracker forecasts without company disclosure

## Expected Commercial Gaps

- IDC/Counterpoint/Omdia/Gartner shipments/share/forecast
- supply allocation
- hyperscaler exact purchase orders
- channel inventory

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `10`
- gap_requirement_count: `2`
- fail_requirement_count: `0`

The gate being `gap` is not a failure of this playbook. It means V1 source closeout must continue against lane-specific missing requirements.
