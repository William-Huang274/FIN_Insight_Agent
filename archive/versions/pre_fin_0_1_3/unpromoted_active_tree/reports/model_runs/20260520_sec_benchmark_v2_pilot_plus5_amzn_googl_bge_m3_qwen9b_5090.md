# Model Run: 20260520_sec_benchmark_v2_pilot_plus5_amzn_googl_bge_m3_qwen9b_5090

## Summary

- Purpose: build the v2 pilot plus5 AMZN/GOOGL cloud profitability peer case,
  run deterministic reviewed-gold gates, then run the locked BGE-M3
  pipeline-context route, trace-aware Judgment Plan, RTX 5090 true-Qwen
  synthesis, and final deterministic post-gates.
- Status: diagnostic-only completed.
- Run type: reviewed artifact build + BGE-M3 retrieval trace + Judgment Plan
  seed/gate + cloud vLLM inference + deterministic post-gates.
- Timestamp: 2026-05-20 00:33-00:43 Asia/Shanghai on the remote RTX 5090 host.
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote single
  RTX 5090 32GB workspace `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command

- Git commit: local workspace is dirty; SEC benchmark artifacts are currently
  staged as local working-tree outputs, not a clean commit.
- Main builder: `scripts/build_sec_benchmark_v2_pilot_plus5_reviewed_gold.py`.
- Remote backup before plus5 sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260520_v2_pilot_plus5_sync_before_qwen_003157.tgz`
- BGE reranker local model path:
  `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`.
- Credentials are omitted from this record.

Key commands:

```bash
/root/miniconda3/bin/python scripts/build_sec_benchmark_v2_pilot_plus5_reviewed_gold.py

/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus5_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_context_bge_m3_top160_object8_local \
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
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus5_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus5_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus5_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus5_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus5_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus5_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus5_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus5_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus5_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus5_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus5_seed.jsonl`.
- New reviewed case:
  `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001`.
- Source reviewed artifact:
  `CLOUD_PROFITABILITY_2023_2025_DIAG_001`, split to AMZN/GOOGL only.
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus5_reviewed_exact_value_ledger.json`.
- BGE reranker: local ModelScope cache for `BAAI/bge-reranker-v2-m3`.
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

## Outputs

- Plus5 reviewed context:
  `eval/sec_cases/reviewed_gold_context/AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001.jsonl`.
- Plus5 reviewed facts:
  `eval/sec_cases/reviewed_gold_facts/AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001.json`.
- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_context_bge_m3_top160_object8_local`.
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus5_judgment_plans_trace_seed.json`.
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`.
- Final post-gates:
  `reports/quality/local_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates/sec_benchmark_post_gates_summary.json`.
- Remote log:
  `reports/logs/20260520_v2_pilot_plus5_bge_m3_judgment_plan_qwen9b_5090.log`.

## Results

- Reviewed artifact:
  - plus5 manifest: 11 total cases, 10 reviewed non-trap cases, 1 trap case.
  - new AMZN/GOOGL case: 12 reviewed facts and 12 reviewed context rows.
  - split policy: strict AMZN/GOOGL subset; MSFT proxy rows excluded.
- Deterministic reviewed gates:
  - readiness: 11/11 pass
  - reviewed-gold mainline: 10/10 pass
  - trap smoke: 1 pass, 10 skipped
  - exact-value ledger: 98 rows
  - ledger-unit: 98/98 pass
- BGE-M3 trace: 11/11 `context_prepared`.
- Judgment Plan: 10 plans, 14 drivers, 1 proxy driver, 2 plans with downgrades,
  0 skipped; gate 10/10 pass with 6 non-blocking trace-support warnings.
- Qwen synthesis:
  - `answered_qwen9b`: 10
  - `answered_contract_fallback`: 1 trap
  - Qwen ledger repairs: 0
  - model load: 40.4665 sec
  - total synthesis elapsed: 528.1113 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 53 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0
  - ledger-missing consistency: pass, false missing count 0
  - abstract judgment: pass, 4/4 required dimensions on the checked case
  - caveat/claim: pass, 25/25 required caveats, 0/29 disallowed violations
  - v2 semantic contract: pass, 10/10 checked cases
  - answer-vs-Judgment-Plan: pass, 10/10 checked cases
  - metric-source grounding: pass, 10 checked cases, 42 checked locations,
    159 metric references
  - ledger-unit: pass, 98/98
  - gold-vs-pipeline: skipped by design for this pipeline-context-only run

## Deterministic Contract Fix

The first post-gate run failed one caveat/claim pattern on the new AMZN/GOOGL
case. The answer said segment revenue growth does not represent overall market
share or customer growth; the original disallowed-claim allow-list covered
`not prove` / `不证明` but not `不代表`. This was a manifest contract false
positive. The builder now includes `does not represent` / `不代表` as allowed
near-negation for the market-share pattern. Qwen was not rerun; only
deterministic post-gates were rerun into the `contractfix1` directory.

## Experiment Governance

- Hypothesis: a clean AMZN/GOOGL peer cloud case should stress entity
  separation and comparable segment metrics without the Microsoft proxy
  asymmetry that made the broad cloud case unsuitable as the next v2 step.
- Decision target: plus5 reviewed artifacts must pass deterministic gates, and
  the full route must pass active post-gates with true-Qwen answers on all
  non-trap cases.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus4 BGE-M3 + Judgment Plan + RTX 5090 Qwen9B run passed all
  active post-gates.
- Stop condition: any non-trap fallback, ledger repair, caveat/claim violation,
  semantic hard failure, answer-vs-plan failure, or metric-source grounding
  failure blocks the next expansion.
- Decision label: diagnostic-only proceed.
- Mainline decision: plus5 can proceed to the Microsoft proxy/not-found case
  build; do not claim full v2 benchmark completion.

## Caveats And Next Step

- The failed initial post-gate directory is preserved for auditability:
  `reports/quality/local_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates`.
- The final accepted post-gate directory is:
  `reports/quality/local_v2_pilot_plus5_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates`.
- Next step: build `MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001` from the
  Microsoft subset of the reviewed broad cloud artifact, then add the Azure
  gross-margin not-found trap after source-policy precheck.
