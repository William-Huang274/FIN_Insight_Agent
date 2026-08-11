# Model Run: 20260519_sec_benchmark_v1_1_reviewed2_bge_pipeline_5090

## Summary
- Purpose: 将 v1.1 reviewed2 的 Semiconductor Durability 与 CAPEX/FCF table case 跑通 pipeline-context true-Qwen，并把 BGE reranker 接入当前 SEC benchmark context pack 路径。
- Status: diagnostic-only completed
- Run type: retrieval trace + BGE cross-encoder rerank + cloud inference + deterministic post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus cloud RTX 5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command
- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮主要涉及 `scripts/run_sec_benchmark_eval.py`, `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`, `scripts/run_sec_eval_synthesis_qwen9b_backend.py`, v1.1 outputs, quality reports, model-run ledger, and worklog。
- Main commands:

```bash
python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_context_bge_top120 \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --evidence-top-k 30 \
  --object-top-k 30 \
  --max-context-rows 120 \
  --context-reranker bge \
  --context-reranker-model /root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3 \
  --context-reranker-device cuda \
  --context-reranker-batch-size 8 \
  --context-reranker-top-k 120

python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_context_bge_top120 \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_bge_qwen9b_vllm_5090_tableprompt3 \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --hardware-profile rtx5090_32gb \
  --structured-json \
  --max-tokens 4096

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_bge_qwen9b_vllm_5090_tableprompt3 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_bge_qwen9b_vllm_5090_tableprompt3 \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --output-dir reports/quality/local_v1_1_reviewed2_pipeline_bge_qwen9b_5090_tableprompt3_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --skip-trap-gate \
  --skip-gold-vs-pipeline-gate \
  --skip-answer-vs-judgment-plan-gate \
  --min-qwen-answer-ratio 1.0

python scripts/validate_sec_benchmark_derived_metrics.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --output-path reports/quality/local_v1_1_reviewed2_pipeline_bge_qwen9b_5090_tableprompt3_post_gates/sec_benchmark_derived_metric_gate.json \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001
```

## Inputs
- Cases:
  - `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
  - `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
- Cases path: `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
- Reviewed v1.1 ledger: `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- BGE reranker: `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs
- BGE pipeline trace: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_context_bge_top120`
- True-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed2_pipeline_bge_qwen9b_vllm_5090_tableprompt3`
- Post-gates: `reports/quality/local_v1_1_reviewed2_pipeline_bge_qwen9b_5090_tableprompt3_post_gates/sec_benchmark_post_gates_summary.json`
- Derived FCF gate: `reports/quality/local_v1_1_reviewed2_pipeline_bge_qwen9b_5090_tableprompt3_post_gates/sec_benchmark_derived_metric_gate.json`

## Results
- BGE context trace prepared 2/2 cases with 120 reranked context rows per case.
- Semiconductor trace includes both previously missing/important target sources:
  - `AMD_2025_10K_ITEM8_BLOCK_0005_PART_01_OF_02`
  - `NVDA_2025_10K_ITEM7_BLOCK_0008_CHUNK_0001`
- True-Qwen synthesis answered 2/2, with `answer_status_counts={"answered_qwen9b":2}` and no ledger repair or fallback answers.
- Post-gate summary:
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, `expected_cell_count=36`, `reported_cell_count=36`, `valid_cell_count=36`
  - `named_fact_gate_pass=true`, `unsupported_token_count=0`
  - `ledger_missing_consistency_gate_pass=true`
  - `ledger_unit_gate_pass=true`, `pass_count=42/42`
  - `abstract_judgment_gate_pass=true`, skipped 2/2 because these v1.1 cases do not yet have abstract rubrics
  - `gold_mean_score_pct=0.88`
- CAPEX/FCF derived metric gate passed `12/12`.

## Experiment Governance
- Hypothesis: The current reviewed SEC benchmark runner should use BM25/ObjectBM25 only as a broad first-stage candidate source, then use BGE reranker to select and order the final evidence pack before Qwen synthesis.
- Decision target: case-filtered v1.1 reviewed2 run must keep true-Qwen answer ratio at 1.0 and pass ledger, metric-role, table-cell, named-fact, missing-consistency, ledger-unit, and derived-metric gates.
- Ceiling / upper bound: This is not a full noisy benchmark and not a generalization claim. It validates the BGE-reranked pipeline path on two reviewed v1.1 cases only.
- Baselines to beat: Earlier BM25-order pipeline run passed structural gates but missed semantically important customer-concentration evidence in the prompt pack and produced a false “not provided” limitation.
- Split and leakage guard: Uses reviewed v1.1 gold artifacts and SEC-only local/cloud indexed evidence. No new external data source or credential is written.
- Stop conditions: If BGE rerank failed to bring reviewed target sources into the prompt pack or any post-gate failed, do not promote this path; inspect candidate coverage and table prose support first.
- Decision label: diagnostic-only proceed.
- Mainline decision: BGE reranker should be the selector for SEC benchmark pipeline context; BM25 remains a candidate generator, not the final ranking policy.

## Runtime Efficiency
- BGE trace run: context-only; no model synthesis invoked.
- Qwen run: model load `41.1862s`, total elapsed `197.3368s`.
- Per-case synthesis elapsed:
  - Semiconductor: `56.3628s`
  - CAPEX/FCF table: `99.7532s`
- GPU profile: RTX 5090 32GB, `max_model_len=65536`, `gpu_memory_utilization=0.92`, `max_num_seqs=1`, `dtype=float16`.
- Runtime caveat: current vLLM stack still emits Blackwell capability warnings about CUDA 12.9 support, but this run completed successfully under the `rtx5090_32gb` compatibility profile.

## Caveats And Next Step
- Skipped by design: trap gate, gold-vs-pipeline gate, answer-vs-Judgment-Plan gate. This run only contains two v1.1 reviewed non-trap cases.
- Table-case prose was canonicalized so company/year/value/citation facts live in `cell_table.cells`; this prevents named-fact failures caused by Qwen mixing several company names in one driver while citing only partial evidence.
- Next step: review and gate additional v1.1/v2 pilot cases before claiming generalization, with priority on SaaS/security subscription visibility and ads/AI infrastructure growth-quality comparison.
