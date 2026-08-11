# 20260516_phase2_qwen35_9b_calibrated_synthesis_demo

## Summary

- Purpose: Run final Chinese synthesis from the calibrated citation/background/missing-aspect evidence pool.
- Status: completed, diagnostic-only.
- Run type: inference evaluation.
- Timestamp: 2026-05-16 19:11-19:15 Asia/Shanghai.
- Environment: cloud RTX 4090 24GB, `/root/miniconda3/bin/python3.12`, vLLM 0.21.0, Qwen3.5-9B text-only mode.
- Owner/agent: Codex.

## Code And Command

- Entry point: `scripts/run_calibrated_synthesis_demo.py`
- Command profile:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
/root/miniconda3/bin/python3.12 scripts/run_calibrated_synthesis_demo.py \
  --output reports/demo/qwen9b_calibrated_synthesis_demo.json \
  --max-model-len 8192 \
  --synthesis-max-tokens 1200 \
  --context-safety-margin 1600 \
  --citation-chars 900 \
  --background-chars 450 \
  --max-background-per-aspect 1 \
  --gpu-memory-utilization 0.86 \
  --cpu-offload-gb 0 \
  --max-num-seqs 1 \
  --structured-json
```

- Git status: dirty local branch `feature/phase1-sec-foundation`; this run script, reports, and worklogs are uncommitted.
- Seeds: vLLM default seed `0`.

## Inputs

- Grouped calibrated evidence pool:
  `reports/evidence_pool/sec_tech_10k_calibrated_evidence_pool_grouped.json`
- Evidence pool report:
  `reports/metrics/sec_tech_10k_calibrated_evidence_pool_report.json`
- Human-gold audit report:
  `reports/metrics/sec_tech_10k_calibrated_evidence_pool_human_gold_eval.json`
- Query set for metadata only:
  `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl`
- Model:
  `data/models_private/modelscope/Qwen/Qwen3.5-9B`

Leakage guard:
- The final synthesis prompt excludes `reference_answer_points`; model input contains only the calibrated evidence package and answer policy.
- Human-gold labels are not embedded in the formal evidence pool or synthesis prompt. They are used only in the run report as upstream citation-quality context.

## Outputs

- Final report:
  `reports/demo/qwen9b_calibrated_synthesis_demo.json`
- Script:
  `scripts/run_calibrated_synthesis_demo.py`

## Results

Upstream evidence pool:

- Queries: 6
- Facets: 23
- Aspects: 73
- Citation evidence: 70
- Background evidence in exporter: 178
- Missing aspects: 3
- Human-reviewed citation precision from the calibration audit: 0.9286

Synthesis run:

- Parsed outputs: 6/6
- Model-rated quality: 5 `good`, 1 `mixed`
- Prompt-packed inputs: 70 citation evidence objects and 47 background evidence objects
- Input missing aspects visible to model: 3
- Model cited objects: 38
- Cited citation objects: 37
- Cited background-only objects: 1
- Invalid cited object IDs: 0
- Citation object use rate: 0.5286
- Cited object precision against input evidence pool: 1.0000

Per-query results:

| Query | Mode | Quality | Elapsed sec | Prompt tokens | Cited objects | Missing aspects |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `agent_daily_aapl_services_2025` | daily_task | good | 29.2860 | 4964 | 5 | 0 |
| `agent_daily_snow_visibility_2025` | daily_task | mixed | 33.7341 | 4880 | 5 | 2 |
| `agent_deep_adbe_arr_rpo_subscription_quality_2025` | deep_reasoning | good | 30.6096 | 5140 | 5 | 1 |
| `agent_deep_nvda_datacenter_durability_2025` | deep_reasoning | good | 39.6168 | 4852 | 10 | 0 |
| `agent_research_amzn_aws_capex_fcf_2025` | comprehensive_research | good | 28.3166 | 5113 | 5 | 0 |
| `agent_research_msft_googl_cloud_ai_capex_2025` | comprehensive_research | good | 32.4689 | 4971 | 8 | 0 |

Runtime:

- Input load: 0.0090s
- Model load: 69.5204s
- Total wall time: 263.5841s
- Per-query synthesis after resident load: about 28.3-39.6s
- vLLM log showed text-only mode, CUDA execution, no CPU offload, and GPU KV cache size of 59,068 tokens.

## Interpretation

- The calibrated evidence-pool path is a clear improvement over the old planner-to-retrieval demo for final synthesis. The model no longer has to decide from noisy top-k chunks; it mostly composes from citation-grade objects and explicitly reports missing aspects.
- Snowflake is the only `mixed` answer, and that is expected: the evidence pool intentionally marks missing total customer count and weighted-average remaining life. The model surfaced both gaps instead of fabricating them.
- Adobe was mostly correct but became conservative because the pool marks the "approximately 65% recognized over next 12 months" aspect missing. This shows the missing-aspect channel works, but also confirms the next retrieval/context-expansion task.
- NVIDIA and Microsoft/Alphabet required a larger output budget. The first cloud attempt with 900 output tokens produced truncated JSON on long answers; the final run used 1200 output tokens and compact evidence metadata.
- The current summary metric is still structural, not a full finance-quality score. It verifies parseability, citation validity, missing-aspect surfacing, and evidence use, but not every claim's financial correctness.

## Experiment Governance

- Hypothesis: If the final model receives role-separated citation/background/missing-aspect evidence, Qwen3.5-9B can generate useful Chinese finance summaries with valid citations and explicit uncertainty.
- Decision target: 6/6 parseable outputs, zero invalid cited object IDs, missing aspects acknowledged, and no reference-answer leakage.
- Ceiling / upper bound: synthesis quality is bounded by the calibrated pool's 70/73 citation aspect coverage and the three missing aspects.
- Baselines to beat: old Qwen3.5-9B planner-to-synthesis demo, where final synthesis citation coverage was weaker and retrieval noise was higher.
- Split and leakage guard: diagnostic fixed 6-query set only; no training; reference answers excluded from prompt.
- Stop conditions: stop or revise if JSON parsing fails, if model cites objects outside the pool, or if missing aspects are silently filled.
- Efficiency gate: single RTX 4090, no CPU offload, per-query synthesis under about 45s after model load.
- Decision label: diagnostic-only, proceed with context expansion and synthesis scoring.
- Mainline decision: keep calibrated evidence pool as the default input contract for final synthesis experiments.

## Runtime Efficiency

- Wall time: 263.5841s for 6 queries.
- Stage timing: model load 69.5204s; generation about 194s total.
- GPU memory: Qwen3.5-9B loaded at about 16.8 GiB model memory; vLLM KV cache available about 2.22 GiB.
- Throughput: vLLM progress showed roughly 23.7-27.4 output tokens/s.
- Bottleneck diagnosis:
  - Cold model load still dominates single-run startup.
  - Long financial answers need 1200 output tokens to close structured JSON reliably.
  - Metadata-heavy evidence packages waste context budget; prompt-side evidence records now omit URL/section/score fields.
- Efficiency improvement:
  - Serve Qwen3.5-9B as a resident process for repeated synthesis requests.
  - Keep prompt packages under about 5.2K tokens for 8K context.
  - Add a compact answer mode for daily tasks and reserve longer outputs for comprehensive/deep queries.

## Caveats And Next Step

- Not run: no human scoring of the generated Chinese answers, no larger final model comparison, no automatic claim-level correctness grader.
- Known risks:
  - The model cited one background-only object; final serving should either disallow background citations at decode-time or post-validate and ask for repair.
  - Citation object use rate is not a target by itself; some direct evidence is intentionally redundant across aspects.
  - The three missing aspects still require wider recall or source-context expansion.
- Next decision:
  - Add an answer-quality scorer against the reviewed query rubric.
  - Add context expansion / wider recall for the three missing aspects.
  - Add post-generation citation repair if `cited_background_object_count > 0`.
