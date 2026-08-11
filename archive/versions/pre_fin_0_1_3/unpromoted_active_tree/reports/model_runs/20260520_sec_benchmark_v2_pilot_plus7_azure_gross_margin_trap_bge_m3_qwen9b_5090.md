# Model Run: 20260520_sec_benchmark_v2_pilot_plus7_azure_gross_margin_trap_bge_m3_qwen9b_5090

## Summary

- Purpose: add the v2 pilot plus7 Azure gross-margin metric-scope not-found
  trap, run deterministic reviewed/trap gates, then run the locked BGE-M3
  pipeline-context route, trace-aware Judgment Plan, RTX 5090 true-Qwen
  synthesis, and final deterministic post-gates.
- Status: diagnostic-only completed.
- Run type: trap artifact build + BGE-M3 retrieval trace + Judgment Plan
  seed/gate + cloud vLLM inference + deterministic post-gates.
- Timestamp: 2026-05-20 14:21-14:31 Asia/Shanghai on the remote RTX 5090 host.
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote single
  RTX 5090 32GB workspace `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command

- Git commit: local workspace is dirty; SEC benchmark artifacts are currently
  local working-tree outputs, not a clean commit.
- Main builder: `scripts/build_sec_benchmark_v2_pilot_plus7_reviewed_gold.py`.
- Validator change:
  `scripts/validate_sec_benchmark_v2_semantic_contracts.py` now checks
  `required_not_found_missing` when a case declares `required_not_found`.
- BGE reranker local model path:
  `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`.
- Credentials are omitted from this record.

Key commands:

```bash
/root/miniconda3/bin/python scripts/build_sec_benchmark_v2_pilot_plus7_reviewed_gold.py

/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus7_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_context_bge_m3_top160_object8_local \
  --object-top-k 8 \
  --evidence-top-k 4 \
  --max-context-rows 160 \
  --context-reranker bge \
  --context-reranker-model /root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3 \
  --context-reranker-top-k 160 \
  --context-reranker-batch-size 8 \
  --context-reranker-max-length 2048 \
  --context-reranker-doc-max-chars 6000

/root/miniconda3/bin/python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus7_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus7_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus7_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus7_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus7_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus7_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus7_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus7_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus7_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus7_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus7_seed.jsonl`.
- New trap case: `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001`.
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus7_reviewed_exact_value_ledger.json`.
- BGE reranker: local ModelScope cache for `BAAI/bge-reranker-v2-m3`.
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

## Outputs

- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_context_bge_m3_top160_object8_local`.
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus7_judgment_plans_trace_seed.json`.
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`.
- Final post-gates:
  `reports/quality/local_v2_pilot_plus7_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`.
- Remote log:
  `reports/logs/20260520_v2_pilot_plus7_bge_m3_judgment_plan_qwen9b_5090.log`.

## Results

- Artifact/gate setup:
  - plus7 manifest: 13 total cases, 11 reviewed non-trap cases, 2 trap cases.
  - new Azure trap: pipeline-context only; no reviewed gold context or facts.
  - exact-value ledger remains 104 rows.
  - readiness: 13/13 pass
  - reviewed-gold mainline: 11/11 pass
  - trap smoke: 2 pass, 11 skipped
  - ledger-unit: 104/104 pass
- Local trap contract microtest:
  - two trap contract outputs passed trap-smoke 2/2.
  - caveat/claim passed 3/3 required caveats and 0/5 violations.
  - v2 semantic passed `required_not_found_missing` and source-policy checks.
- BGE-M3 trace: 13/13 `context_prepared`.
- Judgment Plan: 11 plans, 15 drivers, 2 proxy drivers, 3 plans with downgrades,
  0 skipped; gate 11/11 pass with 6 non-blocking trace-support warnings.
- Qwen synthesis:
  - `answered_qwen9b`: 11
  - `answered_contract_fallback`: 2 traps
  - Qwen ledger repairs: 0
  - model load: 39.3596 sec
  - total synthesis elapsed: 552.7836 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 57 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0, warning count 1
  - ledger-missing consistency: pass, false missing count 0
  - abstract judgment: pass, 4/4 required dimensions on the checked case
  - caveat/claim: pass, 30/30 required caveats, 0/37 disallowed violations
  - v2 semantic contract: pass, 12/12 checked cases, including
    `required_not_found_missing=1`
  - answer-vs-Judgment-Plan: pass, 11/11 checked cases
  - metric-source grounding: pass, 11 checked cases, 43 checked locations,
    162 metric references
  - ledger-unit: pass, 104/104
  - gold-vs-pipeline: skipped by design for this pipeline-context-only run

## Experiment Governance

- Hypothesis: the system should refuse exact Azure gross margin while still
  allowing Microsoft Cloud gross margin only as broad proxy context.
- Decision target: the new trap must pass trap-smoke, caveat/claim, and
  `required_not_found_missing` semantic checks while preserving all existing
  non-trap pipeline gates.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus6 Microsoft Cloud proxy run passed all active post-gates.
- Stop condition: any new trap failure, non-trap fallback, ledger repair,
  semantic hard failure, answer-vs-plan failure, or metric-source grounding
  failure blocks further expansion.
- Decision label: diagnostic-only proceed.
- Mainline decision: plus7 can proceed to the remaining text-heavy v2 cases
  (`NVDA_DATACENTER_2023_2025_001` and `SNOW_RISK_2023_2025_001`) or to an MVP
  freeze-readiness review; do not claim full v2 benchmark completion.

## Caveats And Next Step

- The new trap is contract-fallback by design because anti-hallucination traps
  are excluded from true-Qwen answer-ratio accounting.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
- Next step: add the remaining text-heavy NVDA/SNOW risk cases or run a
  freeze-readiness coverage review before declaring any MVP pack.
