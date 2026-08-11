# Model Run: 20260518_sec_benchmark_reviewed4_qwen9b_canonicalized

## Summary
- Purpose: 在 reviewed 4 个 SEC benchmark non-trap case 上验证真实 Qwen3.5-9B resident vLLM 输出能否通过 Exact-Value Ledger、ledger unit、true-Qwen ratio 三个硬门。
- Status: diagnostic-only completed.
- Run type: cloud resident vLLM inference + qwen-only post-gates.
- Timestamp: 2026-05-18.
- Environment: cloud RTX 4090, `/root/miniconda3/bin/python`, Qwen3.5-9B FP16 from `data/models_private/modelscope/Qwen/Qwen3___5-9B`.

## Code Changes
- `src/evidence/structured_extractor.py`
  - Fixed table header detection so segment numeric rows such as Apple `Products/Services` gross-margin percentage are not misclassified as headers.
  - Fixed unit-row detection so metric rows like `Remaining performance obligations (in millions)` are retained instead of being skipped.
  - Preserved sentence-level `$... million/billion` units as `usd_millions` / `usd_billions`.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Added deterministic exact-value canonicalization: if a numeric mention uniquely matches a case ledger row, rewrite it as `display_value_zh (metric_id)`.
  - Kept fallback behavior for ledger-external or ambiguous values.

## Validation Before Inference
- Rebuilt structured objects:
  - `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`
  - `data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl`
  - `data/processed_private/structured_objects/sec_tech_10k_claims.jsonl`
- `python scripts/validate_structured_objects.py`
  - `passed=true`
  - Apple Services gross margin percentage check passed.
  - Snowflake RPO table + sentence evidence check passed.
- Rebuilt reviewed ledger:
  - `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
  - `row_count=17`
- Ledger unit gate:
  - `reports/quality/cloud_reviewed4_ledger_unit_gate_after_extractor_fix.json`
  - `can_enter_gate=true`, `pass_count=17`, `fail_count=0`.

## Inference Run
- Command shape:
  - `python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed4_gold_context_traces --output-dir eval/sec_cases/outputs/run_20260518_reviewed4_qwen9b_vllm_structured_2600_canonicalized --mode gold_context --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json --max-model-len 32768 --max-tokens 2600 --structured-json`
- Output:
  - `eval/sec_cases/outputs/run_20260518_reviewed4_qwen9b_vllm_structured_2600_canonicalized/`
- Runtime:
  - model load `50.613s`
  - total elapsed `242.0882s`
  - trace count `4`
  - agent output count `4`

## Results
- Answer status counts:
  - `answered_qwen9b=4`
  - `answered_qwen9b_ledger_repair=0`
  - fallback `0`
- Qwen-only post-gates:
  - `reports/quality/cloud_reviewed4_qwen9b_vllm_structured_2600_canonicalized_qwen_only_gates/sec_benchmark_post_gates_summary.json`
  - `answer_ledger_gate_pass=true`
  - `answer_ledger_summary.pass_count=4`
  - `answer_ledger_summary.fail_count=0`
  - `ledger_unit_gate_pass=true`
  - `ledger_unit_summary.pass_count=17`
  - `ledger_unit_summary.fail_count=0`
  - `qwen_answer_ratio=1.0`
  - `qwen_answer_gate_pass=true`
- Non-applicable gates in qwen-only run:
  - `trap_gate_skipped=true`
  - `gold_vs_pipeline_gate_skipped=true`

## Interpretation
- The previous GOOGL repair was not a factual failure. The raw model output used ledger values but did not attach `metric_id` near summary numbers. Canonicalization fixed this without replacing the model answer.
- This run proves the reviewed 4 non-trap cases can pass true-model, exact-value, and unit gates under resident vLLM structured JSON.
- This does not yet prove full main-chain readiness because trap refusal and gold-vs-pipeline comparison were intentionally skipped for this qwen-only boundary.

## Follow-up
- Run the same gate profile on pipeline-context traces, then run a separate trap suite with trap gate enabled.
- Keep canonicalization narrow: only unique ledger matches may be rewritten; ambiguous or ledger-external values must remain hard failures or deterministic repair.
