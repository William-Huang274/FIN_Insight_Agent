# Model Run: 20260517_phase2_aspectfit_memory_celljson_synthesis_rerun

## Summary
- Purpose: 验证 aspect-aware facet memory、cell JSON 输出契约、deterministic citation repair、scale-aware numeric validator 能否把 expanded v0.2 13-query synthesis 推到可审查状态。
- Status: diagnostic-only。
- Run type: inference + evaluation。
- Timestamp: 2026-05-17。
- Environment: cloud RTX 4090, vLLM text-only Qwen3.5-9B; local Windows for final scale-aware validator rerun.

## Code And Command
- Entry points: `scripts/run_calibrated_synthesis_demo.py`, `scripts/repair_synthesis_citations.py`, `scripts/validate_synthesis_citations.py`, `scripts/validate_metric_table_cells.py`, `scripts/score_synthesis_quality.py`.
- Main inputs: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit.json`, `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Main synthesis: `--max-model-len 16384 --synthesis-max-tokens 4500 --context-safety-margin 1200`.
- Targeted retry: two truncated table queries with `--synthesis-max-tokens 6500 --context-safety-margin 800`.
- Git commit / dirty files: dirty worktree; this run depends on uncommitted Phase 2 scripts and reports.
- Seeds: vLLM default seed 0.

## Inputs
- Query set: 13 expanded v0.2 queries, 6 `complex_insight`, 7 `metric_table_stability`.
- Facets/aspects: 84 facets, 698 aspects.
- Candidate boundary: structured `MetricObject`, `TableObject`, `ClaimObject` evidence selected into facet-level memory.
- Leakage guard: reference answer/baseline labels are not included in the final synthesis prompt.
- Evidence contract: citation evidence can support facts; background evidence can only provide context.

## Model Parameters
- Model: Qwen3.5-9B via vLLM.
- Mode: text-only, no CPU offload.
- Dtype: float16.
- Max model length: 16,384.
- GPU memory utilization: 0.86.
- Max num seqs: 1.
- Structured output: guided JSON schema enabled.

## Outputs
- Full 4500-token synthesis: `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500.json`.
- Retry 2-query synthesis: `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_retry_2q_16k_celljson_6500.json`.
- Merged repaired synthesis: `reports/demo/qwen9b_expanded_v0_2_cell_vllm_facet_memory_aspectfit_synthesis_16k_celljson_4500_retry6500_merged_repaired.json`.
- Citation validation: `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_citation_validation_16k_celljson_4500_retry6500_merged_repaired.json`.
- Scale-aware cell validation: `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_metric_cell_validation_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json`.
- Scale-aware answer quality: `reports/quality/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit_answer_quality_16k_celljson_4500_retry6500_merged_repaired_scaleaware.json`.
- Final concise summary: `reports/logs/qwen9b_aspectfit_4500_retry6500_merged_scaleaware_summary.json`.

## Results
- Parse status: 13/13 parsed after targeted retry.
- Model quality flags: `good=3`, `mixed=6`, `weak=4`.
- Citation gate: 13/13 pass, hard failures 0, repair required 0 after deterministic repair.
- Citation precision against input: 1.0000.
- Background cited as fact: 0.
- Cell validation: reported cells 70, valid reported 66, exact rate 0.9571, unit rate 0.9714, invalid cells 5.
- Answer quality: mean overall 0.7107, min 0.5548, max 0.8422, teacher_ready 0/13.
- Main blockers: `citation_or_number_warning=12`, `low_required_coverage=9`, `low_citation_use_rate=7`, `numeric_validation_failed=2`, `unit_scale_validation_failed=2`, `cell_json_validation_failed=1`.

## Runtime Efficiency
- Main 13-query wall time: 1,275.5655 seconds.
- Model load: 68.2165 seconds.
- Targeted retry generation: `expanded_metric_cloud_segment_table_2023_2025` 208.5637 seconds; `expanded_metric_revenue_income_cfo_table_2023_2025` 112.7173 seconds.
- Observed output speed: about 21-27 output tokens/sec in vLLM logs.
- GPU path: text-only vLLM, no CPU fallback observed.
- Bottleneck: long structured table output length and single-request sequential generation, not CPU offload.

## Experiment Governance
- Hypothesis: aspect-aware memory plus cell JSON contract should reduce strong-evidence omission and make table outputs auditable.
- Decision target: 13/13 parse, citation hard failure 0, background-as-fact 0, cell exact/unit rates above 0.95 on reported cells, and no teacher-ready promotion unless numeric blockers are removed.
- Ceiling / upper bound: current input still has 150 missing aspects and quality coverage warnings, so this run cannot justify teacher/judge status.
- Baselines: prior facet memory cell JSON run had 2 invalid JSON outputs before retry and 7 invalid cells before scale-aware validator fix.
- Decision label: diagnostic-only.
- Mainline decision: aspectfit memory and citation repair are accepted as engineering direction; final answer outputs remain review-only.

## Error Analysis
- `GOOGL 2023 Google Cloud Revenue`: status is unsupported but a value was filled, so the output contract was violated.
- `SNOW Other -708` and `SNOW Federal -6294`: values appear to use thousands while labeled as millions, so these are model/table interpretation errors.
- `ADBE Jillian Forusz 50`: a signature/disclosure row was treated as a business metric.
- `SNOW 2025 RPO 6900`: the answer cited an RPO definition claim rather than a numeric `$6.9B` claim.
- Validator fix: `usd_thousands` now canonicalizes to `usd_millions` by dividing by 1000; a restricted `/1000` compatibility path covers large SEC table `usd_unscaled` values when the output cell is explicitly `usd_millions`.

## Safety Notes
- No model training was performed.
- No credentials were written to repository files.
- The quality report remains `strict_diagnostic_not_teacher`; it should not be used as a teacher or judge source.
- Next step should improve evidence selection and table row filtering before expanding sample size.
