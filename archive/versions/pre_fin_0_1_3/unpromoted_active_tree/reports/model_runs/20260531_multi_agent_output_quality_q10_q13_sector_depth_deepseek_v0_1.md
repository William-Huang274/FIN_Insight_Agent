# Model Run: 20260531_multi_agent_output_quality_q10_q13_sector_depth_deepseek_v0_1

## Summary

- Purpose: validate the Q10 multi-agent quality/cost fixes and run real sector-depth full-chain cases from Research Lead through retrieval, Specialists, Judgment Aggregator, Memo Writer, Verifier, and renderer.
- Status: accepted for diagnostic sector-depth quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-05-31.
- Environment: local Windows workspace, real DeepSeek `deepseek-v4-pro`, real retrieval path, CUDA BGE rerank metadata reported true in the checked full-chain runs.
- Safety: runtime credential was supplied only through process environment; plaintext credential and raw model responses were not saved.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_real_llm_chain.py`
  - `scripts/audit_multi_agent_output_quality.py`
- Main changed surfaces:
  - `src/sec_agent/specialist_llm.py`
  - `src/sec_agent/memo_llm.py`
  - `src/sec_agent/multi_agent_runtime.py`
  - `tests/test_multi_agent_specialist_llm.py`
  - `tests/test_multi_agent_memo_llm_repair.py`
- Command shape:

```text
<set DeepSeek credential in process env>
python scripts/eval_multi_agent_real_llm_chain.py --provider deepseek --model deepseek-v4-pro --run-id <case_run_id> --cases <sector-depth case> --real-retrieval --require-real-specialist-quality
python scripts/audit_multi_agent_output_quality.py --run-id <case_run_id>
```

- Git state: dirty working tree with multi-agent source, tests, worklogs, and reports under active development; no commit was created for this run.
- Seeds: not applicable for remote LLM inference; deterministic validators and gates were used for pass/fail interpretation.

## Inputs

- Data profile: sector-depth multi-agent full-chain eval cases with real retrieval and bounded evidence rows.
- Cases:
  - AI infrastructure: `ma_real_sector_ai_infra_full_chain_real_retrieval`
  - Banking: `ma_real_sector_banking_full_chain_real_retrieval`
  - Healthcare: `ma_real_sector_healthcare_full_chain_real_retrieval`
  - Energy / utilities: `ma_real_sector_energy_utilities_full_chain_real_retrieval`
- Candidate boundary:
  - SEC filings / 8-K evidence via real `sec_search_filings`.
  - ObjectBM25 and BM25 candidate generation.
  - BGE rerank.
  - Market, industry, relationship rows only through registered role data views.
- Leakage guard:
  - Specialists can only cite evidence refs passed in their bounded input.
  - Risk Specialist no longer receives `relationship_graph` rows.
  - Industry/Supply-Chain Specialist must cite expected relationship packs for sector-depth / relationship cases.
  - Memo Writer only sees compact verified judgment plan, not raw tool outputs.
  - Verifier sees compact memo / evidence inventory and blocks unsupported leakage.

## Q10 Changes Under Test

- Memo Writer repair path uses compact-only payload for truncation, parse, or deterministic failures.
- Memo Writer first pass has tighter memo-ready output budget.
- Verifier uses compact inventory rather than full judgment/data-view payload.
- Specialist row summaries use source-family-aware character budgets.
- Fundamental deep-research budget is limited to 2-4 supported ClaimCards.
- Risk data view excludes relationship graph rows to align with the role/source matrix.
- Model-call aggregation now preserves finish reasons for future route diagnostics.

## Results

| Case | Run id | Gate | Tool calls | Total tokens | Memo tokens | Verifier tokens | ClaimCard stats | Memo slots | Key flags |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| AI infra | `20260531_ai_infra_full_chain_real_retrieval_quality_q10_single_deepseek_v0_1` | pass | 9 | 68,176 | 10,505 | 9,494 | supported 17 / high 10 / unsupported 12 / conflicts 5 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `deep_research_all_specialists_active` |
| Banking | `20260531_banking_full_chain_real_retrieval_quality_q11_single_deepseek_v0_1` | pass | 10 | 66,555 | 9,124 | 7,214 | supported 17 / high 11 / unsupported 12 / conflicts 4 | 4/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin`, `deep_research_all_specialists_active` |
| Healthcare | `20260531_healthcare_full_chain_real_retrieval_quality_q12_single_deepseek_v0_1` | pass | 8 | 73,842 | 9,735 | 8,257 | supported 18 / high 11 / unsupported 12 / conflicts 3 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `deep_research_all_specialists_active` |
| Energy / utilities | `20260531_energy_utilities_full_chain_real_retrieval_quality_q13_single_deepseek_v0_1` | pass | 9 | 65,170 | 10,512 | 8,897 | supported 18 / high 12 / unsupported 12 / conflicts 3 | 4/5 | `high_total_token_cost`, `source_gaps_without_second_pass`, `many_unsupported_specialist_claims`, `deep_research_all_specialists_active` |

## Layer Observations

- Research Lead: correctly routes sector-depth cases, but still activates all four Specialists for these diagnostic cases. This is safe but expensive.
- Universe / Relationship: expected-pack propagation and semantic pack filtering work. Industry cites the right sector-depth packs in AI infra, banking, healthcare, and energy/utilities.
- Evidence Operators: real retrieval is active; SEC search, BM25/ObjectBM25, BGE rerank, and runtime ledger rows are present in the checked runs.
- Specialists: all roles understand bounded evidence constraints. Industry relationship usage is now correct. Risk no longer consumes relationship evidence. Healthcare Risk still needed a repair attempt, indicating schema/output breadth rather than upstream instruction failure.
- Judgment Aggregator: blocks unsupported claims effectively, but converts the plan into a conservative verified outline rather than a high-conviction investment thesis.
- Memo Writer: Q10 compact repair removed the Q9 token blow-up; all four cases completed with one memo call. Outputs remain bounded and conservative.
- Verifier: compact inventory preserves safety behavior at lower cost. It guards the final memo but does not add analytical depth.

## Interpretation

The full chain is now real and auditable rather than dry-run:

- Main agent routing, relationship route, evidence operators, Specialist LLM calls, judgment aggregation, Memo Writer, and Verifier are all activated.
- Real retrieval and BGE rerank are present.
- Role/source boundaries align better with the 186 matrix, especially the Risk/Relationship separation.
- Token cost improved materially versus Q8/Q9:
  - Q8 AI infra total: `98,180`.
  - Q9 AI infra total: `99,870`.
  - Q10 AI infra total: `68,176`.

The remaining quality issue is not primarily a model-understanding failure. It is a chain-design issue:

- Specialists generate too many unsupported/gap claims.
- Aggregator lacks an evidence-backed thesis synthesis step.
- Memo Writer receives a safe verified plan, but not always a strong thesis slot.
- Research Lead spends tokens on all-role coverage even when priority should be sharper.
- Source-gap second pass needs tighter trigger logic.

## Decision

- Proceed with Q14 design and implementation.
- Do not loosen source-boundary gates as the primary fix.
- Improve quality by changing intermediate contracts:
  - Aggregator thesis ClaimCard synthesis from existing supported claims.
  - Specialist unsupported-claim cap and risk compact schema.
  - Research Lead activation priority.
  - More precise source-gap second-pass trigger.

## Verification

```text
python -m pytest tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 39 passed

python -m compileall src\sec_agent\memo_llm.py src\sec_agent\specialist_llm.py src\sec_agent\multi_agent_runtime.py
result: pass

python -m pytest tests/test_sec_agent_ledger_store.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py -q
result: 93 passed
```

## Caveats

- Q10-Q13 artifacts were created before the final finish-reason aggregation observability patch, so `memo_writer.route_result.finish_reasons` may be empty in those artifact summaries even though diagnostics show `finish_reason=stop`.
- These runs are diagnostic inference evaluations, not a production memo-quality acceptance gate.
- High token cost remains a diagnostic flag even after Q10 improvement.
