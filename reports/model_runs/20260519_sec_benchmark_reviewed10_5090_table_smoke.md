# Model Run: 20260519_sec_benchmark_reviewed10_5090_table_smoke

## Summary
- Purpose: 在 RTX 5090 32GB / Blackwell 云端验证 `rtx5090_32gb` vLLM profile 能稳定跑 reviewed10 表格 case，并确认 corrected runtime env 不破坏 table-cell post-gates。
- Status: diagnostic-only completed
- Run type: cloud inference + deterministic post-gates + hardware-profile smoke
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus cloud RTX 5090 repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command
- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮涉及 5090 vLLM profile、Blackwell env checker、reviewed10 5090 outputs、gate reports 和 worklog。
- Profile/config:
  - `configs/vllm_hardware_profiles.json`
  - `--hardware-profile rtx5090_32gb`
  - profile runtime env: `TORCHDYNAMO_DISABLE=1`, `VLLM_USE_FLASHINFER_SAMPLER=0`
- Main commands:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20_5090 \
  --output-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids_5090_torchdynamo_off \
  --case-id REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --hardware-profile rtx5090_32gb \
  --max-tokens 6000 \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids_5090_torchdynamo_off \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids_5090_torchdynamo_off \
  --output-dir reports/quality/cloud5090_reviewed10_revenue_table_pipeline_qwen9b_post_gates_torchdynamo_off \
  --skip-trap-gate \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json \
  --skip-answer-vs-judgment-plan-gate
```

## Inputs
- Case: `REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001`
- Pipeline trace: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20_5090`
- Reviewed ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs
- Pipeline true-Qwen table run: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids_5090_torchdynamo_off`
- Single-case post-gates: `reports/quality/cloud5090_reviewed10_revenue_table_pipeline_qwen9b_post_gates_torchdynamo_off/sec_benchmark_post_gates_summary.json`
- Runtime log: `reports/logs/20260519_5090_reviewed10_revenue_table_pipeline_torchdynamo_off.log`

## Results
- vLLM 5090 run completed with `answer_status_counts={"answered_qwen9b":1}`.
- Applied profile runtime env was `{"TORCHDYNAMO_DISABLE":"1","VLLM_USE_FLASHINFER_SAMPLER":"0"}`.
- Timings from `run_summary.json`: `load_inputs_sec=0.0129`, `load_model_sec=31.9281`, `total_elapsed_sec=124.4674`.
- Post-gates passed for this single reviewed table case:
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, `expected_cell_count=48`, `reported_cell_count=48`, `valid_cell_count=48`
  - `named_fact_gate_pass=true`, `unsupported_token_count=0`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`, skipped by rubric for this table case
  - `ledger_unit_gate_pass=true`, `pass_count=98`, `fail_count=0`
  - `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`
- This run intentionally skipped trap, gold-vs-pipeline, and answer-vs-Judgment-Plan gates because it was a hardware/profile smoke on one non-trap case.

## Experiment Governance
- Hypothesis: 32GB RTX 5090 can run the reviewed10 table synthesis with larger 65k resident context when Blackwell-specific vLLM runtime toggles are applied at the profile layer.
- Decision target: Qwen output must be real model output, parse successfully, hit 48/48 table cells, and pass deterministic single-case gates with no ledger repair or fallback answer.
- Ceiling / upper bound: This proves 5090 profile viability for one reviewed10 table case only. It is not a full reviewed10 + 2 trap bundle run on 5090 and not a full noisy benchmark.
- Baselines to beat: prior 4090 reviewed10 table bundle passed; prior 5090 import workaround using `python -O` was unsafe because it disabled vLLM asserts.
- Split and leakage guard: Uses the existing reviewed10 table case, reviewed ledger, and pipeline trace. No new evaluation labels were created.
- Decision label: diagnostic-only proceed for using `rtx5090_32gb` on the next bounded SEC benchmark run.
- Mainline decision: Keep reviewed10 + 2 trap bundle as the current case-filtered diagnostic baseline; 5090 is now available as an execution profile after this smoke.

## Runtime Efficiency
- Hardware: NVIDIA GeForce RTX 5090, 32607 MiB VRAM, driver `580.76.05`, compute capability `sm_120`.
- Package stack observed by env checker: Python `3.12.3`, torch `2.11.0+cu130`, CUDA build `13.0`, vLLM `0.21.0`.
- vLLM runtime notes from log: model weights loaded in about 4.34 seconds inside engine, model memory footprint about 16.8 GiB, available KV cache memory about 10.78 GiB, GPU KV cache size 342,528 tokens, maximum concurrency for 65,536 tokens about 5.23x.
- First long prompt had expected Triton JIT compile latency; measured total single-case elapsed time was 124.4674 seconds.

## Root Cause And Safety Notes
- Plain `from vllm import LLM` failed on this torch/vLLM stack with a torch inductor duplicate-template assertion.
- `python -O` / `PYTHONOPTIMIZE=1` can make the import pass, but it is unsafe here because vLLM relies on Python asserts for Qwen3.5 hybrid KV-cache grouping. Disabling asserts caused a `MambaSpec` / full-attention backend mismatch during generation.
- Correct workaround for this host is `TORCHDYNAMO_DISABLE=1` while keeping Python asserts enabled, plus `VLLM_USE_FLASHINFER_SAMPLER=0` until FlashInfer sampler sm_120 behavior is validated.
- The historical `rtx4090_24gb` profile remains in `configs/vllm_hardware_profiles.json` for rollback.

## Caveats And Next Step
- Not run: full reviewed10 + 2 trap bundle on 5090, 27B 4bit feasibility, new v1.1 reviewed cases, or full noisy benchmark.
- Next decision: proceed below Answer Plan with reviewed-gold expansion, starting from the seed cases already scaffolded, while using the 5090 profile only after passing per-run gates.
