# 128 - Full30 Qwen9B vs DeepSeek API A/B

## Summary
- Date: 2026-05-21
- Scope: constrained free-query SEC agent, full 30-company SEC 10-K inventory, 2023-2025.
- Prompt: `你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Status: completed; artifacts synced from cloud to local with folder structure preserved.

## Runs
- DeepSeek v4-pro high-thinking diagnostic:
  - Artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_161252_b38c717195`
  - Planner: `llm:deepseek:fallback_after_error`
  - Parse: `parse_error_ledger_repair`
  - Gates: failed `caveat_claim_gate_pass`, `qwen_answer_gate_pass`
  - Tokens: 23,902 input / 5,000 output
  - Elapsed: 389.7 sec
- Qwen9B local vLLM baseline:
  - Artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_161929_b38c717195`
  - Planner: `heuristic:ok`
  - Parse: `parsed`
  - Gates: all green
  - Tokens: 26,335 input / 3,007 output
  - Elapsed: 236.2 sec
- DeepSeek v4-pro no-thinking diagnostic:
  - Artifacts: `eval/sec_cases/outputs/interactive_sec_agent/20260521_162939_b38c717195`
  - Planner: `llm:deepseek:ok`
  - Parse: `parsed`
  - Gates: failed `v2_semantic_contract_gate_pass`
  - Tokens: 21,177 input / 1,948 output
  - Elapsed: 294.9 sec

## Query And Outputs
- User query and rendered model outputs are recorded in `reports/model_runs/20260521_sec_agent_full30_qwen9b_deepseek_ab_outputs.md`.
- Raw provider output JSON/text remains in each run directory under `qwen/raw_model_outputs.jsonl`.

## Findings
- DeepSeek high-thinking is not compatible with the current strict JSON contract at the tested budget. It filled the 5,000 output-token limit and caused invalid JSON repair.
- DeepSeek no-thinking is the better API profile for this project stage. It successfully generated a Query Contract from inventory-injected prompts and passed planner validation.
- Qwen9B remains the most gate-stable path today, but its final answer is still conservative and insight-light: three key points, mostly AMZN/META/INTC after claim-first filtering.
- DeepSeek no-thinking gave a cleaner planner and broader focus scope, but the final answer still had a semantic-contract failure. The failure was `peer_case_missing_company_mention`, triggered by the current gate treating a broad free-query as if all 30 companies must be explicitly mentioned.
- Claim-first verifier is doing useful work:
  - Qwen9B: 7 candidates, 5 promoted, 2 rejected.
  - DeepSeek no-thinking: 7 candidates, 5 promoted, 2 rejected.
  - DeepSeek high-thinking: 11 candidates, 7 promoted, 4 rejected.

## Decision
- Keep Qwen9B as the local safe baseline.
- Use DeepSeek v4-pro no-thinking, not high-thinking, for strict JSON planner/synthesis experiments.
- Mark this A/B as diagnostic-only. The route is not yet production-ready because the broad-query evidence pack and semantic gate contract need adjustment.

## Next Work
- Add provider profiles so planner/synthesis JSON tasks default to no-thinking API mode while allowing a separate free-form analysis mode later.
- Align free-query semantic gates with `focus_tickers` and `decomposed_tasks`; do not require all 30 manifest companies to appear unless the Query Contract explicitly asks for a full universe survey.
- Widen or diversify Evidence Pack selection for broad industry prompts so the final answer can support richer insight without unsupported claims.
- Split synthesis into two calls: claim-candidate generation and final renderer, using the claim-first verifier between them.

## 2026-05-21 Structural Follow-Up
- Completed the semantic-gate and evidence/ledger structural fixes in `docs/worklog/129_sec_agent_free_query_structural_fixes.md`.
- Semantic replay on the DeepSeek no-thinking diagnostic output now passes with `fail_count=0`; the prior broad-query `peer_case_missing_company_mention` failure is resolved by focus/decomposed-task semantics.
- Offline ledger replay now produces 36 cleaner rows across cloud revenue, data-center revenue, semiconductor revenue, capex, and operating income families.
- Remaining decision: rerun cloud Qwen9B and DeepSeek no-thinking after syncing code; the local validation did not execute fresh model inference.
