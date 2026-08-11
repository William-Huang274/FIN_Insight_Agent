# Model Run: 20260519_sec_benchmark_v2_pilot_reviewed_gold_gates

## Summary

- Purpose: promote the v2 pilot seed manifest into reviewed-gold artifacts for
  five non-trap cases and approve the Microsoft/YouTube trap for pipeline-only
  trap smoke.
- Status: completed
- Run type: deterministic artifact build + validation gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace, no GPU/model inference

## Code And Command

- Entry points:
  - `scripts/build_sec_benchmark_v2_pilot_reviewed_gold.py`
  - `scripts/validate_sec_gold_gate.py`
  - `scripts/validate_sec_benchmark.py`
  - `scripts/build_sec_benchmark_exact_value_ledger.py`
  - `scripts/validate_sec_benchmark_ledger_units.py`
- Commands:
  - `python scripts/build_sec_benchmark_v2_pilot_reviewed_gold.py`
  - `python scripts/validate_sec_benchmark.py --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl --gold-context-dir eval/sec_cases/reviewed_gold_context --output-path reports/quality/sec_benchmark_v2_pilot_reviewed_readiness.json`
  - `python scripts/validate_sec_gold_gate.py --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl --gold-context-dir eval/sec_cases/reviewed_gold_context --gold-facts-dir eval/sec_cases/reviewed_gold_facts --manual-review-path reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json --gate mainline_scored --case-id META_REALITY_LABS_2024_001 --case-id PANW_RPO_BILLINGS_NUMERIC_2023_2025_001 --case-id GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001 --case-id AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001 --case-id AMD_SEGMENT_MIX_2023_2025_001 --output-path reports/quality/sec_benchmark_v2_pilot_reviewed_gold_gate.json`
  - `python scripts/validate_sec_gold_gate.py --cases-path eval/sec_cases/test_cases_v2_pilot_seed.jsonl --gold-context-dir eval/sec_cases/reviewed_gold_context --gold-facts-dir eval/sec_cases/reviewed_gold_facts --manual-review-path reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json --gate trap_smoke --case-id MSFT_YOUTUBE_REVENUE_TRAP_001 --output-path reports/quality/sec_benchmark_v2_pilot_trap_smoke_gate.json`
  - `python scripts/build_sec_benchmark_exact_value_ledger.py --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts --approval-path reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json --output-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`
  - `python scripts/validate_sec_benchmark_ledger_units.py --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json --output-path reports/quality/sec_benchmark_v2_pilot_reviewed_ledger_unit_gate.json`
- Config: project-native SEC benchmark v1 schema plus v2 optional fields
- Seeds: not applicable

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
- Source evidence: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- Structured tables/metrics:
  - `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`
  - `data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl`
- Candidate boundary: reviewed SEC 10-K evidence and structured objects only
- Leakage guard: no model outputs or retrieval scores were used to tune facts

## Outputs

- Reviewed context/facts: `eval/sec_cases/reviewed_gold_context/` and
  `eval/sec_cases/reviewed_gold_facts/`
- Approval: `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json`
- Build report: `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_build_report.json`
- Readiness: `reports/quality/sec_benchmark_v2_pilot_reviewed_readiness.json`
- Gold gate: `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_gate.json`
- Trap gate: `reports/quality/sec_benchmark_v2_pilot_trap_smoke_gate.json`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`
- Ledger unit gate:
  `reports/quality/sec_benchmark_v2_pilot_reviewed_ledger_unit_gate.json`
- Regression:
  `reports/quality/sec_benchmark_v1_1_reviewed4_gold_gate_after_expected_facts_patch.json`

## Results

- Reviewed build: 5 non-trap cases, 40 reviewed facts, 63 context rows.
- Readiness: 6/6 pass, 0 warnings.
- Reviewed gold gate: 5/5 pass, no blockers or warnings.
- Trap smoke approval: 1/1 pass.
- Exact-value ledger: 40 rows.
- Ledger unit gate: 40/40 pass, 0 failures, 0 warnings.
- v1.1 reviewed4 regression: 4/4 pass after the expected-facts validator patch.

## Experiment Governance

- Hypothesis: compact reviewed facts plus optional `expected_facts` coverage can
  safely represent multi-row target cells without breaking old gold gate behavior.
- Decision target: v2 pilot readiness, reviewed gold, trap smoke, ledger unit,
  and v1.1 reviewed4 regression must all pass.
- Ceiling: deterministic annotation readiness only; no BGE-M3 retrieval or
  Qwen answer-quality claim.
- Baselines to beat: v1.1 reviewed4 deterministic gold gates.
- Split and leakage guard: SEC-only reviewed source rows; no model-output tuning.
- Stop conditions: any gate failure blocks pipeline-context inference.
- Decision label: proceed to BGE-M3 pipeline-context pilot smoke.
- Mainline decision: diagnostic-only; full v2 remains blocked.

## Runtime Efficiency

- Wall time: local deterministic scripts completed in seconds.
- GPU utilization / memory: not applicable.
- Bottleneck diagnosis: none for deterministic gates; next bottleneck is
  pipeline-context retrieval/synthesis and v2-specific post-gates.

## Caveats And Next Step

- Not run: no Qwen/vLLM inference and no BGE-M3 pipeline-context retrieval run.
- Known risks: v2-specific entity-separation/source-policy/proxy validators are
  not all implemented yet.
- Next decision: run the reviewed v2 pilot through the fixed BGE-M3 pipeline
  route and true-Qwen post-gates.
