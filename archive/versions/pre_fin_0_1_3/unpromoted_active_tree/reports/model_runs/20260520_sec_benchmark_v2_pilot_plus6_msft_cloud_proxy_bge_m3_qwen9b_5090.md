# Model Run: 20260520_sec_benchmark_v2_pilot_plus6_msft_cloud_proxy_bge_m3_qwen9b_5090

## Summary

- Purpose: build the v2 pilot plus6 Microsoft Cloud proxy case, run
  deterministic reviewed-gold gates, then run the locked BGE-M3
  pipeline-context route, trace-aware Judgment Plan, RTX 5090 true-Qwen
  synthesis, and final deterministic post-gates.
- Status: diagnostic-only completed.
- Run type: reviewed artifact build + BGE-M3 retrieval trace + Judgment Plan
  seed/gate + cloud vLLM inference + deterministic post-gates.
- Timestamp: 2026-05-20 13:41-13:50 Asia/Shanghai on the remote RTX 5090 host.
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote single
  RTX 5090 32GB workspace `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command

- Git commit: local workspace is dirty; SEC benchmark artifacts are currently
  local working-tree outputs, not a clean commit.
- Main builder: `scripts/build_sec_benchmark_v2_pilot_plus6_reviewed_gold.py`.
- Remote backup before plus6 sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260520_v2_pilot_plus6_sync_before_qwen_133909.tgz`.
- BGE reranker local model path:
  `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`.
- Credentials are omitted from this record.

Key commands:

```bash
/root/miniconda3/bin/python scripts/build_sec_benchmark_v2_pilot_plus6_reviewed_gold.py

/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus6_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_context_bge_m3_top160_object8_local \
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
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus6_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus6_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus6_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus6_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus6_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus6_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus6_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus6_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus6_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus6_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus6_seed.jsonl`.
- New reviewed case: `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001`.
- Source reviewed artifact: `CLOUD_PROFITABILITY_2023_2025_DIAG_001`, split to
  MSFT rows only.
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus6_reviewed_exact_value_ledger.json`.
- BGE reranker: local ModelScope cache for `BAAI/bge-reranker-v2-m3`.
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

## Outputs

- Plus6 reviewed context:
  `eval/sec_cases/reviewed_gold_context/MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001.jsonl`.
- Plus6 reviewed facts:
  `eval/sec_cases/reviewed_gold_facts/MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001.json`.
- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_context_bge_m3_top160_object8_local`.
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus6_judgment_plans_trace_seed.json`.
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`.
- Final post-gates:
  `reports/quality/local_v2_pilot_plus6_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`.
- Remote log:
  `reports/logs/20260520_v2_pilot_plus6_bge_m3_judgment_plan_qwen9b_5090.log`.

## Results

- Reviewed artifact:
  - plus6 manifest: 12 total cases, 11 reviewed non-trap cases, 1 trap case.
  - new MSFT case: 6 reviewed facts and 7 reviewed context rows.
  - split policy: strict MSFT subset; AMZN/GOOGL segment rows excluded.
  - metric families: `cloud_revenue_proxy`, `gross_margin`.
  - metric roles: `total_value`, `percentage_rate`.
  - comparability caveat context rows: 1.
- Deterministic reviewed gates:
  - readiness: 12/12 pass
  - reviewed-gold mainline: 11/11 pass
  - trap smoke: 1 pass, 11 skipped
  - exact-value ledger: 104 rows
  - ledger-unit: 104/104 pass
- BGE-M3 trace: 12/12 `context_prepared`.
- Judgment Plan: 11 plans, 15 drivers, 2 proxy drivers, 3 plans with downgrades,
  0 skipped; gate 11/11 pass with 6 non-blocking trace-support warnings.
- Qwen synthesis:
  - `answered_qwen9b`: 11
  - `answered_contract_fallback`: 1 trap
  - Qwen ledger repairs: 0
  - model load: 52.3665 sec
  - total synthesis elapsed: 570.7566 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 57 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0, warning count 1
  - ledger-missing consistency: pass, false missing count 0
  - abstract judgment: pass, 4/4 required dimensions on the checked case
  - caveat/claim: pass, 28/28 required caveats, 0/34 disallowed violations
  - v2 semantic contract: pass, 11/11 checked cases
  - answer-vs-Judgment-Plan: pass, 11/11 checked cases
  - metric-source grounding: pass, 11 checked cases, 43 checked locations,
    162 metric references
  - ledger-unit: pass, 104/104
  - gold-vs-pipeline: skipped by design for this pipeline-context-only run

## Experiment Governance

- Hypothesis: after plus5 passed the comparable AMZN/GOOGL cloud segment case,
  the Microsoft proxy counterpart should stress the Azure/Microsoft Cloud
  disclosure boundary without contaminating peer comparisons.
- Decision target: plus6 reviewed artifacts must pass deterministic gates, and
  the full route must pass active post-gates with true-Qwen answers on all
  non-trap cases.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus5 AMZN/GOOGL BGE-M3 + Judgment Plan + RTX 5090 Qwen9B run
  passed final post-gates.
- Stop condition: any non-trap fallback, ledger repair, caveat/claim violation,
  semantic hard failure, answer-vs-plan failure, or metric-source grounding
  failure blocks the next expansion.
- Decision label: diagnostic-only proceed.
- Mainline decision: plus6 can proceed to the Azure gross-margin not-found trap
  design/build path; do not claim full v2 benchmark completion.

## Caveats And Next Step

- Microsoft Cloud revenue and gross margin are treated as broad proxy evidence,
  not exact Azure revenue, exact Azure gross margin, or cloud segment operating
  income.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
- Next step: add `MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001` as the
  metric-scope source-policy trap after source-policy precheck.
