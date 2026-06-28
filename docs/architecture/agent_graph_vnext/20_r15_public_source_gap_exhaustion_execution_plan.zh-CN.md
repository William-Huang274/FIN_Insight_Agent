# R15 Public Source Gap Exhaustion Execution Plan

## 目标

R15 的目标不是把所有公司所有 source role 都强行补齐，而是把每条 L1/L2/L3 缺口推进到可审计终态：

- `runtime_ready`: 已生成 parser-backed runtime row，并被 exact-slot matrix 接受。
- `final_public_boundary`: 已尝试所有适用公开/免费 source ladder，仍没有可提权 exact row；必须有 attempt ledger。
- `not_applicable`: requirement 对公司/产品族不适用，且有规则或 attempt-backed 说明。
- `rerouted`: 原 Product-KPI gap 不应进入 Product-KPI exact，已改入 business segment、industry operating metric、geography exposure、directionality 等正确槽位。

禁止把 URL existence、blocked page、搜索摘要、issuer mismatch、business segment、region-only、percentage/change 或 closeout row 作为 evidence 提权。

## 输入基线

当前冻结输入：

- `data/manifests/company_gap_docket_v0_1.jsonl`
- `data/manifests/exact_slot_gap_ledger_v0_1.jsonl`
- `data/manifests/product_kpi_deep_gap_diagnostic_v0_1.jsonl`
- `data/manifests/product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl`

基线数字：

- `source_role_gap_docket_count=109`
- `product_kpi_gap_docket_count=377`
- `docket_count=486`
- `cluster_count=20`
- `unclassified_docket_count=0`

## 阶段

### R15-1 Source-Role 补齐 / 公开源边界

范围：

- `technology_research_proxy=17`
- `developer_ecosystem_proxy=13`
- `public_order_proxy=25`
- `hiring_capacity_proxy=36`
- `channel_offer_proxy=8`
- `app_rank_store_proxy=4`
- `platform_review_proxy=4`
- `supply_chain_official_relationship=1`
- `auto_product_identity_context=1`

通过条件：

- 每条 source-role gap 至少满足 `runtime_ready`、`final_public_boundary` 或 `not_applicable`。
- `build_exact_slot_coverage_matrix.py` validation pass。
- `build_exact_slot_gap_closeout_ledger.py --strict` pass。
- `build_company_gap_docket.py --strict` pass。
- R15 audit ledger 中 source-role `open_gap_without_attempt_count=0`。

### R15-2 Product-KPI 可修 exact 补齐

范围：

- `product_kpi_non_us_ir_local_exchange_parser=4`
- `product_kpi_column_group_schema_verifier=18`
- `product_kpi_period_version_schema_verifier=7`
- `product_kpi_sentence_relation_verifier=9`
- `product_kpi_ir_deck_annual_report_locator=101`

通过条件：

- 只允许 value / unit / period / product / citation 全齐的 company-disclosed row 提权。
- 其他项必须有 source ladder attempt-backed closeout。
- Product-KPI diagnostic `unclassified_count=0`。

### R15-3 Product-KPI 改槽位 / 不可提权归因

范围：

- `product_kpi_business_segment_boundary=107`
- `product_kpi_industry_operating_metric_slot_router=32`
- `product_kpi_percentage_change_rejection_gate=72`
- `product_kpi_region_dimension_or_rejection_gate=15`
- `product_kpi_non_product_total_rejection_gate=12`

通过条件：

- business segment 进入 business mix / fundamental segment slot。
- operating metric 进入 industry operating metric slot。
- percentage/change 进入 directionality slot，不能填 exact revenue。
- geography 进入 geographic exposure slot。
- generic total/non-product 保持 rejection 或另找 product table。

### R15-4 长尾逐公司 Closeout

范围：

- R15-1 到 R15-3 后仍未达终态的公司。

通过条件：

- 每条剩余 gap 有 `final_gap_reason`：
  - `company_undisclosed`
  - `public_free_source_unavailable`
  - `blocked_or_paywalled_public_route`
  - `commercial_tracker_required`
  - `not_applicable`
  - `parser_scope_remaining_with_attempts`
- 不能出现 “not found” 这种无 source ladder / attempt 的泛化原因。

### R15-5 回灌 Runtime 与最终验收

范围：

- runtime rows
- exact-slot matrix
- closeout ledger
- company gap docket
- Product-KPI diagnostic
- Research Lead / specialist 可见 source capability view

通过条件：

- `R15_repair_attempt_ledger` pass。
- `exact_slot_coverage_matrix` validation pass。
- `closeout --strict` pass。
- `company_gap_docket --strict` pass。
- `product_kpi_deep_gap_diagnostic --strict` pass。
- `git diff --check` pass。

## 输出

- `data/manifests/r15_public_source_gap_exhaustion_ledger_v0_1.jsonl`
- `data/manifests/r15_public_source_gap_exhaustion_summary_v0_1.json`
- `docs/internal/vnext_20260610/vertical_lanes/r15_public_source_gap_exhaustion.zh-CN.md`
- `docs/worklog/integrated_execution_p_series/377_r15_public_source_gap_exhaustion.md`

## 2026-06-21 执行结果

R15 已按 R15-1 到 R15-5 顺序完成并验收。

### Runtime / Matrix

- `exact_slot_coverage_matrix` validation pass，`exact_slot_row_count=35,247`，`exact_slot_gap_count=108`。
- `primary_company_disclosure=603/603`，非美 L1 disclosure runtime 保持 `company_ir_reports=87` exact rows。
- `official_product_surface.ready_count=559`，`official_product_surface.gap_count=0`。
- source-role gaps 全部有 runtime row、attempt-backed `final_public_boundary` 或 `not_applicable`，R15 不再有 pending。

### Source-Role Closeout

- `source_role_row_count=108`。
- R15 terminal attempts:
  - `public_order_proxy=8`：jurisdiction public tender / contract portal checked 后无 supplier-bound structured award row。
  - `technology_research_proxy=17`：OpenAlex 无 issuer-topic row，PatentsView 需要当前 runtime 未配置的 API key；禁止 URL-only / keyword-only patent rows 提权。
- closeout strict pass，`unclassified_closeout_count=0`。

### Product-KPI Closeout

- `product_kpi_row_count=377`。
- Product-KPI verifier strict pass：`target_ticker_count=272`，`candidate_count=21,822`，`unclassified_candidate_count=0`，`promotable_product_metric_count=0`。
- Product-KPI diagnostic strict pass：`unclassified_count=0`。
- Product-KPI coverage:
  - `ready_product_kpi_exact=133`
  - `ready_business_segment_metric_only=83`
  - `geographic_or_non_product_only=10`
  - `product_kpi_exact_gap=377`
- R15-2 terminal attempts:
  - `product_kpi_ir_deck_annual_report_locator=101`
  - `product_kpi_column_group_schema_verifier=18`
  - `product_kpi_sentence_relation_verifier=9`
  - `product_kpi_period_version_schema_verifier=7`
  - `product_kpi_non_us_ir_local_exchange_parser=4`
- R15-3 reroutes:
  - `product_kpi_business_segment_boundary=107`
  - `product_kpi_industry_operating_metric_slot_router=32`
  - `product_kpi_percentage_change_rejection_gate=72`
  - `product_kpi_region_dimension_or_rejection_gate=15`
  - `product_kpi_non_product_total_rejection_gate=12`

### Final R15 Ledger

- `row_count=485`
- `source_role_row_count=108`
- `product_kpi_row_count=377`
- `pending_gap_count=0`
- `open_gap_count=0`
- terminal states:
  - `final_public_boundary=246`
  - `not_applicable=1`
  - `rerouted=238`

### Boundary

R15 的完成含义是“所有当前 company-gap docket rows 已有 runtime row、attempt-backed public boundary、not-applicable 或 reroute 终态”。这不等于所有公司都有产品级销量 / ASP / sell-through / market share / backlog / channel inventory exact 数据。对未披露或免费公开源无法精确支持的项，继续暴露 gap 或 commercial tracker requirement，不能用 L3 proxy、URL existence、blocked page、search snippet、business segment、region-only、percentage/change 或 closeout row 代替 Product-KPI exact evidence。
