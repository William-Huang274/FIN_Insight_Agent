# 20260515_phase1_qwen35_9b_full_chain_demo

## Summary

- Purpose: Test a resident Qwen3.5-9B planner-to-synthesis demo on the cloud RTX 4090 for daily, comprehensive research, and deep reasoning SEC 10-K questions.
- Status: completed, diagnostic-only
- Run type: inference demo
- Timestamp: 2026-05-15 23:18-23:35 Asia/Shanghai
- Environment: cloud RTX 4090 24GB, Python 3.12, vLLM 0.21.0
- Owner/agent: Codex

## Code And Command

- Entry point: `scripts/run_qwen_planner_evidence_demo.py`
- Query set: `eval_sets/sec_tech_10k_demo_queries.jsonl`
- Primary command profile:
  - model: `data/models_private/modelscope/Qwen/Qwen3.5-9B`
  - retrieval: hybrid BM25 + dense, dense query encoder on CPU
  - `candidate_k=6`, `verify_k=2`, `selected_per_task=2`
  - `max_model_len=8192`, `cpu_offload_gb=0`, `gpu_memory_utilization=0.86`
  - `language_model_only=True`, `skip_mm_profiling=True`
  - `planner_max_tokens=1024`, `verifier_max_tokens=160`, `synthesis_max_tokens=900`
  - `allow_fallback_planner=False`
- Git status: dirty local branch `feature/phase1-sec-foundation`; demo script and this ledger are uncommitted.
- Seeds: vLLM default seed `0`.

## Inputs

- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_10k`
- Dense index: `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16`
- Model artifact: `/root/autodl-tmp/FIN_Insight_Agent/data/models_private/modelscope/Qwen/Qwen3.5-9B`
- Query modes:
  - daily task: Apple Services net sales and gross margin.
  - comprehensive research: Microsoft vs Alphabet cloud growth and AI infrastructure capex pressure.
  - deep reasoning: NVIDIA Data Center durability, customer concentration, CSP demand, and manufacturing risk.

## Outputs

- Successful run output: `reports/demo/qwen9b_planner_evidence_pack_demo_v2.json`
- Successful run log: `reports/demo/qwen9b_planner_evidence_pack_demo_v2.log`
- Structured/adaptive run output: `reports/demo/qwen9b_planner_evidence_pack_demo_v3_adaptive_structured.json`
- Structured/adaptive run log: `reports/demo/qwen9b_planner_evidence_pack_demo_v3_adaptive_structured.log`
- Variant-fusion run output: `reports/demo/qwen9b_planner_evidence_pack_demo_v4_variants.json`
- Variant-fusion run log: `reports/demo/qwen9b_planner_evidence_pack_demo_v4_variants.log`
- Original-query-priority variant run output: `reports/demo/qwen9b_planner_evidence_pack_demo_v5_variants_original2.json`
- Original-query-priority variant run log: `reports/demo/qwen9b_planner_evidence_pack_demo_v5_variants_original2.log`
- Table-rescue diagnostic run output: `reports/demo/qwen9b_planner_evidence_pack_demo_v6_table_rescue.json`
- Table-rescue diagnostic run log: `reports/demo/qwen9b_planner_evidence_pack_demo_v6_table_rescue.log`
- First parse-failure diagnostic output: `reports/demo/qwen9b_planner_evidence_pack_demo.json`
- First parse-failure diagnostic log: `reports/demo/qwen9b_planner_evidence_pack_demo.log`
- First utilization failure log: `reports/demo/qwen9b_planner_evidence_pack_demo_fail_util092.log`
- Prior serving benchmark log on cloud: `/root/autodl-tmp/FIN_Insight_Agent/reports/demo/qwen9b_textonly_bench.log`

## Results

- Serving gate:
  - `Qwen/Qwen3.5-9B` can run in vLLM text-only mode on RTX 4090 without CPU offload.
  - Logs show `language_model_only=True`, `skip_mm_profiling=True`, `device_config=cuda`, and "running in text-only mode."
  - Checkpoint size: about 17.98 GiB.
  - With another unrelated process using about 1.75 GiB GPU memory, `gpu_memory_utilization=0.92` failed on startup because requested memory exceeded free memory by about 0.23 GiB.
  - `gpu_memory_utilization=0.86` succeeded with GPU KV cache size about 59,068 tokens.
- Runtime:
  - Successful v2 `load_resident_model_sec`: 90.114s.
  - Successful v2 total wall time: 286.916s for three queries.
  - Query elapsed times: 58.487s, 61.941s, 62.584s.
  - Planner generation speed in logs: about 24-27 output tok/s after warmup.
  - Batched verifier generation speed in logs: commonly about 39-51 output tok/s for 2-candidate batches.
- Planner:
  - First run with `planner_max_tokens=512` failed JSON parsing on all 3 queries because output was truncated before closing JSON.
  - v2 with compact JSON instruction and `planner_max_tokens=1024` produced parseable planner tasks for all 3 queries.
  - Total planned tasks: 12.
- Evidence quality:
  - Total task packs: 12.
  - Tasks with at least one direct verified candidate: 7.
  - Tasks missing direct evidence among top-2 verified candidates: 5.
  - Verifier labels across 24 checked candidates: 8 direct, 14 partial, 2 false.
  - Selected evidence groups: 22.
- Synthesis quality:
  - Apple daily query: `good`; retrieved direct table evidence for Services sales and margin.
  - Microsoft vs Alphabet comprehensive query: `mixed`; Microsoft evidence was strong, Alphabet cloud/capex tasks were mostly partial.
  - NVIDIA deep query: `mixed`; Data Center growth, concentration, and manufacturing risk evidence were useful; CSP demand remained partial.

## Hardening Runs V3-V6

Purpose:
- Test structured JSON decoding, adaptive verification, task query variants, original-query-priority variant fusion, and a bounded table-rescue diagnostic.

Profiles:
- v3: `structured_json=true`, `adaptive_verify_k=6`, `adaptive_min_direct=1`, no task query variants.
- v4: v3 plus task query variants and naive round-robin variant fusion.
- v5: v4 plus `variant_original_quota=2`, preserving the original query top candidates before round-robin fill.
- v6: v5 plus added revenue/capex query variants and `table_rescue_k=3` diagnostic.

Results:
| Run | Direct task packs | Missing direct | Verified candidates | Label counts | Total wall time |
| --- | ---: | ---: | ---: | --- | ---: |
| v2 baseline | 7/12 | 5 | 24 | 8 direct / 14 partial / 2 false | 286.9s |
| v3 structured + adaptive | 7/12 | 5 | 44 | 8 direct / 24 partial / 12 false | 358.6s |
| v4 variants | 8/12 | 4 | 52 | 12 direct / 22 partial / 18 false | 419.0s |
| v5 original-quota variants | 8/12 | 4 | 44 | 9 direct / 23 partial / 12 false | 414.2s |
| v6 table-rescue diagnostic | 9/12 | 3 | 50 | 10 direct / 25 partial / 15 false | 402.4s |

Interpretation:
- Structured JSON stabilized planner/verifier/synthesis parsing, but by itself did not improve direct evidence coverage.
- Adaptive verification found additional Apple evidence, but also exposed more false/partial candidates; it should remain bounded and task-triggered.
- Naive query variant round-robin improved coverage but increased noise and verifier cost.
- v5 is the better default fusion policy than v4: it keeps the v4 8/12 direct coverage while reducing verified candidates from 52 to 44 and false labels from 18 to 12.
- v6 improved to 9/12 by moving `GOOGL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001` into adaptive verification for the Alphabet cloud revenue task. This gain came from the added "disaggregated revenues" query variant, not from table rescue.
- Table rescue triggered on three tasks and verified six extra candidates, but did not add a direct hit in this query set. It should remain optional (`--table-rescue-k 0` default) until tested on a broader reviewed set.

Remaining weak facets:
- `msft_ai_capex_2025`: current evidence is useful but mostly partial because it mixes AI infrastructure narrative, PP&E, and broader capital use rather than a single direct AI capex disclosure.
- `googl_ai_capex_2025`: current evidence gives AI/technical infrastructure investment pressure, but quantitative capex evidence and AI attribution remain split.
- `cloud_provider_demand`: NVIDIA Data Center demand and CSP context are present, but direct CSP-demand durability evidence remains partial under current task wording.

Mainline decision:
- Keep structured JSON, adaptive verification, task query variants, and original-query-priority fusion as the current demo default.
- Keep table rescue available as an explicit diagnostic knob, but do not enable it by default for the precision-sensitive evidence pack path.

## Interpretation

The 9B model is viable as a resident single-card planner/verifier/summarizer for a diagnostic demo. It is much more practical than the 27B GPTQ artifact under 24GB because it avoids CPU offload and can keep an 8K context.

The main bottleneck is no longer model serving feasibility. The weak point is retrieval/evidence coverage after decomposition. The current top-2 verifier pass often sees only partial evidence for multi-facet tasks, especially Alphabet cloud/capex and NVIDIA CSP demand. This supports the earlier product direction: use planner-generated search tasks, retrieve per task, verify per task, then synthesize from an evidence pack, but improve task-specific retrieval depth, route filters, and direct-evidence recovery before judging answer quality.

## Experiment Governance

- Hypothesis: A resident Qwen3.5-9B text-only vLLM profile can run the whole planner-to-summary chain on a single RTX 4090 without CPU offload, and can expose whether evidence-pack quality is the actual bottleneck.
- Decision target: successful no-offload model initialization, parseable planner tasks for all three query modes, and evidence-backed synthesis with explicit missing evidence.
- Ceiling / upper bound: current evidence store and top-2 verifier candidates limit direct evidence recovery; this run is not a final retrieval-quality metric.
- Baselines to beat: Qwen3.5-27B GPTQ diagnostic, which required 10-14GB CPU offload and generated at about 0.7-1.0 tok/s.
- Split and leakage guard: no training or benchmark claim; diagnostic fixed query set only.
- Stop conditions: if 9B required CPU offload or planner JSON remained unstable after output budget increase, stop this path.
- Efficiency gate: no CPU offload, single RTX 4090, interactive-scale per-query runtime after resident load.
- Decision label: diagnostic-only, proceed with pipeline hardening.
- Mainline decision: keep 9B resident demo path for pipeline development; do not treat its answers or verifier labels as final evaluation.

## Runtime Efficiency

- Wall time: 286.916s for v2.
- Stage timing: evidence/index load 0.262s; resident model load 90.114s; per-query chain about 58-63s.
- GPU utilization / memory: v2 used roughly 20-22.6GB during inference; GPU freed after process exit.
- Throughput: planner about 24-27 tok/s; batched verifier often about 39-51 tok/s; synthesis about 23-27 tok/s.
- Bottleneck diagnosis:
  - Cold model load dominates startup.
  - Per-query cost is mostly planner + batched verifier + long synthesis prompts.
  - Retrieval depth is too shallow for some facets when only top-2 candidates are verified.
  - Current script runs as batch demo, not an always-on API; it reloads the resident model per process.
- Efficiency improvement:
  - Move to a persistent service process for repeated queries.
  - Add guided JSON or schema-constrained decoding for planner/verifier.
  - Increase per-task retrieval/verify depth adaptively for missing-direct facets.
  - Consider vLLM non-eager/CUDA graph profile after isolating GPU memory, since the earlier benchmark reached about 45-46 tok/s on short JSON after warmup.
- Serving latency implication:
  - With a true resident process, the model-load cost disappears from request latency.
  - A three-facet query should still be optimized with batched verifier and route-specific retrieval because current end-to-end per-query runtime is about one minute in batch-demo form.

## Caveats And Next Step

- Not run: no human qrels, no formal precision/nDCG evaluation for the generated evidence packs, no guided decoding, no reranker.
- Known risks:
  - Verifier labels are model-authored and diagnostic-only.
  - Some synthesis claims cite partial evidence or state absence based only on top-2 verified candidates.
  - Alphabet and NVIDIA CSP facets show retrieval-depth/candidate-generation gaps.
- Reproduce/rollback:
  - Reproduce with `scripts/run_qwen_planner_evidence_demo.py` and the v2 profile above.
  - If another process uses GPU memory, keep `gpu_memory_utilization=0.86` or lower.
- Next decision:
  - Harden planner/verifier structured output.
  - Add adaptive evidence expansion for tasks with no direct verified candidate.
  - Compare top-2 vs top-5 verification cost and evidence quality before adding a heavier reranker.
