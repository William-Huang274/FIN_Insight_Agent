# Model Run: 20260521_sec_agent_free_query_deepseek_user_output_namedfact_gate_patch_v1

## Summary
- Purpose: validate user-facing quiet terminal output, improved named-fact recovery, and the percentage phrase-boundary semantic gate fix on the full30 DeepSeek SEC chain.
- Status: completed; post-gate replay passed all deterministic gates.
- Run type: inference + deterministic gate replay.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 5090 host; artifacts synced back to local `D:\FIN_Insight_Agent`.

## Code And Command
- Entry points:
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/cloud/sec_agent_interactive.sh`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/validate_sec_benchmark_named_fact_support.py`
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
- User-facing command shape:
  - `USER_OUTPUT=1 bash scripts/cloud/sec_agent_interactive.sh ask-deepseek "..."`
- Replay command shape:
  - `python scripts/run_sec_benchmark_post_gates.py --gold-run-dir <run>/qwen --pipeline-run-dir <run>/qwen --cases-path <run>/case.jsonl --output-dir <run>/post_gates_replay_after_percentage_phrase_boundary_patch --ledger-path <run>/runtime_exact_value_ledger.json --judgment-plan-path <run>/runtime_judgment_plan.json --skip-trap-gate --skip-gold-vs-pipeline-gate --min-qwen-answer-ratio 1.0`

## Inputs
- Prompt:
  - `你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Scope:
  - 30 companies, years `2023,2024,2025`, SEC 10-K only.
- Backend:
  - DeepSeek API `deepseek-v4-pro`, thinking disabled.
- Inventory digest:
  - `e413b6c9ccd0`

## Outputs
- Quiet run:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195`
- Logged query/output:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195/qwen/input_output.md`
- Quiet stage log:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195/console_events.log`
- Final replayed post-gates:
  - `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195/post_gates_replay_after_percentage_phrase_boundary_patch/sec_benchmark_post_gates_summary.json`

## Results
- Quiet inference run:
  - Runtime ledger rows `36`
  - Context rows `360`
  - Elapsed `449.15 sec`
  - Initial post-gates failed only `v2_semantic_contract_gate_pass` due to a false positive on a gross-margin percentage phrase followed by an operating-income amount phrase.
- Post-gate replay after validator patch:
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `caveat_claim_gate_pass=true`
  - `v2_semantic_contract_gate_pass=true`
  - `answer_vs_judgment_plan_gate_pass=true`
  - `metric_source_grounding_gate_pass=true`
  - `ledger_unit_gate_pass=true`
  - `qwen_answer_ratio=1.0`

## Quality Read
- Quiet terminal mode now surfaces the answer without retrieval/progress noise; full progress is still durable in `console_events.log`.
- Named-fact recovery no longer over-sanitizes supported names in this run; the answer keeps user-facing names such as `博通`, `Applied Materials`, `微软`, and `亚马逊` when backed by the runtime ledger or evidence IDs.
- The percentage semantic patch is a phrase-boundary fix: it keeps the rule that percentage metrics cannot be used as dollar amounts, while avoiding contamination from the next metric phrase.

## Decision
- Proceed with quiet mode as the recommended interactive terminal mode for human quality review.
- Keep DeepSeek API insight mode as the preferred production synthesis path for broad free-query prompts.
- No model rerun was needed after the validator patch; the post-gate replay reused the saved DeepSeek output and evidence artifacts.
