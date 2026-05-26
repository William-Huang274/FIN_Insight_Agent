# Model Run: 20260520_sec_benchmark_v2_full40_bge_m3_qwen9b_5090

## Summary

- Purpose: run the governed v2 full40 benchmark through the locked BGE-M3 pipeline-context route, trace-aware Judgment Plan, RTX 5090 Qwen9B synthesis, and all active deterministic post-gates.
- Status: diagnostic-only completed.
- Run type: retrieval trace + inference + evaluation.
- Timestamp: 2026-05-20.
- Environment: local Windows workspace for deterministic prep and BGE-M3 trace; remote RTX 5090 32GB cloud host for Qwen9B vLLM synthesis. Credentials are intentionally omitted.

## Code And Command

- Git commit: local workspace is dirty; these are working-tree benchmark artifacts.
- Case manifest: `eval/sec_cases/test_cases_v2_full40_seed.jsonl`.
- BGE trace run:

```bash
python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_full40_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_context_bge_m3_top160_object8_local \
  --object-top-k 8 \
  --evidence-top-k 4 \
  --max-context-rows 160 \
  --context-reranker bge \
  --context-reranker-model BAAI/bge-reranker-v2-m3 \
  --context-reranker-top-k 160 \
  --context-reranker-batch-size 8 \
  --context-reranker-max-length 2048 \
  --context-reranker-doc-max-chars 6000
```

- Judgment Plan:

```bash
python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_full40_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_full40_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_full40_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_full40_judgment_plan_trace_seed_report.json
```

- Qwen synthesis on cloud:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_full40_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_full40_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_full40_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json
```

- Contract replay after deterministic fixes:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1 \
  --cases-path eval/sec_cases/test_cases_v2_full40_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_full40_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_full40_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json \
  --raw-model-outputs-path eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090/raw_model_outputs.jsonl
```

- Final post-gates:

```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1 \
  --cases-path eval/sec_cases/test_cases_v2_full40_seed.jsonl \
  --output-dir reports/quality/local_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_full40_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_full40_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Full40 manifest: 40 cases, 34 reviewed non-trap cases, 6 pipeline traps.
- Reviewed exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_full40_reviewed_exact_value_ledger.json`, 262 rows.
- BGE-M3 trace: `eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_context_bge_m3_top160_object8_local`.
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_full40_judgment_plans_trace_seed.json`.
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`, `max_model_len=65536`, `max_tokens=6000`, `gpu_memory_utilization=0.92`, FlashInfer sampler disabled.

## Outputs

- Final Qwen output: `eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1`.
- Final post-gates: `reports/quality/local_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates/sec_benchmark_post_gates_summary.json`.
- Remote Qwen log: `reports/logs/20260520_v2_full40_bge_m3_judgment_plan_qwen9b_5090.log`.
- Judgment Plan validation: `reports/quality/sec_benchmark_v2_full40_judgment_plan_trace_seed_validation.json`.

## Results

- Deterministic readiness/gold gates before Qwen:
  - readiness/BM25 smoke: 40/40 pass.
  - all40 mainline gold gate: 40/40 pass.
  - trap6 smoke gate: 6/6 pass.
  - ledger-unit precheck: 262/262 pass.
- BGE-M3 trace: 40/40 `context_prepared`.
- Judgment Plan: 24 plans, 39 drivers, 6 proxy drivers, 7 plans with downgrades, validator 24/24 pass.
- Qwen synthesis:
  - `answered_qwen9b`: 34
  - `answered_contract_fallback`: 6 traps
  - non-trap Qwen answer ratio: 1.0
  - Qwen ledger repairs: 0
  - model load: 38.7782 sec
  - first true-Qwen synthesis wall time: 1466.9654 sec total
  - observed average eligible Qwen case latency: about 42 sec/case after load
  - deterministic raw replay contractfix1: 3.5607 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap gate: pass
  - answer-ledger: pass, 98 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 96/96 valid cells across 3 table cases
  - named-fact: pass, 0 unsupported tokens, 2 non-blocking warnings
  - ledger-missing consistency: pass, false missing count 0
  - abstract judgment: pass, 17/17 checked cases, 56/56 dimensions covered
  - caveat/claim: pass, 67/67 caveats covered, 0/88 disallowed violations
  - v2 semantic contract: pass, 38/38 checked cases
  - answer-vs-Judgment-Plan: pass, 24/24 checked cases
  - metric-source grounding: pass, 34 pass / 6 traps skipped / 430 metric refs
  - ledger-unit: pass, 262/262
  - gold-vs-pipeline: skipped by design for this pipeline-context-only run

## Contractfix1 Notes

The first post-gate pass failed only deterministic contract checks, not model availability or ledger grounding. Fixes were applied without rerunning Qwen:

- Trap contract fallback now appends manifest-native `required_caveats` and `required_not_found` coverage, and includes explicit Alphabet/AWS and NVIDIA/CUDA refusals.
- Abstract rubric allow-lists now handle negated phrasing such as `不等于`, `区分`, and `不能直接证明`.
- The v2 semantic percentage-rate validator now evaluates the local metric-id clause instead of reading the next metric clause as amount language.
- The answer-vs-Judgment-Plan weak-support check now recognizes local caveats such as `无法`, `未提供`, `缺乏`, `not disclosed`, and `limited`.

## Experiment Governance

- Hypothesis: after all 12 seed-only full40 cases were promoted to reviewed artifacts, the locked BGE-M3 + trace-aware Judgment Plan + RTX 5090 Qwen9B route should scale from plus8 to 40 cases without non-trap fallback, ledger repair, or deterministic gate failure.
- Decision target: full40 must pass qwen answer ratio 1.0, trap, ledger, table-cell, named-fact, ledger-missing, abstract judgment, caveat/claim, v2 semantic, answer-vs-plan, metric-source grounding, and ledger-unit gates.
- Ceiling: the benchmark still spans the current 10-company SEC universe; this supports full40 route validation but not broad-company generalization claims.
- Baseline: plus8 frozen MVP diagnostic pack and plus8 gold-vs-pipeline parity both passed all active gates.
- Stop condition: any non-trap fallback, ledger repair, table-cell failure, false missing, unsupported named fact, required caveat miss, semantic contract failure, or answer-vs-plan failure blocks expansion to more SEC companies.
- Decision label: diagnostic-only proceed.
- Mainline decision: full40 can now be treated as the current reviewed benchmark route for internal evaluation; next expansion should add more SEC companies before claiming broader generalization.

## Runtime Efficiency

- BGE-M3 local trace wall time: about 1021.9 sec, including first local HF model load/download.
- Qwen9B first run total wall time: 1466.9654 sec, with 38.7782 sec model load.
- Qwen generation speed in vLLM logs was typically around 40 output tokens/sec, with per-case elapsed times mostly 20-65 sec and the largest table/long-context cases around 85-88 sec.
- Bottleneck: single-sequence resident generation (`max_num_seqs=1`) plus long structured JSON outputs; local BGE first-load overhead is a separate setup cost.
- Serving implication: resident model removes the 38.8 sec load cost, but full40 batch evaluation remains roughly 24 minutes under the current single-sequence profile.

## Caveats And Next Step

- This is not a larger-universe test; the case set still uses the existing 10 SEC companies.
- Gold-vs-pipeline parity was skipped by design because this run only evaluates pipeline-context Qwen outputs.
- Next decision: expand the SEC universe beyond 10 companies, rebuild filings/evidence/objects/indexes, and design the next company-diverse benchmark slice before scaling case count further.
