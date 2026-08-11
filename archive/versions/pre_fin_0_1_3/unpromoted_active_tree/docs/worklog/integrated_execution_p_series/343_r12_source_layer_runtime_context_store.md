# 343 R12 Source-Layer Runtime Context Store

Date: 2026-06-16

## Scope

This checkpoint implements the first step of the next source-layer plan in document 15: SLR0 Runtime Evidence Graph / DB Reader integration.

The goal is to stop leaving newly generated source-layer rows as standalone manifests only. Generated L1 product KPI rows and L2 bounded context rows must be selectable by runtime state, evidence fusion, and Specialist data views before any full-chain case is rerun.

## Changes

- Updated `docs/architecture/agent_graph_vnext/15_source_layer_capability_and_analyst_first_optimization.zh-CN.md`:
  - fixed duplicate numbering in the unfinished section;
  - added SLR0-SLR5 execution plan with gates for runtime context store, resolver repair, official product surface expansion, L3 public proxy backfill, Research Lead targeted repair, and memo/eval regression.
- Added `src/sec_agent/runtime_source_context_store.py`:
  - reads default generated manifests or explicit state/env paths;
  - selects rows by `focus_tickers` / `search_scope_tickers`;
  - routes L1 `company_product_evidence_graph` rows to `product_evidence_rows`;
  - routes L2/L3 official/API/proxy context rows to `public_source_context_rows`;
  - keeps unbound macro/official API rows budgeted by source/metric latest row to avoid dumping full FRED/EIA histories into prompts;
  - preserves `exact_value_authority=false` boundary for public/live context rows and reports any public exact-authority violations.
- Updated LangGraph first-pass merge:
  - `_node_execute_evidence_operators` now merges `product_evidence_rows` and `public_source_context_rows` from operator results in the first pass, not only in second pass.
  - explicit `multi_agent_context.runtime_source_context.enabled=true` or env flag can attach generated manifest rows before evidence fusion.
  - `runtime_source_context_store` is now part of graph state/checkpoint keys for auditability.
- Added deterministic tests:
  - runtime store filtering, dedupe, ticker budgeting, latest unbound macro selection, and boundary summary;
  - graph first-pass merge of product/public rows;
  - graph state-config attach of runtime source context store and Product Specialist visibility.

## Gates

Passed:

- `python -m py_compile src\sec_agent\runtime_source_context_store.py src\sec_agent\langgraph_orchestrator.py`
- `python -m pytest tests\test_runtime_source_context_store.py tests\test_multi_agent_langgraph_routing.py::test_multi_agent_graph_first_pass_merges_product_and_public_source_rows tests\test_multi_agent_langgraph_routing.py::test_multi_agent_graph_attaches_runtime_source_context_store_from_state_config -q`
  - result: `4 passed`
- `python -m pytest tests\test_runtime_source_context_store.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_specialist_llm.py::test_agent_data_view_routes_product_evidence_and_public_source_context_rows tests\test_product_spec_pack.py tests\test_source_coverage_gate.py tests\test_official_product_surface_context_rows.py tests\test_company_reported_product_operating_metric_runtime_rows.py tests\test_public_official_api_context_rows.py -q`
  - result: `49 passed`
- `python scripts\data_expansion\audit_source_coverage_gate.py --strict`
  - result: `status=gap`, `65` requirements, `35` gap requirements, `0` fail, `0` exact-authority violations.
- Default manifest runtime store smoke for `AAPL,NVDA`:
  - input rows: `6,149`
  - selected rows: `23`
  - product evidence rows: `4`
  - public/source context rows: `19`
  - public exact-authority violations: `0`
- `git diff --check`

Not run in this checkpoint:

- DeepSeek / full-chain Workbench cases.
- Full source coverage gate rerun.
- Full pytest suite.

## Remaining

- SLR1 resolver repair still pending: FDIC, EIA, NHTSA, ClinicalTrials/openFDA/CMS, OpenAlex/PatentsView.
- SLR2 official product page expansion still only has the current AAPL/NVDA/AMD first batch.
- SLR3 true L3 backfill still needs real-source coverage for developer ecosystem, app marketplace, hiring, tender/order, ecommerce/channel/review.
- Research Lead targeted repair must now consume `runtime_source_context_store.summary`, source coverage gate output, and Specialist row distribution to avoid exposing retrievable gaps too early.
