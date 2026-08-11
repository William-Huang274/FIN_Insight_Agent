# 350 R12 Channel Offer Review L3 Backfill

Date: 2026-06-17

## Scope

SLR3e turns the ecommerce / channel offer / platform review route from parser smoke into a first real materialized L3 runtime source.

This tranche uses CDW public search and product pages because common major consumer ecommerce sites probed during smoke returned robot pages, `403`, or timeouts. CDW rows remain bounded proxy/context only: they can support public listing, SKU/configuration, quoted price, availability or lead-time, and platform review/rating context, but cannot support ASP, sell-through, channel inventory, sales volume, revenue, demand, market share, or moat claims.

## Changes

- Added `scripts/data_expansion/build_channel_offer_context_rows.py`.
- Added `tests/test_channel_offer_context_rows.py`.
- Extended `src/sec_agent/public_web_context_parser.py` with commerce microdata / CDW tag-data parsing:
  - `window.cdwTagManagementData`
  - `itemprop=offers`
  - `price`, `priceCurrency`, `availability`
  - `total_review_count`, `average_overall_rating`
- Registered `channel_pricing_quotations` and `platform_reviews_rankings_downloads` as `runtime_ready_context` in `source_layer_capability_audit`, with `exact_value_authority_ready=false`.
- Added `channel_offer_context_rows_v0_1.jsonl` to `RuntimeSourceContextStore` default public-source paths.
- Hardened product resolver:
  - issuer binding for CDW pages must come from brand/root-brand fields, not product-title mentions.
  - product binding must come from product name/title, not broad category fields.
  - third-party compatible accessories such as Kingston, Axiom, or Total Micro rows that mention Dell/PowerEdge are rejected as `skipped_product_mismatch`.

## Materialized Results

Command:

```powershell
python scripts\data_expansion\build_channel_offer_context_rows.py --strict --timeout-s 15 --fetch-retries 1 --max-products-per-probe 2 --max-search-links 6
```

Result:

- `attempted_count=22`
- `materialized_count=11`
- `failed_count=0`
- `context_row_count=12`
- `parser_backed_row_count=12`
- `ticker_count=6`: AAPL, DELL, HPQ, LNVGY, MSFT, NVDA
- structured context:
  - `channel_offer_context=11`
  - `platform_review_ranking_context=1`
- source ids:
  - `channel_pricing_quotations=11`
  - `platform_reviews_rankings_downloads=1`
- binding:
  - `issuer_mentioned_in_snapshot=12`
  - `product_mentioned_in_snapshot=12`

Runtime coverage:

- `channel_offer_proxy=pass`
  - `observed_row_count=11`
  - `parser_row_count=11`
  - `entity_bound_row_count=11`
  - `specialist_visible_row_count=22`
- `platform_review_proxy=pass`
  - `observed_row_count=1`
  - `parser_row_count=1`
  - `entity_bound_row_count=1`
  - `specialist_visible_row_count=3`
- `coverage_gate_status=pass`
- `exact_authority_violation_count=0`

## Skipped Rows

The live CDW search returned several adjacent but non-issuer products. These were intentionally rejected instead of being weakly bound:

- Kingston DDR4 memory in DELL PowerEdge search.
- Axiom DDR5 / DDR4 modules in DELL PowerEdge search.
- Total Micro memory titled with Dell PowerEdge compatibility but branded `Total Micro`.

These are not company product-performance rows for DELL. They can be treated as channel ecosystem leads in a future accessory/compatibility model, but not as issuer product rows in the current Product Specialist path.

## Runtime Store Smoke

Ticker scope: AAPL, MSFT, DELL, HPQ, NVDA, LNVGY.

`RuntimeSourceContextStore` selected `9` channel/review rows under the current per-ticker public-source budget. The full manifest remains `12` rows; budgeted runtime selection is expected and does not change the persisted manifest.

## Verification

```powershell
python -m pytest tests\test_channel_offer_context_rows.py tests\test_public_web_gap_repair.py::test_public_web_repair_parses_channel_offer_jsonld_without_sell_through_authority tests\test_runtime_source_context_store.py tests\test_source_layer_capability_audit.py tests\test_source_coverage_gate.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python scripts\data_expansion\audit_source_coverage_gate.py --strict
```

Observed:

- Targeted tests: `17 passed` before resolver hardening; dedicated channel tests after hardening: `5 passed`.
- Source-layer audit: `pass`, `expected_missing_count=4`, `runtime_ready_count=13`.
- Source coverage gate: `66` requirements / `13` gaps / `0` fail / `0` exact-authority violations.

## Remaining Gaps

- CDW is a first real public reseller route, not full ecommerce coverage.
- Amazon, BestBuy, Walmart, B&H, Newegg and similar major sites returned robot pages, `403`, or timeouts in smoke probes; keep them as compliant-access / anti-bot source gaps until a lawful stable route exists.
- Google Play and other marketplace ranking/download metadata remain separate source gaps.
- CDW prices can be quoted as `0` for some NVIDIA products while still exposing lead-time / availability; these rows are kept as availability/configuration proxy, not price authority.
- No channel rows may be promoted to ASP, sell-through, channel inventory, revenue, demand, market share, or sales evidence.
