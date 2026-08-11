# Model Run: 20260519_sec_benchmark_v1_1_reviewed4_bge_m3_qwen9b_5090

## Summary

- Purpose: 将 ADS/AI infrastructure growth-quality case 收入 v1.1 reviewed4，并验证 BGE-M3 pipeline-context + RTX 5090 true-Qwen synthesis 是否能通过当前 deterministic gates。
- Status: diagnostic-only completed
- Run type: reviewed artifact build + retrieval trace + BGE cross-encoder rerank + cloud inference + deterministic post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus cloud RTX 5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮主要涉及 reviewed4 gold artifacts, BGE trace/output dirs, `scripts/build_sec_benchmark_v1_1_reviewed_gold.py`, `scripts/run_sec_benchmark_eval.py`, `scripts/run_sec_eval_synthesis_qwen9b_backend.py`, `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`, model-run ledger, and worklog。
- Remote backups:
  - `.tmp_remote_backups/20260519_reviewed4_bge_backup`
  - `.tmp_remote_backups/20260519_reviewed4_named_fact_fix`
- Commands, with credentials omitted:

```bash
python scripts/build_sec_benchmark_v1_1_reviewed_gold.py

python scripts/build_sec_benchmark_exact_value_ledger.py \
  --approval-path reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json \
  --output-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json

python scripts/validate_sec_gold_gate.py \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --approval-path reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json \
  --output-path reports/quality/sec_benchmark_v1_1_gold_gate_reviewed4_semiconductor_capex_subscription_ads_ai_infra.json

python scripts/validate_sec_benchmark_ledger_units.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --output-path reports/quality/sec_benchmark_v1_1_reviewed4_ledger_unit_gate.json

python scripts/validate_sec_benchmark_derived_metrics.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --output-path reports/quality/sec_benchmark_v1_1_reviewed4_derived_metric_gate.json \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001

python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_context_bge_m3_top160_object8_local \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --case-id SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001 \
  --case-id ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001 \
  --evidence-top-k 30 \
  --object-top-k 8 \
  --max-context-rows 160 \
  --context-reranker bge \
  --context-reranker-model BAAI/bge-reranker-v2-m3 \
  --context-reranker-top-k 160

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_namedfix \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --case-id SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001 \
  --case-id ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_displayfix \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_displayfix \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --output-dir reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_qwen9b_5090_sanitized_displayfix_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --skip-trap-gate \
  --skip-gold-vs-pipeline-gate \
  --skip-answer-vs-judgment-plan-gate \
  --min-qwen-answer-ratio 1.0

python scripts/build_sec_benchmark_judgment_plan.py \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --case-id SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001 \
  --case-id ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001 \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v1_1_reviewed4_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v1_1_reviewed4_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_sanitized \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_1_reviewed4_judgment_plans_trace_seed.json \
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 \
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 \
  --case-id SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001 \
  --case-id ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001 \
  --hardware-profile rtx5090_32gb \
  --structured-json

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_vllm_5090_planfix \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_vllm_5090_planfix \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_1_reviewed4_judgment_plans_trace_seed.json \
  --output-dir reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_5090_planfix_post_gates \
  --skip-trap-gate \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases:
  - `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
  - `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
  - `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
  - `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`
- Cases path: `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- BGE reranker: `BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs

- BGE pipeline trace: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_context_bge_m3_top160_object8_local`
- Superseded first true-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized`
- Intermediate true-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_namedfix`
- Final displayfix output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_displayfix`
- Final post-gates: `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_qwen9b_5090_sanitized_displayfix_post_gates/sec_benchmark_post_gates_summary.json`
- Derived metric gate: `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_qwen9b_5090_sanitized_displayfix_post_gates/sec_benchmark_derived_metric_gate.json`
- Trace-aware Judgment Plan seed: `reports/evidence_packs/sec_benchmark_v1_1_reviewed4_judgment_plans_trace_seed.json`
- Plan-injected true-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_sanitized`
- Final planfix output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_vllm_5090_planfix`
- Final planfix post-gates: `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_5090_planfix_post_gates/sec_benchmark_post_gates_summary.json`
- Audit report: `docs/worklog/91_sec_benchmark_v1_1_reviewed4_ads_bge_m3_audit.md`
- Runtime log: `reports/logs/20260519_reviewed4_bge_m3_qwen9b_5090_synthesis_namedfix.log`

## Results

- Reviewed gold gate passed 4/4.
- Exact-value ledger rebuilt to 69 rows.
- Ledger-unit gate passed 69/69.
- CAPEX/FCF derived metric gate passed 12/12.
- BGE trace prepared 4/4 cases with `effective_context_reranker=bge`, `context_reranker_model=BAAI/bge-reranker-v2-m3`, and `bm25_only_allowed_for_this_run=false`.
- True-Qwen synthesis answered 4/4 with no fallback and no ledger repair.
- Clean displayfix post-gate summary:
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`, exact-value hits 18
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, 36/36 valid cells
  - `named_fact_gate_pass=true`, unsupported token count 0
  - `ledger_missing_consistency_gate_pass=true`, false missing count 0
  - `ledger_unit_gate_pass=true`, 69/69 pass
  - `abstract_judgment_gate_pass=true`, skipped 4/4 because no abstract rubrics yet
  - CAPEX/FCF derived metric gate: 12/12 pass
- Trace-aware Judgment Plan seed:
  - plan gate 4/4 pass, 12 drivers, `can_enter_gate=true`
  - validator now allows qualitative supporting evidence from the active BGE-M3 trace, not only exact-value ledger source rows
  - support selection is criterion/topic bounded; the earlier broad top-trace fallback was removed
  - remaining plan warnings: 8 reviewed-ledger source evidence IDs are not present in the BGE trace, but are accepted through the ledger support path
- Plan-injected true-Qwen synthesis:
  - answered 4/4 with no fallback and no ledger repair
  - total elapsed 289.1818 sec; model load 39.0119 sec
  - per-case elapsed: semiconductor 35.1445 sec, CAPEX/FCF 95.1471 sec, subscription 51.9829 sec, ADS 67.7125 sec
- Final planfix post-gate summary:
  - `qwen_answer_ratio=1.0`
  - `answer_vs_judgment_plan_gate_pass=true`, 4/4 pass
  - `answer_ledger_gate_pass=true`, 4/4 pass, exact-value hits 20
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, 36/36 valid cells
  - `named_fact_gate_pass=true`, unsupported token count 0, warning count 0
  - `ledger_missing_consistency_gate_pass=true`, false missing count 0
  - `ledger_unit_gate_pass=true`, 69/69 pass
  - CAPEX/FCF derived metric gate: 12/12 pass

## Experiment Governance

- Hypothesis: BGE-M3 final selection over BM25/ObjectBM25 candidates should keep the reviewed v1.1 context pack complete enough for true-Qwen synthesis when the ADS/AI infrastructure case is added.
- Decision target: reviewed4 run must keep qwen answer ratio at 1.0 and pass ledger, metric-role, table-cell, named-fact, missing-consistency, ledger-unit, and CAPEX derived-metric gates.
- Ceiling / upper bound: This is a four-case reviewed diagnostic run. It is not a full noisy benchmark or v2 generalization proof.
- Baselines to beat: reviewed3 BGE-M3 path; BM25-only is not accepted as a final selector except explicit ablation.
- Split and leakage guard: Uses project-reviewed SEC-only 10-K artifacts. No external data source was introduced.
- Stop conditions: Any false missing, unsupported named fact, table-cell failure, ledger-unit failure, or Qwen fallback blocks promotion.
- Efficiency gate: Single RTX 5090 32GB, Qwen9B resident vLLM, no CPU offload; case-filtered run should remain within a few minutes.
- Decision label: diagnostic-only proceed.
- Mainline decision: BGE-M3 remains fixed as the SEC benchmark pipeline-context selector.
- Answer Plan decision: trace-aware Judgment Plan plus deterministic planfix binding is the current continuation path; ledger-only Judgment Plan was too narrow for qualitative SEC caveats.

## Runtime Efficiency

- Qwen final run total elapsed: 292.8049 sec
- Model load: 32.0934 sec
- Per-case elapsed:
  - Semiconductor durability: 52.4232 sec
  - CAPEX/FCF table: 76.0179 sec
  - Subscription visibility: 70.27 sec
  - ADS/AI infrastructure: 61.9382 sec
- GPU profile: RTX 5090 32GB, `max_model_len=65536`, `max_tokens=6000`, `gpu_memory_utilization=0.92`, `max_num_seqs=1`, `dtype=float16`
- GPU KV cache: 342,528 tokens; available KV cache memory: 10.78 GiB
- Runtime caveat: vLLM still reports `SM 12.x requires CUDA >= 12.9`; this compatibility warning did not block the run under the current profile.

## Caveats And Next Step

- Skipped by design for the displayfix baseline: trap gate, gold-vs-pipeline gate, and answer-vs-Judgment-Plan gate.
- First non-namedfix output is superseded because named-fact gate caught unsupported `NRR` and `Evidence Text` tokens in the subscription case.
- These v1.1 cases do not yet carry abstract rubrics, so the abstract judgment gate is structurally skipped.
- Deterministic displayfix changed 1 agent output row to clean nested negative-capex parentheses while preserving metric-id support; all post-gates still pass.
- Deterministic planfix changed 4 agent output rows to bind answer prose to the trace-aware Judgment Plan; all post-gates, including answer-vs-plan, pass.
- Deterministic support clamp now keeps generated answer support IDs, strength, and caveats within the matched plan driver; auto-added ledger boundary key_points cite only the selected metrics' ledger source evidence.
- Next step: add v2 required-caveat/disallowed-claim validators and then create a small v2 pilot manifest.
