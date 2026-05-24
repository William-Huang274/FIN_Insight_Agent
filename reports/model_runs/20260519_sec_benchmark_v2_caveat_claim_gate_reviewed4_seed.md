# Model Run: 20260519_sec_benchmark_v2_caveat_claim_gate_reviewed4_seed

## Summary

- Purpose: Add and validate the v2 `required_caveats` / `disallowed_claims` gate, then create a small v2 pilot seed manifest.
- Status: diagnostic-only completed
- Run type: evaluation / validator smoke
- Timestamp: 2026-05-19
- Environment: local Windows workspace, no model inference

## Code And Commands

Changed validator and prompt/planning surfaces:

- `scripts/validate_sec_benchmark_caveat_claims.py`
- `scripts/run_sec_benchmark_post_gates.py`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- `scripts/build_sec_benchmark_judgment_plan.py`

Validation commands:

```bash
python scripts/validate_sec_benchmark_caveat_claims.py \
  --run-dir eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_vllm_5090_planfix \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --output-path reports/quality/sec_benchmark_v1_1_reviewed4_caveat_claim_gate_planfix.json

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

python scripts/validate_sec_benchmark.py \
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl \
  --output-path reports/quality/sec_benchmark_v1_1_reviewed4_with_v2_fields_readiness.json

python scripts/validate_sec_benchmark.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --output-path reports/quality/sec_benchmark_v2_pilot_seed_readiness.json

python scripts/validate_sec_benchmark.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --output-path reports/quality/sec_benchmark_v2_pilot_seed_bm25_smoke.json \
  --run-bm25-smoke \
  --bm25-top-k 5

python -m py_compile \
  scripts/validate_sec_benchmark_caveat_claims.py \
  scripts/run_sec_benchmark_post_gates.py \
  scripts/run_sec_eval_synthesis_qwen9b_backend.py \
  scripts/build_sec_benchmark_judgment_plan.py
```

## Inputs

- Reviewed4 planfix output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_vllm_5090_planfix`
- Reviewed4 cases with v2 fields: `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
- v2 pilot seed manifest: `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v1_1_reviewed4_judgment_plans_trace_seed.json`
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`

## Outputs

- Caveat/claim gate report: `reports/quality/sec_benchmark_v1_1_reviewed4_caveat_claim_gate_planfix.json`
- Integrated post-gate summary: `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_5090_planfix_post_gates/sec_benchmark_post_gates_summary.json`
- Reviewed4 readiness after v2 fields: `reports/quality/sec_benchmark_v1_1_reviewed4_with_v2_fields_readiness.json`
- v2 pilot readiness: `reports/quality/sec_benchmark_v2_pilot_seed_readiness.json`
- v2 pilot BM25 smoke: `reports/quality/sec_benchmark_v2_pilot_seed_bm25_smoke.json`
- Worklog: `docs/worklog/92_sec_benchmark_v2_caveat_claim_gate_and_pilot_seed.md`

## Results

- Caveat/claim gate:
  - checked 4/4 reviewed4 cases
  - required caveats 9/9 covered
  - disallowed claims 11 checked
  - disallowed violations 0
- Integrated reviewed4 post-gates:
  - `qwen_answer_ratio=1.0`
  - answer-vs-plan 4/4 pass
  - answer-ledger 4/4 pass, exact-value hits 20
  - table cells 36/36 valid
  - named-fact unsupported tokens 0
  - ledger units 69/69 pass
  - caveat/claim gate pass
- v2 pilot seed:
  - 6/6 readiness pass
  - BM25 smoke 6/6 pass
  - only warning: `gold_context_missing=5`, expected because non-trap pilot cases are not reviewed yet

## Decision

Proceed to v2 pilot annotation planning. The pilot manifest is not reviewed gold and must not be used as a mainline benchmark until reviewed context/facts and downstream gates are built.
