# Model Run: 20260520_sec_benchmark_v2_pilot_plus8_text_heavy_nvda_snow_bge_m3_qwen9b_5090

## Summary

- Purpose: add the v2 pilot plus8 text-heavy NVDA/SNOW reviewed cases, run
  deterministic reviewed gates, then run the locked BGE-M3 pipeline-context
  route, trace-aware Judgment Plan, RTX 5090 true-Qwen synthesis, and final
  deterministic post-gates.
- Status: diagnostic-only completed.
- Run type: reviewed artifact build + BGE-M3 retrieval trace + Judgment Plan
  seed/gate + cloud vLLM inference + deterministic post-gates.
- Timestamp: 2026-05-20 14:53-15:05 Asia/Shanghai on the remote RTX 5090 host.
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote single
  RTX 5090 32GB workspace `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command

- Git commit: local workspace is dirty; SEC benchmark artifacts are currently
  local working-tree outputs, not a clean commit.
- Main builder: `scripts/build_sec_benchmark_v2_pilot_plus8_reviewed_gold.py`.
- BGE reranker local model path:
  `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`.
- Credentials are omitted from this record.

Key commands:

```bash
/root/miniconda3/bin/python scripts/build_sec_benchmark_v2_pilot_plus8_reviewed_gold.py

/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_context_bge_m3_top160_object8_local \
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
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus8_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl`.
- New reviewed text cases:
  - `NVDA_DATACENTER_2023_2025_001`
  - `SNOW_RISK_2023_2025_001`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json`.
- BGE reranker: local ModelScope cache for `BAAI/bge-reranker-v2-m3`.
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

## Outputs

- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_context_bge_m3_top160_object8_local`.
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json`.
- Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`.
- Final post-gates:
  `reports/quality/local_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`.
- Remote log:
  `reports/logs/20260520_v2_pilot_plus8_bge_m3_judgment_plan_qwen9b_5090.log`.

## Results

- Artifact/gate setup:
  - plus8 manifest: 15 total cases, 13 reviewed non-trap cases, 2 trap cases.
  - new text-heavy cases: 12 NVDA reviewed context rows, 9 SNOW reviewed
    context rows, and 0 target numeric facts for each.
  - exact-value ledger remains 104 rows.
  - readiness: 15/15 pass
  - reviewed-gold mainline: 13/13 pass
  - trap smoke: 2 pass, 13 skipped
  - ledger-unit: 104/104 pass
- BGE-M3 trace: 15/15 `context_prepared`.
- Judgment Plan: 11 plans, 15 drivers, 2 proxy drivers, 3 plans with downgrades,
  0 skipped; gate 11/11 pass with 6 non-blocking trace-support warnings.
- Qwen synthesis:
  - `answered_qwen9b`: 13
  - `answered_contract_fallback`: 2 traps
  - Qwen ledger repairs: 0
  - model load: 38.3242 sec
  - total synthesis elapsed: 619.6674 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap: pass
  - answer-ledger: pass, 57 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0, warning count 1
  - ledger-missing consistency: pass, false missing count 0
  - abstract judgment: pass, 3 checked cases, 12/12 required dimensions
  - caveat/claim: pass, 37/37 required caveats, 0/43 disallowed violations
  - v2 semantic contract: pass, 14/14 checked cases
  - answer-vs-Judgment-Plan: pass, 11/11 checked cases; 4 skipped cases are
    the two no-ledger text cases plus two traps.
  - metric-source grounding: pass, 13 pass, 2 skipped traps, 162 metric refs
  - ledger-unit: pass, 104/104
  - gold-vs-pipeline: skipped by design for this pipeline-context-only run

## Experiment Governance

- Hypothesis: the system should answer reviewed NVDA/SNOW qualitative cases
  using SEC text support while refusing unsupported numeric, stock, market-share,
  customer-count, NRR, or retention claims.
- Decision target: the two text cases must pass abstract judgment, required
  caveat, disallowed-claim, source-policy, named-fact, and no-ledger consistency
  gates while preserving all existing numeric and trap gates.
- Ceiling: diagnostic-only staged expansion. This is not a full v2 benchmark or
  MVP frozen pack.
- Baseline: plus7 Azure gross-margin trap run passed all active post-gates.
- Stop condition: any text-case rubric failure, required caveat miss,
  unsupported named fact, non-trap fallback, ledger repair, or post-gate failure
  blocks further expansion.
- Decision label: diagnostic-only proceed.
- Mainline decision: plus8 can proceed to an MVP freeze-readiness coverage
  review; do not claim full v2 benchmark completion.

## Caveats And Next Step

- The two new text-heavy cases do not produce Judgment Plans because the current
  deterministic plan builder is ledger-row driven. They are instead gated by
  abstract judgment, caveat/claim, named-fact, source-policy, and no-ledger
  consistency checks.
- BGE-M3 remains the final context selector. BM25/ObjectBM25 remain candidate
  generators only.
- Next step: run a freeze-readiness coverage review of the plus8 MVP-extension
  pack before adding more cases.
