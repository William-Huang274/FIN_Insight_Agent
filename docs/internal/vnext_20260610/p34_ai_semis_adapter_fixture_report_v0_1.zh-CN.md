# P34 AI/Semis Adapter Fixture Report v0.1

日期：2026-07-07

状态：`adapter_fixture_parser_contract_pass_live_fetch_pending`

## 1. 目的

本报告验证 P34-5 首批 adapter-family fixture 是否能把代表性输入解析成统一 runtime row。
它不是 live fetch / crawler / parser 全量验收，也不是 paid LLM、full-chain 或模型对比。

## 2. 指标

- adapter family：`3`
- fixture：`9`
- runtime rows：`9`
- rejected candidates：`9`
- typed gaps：`0`
- rows with parser lineage：`9`
- rows with authority scope：`9`

## 3. Adapter Family 结果

### sec_8k_earnings_release_table_adapter

- status：`pass`
- fixture_count：`3`
- runtime_row_count：`3`
- rejected_candidate_count：`3`
- typed_gap_count：`0`
- planned_in_source_route_plan：`True`

### official_product_spec_page_adapter

- status：`pass`
- fixture_count：`3`
- runtime_row_count：`3`
- rejected_candidate_count：`3`
- typed_gap_count：`0`
- planned_in_source_route_plan：`True`

### semicap_bookings_backlog_adapter

- status：`pass`
- fixture_count：`3`
- runtime_row_count：`3`
- rejected_candidate_count：`3`
- typed_gap_count：`0`
- planned_in_source_route_plan：`True`

## 4. 边界

- 本报告使用本地 artifact-backed fixture snippets，不做 live fetch。
- `source_url` 使用 `source-ledger://p34/...`，表示 parser contract fixture，不表示真实 URL snapshot。
- fixture rows 的 `promotion_status=fixture_parser_contract_pass_live_fetch_pending`，不能直接进入 live evidence bundle。
- 下一步必须把这些 adapter 接到真实 source route attempts，或记录 attempt-backed typed gap。
