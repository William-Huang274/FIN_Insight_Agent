# V4 Source Playbook: Pharma / Biotech / Medtech

## L1 Required Facts

- product sales if disclosed
- pipeline table
- R&D
- acquired IPR&D
- milestone obligations

## L2 Trusted / Official Sources

- advisory_committee_materials
- clinicaltrials_api
- cms_public_data
- company_ir_reports
- company_product_pages
- labels
- mainstream_financial_news
- medical_guidelines_where_public
- official_label_or_device_pages
- official_press_releases
- openfda_api

## L3 Proxy Sources

- public_tenders_contracts_orders
- job_postings_hiring_signals
- procedure_public_leads_where_available

## L4 Discovery Boundary

- patient_community_discussion_as_discovery_only
- common_crawl_index

L4 must stay as `WeakSignalLead`, `WeakSignalExclusionNote`, or `L4PromotionAttempt`. It cannot become ClaimCard evidence.

## Public Data Ceiling

- ClinicalTrials/openFDA/CMS support R&D/regulatory/use context, not prescriptions, utilization share, or sales unless company/official source states it

## Expected Commercial Gaps

- IQVIA/Symphony scripts
- prescription share
- procedure volumes
- hospital channel sell-through

## Current Registry Coverage Gate

- status: `gap`
- requirement_count: `8`
- gap_requirement_count: `3`
- fail_requirement_count: `0`

Registry `gap` means source profiles require runtime row closeout. It is not permission to replace missing L1 facts with L2/L3/L4 proxies.
