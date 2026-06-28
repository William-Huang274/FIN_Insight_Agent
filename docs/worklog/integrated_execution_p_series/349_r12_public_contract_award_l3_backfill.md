# 349 R12 Public Contract Award L3 Backfill

Date: 2026-06-17

## Scope

SLR3d turns the public tender / public order route from JSON-LD parser smoke into a first real materialized L3 runtime source. This tranche uses USAspending contract award search for public U.S. federal contract award records.

Rows remain bounded proxy/context only: they can support individual public award existence and agency relationship context, but cannot support total company orders, backlog, revenue, sales, demand, or market share claims.

## Changes

- Added `scripts/data_expansion/build_public_contract_award_context_rows.py`.
- Added `tests/test_public_contract_award_context_rows.py`.
- Registered `public_tenders_contracts_orders` as `runtime_ready_context` in `source_layer_capability_audit`, with `exact_value_authority_ready=false`.
- Added `public_contract_award_context_rows_v0_1.jsonl` to `RuntimeSourceContextStore` default public-source paths.
- Added `public_order_proxy` to the `software_saas` source coverage schema because govtech/cloud software issuers need this route.
- The materializer supports:
  - USAspending `spending_by_award` public API.
  - Contract award type codes `A/B/C/D`.
  - issuer + counterparty binding through recipient and awarding agency.
  - transient fetch retry.
  - explicit no-backlog / no-revenue / no-total-order boundary.

## Materialized Results

Command:

```powershell
python scripts\data_expansion\build_public_contract_award_context_rows.py --strict
```

Result:

- `attempted_count=6`
- `materialized_count=6`
- `failed_count=0`
- `context_row_count=18`
- `parser_backed_row_count=18`
- `ticker_count=6`: AMZN, IBM, LDOS, MSFT, ORCL, PLTR
- provider counts:
  - USAspending: `18`
- structured context:
  - `public_tender_contract_context=18`
- binding:
  - `issuer_mentioned_in_snapshot=18`
  - `counterparty_mentioned_in_snapshot=18`

Runtime coverage:

- `public_order_proxy=pass`
- `observed_row_count=18`
- `parser_row_count=18`
- `entity_bound_row_count=18`
- `specialist_visible_row_count=54`
- `exact_authority_violation_count=0`

## Runtime Store Smoke

Ticker scope: PLTR, MSFT, AMZN, ORCL, IBM, LDOS.

`RuntimeSourceContextStore` selected `14` public contract rows and kept `public_exact_authority_violation_count=0`.

## Verification

```powershell
python -m py_compile scripts\data_expansion\build_public_contract_award_context_rows.py scripts\data_expansion\build_hiring_capacity_context_rows.py src\sec_agent\source_layer_capability_audit.py src\sec_agent\runtime_source_context_store.py
python -m pytest tests\test_public_contract_award_context_rows.py tests\test_hiring_capacity_context_rows.py tests\test_app_marketplace_context_rows.py tests\test_developer_ecosystem_context_rows.py tests\test_runtime_source_context_store.py tests\test_source_coverage_gate.py -q
python scripts\data_expansion\audit_source_layer_capabilities.py --strict
python scripts\data_expansion\audit_source_coverage_gate.py --strict
```

Observed:

- Targeted tests: `27 passed`.
- Source-layer audit: `pass`, `expected_missing_count=6`, `runtime_ready_count=11`.
- Source coverage gate: `66` requirements / `20` gaps / `0` fail / `0` exact-authority violations.

## Remaining Gaps

- Coverage is limited to USAspending federal contract awards; non-U.S., state/local, procurement portals, and industry-specific award portals remain open.
- USAspending award rows are single-record public award context, not company-wide order, backlog, or sales authority.
- Product resolver is intentionally weak in this tranche; the accepted gate is issuer + counterparty, not product-level contract use.
- Refresh cadence, de-duplication against future contract feeds, and broader jurisdiction adapters remain open.
