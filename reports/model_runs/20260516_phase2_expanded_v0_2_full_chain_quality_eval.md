# 20260516_phase2_expanded_v0_2_full_chain_quality_eval

## Summary

- Purpose: Run the expanded multi-company/multi-year query set through object retrieval, BGE reranking, Qwen small verifier, calibrated evidence pooling, Qwen3.5-9B Chinese synthesis, citation validation, and answer-quality scoring.
- Status: completed, diagnostic-only.
- Run type: retrieval + verifier inference + synthesis inference + evaluation.
- Timestamp: 2026-05-16 21:15-21:38 Asia/Shanghai.
- Environment: cloud RTX 4090 24GB, `/root/miniconda3/bin/python3.12`, vLLM 0.21.0 for Qwen3.5-9B synthesis; local Windows used for report scoring/export after artifacts were synced.
- Owner/agent: Codex.

## Code And Command

- Main scripts:
  - `scripts/build_expanded_object_tasks.py`
  - `scripts/evaluate_object_reranker.py`
  - `scripts/build_bge_evidence_pool.py`
  - `scripts/build_aspect_evidence_pool.py`
  - `scripts/run_qwen_small_verifier.py`
  - `scripts/export_calibrated_evidence_pool.py`
  - `scripts/run_calibrated_synthesis_demo.py`
  - `scripts/validate_synthesis_citations.py`
  - `scripts/score_synthesis_quality.py`
  - `scripts/export_expanded_synthesis_trace.py`
- Command profile:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
# Resume from BGE reranker after metadata-passthrough fixes.
# BGE top15 -> aspect pool -> Qwen3.5-2B verifier strict fast path
# -> calibrated pool -> Qwen3.5-9B final Chinese synthesis.
```

Local post-run evaluation:

```powershell
python scripts\validate_synthesis_citations.py
python scripts\score_synthesis_quality.py --eval-path eval_sets\sec_tech_10k_expanded_eval_v0_2.jsonl --synthesis-path reports\demo\qwen9b_expanded_v0_2_synthesis_demo.json --citation-validation-path reports\quality\sec_tech_10k_expanded_v0_2_citation_validation.json --output-path reports\quality\sec_tech_10k_expanded_v0_2_answer_quality.json
python scripts\export_expanded_synthesis_trace.py --output-path reports\demo\qwen9b_expanded_v0_2_trace_zh.md
```

- Git status: dirty local branch with Phase 2 scripts, eval sets, reports, and worklogs uncommitted.
- Seeds: vLLM default seed `0`; reranker/verifier deterministic decoding where applicable.

## Inputs

- Expanded query set: `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`
- Object tasks: `eval_sets/sec_tech_10k_expanded_eval_v0_2_object_tasks.jsonl`
- Object BM25 index: `data/processed_private/indexes/sec_tech_10k_object_bm25`
- Structured objects: `data/processed_private/sec/structured_objects/sec_tech_10k_objects.jsonl`
- BGE reranker input: `reports/retrieval_eval/sec_tech_10k_expanded_v0_2_object_bm25_predictions.jsonl`
- Verifier model: `Qwen/Qwen3.5-2B`, strict fast path with causal-conv1d and FLA available, fallback disabled.
- Synthesis model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`, text-only vLLM, bf16, no quantization, no CPU offload.

Leakage guard:

- `rough_baseline_points` and answer rubrics are not included in the synthesis prompt.
- Answer-quality scoring reads the rubric after generation for diagnostics only.
- Current expanded set has no final human gold labels; all quality scores are diagnostic.

## Outputs

- BGE predictions: `reports/retrieval_eval/sec_tech_10k_expanded_v0_2_object_bge_predictions.jsonl`
- Aspect pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_bge_top15_aspect_evidence_pool.jsonl`
- Qwen verifier output: `reports/verifier/sec_tech_10k_expanded_v0_2_qwen35_2b_aspect_verifier.jsonl`
- Calibrated grouped pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_calibrated_evidence_pool_grouped.json`
- Pool metrics: `reports/metrics/sec_tech_10k_expanded_v0_2_calibrated_evidence_pool_report.json`
- Synthesis output: `reports/demo/qwen9b_expanded_v0_2_synthesis_demo.json`
- Citation validation: `reports/quality/sec_tech_10k_expanded_v0_2_citation_validation.json`
- Answer-quality report: `reports/quality/sec_tech_10k_expanded_v0_2_answer_quality.json`
- Human-readable trace: `reports/demo/qwen9b_expanded_v0_2_trace_zh.md`
- Run log: `reports/logs/expanded_v0_2_resume_from_bge.log`

## Results

Query set:

- Total queries: 13
- `complex_insight`: 6
- `metric_table_stability`: 7
- Facets: 84
- Aspects: 168

Evidence pool:

- Citation evidence: 143
- Background evidence in grouped pool: 503 available; 55 packed into prompts
- Missing aspects: 25
- Prompt input object types: 74 claim, 96 metric, 28 table

Synthesis:

- Parsed outputs: 12/13
- Invalid JSON outputs: 1
- Model-rated quality: 1 `good`, 10 `mixed`, 2 `weak`
- Model cited objects: 78
- Cited citation objects: 77
- Cited background-only objects: 1
- Invalid cited object IDs: 0
- Citation object use rate: 0.5385
- Cited-object precision against input pool: 1.0000

Citation validation:

- Pass: 11/13
- Repair required: 2/13
- Hard failures:
  - `invalid_json`: 1
  - `background_cited_as_fact`: 1
- Warnings:
  - `number_not_verbatim_in_cited_text`: 22, conservative because Chinese unit conversion/translation may not be string-identical.

Answer-quality scoring:

- Status: diagnostic-only
- Mean overall: 0.7972
- Min overall: 0.3857
- Max overall: 0.9429
- Lowest query: `expanded_metric_revenue_income_cfo_table_2023_2025`, invalid JSON and repair required.
- Stronger queries: `expanded_metric_capex_fcf_table_2023_2025` and `expanded_metric_subscription_visibility_table_2023_2025`, both 0.9429 diagnostic score.

Per-query synthesis:

| Query | Mode | Quality | Elapsed sec | Prompt tokens | Citation evidence | Missing aspects | Cited objects |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `expanded_insight_ads_ai_infra_2023_2025` | industry_research | mixed | 54.55 | 5266 | 17 | 3 | 6 |
| `expanded_insight_ai_capex_monetization_2023_2025` | industry_research | mixed | 44.94 | 4801 | 15 | 6 | 6 |
| `expanded_insight_ai_semiconductor_durability_2023_2025` | industry_research | mixed | 55.35 | 5265 | 21 | 1 | 11 |
| `expanded_insight_cloud_profitability_comparison_2023_2025` | industry_research | mixed | 44.56 | 4208 | 14 | 1 | 7 |
| `expanded_insight_platform_services_recurring_quality_2023_2025` | industry_research | good | 51.16 | 4476 | 15 | 0 | 9 |
| `expanded_insight_subscription_visibility_2023_2025` | industry_research | mixed | 41.67 | 4785 | 16 | 4 | 7 |
| `expanded_metric_aapl_services_msft_adbe_margin_table_2023_2025` | metric_table | mixed | 49.58 | 2906 | 5 | 0 | 5 |
| `expanded_metric_capex_fcf_table_2023_2025` | metric_table | mixed | 47.76 | 4839 | 6 | 3 | 6 |
| `expanded_metric_cloud_segment_table_2023_2025` | metric_table | weak | 49.04 | 4277 | 7 | 0 | 6 |
| `expanded_metric_customer_concentration_visibility_table_2023_2025` | metric_table | weak | 17.45 | 1965 | 0 | 5 | 0 |
| `expanded_metric_revenue_income_cfo_table_2023_2025` | metric_table | mixed | 59.03 | 5398 | 11 | 1 | 0 |
| `expanded_metric_semiconductor_segment_table_2023_2025` | metric_table | mixed | 35.87 | 3705 | 6 | 1 | 6 |
| `expanded_metric_subscription_visibility_table_2023_2025` | metric_table | mixed | 55.35 | 5217 | 10 | 0 | 9 |

Runtime:

- BGE reranker wall time: 30.3871s
- Qwen3.5-2B verifier load: 36.2292s
- Qwen3.5-2B verifier generation: 395.4206s
- Qwen3.5-2B verifier total: 431.6498s for 2,520 aspect rows, batch size 8
- Qwen3.5-9B synthesis model load: 55.2894s
- Qwen3.5-9B synthesis total: 661.7082s for 13 queries
- End-to-end resumed cloud run: about 1,138s from BGE rerank through synthesis
- Synthesis decode speed: about 22.6-23.9 output tokens/s in vLLM logs

## Interpretation

- The expanded full chain is useful as a diagnostic research assistant path. It can split complex finance questions into facets, keep missing evidence visible, and generate mostly coherent Chinese summaries from citation-grade evidence.
- It is not yet stable enough for table-heavy production output. Metric/table tasks need strict machine-readable table schema, a repair pass for invalid JSON, and numeric exactness checks against MetricObject/TableObject fields rather than lexical answer text.
- The current evidence-pool contract is directionally right: 25 missing aspects were exposed to synthesis instead of silently filled, and no invalid object IDs were cited. This is more important than raw citation object use rate.
- The biggest quality gap is not only retrieval recall. Some weak cases are caused by the answer format and table traceability contract: the model writes prose instead of cell-level table JSON, so validator/scorer cannot reliably verify exact values.
- The `customer_concentration_visibility` query correctly abstained because the pool had no citation evidence. This looks weak as an answer but is desirable behavior under the current evidence policy.

## Experiment Governance

- Hypothesis: Expanding from six single-company/simple tasks to 13 multi-company/multi-year tasks will reveal whether the current evidence-pool and Qwen3.5-9B synthesis path remains stable under realistic finance workloads.
- Decision target: at least 11/13 parseable outputs, no invalid cited IDs, missing aspects acknowledged, and citation validation failures isolated enough to guide repair.
- Ceiling / upper bound: no final human gold labels; BGE eval labels are absent for this expanded set; numeric exactness cannot be final until table outputs become machine-readable.
- Baselines to beat: prior six-query calibrated synthesis demo had 6/6 parsed outputs and stronger subjective quality; expanded v0.2 is expected to be harder and is diagnostic.
- Split and leakage guard: fixed v0.2 diagnostic set only; no training; rough baseline excluded from synthesis prompt.
- Stop conditions: do not promote to mainline if invalid JSON remains, if background-only citations are used as hard facts, or if table numeric exactness cannot be checked.
- Efficiency gate: single RTX 4090, no CPU offload for 9B synthesis; verifier and synthesis should remain feasible under a resident-service design.
- Decision label: diagnostic-only.
- Mainline decision: keep expanded v0.2 as an evaluation set, but gate next work on table schema/repair and numeric citation validation rather than adding more queries immediately.

## Runtime Efficiency

- Wall time: about 19 minutes for the resumed cloud run from BGE reranker through synthesis.
- Stage timing: BGE 30.4s; verifier 431.6s; synthesis 661.7s.
- GPU use: single RTX 4090; Qwen3.5-9B ran text-only, bf16, no CPU offload.
- Throughput: verifier handled 2,520 rows in about 431.6s; synthesis took about 50.9s/query including resident model generation after load.
- Bottleneck diagnosis:
  - Final synthesis is the largest wall-time component.
  - The 2B verifier is also material because every aspect-candidate pair is classified.
  - Table answers spend output tokens on prose, increasing JSON truncation risk.
- Efficiency improvement:
  - Keep verifier and synthesis as resident services.
  - Reduce verifier rows with stronger reranker thresholding only after candidate recall is audited.
  - For metric/table tasks, switch to compact cell JSON output and separate prose explanation.

## Caveats And Next Step

- Not run: no human finance-quality review on all 13 outputs, no final numeric exactness audit, no repair generation pass.
- Known risks:
  - The answer-quality scorer is diagnostic and partly lexical.
  - BGE reranker metrics are not meaningful on this set without labels; it is being used as a candidate orderer, not a measured winner.
  - Citation validation warnings for numbers are conservative and may overcount unit-converted Chinese claims.
- Next decision:
  - Implement table/cell JSON output contract.
  - Add post-synthesis repair for invalid JSON and background-only citations.
  - Add numeric validator over structured MetricObject/TableObject values.
