# 124 - Query Contract Inventory-Aware Planner

## Summary
- Date: 2026-05-21
- Purpose: implement the first vNext step from `123_model_gateway_intermediate_artifact_framework.md`: make Query Contract planning aware of the current project source inventory.
- Status: local implementation and syntax checks complete; no cloud run in this step.

## User Requirement
The Query Contract planner must not plan in an abstract vacuum. Its system prompt should include the current project material inventory, including:

- available companies;
- industry/category coverage;
- available fiscal years;
- available filing/source types such as `10-K` or future `8-K`;
- current indexed SEC sections and retrieval assets.

The prompt must change automatically when the project data sources change, so the model does not drift outside the project boundary.

## Work Completed
- Added `src/sec_agent/project_inventory.py`.
  - Builds a manifest-derived `Project Source Inventory`.
  - Summarizes company count, filing count, years, filing types, source types, categories, selected company filings, and index profile.
  - Generates an `inventory_digest` for traceability.
  - Generates the system-prompt inventory block used by the Query Contract planner.
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - `plan` and run paths now build project inventory from the active manifest.
  - Query Contract now includes:
    - `project_inventory_digest`
    - `project_inventory` summary
    - `filing_types`
    - `scope.filing_types`
    - `analysis_axes`
    - `decomposed_tasks`
    - `forbidden_claims`
    - `planner_backend`
    - `planner_status`
  - Added `--query-planner heuristic|llm`.
  - Added model-assisted Query Contract planner path with an inventory-injected system prompt.
  - Added deterministic normalization and clamps:
    - tickers must come from selected manifest scope;
    - years must come from selected manifest scope;
    - filing types must come from selected manifest scope;
    - metric families are clamped to the project ontology;
    - model planner failures fall back to heuristic contracts with explicit `planner_status=fallback_after_error`.
  - Runs now write `project_inventory.json` beside `query_contract.json`.
- Updated `scripts/cloud/sec_agent_interactive.sh`.
  - Adds `--query-planner`.
  - DeepSeek commands default to `QUERY_PLANNER=llm`.
  - Local Qwen commands still default to heuristic planner unless explicitly overridden, avoiding an unnecessary Qwen load before BGE-first retrieval.

## Validation
- `python -m py_compile scripts/cloud/sec_agent_interactive.py src/sec_agent/project_inventory.py` passed.
- `bash -n scripts/cloud/sec_agent_interactive.sh` passed.
- Local `plan` preview passed for the full30 AI prompt.
- Local DeepSeek planner path without `DEEPSEEK_API_KEY` correctly fell back to heuristic and exposed the fallback status.
- Explicit ticker prompt smoke (`NVDA` vs `AMD`) now keeps full search scope but narrows `focus_tickers` to `AMD,NVDA` in fallback mode.

## Current Inventory Snapshot
- Inventory digest: `e413b6c9ccd0`
- Companies: 30
- Filings: 90
- Years: 2023, 2024, 2025
- Form/source types: `10-K`
- Categories include AI/GPU semiconductor, search/ads/cloud, ecommerce/cloud, software/cloud, cybersecurity, banking, pharma, industrial, consumer, energy, and semiconductor subsectors.

## Decision
This implements the first non-fallback piece of the vNext architecture: the Query Contract planner is now bounded by current project data instead of free-form model assumptions.

Next implementation should continue along the documented path:

1. factor the current chat-completion helper into a small provider-neutral `LLM Gateway`;
2. turn the current planner normalization into a dedicated Query Contract validator;
3. add claim-first synthesis and claim verification.
