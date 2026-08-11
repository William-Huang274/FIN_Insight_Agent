# Model Run: 20260519_sec_benchmark_v1_1_reviewed2_gold_gates

## Summary
- Purpose: 将 v1.1 gold-expansion seed 中优先级最高的两个 case 收成 reviewed-gold artifacts，并补齐 CAPEX/FCF 派生值 gate，为后续 pipeline-context true-Qwen 泛化测试做输入准备。
- Status: completed
- Run type: reviewed artifact build + deterministic validation gates
- Timestamp: 2026-05-19 14:36:33 +08:00
- Environment: local Windows workspace `D:\FIN_Insight_Agent`

## Code And Command
- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮新增 v1.1 reviewed-gold builder、derived-metric gate、reviewed context/facts、v1.1 partial approval、ledger/gate reports 和 worklog 记录。
- Entry points:
  - `scripts/build_sec_benchmark_v1_1_reviewed_gold.py`
  - `scripts/validate_sec_gold_gate.py`
  - `scripts/build_sec_benchmark_exact_value_ledger.py`
  - `scripts/validate_sec_benchmark_ledger_units.py`
  - `scripts/validate_sec_benchmark_derived_metrics.py`
- Commands:

```powershell
python scripts/build_sec_benchmark_v1_1_reviewed_gold.py

python scripts/validate_sec_gold_gate.py `
  --cases-path eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl `
  --gold-context-dir eval/sec_cases/reviewed_gold_context `
  --gold-facts-dir eval/sec_cases/reviewed_gold_facts `
  --manual-review-path reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json `
  --gate mainline_scored `
  --case-id SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001 `
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 `
  --output-path reports/quality/sec_benchmark_v1_1_gold_gate_reviewed2_semiconductor_capex.json

python scripts/build_sec_benchmark_exact_value_ledger.py `
  --reviewed-facts-dir eval/sec_cases/reviewed_gold_facts `
  --approval-path reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json `
  --output-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json

python scripts/validate_sec_benchmark_ledger_units.py `
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json `
  --output-path reports/quality/sec_benchmark_v1_1_reviewed2_ledger_unit_gate.json

python scripts/validate_sec_benchmark_derived_metrics.py `
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json `
  --case-id CAPEX_FCF_TABLE_2023_2025_DIAG_001 `
  --output-path reports/quality/sec_benchmark_v1_1_reviewed2_derived_metric_gate.json
```

## Inputs
- Expansion cases: `eval/sec_cases/test_cases_v1_1_gold_expansion.jsonl`
- Reviewed-gold source evidence: SEC evidence and structured object artifacts under `data/processed_private`
- Seed candidates used only as reference, not as approved rows:
  - `eval/sec_cases/gold_context/SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001.jsonl`
  - `eval/sec_cases/gold_context/CAPEX_FCF_TABLE_2023_2025_DIAG_001.jsonl`
  - `eval/sec_cases/gold_facts/SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001.json`
  - `eval/sec_cases/gold_facts/CAPEX_FCF_TABLE_2023_2025_DIAG_001.json`

## Outputs
- Builder: `scripts/build_sec_benchmark_v1_1_reviewed_gold.py`
- Derived metric validator: `scripts/validate_sec_benchmark_derived_metrics.py`
- Partial approval: `reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json`
- Gold gate: `reports/quality/sec_benchmark_v1_1_gold_gate_reviewed2_semiconductor_capex.json`
- Exact ledger: `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- Ledger unit gate: `reports/quality/sec_benchmark_v1_1_reviewed2_ledger_unit_gate.json`
- Derived metric gate: `reports/quality/sec_benchmark_v1_1_reviewed2_derived_metric_gate.json`
- Reviewed context:
  - `eval/sec_cases/reviewed_gold_context/SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001.jsonl`
  - `eval/sec_cases/reviewed_gold_context/CAPEX_FCF_TABLE_2023_2025_DIAG_001.jsonl`
- Reviewed facts:
  - `eval/sec_cases/reviewed_gold_facts/SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001.json`
  - `eval/sec_cases/reviewed_gold_facts/CAPEX_FCF_TABLE_2023_2025_DIAG_001.json`

## Results
- Reviewed cases: 2.
- Semiconductor durability:
  - Context rows: 17 reviewed rows.
  - Facts: 6 rows.
  - Scope: NVIDIA Compute & Networking revenue proxy for fiscal 2023-2025 and AMD Data Center net revenue for fiscal 2023-2025, plus risk/comparability caveat context.
- CAPEX/FCF table:
  - Context rows: 41 reviewed rows.
  - Facts: 36 rows.
  - Scope: MSFT/GOOGL/META/AMZN operating cash flow, PP&E purchases/capex cash outflow, and deterministic FCF proxy for 2023-2025.
- Gold gate:
  - `can_enter_gate=true`
  - `case_count=2`
  - `status_counts={"pass":2}`
  - `overall_blocker_count=0`
- Exact-value ledger:
  - `approved_case_count=2`
  - `row_count=42`
- Ledger-unit gate:
  - `can_enter_gate=true`
  - `ledger_row_count=42`
  - `pass_count=42`
  - `fail_count=0`
- Derived metric gate:
  - `can_enter_gate=true`
  - `derived_row_count=12`
  - `pass_count=12`
  - `fail_count=0`

## Experiment Governance
- Hypothesis: The first two v1.1 seed cases can be promoted from noisy seed candidates into compact reviewed-gold inputs without weakening the reviewed10 baseline.
- Decision target: case-filtered gold gate, exact ledger rebuild, unit gate, and CAPEX/FCF derived metric gate must all pass for the two selected cases.
- Ceiling / upper bound: This run validates reviewed artifacts only. It does not measure retrieval recall, true-Qwen answer quality, or post-gate generalization.
- Baselines to beat: reviewed10 v1 baseline remains unchanged; v1.1 reviewed2 is a separate partial approval for expansion smoke.
- Split and leakage guard: SEC-only local artifacts; no external data; no model inference; no changes to `test_cases_v1.jsonl`.
- Stop conditions: If any seed row remained in reviewed context/facts, any required numeric fact was missing, any ledger unit failed, or any FCF proxy failed formula validation, do not proceed to pipeline-context true-Qwen on these cases.
- Decision label: proceed to case-filtered pipeline-context smoke for these two v1.1 cases.
- Mainline decision: Do not treat this as full benchmark promotion. `reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json` explicitly blocks full mainline scored test.

## Runtime Efficiency
- Wall time: sub-second deterministic scripts locally, excluding manual inspection.
- GPU utilization / memory: not applicable.
- Throughput: not material; artifacts are 2 cases and 42 ledger rows.
- Bottleneck diagnosis: manual canonical source selection remains the bottleneck for reviewed-gold expansion.
- Serving latency implication: none yet; next run should measure pipeline trace and true-Qwen synthesis on the 5090 or chosen cloud profile.

## Caveats And Next Step
- Not run: no pipeline-context retrieval trace, no true-Qwen synthesis, no SEC benchmark post-gates, no trap bundle, no full noisy benchmark.
- Known risks: NVIDIA Compute & Networking is a reportable-segment proxy and must stay caveated against AMD Data Center direct comparability; CAPEX/FCF table relies on negative cash-outflow sign discipline.
- Next decision: run these two v1.1 reviewed cases through pipeline-context true-Qwen plus post-gates before expanding to subscription visibility and ads/AI infrastructure cases.
