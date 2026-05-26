# 167 Market Snapshot Planner Contract

Date: 2026-05-25

## Problem

`market_snapshot` 已经有 DuckDB/parquet 底座、event-window analytics 和 Query Contract validator，但真实交互 planner 仍可能不知道什么时候该请求市场数据，也可能把市场源默认混进 SEC-only 问题。需要把 planner prompt 和 normalizer 的执行合同补齐。

## Decision

- Planner 只有在用户明确或隐含询问股价、估值、市场反应、相对收益、回撤、波动、是否 priced in / 是否已经反映时，才允许加入 `market_snapshot`。
- `market_snapshot` 是外部 source tier，不是 SEC filing inventory；它不能替代 SEC ledger，也不能默认污染 SEC/8-K 问题。
- 如果 planner 请求 market snapshot 但没有 seed 提供 `snapshot_id/as_of_date`，normalizer 保留空值，由 Query Contract validator 记录 market source gap；不能让模型猜。

## Work Completed

- 更新 `scripts/cloud/sec_agent_interactive.py` planner prompt:
  - schema 增加 `market_snapshot` object。
  - 说明 market source tier 的触发条件。
  - 限制 `market_snapshot.window` 为 `3M/6M/YTD/1Y`。
  - 限制 market fields/tools，并强调 snapshot_id/as_of_date 不能编造。
- 更新 planner normalizer / repair:
  - `_normalize_llm_query_contract` 可保留 planner 输出的 `market_snapshot`。
  - `_repair_query_contract_from_prompt` 可从用户 prompt 的市场/估值/反应意图补入 `market_snapshot`。
  - `source_policy` 在 source tiers 包含 `market_snapshot` 时变为 `SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT`。
  - 非 market 问题仍保持原 `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` 或 SEC-only contract。
  - output limits 会对 market fields/tools 继续做 allowlist/长度压缩。
- 更新测试:
  - planner prompt 必须包含 market snapshot 触发规则。
  - market-intent planner normalization 保留 source tier、fields/tools allowlist、source policy。
  - 既有 8-K planner normalization 不被 market source tier 污染。

## Verification

Commands run:

```powershell
python -m py_compile scripts/cloud/sec_agent_interactive.py src/sec_agent/query_contract.py
python -m pytest tests/test_sec_agent_8k_earnings_source.py::test_planner_prompt_uses_compact_json_contract tests/test_sec_agent_8k_earnings_source.py::test_planner_normalization_preserves_market_snapshot_contract tests/test_sec_agent_8k_earnings_source.py::test_llm_contract_normalization_preserves_8k_source_tier tests/test_market_snapshot_fixture.py::test_query_contract_accepts_market_snapshot_external_source_tier -q
python -m pytest tests -q
```

Result:

- Targeted planner/market/8-K tests: `4 passed`
- Full local suite: `92 passed`

## Remaining Work

- Wire market evidence pack into Evidence Coverage Matrix and Judgment Plan.
- Add `fundamental_market_divergence_view` once SEC/8-K drivers and market analytics are both available in the same run state.
- Extend synthesis prompt, deterministic gates, renderer, and ContextManager refs.
- Run 7-company local fixture smoke before any provider adapter.

## Safety Notes

- Planner changes do not fetch market data or call any market API.
- Planner cannot invent snapshot values; missing `snapshot_id/as_of_date` remains a source gap.
- Market source tier remains opt-in by user intent.
