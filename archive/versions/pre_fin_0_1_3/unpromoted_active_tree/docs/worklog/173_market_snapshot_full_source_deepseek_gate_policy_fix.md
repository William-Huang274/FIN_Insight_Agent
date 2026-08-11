# 173 - Market Snapshot Full-Source DeepSeek Gate Policy Fix

Date: 2026-05-26

## Goal

修复 full30 + 10-K + 10-Q + 8-K + market snapshot 链路中两个合同噪音：

1. `entity_bleed_between_peers` gate 把 full30 宽范围横向扫描误判为必须逐一提到全部 focus companies。
2. Coverage Matrix 在非市场任务上错误标记 `market_snapshot` source tier 缺失，虽然全局 market snapshot coverage 已完整。

这两个问题都按合同修复，不加业务兜底。

## Root Cause

### Semantic Gate

旧逻辑中，只要 planner 识别到 peer/comparison 且用户问题包含“比较/compare”，`_semantic_gate_policy_for_prompt()` 就会设置：

- `company_coverage=all_focus`
- `require_company_coverage=true`

当 `focus_tickers` 是 full30 时，模型只选择证据最强的公司作比较也会被判为 `peer_case_missing_company_mention`。这不是实体串台，而是 gate 把“宽范围扫描”错当成“逐家公司覆盖”。

### Coverage Matrix

`source_tiers` 是 Query Contract 全局 scope。加入 `market_snapshot` 后，非市场基本面任务也用全局 `source_tiers` 计算 `missing_source_tiers`，导致 SEC-only task 出现：

- `Missing requested source-tier coverage: market_snapshot.`

但 market coverage summary 同时又显示 `market_snapshot_support_complete=true`。这会给 synthesis 错误缺口信号。

## Code Changes

- `scripts/cloud/sec_agent_interactive.py`
  - 对宽范围 peer/comparison task 调整 semantic gate：
    - 明确 `全部/所有/每家/逐一` 仍要求全覆盖。
    - 少量 focus tickers（`<=8`）的直接 peer compare 仍要求 `all_focus`。
    - full30 宽扫描默认 `selected_companies`，保留 support ticker 串台检查，但不要求逐一枚举全部 30 家。

- `src/sec_agent/coverage_matrix.py`
  - `missing_source_tiers` 按 task intent 计算。
  - 非市场任务不再要求 `market_snapshot`。
  - 市场/估值/市场反应任务仍要求 market fields/tools，并继续走 `market_snapshot_coverage`。

- Tests:
  - `tests/test_sec_agent_10q_source_contract.py`
    - full30 peer scan 不再因未提全部公司失败。
    - 小范围 peer compare 仍保持严格 `all_focus`。
  - `tests/test_market_snapshot_fixture.py`
    - 非市场 SEC task 不再错误标记 `market_snapshot` 缺口。
    - market snapshot 字段/工具覆盖测试保留。

## Validation

Local:

```powershell
python -m pytest tests/test_market_snapshot_fixture.py -q
python -m pytest tests/test_sec_agent_10q_source_contract.py -q
python -m py_compile src/sec_agent/coverage_matrix.py scripts/cloud/sec_agent_interactive.py src/sec_agent/market_snapshot.py scripts/market/09_download_fmp_historical_snapshot.py
```

Result:

- `tests/test_market_snapshot_fixture.py`: `16 passed`
- `tests/test_sec_agent_10q_source_contract.py`: `39 passed`
- `py_compile`: passed

Cloud targeted tests:

- `tests/test_market_snapshot_fixture.py` plus semantic-gate focused tests: `18 passed`

## Final Cloud Full-Source Run

Run:

- Path: `eval/sec_cases/outputs/full_source_deepseek_yahoo_fmp_latest_coverage_fix_benchmark/20260526_024807_3fbff2951a`
- Model: DeepSeek `deepseek-v4-pro`
- Sources:
  - 2025/2026 mixed SEC 10-K + latest 10-Q
  - full30 2026/2027 SEC 8-K earnings release / Exhibit 99.1
  - offline market snapshot `20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1`
- Market as-of date: `2026-05-22`
- API keys: supplied only through environment variables; not written to files.

Key results:

- Planner: `llm:deepseek:ok`
- Answer status: `answered_api_model`
- Runtime ledger rows: `48`
- Context rows: `150`
- Market context rows: `30`
- End-to-end elapsed: `248.9719 sec`
- DeepSeek synthesizer latency: `56993 ms`
- Tokens: `75426 input / 2662 output / 78088 total`

Coverage:

- `coverage_complete=true`
- `primary_task_support_complete=true`
- `market_snapshot_support_complete=true`
- `missing_source_tiers=[]`
- Market fields covered include:
  - `return_3m`
  - `relative_return_vs_benchmark_3m`
  - `max_drawdown_3m`
  - `volatility_3m`
  - `market_cap`
  - `pe_ttm`
  - `ev_sales_ttm`
  - `ev_ebitda_ttm`
  - `latest_10q_filing_return_1d/3d/5d/10d`
  - `8k_earnings_release_return_1d/3d/5d/10d`

Post-gates:

- `answer_ledger_gate_pass=true`
- `metric_role_term_gate_pass=true`
- `table_cell_gate_pass=true`
- `named_fact_gate_pass=true`
- `ledger_missing_consistency_gate_pass=true`
- `abstract_judgment_gate_pass=true`
- `caveat_claim_gate_pass=true`
- `v2_semantic_contract_gate_pass=true`
- `answer_vs_judgment_plan_gate_pass=true`
- `metric_source_grounding_gate_pass=true`
- `ledger_unit_gate_pass=true`
- `qwen_answer_gate_pass=true`

Semantic gate contract in the final case:

```json
{
  "company_coverage": "selected_companies",
  "require_company_coverage": false
}
```

The gate still ran `entity_bleed_between_peers`, but treated missing full30 company mentions as a warning, not a failure. This preserves entity/support separation while avoiding an exhaustive-coverage requirement for broad scans.

## Observed Output Quality

The answer is now a useful full-source investment memo slice:

- It explicitly compares SEC fundamentals, 8-K management explanation, and market snapshot reaction.
- It marks market data as non-real-time and stamped `as_of=2026-05-22`.
- It marks FMP valuation gaps instead of pretending valuation is complete.
- It separates 8-K unaudited management commentary from 10-K/10-Q filed evidence.
- It limits claims when evidence is incomplete, for example CVX/XOM peer comparison.

Current limitation:

- The model still chooses a focused subset of companies for the actual memo, even though market snapshot covers all 30. This is acceptable for `selected_companies` broad scan behavior, but not for a user request that explicitly asks “逐一覆盖30家公司”.
- Summary still reports `missing_filing_types=["10-K"]` from task-level filing coverage. It did not cause a gate failure, but should be reviewed later with the same task-intent principle used for `market_snapshot`.

## Next Step

Proceed to improve full30 source/task planning quality rather than gate plumbing:

1. Teach planner to distinguish `broad_scan_select_winners_losers` from `exhaustive_company_table`.
2. Add an explicit renderer mode for broad scans:
   - “covered universe”
   - “companies selected for memo”
   - “companies not discussed due to weaker retrieved support”
3. Review task-level `missing_filing_types` so annual/quarterly/8-K requirements are tied to period role and task intent, not always copied from global source scope.
