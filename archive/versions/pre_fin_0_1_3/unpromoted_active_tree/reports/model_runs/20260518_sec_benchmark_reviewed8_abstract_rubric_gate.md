# Model Run: 20260518_sec_benchmark_reviewed8_abstract_rubric_gate

## Summary
- Purpose: 扩展 reviewed SEC benchmark gold 到 Cloud L4 diagnostic case，并把“中文抽象判断是否覆盖充分”落成可执行人工 rubric / critic gate。
- Status: completed, case-filtered diagnostic-only.
- Run type: artifact build + deterministic evaluation gates.
- Timestamp: 2026-05-18.
- Environment: local deterministic scripts on Windows workspace.

## Code And Command
- Entry points:
  - `scripts/build_sec_benchmark_exact_value_ledger.py`
  - `scripts/validate_sec_gold_gate.py`
  - `scripts/validate_sec_benchmark_abstract_judgment_rubric.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Reviewed ledger rebuild:
  - `python scripts/build_sec_benchmark_exact_value_ledger.py --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts --approval-path reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json --output-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Reviewed8 gold gate:
  - `python scripts/validate_sec_gold_gate.py --gate mainline_scored --gold-context-dir eval/sec_cases/reviewed_gold_context --gold-facts-dir eval/sec_cases/reviewed_gold_facts --manual-review-path reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json --case-id AMZN_AWS_NUMERIC_2023_2025_001 --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 --case-id AAPL_SERVICES_MARGIN_2023_2025_001 --case-id PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001 --case-id SNOW_RISK_2023_2025_001 --case-id NVDA_DATACENTER_2023_2025_001 --case-id MSFT_AI_CLOUD_2023_2025_001 --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 --output-path reports/quality/sec_benchmark_v1_gold_gate_reviewed8_text_numeric_cloud.json`
- Reviewed7 bundle post-gate regression:
  - `python scripts/run_sec_benchmark_post_gates.py --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed7_gold_reference_qwen9b_mixed --pipeline-run-dir eval/sec_cases/outputs/run_20260518_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle --output-dir reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates --min-qwen-answer-ratio 1.0`
- Code changes were in a dirty worktree; no git commit was created.

## Inputs
- New reviewed Cloud case: `CLOUD_PROFITABILITY_2023_2025_DIAG_001`.
- New reviewed context: `eval/sec_cases/reviewed_gold_context/CLOUD_PROFITABILITY_2023_2025_DIAG_001.jsonl`.
- New reviewed facts: `eval/sec_cases/reviewed_gold_facts/CLOUD_PROFITABILITY_2023_2025_DIAG_001.json`.
- Updated approval file: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`.
- Abstract judgment rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`.

## Outputs
- Reviewed exact ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`.
- Reviewed8 gold gate report: `reports/quality/sec_benchmark_v1_gold_gate_reviewed8_text_numeric_cloud.json`.
- Abstract judgment direct report: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_abstract_judgment_gate.json`.
- Full post-gates summary with abstract gate: `reports/quality/local_reviewed7_sanitized_cnlimit_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`.

## Results
- Reviewed approval expanded from 7 to 8 approved case-filtered smoke cases.
- Reviewed exact ledger expanded from 17 to 35 rows.
- Reviewed8 gold gate: `can_enter_gate=true`, `status_counts={"pass": 8}`, `overall_blocker_count=0`.
- Abstract judgment gate on the existing reviewed7+2 trap bundle:
  - `can_enter_gate=true`.
  - `checked_case_count=7`, `pass_count=7`, `fail_count=0`, `skip_count=2`.
  - `required_dimension_count=25`, `covered_required_dimension_count=25`.
- Full post-gates regression:
  - `trap_gate_pass=true`.
  - `gold_vs_pipeline_pass=true`.
  - `answer_ledger_gate_pass=true`.
  - `metric_role_term_gate_pass=true`.
  - `named_fact_gate_pass=true`.
  - `abstract_judgment_gate_pass=true`.
  - `ledger_unit_gate_pass=true`, now over `ledger_row_count=35`.
  - `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`.

## Interpretation
- Cloud L4 is now reviewed enough to enter case-filtered gold-context smoke. The approval remains partial; full benchmark mainline is still blocked.
- The Cloud case explicitly separates AWS/Google Cloud comparable revenue and operating income from Microsoft Cloud broad proxy revenue and gross margin. Microsoft Cloud support rows can inform disclosure scope, growth, margin pressure, and caveats, but must not support a simple directly comparable cloud-profitability winner claim.
- The abstract judgment rubric is a deterministic hard gate, not an LLM critic. It checks whether the final Chinese synthesis covers case-specific judgment dimensions, decision-driver structure, caveat calibration, and forbidden overclaim patterns.
- Current reviewed7 pipeline outputs pass this new abstract gate, so the gate did not break the existing accepted reviewed7+trap bundle.

## Governance
- Decision label: diagnostic-only.
- Mainline decision: proceed to the next reviewed-case generation/testing step only under case-filtered reviewed gold; do not promote full benchmark.
- Boundary: no new Cloud Qwen synthesis was run in this step. This run only approves Cloud gold artifacts and validates the gate framework against the existing reviewed7 bundle.

## Caveats And Next Step
- The abstract rubric uses explicit phrase/pattern coverage. It is intentionally auditable but not a full semantic judge.
- Next useful test is a reviewed8 case-filtered synthesis run that includes the Cloud L4 case, then rerun post-gates with the same abstract judgment rubric.
