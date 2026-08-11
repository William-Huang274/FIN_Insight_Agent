# 376 R14 Sequential Source-Role / Product-KPI Repair

Date: 2026-06-20

Scope: execute the five remaining repair tracks sequentially and only advance after each track passes deterministic gates. The repair tracks are careers site-specific adapters, channel locator adapters, PatentsView/assignee technology resolver, public-order/local tender adapters, and Product-KPI verifier improvements.

## Guardrail

Only parser-backed, issuer-bound exact rows can reduce a source-role gap. URL existence, blocked pages, blind search, issuer mismatch, geography-only rows, business-segment rows, and percentage/change cells remain rejected or closeout-only. Closeout rows are not evidence.

## Step 1: Careers Site-Specific Adapters

Problem: `hiring_capacity_proxy` still had 41 companies in the gap docket. Existing generic Greenhouse / Lever / Workday token generation missed verified official Workday tenants for several large issuers.

Work completed:

- Added verified direct Workday ATS URLs for `ADSK`, `CRM`, `MSI`, `OTIS`, and `TMUS` in `scripts/data_expansion/build_broad_official_careers_context_rows.py`.
- Added a generic Ashby public job-board parser, but did not bind `PWR -> quanta` because the live Ashby hit is a different Quanta issuer, not Quanta Services.
- Added tests for direct ATS URL precedence and Ashby JSON parsing into `hiring_capacity_proxy` exact slots.
- Ran live materialization for `ADSK/CRM/MSI/OTIS/TMUS`.

Result:

- `python -m pytest tests\test_broad_official_careers_context_rows.py -q` -> `3 passed`.
- `python -m py_compile scripts\data_expansion\build_broad_official_careers_context_rows.py tests\test_broad_official_careers_context_rows.py` -> pass.
- `python scripts\data_expansion\build_broad_official_careers_context_rows.py --tickers ADSK CRM MSI OTIS TMUS --workers 8 --max-career-pages 1 --max-jobs-per-company 2 --timeout-s 10 --strict` -> Workday rows materialized.
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`.
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`, `hiring_capacity_proxy=36`.
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`, `source_role_gap_docket_count=131`.

Metrics after Step 1:

- `exact_slot_gap_count=131`
- `all_required_exact_ready_company_count=488`
- `partial_exact_ready_company_count=115`
- `source_role_gap_docket_count=131`
- `product_kpi_gap_docket_count=377`
- `docket_count=508`
- `hiring_capacity_proxy.gap_count=36`

Important operational note: `build_exact_slot_gap_closeout_ledger.py` must run before `build_company_gap_docket.py`; running them in parallel can leave the docket on stale closeout input.

## Next

Step 2 is channel locator adapters. Pass condition: reduce `channel_offer_proxy` only with issuer/product/SKU-bound public offer or distributor/official-store rows that pass exact-slot gates; blocked locator pages and URL-only seeds remain gaps.

## Step 2: Channel Locator Adapters

Problem: after Step 1, `channel_offer_proxy` still had 12 company gaps. The remaining group mixed true site protection, stale company-domain discovery, missing non-US/brand domains, and parser windows that were too narrow for manual official locator/contact seeds.

Work completed:

- Added verified non-US / brand official seeds and domain overrides for `1211.HK` BYD, `LI` Li Auto, `ITW` / MillerWelds, and `CRDO` Credo.
- Added trusted distributor seeds for `DIOD` and `MPWR` through Arrow pages, requiring issuer binding in returned page content and channel/distributor context before promotion.
- Added official/manual locator seeds for `DOV`, `IEX`, `MRVL`, `PH`, and `WAB`, and widened manual verified page parsing so deep-body channel signals are not missed.
- Added optional `--browser-fallback` for manual verified channel seeds. It uses local Chrome/Edge through Playwright only when static HTML produces no row, and records `live_browser_fetch` in the attempt ledger.
- Tightened blocked/stale output handling so cached 404/access-denied pages are removed rather than promoted.
- Probed remaining retail locator sites with system Chrome. `AZO`, `CASY`, `DG`, `HD`, `GPC/NAPA`, `DECK/Hoka`, and `MNST` remained blocked by Akamai/DataDome/Cloudflare/access-denied responses in this environment; they were not promoted from URL existence or search snippets.

Result:

- `python -m pytest tests\test_family_channel_distributor_context_rows.py -q` -> `16 passed`.
- `python -m py_compile scripts\data_expansion\build_family_channel_distributor_context_rows.py tests\test_family_channel_distributor_context_rows.py` -> pass.
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --tickers DOV MRVL PH IEX WAB DIOD MPWR 1211.HK CRDO ITW LI ...` -> official / trusted channel rows materialized.
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --tickers CRDO LI --workers 1 --timeout-s 25 --max-seeds-per-ticker 3 --max-links-per-seed 6 --max-rows-per-ticker 2 --browser-fallback --strict` -> browser fallback materialized `CRDO` and `LI`.
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`.
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`, `channel_offer_proxy=8`.
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`, `source_role_gap_docket_count=120`.

Metrics after Step 2:

- `channel_offer_proxy.gap_count=8`, down from `19` at this continuation start and `12` after the earlier Step 2 partial run.
- `channel_offer_proxy.ready_count=54`.
- `exact_slot_gap_count=120`.
- `all_required_exact_ready_company_count=494`.
- `partial_exact_ready_company_count=109`.
- `source_role_gap_docket_count=120`.
- `product_kpi_gap_docket_count=377`.
- `docket_count=497`.

Remaining channel gaps:

- `AZO`, `CASY`, `DECK`, `DG`, `GPC`, `HD`, `MNST`, `NIO`.
- Current reason: official locator / store / channel routes have no parser-backed bound row in the local runtime. For `AZO/CASY/DG/HD/GPC/DECK/MNST`, browser probes still hit site protection or Cloudflare/Akamai/DataDome-style blocks. For `NIO`, the public location route returned non-standard `567`/rendering protection in the current environment. These cannot be promoted without a stable site-specific API/parser or accepted browser materialization path.

## Next

Step 3 is PatentsView / assignee technology resolver. Pass condition: reduce `technology_research_proxy` only with issuer/assignee/topic-bound public patent or research rows; broad OpenAlex or patent keyword hits without issuer binding remain gaps.

## Step 3: PatentsView / Assignee Technology Resolver

Problem: `technology_research_proxy` still had 17 company gaps. OpenAlex had already been attempted for these issuer/product-family routes, but several remaining companies needed an assignee/topic IP route rather than broad research search. The gate must not promote patent keyword hits unless issuer assignee and product/topic are both bound.

Work completed:

- Added `scripts/data_expansion/build_v1_patentsview_technology_research_context_rows.py` as a PatentSearch / PatentsView assignee-topic resolver.
- Added parser gates requiring assignee alias match plus product/topic match before any row becomes `technology_research_proxy_context`.
- Added no-key / API-unavailable attempt rows so PatentsView is auditable in closeout even when no runtime key is available.
- Wired PatentsView rows into `build_exact_slot_coverage_matrix.py` default observed rows.
- Wired PatentsView attempts into `build_exact_slot_gap_closeout_ledger.py` default attempts and split closeout reasons from OpenAlex-only gaps.
- Kept PatentsView rows L3 bounded context only: IP / technology activity proxy, not product launch, sales, revenue, market share, or durable moat evidence.

Result:

- `python -m py_compile scripts\data_expansion\build_v1_patentsview_technology_research_context_rows.py tests\test_v1_patentsview_technology_research_context_rows.py scripts\data_expansion\build_exact_slot_coverage_matrix.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py tests\test_exact_slot_gap_closeout_ledger.py` -> pass.
- `python -m pytest tests\test_v1_patentsview_technology_research_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py -q` -> `11 passed`.
- `python scripts\data_expansion\build_v1_patentsview_technology_research_context_rows.py --replace-output --strict` -> `attempt_count=17`, `context_row_count=0`, `attempt_status_counts.missing_patentsview_api_key=17`.
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`.
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`, `unclassified_closeout_count=0`, `technology_research_proxy=17`, closeout reason `patentsview_api_key_missing_or_patentsearch_unavailable=17`.
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`, `technology_research_patents_assignee_resolver=17`.

Metrics after Step 3:

- `technology_research_proxy.ready_count=61`.
- `technology_research_proxy.gap_count=17`.
- `exact_slot_gap_count=120`.
- `all_required_exact_ready_company_count=494`.
- `partial_exact_ready_company_count=109`.
- `source_role_gap_docket_count=120`.
- `product_kpi_gap_docket_count=377`.
- `docket_count=497`.

Current boundary:

- The PatentsView route is now implemented and attempt-backed, but no `PATENTSVIEW_API_KEY` / `USPTO_PATENTSVIEW_API_KEY` is available in the local runtime and no row can be promoted from URL existence.
- These 17 technology gaps are no longer silent OpenAlex-only gaps; they are explicit `patentsview_api_key_missing_or_patentsearch_unavailable` gaps until a key, USPTO ODP bulk route, or another issuer-assignee/topic-bound public IP route is available.

## Next

Step 4 is public-order / local tender adapters. Pass condition: reduce `public_order_proxy` only with recipient-bound award/tender/contract rows or jurisdiction-specific official tender rows; generic web results, non-recipient awards, and local tender routes without parser-backed rows remain gaps.

## Step 4: Public-Order / Local Tender Adapters

Problem: `public_order_proxy` had 36 company gaps. The remaining group mixed USAspending alias misses, non-US/FPI issuer ambiguity, and local HK/TW/JP tender routes that had never been attempt-backed with jurisdiction-specific sources.

Work completed:

- Repaired `build_broad_public_contract_award_context_rows.py` recipient alias handling. The prior alias de-dupe collapsed suffix-sensitive query strings, so `HONDA MOTOR CO LTD` and `Honda Motor` were treated as duplicates even though USAspending returns different results.
- Added verified recipient aliases for `ASML`, `CAMT`, `HMC`, `HUBS`, `PATH`, `PWR`, and `TM`; rows now record `matched_recipient_alias`.
- Added `STRICT_RECIPIENT_ALIAS_ONLY_TICKERS` for `TM` after audit showed broad `Toyota Motor` matched `OKINAWA TOYOTA MOTOR CO.LTD.`. Full USAspending manifest was rebuilt after this fix to remove stale false-positive rows.
- Added `build_local_public_tender_context_rows.py` for local public tender routes. HK uses the official `digitalpolicy.gov.hk` SOA-QPS awarded service contracts CSV parser; TW/JP write official-route attempts against PCC/JETRO when no supplier-bound award row is available.
- Wired local tender rows into exact-slot coverage and local tender attempts into closeout; docket now labels local HK/TW/JP attempts as attempt-backed public boundary instead of unrun adapter work.

Result:

- `python -m pytest tests\test_broad_public_contract_award_context_rows.py -q` -> `5 passed`.
- `python -m pytest tests\test_local_public_tender_context_rows.py tests\test_broad_public_contract_award_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py -q` -> `16 passed`.
- `python scripts\data_expansion\build_broad_public_contract_award_context_rows.py --replace-output --workers 12 --timeout-s 20 --limit 5 --strict` -> `success_ticker_count=133`, `row_count=652`.
- `python scripts\data_expansion\build_local_public_tender_context_rows.py --replace-output --strict` -> `target_ticker_count=7`, `attempt_count=7`, `row_count=0`; HK/TW/JP routes had no supplier-bound award row with amount/date/agency in current public route.
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`, `public_order_proxy.gap_count=25`.
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`, `unclassified_closeout_count=0`.
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`, `source_role_gap_docket_count=109`.

Metrics after Step 4:

- `public_order_proxy.ready_count=134`, `gap_count=25`.
- `exact_slot_gap_count=109`.
- `all_required_exact_ready_company_count=503`.
- `partial_exact_ready_company_count=100`.
- `source_role_gap_docket_count=109`.
- `product_kpi_gap_docket_count=377`.
- `docket_count=486`.

Newly repaired / validated public-order examples:

- `ASML -> ASML US LLC` Department of Commerce awards.
- `CAMT -> CAMTEK, INC.` Department of Defense awards.
- `HMC -> AMERICAN HONDA MOTOR CO., INC.` awards.
- `HUBS -> HUBSPOT, INC.` Department of Defense award.
- `PATH -> UIPATH INC` GSA / DoD awards.
- `PWR -> PAR ELECTRICAL CONTRACTORS, LLC` awards.
- `TM -> TOYOTA MOTOR CORPORATION` awards only after strict alias filtering.
- `2308.TW -> DELTA ELECTRONICS MANUFACTURING CORP` USAspending rows.

Remaining public-order gaps:

- `19` companies remain in `public_order_local_tender_and_recipient_adapter`, mostly USAspending no-recipient-bound or non-US/FPI/local jurisdiction ambiguity: `AEHR`, `AMKR`, `BILL`, `CCJ`, `CRDO`, `CSIQ`, `DNN`, `DQ`, `ENLT`, `ENPH`, `JKS`, `NXT`, `OKLO`, `PCAR`, `RUN`, `SEDG`, `SHOP`, `SMR`, `UROY`.
- `6` local HK/TW/JP companies are attempt-backed public boundaries: `1211.HK`, `2317.TW`, `2382.TW`, `3231.TW`, `6752.T`, `8035.T`.
- Current local tender boundary: portal existence and non-structured pages cannot fill `public_order_proxy`; exact row requires supplier-bound award id, amount, award date, agency, and official source URL.

## Next

Step 5 is Product-KPI verifier improvements. Pass condition: promote only company-disclosed product/category/product-line or industry-defined operating metric rows with value/unit/period/product/citation; business segment, region-only, percentage/change, mixed column group, and sentence-relation-insufficient rows must remain classified gaps.

## Step 5: Product-KPI Verifier Improvements

Problem: after Step 4, Product-KPI still had `377` docket gaps. The prior docket collapsed `272` strict-candidate tickers into one generic `product_kpi_source_specific_table_verifier` cluster even though the source-specific verifier had already classified the underlying `21,822` candidates. That made the remaining Product-KPI work look like one undifferentiated parser backlog.

Work completed:

- Wired `product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl` into `build_product_kpi_deep_gap_diagnostic.py`.
- Added per-company diagnostic fields for verifier candidate count, class counts, decision counts, top reasons, dominant verifier class, and dominant verifier reason.
- Split strict-candidate Product-KPI gaps into concrete classes:
  - `verifier_business_segment_only_candidates`
  - `verifier_business_segment_column_group_required`
  - `verifier_operating_metric_requires_industry_slot`
  - `verifier_percentage_or_change_only_candidates`
  - `verifier_period_or_version_conflict`
  - `verifier_region_or_geography_only_candidates`
  - `verifier_sentence_relation_insufficient`
  - `verifier_non_product_or_total_candidates`
- Updated `build_company_gap_docket.py` so these Product-KPI classes become separate adapter clusters instead of one giant backlog.
- Kept strict Product-KPI promotion unchanged: no business segment, geography, percentage/change, generic total, or unstructured sentence candidate can fill a Product-KPI exact slot.

Result:

- `product_kpi_source_specific_verifier` re-run: `target_ticker_count=272`, `candidate_count=21,822`, `unclassified_candidate_count=0`, `promotable_product_metric_count=0`.
- `product_kpi_deep_gap_diagnostic` re-run: `status=pass`, `unclassified_count=0`, `product_family_exact_ready_ticker_count=133`, `business_or_segment_exact_ready_ticker_count=83`, `product_or_business_kpi_ready_ticker_count=216`.
- Product-KPI gap classes after verifier decomposition:
  - `product_surface_or_taxonomy_available_no_company_kpi_candidate=101`
  - `verifier_business_segment_only_candidates=107`
  - `verifier_percentage_or_change_only_candidates=72`
  - `verifier_operating_metric_requires_industry_slot=32`
  - `verifier_business_segment_column_group_required=18`
  - `verifier_region_or_geography_only_candidates=15`
  - `verifier_non_product_or_total_candidates=12`
  - `verifier_sentence_relation_insufficient=9`
  - `verifier_period_or_version_conflict=7`
  - `non_us_local_or_ir_parser_required=4`
- `company_gap_docket` final re-run: `status=pass`, `docket_count=486`, `source_role_gap_docket_count=109`, `product_kpi_gap_docket_count=377`, `cluster_count=20`, `unclassified_docket_count=0`.

Interpretation:

- This step intentionally did not lower `product_kpi_gap_docket_count`; no remaining candidate passed the company-disclosed product/category/product-line value/unit/period/product/citation gate.
- The gain is auditability and execution routing: the `272` strict-candidate tickers are now split into business segment boundary, column-group parser, industry operating metric slot, percentage/change rejection, region exposure, sentence relation verifier, period/version reconciliation, and non-product/total rejection queues.
- `Product-KPI exact` remains a high-strength L1 slot. Business-segment metrics and typed operating metrics can support fundamental/business mix analysis, but they do not become product-family KPI proof.

Verification:

- `python -m py_compile scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py scripts\data_expansion\build_company_gap_docket.py tests\test_product_kpi_deep_gap_diagnostic.py tests\test_company_gap_docket.py` -> pass.
- `python -m pytest tests\test_product_kpi_deep_gap_diagnostic.py tests\test_company_gap_docket.py tests\test_product_kpi_source_specific_verifier.py -q` -> `9 passed`.
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`.
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`, `unclassified_closeout_count=0`.
- `python scripts\data_expansion\build_product_kpi_source_specific_verifier.py --strict` -> `status=pass`.
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> `status=pass`.
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`.

## Final State After Sequential Steps 1-5

- `exact_slot_gap_count=109`
- `all_required_exact_ready_company_count=503`
- `partial_exact_ready_company_count=100`
- `source_role_gap_docket_count=109`
- `product_kpi_gap_docket_count=377`
- `docket_count=486`
- `unclassified_closeout_count=0`
- `unclassified_docket_count=0`
