# Worklog: SEC Benchmark v2 Pilot Plus4 AMZN Reviewed-Gold Audit

Date: 2026-05-19

## Prompt

User asked to continue after the next v2 reviewed-batch design and start the
first concrete case promotion. The requested constraint remains: keep BGE-M3 as
the fixed pipeline-context final selector; do not drift back to BM25-only.

## Decision

Promote `AMZN_AWS_NUMERIC_2023_2025_001` first because it already has reviewed
AWS revenue and AWS operating-income facts/context and does not require a new
validator before deterministic gates.

This step is reviewed-gold artifact work only. No BGE trace, Judgment Plan, or
Qwen inference was run in this step.

## Work Completed

- Added `scripts/build_sec_benchmark_v2_pilot_plus4_reviewed_gold.py`.
- Generated `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`.
- Reused existing reviewed AMZN artifacts:
  - `eval/sec_cases/reviewed_gold_context/AMZN_AWS_NUMERIC_2023_2025_001.jsonl`
  - `eval/sec_cases/reviewed_gold_facts/AMZN_AWS_NUMERIC_2023_2025_001.json`
- Added v2 manifest fields for AMZN:
  - `case_family=v2_pilot_plus4`
  - `required_caveats`
  - `disallowed_claims`
  - stricter hard-gate and hallucination-trap coverage for YoY percentages,
    segment scope, and operating-income role separation.
- Generated approval/build reports:
  - `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_partial_approval.json`
  - `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_build_report.json`

## Result

Plus4 deterministic gate status:

- Readiness: pass, 10/10 cases.
- Reviewed-gold mainline gate: pass, 9/9 non-trap reviewed cases.
- Trap smoke: pass, 1 trap case, 9 non-applicable skipped.
- Exact-value ledger: generated 86 rows for 9 approved reviewed cases.
- Ledger-unit gate: pass, 86/86 rows.

Key output paths:

- Manifest: `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`
- Readiness:
  `reports/quality/sec_benchmark_v2_pilot_plus4_readiness.json`
- Mainline gold gate:
  `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_mainline.json`
- Trap smoke:
  `reports/quality/sec_benchmark_v2_pilot_plus4_reviewed_gold_gate_trap_smoke.json`
- Ledger-unit:
  `reports/quality/sec_benchmark_v2_pilot_plus4_ledger_unit_gate.json`

## BGE-M3 Policy

The plus4 build report explicitly preserves the retrieval policy:

- `final_context_selector=BAAI/bge-reranker-v2-m3`
- `bm25_role=candidate_generator_only`
- `bm25_only_allowed=false`

This locks the intended future pipeline-context route for the next Qwen run.

## Follow-Up

Next practical options:

1. Run plus4 pipeline-context with BGE-M3 trace, Judgment Plan, RTX 5090 Qwen9B,
   and full post-gates.
2. Build the next reviewed case:
   `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001`.

Safety notes:

- No model inference was run.
- No secrets or cloud credentials were written.
- Existing 4090/5090 hardware configs were not changed.
