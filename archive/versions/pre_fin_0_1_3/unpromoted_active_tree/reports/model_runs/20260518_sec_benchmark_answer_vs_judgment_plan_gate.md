# Model Run: 20260518_sec_benchmark_answer_vs_judgment_plan_gate

## Summary

- Purpose: Add a deterministic final-answer gate that checks whether Qwen output stays inside the validated Judgment Plan.
- Status: diagnostic-only completed.
- Run type: deterministic validator + post-gate integration.
- Timestamp: 2026-05-18.
- Environment: local `D:\FIN_Insight_Agent`; no new true-Qwen inference was run because local `vllm` and local Qwen3.5-9B model paths were unavailable.

## Work Completed

- Added `scripts/validate_sec_benchmark_answer_vs_judgment_plan.py`.
- Wired optional `--judgment-plan-path` / `--skip-answer-vs-judgment-plan-gate` into `scripts/run_sec_benchmark_post_gates.py`.
- Ran standalone validator smoke on existing rubric-only Cloud and Platform outputs.
- Ran post-gate integration smoke on the existing Platform output.

## Gate Behavior

The validator checks:

- Final answer support IDs must be inside the Judgment Plan.
- Each answer `decision_driver` must match one plan driver by metric/evidence overlap.
- Driver-local evidence cannot be borrowed from another plan driver.
- Final answer cannot upgrade a driver above the plan strength.
- Proxy metrics cannot be marked `strong` and must carry proxy/comparability caveats.
- Weak plan support cannot be used in local prose as a strong claim without an immediate caveat.

## Commands

```powershell
python -m py_compile scripts\validate_sec_benchmark_answer_vs_judgment_plan.py scripts\run_sec_benchmark_post_gates.py scripts\run_sec_eval_synthesis_qwen9b_backend.py scripts\run_sec_benchmark_vllm_synthesis_from_traces.py scripts\build_sec_benchmark_judgment_plan.py scripts\validate_sec_benchmark_judgment_plan.py

python scripts\validate_sec_benchmark_answer_vs_judgment_plan.py --run-dir eval\sec_cases\outputs\run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200_summaryshort_consistency --judgment-plan-path reports\evidence_packs\sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json --output-path reports\quality\sec_benchmark_v1_reviewed8_cloud_answer_vs_judgment_plan_validation.json

python scripts\validate_sec_benchmark_answer_vs_judgment_plan.py --run-dir eval\sec_cases\outputs\run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe --judgment-plan-path reports\evidence_packs\sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json --output-path reports\quality\sec_benchmark_v1_platform_answer_vs_judgment_plan_validation.json

python scripts\run_sec_benchmark_post_gates.py --gold-run-dir eval\sec_cases\outputs\run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe --output-dir reports\quality\local_platform_answer_vs_judgment_plan_post_gate_smoke --skip-trap-gate --skip-gold-vs-pipeline-gate --judgment-plan-path reports\evidence_packs\sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

## Outputs

- Cloud standalone report: `reports/quality/sec_benchmark_v1_reviewed8_cloud_answer_vs_judgment_plan_validation.json`.
- Platform standalone report: `reports/quality/sec_benchmark_v1_platform_answer_vs_judgment_plan_validation.json`.
- Platform post-gate smoke summary: `reports/quality/local_platform_answer_vs_judgment_plan_post_gate_smoke/sec_benchmark_post_gates_summary.json`.

## Results

- Cloud old output: `can_enter_gate=false`.
  - Caught a Google driver citing an AMZN evidence ID.
  - Caught the MSFT proxy driver being upgraded from plan `weak` to answer `medium`.
  - Caught missing proxy caveat wording for the MSFT proxy driver.
- Platform old output: `can_enter_gate=false`.
  - Caught three final-answer evidence IDs not present in the Judgment Plan.
  - Caught the same IDs at driver and key-point support locations.
- Platform post-gate smoke:
  - Existing gates still passed: answer ledger, metric-role terms, named-fact support, ledger-missing consistency, abstract judgment, ledger unit.
  - New answer-vs-plan gate failed as intended, proving it adds coverage not provided by the earlier gates.

## Environment Blocker For True-Qwen Rerun

- `vllm` import check: unavailable locally.
- `data\models_private\modelscope\Qwen\Qwen3___5-9B`: not found locally.
- `data\models_private\modelscope\Qwen\Qwen3.5-9B`: not found locally.

## Next Cloud Command

Run this on the 4090 environment with the model available:

```bash
python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_cloud_pipeline_qwen9b_judgment_plan \
  --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json

python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_pipeline_qwen9b_judgment_plan \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

Then run post-gates with `--judgment-plan-path` and require the new gate to pass before promoting the Answer Plan path.
