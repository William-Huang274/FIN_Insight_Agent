# 342 R12 Public Official API Context Projection

Date: 2026-06-16

## Scope

This checkpoint projects already materialized public official API normalized records into bounded runtime context rows.

It covers official API context only. It does not promote rows into company exact facts, market share, sales volume, approval success, commercial uptake, or durable moat claims.

## Changes

- Added `scripts/data_expansion/build_public_official_api_context_rows.py`.
- Added `tests/test_public_official_api_context_rows.py`.
- Tightened `src/sec_agent/source_coverage_gate.py` entity-binding semantics: when a requirement declares multiple binding kinds, every declared kind must be strongly bound.
- Added regression coverage so product-only or issuer-only rows do not satisfy `issuer+product` requirements.
- Fixed issuer resolver pollution for public API rows by preventing single-letter ticker aliases from participating in substring fuzzy matching.

## Runtime Materialization

Input:

- `Z:/FIN_Insight_Agent_data/processed_private/public_sources/public_source_normalized_materialized_v0_3/normalized_records.jsonl`

Generated outputs:

- `data/manifests/public_official_api_context_rows_v0_1.jsonl`
- `data/manifests/public_official_api_context_summary_v0_1.json`
- `data/manifests/public_official_api_context_coverage_gate_v0_1.json`

Observed result:

- `input_record_count=404`
- `context_row_count=150`
- `parser_backed_row_count=150`
- `issuer_bound_row_count=10`
- `product_bound_row_count=150`

Source coverage:

- `fred_api=12`
- `fred_graph_csv=50`
- `eia_open_data=9`
- `nhtsa_vpic_api=8`
- `fdic_bankfind_api=5`
- `clinicaltrials_api=5`
- `openfda_api=5`
- `cms_public_data=50`
- `openalex_api=5`
- `patentsview_api=1`

Runtime coverage smoke:

- `generic_public_research:macro_official_context=pass`
- `auto_mobility:auto_product_identity_context=pass`
- `healthcare_pharma_medtech:regulated_product_context=pass`
- `financials_banks:financial_regulatory_context=gap`
- `energy_utilities:energy_utility_context=gap`
- `semiconductors_hardware:technology_research_proxy=gap`

The three remaining gaps are real resolver gaps, not crawler/parser absence:

- FDIC institution/subsidiary -> listed issuer resolver
- EIA series/asset/service territory -> issuer/product exposure resolver
- OpenAlex/PatentsView topic/assignee/product -> issuer/product resolver

## Resolver Quality Finding

The first real run exposed a bad fuzzy resolver behavior: single-letter ticker alias `A` matched unrelated FDIC, CMS, ClinicalTrials, openFDA, and PatentsView rows to Agilent.

The resolver now:

- exact-matches normalized names first;
- allows fuzzy substring matching only when both sides are at least 6 characters;
- leaves unresolved regulatory entities as `regulatory_entity_unresolved`.

After the fix, issuer-bound rows are limited to plausible examples:

- NHTSA Tesla make/model rows -> `TSLA`
- ClinicalTrials sponsor `Amgen` -> `AMGN`
- openFDA sponsor `PFIZER` -> `PFE`

## Verification

Commands run:

```powershell
python -m py_compile src\sec_agent\source_coverage_gate.py scripts\data_expansion\build_public_official_api_context_rows.py
python -m pytest tests\test_public_official_api_context_rows.py tests\test_source_coverage_gate.py -q
python scripts\data_expansion\build_public_official_api_context_rows.py --strict
```

Results:

- projector/source-coverage tests: `11 passed`
- official API projector strict: `pass`

## Remaining Gap

This closes normalized official API context projection, not full source-specific adapter coverage.

Still open:

- deeper endpoint-specific queries beyond smoke snapshots;
- source-specific issuer/product/asset/topic resolvers;
- persistent runtime evidence graph / DB reader integration for these context rows;
- commercial tracker gaps for real market share, sales, prescription volume, registrations, sell-through, POS, app revenue, and consensus-style estimates.
