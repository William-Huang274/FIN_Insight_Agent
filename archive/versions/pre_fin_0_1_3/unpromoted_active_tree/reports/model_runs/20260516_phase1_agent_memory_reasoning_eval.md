# Model Run: 20260516_phase1_agent_memory_reasoning_eval

## Summary
- Purpose: Evaluate Qwen3.5-9B as a resident planner/verifier/synthesizer over a reviewed-style finance reasoning query set with task-specific evidence memory.
- Status: completed, diagnostic-only.
- Run type: inference and qualitative evaluation.
- Timestamp: 2026-05-16 Asia/Shanghai.
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, single RTX 4090 24GB, `/root/miniconda3/bin/python`, vLLM text-only mode.

## Code And Command
- Entry point: `scripts/run_qwen_planner_evidence_demo.py`
- Eval set: `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl`
- Main output: `reports/demo/qwen9b_agent_reasoning_eval_v2.json`
- Main log: `reports/demo/qwen9b_agent_reasoning_eval_v2.log`
- Patch validation output: `reports/demo/qwen9b_agent_reasoning_eval_adbe_v3.json`
- Patch validation log: `reports/demo/qwen9b_agent_reasoning_eval_adbe_v3.log`
- Key command settings: `--retrieval-mode hybrid`, `--candidate-k 10`, `--verify-k 2`, `--adaptive-verify-k 8`, `--table-rescue-k 3`, `--selected-per-task 3`, `--max-task-count 5`, `--max-model-len 8192`, `--synthesis-max-tokens 1000`, `--language-model-only`, `--structured-json`, no fallback planner.
- Code version: dirty workspace; key changed files include `scripts/run_qwen_planner_evidence_demo.py`, `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl`, and `docs/worklog/20_agent_memory_evaluation_plan.md`.

## Inputs
- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_10k`
- Dense index: `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16`
- Model: `data/models_private/modelscope/Qwen/Qwen3.5-9B`
- Query profile: 6 queries, covering daily task, comprehensive research, and deep reasoning modes.
- Label protocol: model-authored reviewed-style seed with `ideal_facets`, `evidence_needs`, `reference_answer_points`, `missing_evidence_expectations`, and `agent_reasoning_rubric`.

## Results
- Main run wall time: 839.5 sec total, including 103.7 sec model load.
- Qwen/vLLM runtime: model loading took about 16.8 GiB; observed GPU memory during run was roughly 22-24GB; no CPU offload was used.
- Main run task count: 27 planner tasks across 6 queries.
- Evidence verification: 167 verified candidates; labels were 19 direct, 83 partial, 65 false.
- Direct evidence coverage: 15/27 task packs had direct selected evidence; 12/27 were missing direct evidence.
- Adaptive verification: 16 task packs required deeper verification beyond the first 2 candidates.
- Synthesis quality labels: Apple was `good`; the other 5 queries were `mixed`.

## Target Evidence Visibility
- Apple Services: target evidence candidate/verified/selected/cited = 2/2, 2/2, 2/2, 2/2.
- Snowflake visibility: target evidence candidate/verified/selected/cited = 4/4, 4/4, 2/4, 2/4.
- Microsoft vs Alphabet cloud/capex: target evidence candidate/verified/selected/cited = 7/7, 7/7, 6/7, 2/7.
- Amazon AWS/capex/FCF: target evidence candidate/verified/selected/cited = 4/4, 4/4, 4/4, 0/4 because final synthesis JSON was truncated or invalid.
- NVIDIA durability: target evidence candidate/verified/selected/cited = 6/6, 6/6, 6/6, 3/6.
- Adobe ARR/RPO: target evidence candidate/verified/selected/cited = 3/4, 3/4, 3/4, 2/4; the missing target was contract-caveat evidence from `ADBE_2025_10K_ITEM8_BLOCK_0002_PART_03_OF_06`.

## Interpretation
- Planner: Qwen3.5-9B is useful for broad task decomposition. It consistently decomposed complex prompts into 5 task packs and usually covered the obvious finance facets.
- Retrieval/evidence memory: broad recall was strong at the candidate level. Most authored target evidence entered candidates and verified pools, which validates the shift away from single-route top5 citation.
- Verifier: the verifier remains the weakest stage. It often marks long chunks as partial because the relevant fact is outside the 1,800-character verifier snippet. Adobe RPO is the clearest example: the relevant RPO text exists in the selected evidence object but was not exposed to the verifier prompt.
- Synthesis: when evidence is compact and direct, 9B uses it correctly. When many tasks and long selected groups compete for 8K context, it drops details, reports false missing evidence, or emits invalid/truncated JSON.
- Main-agent decision: keep 9B as a worker/planner/verifier candidate for now, not the final main analyst. It can run the workflow, but final synthesis and missing-evidence calibration need stronger context management or a larger/smarter model.

## Engineering Findings
- Fixed the previous global `compact_pack[:12000]` failure by adding task-specific evidence pools with planner memory, coverage memory, evidence cards, selected evidence groups, and synthesis input audit.
- First full run attempt failed on Snowflake because character budgets did not guarantee tokenizer-level context fit. Added tokenizer-aware synthesis packing.
- The full `v2` run completed, but Adobe still exceeded the conservative internal prompt safety budget in audit. Added compact coverage-memory ID lists and validated Adobe in `adbe_v3`: `prompt_tokens=6049`, `max_input_tokens=7064`, `within_model_context=True`.
- Remaining issue: per-task char budgets can force evidence cards out of the prompt (`max_cards=0`) while selected group IDs/key facts remain. This is acceptable for a smoke demo but not enough for final-grade finance synthesis.

## Experiment Governance
- Hypothesis: task-specific evidence memory should prevent global truncation loss and make it possible to distinguish retrieval failure from evidence-use failure.
- Decision target: completed run on 6 reviewed-style queries with no fallback planner, no context overflow, auditable per-task coverage, and visible selected evidence IDs.
- Ceiling: 8K context is a hard ceiling for current 9B synthesis; broad evidence can enter the artifact but cannot all enter the final prompt.
- Baseline: prior 3-query demo with global prompt truncation and false missing evidence.
- Decision label: diagnostic-only.
- Mainline decision: proceed with evidence-memory architecture, but do not promote Qwen3.5-9B final synthesis as mainline quality.

## Next Step
- Add MetricObject/TableObject/ClaimObject extraction so verifier and synthesis see task-relevant facts instead of raw long chunks.
- Replace fixed verifier text crop with task-aware snippet extraction around `must_find` terms and table spans.
- Add a strict synthesis output budget or repair pass because Amazon produced invalid/truncated JSON despite structured output mode.
- Add evaluation code that scores planner facets, target visibility, selected evidence, and cited evidence automatically from the authored eval set.
