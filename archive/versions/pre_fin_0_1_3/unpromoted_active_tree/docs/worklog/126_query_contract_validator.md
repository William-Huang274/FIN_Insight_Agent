# 126 - Query Contract Validator

## Summary
- Date: 2026-05-21
- Purpose: implement the third vNext step from `123_model_gateway_intermediate_artifact_framework.md`: make Query Contract validation a standalone deterministic stage.
- Status: local implementation and syntax checks complete; no cloud inference or API spend in this step.

## Work Completed
- Added `src/sec_agent/query_contract.py`.
  - Centralizes Query Contract constants and validation:
    - allowed `task_type`;
    - metric-family ontology;
    - selected ticker/year/form clamps;
    - decomposed task normalization;
    - required caveat insertion;
    - forbidden-claim insertion;
    - evidence gap normalization;
    - validation report generation.
  - Returns a normalized contract plus `query_contract_validation`.
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - Heuristic contracts and LLM planner contracts now both pass through the standalone validator.
  - Invalid contracts now fail fast before retrieval instead of drifting into later stages.
  - Terminal plan preview now prints `validation=pass|fail`.
  - Explicit company prompts keep full search scope but narrow `focus_tickers`, for example `JPM,V` or `AMD,NVDA`.

## Validation
- `python -m py_compile scripts/cloud/sec_agent_interactive.py src/sec_agent/project_inventory.py src/sec_agent/llm_gateway.py src/sec_agent/query_contract.py` passed.
- Local plan previews passed:
  - full30 AI industry prompt: `validation=pass`, focus is AI-relevant 13-company subset.
  - `NVDA` vs `AMD`: `validation=pass`, focus narrows to `AMD,NVDA`.
  - `JPM` vs `V`: `validation=pass`, focus narrows to `JPM,V`.
- `bash -n scripts/cloud/sec_agent_interactive.sh` passed in the previous gateway validation and remains unchanged by this validator patch.

## Decision
Query Contract is now a validated artifact rather than just planner output. This keeps the implementation aligned with the vNext architecture: model output can propose a contract, but deterministic validation decides whether it can enter retrieval, ledger, Judgment Plan, and synthesis.

Next step should be claim-first synthesis: ask the model for structured claims first, verify each claim against `Judgment Plan`, `Evidence Pack`, and `Exact-Value Ledger`, then render only verified/downgraded claims.
