# 346 R12 Developer Ecosystem L3 Backfill

Date: 2026-06-17

## Scope

SLR3a turns the GitHub / npm / PyPI / HuggingFace developer-ecosystem route from URL-derived parser smoke into a first real materialized L3 runtime source. The output remains bounded proxy/context only: it can support developer activity, package, repository, or model-attention context, but cannot support revenue, market share, sales volume, customer adoption, or moat proof.

## Changes

- Added `scripts/data_expansion/build_developer_ecosystem_context_rows.py`.
- Materializes public developer-source APIs from official public endpoints:
  - GitHub repos API.
  - npm registry JSON.
  - PyPI package JSON.
  - HuggingFace model API.
- Writes raw JSON snapshots to `Z:\FIN_Insight_Agent_data\raw_private\public_source_extended_materialization\developer_ecosystem`.
- Parses snapshots through `public_web_context_parser` into `developer_ecosystem_context`, `developer_package_context`, and `market_proxy_context` rows.
- Added transient fetch retry for network truncation such as npm `IncompleteRead`; repeated failure remains visible as a failed attempt and is not hidden by cache fallback.
- Registered `developer_ecosystem_github_npm_pypi_huggingface` as `runtime_ready_context` in `source_layer_capability_audit`, with `exact_value_authority_ready=false`.
- Added `developer_ecosystem_context_rows_v0_1.jsonl` to `RuntimeSourceContextStore` default public-source paths.
- Fixed runtime public-source selection to preserve source diversity under per-ticker budgets, so official product pages cannot starve developer ecosystem rows.

## Materialized Results

Command:

```powershell
python scripts\data_expansion\build_developer_ecosystem_context_rows.py --strict
```

Result:

- `attempted_count=10`
- `materialized_count=10`
- `failed_count=0`
- `context_row_count=13`
- `parser_backed_row_count=13`
- `ticker_count=5`: AMZN, CRM, GOOGL, MSFT, NVDA
- provider counts:
  - GitHub: `5`
  - npm: `4`
  - PyPI: `3`
  - HuggingFace: `1`
- binding:
  - `issuer_mentioned_in_snapshot=13`
  - `product_mentioned_in_snapshot=13`

Runtime coverage:

- `developer_ecosystem_proxy=pass`
- `observed_row_count=13`
- `parser_row_count=13`
- `entity_bound_row_count=13`
- `specialist_visible_row_count=26`
- `exact_authority_violation_count=0`

Global source coverage after registry update:

- `requirement_count=65`
- `gap_requirement_count=33`
- `fail_requirement_count=0`
- `exact_authority_violation_count=0`

## Runtime Store Smoke

Ticker scope: MSFT, AMZN, GOOGL, NVDA, CRM.

Selected public-source rows now include developer ecosystem rows for:

- AMZN: `aws/aws-sdk-js-v3`
- CRM: `forcedotcom/cli`
- GOOGL: `google-cloud-aiplatform`
- MSFT: `@azure/identity`
- NVDA: `NVIDIA-NeMo/NeMo`

This confirms the runtime source store can expose L3 developer rows alongside L2 official product rows under a bounded per-ticker public-source budget.

## Verification

```powershell
python -m py_compile scripts\data_expansion\build_developer_ecosystem_context_rows.py src\sec_agent\runtime_source_context_store.py src\sec_agent\source_layer_capability_audit.py
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python scripts\data_expansion\audit_source_coverage_gate.py --strict
python -m pytest tests\test_developer_ecosystem_context_rows.py tests\test_runtime_source_context_store.py tests\test_source_coverage_gate.py -q
```

Observed:

- Source-layer audit: `pass`, `expected_missing_count=9`, `runtime_ready_count=8`.
- Source coverage gate: `gap` as expected, with remaining unimplemented source families exposed and no exact-authority violations.
- Targeted tests: `14 passed`.

## Remaining Gaps

- The current first tranche is hand-seeded for five software / cloud / AI infrastructure issuers. It is not yet a broad issuer-project resolver.
- Developer ecosystem rows are L3 directional context only; they must not be used as proof of revenue, customer adoption, product sales, market share, or durable moat.
- App Store / marketplace, hiring, tenders/orders, ecommerce/channel, and platform reviews still need real backfill beyond fixture or URL-pattern smoke.
- Runtime rows are still manifest-backed; full SQL/ObjectStore persistence remains part of the later D-series hardening.
