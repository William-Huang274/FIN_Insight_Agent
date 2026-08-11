# Model Run: 20260517_phase2_driver_pack_ledger_synthesis_qwen9b_complex6

## Summary
- Purpose: 将 `qwen9b_normalized` Decision Driver Evidence Pack 接入 final synthesis，并限制精确数字只能来自 Exact-Value Ledger 的 `metric_id/display_value_zh`。
- Status: diagnostic-only completed.
- Run type: inference + validation.
- Timestamp: 2026-05-17.
- Environment: cloud RTX 4090, `/root/miniconda3/bin/python3`, Qwen3.5-9B FP16, vLLM 128k.

## Code And Command
- Entry point: `scripts/run_calibrated_synthesis_demo.py`.
- Main command: `python3 scripts/run_calibrated_synthesis_demo.py --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B --driver-pack-path reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json --driver-pack-candidate-path reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json --exact-value-ledger-path reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json --max-model-len 131072 --synthesis-max-tokens 8500 --context-safety-margin 1200 --dtype float16 --gpu-memory-utilization 0.95 --max-num-seqs 1 --output reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500.json`
- Repair command: `python3 scripts/repair_synthesis_citations.py --synthesis-path reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500.json --output-path reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired.json --repair-report-path reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repair_report.json --ledger-path reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json`
- Code changes: final synthesis driver-pack package builder now filters ledger augmentation by `query_id`, hides `contract_id/supporting_contract_ids` from the model prompt, and post-repairs cited `metric_id` to ledger `object_id`.

## Inputs
- Query set: 6 complex-insight queries from expanded v0.2.
- Driver Pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json`.
- Candidate pack: `reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json`.
- Exact-Value Ledger: `reports/exact_value_ledgers/sec_tech_10k_expanded_v0_2_complex6_exact_value_ledger.json`.

## Outputs
- Raw synthesis: `reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500.json`.
- Repaired synthesis: `reports/demo/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired.json`.
- Repair report: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repair_report.json`.
- Citation validation: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired_citation_validation.json`.
- Numeric ledger validation: `reports/quality/qwen9b_driver_pack_ledger_complex6_queryfiltered_8500_repaired_numeric_ledger_validation.json`.
- Run log: `reports/logs/qwen9b_driver_pack_ledger_synthesis_complex6_queryfiltered_8500.log`.

## Results
- Parse: `6/6` parsed.
- Model self-quality: `good=4`, `weak=2`.
- Prompt tokens: `10,479` to `17,471`.
- Runtime: model load `60.3147s`, total `871.4676s`; per-query elapsed `83.4952s` to `182.329s`.
- Repaired summary: cited object precision against input `1.0`; invalid cited object IDs `0`.
- Citation validator: `6/6` pass, hard failures `0`; warnings: `number_not_verbatim_in_cited_text=7`, `numeric_conversion_without_role_check=10`.
- Numeric ledger validator: `58/58` numeric claims pass, prose exact values `26`, prose failures `0`.
- Repair layer: `25` applied, `0` rejected. Repairs were metric-id-to-object-id citation mapping and unique authorized display-value numeric_claim backfill.

## Manual Review
- Positive: Driver Pack + Ledger mode materially reduces free-form numeric/unit risk; exact values are auditable through `metric_id` and `display_value_zh`, and caveats now visibly downgrade weak conclusions in ads/AI infra and semiconductor durability.
- Positive: `platform_services_recurring_quality` no longer shows the prior most obvious unit/role drift; Apple margin, Microsoft cloud margin, and Adobe subscription revenue are ledger-backed.
- Remaining semantic issue: `cloud_profitability_comparison` still contains a trend statement that says Google Cloud revenue grew from `330.88 亿美元` to `139.1 亿美元`. The value `139.1 亿美元` is ledger-backed but comes from a Google Cloud segment operating income table row that was labeled as `cloud_revenue total_value`; this is an upstream Evidence Object Contract / metric-family table-context error, not a final-copy error.
- Remaining quality issue: `ai_capex_monetization` is too compressed after Driver Pack constraints. It passes hard gates but gives only one real driver and reads more like a guarded summary than a rich analyst answer.

## Experiment Governance
- Hypothesis: Normalized Driver Pack plus Exact-Value Ledger can preserve 9B judgment while reducing unsupported exact numeric claims.
- Decision target: 6 complex-insight queries parsed, citation pass, numeric claims/prose exact values fully ledger-backed.
- Result: Hard target passed after deterministic repair.
- Mainline decision: diagnostic-only. Do not promote until metric-family/table-context conflicts are gated and relation/trend consistency is validated.

## Follow-Up
- Add a ledger/table-context validator for rows where `metric_family` conflicts with source table context, for example `cloud_revenue` values coming from `segment operating income`.
- Add numeric relation validation for prose patterns such as `从 X 增长至 Y`; exact ledger correctness is insufficient if the relation direction contradicts the values.
- Improve Driver Pack candidate selection so final synthesis gets the right Google Cloud revenue row (`587.05 亿美元` / `432.29 亿美元` depending on intended fiscal/source context) rather than operating income mislabeled as revenue.
