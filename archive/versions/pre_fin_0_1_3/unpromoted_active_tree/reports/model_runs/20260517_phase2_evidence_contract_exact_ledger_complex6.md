# Model Run: 20260517_phase2_evidence_contract_exact_ledger_complex6

## Summary
- Purpose: 为 6 个 `complex_insight` query 构建 deterministic `Evidence Object Contract` 与 `Exact-Value Ledger`，并验证它们对上一轮 v3 numeric-safe 输出的数值约束效果。
- Status: completed.
- Run type: deterministic artifact build + evaluation.
- Timestamp: 2026-05-17 CST.
- Environment: local `D:\FIN_Insight_Agent`.
- Decision label: diagnostic-only.

## Code And Command
- Git commit: `820df59` with dirty worktree from current phase artifacts and scripts.
- Entry points:
  - `scripts/build_evidence_object_contracts.py`
  - `scripts/build_exact_value_ledger.py`
  - `scripts/validate_numeric_claims_against_ledger.py`

```powershell
python scripts\build_evidence_object_contracts.py `
  --query-contract-path reports\query_contracts\sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json `
  --grouped-pool-path reports\evidence_pool\sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json `
  --output-path reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json `
  --report-path reports\quality\sec_tech_10k_expanded_v0_2_complex6_evidence_object_contract_validation.json

python scripts\build_exact_value_ledger.py `
  --contracts-path reports\evidence_packs\sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json `
  --output-path reports\exact_value_ledgers\sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json `
  --report-path reports\quality\sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger_validation.json

python scripts\validate_numeric_claims_against_ledger.py `
  --synthesis-path reports\demo\qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_repaired.json `
  --ledger-path reports\exact_value_ledgers\sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json `
  --output-path reports\quality\qwen9b_longctx_128k_contract_v3_numeric_claims_vs_exact_ledger.json
```

## Inputs
- Query Contract: `reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json`.
- Grouped evidence pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Structured objects:
  - `data/processed_private/structured_objects/sec_tech_10k_metrics.jsonl`
  - `data/processed_private/structured_objects/sec_tech_10k_tables.jsonl`
  - `data/processed_private/structured_objects/sec_tech_10k_claims.jsonl`
- Replay target: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_repaired.json`.

## Outputs
- Evidence Object Contracts: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contracts.json`.
- Exact-Value Ledger: `reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json`.
- Evidence contract validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_evidence_object_contract_validation.json`.
- Ledger validation: `reports/quality/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger_validation.json`.
- Numeric replay validation: `reports/quality/qwen9b_longctx_128k_contract_v3_numeric_claims_vs_exact_ledger.json`.
- Summary: `reports/logs/evidence_contract_exact_ledger_complex6_summary.json`.

## Results
- Evidence Object Contract:
  - `3083` evidence refs processed.
  - `1908` unique objects.
  - role counts: `citation=925`, `background=2158`.
  - object type counts: `metric=2210`, `claim=822`, `table=51`.
  - structured hit rate: `1.0`.
  - primary facet citation coverage: `16/16 = 1.0`.
- Numeric candidates:
  - total numeric candidates: `2580`.
  - citation numeric candidates: `905`.
  - citation numeric candidates allowed into narrative: `838`.
  - major rejection reasons: `not_citation_evidence=1675`, `metric_family_unknown=217`, `display_value_unavailable=124`, `unit_unknown=124`, `metric_role_unknown=69`, `usd_source_scale_ambiguous=18`.
- Exact-Value Ledger:
  - ledger rows: `729`.
  - accept rate over all numeric candidates: `0.2826`.
  - role counts: `total_value=502`, `percentage_rate=154`, `period_change_amount=73`.
  - hard failures: none.
  - warnings: none.
- Replay against v3 numeric-safe output:
  - v3 numeric claims checked: `65`.
  - ledger pass: `43`.
  - ledger fail: `22`.
  - failure types: `numeric_claim_not_in_ledger=12`, `metric_role_not_allowed_by_ledger=7`, `cited_object_has_no_ledger_rows=3`.

## Interpretation
This layer has real blocking power. It would reject about one-third of the prior v3 numeric claims, including claims whose cited object has no ledger-backed exact value, claims with metric-role mismatch, and exact values copied in a form not authorized by the ledger. The layer is still intentionally broad: the ledger contains all safe candidate numbers, not just the few numbers that should appear in the final answer. Driver Pack generation must therefore select a small subset of `metric_id` rows for each driver.

## Experiment Governance
- Hypothesis: deterministic Evidence Object Contract + Exact-Value Ledger can reduce exact-value and metric-role drift before final synthesis.
- Decision target: structured hit rate near 1.0, primary facet coverage complete, ledger rows have no unknown metric role/family/display, and replay catches prior numeric risks.
- Result: target met for first diagnostic.
- Mainline decision: proceed to `Decision Driver Evidence Pack`; do not feed the full ledger directly to final synthesis.

## Safety Notes
- No LLM inference was run in this step.
- This does not prove final synthesis quality. It proves that numeric evidence can be constrained before synthesis.
- Remaining risk: metric-family rules are still broad for table metrics such as PP&E balances versus true capex cash outflows. Driver Pack selection and future metric-family refinements should narrow this.
