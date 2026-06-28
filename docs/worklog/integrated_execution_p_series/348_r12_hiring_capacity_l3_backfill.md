# 348 R12 Hiring Capacity L3 Backfill

Date: 2026-06-17

## Scope

SLR3c turns the hiring / capacity route from `JobPosting` JSON-LD parser smoke into a first real materialized L3 runtime source. This tranche uses official public ATS APIs from Greenhouse and Lever, then converts selected postings into standard `JobPosting` JSON-LD for the shared bounded public-web parser.

Rows remain proxy/context only: they can support hiring direction, role focus, geography, and capacity-signal context, but cannot support exact headcount, demand, order volume, revenue, production capacity, or margin claims.

## Changes

- Added `scripts/data_expansion/build_hiring_capacity_context_rows.py`.
- Added `tests/test_hiring_capacity_context_rows.py`.
- Registered `job_postings_hiring_signals` as `runtime_ready_context` in `source_layer_capability_audit`, with `exact_value_authority_ready=false`.
- Added `hiring_capacity_context_rows_v0_1.jsonl` to `RuntimeSourceContextStore` default public-source paths.
- The materializer supports:
  - Greenhouse board API.
  - Lever postings API.
  - role-focus selection against title / department / team / location.
  - transient fetch retry.
  - explicit no-headcount / no-demand / no-revenue boundary.

## Materialized Results

Command:

```powershell
python scripts\data_expansion\build_hiring_capacity_context_rows.py --strict
```

Result:

- `attempted_count=9`
- `materialized_count=9`
- `failed_count=0`
- `context_row_count=45`
- `parser_backed_row_count=45`
- `ticker_count=9`: ABNB, ASAN, COIN, DASH, DDOG, LYFT, NET, PLTR, RBLX
- provider counts:
  - Greenhouse: `40`
  - Lever: `5`
- structured context:
  - `hiring_signal_context=45`
- binding:
  - `issuer_mentioned_in_snapshot=45`
  - `product_mentioned_in_snapshot=45`

Runtime coverage:

- `hiring_capacity_proxy=pass`
- `observed_row_count=45`
- `parser_row_count=45`
- `entity_bound_row_count=45`
- `specialist_visible_row_count=135`
- `exact_authority_violation_count=0`

## Runtime Store Smoke

Ticker scope: DDOG, NET, PLTR, COIN, RBLX, DASH, ABNB, LYFT, ASAN.

`RuntimeSourceContextStore` selected `45` hiring rows and kept `public_exact_authority_violation_count=0`.

## Verification

```powershell
python -m py_compile scripts\data_expansion\build_hiring_capacity_context_rows.py src\sec_agent\source_layer_capability_audit.py src\sec_agent\runtime_source_context_store.py
python -m pytest tests\test_hiring_capacity_context_rows.py tests\test_app_marketplace_context_rows.py tests\test_developer_ecosystem_context_rows.py tests\test_runtime_source_context_store.py tests\test_source_coverage_gate.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python scripts\data_expansion\audit_source_coverage_gate.py --strict
```

Observed:

- Targeted tests: `23 passed` before the public-contract tranche.
- Source-layer audit after this and the public-contract tranche: `pass`, `expected_missing_count=6`, `runtime_ready_count=11`.
- Source coverage gate after this and the public-contract tranche: `66` requirements / `20` gaps / `0` fail / `0` exact-authority violations.

## Remaining Gaps

- Coverage is limited to the first set of official public ATS boards.
- Role taxonomy is lexical and source-bound; it is not a full occupation ontology or headcount estimator.
- These rows cannot be used as proof of true hiring volume, demand, revenue, product success, production capacity, or margin trajectory.
- Refresh cadence and broader ATS resolver coverage remain open.
