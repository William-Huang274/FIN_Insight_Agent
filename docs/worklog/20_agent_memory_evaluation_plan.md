# Agent Memory Evaluation Plan

## Purpose

Design a reviewed finance-query evaluation layer and upgrade the demo pipeline
from "RAG finds chunks" to a task-specific evidence memory flow:

```text
Raw sources
-> EvidenceObject
-> MetricObject / TableObject / ClaimObject
-> Task-specific evidence pool
-> LLM synthesis
```

The immediate goal is not to maximize a retrieval benchmark. It is to test
whether Qwen3.5-9B can operate as a useful finance agent when memory is external:
planning, evidence need prediction, useful-candidate triage, missing-evidence
calibration, and final evidence use.

## Execution Steps

1. Create a reviewed-style query set.
   - Cover daily task, comprehensive research, and deep reasoning modes.
   - For each query, write expected facets, evidence needs, acceptable evidence
     types, reference answer outline, and main-agent reasoning rubric.
   - Keep this set small enough for fast Qwen3.5-9B cloud runs.

2. Add machine-readable eval data.
   - Store query records in `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl`.
   - Include fields for `ideal_facets`, `evidence_needs`,
     `reference_answer_points`, `missing_evidence_expectations`, and
     `agent_reasoning_rubric`.
   - This is a reviewed-style seed authored by the full model, not final human
     gold data.

3. Upgrade the demo script's evidence memory flow.
   - Keep broad per-task recall candidates instead of relying only on selected
     evidence groups.
   - Convert candidates into compact Evidence Cards containing provenance,
     retrieval route, verifier label, key facts, table/snippet excerpts, and raw
     evidence availability.
   - Build a Task-specific Evidence Pool per query, including planner memory,
     evidence memory, coverage memory, synthesis memory inputs, and audit IDs.
   - Replace global `compact_pack[:12000]` truncation with per-task budgeted
     prompt packing.
   - Preserve direct evidence ID/key facts before raw text, and guarantee every
     task is visible to synthesis.

4. Run Qwen3.5-9B cloud demo on the new query set.
   - Use no fallback planner.
   - Keep structured JSON enabled.
   - Use the current single RTX 4090 environment and Qwen3.5-9B text-only vLLM.
   - Save JSON/log artifacts under `reports/demo/`.

5. Evaluate the result qualitatively and structurally.
   - Planner quality: compare planner tasks against expected facets.
   - Evidence need quality: check whether task evidence hints match financial
     evidence requirements.
   - Evidence pool quality: inspect whether useful evidence was visible to
     synthesis as cards even if not selected as final evidence.
   - Synthesis quality: check claim support, coverage utilization, false
     missing evidence, and unsupported claims.
   - Decide whether 9B is viable as main agent or should remain a worker.

## Query Design Criteria

- Queries should require professional finance judgment, not only string lookup.
- Each query should have an explicit coverage target.
- At least some queries must contain counter-evidence or missing-evidence traps.
- Questions should be answerable primarily from the current SEC 10-K universe,
  but reference answers should explicitly state where current 10-K evidence is
  insufficient.
- The set must include both table-heavy metrics and narrative risk/strategy
  evidence.

## Evaluation Rubric

### Planner

- 5: Covers all core financial facets and counter-evidence dimensions.
- 3: Covers surface metrics but misses either risk, cost, or quality dimensions.
- 1: Mostly rewrites the query or searches a single broad phrase.

### Evidence Need Prediction

- 5: Requests the right SEC sections, table/note types, metrics, and risk
  disclosures for the facet.
- 3: Requests generally relevant evidence but misses specific financial objects.
- 1: Uses generic terms that cannot distinguish direct from partial evidence.

### Evidence Management

- 5: Useful candidates remain visible as cards, direct evidence is not dropped,
  and missing facets are explicit.
- 3: Some useful evidence is found but hidden by packing or selected too late.
- 1: Important evidence is absent from the working pool or synthesis input.

### Synthesis

- 5: Uses all key direct evidence, distinguishes direct/partial/missing, and
  balances support with risks or counter-evidence.
- 3: Mostly correct but misses one major direct fact or overstates a partial
  evidence item.
- 1: Unsupported claims, false missing evidence, or materially incomplete answer.

## Current Stop/Proceed Gate

- Proceed if the upgraded evidence memory flow prevents known truncation loss
  and exposes per-task coverage status in the final artifact.
- Mark 9B as worker-only if it repeatedly fails planner coverage, missing
  evidence calibration, or synthesis coverage utilization despite evidence
  cards being visible.
- Do not promote a run as mainline if final synthesis ignores visible direct
  evidence.

## 2026-05-16 Execution Status

- Created `eval_sets/sec_tech_10k_agent_reasoning_eval.jsonl` with 6
  reviewed-style seed queries:
  - 2 daily / daily-plus tasks: Apple Services, Snowflake visibility.
  - 2 comprehensive research tasks: Microsoft vs Alphabet cloud/capex, Amazon
    AWS/capex/free-cash-flow pressure.
  - 2 deep reasoning tasks: NVIDIA durability, Adobe ARR/RPO subscription
    durability.
- Upgraded `scripts/run_qwen_planner_evidence_demo.py` from selected-chunk
  synthesis to task evidence memory:
  - `planner_memory`: task, query variants, required facts.
  - `coverage_memory`: candidate/verified/direct/partial/false status.
  - `evidence_memory`: compact evidence cards and selected evidence groups.
  - `audit_memory`: candidate and selected evidence IDs.
- Replaced global JSON truncation with token-aware synthesis prompt packing.
  The first cloud attempt failed on Snowflake at 8,193 input tokens; the fix now
  measures prompt tokens with the tokenizer and compresses per-task evidence
  until the prompt fits the model context.
- Added a second compression pass for coverage/audit ID lists after Adobe showed
  that ID metadata alone could exceed the conservative synthesis safety budget.

## 2026-05-16 Run Results

- Main run artifact: `reports/demo/qwen9b_agent_reasoning_eval_v2.json`.
- Patch validation artifact: `reports/demo/qwen9b_agent_reasoning_eval_adbe_v3.json`.
- Model run ledger:
  `reports/model_runs/20260516_phase1_agent_memory_reasoning_eval.md`.
- Runtime: Qwen3.5-9B loaded in text-only vLLM mode on RTX 4090 with no CPU
  offload; full 6-query run took 839.5 seconds, including 103.7 seconds model
  load.
- Coverage summary:
  - 6 queries, 27 planner tasks.
  - 167 verified candidates.
  - Verifier labels: 19 direct, 83 partial, 65 false.
  - 15/27 task packs had direct selected evidence.
  - 16 task packs needed adaptive verification.
- Result quality:
  - Apple daily task was good and cited all target evidence.
  - Snowflake, Microsoft/Alphabet, Amazon, NVIDIA, and Adobe were mixed.
  - Broad recall was strong: most authored target evidence reached candidates
    and verified pools.
  - Final synthesis citation coverage was weaker than retrieval coverage.

## 2026-05-16 Decision

- The memory architecture direction should proceed.
- Qwen3.5-9B should not yet be promoted as the final main analyst model.
  It is useful as a planner/verifier worker, but final answer quality is still
  limited by evidence extraction and context packing.
- Next engineering priority should be structured object extraction before final
  synthesis:
  - MetricObject for numeric facts.
  - TableObject for table spans and row/column facts.
  - ClaimObject for risk/strategy claims.
  - Task-aware verifier snippets around `must_find` terms and relevant table
    spans instead of fixed first-1,800-character chunk crops.
