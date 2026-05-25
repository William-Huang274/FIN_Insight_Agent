# Real Market Snapshot Provider Probe

Date: 2026-05-25

## Goal

为 `market_snapshot` 链路找一个可以立即离线落盘测试的真实免费 provider。要求是不依赖实时订阅、不写入密钥、覆盖当前 full30 公司，并能进入现有 CSV -> normalize -> DuckDB -> analytics -> evidence pack -> main-chain smoke。

## Provider Probe

### Selected For Pilot: Yahoo Chart Endpoint

- Provider label: `yahoo_finance_chart_unofficial`
- Access mode: no API key in this probe.
- Coverage tested: full30 target tickers plus `SPY,QQQ`.
- Result: `32/32` symbols downloaded successfully.
- Window: `3mo`, `1d`.
- Latest common market date: `2026-05-22`.
- Saved rows: `2048` daily OHLCV rows.
- Data available: open, high, low, close, adjusted close, volume, currency, exchange/company metadata in provider probe JSON.
- Data missing: market cap, enterprise value, P/E, EV/Sales, EV/EBITDA. Yahoo quote and quoteSummary endpoints returned `401 Unauthorized` in this environment, so valuation fields are explicitly saved as `missing_not_provided`.
- Boundary: suitable for market reaction, relative return, drawdown, volatility, and event-window price reaction. Not suitable yet for valuation analysis without a key-backed or alternate valuation provider.

### Not Selected Now

- Stooq CSV: no-key daily CSV request returned an API-key/captcha instruction page, so it is not directly usable for automated no-key download in this environment.
- Alpha Vantage: official docs require `apikey`; demo quote for `MSFT` worked, but this is not a legitimate full30 provider run. It remains a candidate if we decide to manage a free key.
- Financial Modeling Prep: broad stock, statements, historical, market cap, and ratio endpoints exist, but official docs require API-key authorization. The demo quote request returned `401` here, so it is not used for this no-key pilot.

## Implementation

Added:

- `scripts/market/06_download_yahoo_chart_snapshot.py`

The script downloads Yahoo chart daily bars, writes a normalizer-compatible CSV, and writes a provider probe JSON with per-ticker coverage, latest date, row count, failures, and valuation-field status.

Command used:

```powershell
python scripts/market/06_download_yahoo_chart_snapshot.py `
  --tickers-config configs/sec_tech_full30_fy2023_2027.yaml `
  --benchmark-tickers SPY,QQQ `
  --range 3mo `
  --interval 1d `
  --snapshot-id 20260525_market_yahoo_chart_full30_3m_v1 `
  --fail-on-missing
```

## Saved Artifacts

Private raw artifacts:

- `data/raw_private/market/provider_snapshots/20260525_market_yahoo_chart_full30_3m_v1_daily_bars.csv`
- `data/raw_private/market/provider_snapshots/20260525_market_yahoo_chart_full30_3m_v1_provider_probe.json`

Private processed artifacts:

- `data/processed_private/market/bars/20260525_market_yahoo_chart_full30_3m_v1_daily_bars.jsonl`
- `data/processed_private/market/bars/20260525_market_yahoo_chart_full30_3m_v1_daily_bars.parquet`
- `data/processed_private/market/snapshots/20260525_market_yahoo_chart_full30_3m_v1_snapshot.jsonl`
- `data/processed_private/market/snapshots/20260525_market_yahoo_chart_full30_3m_v1_snapshot.parquet`
- `data/processed_private/market/analytics/20260525_market_yahoo_chart_full30_3m_v1_3m_analytics.jsonl`
- `data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_v1_3m_market_evidence.jsonl`
- `data/processed_private/market/catalog.duckdb`

Validation report:

- `reports/quality/20260525_market_yahoo_chart_full30_3m_v1_validation.json`

## Validation

Provider download:

- full30 + `SPY,QQQ`: `32/32` symbols downloaded.
- raw rows: `2048`.
- per-symbol latest date: `2026-05-22`.

Normalization:

- daily bars: `2048`.
- target snapshots: `30`.
- benchmark tickers: `SPY,QQQ`.
- as-of date: `2026-05-22`.

Analytics:

- analytics rows: `30`.
- benchmark: `SPY`.
- covered fields: `return_1d`, `return_5d`, `return_1m`, `return_3m`, `return_ytd`, `relative_return_vs_benchmark_3m`, `max_drawdown_3m`, `volatility_3m`, `close_price`.
- valuation fields remain missing by provider contract.

DuckDB catalog spot check:

- `market_daily_bars` rows for this snapshot: `2048`.
- `market_snapshots` rows for this snapshot: `30`.
- snapshot as-of range: `2026-05-22` to `2026-05-22`.

Validator:

- `can_enter_market_snapshot_chain=true`.
- `error_count=0`.
- `warning_count=0`.

Main-chain smoke:

- First full30 smoke with years `2025,2026` correctly attached market evidence, but final status was `fail` because existing SEC inventory has 2026 10-Q source gaps for `NVDA`, `CRWD`, `SNOW`, and `WMT`. This is not a market provider failure.
- Isolated full30 smoke with SEC year `2025` passed:
  - status: `pass`
  - market context rows: `30`
  - coverage complete: `true`
  - market snapshot support complete: `true`
  - market source gaps: `[]`
  - source coverage gaps: `[]`
  - run root: `eval/sec_cases/outputs/market_snapshot_main_chain_smoke_real_yahoo_2025sec/20260525_231449_eaa1444fea`

## Decision

Proceed with `yahoo_finance_chart_unofficial` as the first real no-key market snapshot provider for price/volume/return analytics only.

Do not claim valuation support yet. For valuation-quality output, the next provider step should either:

1. add a key-backed free-tier provider such as Alpha Vantage or FMP with a documented key-handling and rate-limit policy, or
2. compute valuation from independently sourced market cap / shares / fundamentals only after source terms and data contract are reviewed.

## Next Work

- Add a provider capability registry so planner/gates know whether a snapshot supports price-only, valuation, event-window, or fundamentals.
- Add a no-valuation renderer line so user-facing output says market snapshot covers price/return but not valuation.
- Decide whether to introduce a free-key provider for valuation fields, with keys stored only in environment variables and data saved under private paths.
- Fix remaining 2026 SEC inventory gaps before promoting a `2025,2026 + market_snapshot` full30 smoke as a mainline result.
