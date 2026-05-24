# SEC Benchmark v2 New20 NewCo Reviewed-Gold Gate

Date: 2026-05-20

## Scope

Promote the 10 new-company seed cases for `AVGO/CSCO/INTC/QCOM/TXN/AMAT/MU/INTU/ADP/CRWD` from seed-only readiness into deterministic reviewed-gold eligibility before any new20 benchmark inference or Qwen3.6-27B smoke comparison.

This step is artifact and gate work only. It does not claim BGE-M3 retrieval quality, Judgment Plan quality, Qwen9B answer quality, or Qwen3.6-27B SEC benchmark quality.

## Inputs

- Seed cases: `eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl`
- Cloud structured sync inputs:
  - `.tmp_remote_diag/cloud_new20_structured/sec_tech_10k_metrics.jsonl`
  - `.tmp_remote_diag/cloud_new20_structured/sec_tech_10k_tables.jsonl`
  - `.tmp_remote_diag/cloud_new20_structured/sec_tech_10k_evidence.jsonl`

The cloud structured corpus covers 20 companies, including the 10 new companies, with 95,372 metrics, 5,658 tables, and 5,472 evidence rows in the synced structured files.

## Changes

- Added `scripts/build_sec_benchmark_v2_new20_reviewed_gold.py`.
- Built explicit reviewed facts and context rows for all 10 new-company seed cases.
- Updated seed-case expected row-label variants where the source filings use different but legitimate labels:
  - CSCO services: `Service` / `Services`
  - INTC gross profit: `Gross margin` / `Gross profit`
  - INTU small business successor label: `Small Business & Self-Employed` / `Global Business Solutions`
- Preserved source-row provenance for normalized facts such as TXN segment rows and INTC gross-margin/gross-profit naming.

## Outputs

- Reviewed facts: `eval/sec_cases/reviewed_gold_facts/<case_id>.json`
- Reviewed context: `eval/sec_cases/reviewed_gold_context/<case_id>.jsonl`
- Partial approval: `reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_partial_approval.json`
- Build report: `reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_build_report.json`
- Gold gate: `reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_gate_mainline.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_new20_newco_reviewed_exact_value_ledger.json`
- Ledger-unit gate: `reports/quality/sec_benchmark_v2_new20_newco_ledger_unit_gate.json`

## Gate Results

- Builder output: 10 reviewed cases, 69 reviewed facts, 79 reviewed context rows.
- Mainline reviewed-gold gate: 10/10 pass, 0 blockers, 0 warnings.
- Exact-value ledger: 69 rows.
- Ledger-unit gate: 69/69 pass, 0 failures, 0 warnings.
- Script syntax check: `python -m py_compile scripts/build_sec_benchmark_v2_new20_reviewed_gold.py` passed.

## Coverage

- AVGO: Products; Subscriptions and services, 2023-2025.
- CSCO: Product; Services; remaining performance obligations, 2023-2025.
- INTC: Net revenue; gross profit/gross margin, 2023-2025.
- QCOM: Handsets; Automotive, 2023-2025.
- TXN: Analog; Embedded Processing, 2023-2025.
- AMAT: Semiconductor Systems; Applied Global Services, 2023-2025.
- MU: DRAM; NAND, 2023-2025.
- INTU: Small Business/Global Business Solutions; Consumer; Credit Karma, 2023-2025.
- ADP: Employer Services; PEO Services; client-funds interest, 2023-2025.
- CRWD: ARR; subscription gross profit, 2023-2025.

## Decision

The 10 new-company seed cases now have deterministic reviewed context/facts and a passing exact-value ledger gate. They can proceed to the next cloud benchmark step: BGE-M3 pipeline-context retrieval, trace-aware Judgment Plan, and Qwen9B inference for the new20 reviewed route.

The Qwen3.6-27B-FP8 route remains diagnostic-only until it passes a separate benchmark-prompt smoke and longer-context feasibility check.

## Caveats

- `.tmp_remote_diag/cloud_new20_structured` is a local temporary sync of cloud structured artifacts, not the main source of truth.
- No SSH passwords, tokens, or temporary credentials were written to repo files.
- No model inference was run in this step.
