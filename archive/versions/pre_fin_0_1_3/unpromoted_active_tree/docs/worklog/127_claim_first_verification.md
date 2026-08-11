# 127 - Claim-First Verification Layer

## Summary
- Date: 2026-05-21
- Purpose: implement the first claim-first synthesis guard from `123_model_gateway_intermediate_artifact_framework.md`.
- Status: local implementation and syntax checks complete; no cloud inference or API spend in this step.

## Work Completed
- Added `src/sec_agent/claim_verifier.py`.
  - Builds candidate claims from model `claim_candidates` / `claims` when present.
  - Falls back to deriving candidate claims from normalized `decision_drivers` and `key_points`.
  - Verifies each claim against:
    - current `Exact-Value Ledger` metric IDs;
    - current retrieved context/evidence IDs;
    - current `Judgment Plan` drivers when available.
  - Marks claims as:
    - `promoted`;
    - `downgraded`;
    - `rejected`.
  - Removes rejected key points / drivers from the rendered answer.
  - Downgrades over-broad claims before rendering.
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - Synthesis prompt now asks the model to form verifiable claim candidates.
  - Post-normalization path now runs claim-first verification before writing outputs.
  - `claim_verification.jsonl` now receives verified claim records from the claim-first layer.
  - Run debug includes `claim_first` summary counts.
  - Existing answer schema and post-gates remain compatible.

## Validation
- `python -m py_compile scripts/cloud/sec_agent_interactive.py src/sec_agent/project_inventory.py src/sec_agent/llm_gateway.py src/sec_agent/query_contract.py src/sec_agent/claim_verifier.py` passed.
- Local synthetic claim verification passed:
  - unsupported key point without metric/evidence IDs was removed;
  - supported key point with current metric/evidence IDs was retained;
  - report showed `candidate_count=3`, `promoted_count=2`, `rejected_count=1`.
- Local plan preview still passes after the claim verifier patch.

## Decision
The chain now has a first claim-first verification layer. This is not yet a fully separate two-call synthesis architecture, but it changes the promotion rule: model prose must survive claim-level support checks before user-facing rendering.

Next step should be a cloud/API A-B run:

1. DeepSeek planner + DeepSeek synthesis under the full constrained chain.
2. Qwen9B baseline under the same artifacts.
3. Compare claim-first promoted/downgraded/rejected counts, insight density, latency, and deterministic gates.
