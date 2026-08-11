# 344 R12 Source-Specific Resolver Repair Gate

Date: 2026-06-16

## Scope

This checkpoint implements SLR1 first-batch resolver repair from document 15.

The goal is not to force current FDIC / EIA / OpenAlex / PatentsView rows to pass. The goal is to make issuer/product/topic binding deterministic, auditable, and fail-closed, so future live/backfill adapters can promote rows only when source fields support the binding.

## Changes

- Updated `scripts/data_expansion/build_public_official_api_context_rows.py`:
  - added `resolve_source_binding` with source-specific issuer candidates and product/topic candidates;
  - added resolver output fields: `source_specific_resolver`, `resolver_status`, `resolver_reason`, `source_entity_role`;
  - added entity-binding matched terms for issuer/product/topic;
  - kept all official API rows as bounded context/proxy with `exact_value_authority=false`;
  - added summary counts for resolver status and reason.
- Updated `src/sec_agent/source_coverage_gate.py`:
  - added `technology_topic_bound` as a strong product/topic binding status for technology proxy requirements;
  - issuer+product requirements still require both sides, so topic-only rows do not pass.
- Expanded tests in `tests/test_public_official_api_context_rows.py`:
  - FDIC holding company / bank name can bind to JPM for `financial_regulatory_context`;
  - EIA utility rows can bind issuer+driver and pass `energy_utility_context`;
  - EIA generic degree-day rows remain `driver_only` and fail issuer binding;
  - OpenAlex institution+topic can pass technology proxy; topic-only remains a gap;
  - single-letter ticker aliases still do not fuzzy-match unrelated rows.

## Gates

Passed:

- `python -m py_compile scripts\data_expansion\build_public_official_api_context_rows.py src\sec_agent\source_coverage_gate.py`
- `python -m pytest tests\test_public_official_api_context_rows.py tests\test_source_coverage_gate.py -q`
  - result: `16 passed`
- `python scripts\data_expansion\build_public_official_api_context_rows.py --strict`
  - result: `150` parser-backed rows;
  - `macro_official_context=pass`, `auto_product_identity_context=pass`, `regulated_product_context=pass`;
  - `financial_regulatory_context=gap`, `energy_utility_context=gap`, `technology_research_proxy=gap`;
  - resolver status distribution: `issuer_product_bound=10`, `macro_driver_only=62`, `product_bound_issuer_unresolved=58`, `driver_only=9`, `topic_only=6`, `unresolved=5`.
- `python scripts\data_expansion\audit_source_coverage_gate.py --strict`
  - result: `status=gap`, `65` requirements, `35` gap requirements, `0` fail, `0` exact-authority violations.

## Findings

The current real normalized public API snapshot does not contain enough fields to resolve the remaining three official API gaps:

- FDIC rows are five Wisconsin local institution samples without listed bank-holding-company linkage.
- EIA rows are regional cooling degree-day macro series without utility, operator, plant, asset, or issuer fields.
- OpenAlex rows are broad semiconductor topic-search works without issuer / assignee / institution binding.
- PatentsView currently materializes USPTO migration/access metadata only, not patent assignee rows.

So SLR1 is now a working resolver contract and diagnostic gate, but the unresolved runtime rows require targeted live/backfill acquisition rather than looser resolver matching.

## Remaining

- SLR2 official product surface expansion should now add more real company product/spec rows beyond AAPL/NVDA/AMD.
- SLR3 public proxy backfill should fetch real rows with bindable issuer/product fields for developer ecosystem, app marketplace, hiring, tender/order, ecommerce/channel/review, plus improved FDIC/EIA/OpenAlex/PatentsView live routes where feasible.
- SLR4 Research Lead targeted repair should consume `resolver_status` / `resolver_reason` to decide whether a gap is retrievable by source acquisition, resolver mapping, or commercial data only.
