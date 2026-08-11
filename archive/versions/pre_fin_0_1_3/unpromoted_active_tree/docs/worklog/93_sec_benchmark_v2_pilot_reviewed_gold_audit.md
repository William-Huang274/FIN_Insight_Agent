# SEC Benchmark v2 Pilot Reviewed Gold Audit

## Summary

Date: 2026-05-19

This entry closes the v2 pilot reviewed-gold annotation step. It does not run
new model inference and does not promote the full v2 benchmark. The BGE-M3
pipeline route remains the required next pipeline-context path.

## Governance

- Hypothesis: the six-case v2 pilot can be moved from seed-only into a
  reviewed-gold pilot by adding compact cell-level target facts, caveat context,
  and explicit source-policy treatment for the trap case.
- Decision target: five non-trap cases must pass case-filtered reviewed gold
  gate; the wrong-attribution trap must pass trap-smoke approval; the new
  ledger must pass unit/scale validation; v1.1 reviewed4 must not regress.
- Ceiling: this step proves reviewed-gold and ledger readiness only. It does not
  measure BGE-M3 retrieval, Judgment Plan quality, or Qwen final-answer quality.
- Baseline: v1.1 reviewed4 BGE-M3 + trace-aware Judgment Plan planfix gates.
- Split/leakage guard: deterministic annotation/gates only; no threshold tuning
  on model outputs.
- Stop condition: any reviewed gold mismatch, source/unit failure, trap approval
  failure, or v1.1 reviewed4 regression blocks the v2 pilot pipeline run.
- Decision label: proceed to case-filtered BGE-M3 pipeline-context smoke.

## Work Completed

Added optional expected fact dimensions to the gold gate:

- `scripts/validate_sec_gold_gate.py`
  - supports per-check `expected_facts`
  - allows multiple target facts inside the same metric family when they are
    separated by row label, metric name, column label, or segment
  - preserves old behavior for cases without `expected_facts`

Updated the v2 pilot manifest:

- `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
  - added `expected_facts` for Meta Family of Apps / Reality Labs segment
    cells
  - added `expected_facts` for Apple Products / Services gross-margin
    percentage cells
  - added `expected_facts` for AMD Data Center / Client / Gaming / Embedded
    segment revenue cells

Added a reproducible reviewed-gold builder:

- `scripts/build_sec_benchmark_v2_pilot_reviewed_gold.py`
  - writes reviewed context/facts for the five non-trap v2 pilot cases
  - writes a partial approval report
  - keeps `MSFT_YOUTUBE_REVENUE_TRAP_001` as pipeline-only trap approval

Generated artifacts:

- `eval/sec_cases/reviewed_gold_context/META_REALITY_LABS_2024_001.jsonl`
- `eval/sec_cases/reviewed_gold_context/PANW_RPO_BILLINGS_NUMERIC_2023_2025_001.jsonl`
- `eval/sec_cases/reviewed_gold_context/GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001.jsonl`
- `eval/sec_cases/reviewed_gold_context/AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001.jsonl`
- `eval/sec_cases/reviewed_gold_context/AMD_SEGMENT_MIX_2023_2025_001.jsonl`
- `eval/sec_cases/reviewed_gold_facts/META_REALITY_LABS_2024_001.json`
- `eval/sec_cases/reviewed_gold_facts/PANW_RPO_BILLINGS_NUMERIC_2023_2025_001.json`
- `eval/sec_cases/reviewed_gold_facts/GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001.json`
- `eval/sec_cases/reviewed_gold_facts/AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001.json`
- `eval/sec_cases/reviewed_gold_facts/AMD_SEGMENT_MIX_2023_2025_001.json`
- `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json`
- `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`

## Reviewed Fact Scope

- Meta Reality Labs case: 4 facts for fiscal 2024 Family of Apps and Reality
  Labs revenue plus operating income/loss.
- PANW visibility case: 6 facts covering subscription/support revenue for
  2023-2025 plus one visibility metric per year: 2023 billings, 2024 billings,
  and 2025 RPO.
- Alphabet/Meta ads privacy case: 6 advertising revenue facts for 2023-2025.
- Apple product/services case: 12 facts covering Products net sales, Services
  net sales, Products gross-margin percentage, and Services gross-margin
  percentage for 2023-2025.
- AMD segment mix case: 12 facts covering Data Center, Client, Gaming, and
  Embedded revenue for 2023-2025.

Total reviewed facts: 40.

## Results

Build report:

- `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_build_report.json`
- reviewed cases: 5
- reviewed facts: 40
- context rows: 63

Readiness:

- `reports/quality/sec_benchmark_v2_pilot_reviewed_readiness.json`
- pass: 6/6
- hard failures: 0
- warnings: 0

Reviewed gold gate:

- `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_gate.json`
- `can_enter_gate=true`
- pass: 5/5 non-trap reviewed cases
- blocker types: none
- warning types: none

Trap smoke approval:

- `reports/quality/sec_benchmark_v2_pilot_trap_smoke_gate.json`
- `can_enter_gate=true`
- pass: 1/1 trap case

Exact-value ledger:

- `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`
- approved cases: 5
- ledger rows: 40

Ledger unit gate:

- `reports/quality/sec_benchmark_v2_pilot_reviewed_ledger_unit_gate.json`
- `can_enter_gate=true`
- pass: 40/40
- failures: 0
- warnings: 0

Regression:

- `reports/quality/sec_benchmark_v1_1_reviewed4_gold_gate_after_expected_facts_patch.json`
- v1.1 reviewed4 pass: 4/4

Py-compile passed for:

- `scripts/validate_sec_gold_gate.py`
- `scripts/build_sec_benchmark_v2_pilot_reviewed_gold.py`
- `scripts/validate_sec_benchmark.py`

## Decision

The v2 pilot is now reviewed-gold ready for a case-filtered smoke. Do not treat
this as full v2 approval.

Next execution should be a BGE-M3 pipeline-context run over the v2 pilot cases,
with true-Qwen synthesis and post-gates. Do not use BM25 as the final selector.

Before or alongside that run, add deterministic v2 validators for:

- peer entity separation;
- wrong-attribution/source-policy refusal;
- proxy-as-direct metric claims;
- non-comparable metric comparison;
- prior-period or percentage-change cells used as target values.

No Qwen/vLLM inference was run in this step.
