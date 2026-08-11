# 345 R12 Official Product Surface Live Materialization

Date: 2026-06-16

## Scope

This checkpoint implements the first real SLR2 official product surface expansion beyond the original AAPL / NVDA / AMD materialized pages.

The objective is to make official company product pages available as bounded product taxonomy/spec context, while refusing blocked pages, thin shell pages, and exact-sales/share promotion.

## Changes

- Added `scripts/data_expansion/materialize_official_product_surface_pages.py`:
  - reads curated official issuer product URL profiles from `sec_agent.official_issuer_repair`;
  - enforces company-domain allowlist;
  - writes raw HTML and clean text to Z-drive materialization directories;
  - upserts `company_product_pages.materialized.jsonl`;
  - records attempt-level status in `official_product_surface_materialization_summary_v0_1.json`;
  - rejects blocked/access-denied/captcha pages and clean text shorter than the configured threshold;
  - supports `--prune-unusable-existing` to remove previously accepted blocked or too-short rows.
- Expanded `ISSUER_PROFILES` in `src/sec_agent/official_issuer_repair.py` with official product-surface seeds for:
  - cloud/SaaS: MSFT, AMZN, GOOGL, CRM, NOW;
  - auto: TSLA;
  - healthcare: LLY, PFE;
  - semis/hardware: AVGO, INTC, QCOM.
- Added `tests/test_official_product_surface_materializer.py` for:
  - allowed company-domain materialization;
  - non-company-domain blocking before fetch;
  - blocked-page rejection;
  - skip-existing behavior.

## Live Run

Commands:

- `python scripts\data_expansion\materialize_official_product_surface_pages.py --tickers ASML TSM NVO --max-urls-per-issuer 2 --timeout-s 12 --strict`
- `python scripts\data_expansion\materialize_official_product_surface_pages.py --tickers MSFT AMZN GOOGL TSLA LLY PFE CRM NOW AVGO INTC QCOM ASML TSM NVO --max-urls-per-issuer 2 --timeout-s 12 --prune-unusable-existing --strict`
- `python scripts\data_expansion\build_official_product_surface_context_rows.py --strict`

Effective materialized pages after pruning:

- `14` official product pages.
- `11` tickers: AAPL, AMD, AMZN, ASML, CRM, GOOGL, MSFT, NVDA, NVO, PFE, TSM.
- Runtime official product surface rows: `96`.
- Parser-backed rows: `96`.
- Entity-bound rows in official product surface coverage gate: `57`.
- Coverage gate: `official_product_surface=pass`.
- Exact authority violations: none; rows remain bounded product taxonomy/spec context only.

Failed or rejected live routes:

- AVGO: official products page returned only `8` clean-text chars.
- QCOM: official products page returned only `57` clean-text chars.
- MSFT Microsoft 365 page returned a blocked page.
- INTC: official product overview returned `403`.
- TSLA Model S / Model Y pages returned `403`.
- LLY medicines page returned `403` / `404` across attempts.
- NOW products page timed out.

These are source/access/parser gaps, not product-performance facts. They require alternate official URLs, page-specific adapters, API routes, or bounded source-gap reporting.

## Gates

Passed:

- `python -m py_compile scripts\data_expansion\materialize_official_product_surface_pages.py scripts\data_expansion\build_official_product_surface_context_rows.py`
- `python -m pytest tests\test_official_product_surface_materializer.py tests\test_official_product_surface_context_rows.py -q`
  - result: `5 passed`
- `python -m pytest tests\test_official_product_surface_materializer.py tests\test_official_product_surface_context_rows.py tests\test_public_web_gap_repair.py tests\test_runtime_bridge_contracts.py::test_official_issuer_repair_materializes_asml_sec_context_without_promoting_exact_fact -q`
  - result: `21 passed`
- `python scripts\data_expansion\audit_source_coverage_gate.py --strict`
  - result: `status=gap`, `65` requirements, `35` gap requirements, `0` fail, `0` exact-authority violations.
- Runtime source store smoke for MSFT / AMZN / GOOGL / CRM / PFE / ASML:
  - selected rows: `40`;
  - product evidence rows: `6`;
  - public source context rows: `34`;
  - public exact-authority violations: `0`.

## Remaining

- SLR2 is materially expanded but not complete: auto, healthcare, semis, and SaaS still need more robust official URL discovery and page-specific adapters.
- SLR3 should now move to real L3 proxy backfill for developer ecosystem, app marketplace, hiring, tender/order, ecommerce/channel/review, using the same reject-before-ingest discipline.
- SLR4 should use product surface materialization failures as targeted repair inputs rather than letting Memo Writer expand them into caveat-heavy prose.
