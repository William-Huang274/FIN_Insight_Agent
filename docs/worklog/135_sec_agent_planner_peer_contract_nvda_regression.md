# 135 SEC Agent Planner Peer Contract NVDA Regression

## Prompt
- User asked why the NVDA memo said AMD/Intel financials were unavailable even though the project inventory contains AMD and INTC filings.
- Follow-up request: fix the issue and rerun the NVDA growth + competitor case.

## Root Cause
- The LLM planner call reused the final-answer JSON extractor. That extractor only accepts answer-like keys such as `summary`, `direct_answer`, and `what_changed`, so a valid Query Contract JSON could be rejected as `planner_returned_no_json_object`.
- After the false planner failure, the heuristic fallback produced only a generic financial-trend task, so retrieval, ledger, coverage, and gates faithfully executed an incomplete contract.
- Even after planner repair, BGE reranking could prune peer structured-object candidates out of the final context, leaving the runtime ledger with only NVDA rows.

## Changes
- Added planner-specific JSON extraction in `scripts/cloud/sec_agent_interactive.py`.
- Added `planner_trace.json` per interactive run so raw planner input/output and normalized contract summaries can be audited.
- Extended Query Contract decomposed tasks with `required_tickers` and `peer_tickers`, preserved through `src/sec_agent/query_contract.py`.
- Updated Evidence Coverage Matrix to honor explicit `required_tickers` / `peer_tickers` instead of inferring only from `focus_tickers`.
- Added heuristic peer-intent handling for prompts containing competitor/peer/同行/竞争对手 language.
- Updated numeric-check generation so peer tasks retrieve structured objects for required and peer companies.
- Added peer structured-object reservation in `scripts/run_sec_benchmark_eval.py` so BGE reranking cannot prune all peer financial candidates.
- Added synthesis constraints to keep unsupported named products/company names out of memo fields and to place peer metrics in `peer_readthrough`.

## Cloud Validation
- Environment: AutoDL/SeeTaCloud RTX 5090 host, `/root/autodl-tmp/FIN_Insight_Agent`.
- Command family: `USER_OUTPUT=1 PLANNER_MAX_TOKENS=2200 MAX_TOKENS=5000 TICKERS=ALL YEARS=2023,2024,2025 bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "<NVDA prompt>"`.
- Planner-only validation passed:
  - `planner=llm:deepseek:ok`
  - `task=company_comparison`
  - peer task generated with `AMD`, `INTC`, `AVGO`, `QCOM` and related semiconductor peers.

## NVDA Full-Chain Runs
- `20260522_140103_60a9e00112`: planner fixed, but peer rows still pruned by reranker; ledger only contained NVDA rows; coverage was partial.
- `20260522_141138_60a9e00112`: peer reservation added; coverage became complete; ledger included peer rows (`NVDA`, `AMD`, `AMAT`, `QCOM`); named-fact gate failed on unsupported product names.
- `20260522_141910_60a9e00112`: named product prompt constraint added; named-fact gate passed; answer-vs-Judgment-Plan failed because peer metrics appeared in `why_it_matters`.
- `20260522_142539_60a9e00112`: peer metrics constrained toward `peer_readthrough`; coverage remained complete, but named-fact gate failed on unsupported named product/SoC wording.

## Current Status
- The original AMD/Intel inventory bug is fixed at the planner/contract/retrieval level.
- The latest run no longer claims the project lacks AMD/INTC filings; it correctly treats unavailable values as current ledger/evidence-pack limitations.
- Coverage is now complete for the NVDA competitor contract, with peer evidence present in context and ledger.
- Remaining blocker is synthesis named-entity discipline: the model can still introduce unsupported product names such as H100/B200 or unsupported category tokens in prose.

## Follow-Up
- Add a deterministic named-entity sanitizer or verifier pass for memo fields before final rendering, scoped to evidence-supported company/product names.
- Consider splitting synthesis into two API calls: claim-candidate generation with evidence IDs, then final renderer over verified claims only.
- Improve Judgment Plan construction for peer-comparison tasks so peer metrics can be first-class plan drivers instead of conflicting with focus-company drivers.
