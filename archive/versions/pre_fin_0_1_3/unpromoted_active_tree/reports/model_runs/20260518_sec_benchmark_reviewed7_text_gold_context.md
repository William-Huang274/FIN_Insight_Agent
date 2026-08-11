# Model Run: 20260518_sec_benchmark_reviewed7_text_gold_context

## Summary
- Purpose: Expand the reviewed SEC benchmark gold-context subset beyond the four numeric regression cases by manually trimming three text-heavy summary cases: `SNOW_RISK_2023_2025_001`, `NVDA_DATACENTER_2023_2025_001`, and `MSFT_AI_CLOUD_2023_2025_001`.
- Status: diagnostic-only
- Run type: artifact build + context gate evaluation
- Timestamp: 2026-05-18 17:10:39 +08:00
- Environment: local Windows workspace

## Code And Command
- Entry points:
  - `scripts/validate_sec_gold_gate.py`
  - `scripts/build_sec_benchmark_exact_value_ledger.py`
  - `scripts/run_sec_benchmark_eval.py`
  - `scripts/validate_sec_benchmark_ledger_units.py`
- Commands:
```powershell
python scripts/validate_sec_gold_gate.py --gold-context-dir eval/sec_cases/reviewed_gold_context --gold-facts-dir eval/sec_cases/reviewed_gold_facts --manual-review-path reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json --gate mainline_scored --case-id AMZN_AWS_NUMERIC_2023_2025_001 --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 --case-id AAPL_SERVICES_MARGIN_2023_2025_001 --case-id PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001 --case-id SNOW_RISK_2023_2025_001 --case-id NVDA_DATACENTER_2023_2025_001 --case-id MSFT_AI_CLOUD_2023_2025_001 --output-path reports/quality/sec_benchmark_v1_gold_gate_reviewed7_text_plus_numeric_cases.json
python scripts/build_sec_benchmark_exact_value_ledger.py --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts --approval-path reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json --output-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json
python scripts/run_sec_benchmark_eval.py --mode gold_context --gold-context-dir eval/sec_cases/reviewed_gold_context --output-dir reports/quality/local_reviewed7_text_plus_numeric_context_trace_smoke --case-id AMZN_AWS_NUMERIC_2023_2025_001 --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 --case-id AAPL_SERVICES_MARGIN_2023_2025_001 --case-id PANW_SUBSCRIPTION_VISIBILITY_2023_2025_001 --case-id SNOW_RISK_2023_2025_001 --case-id NVDA_DATACENTER_2023_2025_001 --case-id MSFT_AI_CLOUD_2023_2025_001
python scripts/validate_sec_benchmark_ledger_units.py --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json --output-path reports/quality/local_reviewed7_text_plus_numeric_ledger_unit_gate.json
```
- Git commit / dirty files: workspace is dirty from the active SEC benchmark work; no commit created.
- Seeds: deterministic artifact build from existing SEC evidence objects; no random seed.

## Inputs
- Cases path: `eval/sec_cases/test_cases_v1.jsonl`
- Source evidence: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- Reviewed context dir: `eval/sec_cases/reviewed_gold_context`
- Reviewed facts dir: `eval/sec_cases/reviewed_gold_facts`
- Approval path: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`
- Leakage guard: gold-context rows were built only from SEC 10-K evidence objects and source-containment checked against the original evidence text.

## Outputs
- New reviewed context:
  - `eval/sec_cases/reviewed_gold_context/SNOW_RISK_2023_2025_001.jsonl` with 9 reviewed rows.
  - `eval/sec_cases/reviewed_gold_context/NVDA_DATACENTER_2023_2025_001.jsonl` with 12 reviewed rows.
  - `eval/sec_cases/reviewed_gold_context/MSFT_AI_CLOUD_2023_2025_001.jsonl` with 11 reviewed rows.
- New reviewed facts:
  - `eval/sec_cases/reviewed_gold_facts/SNOW_RISK_2023_2025_001.json`
  - `eval/sec_cases/reviewed_gold_facts/NVDA_DATACENTER_2023_2025_001.json`
  - `eval/sec_cases/reviewed_gold_facts/MSFT_AI_CLOUD_2023_2025_001.json`
- Updated approval: `reports/quality/sec_benchmark_v1_reviewed_gold_partial_approval.json`
- Gate reports:
  - `reports/quality/sec_benchmark_v1_gold_gate_reviewed7_text_plus_numeric_cases.json`
  - `reports/quality/local_reviewed7_text_plus_numeric_context_trace_smoke/`
  - `reports/quality/local_reviewed7_text_plus_numeric_ledger_unit_gate.json`
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`

## Results
- Reviewed approval case count: 7.
- Gold gate: `can_enter_gate=true`; 7/7 pass; no blockers or warnings.
- Seed leakage check: all 7 approved cases have `seed_rows=0` and `seed_facts=0`.
- Context-only trace: 7/7 `context_prepared`.
- Context rows:
  - SNOW: 9 evidence-object rows.
  - NVDA: 12 evidence-object rows.
  - MSFT: 11 evidence-object rows.
  - AMZN: 11 rows, including 6 structured objects.
  - GOOGL: 5 rows, including 2 structured objects.
  - AAPL: 6 structured-object rows.
  - PANW: 3 structured-object rows.
- Exact-value ledger: approved case count 7, row count remains 17 because the three new text-heavy cases intentionally have no target numeric facts.
- Ledger unit gate: 17/17 pass, 0 fail.

## Experiment Governance
- Hypothesis: manually trimmed SEC excerpts for the three text-heavy cases can enter case-filtered gold-context testing without seed noise or unreviewed numeric facts.
- Decision target: reviewed gold gate passes for the 7 approved cases; context trace prepares all 7 cases; exact-value ledger remains limited to reviewed numeric facts.
- Ceiling / upper bound: this does not approve the full benchmark because remaining diagnostic/table cases still lack reviewed target facts or trimmed context.
- Baselines to beat: previous reviewed4 subset with four numeric regression cases.
- Split and leakage guard: no model tuning or full benchmark claim; this is an artifact-readiness gate over approved case IDs only.
- Stop conditions: any seed row, seed fact, missing context, or ledger unit failure would block progression.
- Decision label: diagnostic-only
- Mainline decision: approved for case-filtered gold-context smoke on these 7 cases only; full benchmark mainline remains blocked.

## Runtime Efficiency
- Wall time: local gate and context-only commands completed within seconds.
- GPU utilization: none.
- Throughput: not applicable; no model inference was run.

## Safety Notes
- No cloud password or private credential was written to files.
- The three new text-heavy cases may contain exact numbers in SEC source excerpts; final synthesis must still obey the Exact-Value Ledger rule and avoid copying non-ledger numbers as precise claims.
- Next step should run a true-Qwen gold-context synthesis smoke for these 3 text-heavy cases before expanding to the remaining diagnostic/table cases.
