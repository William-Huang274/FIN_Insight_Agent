# 166 Market Snapshot Event Window And Query Contract

Date: 2026-05-25

## Problem

在 DuckDB-backed market snapshot 底座跑通后，下一步需要避免 market data 只停留在笼统 3M 表现。投研链路需要能围绕 8-K earnings release 和 latest 10-Q filing date 计算事件窗口表现，并且 Query Contract 必须先能表达 `market_snapshot` source tier、字段、窗口和工具选择。

## Decision

- 事件窗口收益由 deterministic analytics 计算，模型只解释结果。
- Event date 输入作为独立 CSV/JSON/JSONL artifact，不从模型记忆推断。
- Query Contract validator 先支持 market snapshot 外部 source tier；主 DAG planner prompt、Coverage Matrix、Judgment Plan、Synthesis、Gates、Renderer 仍按后续步骤接入。
- `market_snapshot` 不进入 SEC filing inventory coverage 检查，避免把外部市场数据误判为 SEC filing source gap。

## Work Completed

- 扩展 `src/sec_agent/market_snapshot.py`:
  - `compute_market_analytics(..., events_path=...)` 支持事件日期输入。
  - 支持每个 ticker 唯一 event type，例如 `8k_earnings_release`、`latest_10q_filing`。
  - 计算 `1d/3d/5d/10d` event-window returns。
  - 保留 `event_window_metadata`，包括 `event_type`, `event_date`, `anchor_date`, `source`。
  - 记录不可计算窗口到 `event_window_gaps`，例如事件后 bar 数不足。
  - validation 检查 event-window 数值字段不能是非数值。
- 扩展 `scripts/market/30_compute_market_analytics.py`:
  - 新增 `--events` 参数。
- 扩展 `src/sec_agent/query_contract.py`:
  - 新增 `market_snapshot` source tier 和 `SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT` source policy。
  - 支持 `market_snapshot.required/snapshot_id/as_of_date/window/fields/analysis_tools/provider/benchmark_ticker`。
  - `market_window` allowlist: `3M, 6M, YTD, 1Y`。
  - `market_fields` max 16，非法字段会被丢弃。
  - `market_analysis_tools` max 5，非法工具会被丢弃。
  - Market required caveats / forbidden claims 会自动加入 contract。
  - SEC filing coverage 只检查 SEC/8-K tiers，不把 `market_snapshot` 当作 SEC inventory tier。
- 扩展 `tests/test_market_snapshot_fixture.py`:
  - 覆盖 event-window returns。
  - 覆盖 Query Contract 对 `market_snapshot` 外部 source tier 的验证。

## Verification

Commands run:

```powershell
python -m py_compile src/sec_agent/market_snapshot.py src/sec_agent/query_contract.py scripts/market/30_compute_market_analytics.py
python -m pytest tests/test_market_snapshot_fixture.py tests/test_sec_agent_8k_earnings_source.py::test_query_contract_recognizes_mixed_with_8k_earnings_policy tests/test_sec_agent_10q_source_contract.py::test_query_contract_records_10q_inventory_gap_for_selected_ticker -q
python -m pytest tests -q
```

Result:

- Targeted query-contract/market tests: `5 passed`
- Full local suite: `91 passed`
- CLI event-window smoke:
  - synthetic 3-company + SPY fixture.
  - event rows for `8k_earnings_release` and `latest_10q_filing`.
  - validation returned `can_enter_market_snapshot_chain: true`, `error_count: 0`, `warning_count: 0`.

## Remaining Work

- Extend interactive planner prompt/normalizer so real planner output selects market snapshot only for market/valuation/reaction/divergence asks.
- Add `fundamental_market_divergence_view` after SEC/8-K driver outputs are available.
- Extend Evidence Coverage Matrix and Judgment Plan for market field coverage, event-window coverage, source gaps, and driver strength.
- Extend DeepSeek synthesis prompt, deterministic gates, renderer, and ContextManager artifact refs.
- Run 7-company local fixture smoke from 164 before any provider adapter.

## Safety Notes

- No real market data, credentials, or API calls were used.
- Event-window output is tool-derived, not provider-reported.
- Market snapshot still cannot overwrite SEC ledger values or support unstamped current/latest claims.
