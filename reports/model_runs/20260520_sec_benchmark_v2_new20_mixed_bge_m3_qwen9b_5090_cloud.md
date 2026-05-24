# 20260520 SEC Benchmark v2 New20 Mixed BGE-M3 Qwen9B 5090 Cloud

Date: 2026-05-20

Type: cloud BGE-M3 retrieval trace + Judgment Plan + RTX 5090 Qwen9B inference + deterministic post-gates

Status: diagnostic-only completed

## Summary

Built and ran a 30-case mixed 20-company SEC benchmark pack: 16 original-company regression cases, 10 new-company reviewed cases, and 4 trap regressions. The route passed local deterministic entry gates, cloud BGE-M3 trace, trace-aware Judgment Plan validation, RTX 5090 Qwen9B inference, and final `rubricfix2` post-gates.

## Inputs

- Mixed manifest: `eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl`
- Review approval: `reports/quality/sec_benchmark_v2_new20_mixed_review_approval.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_new20_mixed_reviewed_exact_value_ledger.json`
- Abstract rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`
- BGE-M3 model: `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Commands

Entry gates:

```bash
python scripts/validate_sec_gold_gate.py --cases-path eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl --gold-context-dir eval/sec_cases/reviewed_gold_context --gold-facts-dir eval/sec_cases/reviewed_gold_facts --manual-review-path reports/quality/sec_benchmark_v2_new20_mixed_review_approval.json --gate mainline_scored --output-path reports/quality/sec_benchmark_v2_new20_mixed_mainline_gold_gate.json

python scripts/build_sec_benchmark_exact_value_ledger.py --approval-path reports/quality/sec_benchmark_v2_new20_mixed_review_approval.json --output-path reports/exact_value_ledgers/sec_benchmark_v2_new20_mixed_reviewed_exact_value_ledger.json
```

Cloud BGE-M3:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py --cases-path eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl --gold-context-dir eval/sec_cases/reviewed_gold_context --mode pipeline_context --output-dir eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_context_bge_m3_top160_object8_cloud --object-top-k 8 --evidence-top-k 4 --max-context-rows 160 --context-reranker bge --context-reranker-model /root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3 --context-reranker-device cuda --context-reranker-top-k 160 --context-reranker-batch-size 8 --context-reranker-max-length 2048 --context-reranker-doc-max-chars 6000
```

Cloud Qwen9B:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_context_bge_m3_top160_object8_cloud --output-dir eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud --cases-path eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_new20_mixed_reviewed_exact_value_ledger.json --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_new20_mixed_judgment_plans_trace_seed_cloud.json --hardware-profile rtx5090_32gb --structured-json
```

Final post-gates:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud --cases-path eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl --output-dir reports/quality/cloud_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_5090_rubricfix2_post_gates --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_new20_mixed_reviewed_exact_value_ledger.json --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_new20_mixed_judgment_plans_trace_seed_cloud.json --abstract-rubric-path eval/sec_cases/abstract_judgment_rubric_v0_1.json --skip-gold-vs-pipeline-gate --min-qwen-answer-ratio 1.0
```

## Results

- Entry gates:
  - mainline gold: 30/30 pass
  - trap review: 4/4 pass
  - ledger: 208 rows
  - ledger-unit: 208/208 pass
- BGE-M3 trace: 30/30 `context_prepared`, about 108 sec.
- Judgment Plan: 23 plans, 30 drivers, 6 proxy drivers, 8 downgrade plans, validation 23/23 pass.
- Qwen9B:
  - 26/26 eligible cases answered by Qwen
  - 4/4 traps answered by contract fallback
  - 0 failed eligible outputs
  - 0 ledger repairs
  - total elapsed 1176.6205 sec
  - model load 28.8775 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - gold mean score pct 0.8853
  - trap pass
  - answer-ledger 30/30, 110 exact-value hits
  - table-cell 48/48
  - named-fact 0 unsupported / 0 warnings
  - ledger-missing false missing count 0
  - abstract judgment 18/18, 47/47 required dimensions
  - caveat/claim 47/47 caveats, 0/61 disallowed violations
  - v2 semantic 30/30
  - answer-vs-plan 23/23
  - metric-source grounding 336 refs
  - ledger-unit 208/208

## Outputs

- BGE trace: `eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_context_bge_m3_top160_object8_cloud`
- Qwen output: `eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Final post-gates: `reports/quality/cloud_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_5090_rubricfix2_post_gates/sec_benchmark_post_gates_summary.json`
- Logs:
  - `reports/logs/20260520_v2_new20_mixed_bge_m3_trace_cloud.log`
  - `reports/logs/20260520_v2_new20_mixed_bge_m3_judgment_plan_qwen9b_5090_cloud.log`

## Governance

- Hypothesis: a mixed 20-company route should preserve original-company regression behavior while adding the 10 new-company reviewed cases, without fallback, ledger repair, or gate failure.
- Decision target: 30-case mixed pack passes BGE-M3 trace, Qwen answer ratio 1.0 on eligible non-trap cases, trap gate, answer-ledger, table-cell, named-fact, abstract judgment, caveat/claim, semantic, answer-vs-plan, metric-source grounding, and ledger-unit gates.
- Result: target met.
- Ceiling: still diagnostic-only; broader generalization requires adding more SEC companies and repeating review/index gates.
- Next decision: use this mixed pack as the frozen comparison target for Qwen3.6-27B-FP8/4bit smoke, or expand to another 10 SEC companies.
