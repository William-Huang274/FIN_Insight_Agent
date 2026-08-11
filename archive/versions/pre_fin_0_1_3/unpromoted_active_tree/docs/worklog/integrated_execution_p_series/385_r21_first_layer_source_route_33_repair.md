# R21 First-Layer Source Route 33 Repair

## Prompt

用户要求继续把 R20 后剩余的 `33` 条 first-layer source-route release blockers 修完；不能用 fallback 隐藏缺口，只有 parser-backed、issuer/counterparty/product-bound、source-role-bound 且 claim-boundary 明确的 rows 才能进入 evidence bundle。

## Decision

本轮目标不是把所有 Product-KPI / public-order exact slots 强行补齐，而是关闭 R18 vertical source-route release gate：

- `public_order_proxy` 可以被官方客户/供应/合同关系 rows 满足为 bounded demand / relationship context，但不能写成 public tender exact snapshot、order value、backlog、收入、销量、ASP、份额或完整 order book。
- `hiring_capacity_proxy` 只接受官方 careers / ATS 的 title、location、department、URL 等结构化 rows；careers landing page 不能提权。
- `channel_offer_proxy` 只接受官方/授权渠道、store locator、distributor、offer parser rows；不能从 URL 存在推断价格、库存、ASP、sell-through、销量或份额。
- `technology_research_proxy` 只接受 issuer/topic-bound 官方技术文档、OpenAlex/PatentsView 等结构化 rows；不能用泛关键词论文/专利搜索结果提权。

## Work Completed

- `public_order_proxy=19`
  - 对 `CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN` 补 targeted official supplier/customer relationship rows。
  - 修复 `public_order_proxy` source-route gate，使 `supplier_customer_official_news` 可以作为 bounded public-order/customer-relationship context 进入 release gate。
  - 保留 strict `public_tender_or_award` exact-slot contract，不把官方关系新闻伪装为 award exact row。
- `hiring_capacity_proxy=4`
  - `VZ`: 新增 browser-executed Next jobs API parser。
  - `MELI`: 使用 official Eightfold API route。
  - `FIX`: 使用 Workday direct ATS route。
  - `ROP`: 增加 Deltek / Findly official subsidiary careers parser，并新增 subsidiary-bound issuer binding status。
- `channel_offer_proxy=6`
  - 继续使用 family channel distributor parser，补 official / reader-proxy / browser fallback 处理。
  - 相关公司进入 channel offer / distributor / locator bounded context rows。
- `technology_research_proxy=4`
  - 新增 `build_targeted_official_technology_document_rows.py`。
  - 对 `PLTR`、`MPWR`、`300750.SZ`、`373220.KS` 物化 official technical / R&D document rows，并接入 source coverage / exact slot coverage / company coverage 默认输入。

## Result

- `r18_vertical_source_route_gate_v0_1`
  - `status=pass`
  - `company_count=603`
  - `pass_company_count=603`
  - `action_required_company_count=0`
  - `missing_requirement_count=0`
  - `requirement_count=2,688`
  - hard gate `flag_count=0`
- `r18_source_authority_data_mart_v0_1`
  - `status=pass`
  - `company_count=603`
  - `row_count=3,761`
  - `evidence_bundle_allowed_count=3,761`
  - `planning_or_gap_only_count=0`
  - `exact_company_fact_authority_count=865`
  - `thesis_driver_authority_count=2,896`
  - hard gate `flag_count=0`
- `r18_source_route_registry_v2`
  - `status=pass`
  - `registry_source_role_count=16`
  - `signal_matrix_row_count=3,761`
  - `evidence_bundle_allowed_count=3,761`
  - `planning_or_gap_only_count=0`
  - hard gate all zero.
- `exact_slot_coverage_matrix_v0_1`
  - validation `status=pass`
  - matrix `status=gap`
  - `all_required_exact_ready_company_count=578`
  - `partial_exact_ready_company_count=25`
  - `exact_slot_gap_count=25`
  - remaining exact gaps are `public_order_proxy` / `context_only_not_exact_slot`.

## Boundary

R21 closes the first-layer source-route release gate, not every fine-grained data need:

- Public-order official relationship rows can support bounded demand/customer/supply-chain context, but not exact award amount, order value, backlog, shipment volume, company revenue, ASP, sell-through, market share, or complete order book.
- Product-KPI exact still requires company-disclosed value/unit/period/product/citation rows.
- Product specs, competitor relationships, capital/funding/ownership, and leading-signal full-chain usage remain follow-up layers under the 23 document direction.

## Verification

- `python -m pytest tests/test_targeted_supply_chain_official_relationship_rows.py tests/test_family_channel_distributor_context_rows.py tests/test_broad_official_careers_context_rows.py tests/test_targeted_official_technology_document_rows.py tests/test_company_public_source_coverage_matrix.py tests/test_source_coverage_gate.py tests/test_r18_data_source_admission_ledger.py tests/test_source_route_registry_v2.py tests/test_r18_source_authority_data_mart.py tests/test_r18_vertical_source_route_gate.py tests/test_exact_slot_contracts.py -q` -> `88 passed`
- `python -m py_compile scripts/data_expansion/build_targeted_supply_chain_official_relationship_rows.py scripts/data_expansion/build_family_channel_distributor_context_rows.py scripts/data_expansion/build_broad_official_careers_context_rows.py scripts/data_expansion/build_targeted_official_technology_document_rows.py scripts/data_expansion/build_company_public_source_coverage_matrix.py scripts/data_expansion/build_exact_slot_coverage_matrix.py scripts/data_expansion/build_r18_data_source_admission_ledger.py scripts/data_expansion/build_r18_source_route_registry_v2.py scripts/data_expansion/build_r18_source_authority_data_mart.py scripts/data_expansion/build_r18_vertical_source_route_gate.py src/sec_agent/exact_slot_contracts.py src/sec_agent/source_coverage_gate.py src/sec_agent/company_public_source_coverage_matrix.py`

## Safety Notes

- No secrets were written to docs.
- No commit was created.
- URL/snippet/search/landing/challenge/attempt-only rows remain excluded from evidence bundle.
