# SEC Benchmark v2 Generalization Plan

This document absorbs the external v2 generalization proposal into the current
Fin Insight Agent benchmark state. It is an execution guide, not yet an
approved benchmark manifest.

## Current Baseline

As of 2026-05-20 after v2 pilot plus8:

- `eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl` is the current accepted
  MVP diagnostic pack candidate.
- The pack has 15 total cases: 13 reviewed non-trap cases and 2 pipeline-only
  traps.
- Coverage spans 10 companies, 15 unique task types, L1/L2/L3/L4 levels,
  numeric/table cases, peer comparisons, proxy/direct boundaries, text-heavy
  no-ledger summaries, wrong-attribution refusal, and metric-scope not-found
  refusal.
- BGE-M3 remains the fixed final context selector for pipeline-context runs.
- The plus8 BGE-M3 + trace-aware Judgment Plan + RTX 5090 Qwen9B route passed
  active post-gates with `qwen_answer_ratio=1.0`, no non-trap fallback, no
  ledger repair, and metric-source grounding pass.
- Freeze-readiness decision:
  `reports/quality/sec_benchmark_v2_pilot_plus8_mvp_freeze_readiness_review.json`.
  plus8 can be frozen as an MVP diagnostic pack, but it is not the full v2
  benchmark and cannot enter full mainline scored testing.
- Continuation alias:
  `v2_plus8_mvp_diagnostic_freeze`, documented in
  `docs/worklog/107_handoff_v2_plus8_mvp_freeze_next.md`.
- Post-freeze branch:
  harden plus8 validation first by expanding abstract rubrics and restoring a
  separate gold-vs-pipeline parity gate before plus9 or full-v2 expansion.
- Abstract-rubric hardening status:
  `reports/quality/sec_benchmark_v2_pilot_plus8_abstract_judgment_gate_expanded.json`
  checks all 13 non-trap plus8 cases and passes 13/13.
- Gold-vs-pipeline parity status:
  `reports/quality/local_v2_pilot_plus8_gold_vs_pipeline_parity_post_gates/sec_benchmark_post_gates_summary.json`
  uses separate reviewed gold-context and BGE-M3 pipeline-context Qwen outputs;
  gold-vs-pipeline is active, 13/13 comparable cases pass, and all active
  post-gates pass.
- Full40 reviewed route status:
  `eval/sec_cases/test_cases_v2_full40_seed.jsonl` now contains 40 governed
  seed cases with the target bucket counts. After promoting the remaining 12
  seed-only non-trap candidates into reviewed context/facts, the full40 pack has
  34 reviewed non-trap cases and 6 pipeline-only traps. Deterministic entry
  gates pass:
  `reports/quality/sec_benchmark_v2_full40_seed_readiness_bm25_smoke.json`
  passes 40/40,
  `reports/quality/sec_benchmark_v2_full40_all40_mainline_gold_gate.json`
  passes 40/40, and
  `reports/quality/sec_benchmark_v2_full40_trap6_smoke_gate.json` passes 6/6.
- Full40 BGE-M3 + Qwen route status:
  `eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1`
  is the current full40 pipeline-context Qwen output, with final post-gates at
  `reports/quality/local_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates/sec_benchmark_post_gates_summary.json`.
  The run has `qwen_answer_ratio=1.0`, 34/34 eligible Qwen answers, 6/6
  contract fallback traps, no ledger repairs, table-cell 96/96, caveat/claim
  67/67 with 0/88 disallowed violations, v2 semantic 38/38, answer-vs-plan
  24/24, metric-source grounding 430 refs, and ledger-unit 262/262. This
  validates the full40 route inside the current 10-company universe.
- Historical full40 seed-route gate:
  `reports/quality/sec_benchmark_v2_full40_seed_readiness_bm25_smoke.json`
  and `reports/quality/sec_benchmark_v2_full40_all40_mainline_gold_gate_expected_blocked.json`
  are now historical negative-control artifacts from before the 12 seed-only
  non-trap candidates were promoted.

As of 2026-05-19 after reviewed4 planfix:

- SEC benchmark v1 has a reviewed10 non-trap baseline plus 2 trap cases.
- Reviewed10 + 2 trap pipeline/table-cell bundle has passed deterministic
  post-gates in a case-filtered diagnostic run.
- v1.1 expansion has 4 reviewed diagnostic cases:
  - `SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001`
  - `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
  - `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
  - `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`
- v1.1 reviewed4 BGE-M3 pipeline-context plus RTX 5090 true-Qwen planfix gates
  passed:
  - `qwen_answer_ratio=1.0`
  - answer-vs-Judgment-Plan `4/4 pass`
  - answer-ledger `4/4 pass`
  - table-cell `36/36 valid`
  - named-fact unsupported tokens `0`
  - ledger-unit `69/69 pass`
  - CAPEX/FCF derived metric gate `12/12 pass`
- A manifest-native caveat/claim gate now exists:
  - reviewed4 `required_caveats` coverage `9/9`
  - reviewed4 `disallowed_claims` violations `0/11`
- A six-case v2 pilot seed manifest exists at
  `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`.

The v2 design should still proceed through reviewed pilot annotation before any
full 40-case benchmark build.

## Purpose

v1 primarily proves that the SEC benchmark path can run with reviewed evidence,
ledger discipline, structured model output, and deterministic post-gates.

v2 should test whether the system generalizes to:

- new companies and peer sets;
- new financial topics and SEC sections;
- new table and metric definitions;
- proxy versus direct metric caveats;
- weak-evidence conclusion calibration;
- not-found, wrong-attribution, and source-policy refusal behavior.

The goal is not to maximize case count. The goal is to add cases that isolate
specific failure modes and can be machine-checked.

## Adopted Principles

The following principles are adopted for future v2 or v2-pilot work:

1. Every case must state `test_objective`.
2. Every non-trap case must support both `gold_context` and `pipeline_context`.
3. Every synthesis case must include `required_caveats` and `disallowed_claims`.
4. Every numeric case must use cell-level reviewed facts, not seed retrieval
   candidates.
5. Text gold context should label evidence rows as `core`, `support`, or
   `caveat`.
6. Peer comparison cases should use 2 companies by default and at most 3.
7. Peer comparison cases must include entity-separation and comparability
   caveats.
8. Not-found or trap cases must test source policy directly and must not cite
   irrelevant evidence as support.
9. Prior-period values, percentage changes, and percentage-of-total rows must
   not enter target facts unless the case explicitly asks for them.
10. Proxy metrics must stay labeled as proxy evidence and must not be scored as
    direct disclosed metrics.

## Manifest Compatibility

The external proposal uses field names such as `id` and `modes`. The current
project uses the v1 manifest shape:

- `case_id`, not `id`
- `evaluation_modes`, not `modes`
- `source_policy`
- `gold_context_status`
- `numeric_checks.metric_families`
- `numeric_checks.metric_roles`
- `hard_gates`
- `hallucination_traps`
- `failure_types`

Any v2 implementation should either:

- keep this project-native schema for compatibility with existing runners; or
- add a deterministic migration script from the proposed v2 schema into the
  existing runner schema.

Until there is a strong reason to fork the runner contract, prefer the
project-native schema and add v2 fields as optional extensions:

- `case_family`
- `test_objective`
- `required_caveats`
- `disallowed_claims`
- `required_not_found`
- `conclusion_calibration_policy`

## Recommended Rollout

Do not create 40 reviewed cases in one step.

### Step 1: finish v1.1 reviewed4 validator baseline

Completed.

The current accepted continuation point is the reviewed4 BGE-M3 planfix output
with criterion-bounded Judgment Plan support and the caveat/claim gate enabled.

### Step 2: v2 pilot manifest

Completed as a seed-only manifest:

- `eval/sec_cases/test_cases_v2_pilot_seed.jsonl`
- readiness: 6/6 pass
- BM25 smoke: 6/6 pass
- expected warning: `gold_context_missing=5`

Reviewed-gold pilot annotation is now also completed for the five non-trap
cases:

- reviewed context/facts build:
  `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_build_report.json`
- partial approval:
  `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_partial_approval.json`
- reviewed gold gate:
  `reports/quality/sec_benchmark_v2_pilot_reviewed_gold_gate.json`, 5/5 pass
- trap smoke approval:
  `reports/quality/sec_benchmark_v2_pilot_trap_smoke_gate.json`, 1/1 pass
- exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_reviewed_exact_value_ledger.json`, 40 rows
- ledger unit gate:
  `reports/quality/sec_benchmark_v2_pilot_reviewed_ledger_unit_gate.json`, 40/40 pass

The v2 pilot has now also passed the first pipeline-context true-Qwen smoke:

- BGE-M3 trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_context_bge_m3_top160_object8_local`
- trace policy:
  `context_reranker=bge`,
  `context_reranker_model=BAAI/bge-reranker-v2-m3`,
  `bm25_only_allowed=false`
- trace-aware Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_judgment_plans_trace_seed.json`
- raw RTX 5090 Qwen output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix4`
- final post-gates:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates/sec_benchmark_post_gates_summary.json`
- result:
  `qwen_answer_ratio=1.0`, trap pass, answer-ledger pass,
  table-cell 12/12 pass, named-fact unsupported token count 0,
  caveat/claim 11/11 required caveats covered and 0/12 disallowed violations,
  answer-vs-Judgment-Plan 5/5 pass, ledger-unit 40/40 pass.

The run exposed and fixed an upstream ledger contract issue: metric IDs now
append a row-label suffix only when a same-case base metric ID duplicates, so
Apple Products and Services gross-margin percentage rows remain distinct.

The seed set contains:

- 1 L2 single-company segment-separation summary;
- 3 L3 numeric or cross-year trend cases;
- 1 L4 peer comparison case;
- 1 trap/source-policy case.

Next action is validator-first expansion, not full v2 scale-up.

### Step 3: validator-first expansion

Before promoting a v2 case into reviewed approval, ensure the needed validator
exists or the case is explicitly diagnostic-only.

Required v2 validator coverage:

- `required_caveats` coverage gate;
- `disallowed_claims` violation gate;
- text context role bounds for `core/support/caveat`;
- peer entity-separation gate;
- proxy-as-direct metric gate;
- non-comparable metric comparison gate;
- prior-period-as-target-value gate;
- percentage-change-as-absolute-value gate;
- trap source-policy and wrong-attribution gate.

Status after the 2026-05-19 validator-first step:

- `scripts/eval_sec_benchmark/validate_sec_benchmark_v2_semantic_contracts.py` now covers peer
  entity separation, source-policy/wrong-attribution traps, proxy/direct use,
  non-comparable metric caveats, `period_change_amount` target-value misuse,
  and percentage-role-as-amount misuse.
- The gate is wired into `scripts/eval_sec_benchmark/run_sec_benchmark_post_gates.py` and can be
  skipped with `--skip-v2-semantic-contract-gate`.
- The six-case v2 pilot passes the expanded post-gates:
  `reports/quality/local_v2_pilot_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix4_post_gates_v2semantic/sec_benchmark_post_gates_summary.json`.
- Current warnings are intentionally retained: GOOGL/META has three
  `one_sided_peer_comparison_support` warnings. They should guide the next
  Answer Plan/output organization pass but do not block this pilot.
- `prior_period_as_target_value` is implemented but still needs a new case with
  actual `period_change_amount` ledger rows to exercise it.

## Full v2 Target Shape

The full v2 target remains 40 high-quality cases, but it is a later milestone:

| Type | Count | Purpose |
|---|---:|---|
| L2 single-company single-year summary | 8 | Company and section-routing generalization |
| L3 single-company cross-year trend | 10 | Light synthesis and temporal generalization |
| Numeric/table cell gold | 10 | Table, unit, metric-role, and cell-role discipline |
| L4 two-company peer comparison | 6 | Entity separation and calibrated comparison |
| Trap/not-found/source-policy | 6 | Refusal, source policy, and unsupported claim control |

Full v2 should not be promoted until the pilot passes gold gates, ledger gates,
pipeline-context true-Qwen runs, and post-gates.

## Pilot Candidate Priority

The following candidates are aligned with the external proposal and current
project gaps. They should be confirmed against SEC availability before
annotation.

### Highest priority

- `META_REALITY_LABS_2024_001`
  - Tests Family of Apps versus Reality Labs separation.
  - Needs segment operating income/loss support and caveats against AI-cost
    invention.
- `PANW_RPO_BILLINGS_NUMERIC_2023_2025_001`
  - Tests RPO, billings, revenue, and visibility definition separation.
  - Must verify SEC disclosure availability and table cells before approval.
- `GOOGL_META_ADS_REGULATION_PRIVACY_2023_2025_001`
  - Tests advertising peer comparison, privacy/regulation caveats, and
    entity separation.
- `MSFT_YOUTUBE_REVENUE_TRAP_001`
  - Tests wrong-attribution refusal and source-scope discipline.

### Good follow-up candidates

- `AMD_SEGMENT_MIX_2023_2025_001`
- `ADBE_DIGITAL_MEDIA_REVENUE_ARR_2023_2025_001`
- `AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001`
- `SNOW_NRR_RPO_GROWTH_2023_2025_001`

### Needs pre-check before use

- `MSFT_CLOUD_GROSS_MARGIN_NUMERIC_2023_2025_001`
  - Microsoft may not disclose a direct `cloud gross margin` cell in the needed
    form. If not, convert this into a proxy/not-found/caveat case.
- `SNOW_PRODUCT_GROSS_MARGIN_TRAP_001`
  - Must confirm whether Snowflake discloses product gross margin or product
    gross profit. If it does, this is not a valid trap.

## Failure Tags To Add

Extend the v1 failure taxonomy with:

- `weak_evidence_overclaim`
- `proxy_as_direct_metric`
- `non_comparable_metric_comparison`
- `prior_period_as_target_value`
- `percentage_change_as_absolute_value`
- `entity_bleed_between_peers`
- `missing_caveat`
- `required_not_found_missing`
- `source_policy_violation`

These tags should be emitted by validators when possible, not only by manual
review notes.

## Pass Targets

Initial v2 pilot targets:

| Type | Target |
|---|---:|
| L2 single-year summary | at least 8.0 |
| L3 cross-year trend | at least 7.2 |
| numeric/table cases | at least 8.3 |
| L4 two-company comparison | at least 6.8 |
| trap/refusal | at least 90% correct |
| unsupported strong conclusion rate | at most 10% |

These targets are diagnostic until the v2 pilot has enough case diversity to
support a mainline claim.

## Governance Decision

Decision label: `proceed`, but only as staged expansion.

Immediate next action is to add the validators required by the next small case
batch, then expand the pilot in a controlled way. The v2 plan remains an
incremental pilot, not permission to build or score a 40-case full benchmark.

## Next Reviewed Batch Design

After the v2 plus3 metric-source grounded closeout, the next reviewed batch is
designed in:

- `docs/eval/sec_benchmark_v2_next_reviewed_batch_design.md`

The proposed batch is an MVP-extension batch, not the full 40-case v2 target.
It prioritizes:

- `AMZN_AWS_NUMERIC_2023_2025_001`;
- a new AMZN/GOOGL comparable cloud profitability peer case;
- a separate Microsoft cloud/AI margin proxy case;
- `NVDA_DATACENTER_2023_2025_001`;
- `SNOW_RISK_2023_2025_001`;
- a new Microsoft Azure gross-margin not-found trap.

The broad 3-company `CLOUD_PROFITABILITY_2023_2025_DIAG_001` should not be
promoted as-is; it should be split to avoid Microsoft disclosure asymmetry
polluting a comparable peer case.
