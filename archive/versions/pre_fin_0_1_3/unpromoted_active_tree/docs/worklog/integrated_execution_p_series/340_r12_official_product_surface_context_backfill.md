# 340 R12 Official Product Surface Context Backfill

Date: 2026-06-16

## Scope

This checkpoint converts the first materialized `company_product_pages` batch into runtime-visible, parser-backed bounded context rows.

It deliberately does not promote official product pages into company sales, product revenue, ASP, shipment, sell-through, inventory, or market-share authority.

## Changes

- Added `scripts/data_expansion/build_official_product_surface_context_rows.py`.
- Added `tests/test_official_product_surface_context_rows.py`.
- Extended `src/sec_agent/source_coverage_gate.py` so runtime parser rows can satisfy a source requirement even when the registry row is still `structured_not_promoted`.
- Extended `tests/test_source_coverage_gate.py` for the runtime parser-row override path.

## Runtime Materialization

Input:

- `Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages/company_product_pages.materialized.jsonl`

Generated outputs:

- `data/manifests/official_product_surface_context_rows_v0_1.jsonl`
- `data/manifests/official_product_surface_context_rows_summary_v0_1.json`
- `data/manifests/official_product_surface_runtime_coverage_gate_v0_1.json`

Observed result:

- `input_page_count=3`
- `tickers=AAPL, AMD, NVDA`
- `context_row_count=23`
- `parser_backed_row_count=23`
- `structured_context_types=official_product_taxonomy_context, product_spec_context`
- `official_product_surface` runtime-case coverage gate: `pass`

## Claim Boundary

Allowed:

- `official_product_surface`
- `product_taxonomy_context`
- `product_spec_context`

Forbidden:

- company sales
- market share
- product revenue
- ASP
- inventory
- sell-through
- shipment / order volume

Every generated row remains:

- `source_layer_id=L2`
- `runtime_ready_context=true`
- `exact_value_authority=false`
- `can_support_company_exact_fact=false`

## Verification

Commands run:

```powershell
python -m py_compile src\sec_agent\source_coverage_gate.py scripts\data_expansion\build_official_product_surface_context_rows.py scripts\data_expansion\audit_source_coverage_gate.py
python -m pytest tests\test_source_coverage_gate.py tests\test_official_product_surface_context_rows.py tests\test_public_web_gap_repair.py -q
python scripts\data_expansion\build_official_product_surface_context_rows.py --strict
python scripts\data_expansion\audit_source_coverage_gate.py --strict
git diff --check
```

Results:

- targeted tests: `22 passed`
- official product surface backfill strict: `pass`
- source coverage registry gate remains expected `gap`: `65` requirements / `35` gaps / `0` fail / `0` exact-authority violations
- whitespace check: pass

## Remaining Gap

This closes only the first official product surface runtime path.

Still open:

- larger company product page coverage
- source-specific official product page crawling and entity matching
- company-reported product operating metric parser
- product KPI period/unit/value binding
- L2/L3 large-scale backfill into persistent runtime evidence graph
- commercial tracker gaps for market share, sell-through, channel inventory, ASP, app revenue, POS, and consensus-style estimates
