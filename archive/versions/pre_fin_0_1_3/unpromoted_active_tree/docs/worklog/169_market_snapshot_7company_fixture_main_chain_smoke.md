# 169 Market Snapshot 7-Company Fixture Main-Chain Smoke

Date: 2026-05-25

## Problem

`market_snapshot` 已接入交互主链路，但 168 只完成了 stage/unit/CLI smoke。本阶段需要按 164 的要求生成 7-company 本地 market fixture，并验证 market evidence 是否能穿过主链路进入 retrieval 后 context、runtime ledger、Evidence Coverage Matrix 和 Judgment Plan。

## Decision

- 继续保持离线 fixture，不调用实时金融 API。
- 新增可复现 synthetic fixture 生成脚本，只产出私有 raw/processed artifacts，不把市场数据入库。
- Query Contract 增加显式 runtime seed：`--market-snapshot-id` 和 `--market-as-of-date`。这不是让模型猜日期，而是由本地 fixture artifact 明确注入 source stamp，避免已有 evidence 时 contract 仍报 `missing_market_snapshot_id/as_of_date`。
- 7-company main-chain smoke 使用本地 10-K/10-Q 覆盖完整的集合 `MSFT, AMZN, GOOGL, JPM, CVX, PG, LLY`。按 164 原集合 `MSFT, NVDA, JPM, CVX, PG, LLY, WMT` 跑 planner 时发现当前本地 mixed manifest 对 `NVDA/WMT` 缺 2026 10-Q，会产生 source coverage gaps；因此本次主链路 smoke 避开该 SEC 覆盖缺口，专门验证 market source 接入。

## Work Completed

- 新增 `scripts/market/05_generate_market_snapshot_fixture.py`
  - 生成 deterministic 7-company + SPY 3M OHLCV / valuation synthetic fixture。
  - 同步生成 8-K earnings release 和 latest 10-Q filing event dates，用于 event-window returns。

- 新增 `scripts/market/60_smoke_market_snapshot_main_chain.py`
  - 构建 Query Contract。
  - 使用 BM25-only retrieval 跑 `pipeline_context`，避免本地缺 BGE 模型影响 source integration smoke。
  - 执行 market context 注入、runtime exact-value ledger、Evidence Coverage Matrix、Judgment Plan。
  - 输出 `market_snapshot_main_chain_smoke_summary.json`，但不调用 synthesis LLM。

- 更新 `scripts/cloud/sec_agent_interactive.py`
  - 增加 `--market-snapshot-id` / `--market-as-of-date` seed 参数。
  - broad cross-industry prompt 中即使包含 `JPM`，也不再自动切成 banking-only contract；只有显式银行指标意图或 JPM-only focus 才进入 banking contract。

- 更新 `tests/test_market_snapshot_fixture.py`
  - 覆盖 runtime snapshot seed 清除 market source gaps。
  - 覆盖跨行业 market prompt 包含 JPM 时不误判成 banking-only。

## Verification

Commands run:

```powershell
python -m py_compile scripts/market/05_generate_market_snapshot_fixture.py scripts/market/60_smoke_market_snapshot_main_chain.py scripts/cloud/sec_agent_interactive.py
python -m pytest tests/test_market_snapshot_fixture.py tests/test_sec_agent_10q_source_contract.py::test_heuristic_banking_contract_sets_source_tiers_without_planner_state -q
python -m pytest tests -q
```

Results:

- Targeted tests: `11 passed`
- Full local suite: `99 passed`

Market fixture artifact smoke:

```powershell
python scripts/market/05_generate_market_snapshot_fixture.py --snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --as-of-date 2026-05-25 --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY
python scripts/market/10_normalize_market_snapshot_fixture.py --input data/raw_private/market/fixtures/market_pilot_2026-05-25_7co_mixed_coverage_v1_daily_fixture.csv --output-root data/processed_private/market --snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --as-of-date 2026-05-25 --provider synthetic_local_fixture --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY --benchmark-tickers SPY
python scripts/market/30_compute_market_analytics.py --output-root data/processed_private/market --snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --window 3M --benchmark-ticker SPY --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY --events data/raw_private/market/fixtures/market_pilot_2026-05-25_7co_mixed_coverage_v1_events.csv
python scripts/market/40_build_market_evidence_pack.py --output-root data/processed_private/market --snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --window 3M --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY --max-rows 7
python scripts/market/50_validate_market_snapshot.py --output-root data/processed_private/market --snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --window 3M --report reports/quality/market_snapshot_pilot_2026-05-25_7co_mixed_coverage_v1_validation.json
python scripts/market/20_build_market_snapshot_catalog.py --output-root data/processed_private/market
```

Artifact results:

- Generated fixture rows: `760`
- Event rows: `14`
- Normalized bars: `760`
- Snapshot rows: `7`
- Analytics rows: `7`
- Evidence pack rows: `7`
- Validation: `can_enter_market_snapshot_chain=true`, `error_count=0`, `warning_count=0`
- DuckDB catalog after both local fixture runs: `market_daily_bars=1520`, `market_snapshots=14`, `market_analytics=14`

Planner / contract smoke:

```powershell
python scripts/cloud/sec_agent_interactive.py --plan-only --query-planner heuristic --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY --years 2025,2026 --manifest-path data/processed_private/manifests/sec_tech_primary_mixed_10k_10q_manifest_2023_2026.jsonl --market-evidence-path data/processed_private/market/evidence_packs/market_pilot_2026-05-25_7co_mixed_coverage_v1_3m_market_evidence.jsonl --market-snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --market-as-of-date 2026-05-25 --prompt "结合SEC 10-Q/10-K和本地市场快照，比较MSFT、AMZN、GOOGL、JPM、CVX、PG、LLY的基本面动能、市场反应和估值语境是否匹配；注明每类证据边界和市场快照日期。"
```

Result:

- `source_policy=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT`
- `source_coverage_gaps=[]`
- `market_source_gaps=[]`
- `market_snapshot.snapshot_id=market_pilot_2026-05-25_7co_mixed_coverage_v1`
- `market_snapshot.as_of_date=2026-05-25`
- Broad prompt with JPM kept general revenue/profitability/cash-flow contract, not banking-only.

Main-chain smoke:

```powershell
python scripts/market/60_smoke_market_snapshot_main_chain.py --tickers MSFT,AMZN,GOOGL,JPM,CVX,PG,LLY --years 2025,2026 --market-evidence-path data/processed_private/market/evidence_packs/market_pilot_2026-05-25_7co_mixed_coverage_v1_3m_market_evidence.jsonl --market-snapshot-id market_pilot_2026-05-25_7co_mixed_coverage_v1 --market-as-of-date 2026-05-25 --prompt "结合SEC 10-Q/10-K和本地市场快照，比较MSFT、AMZN、GOOGL、JPM、CVX、PG、LLY的基本面动能、市场反应和估值语境是否匹配；注明每类证据边界和市场快照日期。"
```

Result summary:

- `status=pass`
- `context_row_count=540`
- `market_context_row_count=7`
- `ledger_row_count=80`
- `coverage_complete=true`
- `primary_task_support_complete=true`
- `market_snapshot_support_complete=true`
- `covered_market_fields` includes returns, relative return, drawdown, volatility, valuation, market cap, event-window fields.
- `judgment_plan_present=true`
- Output root: `eval/sec_cases/outputs/market_snapshot_main_chain_smoke/20260525_203832_44f4a210b8`

Rerun after implementation review:

- Full local suite: `99 passed`
- Main-chain smoke: `status=pass`
- Output root: `eval/sec_cases/outputs/market_snapshot_main_chain_smoke/20260525_210829_44f4a210b8`

## Smoke Boundary

- This stage intentionally did not call DeepSeek/Qwen synthesis. The new main-chain smoke stops before LLM synthesis so it can validate source integration without API keys or local GPU model availability.
- Market data artifacts remain under ignored private paths:
  - `data/raw_private/market/fixtures/`
  - `data/processed_private/market/`
  - validation/report/runtime output under ignored `reports/quality/` and `eval/`
- The smoke uses BM25-only retrieval as a local source-integration ablation. It does not claim BGE-M3 rerank quality.

## Remaining Work

- Run one real DeepSeek API full-chain synthesis using the same 7-company market evidence pack.
- Inspect rendered memo for source boundary quality: SEC/10-Q audited/unaudited boundary, market snapshot `as_of_date`, valuation/return claims citing market evidence ids, and no market data overriding SEC ledger facts.
- Decide whether to backfill NVDA/WMT 2026 10-Q locally or keep the market smoke universe aligned to available 10-Q coverage.
