# Model Run: 20260519_sec_benchmark_v2_pilot_plus3_snow_bge_m3_qwen9b_5090

## Summary

- Purpose: run the v2 pilot plus3 reviewed batch through locked BGE-M3
  pipeline-context retrieval, trace-aware Judgment Plan prompt injection, RTX
  5090 true-Qwen synthesis, and deterministic post-gates.
- Status: diagnostic-only completed
- Run type: BGE-M3 retrieval trace + Judgment Plan seed + cloud inference +
  deterministic metric-label/gate fix + post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote RTX
  5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Git commit: local workspace is dirty; remote path is not a git repo.
- Remote backup before plus3 sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus3_sync_before_qwen_20260519_221731`
- Key commands, with credentials omitted:

```bash
python scripts/build_sec_benchmark_v2_pilot_plus3_reviewed_gold.py

python scripts/validate_sec_gold_gate.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --gold-facts-dir eval/sec_cases/reviewed_gold_facts \
  --manual-review-path reports/quality/sec_benchmark_v2_pilot_plus3_reviewed_gold_partial_approval.json \
  --gate mainline_scored \
  --case-id META_REALITY_LABS_2024_001 \
  --case-id PANW_RPO_BILLINGS_NUMERIC_2023_2025_001 \
  --case-id GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001 \
  --case-id AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001 \
  --case-id AMD_SEGMENT_MIX_2023_2025_001 \
  --case-id ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001 \
  --case-id GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001 \
  --case-id SNOW_NRR_RPO_GROWTH_2023_2025_001 \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus3_reviewed_gold_gate.json

python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_context_bge_m3_top160_object8_local \
  --object-top-k 8 \
  --evidence-top-k 4 \
  --max-context-rows 160 \
  --context-reranker bge \
  --context-reranker-model BAAI/bge-reranker-v2-m3 \
  --context-reranker-top-k 160 \
  --context-reranker-batch-size 8 \
  --context-reranker-max-length 2048 \
  --context-reranker-doc-max-chars 6000

python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus3_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus3_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus3_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus3_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus3_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_namedfact_metriclabel_fix \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_namedfact_metriclabel_fix \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_namedfact_metriclabel_fix_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus3_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus3_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl`
- New reviewed case: `SNOW_NRR_RPO_GROWTH_2023_2025_001`
- BGE trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_context_bge_m3_top160_object8_local`
- Ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus3_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus3_judgment_plans_trace_seed.json`
- BGE reranker: `BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs

- Raw Qwen output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- Final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_namedfact_metriclabel_fix`
- Metric-source grounded deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_metric_source_grounded`
- Post-gates:
  `reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_namedfact_metriclabel_fix_post_gates/sec_benchmark_post_gates_summary.json`
- Metric-source grounded post-gates:
  `reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_metric_source_grounded_post_gates/sec_benchmark_post_gates_summary.json`
- Remote synthesis log:
  `reports/logs/20260519_v2_pilot_plus3_bge_m3_judgment_plan_qwen9b_5090_synthesis.log`
- Worklog audit:
  `docs/worklog/97_sec_benchmark_v2_pilot_plus3_snow_bge_m3_qwen9b_5090_audit.md`

## Results

- BGE trace prepared 9/9 with BGE-M3 as final selector and
  `bm25_only_allowed=false`.
- Judgment Plan seed: 8 plans, 11 drivers, 1 proxy driver.
- Raw synthesis answer status:
  - `answered_qwen9b`: 8
  - `answered_contract_fallback`: 1
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap gate: pass
  - answer-ledger: pass, exact-value hits 51
  - metric-role term: pass
  - table-cell: pass, 12/12 AAPL cells
  - named-fact: pass, unsupported token count 0
  - ledger-missing consistency: pass
  - caveat/claim: pass, 19/19 caveats covered and 0/20 disallowed violations
  - v2 semantic contract: pass, 8/8 checked cases
  - answer-vs-Judgment-Plan: pass, 8/8 checked cases
  - metric-source grounding: pass, 8/8 checked cases, 31 checked locations,
    133 metric references
  - ledger-unit: pass, 80/80
  - gold-vs-pipeline: skipped by design

## Notes

- The final deterministic output was rebuilt from saved raw Qwen outputs after
  fixing metric-label named-fact sanitization and two validator false positives.
  Qwen was not rerun for those fixes.
- A later deterministic replay added metric-source grounding. The previous
  normalized output failed the new gate on 2 cases, with 5 missing evidence-id
  locations and 8 off-source metric references. The replayed output appends the
  ledger `source_evidence_id`/`object_id` for each retained metric-backed
  driver/key point and passes the new gate.
- This run remains diagnostic-only and should feed the next v2 reviewed coverage
  design rather than be presented as full generalization.

## Metric Source Grounding Replay

Command:

```bash
python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_metric_source_grounded \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus3_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus3_judgment_plans_trace_seed.json \
  --raw-model-outputs-path eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_namedfact_metriclabel_fix/raw_model_outputs.jsonl \
  --mode pipeline_context \
  --hardware-profile rtx5090_32gb \
  --disable-vllm
```

Replay status:

- No model load or new inference was run.
- Answer status counts: `answered_qwen9b=8`,
  `answered_contract_fallback=1`.
- Final post-gates include `metric_source_grounding_gate_pass=true`; all other
  active gates remain passing.
