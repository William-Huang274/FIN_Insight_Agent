# SEC Benchmark v2 Pilot Plus3 Snow BGE-M3 Qwen9B 5090 Audit

## Summary

Date: 2026-05-19

This entry closes the v2 pilot plus3 run. The run kept the pipeline-context
retrieval route fixed on BGE-M3 as the final selector over BM25/ObjectBM25
candidates, added one reviewed Snowflake case covering product revenue, net
revenue retention, RPO, and consumption-based revenue visibility, built a
trace-aware Judgment Plan, ran RTX 5090 resident Qwen3.5-9B synthesis, and
passed the final deterministic post-gates after two validator/postprocess
cleanup fixes.

The result is diagnostic-only. It supports continuing staged v2 expansion, but
it is not a full v2 benchmark or full noisy-benchmark claim.

## Governance

- Hypothesis: the locked BGE-M3 pipeline route plus trace-aware Judgment Plan
  should generalize from plus2 to a third v2 reviewed case covering
  consumption-based SaaS visibility and percentage-vs-dollar metric separation.
- Decision target: all eight reviewed non-trap outputs must pass trap,
  answer-ledger, metric-role, table-cell, named-fact, ledger-missing
  consistency, caveat/claim, v2 semantic contract, answer-vs-Judgment-Plan, and
  ledger-unit gates with `qwen_answer_ratio=1.0`.
- Ceiling: plus3 diagnostic only; no full v2 benchmark, no noisy benchmark, and
  no gold-context Qwen synthesis.
- Stop condition: any non-trap Qwen fallback, ledger repair, hard semantic
  failure, unsupported named fact, table-cell miss, or answer-vs-plan failure
  blocks expansion.
- Decision label: diagnostic-only proceed.

## Inputs

- Cases:
  `eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl`
- New reviewed case:
  `SNOW_NRR_RPO_GROWTH_2023_2025_001`
- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_context_bge_m3_top160_object8_local`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus3_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus3_judgment_plans_trace_seed.json`
- Remote environment:
  `/root/autodl-tmp/FIN_Insight_Agent` on single RTX 5090 32GB
- Hardware profile:
  `rtx5090_32gb`

## Work Completed

Generated the plus3 reviewed artifact bundle:

- new builder:
  `scripts/build_sec_benchmark_v2_pilot_plus3_reviewed_gold.py`
- new manifest:
  `eval/sec_cases/test_cases_v2_pilot_plus3_seed.jsonl`
- reviewed facts/context for:
  `SNOW_NRR_RPO_GROWTH_2023_2025_001`
- exact-value ledger:
  80 rows, ledger-unit gate 80/80
- reviewed gold gate:
  8/8 pass, no blockers or warnings

Built the trace-aware Judgment Plan:

- plans: 8
- skipped: 0
- drivers: 11
- proxy drivers: 1
- plans with downgrades: 2
- Judgment Plan gate: 8/8 pass

Confirmed BGE-M3 stayed fixed as the final context selector:

- `effective_context_reranker=bge`
- `context_reranker_model=BAAI/bge-reranker-v2-m3`
- `bm25_only_allowed_for_this_run=false`
- candidate generators:
  `evidence_bm25`, `object_bm25`, `requirement_bm25`
- context prepared: 9/9 including the trap case
- SNOW context rows: 142

Ran RTX 5090 true-Qwen synthesis:

- raw output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_namedfact_metriclabel_fix`
- metric-source grounded deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_metric_source_grounded`
- post-gates:
  `reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_namedfact_metriclabel_fix_post_gates/sec_benchmark_post_gates_summary.json`
- metric-source grounded post-gates:
  `reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_metric_source_grounded_post_gates/sec_benchmark_post_gates_summary.json`
- remote log:
  `reports/logs/20260519_v2_pilot_plus3_bge_m3_judgment_plan_qwen9b_5090_synthesis.log`

Remote backup before overwrite:

- `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus3_sync_before_qwen_20260519_221731`

## Deterministic Fixes

Two deterministic gate/postprocess issues were fixed after the raw run:

- `scripts/validate_sec_benchmark_caveat_claims.py` and
  `scripts/validate_sec_benchmark_judgment_plan.py` now treat common Chinese
  negations such as `未`, `未证明`, and `未将` as valid near-window negation for
  disallowed-claim patterns that already define `allow_if_any_near`.
- `scripts/build_sec_benchmark_v2_pilot_plus2_reviewed_gold.py` now records the
  same Chinese negation terms in the GOOGL/META AI infrastructure case manifest
  so future plus2/plus3 builds do not regress.
- `scripts/validate_sec_benchmark_named_fact_support.py` now treats `Product`
  and `Net` as generic metric-label tokens, preventing the named-fact sanitizer
  from replacing `Product revenue` and `Net revenue retention rate` labels in
  Snowflake prose.
- `scripts/validate_sec_benchmark_v2_semantic_contracts.py` now avoids treating
  `revenue` inside `net revenue retention rate` as dollar/amount language when
  no explicit amount marker is present.

The final deterministic output was rebuilt from saved `raw_model_outputs.jsonl`;
Qwen was not rerun for these fixes.

## Results

Remote synthesis:

- answer status counts:
  - `answered_qwen9b`: 8
  - `answered_contract_fallback`: 1
- Qwen ledger repairs: 0
- model load: 40.4727 sec
- total raw synthesis elapsed: 413.7131 sec
- profile applied:
  - `max_model_len=65536`
  - `max_tokens=6000`
  - `gpu_memory_utilization=0.92`
  - `max_num_seqs=1`
  - `dtype=float16`
  - `TORCHDYNAMO_DISABLE=1`
  - `VLLM_USE_FLASHINFER_SAMPLER=0`

Final post-gates:

- `qwen_answer_ratio=1.0`
- trap gate: pass
- answer-ledger gate: pass, 51 exact-value hits
- metric-role term gate: pass
- table-cell gate: pass, 12/12 valid AAPL cells
- named-fact gate: pass, unsupported token count 0
- ledger-missing consistency gate: pass, false missing count 0
- caveat/claim gate: pass, 19/19 required caveats covered and 0/20
  disallowed-claim violations
- v2 semantic contract gate: pass, 8/8 checked cases
- answer-vs-Judgment-Plan gate: pass, 8/8 checked cases
- metric-source grounding gate: pass, 8/8 checked cases, 31 checked locations,
  133 metric references
- ledger-unit gate: pass, 80/80
- abstract judgment gate: structurally skipped, 0 v2 abstract rubrics
- gold-vs-pipeline gate: skipped by design because this was pipeline-context
  only

## Findings

- The new Snowflake case passed the target stress: product revenue, NRR
  percentage, RPO dollars, and 2025 RPO recognition timing stayed separated.
- BGE-M3 retrieved the Snowflake product revenue / NRR / RPO table context and
  the consumption-recognition caveat inside the 142-row context pack.
- The raw Snowflake answer was numerically good, but Qwen emitted invalid
  generated metric-object citation IDs for several Snowflake key points. A new
  metric-source grounding gate caught that the previous deterministic output
  left some metric-backed locations with empty or off-source evidence IDs. The
  backend now backfills each retained `metric_id` with its ledger
  `source_evidence_id`/`object_id`, and the replayed output passes the new gate.
- Residual non-blocking warnings remain:
  - named-fact summary warning: 1 `Llama` summary warning in the older Meta case.
  - v2 semantic warnings: 4 `one_sided_peer_comparison_support` warnings across
    older peer-comparison cases.
  - proxy/non-comparable checks are recorded as checked-with-no-violation
    warnings where expected.
- BGE-M3 remains the fixed route. BM25/ObjectBM25 are candidate generators, not
  the final selector.

## Decision

The plus3 run passes as a diagnostic v2 expansion smoke after adding the
metric-source grounding gate. Proceed to design the next reviewed v2 coverage
batch before any full noisy benchmark.

## Safety Notes

- No password or private token was written to project logs.
- The historical RTX 4090 profile was not changed.
- The raw Qwen output directory is preserved separately from the deterministic
  final output directory.

## 2026-05-19 Metric Source Grounding Delta

Problem:

- The existing answer-vs-Judgment-Plan gate allowed an answer location to keep
  valid metric IDs while its evidence IDs were empty or did not intersect the
  source evidence backing those metric IDs.
- Baseline gate run on
  `run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_namedfact_metriclabel_fix`
  failed 2 cases:
  `GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001` and
  `SNOW_NRR_RPO_GROWTH_2023_2025_001`.

Work completed:

- Added `scripts/validate_sec_benchmark_metric_source_grounding.py`.
- Wired the new gate into `scripts/run_sec_benchmark_post_gates.py`.
- Added deterministic ledger-source backfill in
  `scripts/run_sec_eval_synthesis_qwen9b_backend.py` for metric-backed
  `decision_drivers` and `key_points`.
- Added raw-output replay support to
  `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`, so saved Qwen raw
  outputs can be re-normalized without rerunning inference.

Evidence:

- Baseline metric-source gate:
  `reports/quality/tmp_metric_source_grounding_plus3_current.json`
  reported `can_enter_gate=false`, `fail_count=2`,
  `metric_location_missing_evidence_ids=5`, and
  `metric_id_not_grounded_to_source_evidence=8`.
- Replayed metric-source grounded output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_metric_source_grounded`.
- Final post-gates:
  `reports/quality/local_v2_pilot_plus3_pipeline_bge_m3_judgment_plan_qwen9b_5090_metric_source_grounded_post_gates/sec_benchmark_post_gates_summary.json`.
- Final status:
  `qwen_answer_ratio=1.0`, trap/answer-ledger/metric-role/table-cell/named-fact/
  ledger-missing/caveat-claim/v2 semantic/answer-vs-plan/metric-source/ledger-unit
  gates all pass. Gold-vs-pipeline remains intentionally skipped because this is
  a pipeline-only diagnostic run.

Follow-up:

- Next work should expand the v2 reviewed coverage matrix. The metric-source
  grounding check is now part of the normal post-gate bundle and should stay on
  for future pipeline-context runs.
