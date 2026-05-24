# Model Run: 20260517_phase2_longctx_128k_complex6_baselines

## Summary
- Purpose: 在引入 `EvidenceBriefObject` 前，验证 Qwen3.5-9B 原生 128k 上下文是否能直接读取更多 evidence，并比较 `full facet memory` 与 `raw citation-only calibrated pool` 两个 complex-insight baseline。
- Status: diagnostic-only。
- Run type: inference + evaluation。
- Timestamp: 2026-05-17。
- Environment: cloud RTX 4090, vLLM text-only Qwen3.5-9B FP16; local Windows for artifact sync and worklog updates.

## Code And Command
- Entry point: `scripts/run_calibrated_synthesis_demo.py`。
- Code change: added non-default long-context packing switches:
  - `--memory-pack-profile full`
  - `--raw-pack-profile citation-only-all|full-all`
- Commands:
  - `128k full facet memory`: `--facet-memory-path reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit.json --max-model-len 131072 --synthesis-max-tokens 2500 --context-safety-margin 1200 --memory-pack-profile full`
  - `128k raw citation-only`: `--grouped-pool-path reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json --max-model-len 131072 --synthesis-max-tokens 2500 --context-safety-margin 1200 --raw-pack-profile citation-only-all --citation-chars 4000 --background-chars 0 --max-background-per-aspect 0`
- Query filter: six `complex_insight` queries from `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`.
- Git commit / dirty files: dirty worktree; run depends on uncommitted Phase 2 scripts/reports.
- Seeds: vLLM default seed 0.

## Inputs
- Facet memory: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_facet_memory_aspectfit.json`.
- Raw calibrated grouped pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json`.
- Query set: 6 complex insight queries, 466 aspects, 109 missing aspects.
- Leakage guard: no `rough_baseline_points` or answer-quality report text was included in synthesis prompts.
- Evidence contract: citation evidence can support final facts; background evidence is not allowed as final factual citation.

## Model Parameters
- Model: Qwen3.5-9B via vLLM.
- Mode: text-only, no CPU offload.
- Dtype: float16.
- Max model length: 131,072.
- Synthesis max tokens: 2,500.
- Context safety margin: 1,200.
- GPU memory utilization: 0.95.
- Max num seqs: 1.
- Structured output: guided JSON schema enabled.

## Outputs
- Facet-memory synthesis: `reports/demo/qwen9b_longctx_128k_facet_full_complex6.json`.
- Raw citation-only synthesis: `reports/demo/qwen9b_longctx_128k_raw_citation_all_complex6.json`.
- Facet-memory citation validation: `reports/quality/qwen9b_longctx_128k_facet_full_complex6_citation_validation.json`.
- Raw citation-only citation validation: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_citation_validation.json`.
- Facet-memory answer quality: `reports/quality/qwen9b_longctx_128k_facet_full_complex6_answer_quality.json`.
- Raw citation-only answer quality: `reports/quality/qwen9b_longctx_128k_raw_citation_all_complex6_answer_quality.json`.
- Combined summary: `reports/logs/qwen9b_longctx_128k_complex6_summary.json`.

## Results
- 128k FP16 serving smoke:
  - Model initialized on single RTX 4090.
  - Model loading memory: 16.8 GiB.
  - GPU KV cache size: 139,914 tokens.
  - Maximum concurrency for 131,072 tokens/request: 1.07x.
- `128k full facet memory`:
  - Parse: 6/6 parsed.
  - Model quality flags: `good=5`, `mixed=1`.
  - Citation gate: 6/6 pass, hard failures 0.
  - Background cited as fact: 0.
  - Invalid cited object IDs: 0.
  - Input citation evidence: 400.
  - Input background evidence: 148.
  - Model cited citation objects: 70.
  - Citation object use rate: 0.1750.
  - Answer quality mean: 0.7107.
  - Teacher-ready: 0/6.
- `128k raw citation-only calibrated pool`:
  - Parse: 6/6 parsed.
  - Model quality flags: `good=6`.
  - Citation gate: 6/6 pass, hard failures 0.
  - Background cited as fact: 0.
  - Invalid cited object IDs: 0.
  - Input citation evidence: 925.
  - Input background evidence: 0.
  - Model cited citation objects: 65.
  - Citation object use rate: 0.0703.
  - Answer quality mean: 0.8017.
  - Teacher-ready: 0/6.
- 16k complex-insight comparison from latest aspectfit baseline:
  - Answer quality mean on the same 6 query IDs: 0.6181.
  - Citation gate previously passed, but prompt inputs were much smaller: 15-33 citation objects per query.

## Prompt And Runtime
- `128k full facet memory` prompt tokens by query: 18,530 to 54,248; wall time 390.1433 seconds; model load 74.4718 seconds.
- `128k raw citation-only` prompt tokens by query: 23,072 to 59,433; wall time 405.3254 seconds; model load 77.9031 seconds.
- Per-query generation elapsed time was roughly 45-81 seconds.
- Observed 128k configuration is feasible in FP16 on this single RTX 4090 for the tested 6-query complex-insight workload.

## Experiment Governance
- Hypothesis: native 128k context should reduce artificial 16k context pressure and improve diagnostic answer quality before adding a brief/summarization stage.
- Decision target: parse 6/6, citation gate 6/6 pass, no background-as-fact, improved diagnostic quality versus 16k complex baseline, and acceptable runtime on single RTX 4090.
- Ceiling / upper bound: 128k can hold full facet memory and raw citation-only calibrated evidence for these 6 complex queries; raw citation+background remains too large for 128k in several cases.
- Baseline: latest 16k aspectfit synthesis had mean quality 0.6181 on the same 6 query IDs.
- Decision label: diagnostic-only.
- Mainline decision: prioritize long-context 128k baselines over `EvidenceBriefObject`; do not implement small-model brief as the next mainline unless long-context outputs hit real context/attention limits.

## Caveats And Next Step
- The answer-quality scorer remains a strict diagnostic alarm, not a teacher or judge.
- Raw citation-only has a lower citation-use rate because its denominator is much larger; this is not automatically worse, but it indicates final answer still cites a small subset of available facts.
- `low_required_coverage` still appears on all 6 queries, partly due lexical scorer limitations and partly because outputs remain concise.
- No 9B quantized model was present on the cloud machine; only Qwen3.5-27B GPTQ Int4 and Qwen3.5-9B FP16 were found. Since 128k FP16 worked, quantized 9B was not downloaded or run.
- Next diagnostic should manually review raw citation-only versus facet-memory answers on 2-3 hard queries, then test whether selected background evidence improves caveat/counter-evidence without increasing hallucination or background-as-fact failures.
