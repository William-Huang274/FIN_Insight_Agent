# SEC Benchmark v2 New20 Mixed BGE-M3 + Qwen9B Cloud Audit

Date: 2026-05-20

## Scope

Build and run a mixed 20-company benchmark pack after the 10 new-company slice passed on cloud. The objective is to verify that the expanded 20-company corpus does not regress the prior original-company route while adding new-company cases.

The mixed pack contains 30 cases:

- 16 original-company reviewed regression cases.
- 10 new-company reviewed cases for `AVGO/CSCO/INTC/QCOM/TXN/AMAT/MU/INTU/ADP/CRWD`.
- 4 trap regression cases.

## New Artifacts

- Mixed pack builder: `scripts/build_sec_benchmark_v2_new20_mixed_pack.py`
- Mixed manifest: `eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl`
- Mixed review approval: `reports/quality/sec_benchmark_v2_new20_mixed_review_approval.json`
- Mixed exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_new20_mixed_reviewed_exact_value_ledger.json`
- Updated abstract rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`
- BGE-M3 trace: `eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_context_bge_m3_top160_object8_cloud`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_new20_mixed_judgment_plans_trace_seed_cloud.json`
- Qwen output: `eval/sec_cases/outputs/run_20260520_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Final post-gates: `reports/quality/cloud_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_5090_rubricfix2_post_gates/sec_benchmark_post_gates_summary.json`

## Entry Gates

- Mixed mainline gold gate: 30/30 pass, 0 blockers, 0 warnings.
- Trap review gate: 4/4 pass, 26 skipped-not-applicable.
- Mixed ledger: 208 rows across 26 reviewed non-trap cases.
- Ledger-unit gate: 208/208 pass, 0 failures, 0 warnings.

## Cloud Run

- BGE-M3 ran on cloud against the 20-company BM25/ObjectBM25 indexes.
- BGE-M3 trace: 30/30 `context_prepared`, about 108 sec.
- Judgment Plan:
  - 23 plans.
  - 30 drivers.
  - 6 proxy drivers.
  - 8 plans with downgrades.
  - Validation: 23/23 pass.
  - Non-blocking warnings: 33 `supporting_evidence_id_not_seen_in_trace`, driven by ledger provenance ids outside the final BGE-selected rows.
- Qwen9B:
  - 26/26 eligible non-trap cases answered by Qwen.
  - 4/4 traps answered by contract fallback.
  - 0 failed eligible outputs.
  - 0 ledger repairs.
  - Total elapsed: 1176.6205 sec.
  - Model load: 28.8775 sec.
  - Per-case Qwen elapsed was typically 22-83 sec.
  - vLLM progress logs show about 40-43 output tokens/sec.

## Final Post-Gates

Final run: `cloud_v2_new20_mixed_pipeline_bge_m3_judgment_plan_qwen9b_5090_rubricfix2_post_gates`.

- `qwen_answer_ratio=1.0`
- trap gate: pass
- answer-ledger: 30/30 pass, 110 exact-value hits
- metric-role term: 30/30 pass
- table-cell: 48/48 valid cells across 2 table cases
- named-fact: 26 pass / 4 traps skipped, 175 named tokens, 0 unsupported, 0 warnings
- ledger-missing consistency: 30/30 pass, false missing count 0
- abstract judgment: 18/18 checked pass, 47/47 required dimensions
- caveat/claim: 30/30 pass, 47/47 caveats covered, 0/61 disallowed violations
- v2 semantic contract: 30/30 pass
- answer-vs-Judgment-Plan: 23/23 checked pass
- metric-source grounding: 26 pass / 4 traps skipped, 336 metric refs
- ledger-unit: 208/208 pass
- gold-vs-pipeline: skipped by design because this run is pipeline-context-only.

## Rubricfix Notes

The first post-gate run failed only abstract-rubric matching on two cases:

- `ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001`: model output used Chinese labels `雇主服务` and `PEO 服务`; rubric only accepted English labels.
- `AMZN_AWS_NUMERIC_2023_2025_001`: model output carried operating-income metric ids in structured `key_points.metric_ids`; the abstract text matcher only saw `经营利润`.

The fixes were rubric vocabulary corrections, not Qwen output changes. No Qwen regeneration or raw-output replay was needed.

## Decision

The mixed 20-company route passes as the current strongest diagnostic benchmark route. It supersedes the new-company-only slice as the next route for model comparisons, including any Qwen3.6-27B diagnostic comparison.

The next meaningful expansion should either:

- run Qwen3.6-27B-FP8/4bit against this frozen mixed pack for model comparison, or
- add another 10 SEC companies and repeat source/index/reviewed-gold gates before expanding the mixed benchmark again.

## Security Note

No SSH password, token, or temporary credential was written to repo files.
