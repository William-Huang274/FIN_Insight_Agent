# 347 R12 App Marketplace L3 Backfill

Date: 2026-06-17

## Scope

SLR3b turns the App Store / marketplace route from URL-pattern repair smoke into a first real materialized L3 runtime source. This tranche uses Apple App Store public pages mapped to iTunes Lookup API. It does not claim Google Play or full marketplace coverage.

Rows remain bounded proxy/context only: app listing metadata, rating, rating count, version, and release recency can support directional app-marketplace context, but cannot support downloads, app revenue, customer adoption, company market share, sales, or moat proof.

## Changes

- Added `scripts/data_expansion/build_app_marketplace_context_rows.py`.
- Materializes Apple App Store URLs through `https://itunes.apple.com/lookup?id=...`.
- Writes raw JSON snapshots to `Z:\FIN_Insight_Agent_data\raw_private\public_source_extended_materialization\app_marketplace`.
- Parses snapshots through `public_web_context_parser` into `app_store_marketplace_context` rows.
- Registered `app_store_rankings` as `runtime_ready_context` in `source_layer_capability_audit`, with `exact_value_authority_ready=false`.
- Added `app_marketplace_context_rows_v0_1.jsonl` to `RuntimeSourceContextStore` default public-source paths.
- Default output is capped to one structured lookup row per app to avoid generic JSON sentence noise entering Specialist context.

## Materialized Results

Command:

```powershell
python scripts\data_expansion\build_app_marketplace_context_rows.py --strict
```

Result:

- `attempted_count=11`
- `materialized_count=11`
- `failed_count=0`
- `context_row_count=11`
- `parser_backed_row_count=11`
- `ticker_count=5`: AAPL, GOOGL, META, MSFT, NFLX
- provider counts:
  - Apple App Store / iTunes Lookup: `11`
- structured context:
  - `app_store_marketplace_context=11`
- binding:
  - `issuer_mentioned_in_snapshot=11`
  - `product_mentioned_in_snapshot=11`

Runtime coverage:

- `app_rank_store_proxy=pass`
- `observed_row_count=11`
- `parser_row_count=11`
- `entity_bound_row_count=11`
- `specialist_visible_row_count=22`
- `exact_authority_violation_count=0`

Global source coverage after registry update:

- `requirement_count=65`
- `gap_requirement_count=31`
- `fail_requirement_count=0`
- `exact_authority_violation_count=0`

## Runtime Store Smoke

Ticker scope: AAPL, GOOGL, META, MSFT, NFLX.

`RuntimeSourceContextStore` selected `7` App Store rows under a public-source budget of `8` rows per ticker. Examples:

- AAPL: Apple Music
- GOOGL: Google Maps
- META: Facebook, Instagram, WhatsApp Messenger
- MSFT: Microsoft Teams
- NFLX: Netflix

Summary remained `public_exact_authority_violation_count=0`.

## Verification

```powershell
python -m py_compile scripts\data_expansion\build_app_marketplace_context_rows.py src\sec_agent\source_layer_capability_audit.py src\sec_agent\runtime_source_context_store.py
python -m pytest tests\test_app_marketplace_context_rows.py tests\test_developer_ecosystem_context_rows.py tests\test_runtime_source_context_store.py tests\test_source_coverage_gate.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python scripts\data_expansion\audit_source_coverage_gate.py --strict
```

Observed:

- Targeted tests: `19 passed`.
- Source-layer audit: `pass`, `expected_missing_count=8`, `runtime_ready_count=9`.
- Source coverage gate: `gap` as expected, with remaining unimplemented source families exposed and no exact-authority violations.

## Remaining Gaps

- Google Play and other app marketplaces are not wired to a first-party public lookup API in this tranche.
- App Store lookup rows are not rankings and not downloads; they are listing/rating/version metadata only.
- These rows cannot be used as app revenue, customer adoption, market share, sales, or moat evidence.
- Broader app-to-issuer resolver coverage and refresh cadence are still needed before treating this as broad app marketplace coverage.
