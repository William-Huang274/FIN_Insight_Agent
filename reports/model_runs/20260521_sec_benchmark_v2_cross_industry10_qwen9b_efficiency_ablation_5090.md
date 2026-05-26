# Model Run: 20260521_sec_benchmark_v2_cross_industry10_qwen9b_efficiency_ablation_5090

## Summary
- Purpose: Test whether turning off `enforce_eager` improves RTX 5090 Qwen9B synthesis throughput on a 3-case cross-industry subset.
- Status: completed with variant failure.
- Run type: inference efficiency ablation.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: remote cloud RTX 5090 host, NVIDIA GeForce RTX 5090 32GB, vLLM 0.21.0, Qwen3.5-9B FP16.

## Code And Command
- Entry point: `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
- Code change: added `--enforce-eager/--no-enforce-eager` CLI flag; default remains `--enforce-eager`.
- Source trace: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_pipeline_context_bge_m3_top160_object8_cloud`
- Cases: `JPM_BANK_SEGMENTS_RATE_CREDIT_RISK_2025_001`, `V_NET_REVENUE_PROCESSED_TRANSACTIONS_2023_2025_001`, `JNJ_INNOVATIVE_MEDICINE_MEDTECH_SCOPE_2025_001`
- Log: `reports/logs/20260520_v2_cross_industry10_qwen9b_efficiency_ablation_5090.log`
- Status: `reports/logs/20260520_v2_cross_industry10_qwen9b_efficiency_ablation_5090.status`

## Inputs
- Cases path: `eval/sec_cases/test_cases_v2_cross_industry10_seed.jsonl`
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v2_cross_industry10_reviewed_exact_value_ledger.json`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_cross_industry10_judgment_plans_trace_seed_cloud.json`
- Model path: `data/models_private/modelscope/Qwen/Qwen3___5-9B`

## Model Parameters
- Model: Qwen3.5-9B via vLLM.
- Dtype: FP16.
- `max_model_len=32768` for this ablation.
- `max_num_seqs=1`.
- Control variant: `enforce_eager=True`.
- Test variant: `enforce_eager=False`.
- Runtime env inherited from RTX 5090 hardware profile unless explicitly overridden.

## Outputs
- Control output: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_qwen9b_efficiency_control_eager32768`
- Test output: no completed output; engine failed before inference.

## Results
- Control variant:
  - `trace_count=3`
  - `agent_output_count=3`
  - `answer_status_counts={"answered_qwen9b":3}`
  - `load_model_sec=33.7511`
  - `total_elapsed_sec=126.3076`
- Test no-eager variant:
  - Status: failed during vLLM engine initialization.
  - Root cause: PyTorch Inductor raised `AssertionError: duplicate template name` while importing `torch._inductor.kernel.flex_attention`.
  - Runner status: `completed_with_variant_failure`.

## Efficiency Diagnosis
- The no-eager route cannot currently be promoted because it fails before model load completes.
- Combined40 logs show FA2 and Triton/FLA kernels are already active under the working eager profile.
- Current throughput issue is mainly runner shape: one prompt per `llm.generate([prompt])` call and `max_num_seqs=1`.
- Practical next optimization: implement a batched synthesis path that collects multiple prompts per vLLM call, then compare 3-case and 10-case wall time before running full combined40 again.

## Governance
- Decision label: diagnostic-only.
- Hypothesis: disabling eager may enable torch.compile/CUDA Graphs and improve throughput.
- Decision target: no-eager variant must initialize cleanly and improve wall time without changing answer/gate behavior.
- Result: target not met; no-eager blocked by environment/runtime bug.
- Stop/proceed: stop no-eager tuning on this stack; proceed with batching refactor or vLLM/torch stack research before retesting no-eager.

## Safety Notes
- No secrets are stored in this run ledger.
- Failed no-eager metrics must not be used as a serving baseline.
