# Model Run: 20260518_sec_benchmark_reviewed7_pipeline_sanitized_gate

## Summary
- Purpose: 验证 reviewed7 SEC benchmark 在 `pipeline_context` 主链路下，真实 Qwen3.5-9B 输出能否通过完整 evidence/ledger/term gates，并修复未入 ledger 派生精确数值导致的 `ledger_repair`。
- Status: completed, case-filtered diagnostic-only.
- Run type: inference + deterministic postprocess + evaluation gates.
- Timestamp: 2026-05-18.
- Environment: cloud RTX 4090 resident vLLM for Qwen3.5-9B synthesis; local deterministic reprocess and post-gates.

## Code And Command
- Entry points:
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Cloud command:
  - `/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_context_traces_top8_textfix --output-dir eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_qwen9b_vllm_structured_2600_top8_textfix_sanitized --mode pipeline_context --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json --max-model-len 32768 --max-tokens 2600 --structured-json`
- Local final gate command:
  - `python scripts/run_sec_benchmark_post_gates.py --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed7_gold_reference_qwen9b_mixed --pipeline-run-dir eval/sec_cases/outputs/run_20260518_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle --output-dir reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates --min-qwen-answer-ratio 1.0 --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Code changes were in a dirty worktree; no git commit was created.

## Inputs
- Reviewed non-trap cases: AMZN, GOOGL, AAPL, PANW, SNOW, NVDA, MSFT reviewed7 case IDs.
- Trap cases: `AAPL_AWS_TRAP_001`, `META_LLAMA_COST_TRAP_001`.
- Pipeline traces: `eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_context_traces_top8_textfix/`.
- Gold reference: `eval/sec_cases/outputs/run_20260518_reviewed7_gold_reference_qwen9b_mixed/`.
- Exact ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`, `row_count=17`.

## Outputs
- Cloud raw Qwen run: `eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_qwen9b_vllm_structured_2600_top8_textfix_sanitized/`.
- Local deterministic reprocess from saved raw outputs: `eval/sec_cases/outputs/run_20260518_reviewed7_pipeline_qwen9b_vllm_structured_2600_top8_textfix_sanitized_cnlimit/`.
- Final 9-case bundle: `eval/sec_cases/outputs/run_20260518_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle/`.
- Full post-gates: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`.
- Cloud log: `reports/logs/20260518_reviewed7_pipeline_qwen9b_vllm_structured_2600_top8_textfix_sanitized.log`.
- Named-fact support gate: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_named_fact_support_gate.json`.
- Strict-summary named-fact diagnostic: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_named_fact_support_gate_strict_summary_diagnostic.json`.

## Results
- Cloud reviewed7 Qwen synthesis:
  - `trace_count=7`, `agent_output_count=7`.
  - `answer_status_counts={"answered_qwen9b": 7}`.
  - Runtime `total_elapsed_sec=380.3904`, `load_model_sec=51.1165`.
- Local final 9-case bundle:
  - `answer_status_counts={"answered_qwen9b": 7, "answered_contract_fallback": 2}`.
  - `trap_gate_pass=true`.
  - `gold_vs_pipeline_pass=true`.
  - `answer_ledger_gate_pass=true`, `exact_value_hit_count=21`, `fail_count=0`.
  - `metric_role_term_gate_pass=true`.
  - `named_fact_gate_pass=true`, `checked_location_count=23`, `named_token_count=41`, `unsupported_token_count=0`, `warning_count=0`.
  - `ledger_unit_gate_pass=true`, `pass_count=17`, `fail_count=0`.
  - `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`, `trap_outputs_excluded=2`.

## Interpretation
- The reviewed7 `pipeline_context` path now passes as real Qwen output under the current reviewed case boundary.
- The key fix was a narrow deterministic sanitizer: unsupported exact values are removed locally instead of forcing whole-answer ledger fallback. GOOGL previously wrote an unauthorized derived amount, `78 亿美元`; the final answer keeps the operating-income judgement but states that the exact growth amount is not ledger-authorized.
- Canonicalization now rewrites ledger-matched exact values as `display_value_zh (metric_id)` when the nearby text lacks an inline metric ID.
- Text-heavy no-ledger cases no longer receive English internal limitations in final answer text.
- Added a standalone named-fact citation gate. It checks citation-bearing `decision_drivers` and `key_points`, with summary validation against the union of cited evidence IDs; ticker/internal metric tokens such as ARR/RPO are ignored.

## Governance
- Decision label: diagnostic-only.
- Mainline decision: proceed to the next reviewed-case expansion or a stricter named-fact/unsupported-claim gate before broad full-chain testing.
- Boundary: this is not full SEC benchmark readiness; only reviewed7 non-trap plus 2 trap cases are approved.

## Caveats And Next Step
- The sanitizer is intentionally narrow: it removes unauthorized exact values but does not prove every qualitative claim is semantically complete.
- Remaining quality risk is named-fact support and coverage depth in text-heavy answers; current named-evidence repair is lightweight and should become a standalone gate before broader sample expansion.
