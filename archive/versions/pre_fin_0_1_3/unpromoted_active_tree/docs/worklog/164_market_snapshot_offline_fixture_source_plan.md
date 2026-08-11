# 164 Market Snapshot Offline Fixture Source Plan

Date: 2026-05-25

## Problem

- 当前 `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS` 链路已经能稳定完成 SEC 10-K/10-Q + 8-K earnings release 的全链路投研 memo，但仍缺少价格、估值、相对收益和市场反应视角。
- 下一步不是接实时行情 API，而是先拉一批离线市场快照到本地，验证“基本面 + 管理层解释 + 市场反应/估值”的完整投研分析链路。
- 目标是让 DeepSeek 像分析师一样做解释和取舍，同时由确定性工具负责取数、计算和校验。

## Scope And Non-Goals

In scope:

- 离线 `market_snapshot` fixture，不依赖实时 API。
- 先支持 7-company pilot: `MSFT, NVDA, JPM, CVX, PG, LLY, WMT`。
- 默认窗口: `3M` daily raw + compact analytics summary。
- 支持 as-of snapshot、returns、relative returns、drawdown、volatility、valuation multiples、peer rank、event-window return、fundamental-market divergence。
- 将 market snapshot 纳入 Query Contract、Evidence Coverage Matrix、Judgment Plan、Synthesis、Gates、Renderer 和 ContextManager artifact refs。

Out of scope for this stage:

- 不接实时交易 API。
- 不接 analyst consensus / target price / rating revision。
- 不做投资建议、价格预测或自动买卖评级。
- 不把市场数据写入 SEC Exact-Value Ledger。
- 不把 daily raw 明细默认塞进 prompt。

## Source Planning: Market Snapshot Offline Fixture

### Purpose

- 投研问题类型:
  - 基本面动能与市场表现是否一致。
  - 8-K 管理层解释是否被市场反应确认。
  - 估值是否已经反映 SEC filing 中的增长/风险。
  - 横向比较时，哪些公司是基本面强但市场反应弱，哪些是估值领先于基本面。
- 预期补充的证据缺口:
  - 当前 SEC-only 链路不能讨论股价、market cap、returns、valuation multiples、relative performance。
  - 当前 8-K 只能提供管理层叙事，不能说明市场是否认可叙事。
- 不解决的问题:
  - 不提供实时行情。
  - 不提供 consensus 或 sell-side 预期差。
  - 不解释市场反应背后的新闻驱动，除非未来另接新闻源。

### Source Contract

- `source_tier`: `market_snapshot`
- `source_policy`: `SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT`
- Source nature: third-party / offline fixture / non-real-time
- Freshness field:
  - `as_of_date`: snapshot 日期，必填。
  - `window`: analytics 窗口，例如 `3M`。
  - `generated_at`: 本地生成时间。
- Required metadata:
  - `snapshot_id`
  - `provider`
  - `provider_dataset`
  - `license_note`
  - `currency`
  - `field_definitions`
  - `raw_artifact_path`
  - `normalized_artifact_path`
  - `analytics_artifact_path`
- Allowed claim types:
  - price / market cap / valuation multiple at `as_of_date`
  - trailing-window return / relative return / drawdown / volatility
  - event-window return around filing or 8-K release date
  - peer rank / percentile within the current selected universe
  - fundamental-market divergence as a derived signal
- Disallowed claim types:
  - unstamped “current price/latest market cap”
  - market facts without `as_of_date`
  - using market data to overwrite SEC reported financial facts
  - implying audited financial authority from market snapshot
  - buy/sell/rating/target-price recommendations
  - model-memory price, valuation, market cap, or return numbers

## Planner Execution Contract

Planner must decide both source tier and analysis tools. Market snapshot should only be requested when the user asks, explicitly or implicitly, about valuation, price performance, market reaction, market confirmation, market divergence, or whether fundamentals are already priced in.

Required planner output additions:

```json
{
  "analysis_intent": "fundamental_vs_market_reaction",
  "source_tiers": [
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "market_snapshot"
  ],
  "market_snapshot": {
    "required": true,
    "snapshot_id": "market_pilot_2026-05-25_manual_v1",
    "as_of_date": "2026-05-25",
    "window": "3M",
    "fields": [
      "close_price",
      "market_cap",
      "return_1m",
      "return_3m",
      "return_ytd",
      "relative_return_vs_spy_3m",
      "relative_return_vs_sector_3m",
      "max_drawdown_3m",
      "volatility_3m",
      "pe_ttm",
      "ev_sales_ttm",
      "ev_ebitda_ttm"
    ],
    "analysis_tools": [
      "return_summary",
      "peer_relative_return",
      "valuation_peer_rank",
      "post_filing_event_return",
      "fundamental_market_divergence"
    ]
  },
  "required_sections": [
    "fundamental_signal",
    "management_explanation",
    "market_reaction",
    "valuation_context",
    "fundamental_market_divergence",
    "risks_and_counterarguments",
    "evidence_boundaries"
  ]
}
```

Planner limits:

- `market_analysis_tools` max 5.
- `market_fields` max 16.
- `market_window` initially limited to `3M`, `6M`, `YTD`, `1Y`; default `3M`.
- If no market snapshot artifact exists for requested tickers/as-of date, planner must produce a source gap, not invent market data.

## Storage Design

Do not store full market data inside session context or the ContextManager JSON store. Store market artifacts under private data paths and keep session state as references only.

Recommended layout:

```text
data/raw_private/market/manual_snapshot/<snapshot_id>/
  provider_export.csv
  provider_export_metadata.json

data/processed_private/market/bars/
  provider=<provider>/symbol=<ticker>/year=<yyyy>/part-*.parquet

data/processed_private/market/snapshots/
  market_snapshot_pilot_<as_of_date>.jsonl
  market_snapshot_pilot_<as_of_date>.parquet

data/processed_private/market/analytics/
  market_analytics_pilot_<as_of_date>_3m.jsonl
  market_analytics_pilot_<as_of_date>_3m.parquet

data/processed_private/market/catalog.duckdb
```

DuckDB role:

- Query normalized parquet and analytics artifacts locally/cloud-side.
- Maintain lightweight tables:
  - `market_snapshot_catalog`
  - `market_daily_bars`
  - `market_snapshot_fields`
  - `market_analytics`
  - `market_event_windows`
- Not a replacement for raw artifact retention. Raw provider exports stay under `data/raw_private/market/...`.

ContextManager/session role:

```json
{
  "market_snapshot_ref": {
    "snapshot_id": "market_pilot_2026-05-25_manual_v1",
    "as_of_date": "2026-05-25",
    "window": "3M",
    "provider": "manual_fixture",
    "analytics_path": "data/processed_private/market/analytics/market_analytics_pilot_2026-05-25_3m.jsonl",
    "snapshot_path": "data/processed_private/market/snapshots/market_snapshot_pilot_2026-05-25.jsonl",
    "catalog_path": "data/processed_private/market/catalog.duckdb"
  }
}
```

## Market Data Schemas

### Daily Bar Raw/Normalized Row

```json
{
  "snapshot_id": "market_pilot_2026-05-25_manual_v1",
  "ticker": "NVDA",
  "date": "2026-05-25",
  "open": 0.0,
  "high": 0.0,
  "low": 0.0,
  "close": 0.0,
  "adjusted_close": 0.0,
  "volume": 0,
  "currency": "USD",
  "provider": "manual_fixture"
}
```

### Snapshot Row

```json
{
  "snapshot_id": "market_pilot_2026-05-25_manual_v1",
  "ticker": "NVDA",
  "as_of_date": "2026-05-25",
  "provider": "manual_fixture",
  "currency": "USD",
  "close_price": 0.0,
  "market_cap": 0.0,
  "enterprise_value": 0.0,
  "pe_ttm": 0.0,
  "ev_sales_ttm": 0.0,
  "ev_ebitda_ttm": 0.0,
  "field_status": {
    "market_cap": "provided",
    "enterprise_value": "missing_not_provided"
  },
  "field_definitions": {
    "pe_ttm": "trailing twelve month price-to-earnings ratio from provider export"
  }
}
```

### Analytics Row

```json
{
  "snapshot_id": "market_pilot_2026-05-25_manual_v1",
  "ticker": "NVDA",
  "as_of_date": "2026-05-25",
  "window": "3M",
  "market_reaction": {
    "return_1m": 0.0,
    "return_3m": 0.0,
    "return_ytd": 0.0,
    "relative_return_vs_spy_3m": 0.0,
    "relative_return_vs_sector_3m": 0.0,
    "max_drawdown_3m": 0.0,
    "volatility_3m": 0.0
  },
  "valuation_context": {
    "pe_ttm": 0.0,
    "ev_sales_ttm": 0.0,
    "peer_ev_sales_rank": 1,
    "peer_ev_sales_bucket": "top_quartile"
  },
  "event_window": {
    "after_8k_earnings_release_5d": 0.0,
    "after_latest_10q_filing_5d": 0.0
  },
  "derived_signals": [
    "market_reaction_positive",
    "valuation_premium_vs_peers"
  ],
  "source_boundary": "market_snapshot; non-real-time; as_of_date=2026-05-25"
}
```

## Tool Scripts To Prepare

Use script names that expose stage and object. Proposed scripts:

- `scripts/market/10_normalize_market_snapshot_fixture.py`
  - Input: local CSV/JSON provider export.
  - Output: normalized daily bars parquet, snapshot JSONL/parquet, metadata JSON.
  - Validates required fields, ticker/date uniqueness, as-of date, provider metadata.
- `scripts/market/20_build_market_snapshot_catalog.py`
  - Input: normalized parquet/JSONL artifacts.
  - Output: `data/processed_private/market/catalog.duckdb`.
  - Creates catalog tables and paths.
- `scripts/market/30_compute_market_analytics.py`
  - Input: catalog + selected tickers + window.
  - Output: analytics JSONL/parquet.
  - Computes returns, relative returns, drawdown, volatility, valuation peer rank.
- `scripts/market/40_build_market_evidence_pack.py`
  - Input: query contract + analytics artifact + snapshot artifact.
  - Output: compact market evidence rows for synthesis.
  - Caps rows and fields; preserves `snapshot_id`, `as_of_date`, `field_name`.
- `scripts/market/50_validate_market_snapshot.py`
  - Input: snapshot + analytics + optional event dates.
  - Output: validation report.
  - Checks as-of date, missing fields, duplicate tickers, invalid returns, source metadata.
- `scripts/market/60_smoke_market_snapshot_tool_calls.py`
  - Deterministic tool-call fixture replay for planner/tool integration.

Future tool-harness actions:

- `get_market_snapshot`
- `get_market_reaction_view`
- `get_valuation_view`
- `get_event_window_view`
- `get_fundamental_market_divergence_view`
- `inspect_market_snapshot`

Tool outputs must be compact JSON objects with `snapshot_id`, `as_of_date`, `ticker`, `field_refs`, and `source_boundary`.

## Evidence Coverage Matrix Changes

Add market-aware coverage dimensions:

- `required_market_fields`
- `covered_market_fields`
- `missing_market_fields`
- `required_market_tools`
- `covered_market_tools`
- `market_snapshot_as_of_date`
- `market_snapshot_id`
- `market_support_level`

Coverage matrix behavior:

- If planner requests market snapshot but no snapshot artifact exists, mark `answer_status=partial` or `insufficient`.
- If required market fields are missing, do not let synthesis make those market claims.
- If SEC/8-K coverage is complete but market coverage is partial, the answer may still discuss fundamentals but must mark market analysis as incomplete.
- If market snapshot exists but `as_of_date` is missing, fail coverage for market tasks.

## Judgment Plan Changes

Judgment Plan should include separate driver groups:

- `fundamental_drivers`: SEC 10-K/10-Q ledger-backed signals.
- `management_explanation_drivers`: 8-K / earnings release commentary with unaudited boundary.
- `market_reaction_drivers`: return/drawdown/relative-performance signals.
- `valuation_context_drivers`: valuation multiples, peer rank, historical percentile if available.
- `divergence_drivers`: fundamental-market consistency or divergence.
- `risk_counter_drivers`: evidence that weakens the thesis.

Each market driver must carry:

- `snapshot_id`
- `as_of_date`
- `field_refs`
- `analysis_tool`
- `conclusion_strength`
- `source_boundary`

Main judgment strength should be capped by the weakest required pillar. Example:

- Strong SEC fundamental evidence + missing market snapshot = no strong “market has priced it in” claim.
- Strong market reaction + weak SEC evidence = no strong “fundamentals improved” claim.

## Synthesis Contract

API memo vnext should require these sections:

- `fundamental_signal`
- `management_explanation`
- `market_reaction`
- `valuation_context`
- `fundamental_market_divergence`
- `risks_and_counterarguments`
- `watch_items`
- `source_limitations`

Rules:

- SEC exact values come only from `runtime_exact_value_ledger`.
- 8-K material supports management explanation and current-period unaudited commentary.
- Market snapshot supports market/valuation/return claims only.
- Market claims must include `snapshot_id`, `as_of_date`, and field refs.
- Daily raw rows are not shown unless the user asks for event-window detail or the tool flags an anomaly.
- The model must not directly calculate returns from daily rows in prose; deterministic tools calculate them.

Required interpretation patterns:

- SEC fundamental strong + market weak = `fundamental_market_divergence`.
- 8-K optimistic + market weak = `market did not confirm management narrative`.
- Valuation high + SEC growth modest = `valuation ahead of filed fundamentals`.
- Market value/fundamental value conflict = SEC ledger wins for reported fundamentals; market snapshot remains valuation context.

## Gates

New deterministic gates:

- `market_snapshot_as_of_date_gate`
  - Every market/valuation/return claim must carry `as_of_date`.
- `market_field_support_gate`
  - Every price, return, valuation multiple, market cap, drawdown, volatility claim must cite a snapshot/analytics field.
- `market_source_boundary_gate`
  - Renderer and answer must label market snapshot as non-real-time market data.
- `sec_market_fact_separation_gate`
  - Market data cannot overwrite SEC reported revenue, earnings, capex, cash flow, margin, assets, liabilities.
- `market_missing_field_gate`
  - If required field is missing, answer must say it is unavailable rather than infer.
- `derived_signal_label_gate`
  - Derived analytics such as divergence, peer rank, percentile, abnormal/event return must be labeled as tool-derived, not provider-reported fact.
- `no_unstamped_market_claim_gate`
  - Blocks “当前股价 / 最新市值 / 市场已经反映” without explicit snapshot date.

Existing gates to extend:

- named-fact support gate should inspect market field refs.
- answer-vs-Judgment-Plan gate should enforce market driver strength.
- source coverage gate should understand `market_snapshot` source tier.
- renderer boundary gate should include SEC / 8-K / market snapshot separately.

## Renderer

Rendered answer should display source boundaries as separate blocks:

```text
证据边界
- SEC 10-K/10-Q: reported financial facts; 10-Q unaudited quarterly filing where applicable.
- 8-K earnings release: company-authored unaudited management material.
- Market snapshot: non-real-time market data, as_of_date=2026-05-25, provider=manual_fixture.
```

Market sections:

```text
市场反应
1. NVDA 3M return ... as of 2026-05-25 ...

估值语境
1. NVDA EV/Sales rank ... within selected peer universe ...

基本面-市场分歧
1. SEC evidence shows ..., while market snapshot shows ...
```

Each rendered market reference should include:

- ticker
- field name
- value
- window
- as_of_date
- provider or snapshot id

## ContextManager And Session Handling

Do not persist market data values inside session memory except compact summaries needed for immediate conversation display. Store artifact refs:

- `market_snapshot_ref`
- `market_analytics_ref`
- `market_evidence_pack_ref`
- `market_snapshot_as_of_date`
- `market_snapshot_scope`

Session resume behavior:

- If user continues in same session, reuse the same snapshot by default.
- If user asks “最新市场表现” and snapshot is stale, ask for or trigger a new snapshot artifact; do not silently use model memory.
- If scope changes to tickers not covered by snapshot, invalidate market snapshot coverage only, not SEC artifacts.
- `/context` should show snapshot id/path/date, not raw daily rows.

## Pilot Plan

Pilot universe:

- `MSFT, NVDA, JPM, CVX, PG, LLY, WMT`

Manual fixture input:

- One local CSV/JSON bundle containing:
  - 3M daily OHLCV or adjusted close.
  - as-of snapshot fields.
  - optional provider valuation fields.
  - provider/source metadata.

Pilot prompt:

```text
结合SEC 10-Q/10-K、8-K业绩新闻稿和本地市场快照，比较MSFT、NVDA、JPM、CVX、PG、LLY、WMT的基本面动能、管理层解释、市场反应和估值语境是否匹配；注明每类证据边界和市场快照日期。
```

Success criteria:

- Planner selects `market_snapshot` only when prompt requires market/valuation context.
- Market tool calls read local fixture and produce compact evidence pack.
- Coverage Matrix records market fields/tools and missing fields.
- Judgment Plan includes fundamental, 8-K, market, valuation, divergence, and risk drivers.
- DeepSeek output uses market data for market/valuation analysis only.
- Gates pass with no unstamped market claims.
- Renderer clearly separates SEC, 8-K, and market snapshot boundaries.

Failure criteria:

- Any market number appears without `snapshot_id/as_of_date/field_ref`.
- Model invents market data not in snapshot.
- Market snapshot overwrites SEC ledger facts.
- Daily raw data floods prompt or answer.
- Missing valuation fields are inferred instead of marked unavailable.

Rollback:

- Disable `market_snapshot` source tier and revert source policy to `SEC_PRIMARY_MIXED_WITH_8K_EARNINGS`.
- Keep market artifacts private and ignored.
- Existing SEC/8-K chain remains unchanged.

## Implementation Order

1. Add schema/fixture validation tests for `market_snapshot`.
2. Add local fixture normalizer script.
3. Add DuckDB catalog builder.
4. Add analytics computation script.
5. Add market evidence pack builder.
6. Extend Query Contract planner schema and validator.
7. Extend Coverage Matrix.
8. Extend Judgment Plan.
9. Extend synthesis prompt/normalizer.
10. Add market-specific deterministic gates.
11. Extend renderer.
12. Add ContextManager artifact refs.
13. Run 7-company local fixture smoke.
14. Only after local fixture smoke passes, consider provider adapter for a real API.

## Safety Notes

- No API keys, passwords, or provider credentials are needed for the offline fixture stage.
- Raw and processed market data stay under ignored private data directories.
- This document does not authorize real-time API ingestion or commercial redistribution.
