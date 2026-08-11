# 165 Market Snapshot DuckDB Pilot Infra

Date: 2026-05-25

## Problem

按照 `164_market_snapshot_offline_fixture_source_plan.md`，进入 market snapshot pilot 前需要先把本地 DuckDB/parquet 存储、离线 fixture 标准化、确定性 analytics 和 compact evidence pack 做成可测试基础设施。用户明确要求先配置 DuckDB，再继续后续 pilot。

## Decision

- 先不接实时 API，不下载真实行情数据，不把 market snapshot 写入 session JSON store。
- 市场数据只进入 `data/processed_private/market/...` 这类 ignored/private 路径；session/context 后续只保存 artifact refs。
- 本阶段只做离线 fixture 底座和脚本入口；主链路 Query Contract、Coverage Matrix、Judgment Plan、Synthesis、Gates、Renderer 仍按 164 的后续步骤推进。
- 不给业务兜底结论。market 数值必须来自 fixture -> deterministic analytics -> evidence pack。

## Work Completed

- 配置 DuckDB:
  - `requirements.txt` 增加 `duckdb>=1.0.0`。
  - 本地安装并验证 `duckdb 1.5.3`，`select 1` 可执行。
- 新增核心模块:
  - `src/sec_agent/market_snapshot.py`
  - 支持 CSV/JSON/JSONL 离线 fixture 输入。
  - 对坏日期、缺价格、重复 `ticker/date`、请求 ticker 缺失执行 fail-closed 校验。
  - 输出 normalized daily bars、as-of snapshot、analytics、evidence pack。
  - 自动写 JSONL，并通过 DuckDB 写 parquet；DuckDB 不可用时不静默降级。
  - 支持 DuckDB catalog: `market_daily_bars`, `market_snapshots`, `market_analytics`。
- 新增脚本入口:
  - `scripts/market/10_normalize_market_snapshot_fixture.py`
  - `scripts/market/20_build_market_snapshot_catalog.py`
  - `scripts/market/30_compute_market_analytics.py`
  - `scripts/market/40_build_market_evidence_pack.py`
  - `scripts/market/50_validate_market_snapshot.py`
- 新增测试:
  - `tests/test_market_snapshot_fixture.py`
  - 使用 synthetic 3-company + SPY fixture，不依赖真实市场数据或外部 API。

## Current Data Contract

Source tier:

- `market_snapshot`

Required stamped fields:

- `snapshot_id`
- `as_of_date`
- `provider`
- `ticker`
- `source_boundary`

Supported snapshot fields:

- `close_price`
- `market_cap`
- `enterprise_value`
- `pe_ttm`
- `ev_sales_ttm`
- `ev_ebitda_ttm`

Supported deterministic analytics:

- `return_1d`
- `return_5d`
- `return_1m`
- `return_3m`
- `return_ytd`
- `relative_return_vs_benchmark_3m`
- `max_drawdown_3m`
- `volatility_3m`
- `peer_ev_sales_rank`
- `peer_ev_sales_bucket`
- neutral derived signals such as `market_reaction_positive`, `outperformed_benchmark_3m`, `valuation_premium_vs_peers`

Not yet implemented:

- Event-window returns around 8-K / 10-Q dates.
- Fundamental-market divergence tool that compares SEC/8-K drivers against market analytics.
- Query Contract / Coverage Matrix / Judgment Plan / Synthesis / Gates / Renderer integration.
- 7-company real local fixture smoke.

## Verification

Commands run:

```powershell
python -m py_compile src/sec_agent/market_snapshot.py scripts/market/10_normalize_market_snapshot_fixture.py scripts/market/20_build_market_snapshot_catalog.py scripts/market/30_compute_market_analytics.py scripts/market/40_build_market_evidence_pack.py scripts/market/50_validate_market_snapshot.py
python -m pytest tests/test_market_snapshot_fixture.py -q
```

Result:

- full local test suite: `90 passed`
- CLI synthetic smoke:
  - normalized 360 daily bars and 3 snapshot rows.
  - built analytics for `NVDA, MSFT, JPM` with `SPY` benchmark.
  - built compact market evidence pack.
  - built DuckDB catalog.
  - validation returned `can_enter_market_snapshot_chain: true`, `error_count: 0`, `warning_count: 0`.

Smoke artifacts were generated only under `.tmp_market_snapshot_smoke_*` and are not staged.

## Next Steps

1. Add event date inputs and event-window analytics for 8-K earnings release and latest 10-Q filing dates.
2. Add `fundamental_market_divergence_view` after SEC/8-K driver outputs are available to compare against market signals.
3. Extend Query Contract planner schema and validator for `market_snapshot`, `market_window`, `market_fields`, and `market_analysis_tools`.
4. Extend Coverage Matrix and Judgment Plan to carry market field coverage, missing fields, source boundary, and driver strength.
5. Extend DeepSeek synthesis, deterministic gates, renderer, and ContextManager artifact refs.
6. Run the 7-company local fixture smoke from 164 before any real provider/API adapter.

## Safety Notes

- No provider credentials, API keys, passwords, or real market data were written.
- Generated market artifacts remain private/ignored.
- Market snapshot still cannot support investment recommendations, real-time/current price claims, or overwrite SEC reported facts.
