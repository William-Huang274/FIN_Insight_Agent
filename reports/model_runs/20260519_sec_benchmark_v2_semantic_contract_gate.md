# Model Run: 20260519_sec_benchmark_v2_semantic_contract_gate

## Summary

- Purpose: add and validate a deterministic v2 semantic contract gate before
  expanding the SEC benchmark v2 gold set.
- Status: diagnostic-only completed
- Run type: deterministic validator + post-gate integration
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent`

## Code And Command

- Entry points:
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Git commit: local workspace is dirty.
- Commands:

```bash
python -m py_compile \
  scripts/validate_sec_benchmark_v2_semantic_contracts.py \
  scripts/run_sec_benchmark_post_gates.py

python scripts/validate_sec_benchmark_v2_semantic_contracts.py \
  --run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --output-path reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_v2_semantic_gate_smoke/sec_benchmark_v2_semantic_contract_gate.json

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json \
  --output-dir reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates_v2semantic \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
- Final pilot outputs:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4`
- Ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json`

## Outputs

- Standalone semantic-gate report:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_v2_semantic_gate_smoke/sec_benchmark_v2_semantic_contract_gate.json`
- Full post-gates with semantic gate:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates_v2semantic/sec_benchmark_post_gates_summary.json`
- Worklog audit:
  `docs/worklog/95_sec_benchmark_v2_semantic_contract_gate.md`

## Results

- Py compile: pass.
- Standalone semantic gate:
  - `can_enter_gate=true`
  - checked cases: 5/6
  - pass: 5
  - fail: 0
  - active checks: entity separation, proxy/direct, non-comparable metric,
    percentage target-value, and source-policy trap.
- Full post-gates:
  - `v2_semantic_contract_gate_pass=true`
  - `qwen_answer_ratio=1.0`
  - previous deterministic gates still pass.
- Warnings:
  - `one_sided_peer_comparison_support=3` on the GOOGL/META advertising case.
    These are local support-organization warnings, not hard entity bleed.

## Experiment Governance

- Hypothesis: v2 expansion should not proceed on manifest text alone; semantic
  failure tags must have deterministic gate output.
- Decision target: current v2 pilot still passes after the new gate is enabled,
  and the report exposes active checks plus warning/failure types.
- Ceiling: six-case pilot only.
- Baseline: previous `contractfix4` post-gates without this semantic gate.
- Decision label: diagnostic-only proceed.

## Caveats And Next Step

- `prior_period_as_target_value` is implemented but not exercised by the
  current pilot because the v2 pilot ledger has no `period_change_amount` rows.
- Next v2 case expansion should intentionally include a period-change case and
  a stricter peer-comparison support case before larger scale-up.
