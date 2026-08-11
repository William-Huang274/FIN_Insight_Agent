# Model Run: 20260517_phase2_longctx_contract_v3_numeric_safe_patch

## Summary
- Purpose: 对 v3 contract 中触发 metric-role narrative warning 的两条 complex-insight query 做 targeted rerun，验证更严格 exact-value rendering prompt 是否能消除 period-change amount 被写进 total-value 趋势句的问题。
- Status: diagnostic-only。
- Run type: inference + patch merge + deterministic repair + evaluation。
- Timestamp: 2026-05-17。
- Environment: cloud RTX 4090 for Qwen3.5-9B FP16/vLLM inference; local Windows for repair, validation, scoring, and ledger updates.

## Code And Command
- Entry point: `scripts/run_calibrated_synthesis_demo.py`。
- Validators: `scripts/repair_synthesis_citations.py`, `scripts/validate_synthesis_citations.py`, `scripts/score_synthesis_quality.py`。
- Prompt change:
  - `thesis_zh` and `decision_drivers` should prioritize judgment over exact currency values.
  - If exact values appear in narrative text, the nearby wording must identify the metric role: `period_change_amount` requires increase/decrease/change wording, `total_value` requires total/scale/balance wording, and `percentage_rate` requires rate/ratio wording.
  - Before returning JSON, the model must rewrite any sentence where a `period_change_amount` display value appears with total-value trend words such as "from/to/reached".
- Validator change:
  - Fixed a false positive where dollar-denominated values inside sentences mentioning "effective tax rate" were inferred as percentage rates. Role inference now prefers raw value/unit before source text keywords.
- Git commit / dirty files: dirty worktree; Phase 2 scripts/reports are uncommitted.
- Seeds: vLLM default seed 0.

## Inputs
- Grouped evidence pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Eval set: `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Rerun query IDs:
  - `expanded_insight_ai_capex_monetization_2023_2025`
  - `expanded_insight_platform_services_recurring_quality_2023_2025`
- Patch baseline: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_merged_repaired.json`.
- Candidate boundary: citation-only calibrated evidence; background evidence count was 0.

## Outputs
- Two-query rerun raw output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex2_contract_v3_numeric_safe_8500.json`.
- Two-query rerun repaired output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex2_contract_v3_numeric_safe_8500_repaired.json`.
- Two-query citation validation: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex2_contract_v3_numeric_safe_8500_citation_validation.json`.
- Two-query answer quality: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex2_contract_v3_numeric_safe_8500_answer_quality.json`.
- Patched six-query output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_repaired.json`.
- Patched six-query citation validation: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_citation_validation.json`.
- Patched six-query answer quality: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_numeric_safe_patch_8500_answer_quality.json`.
- Summary JSON: `reports/logs/qwen9b_longctx_128k_contract_v3_numeric_safe_patch_summary.json`.
- Cloud log: `reports/logs/qwen9b_longctx_128k_raw_citation_all_complex2_contract_v3_numeric_safe_8500.log`.

## Results
- Two-query rerun parse: 2/2 parsed.
- Two-query citation gate: 2/2 pass, hard failures 0, deterministic repair count 0.
- Runtime:
  - `ai_capex_monetization`: 205.3821 sec.
  - `platform_services_recurring_quality`: 190.8831 sec.
- Metric-role result:
  - `metric_role_mismatch_period_change_in_narrative` dropped from 3 in the original v3 six-query report to 0 in the patched six-query report.
  - `ai_capex_monetization` numeric discipline improved from 0.0 to 0.6.
  - `platform_services_recurring_quality` numeric discipline improved from 0.0 to 0.6667 under the latest validator.
- Patched six-query quality:
  - Parse: 6/6.
  - Citation pass: 6/6.
  - Mean overall: 0.6311, up from 0.5236 in original v3.
  - Warning types: `number_not_verbatim_in_cited_text=21`, `numeric_claim_raw_value_not_in_cited_text=7`, `numeric_conversion_without_role_check=2`.
  - Teacher-ready: 0/6.

## Manual Review
- The targeted failure is fixed: `platform_services_recurring_quality` no longer uses Apple FY2023 `$7.1 billion` service revenue increase as a total-value baseline. It now states that figure as a period-change caveat and uses FY2024/FY2025 total service revenue separately.
- The answer structure remains useful: thesis first, then ranked drivers, then caveats. This preserves the main v3 gain over v2.
- Remaining issue: exact-value rendering is still fragile. Some table raw values are not copied verbatim, some Chinese conversions still trigger conservative warnings, and one `ai_capex_monetization` raw value does not match the cited text exactly.
- Decision: prompt-only control improves the specific period-change narrative problem, but it is not enough for teacher-ready exact numeric output.

## Experiment Governance
- Hypothesis: stronger prompt constraints around exact-value placement and nearby metric-role wording will eliminate the observed period-change-as-total narrative failure without weakening decision-priority structure.
- Decision target: targeted rerun removes `metric_role_mismatch_period_change_in_narrative` for the two failing queries, citation gate remains pass, and decision-priority discipline remains 1.0.
- Result: target passed for metric-role narrative and citation validity; exact numeric discipline remains below teacher-ready threshold.
- Decision label: diagnostic-only.
- Mainline decision: keep the v3 two-layer contract and numeric prompt constraints. The next improvement should not be more prompt wording alone; use deterministic metric snippets or a post-generation numeric rewrite/check stage for exact values.

## Caveats And Next Step
- The patched six-query output is a diagnostic merge, not a fresh six-query inference run under identical prompt conditions.
- `number_not_verbatim_in_cited_text` is partly conservative for Chinese unit conversion, but `numeric_claim_raw_value_not_in_cited_text` is a real blocker for exact-value reliability.
- Next step: implement a structured exact-value layer where the model selects from preformatted metric snippets rather than copying table numbers/free-form raw values.
