# Model Run: 20260519_sec_benchmark_v1_1_reviewed3_bge_m3_qwen9b_5090

## Summary

- Purpose: 将 v1.1 第三个 SaaS/security subscription visibility case 收入 reviewed gold，并验证 BGE-M3 reranked pipeline-context + RTX 5090 true-Qwen synthesis 是否能稳定通过当前 post-gates。
- Status: diagnostic-only completed
- Run type: reviewed artifact build + retrieval trace + BGE cross-encoder rerank + cloud inference + deterministic post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus cloud RTX 5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮主要涉及 reviewed3 gold artifacts, BGE trace/output dirs, `scripts/run_sec_eval_synthesis_qwen9b_backend.py`, `scripts/validate_sec_benchmark_ledger_missing_consistency.py`, model-run ledger, and worklog。
- Commands, with credentials omitted:

```bash
python scripts/build_sec_benchmark_v1_1_reviewed_gold.py

python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_context_bge_m3_top120_local \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --case-id SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001 \
  --evidence-top-k 30 \
  --object-top-k 30 \
  --max-context-rows 120 \
  --context-reranker bge \
  --context-reranker-model BAAI/bge-reranker-v2-m3 \
  --context-reranker-top-k 120

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_context_bge_m3_top120_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090_sanitized \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --case-id SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090_sanitized \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090_sanitized \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --output-dir reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --skip-trap-gate \
  --skip-gold-vs-pipeline-gate \
  --skip-answer-vs-judgment-plan-gate \
  --min-qwen-answer-ratio 1.0

/root/miniconda3/bin/python scripts/validate_sec_benchmark_derived_metrics.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --output-path reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates/sec_benchmark_derived_metric_gate.json \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001
```

## Inputs

- Cases:
  - `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
  - `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
  - `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
- Cases path: `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- BGE reranker: `BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs

- BGE pipeline trace: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_context_bge_m3_top120_local`
- Superseded first true-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090`
- Clean true-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090_sanitized`
- Clean post-gates: `reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates/sec_benchmark_post_gates_summary.json`
- Derived metric gate: `reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates/sec_benchmark_derived_metric_gate.json`
- Audit report: `docs/worklog/90_sec_benchmark_v1_1_reviewed3_bge_m3_audit.md`

## Results

- Reviewed gold gate passed 3/3.
- Exact-value ledger rebuilt to 51 rows.
- Ledger-unit gate passed 51/51.
- BGE trace prepared 3/3 cases with `effective_context_reranker=bge`, `context_reranker_model=BAAI/bge-reranker-v2-m3`, and `bm25_only_allowed_for_this_run=false`.
- True-Qwen synthesis answered 3/3 with no fallback and no ledger repair.
- Clean post-gate summary:
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, 36/36 valid cells
  - `named_fact_gate_pass=true`, unsupported token count 0
  - `ledger_missing_consistency_gate_pass=true`, false missing count 0
  - `ledger_unit_gate_pass=true`, 51/51 pass
  - `abstract_judgment_gate_pass=true`, skipped 3/3 because no abstract rubrics yet
- CAPEX/FCF derived metric gate passed 12/12.

## Experiment Governance

- Hypothesis: BGE-M3 final selection over BM25/ObjectBM25 candidates should keep the reviewed v1.1 context pack sufficiently complete for true-Qwen synthesis and deterministic gates when a third subscription-visibility case is added.
- Decision target: reviewed3 run must keep qwen answer ratio at 1.0 and pass ledger, metric-role, table-cell, named-fact, missing-consistency, ledger-unit, and CAPEX derived-metric gates.
- Ceiling / upper bound: This is a three-case reviewed diagnostic run. It is not a full noisy benchmark or v2 generalization proof.
- Baselines to beat: reviewed2 BGE-M3 path on semiconductor + CAPEX/FCF; earlier BM25-order pipeline is not accepted as final selector.
- Split and leakage guard: Uses project-reviewed SEC-only 10-K artifacts. No external data source was introduced.
- Stop conditions: Any false missing, unsupported named fact, table-cell failure, ledger-unit failure, or Qwen fallback blocks promotion.
- Efficiency gate: Single RTX 5090 32GB, Qwen9B resident vLLM, no CPU offload; per-run synthesis should remain in a few minutes for this case-filtered size.
- Decision label: diagnostic-only proceed.
- Mainline decision: BGE-M3 remains fixed as the SEC benchmark pipeline-context selector; BM25-only requires explicit ablation flag.

## Runtime Efficiency

- Qwen clean run total elapsed: 211.9695 sec
- Model load: 41.3767 sec
- Per-case elapsed:
  - Semiconductor durability: 42.7782 sec
  - CAPEX/FCF table: 82.0808 sec
  - Subscription visibility: 45.6796 sec
- GPU profile: RTX 5090 32GB, `max_model_len=65536`, `max_tokens=6000`, `gpu_memory_utilization=0.92`, `max_num_seqs=1`, `dtype=float16`
- Runtime caveat: vLLM still reports `SM 12.x requires CUDA >= 12.9`; this compatibility warning did not block the run under the current profile.

## Caveats And Next Step

- Skipped by design: trap gate, gold-vs-pipeline gate, and answer-vs-Judgment-Plan gate.
- First non-sanitized output is superseded because it contained a table-case false missing statement; the enhanced validator now catches that old output.
- These v1.1 cases do not yet carry abstract rubrics, so the abstract judgment gate is structurally skipped.
- Next step: add the ads/AI infrastructure growth-quality reviewed case, then add required-caveat and disallowed-claim validators before starting a broader v2 pilot.
