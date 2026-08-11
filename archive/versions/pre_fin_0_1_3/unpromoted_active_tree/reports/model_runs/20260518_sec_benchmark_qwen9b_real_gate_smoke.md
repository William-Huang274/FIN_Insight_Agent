# Model Run: 20260518_sec_benchmark_qwen9b_real_gate_smoke

## Summary
- Purpose: 重新审计 2026-05-18 13:00 以来新增 SEC benchmark / gate / Qwen backend 工作，确认方向是否偏离，并用云端真实 Qwen3.5-9B 做最小 gate smoke。
- Status: diagnostic-only completed.
- Run type: gate audit + real-model smoke.
- Timestamp: 2026-05-18.
- Environment: cloud RTX 4090, `/root/miniconda3/bin/python`, Qwen3.5-9B FP16 from `data/models_private/modelscope/Qwen/Qwen3___5-9B`.

## Code Changes
- `scripts/run_sec_benchmark_post_gates.py`
  - Replaced child-process `"python"` calls with `sys.executable`, so cloud conda Python is preserved.
  - Changed Qwen ratio denominator to non-trap eligible outputs; anti-hallucination trap refusal is excluded from the Qwen answer ratio.
  - Added `qwen_ledger_repaired` accounting and made `answered_qwen9b` the only status counted as true Qwen pass.
  - Fixed false fallback accounting where `qwen_failed_no_fallback` was previously matched by substring.
- `scripts/run_sec_benchmark_eval.py`
  - Added repeated `--case-id` filter for cloud single-case smoke runs.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Switched the prompt package from metadata-only `preview` to `Exact-Value Ledger + Evidence Text`.
  - Required exact numbers to use ledger `metric_id/display_value_zh`.
  - Added JSON parsing and deterministic ledger repair when Qwen output is not valid JSON.
  - Split statuses: `answered_qwen9b` means valid JSON from Qwen; `answered_qwen9b_ledger_repair` means real model was invoked but final answer was repaired from ledger because model output was invalid JSON.

## Local Validation
- `python -m py_compile scripts/run_sec_benchmark_eval.py scripts/run_sec_benchmark_post_gates.py scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- Local fallback regression:
  - `reports/quality/local_ratio_regression_fallback_gates/sec_benchmark_post_gates_summary.json`
  - `qwen_answer_ratio=0.0`, `fallback_answered=20`, `trap_outputs_excluded=2`, `qwen_answer_gate_pass=false` under `--min-qwen-answer-ratio 0.8`.
- Local no-fallback regression:
  - `reports/quality/local_ratio_regression_no_fallback_gates/sec_benchmark_post_gates_summary.json`
  - `qwen_answer_ratio=0.0`, `failed_eligible_outputs=20`, `fallback_answered=0`, `trap_outputs_excluded=2`.

## Cloud Smoke
- Case: `AMZN_AWS_NUMERIC_2023_2025_001`.
- Mode: `gold_context`.
- Run output: `eval/sec_cases/outputs/run_20260518_qwen9b_singlecase_smoke_v4/`.
- Gate output: `reports/quality/cloud_qwen9b_singlecase_smoke_v4_gates/sec_benchmark_post_gates_summary.json`.
- First smoke finding: real 9B ran, but the old backend only passed `preview`, so the model correctly reported evidence as missing.
- After ledger/text prompt fix: model invocation succeeded and exact ledger values were preserved, but Qwen still emitted non-JSON/thinking-style text. The backend repaired to ledger-only output and marked the row as `answered_qwen9b_ledger_repair`.

## Results
- `answer_status`: `answered_qwen9b_ledger_repair`.
- `score_total`: `8.4`.
- `failure_types`: `qwen_output_invalid_json_repaired`.
- Gate summary:
  - `eligible_outputs=1`
  - `qwen_answered=0`
  - `qwen_ledger_repaired=1`
  - `fallback_answered=0`
  - `qwen_answer_ratio=0.0`
  - `qwen_answer_gate_pass=false`
- This is the intended hard-gate behavior: calling the true model is not enough; only valid structured Qwen output counts as true pass.

## Audit Decision
- Direction is correct: reviewed gold, Exact-Value Ledger, backend interface, post-gates, trap gate, gold-vs-pipeline gate, and minimum true-Qwen ratio form the right promotion boundary.
- Main issue fixed: fallback / repair can no longer be counted as true Qwen answer.
- Remaining blocker: the current HF per-case Qwen backend does not yet reliably produce valid JSON; it must not be promoted to main-chain benchmark generation.
- Next step: fix structured Qwen output conformance, preferably through the existing resident vLLM/no-think path rather than per-case HF model loading, then rerun the 4 reviewed non-trap cases before any broader benchmark.
