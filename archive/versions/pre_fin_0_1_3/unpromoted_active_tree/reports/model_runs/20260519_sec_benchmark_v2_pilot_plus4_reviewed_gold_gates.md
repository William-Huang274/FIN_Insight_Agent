# Model Run: 20260519_sec_benchmark_v2_pilot_plus4_reviewed_gold_gates

## Summary

- Purpose: promote `AMZN_AWS_NUMERIC_2023_2025_001` into the v2 reviewed batch
  and validate the reviewed-gold artifact before any pipeline-context inference.
- Status: completed
- Run type: deterministic reviewed artifact build + validation gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent`

## Code And Command

- Entry point: `scripts/build_sec_benchmark_v2_pilot_plus4_reviewed_gold.py`
- Git commit: local workspace is dirty.
- Key commands:

```bash
python scripts/build_sec_benchmark_v2_pilot_plus4_reviewed_gold.py

python scripts/validate_sec_benchmark.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_readiness.json

python scripts/validate_sec_gold_gate.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --gold-facts-dir eval/sec_cases/reviewed_gold_facts \
  --manual-review-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json \
  --gate mainline_scored \
  --case-id META_REALITY_LABS_2024_001 \
  --case-id PANW_RPO_BILLINGS_NUMERIC_2023_2025_001 \
  --case-id GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001 \
  --case-id AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001 \
  --case-id AMD_SEGMENT_MIX_2023_2025_001 \
  --case-id ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001 \
  --case-id GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001 \
  --case-id SNOW_NRR_RPO_GROWTH_2023_2025_001 \
  --case-id AMZN_AWS_NUMERIC_2023_2025_001 \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_mainline.json

python scripts/validate_sec_gold_gate.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --gold-facts-dir eval/sec_cases/reviewed_gold_facts \
  --manual-review-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json \
  --gate trap_smoke \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_trap_smoke.json

python scripts/build_sec_benchmark_exact_value_ledger.py \
  --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts \
  --approval-path reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json \
  --output-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json

python scripts/validate_sec_benchmark_ledger_units.py \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_ledger_unit_gate.json
```

## Inputs

- Base cases: `eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl`
- Source AMZN case: `eval/sec_cases/test_cases_v1.jsonl`
- Reused AMZN reviewed context:
  `eval/sec_cases/reviewed_gold_context/AMZN_AWS_NUMERIC_2023_2025_001.jsonl`
- Reused AMZN reviewed facts:
  `eval/sec_cases/reviewed_gold_facts/AMZN_AWS_NUMERIC_2023_2025_001.json`

## Outputs

- Plus4 manifest: `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`
- Partial approval:
  `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json`
- Build report:
  `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_build_report.json`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`
- Gate reports:
  - `reports/quality/sec_benchmark_v2_pilot_plus4_readiness.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_mainline.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_trap_smoke.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus4_ledger_unit_gate.json`

## Results

- Builder output: plus4 reviewed case count 9; AMZN adds 6 reviewed facts and
  11 reviewed context rows.
- Readiness: 10/10 pass.
- Reviewed-gold mainline gate: 9/9 pass.
- Trap smoke: pass for the existing trap, 9 non-applicable skipped.
- Ledger: 86 exact-value rows.
- Ledger-unit: 86/86 pass, no failures or warnings.

## Experiment Governance

- Hypothesis: AMZN AWS can extend v2 coverage without new validator work because
  reviewed facts already separate cloud revenue from operating income.
- Decision target: deterministic gates must pass before any BGE-M3/Qwen run.
- Ceiling: artifact-only validation; this does not measure model behavior.
- Baseline: v2 plus3 reviewed artifact and metric-source-grounded pipeline run.
- Stop condition: any seed gold row, missing fact/context, or ledger-unit
  failure blocks pipeline-context inference.
- Decision label: proceed to case-filtered pipeline smoke.
- Mainline decision: not a full benchmark promotion.

## Caveats And Next Step

- Not run: BGE-M3 trace, Judgment Plan seed, RTX 5090 Qwen9B synthesis, and
  post-gates.
- Known risks: model may still misuse YoY percentage rows or segment operating
  income in pipeline-context output; deterministic manifest claims now expose
  those errors to caveat/claim and semantic gates.
- Next decision: either run plus4 through the existing BGE-M3 + Judgment Plan +
  Qwen9B path, or build the AMZN/GOOGL cloud profitability peer case first.
