# Model Run: 20260521_sec_benchmark_v2_combined40_bge_m3_qwen9b_5090_cloud_aliasfix

## Summary
- Purpose: Run the combined40 SEC benchmark through cloud BGE-M3 context, trace-aware Judgment Plan, RTX 5090 Qwen9B synthesis, and deterministic post-gates; repair the one deterministic alias-sanitizer gate failure without rerunning LLM inference.
- Status: completed.
- Run type: retrieval + inference + evaluation + deterministic raw replay.
- Timestamp: 2026-05-21 Asia/Shanghai.
- Environment: remote cloud RTX 5090 host, NVIDIA GeForce RTX 5090 32GB, vLLM 0.21.0, Qwen3.5-9B FP16.

## Code And Command
- Entry points:
  - `scripts/build_sec_benchmark_v2_combined40_pack.py`
  - `scripts/run_sec_benchmark_eval.py`
  - `scripts/build_sec_benchmark_judgment_plan.py`
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Key local code changes:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`: named-fact sanitizer now ignores company aliases for tickers present in context rows.
  - `scripts/validate_sec_benchmark_named_fact_support.py`: named-fact gate now applies the same in-context company alias ignore policy.
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`: exposes `--enforce-eager/--no-enforce-eager`.
- Seeds: deterministic generation, vLLM seed 0.

## Inputs
- Case manifest: `eval/sec_cases/test_cases_v2_combined40_seed.jsonl`
- Approved cases: `reports/quality/sec_benchmark_v2_combined40_review_approval.json`
- Reviewed context/facts: `eval/sec_cases/reviewed_gold_context`, `eval/sec_cases/reviewed_gold_facts`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_combined40_reviewed_exact_value_ledger.json`
- Abstract rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`
- BGE-M3 reranker: `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`
- Model path: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Data profile: 40 cases, 36 eligible non-trap cases, 4 trap cases.
- Leakage guard: SEC-only source policy; reviewed gold and exact-value ledger are deterministic inputs; traps excluded from qwen-answer ratio.

## Model Parameters
- Model: Qwen3.5-9B via vLLM.
- Dtype: FP16.
- Hardware profile: `rtx5090_32gb`.
- `max_model_len=65536`.
- `max_tokens=6000`.
- `gpu_memory_utilization=0.92`.
- `max_num_seqs=1`.
- `enforce_eager=True`.
- Structured JSON: enabled.
- Runtime env: `TORCHDYNAMO_DISABLE=1`, `VLLM_USE_FLASHINFER_SAMPLER=0`.

## Outputs
- BGE trace: `eval/sec_cases/outputs/run_20260520_v2_combined40_pipeline_context_bge_m3_top160_object8_cloud`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_combined40_judgment_plans_trace_seed_cloud.json`
- Original Qwen output: `eval/sec_cases/outputs/run_20260520_v2_combined40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Original post-gates: `reports/quality/cloud_v2_combined40_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates`
- Alias-fix replay output: `eval/sec_cases/outputs/run_20260521_v2_combined40_qwen9b_raw_replay_company_alias_fix_cloud`
- Final post-gates: `reports/quality/cloud_v2_combined40_qwen9b_raw_replay_company_alias_fix_post_gates/sec_benchmark_post_gates_summary.json`
- Log: `reports/logs/20260520_v2_combined40_bge_m3_judgment_plan_qwen9b_5090_cloud.log`

## Results
- BGE trace: 40/40 `context_prepared`.
- Judgment Plan: 29 plans; validation 29/29 pass.
- Original Qwen synthesis: 40/40 outputs; 36 `answered_qwen9b`, 4 `answered_contract_fallback`.
- Original inference total elapsed: 1586.4576 sec.
- Model load: 33.4068 sec.
- Qwen non-trap per-case elapsed: min 23.6282 sec, median 39.6698 sec, mean 42.9837 sec, max 98.7325 sec.
- Positive output TPS from vLLM log: min 35.92, median 39.67, mean 39.63, max 40.94 tok/s.
- Alias-fix raw replay: 40/40 outputs in 4.0181 sec.
- Final `qwen_answer_ratio=1.0`; 36/36 eligible Qwen answers, 0 eligible fallback, 0 ledger repairs, 4 traps excluded.
- Final mean score pct: 0.884.
- Final deterministic gates:
  - trap gate pass.
  - answer-ledger pass, 40/40, 127 exact-value hits.
  - metric-role term pass, 40/40.
  - table-cell pass, 48/48 cells valid.
  - named-fact pass, 220 named tokens, 0 unsupported.
  - ledger-missing consistency pass, false missing count 0.
  - abstract judgment pass, 47/47 required dimensions covered.
  - caveat/claim pass, 57/57 caveats covered, 0/71 disallowed violations.
  - v2 semantic contract pass, 40/40.
  - answer-vs-Judgment-Plan pass, 29/29.
  - metric-source grounding pass, 419 metric references checked.
  - ledger-unit pass, 247/247.

## Efficiency Diagnosis
- vLLM logs confirm `Using FlashAttention version 2` and `Using Triton/FLA GDN prefill kernel`.
- FlashInfer sampler is intentionally disabled.
- `enforce_eager=True` disables torch.compile and CUDA Graphs.
- Current runner is sequential: it sends one prompt per `llm.generate([prompt])` call, so GPU utilization is limited even with FA2/FLA active.
- Next optimization should batch multiple prompts and raise `max_num_seqs` in a controlled 3-case then 10-case profile.

## Governance
- Decision label: diagnostic mainline baseline for SEC benchmark v2 combined40.
- Hypothesis: adding cross-industry cases should preserve `qwen_answer_ratio=1.0` and all deterministic gates under the BGE-M3 + Judgment Plan + Qwen9B route.
- Decision target: 36 eligible non-trap cases all answered by Qwen9B, trap cases refused by contract fallback, and all post-gates pass.
- Result: target met after deterministic company-alias sanitizer fix.
- Stop/proceed: proceed to larger company expansion only with this combined40 pack as regression baseline; do not claim serving throughput readiness until batching/no-eager work is resolved.

## Safety Notes
- No secrets are stored in this run ledger.
- Alias-fix replay reuses raw model outputs and changes deterministic post-processing only.
