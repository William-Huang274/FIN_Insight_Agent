# R20 First-Layer Source Route Closeout

## Prompt

用户要求继续补“第一层”：把 600+ 公司公开可得数据源中能真实进入 evidence bundle 的 source-role rows 继续补齐；不能用 fallback 隐藏缺口，只有 parser-backed、issuer-bound、claim-boundary 明确的 runtime rows 才能通过。

## Decision

本轮沿用 R18/R19 的硬门控：

- URL、snippet、search result、seed、landing page、attempt-only row 不进入 ClaimCard / Memo。
- L2/L3 proxy row 可以做 bounded thesis driver，但不能写成 revenue、ASP、share、sales、sell-through、backlog、order value。
- release 阻断口径读 `r18_vertical_source_route_gate_summary_v0_1` 和公司行 `missing_source_roles`，不是把更宽的 planning gap 误当 runtime evidence。
- 公开源理论可得但 parser/source route 没吃到，继续标记为 action-required；只有经 live probe 后仍没有稳定 issuer-bound row 的才写入 boundary。

## Work Completed

- `hiring_capacity_proxy`
  - 新增 IBM official careers search API adapter。
  - IBM careers 页面内 search bundle 使用 `https://www-api.ibm.com/search/api/v2`；adapter 只接受该 API 返回的 title / location / department / URL 等结构化 job rows。
  - 真实 materialization 后 `IBM` 通过 `ibm_search_api` 进入 `broad_official_careers_context_rows_v0_1`，只作为 hiring capacity / role-mix proxy。
- 重建 canonical artifacts：
  - `company_public_source_coverage_matrix_v0_1`
  - `exact_slot_coverage_matrix_v0_1`
  - `r18_data_source_admission_ledger_v0_1`
  - `r18_source_route_registry_v2`
  - `r18_source_authority_data_mart_v0_1`
  - `r18_vertical_source_route_gate_v0_1`
- 对剩余 action-required buckets 做 live probe，不做弱提权：
  - `VZ/MELI/FIX/ROP` careers：VZ/MELI 官方 careers surface 存在但未暴露稳定公开 job rows；FIX jobs 域名/官方 careers 不能给 issuer-bound title/location rows；ROP 需要 operating-company/subsidiary-to-issuer resolver。
  - `PLTR/300750.SZ/373220.KS/MPWR` technology research：OpenAlex 未返回稳定 issuer-topic-bound rows；PatentsView route 仍缺 credential / assignee resolver。
  - `CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN` public order：USAspending 未返回 recipient-bound award rows；需要 jurisdiction-specific tender 或 official customer/contract relationship parser。
  - `GPC/AZO/CASY/DG/HD/MNST` channel：官方 store / locator / ecommerce 页面仍需 site-specific API/browser parser；Monster Beverage 未发现 verified official channel locator。

## Result

- `r18_source_authority_data_mart_v0_1`
  - `status=pass`
  - `company_count=603`
  - `row_count=3,729`
  - `evidence_bundle_allowed_count=3,674`
  - `planning_or_gap_only_count=55`
  - hard gate `flag_count=0`
- `exact_slot_coverage_matrix_v0_1`
  - validation `status=pass`
  - `all_required_exact_ready_company_count=564`
  - `partial_exact_ready_company_count=39`
  - `exact_slot_gap_count=39`
  - remaining role gaps: `public_order_proxy=25` in exact-slot matrix, `channel_offer_proxy=6`, `hiring_capacity_proxy=4`, `technology_research_proxy=4`
- `r18_vertical_source_route_gate_v0_1`
  - `status=action_required`
  - `pass_company_count=570`
  - `action_required_company_count=33`
  - `missing_requirement_count=33`
  - hard gate `flag_count=0`

## Remaining Action-Required Boundary

- `public_order_proxy=19`: `CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN`
  - Boundary: USAspending / current local tender routes did not yield recipient-bound award/order rows. Need jurisdiction-specific tender parser, customer-contract route, or issuer/customer official relationship parser.
- `channel_offer_proxy=6`: `GPC/AZO/CASY/DG/HD/MNST`
  - Boundary: current official locator/ecommerce routes are blocked, dynamic, site-specific, or not verified. Need NAPA/HomeDepot/AutoZone/DollarGeneral/Casey's site parser and Monster official-channel resolution.
- `hiring_capacity_proxy=4`: `ROP/VZ/FIX/MELI`
  - Boundary: careers surface exists for some, but no stable issuer-bound title/location rows from current routes. ROP/FIX need operating-company/subsidiary binding before promotion.
- `technology_research_proxy=4`: `PLTR/300750.SZ/373220.KS/MPWR`
  - Boundary: OpenAlex did not produce issuer-topic-bound rows; PatentsView / USPTO route still needs credential and assignee resolver.

## Verification

- `python -m py_compile scripts\data_expansion\build_broad_official_careers_context_rows.py scripts\data_expansion\build_family_channel_distributor_context_rows.py src\sec_agent\company_public_source_coverage_matrix.py`
- `python -m pytest tests\test_broad_official_careers_context_rows.py tests\test_family_channel_distributor_context_rows.py tests\test_company_public_source_coverage_matrix.py tests\test_exact_slot_contracts.py tests\test_r18_data_source_admission_ledger.py tests\test_r18_source_authority_data_mart.py tests\test_r18_vertical_source_route_gate.py -q` -> `67 passed`

## Safety Notes

- No secrets were written to docs.
- No commit was created.
- R20 fixes one real release blocker (`IBM`) and exposes the remaining `33` as source-role-specific work, not as hidden fallback or memo evidence.
