# P33 Gold-set Live Source Backfill v0.1

日期：2026-07-07

## 1. 结论

本轮没有跑 paid LLM、full-chain、新爬虫或新 parser，而是把 gold-set matrix 的 68 条 row 回填到现有已物化 source/runtime manifests，检查哪些已经有 parser-backed runtime row。

当前状态为 `partial_live_backfill_pass_remaining_route_parser_work`。这表示一部分 slot 已能绑定到现有 runtime row，但仍有 row 需要 issuer 绑定、source route/parser 深挖，或保持 failure fixture。

## 2. Backfill Metrics

- `case_count`: `15`
- `row_count`: `68`
- `live_runtime_ready_row_count`: `4`
- `route_candidate_only_parser_lineage_pending_count`: `1`
- `source_route_candidate_weak_not_bound_count`: `13`
- `source_route_not_bound_required_count`: `0`
- `case_binding_required_count`: `44`
- `failure_fixture_count`: `6`
- `remaining_action_required_row_count`: `58`
- `indexed_row_count`: `154484`
- `indexed_ticker_count`: `603`

## 3. Source Index

- `rowset_count`: `8`
- `indexed_row_count`: `154484`
- `indexed_ticker_count`: `603`
- `missing_rowsets`: `0`

## 4. Case Summary

| Case | Type | Status | Rows | Live ready | Action required | Source rowsets |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `ai_semis_dell_nvda_anchor_v0_1` | `deep_gold_case` | `live_backfill_partial_or_pending` | 20 | 4 | 16 | data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl, data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl, data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl |
| `auto_ev_industrial_cycle_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 6 | 0 | 6 | - |
| `capital_market_feedback_price_in_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 5 | 0 | 5 | - |
| `cloud_saas_ai_monetization_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 5 | 0 | 5 | - |
| `energy_utilities_power_demand_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 5 | 0 | 5 | - |
| `financials_rate_credit_capital_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 6 | 0 | 6 | - |
| `healthcare_regulated_product_adoption_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 5 | 0 | 5 | - |
| `negative_available_evidence_not_used_v0_1` | `negative_gold_case` | `failure_fixture_only` | 1 | 0 | 0 | - |
| `negative_commercial_tracker_boundary_v0_1` | `negative_gold_case` | `failure_fixture_only` | 1 | 0 | 0 | - |
| `negative_demand_pool_not_supplier_allocation_v0_1` | `negative_gold_case` | `failure_fixture_only` | 1 | 0 | 0 | - |
| `negative_parser_gap_not_public_source_absent_v0_1` | `negative_gold_case` | `failure_fixture_only` | 1 | 0 | 0 | - |
| `negative_relationship_graph_not_financial_fact_v0_1` | `negative_gold_case` | `failure_fixture_only` | 1 | 0 | 0 | - |
| `negative_sku_revenue_missing_not_product_failure_v0_1` | `negative_gold_case` | `failure_fixture_only` | 1 | 0 | 0 | - |
| `retail_consumer_traffic_margin_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 5 | 0 | 5 | - |
| `semicap_cycle_rubric_v0_1` | `rubric_gold_case` | `live_backfill_partial_or_pending` | 5 | 0 | 5 | - |

## 5. 关键解释

- `live_runtime_ready`：同 issuer、角色/产品/metric 语义匹配，且已有 source/parser/runtime lineage。
- `source_route_candidate_weak_not_bound`：有候选但不足以安全绑定，不能提权。
- `source_route_not_bound_required`：当前 manifests 找不到足够候选，下一步需要 locator/parser 或 typed gap attempt。
- `case_binding_required_before_live_lookup`：rubric / basket slot 还没绑定到具体 issuer，不能直接查 live row。
- `not_applicable_failure_fixture`：negative case 只用于失败检测，不进 evidence bundle。

## 6. 下一步

Repair remaining rows by priority: issuer-bound AI/Semis source-route/parser first, then rubric case vertical-specific source routes, and keep negative fixtures out of evidence bundles.

## 7. Artifact refs

- `json_out`: `docs/project_os/p33_goldset_live_source_backfill_v0_1.json`
- `md_out`: `docs/internal/vnext_20260610/p33_goldset_live_source_backfill_v0_1.zh-CN.md`
