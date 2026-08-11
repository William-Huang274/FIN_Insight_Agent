# Model Run: 20260522_sec_agent_banking_metric_ixbrl_jpm_rerun

## Summary
- Purpose: Validate the bank-specific ontology, iXBRL structured extraction, and runtime ledger selection fix for the JPM banking-quality prompt.
- Status: completed for bank metric coverage; one residual named-fact citation-format issue remains.
- Run type: structured-object rebuild + retrieval/index rebuild + free-query API memo inference + deterministic audit.
- Timestamp: 2026-05-22.
- Environment: cloud RTX 5090, `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command
- Main branch: `codex/api-model-call-architecture`.
- Rebuild entry points:
  - `scripts/build_structured_objects.py`
  - `scripts/build_object_bm25_index.py`
- Inference entry point: `scripts/cloud/sec_agent_interactive.sh`.
- Prompt: `JPM 这几年净利息收入和信用风险变化说明银行业务质量怎么样？`
- Inference command profile: `USER_OUTPUT=1`, `QUERY_PLANNER=heuristic`, `SYNTHESIS_PROFILE=api_memo_v1`, `MAX_TOKENS=5200`, `TICKERS=ALL`, `YEARS=2023,2024,2025`, `BGE_DEVICE=cuda`, `ask-deepseek`.
- API key was passed through environment variable only and was not written to files.

## Inputs
- Evidence source: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Raw SEC filing source: `data/raw_private/sec/...`.
- Structured output prefix: `sec_tech_10k`.
- Retrieval boundary: current 30-company SEC universe, 2023-2025 10-K evidence.

## Structured Object Rebuild
- `evidence_count=8461`
- `table_count=9030`
- `metric_count=184784`
- `claim_count=64141`
- Metric extraction method counts:
  - `table_row_heuristic=178943`
  - `sentence_heuristic=5739`
  - `banking_ixbrl_fact_heuristic=102`
- JPM metric count after rebuild: `227`.
- Object BM25 records after rebuild: `257955`.

## Inference Outputs
- Artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_161702_914dee0e50`.
- Runtime ledger rows: `24`.
- Context rows: `120`.
- Elapsed: `220.45 sec`.
- Main model answer now states that JPM net interest income rose while credit risk indicators also increased but remained manageable under the available SEC evidence.

## Representative Ledger Values
- Net interest income: 2023 `89,267`, 2024 `92,583`, 2025 `95,443`.
- Provision for credit losses: 2023 `9,320`, 2024 `10,678`, 2025 `14,212`.
- Net charge-offs: 2023 `6,209`, 2024 `8,638`, 2025 `9,849`.
- Loans: 2023 `1,323,706`, 2024 `1,347,988`, 2025 `1,493,429`.
- Deposits: 2023 `2,400,688`, 2024 `2,406,032`, 2025 `2,559,320`.
- Allowance for credit losses: 2023 `22,420`, 2024 `24,345`, 2025 `25,765`.
- Common Equity Tier 1 capital ratio: 2023 `15.0%`, 2024 `15.7%`, 2025 `14.6%`.

## Results
- Evidence Coverage Matrix:
  - `complete=True`
  - `primary_complete=True`
  - `answer_status=complete`
  - support `{'medium': 1, 'strong': 2}`
- Deterministic gates:
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`
  - `metric_source_grounding_gate_pass=true`
  - `ledger_unit_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `caveat_claim_gate_pass=true`
  - `v2_semantic_contract_gate_pass=true`
  - `answer_vs_judgment_plan_gate_pass=true`
  - `named_fact_gate_pass=false`

## Interpretation
- The main upstream gap for JPM banking prompts is fixed: bank-specific numeric facts now enter structured objects, retrieval, coverage, and runtime exact-value ledger.
- The remaining gate failure is not caused by missing JPM bank metrics. It is caused by a memo narrative field naming `Common Equity Tier` with metric IDs but without an evidence ID line that satisfies the named-fact gate.
- This should be handled in the citation propagation or named-fact verifier path, not by adding another banking ontology fallback.

## Follow-Up
- Ensure capital-ratio ledger-backed facts carry evidence IDs into memo `why_it_matters` and related fields.
- Add a small iXBRL parsing fixture for banking facts and context-year resolution.
- Expand the bank coverage test once additional banking SEC issuers are added to the universe.
