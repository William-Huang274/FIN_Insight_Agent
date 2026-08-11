# Model Run: 20260518_sec_benchmark_reviewed4_pipeline_metricterms_strict

## Summary
- Purpose: 验证 reviewed4 SEC benchmark 在 `pipeline_context` 主链路下，真实 Qwen3.5-9B 输出能否同时通过 Exact-Value Ledger、metric-role terminology、gold-vs-pipeline、ledger-unit、true-Qwen ratio，以及两个 trap refusal gate。
- Status: completed, case-filtered diagnostic-only.
- Run type: inference + evaluation gates.
- Timestamp: 2026-05-18.
- Environment: cloud RTX 4090 resident vLLM for non-trap synthesis; local + cloud deterministic post-gates.

## Code And Command
- Entry points:
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - `scripts/run_sec_benchmark_post_gates.py`
  - `scripts/validate_sec_benchmark_metric_role_terms.py`
- Key cloud command:
  - `python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed4_pipeline_context_traces --output-dir eval/sec_cases/outputs/run_20260518_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict --mode pipeline_context --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json --max-model-len 32768 --max-tokens 2600 --structured-json`
  - `python scripts/run_sec_benchmark_post_gates.py --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed4_gold_qwen9b_vllm_structured_2600_metricterms --pipeline-run-dir eval/sec_cases/outputs/run_20260518_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict --output-dir reports/quality/cloud_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict_post_gates_v2 --min-qwen-answer-ratio 1.0 --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json --skip-trap-gate`
- Code changes were in a dirty worktree; no git commit was created.

## Inputs
- Reviewed non-trap cases:
  - `AMZN_AWS_NUMERIC_2023_2025_001`
  - `GOOGL_CLOUD_CONTEXT_ROLE_2025_001`
  - `AAPL_SERVICES_MARGIN_2023_2025_001`
  - `PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001`
- Trap cases:
  - `AAPL_AWS_TRAP_001`
  - `META_LLAMA_COST_TRAP_001`
- Exact ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`, `row_count=17`.
- Pipeline traces: `eval/sec_cases/outputs/run_20260518_reviewed4_pipeline_context_traces/`.
- Gold reference run: `eval/sec_cases/outputs/run_20260518_reviewed4_gold_qwen9b_vllm_structured_2600_metricterms/`.

## Outputs
- Strict pipeline Qwen output: `eval/sec_cases/outputs/run_20260518_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict/`.
- Cloud post-gates: `reports/quality/cloud_reviewed4_pipeline_qwen9b_vllm_structured_2600_metricterms_strict_post_gates_v2/sec_benchmark_post_gates_summary.json`.
- Trap output: `eval/sec_cases/outputs/run_20260518_trap_pipeline_contract_vllm_path/`.
- Local 6-case bundle: `eval/sec_cases/outputs/run_20260518_reviewed4_metricterms_strict_plus_traps_pipeline_gate_bundle/`.
- Local 6-case bundle gates: `reports/quality/local_reviewed4_metricterms_strict_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`.

## Results
- Cloud reviewed4 pipeline-context:
  - `answer_status_counts={"answered_qwen9b": 4}`.
  - `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`.
  - `gold_vs_pipeline_pass=true`.
  - `answer_ledger_gate_pass=true`, `exact_value_hit_count=29`.
  - `metric_role_term_gate_pass=true`.
  - `ledger_unit_gate_pass=true`, `pass_count=17`, `fail_count=0`.
- Local reviewed4 + trap bundle:
  - `answer_status_counts={"answered_qwen9b": 4, "answered_contract_fallback": 2}`.
  - `trap_gate_pass=true`.
  - `gold_vs_pipeline_pass=true`.
  - `answer_ledger_gate_pass=true`.
  - `metric_role_term_gate_pass=true`.
  - `ledger_unit_gate_pass=true`.
  - `qwen_answer_ratio=1.0`; trap rows are excluded from the non-trap true-Qwen denominator.

## Interpretation
- The reviewed4 pipeline-context path now passes as a real-model run, not a fallback or deterministic ledger repair run.
- The new `metric_role_term_gate` caught semantic issues that Exact-Value Ledger alone could not catch: RPO described as forecast recurring revenue, Billings phrased as revenue, and Apple Services overclaimed as recurring quality.
- Prompt-side metric naming rules fixed the AAPL and RPO failures. A too-broad Billings rule was narrowed after it falsely flagged correct text saying Billings is not recognized revenue.
- GOOGL initially copied ledger-external 2023/2024 comparison values from Evidence Text; the stricter prompt now forbids ledger-external exact values, rounded values, and unit conversions.

## Governance
- Decision label: diagnostic-only.
- Mainline decision: proceed to the next case-filtered pipeline step; do not claim full benchmark readiness.
- Blocked from full mainline: only 4 non-trap reviewed cases and 2 trap cases are approved. The remaining seed/diagnostic cases still require reviewed gold facts or explicit exclusion.

## Runtime Efficiency
- Cloud resident vLLM full reviewed4 pipeline strict run: about 262 seconds wall time, including model load.
- Per-case elapsed times ranged from about 29 seconds to 65 seconds after model load/warmup.
- Model path: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.

## Caveats And Next Step
- Not run: full 12-case benchmark, L4 diagnostic stress cases, and production-scale end-to-end query serving.
- Known risk: metric-role terminology gate is intentionally narrow; broader financial concept misuse still needs more reviewed examples before expanding rules.
- Next decision: either review more SEC benchmark cases into gold facts, or connect these gates to the broader complex-insight pipeline before expanding sample size.
