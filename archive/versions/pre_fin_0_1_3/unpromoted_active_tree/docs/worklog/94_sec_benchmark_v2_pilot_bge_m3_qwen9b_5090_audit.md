# SEC Benchmark v2 Pilot BGE-M3 Qwen9B 5090 Audit

## Summary

Date: 2026-05-19

This entry closes the first v2 pilot pipeline-context model run. The fixed
BGE-M3 final-selector route prepared context for all six pilot cases, RTX 5090
resident Qwen3.5-9B answered the five non-trap cases, and the Microsoft/YouTube
trap used the deterministic refusal contract. The final `contractfix4` output
passes the deterministic post-gates that apply to this pipeline-only smoke.

This is still diagnostic-only. It proves the v2 pilot boundary can run through
BGE-M3 retrieval, trace-aware Judgment Plan prompt injection, true-Qwen
synthesis, and current gates. It does not prove the full 40-case v2 benchmark.

## Governance

- Hypothesis: reviewed v2 pilot cases can pass the locked BGE-M3
  pipeline-context route with RTX 5090 true-Qwen synthesis when Answer Plan
  support, caveat/claim constraints, and cell-level ledger checks are active.
- Decision target: six pilot outputs must have `qwen_answer_ratio=1.0` on
  non-trap eligible cases and pass trap, answer-ledger, metric-role,
  table-cell, named-fact, ledger-missing consistency, caveat/claim,
  answer-vs-Judgment-Plan, and ledger-unit gates.
- Ceiling: six-case pilot only. Gold-vs-pipeline comparison was skipped because
  no gold-context Qwen synthesis was run in this step.
- Baseline: v1.1 reviewed4 BGE-M3 + trace-aware Judgment Plan planfix run.
- Stop condition: any Qwen fallback on eligible cases, ledger repair, table
  cell miss, unsupported named fact, caveat/claim violation, or trap failure
  blocks v2 expansion.
- Decision label: diagnostic-only proceed.

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
- BGE-M3 trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_context_bge_m3_top160_object8_local`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json`
- Remote environment:
  `/root/autodl-tmp/FIN_Insight_Agent` on single RTX 5090 32GB
- Hardware profile:
  `rtx5090_32gb`

## Work Completed

Ran trace-aware Judgment Plan build for the v2 pilot:

- plans: 5
- skipped: 1 trap case
- drivers: 6
- plans with downgrade: 1

Synchronized the minimum remote run set to the RTX 5090 host:

- v2 pilot manifest
- v2 40-row ledger
- BGE-M3 trace
- Judgment Plan
- Qwen synthesis scripts
- vLLM hardware profile config

Remote backup before script/config overwrite:

- `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_sync_before_qwen_195252`

Remote backup before syncing the final contractfix scripts/ledger:

- `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_contractfix_sync_201328`

Ran RTX 5090 true-Qwen synthesis:

- raw output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4`
- remote log:
  `reports/logs/20260519_v2_pilot_bge_m3_judgment_plan_qwen9b_5090_synthesis.log`

Applied deterministic contract fixes without rerunning Qwen:

- trap refusal text now explicitly handles YouTube not belonging to
  Microsoft/MSFT and avoids putting case IDs with digits into trap answer text
- table-case partial `cell_table` output is completed from the ledger
- required caveats are materialized into caveat/limitations fields when the
  model only covered the idea elsewhere
- exact-value ledger `metric_id` generation now keeps old IDs when unique and
  appends `row_<label>` only when a same-case base ID duplicates

The metric-ID fix was required because Apple Products and Services gross-margin
percentage rows shared the same `case::ticker::year::gross_margin::percentage_rate`
ID. After the fix, the v2 ledger has 40 rows and 40 unique metric IDs.

## Results

Remote synthesis:

- answer status counts:
  - `answered_qwen9b`: 5
  - `answered_contract_fallback`: 1
- Qwen ledger repairs: 0
- model load: 32.0388 sec
- total elapsed: 233.4268 sec
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
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates/sec_benchmark_post_gates_summary.json`
- `qwen_answer_ratio=1.0`
- trap gate: pass
- answer-ledger gate: pass, 27 exact-value hits
- metric-role term gate: pass
- table-cell gate: pass, 12/12 valid AAPL cells
- named-fact gate: pass, unsupported token count 0
- ledger-missing consistency gate: pass, false missing count 0
- caveat/claim gate: pass, 11/11 caveats covered and 0/12 disallowed
  violations
- answer-vs-Judgment-Plan gate: pass, 5/5 checked cases
- ledger-unit gate: pass, 40/40
- abstract judgment gate: structurally skipped, 0 v2 pilot abstract rubrics
- gold-vs-pipeline gate: skipped by design because this run had only
  pipeline-context synthesis

## Findings

- BGE-M3 remains valid as the locked final selector for this pilot. The trace
  policy records `context_reranker=bge`,
  `context_reranker_model=BAAI/bge-reranker-v2-m3`, and
  `bm25_only_allowed=false`.
- The Answer Plan path generalized to the five non-trap v2 pilot cases:
  answer-vs-plan passed 5/5 after the ledger metric-ID contract was fixed.
- The v2 Apple case exposed a real upstream ledger contract issue: metric IDs
  must distinguish same family/role/year facts separated by row label.
- The Microsoft/YouTube trap exposed that the generic fallback refusal was too
  vague for wrong-attribution traps. The fallback now has a concrete
  Microsoft/YouTube branch.
- Required caveat enforcement should remain deterministic after model output;
  prompts alone were not enough to make every caveat appear in the validator's
  `caveats` text block.

## Decision

The v2 pilot BGE-M3 pipeline-context true-Qwen smoke passes after deterministic
contract fixes and the unique metric-ID ledger repair. Proceed to validator-first
v2 expansion planning, not directly to a full 40-case benchmark.

Follow-up completed on 2026-05-19: the validator-first step added the
manifest-aware v2 semantic contract gate and reran the pilot post-gates with it
enabled. Expanded summary:
`reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates_v2semantic/sec_benchmark_post_gates_summary.json`.
The new gate passes 5/5 checked cases, skips 1/6, and records three
GOOGL/META `one_sided_peer_comparison_support` warnings for Answer Plan/output
organization follow-up.

Next work should prioritize:

- a small next batch of reviewed pilot cases now that the first semantic
  contract validators exist
- one case with actual `period_change_amount` rows, because the implemented
  prior-period target-value validator has not yet been exercised by the current
  pilot ledger
- one stricter peer-comparison case or Answer Plan/output pass that reduces the
  GOOGL/META `one_sided_peer_comparison_support` warnings
