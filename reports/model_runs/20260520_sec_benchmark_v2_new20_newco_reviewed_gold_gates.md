# 20260520 SEC Benchmark v2 New20 NewCo Reviewed-Gold Gates

Date: 2026-05-20

Type: deterministic reviewed artifact build + validation gates

Status: completed

## Scope

Build reviewed context/facts and an exact-value ledger for the 10 new-company SEC benchmark seed cases before running BGE-M3 retrieval, Judgment Plan, Qwen9B inference, or Qwen3.6-27B diagnostic benchmark smoke.

## Governance

- Hypothesis: explicit SEC-reviewed numeric facts can promote the 10 new-company seed cases from seed-only readiness to case-filtered reviewed-gold eligibility.
- Decision target: all 10 cases pass the mainline reviewed-gold gate and all exact-value ledger rows pass unit validation.
- Ceiling: deterministic reviewed assets only; no model-output quality claim is made.
- Stop condition: any missing reviewed fact, unsupported expected fact, unit mismatch, or ledger-table mismatch blocks the next inference step.

## Artifacts

- Builder: `scripts/build_sec_benchmark_v2_new20_reviewed_gold.py`
- Seed cases: `eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl`
- Reviewed facts: `eval/sec_cases/reviewed_gold_facts/<case_id>.json`
- Reviewed context: `eval/sec_cases/reviewed_gold_context/<case_id>.jsonl`
- Approval: `reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_partial_approval.json`
- Build report: `reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_build_report.json`
- Gold gate: `reports/quality/sec_benchmark_v2_new20_newco_reviewed_gold_gate_mainline.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_new20_newco_reviewed_exact_value_ledger.json`
- Ledger-unit gate: `reports/quality/sec_benchmark_v2_new20_newco_ledger_unit_gate.json`

## Results

- Reviewed cases: 10.
- Reviewed facts: 69.
- Reviewed context rows: 79.
- Mainline reviewed-gold gate: 10/10 pass, 0 blockers, 0 warnings.
- Exact-value ledger rows: 69.
- Ledger-unit gate: 69/69 pass, 0 failures, 0 warnings.
- Script syntax check: passed.

## Decision

The new-company seed pack is no longer blocked at reviewed context/facts or ledger. The next valid step is a cloud new20 benchmark route using locked BGE-M3 pipeline-context retrieval, trace-aware Judgment Plan, and Qwen9B synthesis, followed by the standard deterministic post-gates.

Qwen3.6-27B-FP8 remains a separate diagnostic candidate and should not replace the Qwen9B main route until it passes prompt/context feasibility and benchmark post-gates.
