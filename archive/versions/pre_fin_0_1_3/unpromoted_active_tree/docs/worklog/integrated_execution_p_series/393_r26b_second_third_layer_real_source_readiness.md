# R26b Second / Third Layer Real Source Readiness

Date: 2026-06-24

## Problem

The previous R26 acceptance gate proved that the second-layer and third-layer contracts, boundary checks, and manifests were internally consistent. It did not prove the stronger requirement: every company in the 600+ universe must have actual parser-backed second-layer and third-layer data-source rows that can be traced to source locators and parsed fields.

The user explicitly rejected a skeleton-only interpretation. This entry records the stricter correction.

## Decision

Add a separate strict gate that does not count planning artifacts as data sources.

Rejected as real sources:

- `company_product_slots` assignment rows.
- closeout rows.
- repair queues.
- URL seeds without parser-backed rows.
- source-route registry rows without materialized evidence.

Accepted as real sources only when the row has:

- `ticker`
- `evidence_ref` / `evidence_id` / `fact_id`
- `source_url` / `api_url` / `snapshot_url` / `raw_path` / citation URL
- parser or materialization marker
- `claim_boundary` / `authority_boundary`

## Work Completed

Added:

- `scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py`
- `tests/test_second_third_layer_real_source_readiness_gate.py`

Updated:

- `src/sec_agent/layer_acceptance_gates.py`
- `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`
- `docs/worklog/00_internal_master_checklist.md`
- `docs/worklog/README.md`

Generated:

- `data/manifests/second_third_layer_real_source_readiness_gate_summary_v0_1.json`
- `data/manifests/second_third_layer_real_source_readiness_company_rows_v0_1.jsonl`

## Results

Strict real-source readiness status: `pass`.

Company-level result:

- pass companies: `603/603`
- fail companies: `0`

Second layer:

- actual parser source company count: `603/603`
- missing companies: `0`

Second-layer source-file company coverage:

- `official_product_surface_context_rows_v0_1.jsonl`: `453`
- `official_product_catalog_context_rows_v0_1.jsonl`: `395`
- `sec_product_taxonomy_context_rows_v0_1.jsonl`: `445`
- `company_reported_product_operating_metric_runtime_rows_v0_1.jsonl`: `214`
- `non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl`: `11`
- `r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl`: `8`
- `r17_product_family_evidence_runtime_rows_v0_1.jsonl`: `5`
- `targeted_official_technology_document_context_rows_v0_1.jsonl`: `4`

Third layer:

- actual parser source company count: `603/603`
- exact financial basis company count: `603/603`
- missing companies: `0`

Third-layer source-file company coverage:

- `sec_financial_statement_metric_runtime_rows_v0_1.jsonl`: `587`
- `non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl`: `16`
- `capital_funding_ownership_context_rows_v0_1.jsonl`: `587`
- `sec_capital_market_event_context_rows_v0_1.jsonl`: `247`

## Verification

Commands:

```powershell
python scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py
python scripts/data_expansion/build_r26_second_third_layer_acceptance_gates.py
python -m pytest tests/test_second_third_layer_real_source_readiness_gate.py tests/test_r26_layer_acceptance_gates.py -q
python -m py_compile src/sec_agent/layer_acceptance_gates.py scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py
```

Results:

- real-source gate: `pass`
- R26 contract gate: `pass/pass/pass`
- tests: `4 passed`
- py_compile: pass

## Boundaries

This gate proves materialized parser-backed public-source rows exist for every company in L2 and L3. It does not prove:

- SKU revenue
- unit sales
- ASP
- market share
- sell-through
- backlog
- order value
- real-time fund flow

Those require stricter company disclosure, source-specific parser support, commercial trackers, or manual/commercial research workflows. They remain outside the exact authority boundary unless explicitly materialized later.
