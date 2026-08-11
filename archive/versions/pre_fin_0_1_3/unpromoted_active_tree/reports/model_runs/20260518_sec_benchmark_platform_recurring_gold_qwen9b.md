# Model Run: 20260518_sec_benchmark_platform_recurring_gold_qwen9b

## Summary
- Purpose: Add the reviewed `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001` diagnostic case and run a true Qwen3.5-9B gold-context synthesis smoke.
- Status: diagnostic-only pass.
- Run type: artifact build + inference + evaluation gates.
- Timestamp: 2026-05-18 21:43 Asia/Shanghai.
- Environment: cloud RTX 4090 HF per-case Qwen3.5-9B; local deterministic gates.

## Code And Command
- Entry points:
  - `scripts/validate_sec_gold_gate.py`
  - `scripts/build_sec_benchmark_exact_value_ledger.py`
  - `scripts/run_sec_benchmark_eval.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Cloud command:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --mode gold_context \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --synthesis-backend external_command \
  --synthesis-command '/root/miniconda3/bin/python scripts/run_sec_eval_synthesis_qwen9b_backend.py --input {input_json} --output {output_json} --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json --max-model-len 32768 --max-tokens 5000 --disable-fallback'
```
- Local post-gate command:
```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260518_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py \
  --output-dir reports/quality/cloud_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py_post_gates \
  --skip-trap-gate \
  --skip-gold-vs-pipeline-gate \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json
```

## Inputs
- Case: `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`.
- Reviewed facts: `eval/sec_cases/reviewed_gold_facts/PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001.json`, 15 rows.
- Reviewed context: `eval/sec_cases/reviewed_gold_context/PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001.jsonl`, 23 rows.
- Exact-Value Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`, 50 rows after reviewed9 expansion.
- Abstract rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`.

## Outputs
- Single-case Qwen output: `eval/sec_cases/outputs/run_20260518_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py/`.
- Single-case post-gates: `reports/quality/cloud_platform_recurring_gold_qwen9b_hf_32768_ledger50_abs_py_post_gates/sec_benchmark_post_gates_summary.json`.
- Reviewed9 gold gate: `reports/quality/sec_benchmark_v1_gold_gate_reviewed9_text_numeric_cloud_platform.json`.
- Single-case gold gate: `reports/quality/sec_benchmark_v1_gold_gate_platform_recurring_quality.json`.

## Results
- Reviewed9 gold gate: `can_enter_gate=true`, `status_counts={"pass": 9}`, blockers `0`.
- Reviewed exact-value ledger rebuild: `approved_case_count=9`, `row_count=50`.
- True Qwen single-case output: `answer_status=answered_qwen9b`, `qwen_output_status=valid_json`, `ledger_text_contract_violation_count=0`, `ledger_text_contract_sanitized_count=0`.
- Backend score: `score_total=8.4`.
- Post-gates:
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`
  - `ledger_unit_gate_pass=true`
- Abstract judgment: `required_dimension_count=6`, `covered_required_dimension_count=6`.
- Ledger unit: `ledger_row_count=50`, `fail_count=0`.

## Manual Review
- The answer's high-level judgment is directionally correct: Apple Services shows rising revenue and gross margin but is not pure subscription; Adobe has cleaner subscription/ARR visibility; Microsoft Cloud is a broad proxy with subscription and consumption elements plus declining Microsoft Cloud gross margin.
- Caveats are present and affect conclusion strength through `strong/medium` driver calibration.
- Residual quality issue: the answer cites ledger `metric_id` arrays but does not include any `display_value_zh` in prose, so `answer_ledger_gate` passes with `exact_value_hit_count=0`. This is safe but less informative than desired.

## Experiment Governance
- Hypothesis: A reviewed evidence pack plus exact-value ledger can let Qwen9B produce a supported recurring-quality comparison without seed fact contamination.
- Decision target: single-case reviewed gold gate passes, true Qwen output is valid JSON with no fallback/ledger repair, and deterministic post-gates pass.
- Baseline: seed facts for this case were rejected because they mixed Apple percentage-change rows, Adobe ARR revaluation deltas, and clean totals.
- Stop conditions: seed rows/facts in reviewed mode, external command fallback, ledger contract violations, metric-role failure, named-fact failure, abstract rubric failure, or ledger-unit failure.
- Decision label: diagnostic-only proceed.
- Mainline decision: approved for case-filtered gold-context smoke; not full-benchmark approval.

## Runtime Efficiency
- Remote HF run took about 166 seconds including per-case model load and generation.
- Bottleneck: HF per-case model loading; resident vLLM remains preferable for multi-case or pipeline-context runs.
- Serving relevance: diagnostic only, not serving-quality throughput.

## Caveats And Next Step
- Not run: pipeline-context retrieval for this case and reviewed9 plus trap full bundle were not run.
- Known risk: current gates do not require a minimum count of `display_value_zh` mentions in prose, so a safe but under-informative answer can pass.
- Next decision: either add a minimum display-value-use requirement for numeric ledger cases or run this case through pipeline-context first to see whether retrieval changes the qualitative coverage.
