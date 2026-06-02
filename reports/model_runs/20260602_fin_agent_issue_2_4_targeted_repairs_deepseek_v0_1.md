# Model Run: 20260602_fin_agent_issue_2_4_targeted_repairs_deepseek_v0_1

## Summary

- Purpose: verify targeted repairs for full17 failure buckets 2-4 without rerunning the full 17-case suite.
- Status: accepted targeted diagnostic; full17 merge-readiness is not claimed.
- Run type: inference / evaluation.
- Timestamp: 2026-06-02 Asia/Shanghai.
- Environment: local Windows workspace, real evidence operators, DeepSeek API via `DEEPSEEK_API_KEY` environment variable. API key and raw LLM responses were not saved.

## Code And Command

- Entry point: `scripts/eval_multi_agent_real_llm_chain.py`
- Main commands:
  - `python scripts\eval_multi_agent_real_llm_chain.py --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl --run-id 20260602_fin_agent_issue_2_4_targeted_exact_multi_v0_2 --real-evidence-operators --strict --case-id fin_full_exact_msft_capex_zh --case-id fin_full_exact_jpm_credit_provision_zh --case-id fin_full_mt_semis_scope_t1 --case-id fin_full_mt_semis_scope_t2 --case-id fin_full_mt_banking_t1 --case-id fin_full_mt_banking_t2`
  - `python scripts\eval_multi_agent_real_llm_chain.py --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl --run-id 20260602_fin_agent_issue_2_4_targeted_banking_t2_market_v0_1 --real-evidence-operators --strict --case-id fin_full_mt_banking_t1 --case-id fin_full_mt_banking_t2`
  - `python scripts\eval_multi_agent_real_llm_chain.py --cases-path tests\fixtures\fin_agent_full_chain_multiturn_cases_v0_1.jsonl --run-id 20260602_fin_agent_issue_2_sector_utilities_scope_budget_fix_v0_2 --real-evidence-operators --strict --case-id fin_full_sector_utilities_power_depth_zh`
- Local verification:
  - `pytest -q tests\test_multi_agent_langgraph_routing.py`
  - `pytest -q tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_research_lead_llm.py`
  - `python -m compileall src\sec_agent\langgraph_orchestrator.py src\sec_agent\multi_agent_runtime.py scripts\eval_multi_agent_real_llm_chain.py`

## Inputs

- Cases: `tests/fixtures/fin_agent_full_chain_multiturn_cases_v0_1.jsonl`
- Target case IDs:
  - exact lookup: `fin_full_exact_msft_capex_zh`, `fin_full_exact_jpm_credit_provision_zh`
  - multi-turn: `fin_full_mt_semis_scope_t1`, `fin_full_mt_semis_scope_t2`, `fin_full_mt_banking_t1`, `fin_full_mt_banking_t2`
  - sector-depth: `fin_full_sector_utilities_power_depth_zh`
- Retrieval mode: real evidence operators with SEC search, exact-value runtime ledger, BM25/ObjectBM25/BGE rerank, relationship lookup, market snapshot, and industry snapshot where required.

## Results

| Run ID | Cases | Result | Notes |
| --- | ---: | --- | --- |
| `20260602_fin_agent_issue_2_4_targeted_exact_multi_v0_2` | 6 | `5/6` pass | Exact lookup and semis multi-turn passed; banking T2 exposed missing market route reconciliation. |
| `20260602_fin_agent_issue_2_4_targeted_banking_t2_market_v0_1` | 2 | `2/2` pass | Banking T2 market route and operator alignment repaired. |
| `20260602_fin_agent_issue_2_sector_utilities_targeted_v0_1` | 1 | `0/1` pass | Diagnostic failure only: top-level `agent_tool_budget_exhausted`; real Specialist quality passed. |
| `20260602_fin_agent_issue_2_sector_utilities_budget_fix_v0_1` | 1 | `1/1` pass | Quality second-pass incremental budget-loop suppression fixed the gate; `13` tool calls. |
| `20260602_fin_agent_issue_2_sector_utilities_scope_budget_fix_v0_2` | 1 | `1/1` pass | Market scope expansion reduced tool calls to `11`; all hard checks true. |

Accepted final targeted run:

- Output: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260602_fin_agent_issue_2_sector_utilities_scope_budget_fix_v0_2/real_chain_eval_summary.json`
- Metrics: `case_count=1`, `passed=1`, `failed=0`, `pass_rate=1.0`, `total_tool_calls=11`, `real_retrieval_required_cases=1`, `real_specialist_quality_required_cases=1`, `real_specialist_quality_passed=1`.
- Gate checks: Research Lead, Universe/Relationship, evidence operators, real SEC retrieval, BM25/ObjectBM25/BGE, market/industry/relationship rows, Specialist real-evidence quality, Memo Writer, Verifier, rendered Chinese answer, and payload safety all passed.

## Efficiency And Safety

- Full17 was not rerun. The repair intentionally limited real API use to previously failing exact/multi/sector-depth subsets.
- Utilities sector-depth wall time remained several minutes due DeepSeek LLM calls plus BGE model cold load. The accepted v0.2 reduced tool calls from `13` to `11`, but future cost work should filter already-covered second-pass market routes.
- API credentials were read from the environment only; no key or raw model response was saved.

## Decision

- Proceed for targeted issue 2-4 repair.
- Do not claim merge readiness from this run alone. A later closeout should rerun the full 17-case suite only after any remaining cost-route cleanup is accepted.
