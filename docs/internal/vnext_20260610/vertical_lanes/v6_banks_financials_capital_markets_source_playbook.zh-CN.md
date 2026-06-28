# V6 Source Playbook: Banks / Financials / Capital Markets

## L1 Required Facts

- deposits
- loans
- NII
- charge-offs
- capital ratios
- AUM
- trading/capital markets revenue

## L2 Trusted / Official Sources

- call_reports
- company_ir_reports
- company_product_pages
- fdic_bankfind_api
- fred_api
- mainstream_financial_news
- official_exchange_statistics
- regulatory_releases

## L3 Proxy Sources

- app_store_rankings
- market_reaction_context

## L4 Discovery Boundary

- social_or_news_chatter_as_regulatory_event_discovery_only
- common_crawl_index

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- FDIC/FRED and market data explain macro/regulatory context, not company revenue or real-time flows unless issuer/official statistics disclose it

## Expected Commercial Gaps

- real-time flows
- private deposit migration
- advisor-channel detail
- consensus revision

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `4`
- gap_requirement_count: `1`
- fail_requirement_count: `0`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
