# 375 R14 Source-Role Exact-Slot Repair Continuation

Date: 2026-06-20

Scope: continue R14 source-role / Product-KPI exact-slot repair after the gap docket showed remaining source-role and Product-KPI gaps. The rule for this slice is unchanged: only parser-backed, issuer-bound rows enter runtime; URL existence, blocked pages, blind search, geography-only rows, business-segment rows, and percentage/change cells are not promoted as Product-KPI exact evidence.

## Implemented

- Added CDNS verified developer seed via Cadence / Fidelity Pointwise official GitHub routes and materialized parser-backed GitHub rows.
- Added HST app/platform alias for `Host Hotels & Resorts, Inc.` and materialized seller-bound iTunes rows.
- Added Greenhouse ATS token overrides for `BILL= billcom` and `ESTC=elastic`, producing official careers job rows.
- Added verified USAspending recipient aliases for `GE`, `J`, `LEU`, `FORM`, and `INTU`; rejected similar-name false positives for DOV / AEHR / AMKR / IOT.
- Probed remaining channel locator URLs with browser-like requests and kept them as gaps where official sites returned anti-bot / access-denied responses.
- Rechecked Product-KPI verifier buckets and kept strict boundary: no new promotable product/category/product-line KPI rows were found in the current candidate set.

## Latest Metrics

- `exact_slot_gap_count=136`
- `all_required_exact_ready_company_count=484`
- `partial_exact_ready_company_count=119`
- `source_role_gap_docket_count=136`
- `product_kpi_gap_docket_count=377`
- `docket_count=513`
- `unique_gap_company_count=412`
- `unclassified_closeout_count=0`
- `unclassified_docket_count=0`

Remaining source-role gaps:

| requirement | gap | reason |
| --- | ---: | --- |
| `hiring_capacity_proxy` | 41 | public ATS / official careers still require site-specific parsers or returned no issuer-bound job rows |
| `public_order_proxy` | 36 | 16 USAspending recipient-bound gaps and 20 non-US / local tender adapter gaps |
| `channel_offer_proxy` | 19 | official locator routes are blocked, unavailable, or need marketplace/SKU-specific adapters |
| `technology_research_proxy` | 17 | OpenAlex issuer-topic binding fails; PatentsView/assignee resolver still needed |
| `developer_ecosystem_proxy` | 13 | no verified official docs/repo/package seed; blind GitHub search remains forbidden |
| `app_rank_store_proxy` | 4 | no seller-bound app listing |
| `platform_review_proxy` | 4 | no seller-bound review/listing |
| `supply_chain_official_relationship` | 1 | AEHR lacks named official counterparty-bound public relationship row |
| `auto_product_identity_context` | 1 | XPEV has no NHTSA make/model exact row in current route |

## Verification

- `python -m pytest tests\test_broad_app_store_platform_context_rows.py -q` -> pass
- `python -m pytest tests\test_broad_official_careers_context_rows.py -q` -> pass
- `python -m pytest tests\test_broad_public_contract_award_context_rows.py -q` -> pass
- `python -m py_compile` on touched data-expansion scripts -> pass
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation pass
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> pass
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> pass

## Remaining Work

The next gains require real site-specific adapters, not more generic retries:

- Eightfold / company-specific careers API parser for MSFT-like pages.
- Browser-rendered or API-backed channel locator adapters for official-store / distributor sites that return anti-bot pages under plain HTTP.
- PatentsView or alternative official assignee resolver for technology research proxy.
- Local tender adapters for non-US public-order routes.
- Product-KPI table/layout recovery for source-specific annual report / IR deck tables; still do not promote geography, segment, percentage/change, or sentence-unverified rows.
