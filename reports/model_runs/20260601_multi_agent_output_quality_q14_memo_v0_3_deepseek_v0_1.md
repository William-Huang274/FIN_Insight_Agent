# Model Run: 20260601_multi_agent_output_quality_q14_memo_v0_3_deepseek_v0_1

## Summary

- Purpose: validate Q14 quality fixes for thesis synthesis, Memo Writer v0.3 compact projection, Specialist no-ref supported-claim salvage, unsupported cap, and source-gap precision on real sector-depth full-chain cases.
- Status: accepted for diagnostic Q14 quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, real DeepSeek `deepseek-v4-pro`, real retrieval path, CUDA BGE rerank metadata reported true.
- Safety: runtime credential was used only for process execution. Plaintext credential and raw LLM responses were not saved.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_real_llm_chain.py`
  - `scripts/audit_multi_agent_output_quality.py`
- Main changed surfaces:
  - `src/sec_agent/multi_agent_contracts.py`
  - `src/sec_agent/memo_llm.py`
  - `src/sec_agent/specialist_llm.py`
  - `src/sec_agent/agent_contracts.py`
  - `src/sec_agent/multi_agent_router.py`
  - `src/sec_agent/research_lead_llm.py`
  - `src/sec_agent/multi_agent_runtime.py`
  - `scripts/audit_multi_agent_output_quality.py`
  - `tests/test_multi_agent_memo_llm_repair.py`
  - `tests/test_multi_agent_specialist_llm.py`
- Command shape:

```text
<set DeepSeek credential in process env>
python scripts/eval_multi_agent_real_llm_chain.py --run-id <run_id> --case-id <sector_depth_case> --real-evidence-operators --bge-device cuda --strict
```

- Git state: dirty working tree with multi-agent source, tests, worklogs, and reports under active development; no commit was created for this run.
- Seeds: not applicable for remote LLM inference; deterministic validators and gates were used for pass/fail interpretation.

## Inputs

- Cases:
  - Banking: `ma_real_sector_banking_full_chain_real_retrieval`
  - Healthcare: `ma_real_sector_healthcare_full_chain_real_retrieval`
  - Energy / utilities: `ma_real_sector_energy_utilities_full_chain_real_retrieval`
- Candidate boundary:
  - SEC filings / 8-K evidence via real `sec_search_filings`.
  - BM25/ObjectBM25 candidate generation and BGE rerank.
  - Market, industry, and relationship rows only through role data views.
- Leakage guard:
  - Specialists can only cite bounded `known_evidence_refs`.
  - Missing-ref supported Specialist observations are dropped from supported output and moved to unsupported only when at least one valid supported observation remains.
  - Memo Writer sees only slot-balanced compact ClaimCards, not raw rows or tool calls.
  - Verifier keeps deterministic source-boundary enforcement.

## Results

| Case | Run id | Gate | Tool calls | Total tokens | Memo tokens | Verifier tokens | ClaimCards | Memo slots | Key flags |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Banking | `20260601_banking_full_chain_real_retrieval_quality_q14_memo_v0_3_single_deepseek_v0_1` | pass | 10 | 69,190 | 6,607 | 7,050 | supported 13 / unsupported 8 / synth thesis 1 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin` |
| Healthcare | `20260601_healthcare_full_chain_real_retrieval_quality_q14_memo_v0_3_specialist_salvage_single_deepseek_v0_1` | pass | 9 | 59,979 | 6,468 | 7,519 | supported 17 / unsupported 8 / synth thesis 0 | 5/5 | `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin` |
| Energy / utilities | `20260601_energy_utilities_full_chain_real_retrieval_quality_q14_memo_v0_3_specialist_salvage_single_deepseek_v0_1` | pass | 11 | 65,992 | 6,822 | 7,024 | supported 14 / unsupported 8 / synth thesis 0 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin` |

## Runtime Evidence

| Case | SEC calls | SEC rows | Runtime ledger rows | BGE CUDA | BGE candidates |
| --- | ---: | ---: | ---: | --- | ---: |
| Banking | 5 | 72 | 0 | true | 72 |
| Healthcare | 4 | 52 | 10 | true | 52 |
| Energy / utilities | 5 | 72 | 5 | true | 72 |

## Layer Observations

- Research Lead: all three cases routed to `deep_research` with valid activation and non-uniform priorities, so the old `deep_research_all_specialists_active` diagnostic no longer fires.
- Universe / Relationship: relationship lookup and validation passed in all three cases. Industry/Supply-Chain cited the expected packs: financial services, healthcare/life sciences, and energy/utilities.
- Evidence Operators: real SEC search, BGE rerank, market snapshot, industry snapshot, and relationship lookup were activated. Banking still has `runtime_ledger_rows=0`, so numeric banking memo conviction remains limited.
- Specialists: all final runs passed real evidence quality. Healthcare Risk completed in one attempt and `9,930` tokens versus Q12's `20,604` Risk-token outlier. Energy initially failed on one Risk supported observation without evidence refs; the final run passed after the safe salvage rule removed such observations from supported output.
- Judgment Aggregator: banking now synthesized a thesis ClaimCard and all three cases have `5/5` memo slots supported. Unsupported claims dropped to `8` per case from Q11-Q13's `12` per case.
- Memo Writer: v0.3 slot-balanced payload fixed the banking regression. Banking moved from an intermediate fallback run with `26,822` Memo Writer tokens to final `pass/1 attempt/6,607` tokens. All final Q14 cases are `pass/1 attempt`.
- Verifier: all final cases passed deterministic and LLM verifier checks; verifier tokens are lower than Q11-Q13.

## Comparison Against Q11-Q13

- Banking:
  - Q11: `66,555` total tokens, `9,124` memo tokens, `12` unsupported claims, `4/5` slots.
  - Q14 final: `69,190` total tokens, `6,607` memo tokens, `8` unsupported claims, `5/5` slots, synthesized thesis.
- Healthcare:
  - Q12: `73,842` total tokens, `9,735` memo tokens, Risk outlier around `20,604` tokens, `12` unsupported claims.
  - Q14 final: `59,979` total tokens, `6,468` memo tokens, Risk `9,930` tokens and one attempt, `8` unsupported claims.
- Energy / utilities:
  - Q13: `65,170` total tokens, `10,512` memo tokens, `8,897` verifier tokens, `12` unsupported claims, `4/5` slots, `source_gaps_without_second_pass`.
  - Q14 final: `65,992` total tokens, `6,822` memo tokens, `7,024` verifier tokens, `8` unsupported claims, `5/5` slots, no `source_gaps_without_second_pass`.

## Decision

- Proceed: Q14 fixes improve contract stability and token usefulness without loosening source-boundary gates.
- Keep as diagnostic, not final memo-quality acceptance:
  - Final memos still often use bounded/evidence-thin language.
  - Unsupported claims remain high at `8` per case.
  - Banking lacks runtime numeric ledger rows despite real context rows.
  - Total token cost remains high for banking and energy/utilities.

## Verification

```text
python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_contracts.py tests/test_multi_agent_output_quality_audit.py -q
result: 50 passed

python -m compileall src\sec_agent\specialist_llm.py src\sec_agent\memo_llm.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_memo_llm_repair.py
result: pass
```

## Caveats

- This report records summarized diagnostics only; raw model responses are not saved.
- The key remaining quality blocker is evidence depth and claim shaping, not route activation or tool execution.
- Banking's lack of runtime ledger rows means numeric banking claims remain weaker than healthcare and energy/utilities.
