# Model Run: 20260517_phase2_longctx_contract_v3_complex6

## Summary
- Purpose: 在 128k raw citation-only complex-insight baseline 上测试两层答案 contract：先给 `thesis_zh` 和最多 3 条 `decision_drivers`，再用 `secondary_context`、`limiting_caveats`、`facet_findings` 做辅证；同时增加 `numeric_claims` 以约束数值、单位和 metric role。
- Status: diagnostic-only。
- Run type: inference + deterministic repair + citation/quality evaluation。
- Timestamp: 2026-05-17。
- Environment: cloud RTX 4090 for Qwen3.5-9B FP16/vLLM inference; local Windows for repair, validation, scoring, and ledger updates.

## Code And Command
- Entry point: `scripts/run_calibrated_synthesis_demo.py`。
- Validators: `scripts/validate_synthesis_citations.py`, `scripts/score_synthesis_quality.py`, `scripts/repair_synthesis_citations.py`。
- Code changes:
  - Added complex-insight fields `thesis_zh`, `decision_drivers`, `secondary_context`, `limiting_caveats`, and `numeric_claims`.
  - Kept `facet_findings` as supporting appendix, with `importance=primary|supporting|caveat_only`.
  - Added metric hints for structured evidence: `raw_value_text`, `unit`, `metric_role`, `numeric_use_rule`, `allowed_claim_roles`, and `disallowed_claim_roles`.
  - Added numeric warnings for missing raw values, raw values not found in cited text, unit conversion without role check, metric-role mismatch, and period-change values used in total-value narrative trend sentences.
  - Fixed answer-quality blocker logic so `numeric_claim_discipline=0.0` is treated as a real blocking score, not as a missing value.
- Inference profile:
  - `--grouped-pool-path reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`
  - `--model-path data/models_private/modelscope/Qwen/Qwen3___5-9B`
  - `--max-model-len 131072 --synthesis-max-tokens 8500 --context-safety-margin 1200`
  - `--raw-pack-profile citation-only-all --citation-chars 4000 --background-chars 0 --max-background-per-aspect 0`
  - Six `complex_insight` query IDs from `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Git commit / dirty files: dirty worktree; Phase 2 scripts/reports are uncommitted.
- Seeds: vLLM default seed 0.

## Inputs
- Grouped evidence pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Eval set: `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Query scope: 6 complex-insight queries, 466 aspects, 925 input citation evidence objects, 109 missing aspects.
- Candidate boundary: citation-only calibrated evidence; background evidence count was 0.
- Leakage guard: no answer-quality report or expected answer text was included in prompts.

## Outputs
- First interrupted 3-query output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500.json`.
- Detached remaining-3 output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_remaining3.json`.
- Merged output before repair: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_merged.json`.
- Merged output after deterministic repair: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_merged_repaired.json`.
- Repair report: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_repair_report.json`.
- Citation validation: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_repaired_citation_validation.json`.
- Answer quality: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v3_8500_repaired_answer_quality.json`.
- Summary JSON: `reports/logs/qwen9b_longctx_128k_contract_v3_complex6_summary.json`.

## Results
- Parse: 6/6 parsed.
- Model quality flags: 6/6 `good`.
- Deterministic citation repair: 3 invalid caveat citations dropped; final rejected count 0.
- Citation gate after repair: 6/6 pass, hard failures 0, invalid object IDs 0, background-as-fact 0.
- Contract structure:
  - `decision_drivers`: 18 total, exactly 3 per query.
  - `secondary_context`: 18 total, exactly 3 per query.
  - `limiting_caveats`: 18 total, exactly 3 per query.
  - `facet_findings`: 19 total.
  - `numeric_claims`: 62 total.
- Citation use: 113 cited citation objects out of 925 input citation evidence objects; use rate 0.1222.
- Quality scoring with current strict gate:
  - Mean overall: 0.5236.
  - Min/max overall: 0.3021 / 0.7443.
  - Decision priority discipline: 1.0 on all six queries.
  - Blocking issues: `citation_or_number_warning=6`, `low_citation_use_rate=6`, `low_required_coverage=6`, `numeric_claim_discipline_warning=5`.
  - Teacher-ready: 0/6.

## Numeric And Metric-Role Findings
- Warning types:
  - `number_not_verbatim_in_cited_text`: 27.
  - `numeric_claim_raw_value_not_in_cited_text`: 7.
  - `numeric_conversion_without_role_check`: 6.
  - `metric_role_mismatch_period_change_in_narrative`: 3.
- Key manual finding: `platform_services_recurring_quality` still misuses Apple FY2023 `$7.1 billion` service revenue increase as part of a total-value trend sentence: the answer says service revenue went from the FY2023 increase of 71 亿美元 to FY2025 total revenue of 1091.58 亿美元. The model separately labels `$7.1 billion` as `period_change_amount` and even writes a caveat, but the driver narrative contradicts that role.
- Additional automatic finding: `ai_capex_monetization` also triggers period-change narrative warnings for Amazon capex cash-flow figures used in trend language.
- Decision: numeric/metric-role gate is working as a diagnostic blocker, but the prompt alone has not eliminated the failure. Do not expand sample size until exact-value rendering is made more deterministic.

## Manual Review
- Insight quality improved over v2 in one specific dimension: the model now states a ranked conclusion before evidence, and the answer no longer treats every facet as equally important.
- The stronger structure is visible in all six queries: `thesis_zh` gives the one-sentence judgment, `decision_drivers` identify the 2-3 facts that drive the conclusion, and caveats are separated from secondary support.
- This does not mean final answer quality is production-ready. The longer output plus explicit numeric claims exposes more unit/role errors; the main open risk is not citation ID validity, but exact metric interpretation.
- `platform_services_recurring_quality` is the clearest failure case: analytically useful conclusion, but unsafe numeric phrasing around Apple service revenue period change versus total service revenue.

## Experiment Governance
- Hypothesis: two-layer contract should improve judgment priority and reduce average facet spreading, while numeric claims should make exact-value errors visible.
- Decision target: 6/6 parse, 6/6 citation pass, `weak_decision_priority=0`, and no material metric-role misuse in narrative text.
- Baseline: `reports/model_runs/20260517_phase2_longctx_contract_v2_complex6.md`.
- Result: parse/citation/decision-priority targets passed; metric-role target failed.
- Decision label: diagnostic-only.
- Mainline decision: keep the two-layer contract idea, but do not promote v3 outputs as teacher-ready. The next change should make exact numeric rendering stricter, likely by forcing structured metric snippets or a post-generation numeric rewrite/check stage before final answer acceptance.

## Runtime Efficiency
- First 3-query run wall time: 631.3535 sec before SSH interruption.
- Detached remaining 3-query run wall time: 636.2381 sec.
- Model: Qwen3.5-9B FP16, vLLM, 131,072 max model length.
- Model load memory from prior 128k run: about 16.8 GiB; KV cache capacity about 139,914 tokens.
- Serving implication: single-query long-context inference is feasible on one RTX 4090, but slow enough that contract iterations should stay on the 6 complex query cohort until gates pass.

## Caveats And Next Step
- Automatic `number_not_verbatim_in_cited_text` remains conservative for Chinese unit conversion, but the period-change narrative warning is a real semantic issue.
- The current answer-quality mean is not directly comparable with v2's old scorer output because v3 adds numeric-claim accounting and stricter blocker logic.
- Next step: rerun only the failing queries after adding stricter exact-value rendering, not the whole 13-query expanded set.
