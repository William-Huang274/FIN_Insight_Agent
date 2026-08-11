# Model Run: 20260517_phase2_longctx_contract_v2_complex6

## Summary
- Purpose: 在 128k raw citation-only baseline 基础上，测试更适合 complex insight 的最终 synthesis 输出 contract：增加 facet-level findings、comparability caveats、missing evidence by facet，并提高 key finding / citation 容量。
- Status: diagnostic-only。
- Run type: inference + deterministic repair + evaluation。
- Timestamp: 2026-05-17。
- Environment: cloud RTX 4090 for Qwen3.5-9B FP16/vLLM inference; local Windows for deterministic citation repair, validation, scoring, and ledger updates.

## Code And Command
- Entry point: `scripts/run_calibrated_synthesis_demo.py`。
- Related validators: `scripts/validate_synthesis_citations.py`, `scripts/score_synthesis_quality.py`, `scripts/repair_synthesis_citations.py`。
- Code changes:
  - Added `facet_findings`, `comparability_caveats_zh`, and `missing_evidence_by_facet` to the non-table analyst synthesis schema.
  - Updated the prompt so complex insight output can use up to 8 key findings, 10 facet findings, and 6 citations per finding.
  - Updated citation extraction, missing-signal counting, citation validation, numeric-warning scan, answer-text aggregation, and deterministic repair to include `facet_findings`.
- Final inference command profile:
  - `--grouped-pool-path reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`
  - `--model-path data/models_private/modelscope/Qwen/Qwen3___5-9B`
  - `--max-model-len 131072 --synthesis-max-tokens 6500 --context-safety-margin 1200`
  - `--raw-pack-profile citation-only-all --citation-chars 4000 --background-chars 0 --max-background-per-aspect 0`
  - Six `complex_insight` query IDs from `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Failed/diagnostic attempt: the same contract with `--synthesis-max-tokens 2500` parsed only 2/6 because outputs were truncated mid-JSON; it was not promoted.
- Git commit / dirty files: dirty worktree; Phase 2 scripts/reports are uncommitted.
- Seeds: vLLM default seed 0.

## Inputs
- Raw calibrated grouped pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Query set: 6 complex insight queries, 466 aspects, 109 missing aspects.
- Candidate boundary: citation-only calibrated evidence; background evidence count was 0 for this run.
- Leakage guard: no answer-quality report, manual review notes, or expected answer text was included in prompts.

## Model Parameters
- Model: Qwen3.5-9B via vLLM.
- Mode: text-only, no CPU offload.
- Dtype: float16.
- Max model length: 131,072.
- Synthesis max tokens: 6,500 for the accepted run.
- GPU memory utilization: 0.95.
- Max num seqs: 1.
- Structured output: guided JSON schema enabled.

## Outputs
- Truncated 2,500-token diagnostic output: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v2.json`.
- Accepted raw output before repair: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v2_6500.json`.
- Accepted output after deterministic citation repair: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v2_6500_repaired.json`.
- Repair report: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v2_6500_repair_report.json`.
- Citation validation: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v2_6500_repaired_citation_validation.json`.
- Answer quality: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_contract_v2_6500_repaired_answer_quality.json`.
- Summary JSON: `reports/logs/qwen9b_longctx_128k_contract_v2_complex6_summary.json`.

## Results
- Parse: 6/6 parsed after increasing generation budget to 6,500.
- Model quality flags: `good=4`, `mixed=2`.
- Citation gate after deterministic repair: 6/6 pass, hard failures 0, background-as-fact 0, invalid object IDs 0.
- Deterministic citation repair: 1 object ID copy error repaired from `ITEM8` to the unique matching input citation ID with the same stable suffix in `ITEM7`.
- Numeric warnings: 19 `number_not_verbatim_in_cited_text` diagnostic warnings, mostly because the validator now scans longer facet findings and remains conservative about Chinese unit conversion.
- Input citation evidence: 925.
- Model cited citation objects: 116.
- Citation object use rate: 0.1243, up from 0.0703 in the earlier 128k raw contract.
- Output structure:
  - Key finding counts by query: 8, 5, 4, 4, 8, 4.
  - Facet finding counts by query: 5, 5, 5, 5, 10, 4.
  - Comparability caveat counts by query: 3, 3, 3, 3, 4, 4.
- Answer quality diagnostic mean: 0.7228 after warnings, versus 0.8017 for the earlier short-contract 128k raw baseline. This is not an apples-to-apples decline because the scorer now sees more text and more numeric claims.
- Teacher-ready: 0/6.

## Prompt And Runtime
- Prompt token range: 23,181 to 59,542.
- Per-query elapsed time:
  - `ads_ai_infra`: 154.2110 sec.
  - `ai_capex_monetization`: 111.3391 sec.
  - `ai_semiconductor_durability`: 112.0204 sec.
  - `cloud_profitability_comparison`: 91.3227 sec.
  - `platform_services_recurring_quality`: 176.0374 sec.
  - `subscription_visibility`: 99.3010 sec.
- Model load time: 71.3988 sec.
- Total script time: 815.8856 sec.
- Model loading memory: 16.8 GiB.
- GPU KV cache size: 139,914 tokens.
- Maximum concurrency for 131,072 tokens/request: 1.07x.

## Manual Review
- Coverage improved versus the earlier short-contract 128k raw baseline: answers now explicitly separate facet-level findings, comparability caveats, and missing-by-facet evidence.
- Clear improvements:
  - `ads_ai_infra`: better separation of ad growth, AI capex/depreciation pressure, operating leverage, and Alphabet/Meta comparability.
  - `ai_semiconductor_durability`: better customer concentration, product transition, supply-chain, and segment-definition caveats.
  - `cloud_profitability_comparison`: better AWS/Google Cloud/Microsoft Cloud facet separation and missing AWS 2025 operating-profit acknowledgement.
  - `platform_services_recurring_quality`: much broader coverage of Apple, Microsoft, and Adobe recurring-quality facets.
  - `subscription_visibility`: better RPO/ARR/consumption-model caveats across Adobe, Snowflake, and PANW.
- Risks:
  - Longer output increases numeric/unit phrasing risk, especially in `platform_services_recurring_quality`.
  - `ai_capex_monetization` remains broad and may over-summarize capex trajectories instead of cleanly separating company-level capex, cloud monetization, margin pressure, and cash-flow pressure.
  - The lexical `low_required_coverage` alarm still fires on 5/6, partly because ideal facet names do not always appear verbatim even when the content is covered.

## Experiment Governance
- Hypothesis: a richer final synthesis contract should improve coverage discipline under 128k without introducing a separate small-model brief variable.
- Decision target: 6/6 parse, 6/6 citation pass, no background-as-fact, higher cited-object use, and manual evidence that facet/caveat coverage improves.
- Baseline: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6.json`.
- Stop conditions: if richer output caused persistent invalid JSON or citation failures after reasonable output budget increase and deterministic copy-error repair, revert to the shorter contract or split output into staged sections.
- Decision label: diagnostic-only.
- Mainline decision: keep long-context raw citation-only as the current complex-insight baseline; do not return to `EvidenceBriefObject` as the next default step. The next useful fix is a numeric/metric phrasing constraint for long analytical outputs.

## Caveats And Next Step
- The 2,500-token run is intentionally retained as a truncation diagnostic only.
- Automatic answer-quality scores are not directly comparable before and after contract v2 because scorer coverage and numeric-warning scope changed.
- Next step: add a stricter numeric phrasing rule for complex insight outputs, for example requiring raw value/unit language to mirror cited object units or to move exact values into structured metric snippets before claiming a trend.
