# 20260520 SEC Benchmark v2 Cross-Industry10 BGE-M3 Qwen9B 5090 Cloud

Date: 2026-05-20

Type: cloud BGE-M3 retrieval trace + Judgment Plan + RTX 5090 Qwen9B inference + deterministic post-gates

Status: diagnostic-only completed

## Summary

Built a 10-case cross-industry SEC benchmark slice covering `JPM/V/JNJ/LLY/CAT/GE/WMT/PG/XOM/CVX`, then ran it through cloud BGE-M3 context retrieval, trace-aware Judgment Plan, and Qwen3.5-9B vLLM synthesis on RTX 5090. All active deterministic post-gates passed with `qwen_answer_ratio=1.0`.

## Code And Command

- Entry point: `.tmp_remote_diag/run_cross_industry10_pipeline_remote.sh`
- Main local builders:
  - `scripts/build_sec_benchmark_v2_cross_industry10_seed.py`
  - `scripts/build_sec_benchmark_v2_cross_industry10_reviewed_gold.py`
- BGE command profile: `run_sec_benchmark_eval.py --mode pipeline_context --context-reranker bge --context-reranker-model /root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3 --object-top-k 8 --evidence-top-k 4 --max-context-rows 160`
- Qwen command profile: `run_sec_benchmark_vllm_synthesis_from_traces.py --hardware-profile rtx5090_32gb --structured-json`
- Post-gates: `run_sec_benchmark_post_gates.py --skip-trap-gate --skip-gold-vs-pipeline-gate --min-qwen-answer-ratio 1.0`
- Code state: dirty worktree; no commit made.
- Secrets: no SSH password or token written to repo files.

## Inputs

- Case manifest: `eval/sec_cases/test_cases_v2_cross_industry10_seed.jsonl`
- Review approval: `reports/quality/sec_benchmark_v2_cross_industry10_review_approval.json`
- Reviewed context/facts: `eval/sec_cases/reviewed_gold_context`, `eval/sec_cases/reviewed_gold_facts`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_cross_industry10_reviewed_exact_value_ledger.json`
- Abstract rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`
- SEC corpus/index profile: 30-company cloud corpus with BM25/ObjectBM25 indexes and BGE-M3 final selector.
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs

- BGE trace: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_pipeline_context_bge_m3_top160_object8_cloud`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_cross_industry10_judgment_plans_trace_seed_cloud.json`
- Judgment Plan validation: `reports/quality/sec_benchmark_v2_cross_industry10_judgment_plan_trace_seed_validation_cloud.json`
- Qwen output: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Post-gates: `reports/quality/cloud_v2_cross_industry10_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`
- Log: `reports/logs/20260520_v2_cross_industry10_bge_m3_judgment_plan_qwen9b_5090_cloud.log`

## Results

- Reviewed-gold entry gates:
  - 10 reviewed cases, 62 reviewed context rows, 39 exact facts.
  - mainline gold gate: 10/10 pass.
  - ledger-unit gate: 39/39 pass.
- BGE-M3 trace: 10/10 `context_prepared`, about 44 sec.
- Judgment Plan: 6 numeric plans, 6 drivers, validation 6/6 pass; 4 text-only cases skipped by design.
- Qwen9B:
  - 10/10 `answered_qwen9b`
  - 0 fallback outputs
  - 0 ledger repairs
  - total elapsed 366.7974 sec
  - model load phase 57.2505 sec
  - per-case generation range 25.0135-39.5535 sec
  - output speed about 39-40 tokens/sec after warmup
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - answer-ledger 10/10, 26 exact-value hits
  - metric-role term 10/10
  - named-fact 10/10, 65 named tokens, 0 unsupported
  - ledger-missing false missing count 0
  - caveat/claim 10/10, 10/10 required caveats, 0/10 disallowed violations
  - v2 semantic 10/10
  - answer-vs-plan 6/6 checked
  - metric-source grounding 10/10, 74 metric references
  - ledger-unit 39/39

## Runtime Efficiency

- BGE-M3 stage wall time: about 44 sec.
- Qwen synthesis total elapsed: 366.7974 sec.
- vLLM reported model memory after load: 16.8 GiB.
- vLLM reported available KV cache memory: 10.78 GiB and 342,528 GPU KV-cache tokens for the 65,536-token profile.
- Primary latency bottleneck remains single-case sequential Qwen generation plus cold-start load/JIT; batching is intentionally constrained by `max_num_seqs=1` for RTX 5090 headroom.

## Experiment Governance

- Hypothesis: adding non-tech SEC disclosure styles should still pass the locked BGE-M3 + Judgment Plan + Qwen9B route if reviewed context/facts and ledger units are sound.
- Decision target: 10/10 Qwen answers, no fallback or ledger repair, and all active deterministic gates pass.
- Result: target met.
- Ceiling: this is a 10-case slice, not a combined regression pack with old cases and traps.
- Mainline decision: diagnostic-only proceed to mixed-pack regression.

## Caveats And Next Step

- Trap gate and gold-vs-pipeline gate were skipped by design for this non-trap pipeline-context-only slice.
- Abstract judgment gate skipped all 10 because no abstract-rubric entries exist for this slice.
- Next decision: build a mixed pack combining prior original/new20 regression cases, this cross-industry10 slice, and traps; then rerun cloud BGE-M3/Qwen post-gates.
