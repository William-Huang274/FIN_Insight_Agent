# SEC Benchmark v2 Pilot Plus2 BGE-M3 Qwen9B 5090 Audit

## Summary

Date: 2026-05-19

This entry closes the v2 pilot plus2 run. The run kept the pipeline-context
retrieval route fixed on BGE-M3 as the final selector over BM25/ObjectBM25
candidates, added two reviewed cases on top of the six-case v2 pilot, built a
trace-aware Judgment Plan, ran RTX 5090 resident Qwen3.5-9B synthesis, and
passed the final deterministic post-gates after a source-evidence/named-fact
contract fix.

The result is diagnostic-only. It supports continuing the staged v2 expansion,
but it is not a full v2 benchmark claim and did not run gold-context Qwen
synthesis.

## Governance

- Hypothesis: the locked BGE-M3 pipeline route plus trace-aware Judgment Plan
  should generalize from the six-case v2 pilot to a small plus2 batch covering
  `period_change_amount` and stricter local peer-comparison support.
- Decision target: all eight outputs must pass trap, answer-ledger,
  metric-role, table-cell, named-fact, ledger-missing consistency,
  caveat/claim, v2 semantic contract, answer-vs-Judgment-Plan, and ledger-unit
  gates with `qwen_answer_ratio=1.0`.
- Ceiling: eight-case diagnostic only; no full 40-case v2 benchmark and no
  gold-vs-pipeline comparison.
- Baseline: six-case v2 pilot
  `run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4`.
- Stop condition: any Qwen fallback on non-trap eligible cases, ledger repair,
  semantic-contract hard failure, unsupported named fact, table-cell miss, or
  answer-vs-plan failure blocks expansion.
- Decision label: diagnostic-only proceed.

## Inputs

- Cases:
  `eval/sec_cases/test_cases_v2_pilot_plus2_seed.jsonl`
- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_context_bge_m3_top160_object8_local`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus2_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus2_judgment_plans_trace_seed.json`
- Remote environment:
  `/root/autodl-tmp/FIN_Insight_Agent` on single RTX 5090 32GB
- Hardware profile:
  `rtx5090_32gb`

## Work Completed

Generated the plus2 reviewed artifact bundle:

- new manifest:
  `eval/sec_cases/test_cases_v2_pilot_plus2_seed.jsonl`
- reviewed facts/context for:
  `ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001`
- reviewed facts/context for:
  `GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001`
- exact-value ledger:
  70 rows, ledger-unit gate 70/70

Built the trace-aware Judgment Plan:

- plans: 7
- skipped: 1 trap case
- drivers: 10
- proxy drivers: 1
- plans with downgrades: 2

Confirmed BGE-M3 stayed fixed as the final context selector:

- `effective_context_reranker=bge`
- `context_reranker_model=BAAI/bge-reranker-v2-m3`
- `bm25_only_allowed_for_this_run=false`
- context prepared: 8/8

Ran RTX 5090 true-Qwen synthesis:

- raw output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix_source_evidence_alias_zhterms`
- remote log:
  `reports/logs/20260519_v2_pilot_plus2_bge_m3_judgment_plan_qwen9b_5090_synthesis.log`

Remote backups before overwrite:

- `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus2_sync_before_qwen_211242`
- `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus2_contractfix_scripts_212656`

## Contract Fix

The raw Qwen output for
`GOOGL_META_ADS_AI_INFRA_LOCAL_SUPPORT_2023_2025_001` locally cited both
Alphabet and Meta in the peer-comparison claim. The deterministic
postprocessor then sanitized `Alphabet` because the named-fact support rule
only recognized English metric terms, while the answer used Chinese financial
phrases such as `广告收入`, `经营利润`, and `资本支出`.

Fixes applied:

- `scripts/run_sec_eval_synthesis_qwen9b_backend.py` now keeps
  `source_evidence_id` in the allowed evidence ID set, not only `object_id` or
  `evidence_id`.
- `scripts/validate_sec_benchmark_named_fact_support.py` now maps
  `Alphabet -> GOOGL`, `Meta -> META`, and `Facebook -> META`.
- The named-fact ledger-backed support check now recognizes Chinese financial
  terms before treating a company name as unsupported.

The final output was regenerated from saved `raw_model_outputs.jsonl`; Qwen was
not rerun for the contractfix.

## Results

Remote synthesis:

- answer status counts:
  - `answered_qwen9b`: 7
  - `answered_contract_fallback`: 1
- Qwen ledger repairs: 0
- model load: 38.4139 sec
- total raw synthesis elapsed: 367.1228 sec
- profile applied:
  - `max_model_len=65536`
  - `max_tokens=6000`
  - `gpu_memory_utilization=0.92`
  - `max_num_seqs=1`
  - `dtype=float16`
  - `TORCHDYNAMO_DISABLE=1`
  - `VLLM_USE_FLASHINFER_SAMPLER=0`

Final post-gates:

- summary:
  `reports/quality/local_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix_source_evidence_alias_zhterms_post_gates/sec_benchmark_post_gates_summary.json`
- `qwen_answer_ratio=1.0`
- trap gate: pass
- answer-ledger gate: pass, 21 exact-value hits
- metric-role term gate: pass
- table-cell gate: pass, 12/12 valid AAPL cells
- named-fact gate: pass, unsupported token count 0
- ledger-missing consistency gate: pass, false missing count 0
- caveat/claim gate: pass, 16/16 required caveats covered and 0/17
  disallowed-claim violations
- v2 semantic contract gate: pass, 7/7 checked cases
- answer-vs-Judgment-Plan gate: pass, 7/7 checked cases
- ledger-unit gate: pass, 70/70
- abstract judgment gate: structurally skipped, 0 v2 abstract rubrics
- gold-vs-pipeline gate: skipped by design because this was pipeline-context
  only

## Findings

- The ADBE case exercised the previously inactive `prior_period_as_target_value`
  path and passed the v2 semantic contract gate.
- The new GOOGL/META AI infrastructure local-support case initially exposed a
  real deterministic postprocessing issue, not a BGE-M3 retrieval failure and
  not a raw-Qwen failure.
- The older GOOGL/META privacy case still emits two
  `one_sided_peer_comparison_support` warnings. They are not hard failures, but
  they remain useful pressure for the next Answer Plan/output organization
  pass.
- BGE-M3 remains the fixed route. BM25/ObjectBM25 are candidate generators in
  this run, not the final selector.

## Decision

The plus2 run passes as a diagnostic v2 expansion smoke. Proceed with another
small reviewed v2 batch or a broader gold-set design pass before any full noisy
benchmark. Do not describe this as full-v2 generalization yet.

## Safety Notes

- No password or private token was written to project logs.
- The historical RTX 4090 profile was not changed.
- The raw Qwen output directory is preserved separately from the deterministic
  contractfix directory.
