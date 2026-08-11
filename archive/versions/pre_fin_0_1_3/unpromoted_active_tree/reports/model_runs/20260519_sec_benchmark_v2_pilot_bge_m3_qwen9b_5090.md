# Model Run: 20260519_sec_benchmark_v2_pilot_bge_m3_qwen9b_5090

## Summary

- Purpose: run the reviewed v2 pilot through the locked BGE-M3
  pipeline-context route, trace-aware Judgment Plan prompt injection, RTX 5090
  true-Qwen synthesis, and deterministic post-gates.
- Status: diagnostic-only completed
- Run type: BGE-M3 retrieval trace + Judgment Plan seed + cloud inference +
  deterministic contractfix + post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote RTX
  5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Git commit: local workspace is dirty; remote path is not a git repo.
- Remote backup before sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_sync_before_qwen_195252`
- Remote backup before final contractfix script/ledger sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_contractfix_sync_201328`
- Commands, with credentials omitted:

```bash
python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_judgment_plan_trace_seed_report.json \
  --case-id META_REALITY_LABS_2024_001 \
  --case-id PANW_RPO_BILLINGS_NUMERIC_2023_2025_001 \
  --case-id GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001 \
  --case-id AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001 \
  --case-id AMD_SEGMENT_MIX_2023_2025_001 \
  --case-id MSFT_YOUTUBE_REVENUE_TRAP_001

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

python scripts/build_sec_benchmark_exact_value_ledger.py \
  --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts \
  --approval-path reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json \
  --output-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json

python scripts/validate_sec_benchmark_ledger_units.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --output-path reports/quality/sec_benchmark_v2_pilot_reviewed_ledger_unit_gate_after_metric_id_fix.json

python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_judgment_plan_trace_seed_report_after_metric_id_fix.json \
  --case-id META_REALITY_LABS_2024_001 \
  --case-id PANW_RPO_BILLINGS_NUMERIC_2023_2025_001 \
  --case-id GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001 \
  --case-id AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001 \
  --case-id AMD_SEGMENT_MIX_2023_2025_001 \
  --case-id MSFT_YOUTUBE_REVENUE_TRAP_001

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
- BGE trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_context_bge_m3_top160_object8_local`
- Ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json`
- BGE reranker: `BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs

- Raw Qwen output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- Final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4`
- Post-gates:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates/sec_benchmark_post_gates_summary.json`
- Expanded post-gates after validator-first semantic contract wiring:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates_v2semantic/sec_benchmark_post_gates_summary.json`
- Remote synthesis log:
  `reports/logs/20260519_v2_pilot_bge_m3_judgment_plan_qwen9b_5090_synthesis.log`
- Worklog audit:
  `docs/worklog/94_sec_benchmark_v2_pilot_bge_m3_qwen9b_5090_audit.md`

## Results

- BGE trace prepared 6/6 with BGE-M3 as final selector and
  `bm25_only_allowed=false`.
- Judgment Plan seed: 5 plans, 6 drivers, 1 trap skipped.
- Raw synthesis answer status:
  - `answered_qwen9b`: 5
  - `answered_contract_fallback`: 1
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap gate: pass
  - answer-ledger: pass, exact-value hits 27
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0
  - ledger-missing consistency: pass, false missing count 0
  - caveat/claim: pass, 11/11 caveats covered, 0/12 disallowed violations
  - v2 semantic contract: pass, 5/5 checked cases, 1 skipped
  - answer-vs-Judgment-Plan: pass, 5/5 checked cases
  - ledger-unit: pass, 40/40
  - abstract judgment: skipped, no v2 pilot abstract rubrics
  - gold-vs-pipeline: skipped because this was pipeline-context only

## Experiment Governance

- Hypothesis: BGE-M3 final selection over BM25/ObjectBM25 candidates plus
  trace-aware Judgment Plan support should carry the six-case v2 pilot through
  true-Qwen synthesis under strict post-gates.
- Decision target: no eligible Qwen fallback, no ledger repair, and all
  applicable deterministic gates pass.
- Ceiling: six-case pilot only, not full v2 generalization.
- Baseline: v1.1 reviewed4 BGE-M3 + Judgment Plan planfix gate pass.
- Stop conditions: table-cell miss, caveat/claim miss, named-fact miss,
  trap-refusal failure, or answer-vs-plan failure blocks v2 expansion.
- Decision label: diagnostic-only proceed.

## Runtime Efficiency

- Total elapsed: 233.4268 sec
- Model load: 32.0388 sec
- GPU profile: RTX 5090 32GB, `max_model_len=65536`,
  `max_tokens=6000`, `gpu_memory_utilization=0.92`, `max_num_seqs=1`,
  `dtype=float16`
- Runtime env:
  `TORCHDYNAMO_DISABLE=1`,
  `VLLM_USE_FLASHINFER_SAMPLER=0`
- Runtime caveat: vLLM still logs `SM 12.x requires CUDA >= 12.9`; it did not
  block this run.

## Caveats And Next Step

- The raw Qwen run did not pass all gates until deterministic contract fixes
  were applied.
- The most important upstream fix is unique metric IDs for duplicate row-label
  facts, exposed by Apple Products versus Services gross-margin rows.
- The validator-first expansion was completed in
  `20260519_sec_benchmark_v2_semantic_contract_gate`.
- The next v2 step should add a small case batch that exercises
  `period_change_amount` and stricter local peer-comparison support before any
  full 40-case run.
