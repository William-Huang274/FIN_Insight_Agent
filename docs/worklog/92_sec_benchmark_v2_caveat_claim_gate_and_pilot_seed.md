# SEC Benchmark v2 Caveat/Claim Gate And Pilot Seed

## Summary

Date: 2026-05-19

This entry records the first v2 validator-first expansion step after the v1.1 reviewed4 BGE-M3 + Judgment Plan planfix run.

The work is still seed/diagnostic only. No new v2 case is reviewed gold yet, and no new Qwen inference was run.

## Governance

- Hypothesis: manifest-native `required_caveats` and `disallowed_claims` can catch v2-style overclaim failures before expanding the gold set.
- Decision target: reviewed4 planfix must continue passing all existing gates and the new caveat/claim gate; v2 pilot seed must pass schema/source readiness without hard failures.
- Ceiling: current v2 pilot has no reviewed gold context, so it can only support manifest/readiness decisions.
- Baseline: v1.1 reviewed4 BGE-M3 planfix output.
- Split/leakage guard: no model tuning or inference; added manifest annotations and deterministic validators only.
- Stop condition: any reviewed4 regression in answer-ledger, answer-vs-plan, named-fact, table-cell, ledger-unit, or caveat/claim gate blocks v2 pilot work.
- Decision label: proceed to annotation planning, diagnostic-only for v2 seed.

## Work Completed

Added a manifest-native validator:

- `scripts/validate_sec_benchmark_caveat_claims.py`
  - validates `required_caveats`
  - validates `disallowed_claims`
  - supports the same pattern style used by existing abstract-rubric checks: plain string, `re:` regex, `all_of_any`, `allow_if_any`, and `allow_if_any_near`
  - skips old cases without these fields

Integrated the gate:

- `scripts/run_sec_benchmark_post_gates.py`
  - adds `--skip-caveat-claim-gate`
  - writes `sec_benchmark_caveat_claim_gate.json`
  - includes `caveat_claim_gate_pass` and `caveat_claim_summary` in `sec_benchmark_post_gates_summary.json`

Updated synthesis/planning contract surface:

- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - injects manifest `Required Caveats` and `Disallowed Claims` into the final-answer prompt
- `scripts/build_sec_benchmark_judgment_plan.py`
  - carries manifest disallowed-claim summaries into `do_not_overstate`

Annotated the current v1.1 reviewed4 manifest:

- `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
  - added v2-style `required_caveats` and `disallowed_claims` for all four reviewed4 cases

Created the v2 pilot seed manifest:

- `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
  - `META_REALITY_LABS_2024_001`
  - `PANW_RPO_BILLINGS_NUMERIC_2023_2025_001`
  - `GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001`
  - `AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001`
  - `AMD_SEGMENT_MIX_2023_2025_001`
  - `MSFT_YOUTUBE_REVENUE_TRAP_001`

## Results

Reviewed4 caveat/claim gate:

- Report: `reports/quality/sec_benchmark_v1_1_reviewed4_caveat_claim_gate_planfix.json`
- `can_enter_gate=true`
- checked cases: 4/4
- required caveats: 9/9 covered
- disallowed claims: 11 checked
- violations: 0

Reviewed4 full post-gates after integration:

- Summary: `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_5090_planfix_post_gates/sec_benchmark_post_gates_summary.json`
- `qwen_answer_ratio=1.0`
- `answer_vs_judgment_plan_gate_pass=true`, 4/4
- `answer_ledger_gate_pass=true`, exact-value hits 20
- `table_cell_gate_pass=true`, 36/36 valid cells
- `named_fact_gate_pass=true`, unsupported token count 0
- `ledger_missing_consistency_gate_pass=true`, false missing 0
- `ledger_unit_gate_pass=true`, 69/69
- `caveat_claim_gate_pass=true`, required caveats 9/9, disallowed violations 0

Manifest readiness:

- Reviewed4 with v2 fields: `reports/quality/sec_benchmark_v1_1_reviewed4_with_v2_fields_readiness.json`
  - 4/4 pass, no hard failures, no warnings
- v2 pilot seed readiness: `reports/quality/sec_benchmark_v2_pilot_seed_readiness.json`
  - 6/6 pass, no hard failures
  - warnings: `gold_context_missing=5`, expected because non-trap v2 pilot cases are seed-only
- v2 pilot seed BM25 smoke: `reports/quality/sec_benchmark_v2_pilot_seed_bm25_smoke.json`
  - 6/6 pass, no hard failures
  - warnings: `gold_context_missing=5`

Py-compile passed for:

- `scripts/validate_sec_benchmark_caveat_claims.py`
- `scripts/run_sec_benchmark_post_gates.py`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- `scripts/build_sec_benchmark_judgment_plan.py`

## Decision

The v2 validator-first gate is ready for pilot annotation work.

The v2 pilot seed is source-ready but not gold-ready. The next step is to annotate reviewed context/facts for the five non-trap pilot cases and keep the wrong-attribution trap as a pipeline-only source-policy case.
