# SEC Benchmark v2 Combined40 Cloud Gates And Efficiency Ablation

Date: 2026-05-21

## Scope

本轮把 `new20_mixed` 30 cases 和 `cross_industry10` 10 cases 合并为 `combined40`，在云端执行完整链路：

- BGE-M3 pipeline context trace
- trace-aware Judgment Plan
- RTX 5090 Qwen9B resident vLLM synthesis
- deterministic post-gates
- 独立效率 ablation：`enforce_eager=True` control vs `--no-enforce-eager`

目标是把 cloud gate 和效率优化拆开看：先确认 combined40 的质量门是否全绿，再确认当前慢在哪里。

## Artifacts

- Combined cases: `eval/sec_cases/test_cases_v2_combined40_seed.jsonl`
- Review approval: `reports/quality/sec_benchmark_v2_combined40_review_approval.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_combined40_reviewed_exact_value_ledger.json`
- BGE trace: `eval/sec_cases/outputs/run_20260520_v2_combined40_pipeline_context_bge_m3_top160_object8_cloud`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_combined40_judgment_plans_trace_seed_cloud.json`
- Original Qwen output: `eval/sec_cases/outputs/run_20260520_v2_combined40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Original post-gates: `reports/quality/cloud_v2_combined40_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates`
- Alias-fix raw replay output: `eval/sec_cases/outputs/run_20260521_v2_combined40_qwen9b_raw_replay_company_alias_fix_cloud`
- Final alias-fix post-gates: `reports/quality/cloud_v2_combined40_qwen9b_raw_replay_company_alias_fix_post_gates/sec_benchmark_post_gates_summary.json`
- Efficiency control: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_qwen9b_efficiency_control_eager32768`
- Efficiency logs: `reports/logs/20260520_v2_cross_industry10_qwen9b_efficiency_ablation_5090.log`

## Entry Gates

- Combined manifest: 40 cases.
- Approved non-trap cases: 36.
- Trap cases: 4.
- Mainline gold gate: 40/40 pass.
- Trap gold gate: 4/4 pass, 36 skipped.
- Exact-value ledger: 247 rows.
- Ledger-unit gate: 247/247 pass.
- BGE-M3 context trace: 40/40 `context_prepared`.
- Trace-aware Judgment Plan: 29 plans; validation 29/29 pass.
- Judgment Plan warnings: 47 `supporting_evidence_id_not_seen_in_trace`, non-blocking and caused by provenance IDs not always appearing verbatim in final BGE trace rows.

## Cloud Qwen9B Result

Original inference run:

- 40/40 outputs.
- 36/36 eligible non-trap outputs were `answered_qwen9b`.
- 4/4 trap outputs were `answered_contract_fallback`.
- `qwen_answer_ratio=1.0` when traps are excluded.
- Total elapsed: 1586.4576 sec.
- Model/input load timing: `load_inputs_sec=0.1086`, `load_model_sec=33.4068`.
- Qwen non-trap case elapsed: min 23.6282 sec, median 39.6698 sec, mean 42.9837 sec, max 98.7325 sec.
- Positive vLLM output speed from logs: min 35.92 tok/s, median 39.67 tok/s, mean 39.63 tok/s, max 40.94 tok/s.

The model did use accelerated attention paths:

- vLLM log reports `Using FlashAttention version 2`.
- vLLM log reports `Using Triton/FLA GDN prefill kernel`.
- FlashInfer sampler is disabled by profile via `VLLM_USE_FLASHINFER_SAMPLER=0`.
- `enforce_eager=True` disables torch.compile and CUDA Graphs.
- Current runner still calls `llm.generate([prompt])` one case at a time; `max_num_seqs=1` and the Python loop keep throughput bounded even when FA2/FLA kernels are active.

## Gate Fix

The first post-gate pass had one failure:

- Gate: `v2_semantic_contract_gate`.
- Case: `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`.
- Failure type: `entity_bleed_between_peers`.
- Root cause: deterministic named-fact sanitizer generalized an in-scope company name (`NVIDIA`) to `相关命名标签`, so the later peer semantic gate saw an AMD-only text span with both AMD and NVDA evidence IDs.

Fix:

- Updated `scripts/run_sec_eval_synthesis_qwen9b_backend.py` to ignore company aliases for tickers present in the current context rows during named-fact sanitization.
- Updated `scripts/validate_sec_benchmark_named_fact_support.py` to use the same company-alias ignore policy in the named-fact gate.
- Replayed the existing raw model outputs through deterministic normalization only; no new LLM inference was run.

Alias-fix raw replay:

- Output dir: `eval/sec_cases/outputs/run_20260521_v2_combined40_qwen9b_raw_replay_company_alias_fix_cloud`
- `trace_count=40`, `agent_output_count=40`.
- `answer_status_counts={"answered_qwen9b":36,"answered_contract_fallback":4}`.
- Total elapsed: 4.0181 sec.

## Final Post-Gates

Final post-gates directory: `reports/quality/cloud_v2_combined40_qwen9b_raw_replay_company_alias_fix_post_gates`.

- `qwen_answer_ratio=1.0`
- `qwen_answer_gate_pass=true`
- `trap_gate_pass=true`
- `answer_ledger_gate_pass=true`
- `metric_role_term_gate_pass=true`
- `table_cell_gate_pass=true`
- `named_fact_gate_pass=true`
- `ledger_missing_consistency_gate_pass=true`
- `abstract_judgment_gate_pass=true`
- `caveat_claim_gate_pass=true`
- `v2_semantic_contract_gate_pass=true`
- `answer_vs_judgment_plan_gate_pass=true`
- `metric_source_grounding_gate_pass=true`
- `ledger_unit_gate_pass=true`
- Mean score pct: 0.884.
- Answer ledger: 40/40 pass, 127 exact-value hits.
- Table-cell gate: 2 table cases checked, 48/48 expected cells reported and valid.
- Named-fact gate: 36/36 non-trap pass, 220 named tokens, 0 unsupported, 0 warnings.
- Caveat/claim gate: 57/57 required caveats covered, 0/71 disallowed claim violations.
- Semantic contract gate: 40/40 pass.
- Answer-vs-Judgment-Plan gate: 29/29 checked pass.
- Metric-source grounding: 36/36 non-trap pass, 419 metric references checked.
- Ledger-unit: 247/247 pass.

## Efficiency Ablation

Control variant:

- Run: `run_20260520_v2_cross_industry10_qwen9b_efficiency_control_eager32768`
- 3-case subset: `JPM`, `V`, `JNJ`.
- `trace_count=3`, `agent_output_count=3`.
- `answer_status_counts={"answered_qwen9b":3}`.
- `load_model_sec=33.7511`.
- `total_elapsed_sec=126.3076`.

No-eager variant:

- Variant: `test_noeager32768`.
- Status: failed at vLLM engine initialization.
- Root cause: PyTorch Inductor import path hit `AssertionError: duplicate template name` in `torch._inductor.kernel.flex_attention`.
- Status file: `reports/logs/20260520_v2_cross_industry10_qwen9b_efficiency_ablation_5090.status` records `completed_with_variant_failure`.

Efficiency interpretation:

- The current slow wall time is not because FA2/FLA is absent; logs show FA2 and Triton/FLA kernels are active.
- The immediate bottleneck is runner shape: sequential single-prompt generation plus `enforce_eager=True`.
- Disabling eager is not currently viable on this torch/vLLM stack because the no-eager variant fails before inference.
- The next practical optimization is a bounded batching refactor: collect multiple prompts and call `llm.generate(prompts)` with `max_num_seqs>1`, then rerun a 3-case and 10-case profile before changing the mainline runner.

## Decision

Combined40 is now a valid diagnostic cloud gate result: 40/40 outputs, 36/36 eligible Qwen answers, 4/4 traps refused by contract fallback, and all deterministic gates green after deterministic company-alias sanitizer fix.

This supports using the current BGE-M3 + Judgment Plan + Qwen9B route as the regression baseline before adding more SEC companies. It does not prove serving efficiency is production-ready; batching and/or a fixed no-eager stack remain required before claiming latency/throughput readiness.

## Safety Notes

- No SSH password, token, or temporary credential was written to repo files.
- Remote artifacts were synchronized back to local under the same repository-relative paths.
- The alias-fix replay uses existing raw model outputs; it changes deterministic normalization and gate behavior, not model inference content.
