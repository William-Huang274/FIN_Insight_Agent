# P33 Gold-set Source Runtime Assimilation Matrix v0.1

日期：2026-07-07

## 1. 结论

本矩阵把 15 个 Humanmade Gold Set packs 逐条映射为：case -> required evidence slot -> registered source role -> crawler/parser 状态 -> runtime row 状态 -> authority boundary。

结果不是 live source 全通过，而是 `partial_artifact_scope_pass_live_runtime_pending`：矩阵完整，但大多数 rubric case 仍是 gold exemplar / required slot，不能被当作真实 source row。

## 2. 指标

- `case_count`: `15`
- `row_count`: `68`
- `live_runtime_ready_row_count`: `0`
- `source_route_unverified_runtime_artifact_row_count`: `20`
- `artifact_only_live_runtime_pending_row_count`: `42`
- `failure_fixture_row_count`: `6`
- `unknown_source_status_row_count`: `0`
- `live_runtime_pending_case_count`: `9`
- `registered_source_role_count`: `43`

## 3. Case Summary

| Case | Type | Status | Rows | Live ready | Runtime artifact/source-route unverified | Artifact-only pending | Failure fixture | Next action |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `ai_semis_dell_nvda_anchor_v0_1` | `deep_gold_case` | `live_runtime_pending` | 20 | 0 | 20 | 0 | 0 | Prove human-ledger rows through actual source routes/parser lineage before claiming source sufficiency. |
| `semicap_cycle_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 5 | 0 | 0 | 5 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `cloud_saas_ai_monetization_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 5 | 0 | 0 | 5 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `financials_rate_credit_capital_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 6 | 0 | 0 | 6 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `healthcare_regulated_product_adoption_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 5 | 0 | 0 | 5 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `energy_utilities_power_demand_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 5 | 0 | 0 | 5 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `retail_consumer_traffic_margin_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 5 | 0 | 0 | 5 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `auto_ev_industrial_cycle_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 6 | 0 | 0 | 6 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `capital_market_feedback_price_in_rubric_v0_1` | `rubric_gold_case` | `live_runtime_pending` | 5 | 0 | 0 | 5 | 0 | Implement vertical-specific route/parser rows for each required evidence slot before runtime promotion. |
| `negative_sku_revenue_missing_not_product_failure_v0_1` | `negative_gold_case` | `failure_fixture_only_not_source_evidence` | 1 | 0 | 0 | 0 | 1 | Wire negative fixtures into failure gates; do not route them through evidence ingestion. |
| `negative_demand_pool_not_supplier_allocation_v0_1` | `negative_gold_case` | `failure_fixture_only_not_source_evidence` | 1 | 0 | 0 | 0 | 1 | Wire negative fixtures into failure gates; do not route them through evidence ingestion. |
| `negative_relationship_graph_not_financial_fact_v0_1` | `negative_gold_case` | `failure_fixture_only_not_source_evidence` | 1 | 0 | 0 | 0 | 1 | Wire negative fixtures into failure gates; do not route them through evidence ingestion. |
| `negative_parser_gap_not_public_source_absent_v0_1` | `negative_gold_case` | `failure_fixture_only_not_source_evidence` | 1 | 0 | 0 | 0 | 1 | Wire negative fixtures into failure gates; do not route them through evidence ingestion. |
| `negative_available_evidence_not_used_v0_1` | `negative_gold_case` | `failure_fixture_only_not_source_evidence` | 1 | 0 | 0 | 0 | 1 | Wire negative fixtures into failure gates; do not route them through evidence ingestion. |
| `negative_commercial_tracker_boundary_v0_1` | `negative_gold_case` | `failure_fixture_only_not_source_evidence` | 1 | 0 | 0 | 0 | 1 | Wire negative fixtures into failure gates; do not route them through evidence ingestion. |

## 4. 关键边界

- AI/Semis deep case 的 20 条 rows 是 gold-depth runtime artifact rows，但还没有逐条证明 live source route / crawler / parser lineage。
- 8 个 rubric cases 的 rows 是 required evidence slots，不是 live retrieval 或 parser-backed facts。
- 6 个 negative cases 是 failure fixtures，只能进入 aggregate / writer / verifier / Workbench 的失败检测，不能进入 evidence bundle。
- 本轮未运行 paid LLM、full-chain、新检索、爬虫或 parser。

## 5. 下一步

按 case 和 required slot 补真实 source route / parser：先从 AI/Semis deep case 的 source-route lineage 验证开始，再按 rubric case 分行业补 live rows；没有可得公开源时必须记录 attempt-backed typed gap。

## 6. Artifact refs

- `json_out`: `docs/project_os/p33_goldset_source_runtime_assimilation_matrix_v0_1.json`
- `md_out`: `docs/internal/vnext_20260610/p33_goldset_source_runtime_assimilation_matrix_v0_1.zh-CN.md`
