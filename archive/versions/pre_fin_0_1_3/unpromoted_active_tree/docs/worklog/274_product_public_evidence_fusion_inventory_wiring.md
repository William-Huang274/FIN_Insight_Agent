# 274 Product/Public Evidence Fusion Inventory Wiring

Date: 2026-06-12

## Prompt

User asked to complete the first two runtime-prep steps before discussing Agent Graph and skill changes:

1. Wire the product evidence graph into source inventory / Evidence Fusion behind feature flags.
2. Wire public-source normalized rows into source inventory / Evidence Fusion behind feature flags.

## Decision

Do not change Agent Graph routing or role prompts yet. Add source-inventory blocks and Evidence Fusion row contracts so the next stage can pass `product_evidence_rows` and `public_source_context_rows` into `build_agent_data_view(...)` with boundaries already enforced.

The product graph has mixed authority, so only rows with `promotion_status=runtime_fact_allowed` and `exact_value_authority=true` may support product KPI facts. Product taxonomy, public context, review candidates, and gap rows remain context/gap rows.

Public source rows remain context/resolver/lead rows. Even if the upstream normalized snapshot has a stronger source label, the runtime bridge sets public normalized rows to `claim_scope=public_context_only` and `exact_value_authority=false`.

## Work Completed

- Extended `src/sec_agent/project_inventory.py` with:
  - `product_evidence_graph` inventory block;
  - `public_source_context` inventory block;
  - source-boundary entries for both;
  - `inventory_brief(...)` and `inventory_prompt(...)` rendering for both.
- Added CLI/env passthrough in `scripts/cloud/sec_agent_interactive.py` for product/public inventory paths without changing graph node execution.
- Extended `src/sec_agent/multi_agent_runtime.py` so Evidence Fusion / Specialist data views can consume:
  - `product_evidence_rows`;
  - `public_source_context_rows`.
- Added `scripts/data_expansion/build_evidence_fusion_context_rows.py` to normalize accepted product facts, product graph nodes/gaps, public inventory rows, and normalized public evidence rows into runtime-consumable row files.
- Added tests for inventory wiring, source-family bundle routing, and bridge-row authority boundaries.

## Results

Generated Evidence Fusion context rows:

- Product rows: `14,642`.
  - `runtime_fact_allowed`: `5,976`.
  - `runtime_context_taxonomy_only`: `566`.
  - `context_or_lead_available`: `5,009`.
  - `review_queue_not_runtime_fact`: `112`.
  - `gap_exposed_not_fallback`: `2,979`.
  - Exact-value authority rows: `5,976`.
- Public source context rows: `25`.
  - `demographic_or_macro_context_only`: `3`.
  - `public_context_only`: `22`.
  - Exact-value authority rows: `0`.

Outputs:

- `data/manifests/evidence_fusion_context_rows_v0_1/product_evidence_rows.jsonl`
- `data/manifests/evidence_fusion_context_rows_v0_1/public_source_context_rows.jsonl`
- `data/manifests/evidence_fusion_context_rows_v0_1/summary.json`

## Evidence

- `python -m py_compile src\sec_agent\project_inventory.py src\sec_agent\multi_agent_runtime.py scripts\cloud\sec_agent_interactive.py scripts\data_expansion\build_evidence_fusion_context_rows.py` -> pass.
- `python -m pytest tests\test_project_inventory_source_inventory.py tests\test_multi_agent_specialist_llm.py tests\test_evidence_fusion_context_rows.py` -> `46 passed`.

## Safety Notes

- No commercial tracker data was introduced.
- Public rows are explicitly non-authoritative for company product sales, market share, channel inventory, and profitability.
- Review candidates are present only as review/gap context and are not allowed to support product KPI facts.
- Agent Graph routing and skill prompts were intentionally not changed in this step.
