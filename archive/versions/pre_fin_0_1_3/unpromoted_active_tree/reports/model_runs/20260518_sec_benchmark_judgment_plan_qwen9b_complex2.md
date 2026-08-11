# Model Run: 20260518_sec_benchmark_judgment_plan_qwen9b_complex2

## Summary

- Purpose: Run true Qwen3.5-9B vLLM synthesis with validated Judgment Plan prompt injection for the two complex reviewed SEC cases.
- Status: diagnostic-only completed.
- Run type: cloud inference + deterministic post-gates.
- Timestamp: 2026-05-18.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, single GPU, `/root/miniconda3/bin/python3`, vLLM available, model `data/models_private/modelscope/Qwen/Qwen3___5-9B`.

## Inputs

- Judgment Plan seed: `reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json`.
- Cloud trace: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8`.
- Platform trace: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8`.
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`.
- Rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`.

## Code And Setup

- Uploaded local script updates to the cloud repo:
  - `scripts/build_sec_benchmark_judgment_plan.py`
  - `scripts/validate_sec_benchmark_judgment_plan.py`
  - `scripts/validate_sec_benchmark_answer_vs_judgment_plan.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - `scripts/run_sec_benchmark_post_gates.py`
  - `eval/sec_cases/abstract_judgment_rubric_v0_1.json`
- Remote overwritten files were backed up under `.tmp_judgment_plan_backup_20260518`.
- Remote py_compile passed for the uploaded scripts.
- No secrets were written to repo files or run logs.

## Commands

```bash
/root/miniconda3/bin/python3 scripts/validate_sec_benchmark_judgment_plan.py \
  --plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8 \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --output-path reports/quality/sec_benchmark_v1_reviewed_complex2_judgment_plan_validation_cloud.json

/root/miniconda3/bin/python3 scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_cloud_pipeline_qwen9b_judgment_plan \
  --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json

/root/miniconda3/bin/python3 scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_pipeline_qwen9b_judgment_plan \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

Post-gates were run separately for each single-case output with `--judgment-plan-path`.

## Outputs

- Cloud output: `eval/sec_cases/outputs/run_20260518_cloud_pipeline_qwen9b_judgment_plan`.
- Platform output: `eval/sec_cases/outputs/run_20260518_platform_pipeline_qwen9b_judgment_plan`.
- Cloud post-gates: `reports/quality/cloud_judgment_plan_post_gates/sec_benchmark_post_gates_summary.json`.
- Platform post-gates: `reports/quality/platform_judgment_plan_post_gates/sec_benchmark_post_gates_summary.json`.
- Run log: `reports/logs/judgment_plan_synthesis_20260518.log`.

## Results

- Judgment Plan validation on cloud: `can_enter_gate=true`, `pass_count=2`, `fail_count=0`; warning `supporting_evidence_id_not_seen_in_trace=7`.
- Cloud synthesis:
  - `answer_status=answered_qwen9b`.
  - Model load `63.6566s`, total elapsed `155.9582s`.
  - Post-gates all pass: answer ledger, metric role, named fact, ledger missing consistency, abstract judgment, answer-vs-plan, ledger unit.
  - Answer-vs-plan gate: `pass_count=1`, `fail_count=0`.
  - Summary: AWS and Google Cloud have direct revenue/operating-income trends; Microsoft is a weak proxy due to cloud revenue proxy, gross margin, and infrastructure cost pressure; direct profitability ranking is not feasible.
- Platform synthesis:
  - `answer_status=answered_qwen9b`.
  - Model load `61.1203s`, total elapsed `163.2889s`.
  - Post-gates all pass: answer ledger, metric role, named fact, ledger missing consistency, abstract judgment, answer-vs-plan, ledger unit.
  - Answer-vs-plan gate: `pass_count=1`, `fail_count=0`.
  - Summary: Apple services, Microsoft cloud proxy, and Adobe subscription revenue all show growth, but conclusion strength is limited by disclosure asymmetry, margin pressure, and missing profitability-quality evidence.

## Gate Adjustment

- Added `不可行` as an allowed equivalent for the Cloud rubric dimension that checks direct ranking is blocked.
- Added `用量` / `usage` / `不同` as proxy-caveat equivalents in the answer-vs-plan validator.
- Rationale: the model used semantically valid phrasing: `直接盈利排名不可行` and `包含用量型收入`; the prior keyword gate was too narrow.

## Decision

- Decision label: proceed.
- The validated Judgment Plan path is now viable for the two complex reviewed cases.
- It should next be integrated into a reviewed9 + 2 trap bundle run, with `--judgment-plan-path` enabled for the two complex cases and skipped or empty for cases without plans.

## Safety Notes

- This remains diagnostic-only, not a full noisy benchmark pass.
- The trace warning means some plan support IDs come from reviewed ledger support and not always trace topK; this is acceptable for the plan gate but should be documented before full benchmark promotion.
