# Market Snapshot Event Window And FMP Valuation Contract

Date: 2026-05-25

## Goal

在真实 Yahoo price/volume snapshot 已可用的基础上，继续补两类能力：

1. 用 SEC filing date 生成真实事件窗口，先接 latest 10-Q filing event。
2. 为 full30 估值字段准备免费 key provider enrichment，不在没有 key 的情况下生成伪数据。

## Changes

### Close Price Field Status Fix

Root cause:

- `normalize_market_snapshot_fixture()` 的 `field_status` 直接检查 `latest["close_price"]`，但 bar row 使用的是 `adjusted_close` / `close` 字段。
- 结果是 raw `close/adjusted_close` 完整，但 snapshot `field_status.close_price` 被错误标为 `missing_not_provided`。

Fix:

- `src/sec_agent/market_snapshot.py` 新增 `_snapshot_field_value()`，将 `close_price` 映射到 latest bar 的 `adjusted_close` / `close`。
- 重新 normalize 后，真实 Yahoo full30 snapshot 的 `close_price` 为 `30/30 provided`。

### SEC Manifest Event Window Builder

Added:

- `scripts/market/08_build_market_events_from_sec_manifest.py`

Contract:

- Reads one or more SEC manifest JSONL files.
- Maps:
  - `10-Q` -> `latest_10q_filing`
  - `8-K` -> `8k_earnings_release`
  - `10-K` -> `latest_10k_filing`
- Selects the latest filing date per `(ticker, event_type)`.
- Writes normal analytics-compatible CSV:
  - `ticker`
  - `event_type`
  - `event_date`
  - `source`
  - `form_type`
  - `fiscal_year`
  - `accession_number`
  - `filing_url`

Command run:

```powershell
python scripts/market/08_build_market_events_from_sec_manifest.py `
  --manifest-paths data/processed_private/manifests/sec_tech_10q_full_manifest_2026.jsonl `
  --tickers-config configs/sec_tech_full30_fy2023_2027.yaml `
  --years 2026 `
  --form-types 10-Q `
  --output data/raw_private/market/provider_snapshots/20260525_market_events_full30_latest_10q_2026_v1.csv
```

Result:

- `event_count=26`
- `event_types=["latest_10q_filing"]`
- Missing event tickers are the same as current local 2026 10-Q inventory gaps: `NVDA`, `CRWD`, `SNOW`, `WMT`.

After recomputing analytics:

- `analytics_count=30`
- tickers with event-window values: `26`
- one event-window gap remains because at least one filing is too close to the snapshot date to support the full 10-day window.
- covered market fields in main-chain smoke now include:
  - `latest_10q_filing_return_1d`
  - `latest_10q_filing_return_3d`
  - `latest_10q_filing_return_5d`
  - `latest_10q_filing_return_10d`

### FMP Valuation Enrichment Script

Added:

- `scripts/market/07_enrich_market_snapshot_valuation_fmp.py`

Provider decision:

- Use Financial Modeling Prep as the first free-key valuation provider candidate because the stable API exposes batch quote and key-metrics TTM style endpoints, which fit full30 enrichment better than one-off no-key scrape endpoints.
- Key handling: script only reads an environment variable, default `FMP_API_KEY`; it never writes the key.
- Default base URL: `https://financialmodelingprep.com/stable`

Field mapping:

- `market_cap`: from quote / key metrics market-cap fields.
- `enterprise_value`: from key metrics enterprise-value fields.
- `pe_ttm`: from quote PE or key-metrics PE fields.
- `ev_sales_ttm`: from key metrics EV/Sales fields.
- `ev_ebitda_ttm`: from key metrics EV/EBITDA fields.

Behavior:

- Reads the existing Yahoo daily bars CSV.
- Enriches only the latest row per target ticker.
- Leaves benchmarks such as `SPY` and `QQQ` untouched.
- Writes an enriched daily-bars CSV that can be fed back into `10_normalize_market_snapshot_fixture.py`.
- Fail-closed if `FMP_API_KEY` is missing.

Local check:

```powershell
python scripts/market/07_enrich_market_snapshot_valuation_fmp.py `
  --input data/raw_private/market/provider_snapshots/20260525_market_yahoo_chart_full30_3m_v1_daily_bars.csv `
  --snapshot-id 20260525_market_yahoo_chart_full30_3m_v1 `
  --tickers-config configs/sec_tech_full30_fy2023_2027.yaml `
  --benchmark-tickers SPY,QQQ
```

Result:

- `FMP_API_KEY` was not set locally.
- Script exited without writing enriched valuation data.
- This is expected and prevents accidental pseudo-valuation.

## Validation

Unit tests:

```powershell
python -m pytest tests/test_market_snapshot_fixture.py -q
```

Result:

- `13 passed`

Real snapshot rebuild:

- Re-ran normalize on `20260525_market_yahoo_chart_full30_3m_v1_daily_bars.csv`.
- Re-ran analytics with `20260525_market_events_full30_latest_10q_2026_v1.csv`.
- Rebuilt market evidence pack.
- Re-ran validator:
  - `can_enter_market_snapshot_chain=true`
  - `error_count=0`
  - `warning_count=0`

Main-chain smoke:

```powershell
python scripts/market/60_smoke_market_snapshot_main_chain.py `
  --prompt "结合SEC基本面、最近三个月市场表现和最新10-Q filing后的事件窗口，比较当前full30公司中哪些公司的市场反应与已披露基本面最一致，哪些可能存在分歧。" `
  --tickers <full30> `
  --years 2025 `
  --market-evidence-path data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_v1_3m_market_evidence.jsonl `
  --market-snapshot-id 20260525_market_yahoo_chart_full30_3m_v1 `
  --market-as-of-date 2026-05-22 `
  --output-root eval/sec_cases/outputs/market_snapshot_main_chain_smoke_real_yahoo_events_2025sec
```

Result:

- status: `pass`
- market context rows: `30`
- covered market fields include returns, relative return, drawdown, volatility, close price, and latest-10Q event-window returns.
- source coverage gaps: `[]`
- market source gaps: `[]`
- run root: `eval/sec_cases/outputs/market_snapshot_main_chain_smoke_real_yahoo_events_2025sec/20260525_234439_0a03f667cf`

## Next Step

When an FMP free key is available:

```powershell
$env:FMP_API_KEY="<your-free-key>"
python scripts/market/07_enrich_market_snapshot_valuation_fmp.py `
  --input data/raw_private/market/provider_snapshots/20260525_market_yahoo_chart_full30_3m_v1_daily_bars.csv `
  --snapshot-id 20260525_market_yahoo_chart_full30_3m_v1 `
  --tickers-config configs/sec_tech_full30_fy2023_2027.yaml `
  --benchmark-tickers SPY,QQQ `
  --fail-on-missing
```

Then feed the enriched CSV through:

1. `10_normalize_market_snapshot_fixture.py`
2. `30_compute_market_analytics.py --events ...`
3. `40_build_market_evidence_pack.py`
4. `50_validate_market_snapshot.py`
5. `60_smoke_market_snapshot_main_chain.py`

Only after that run passes should valuation fields be promoted in renderer/gates as valuation-capable market evidence.
