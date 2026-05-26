# 20260520 SEC Benchmark v2 New20 NewCo BGE-M3 Qwen9B 5090 Cloud

Date: 2026-05-20

Type: cloud BGE-M3 retrieval trace + Judgment Plan + RTX 5090 Qwen9B inference + deterministic post-gates

Status: diagnostic-only completed

## Summary

Ran the 10 reviewed new-company SEC benchmark cases through the full cloud path. BGE-M3 ran on the cloud RTX 5090 host against the 20-company BM25/ObjectBM25 indexes, then Qwen9B synthesized all 10 answers from the trace-aware Judgment Plan. Final `contractfix2` post-gates passed all active gates.

## Artifact Paths

- Case manifest: `eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl`
- Reviewed ledger: `reports/exact_value_ledgers/sec_benchmark_v2_new20_newco_reviewed_exact_value_ledger.json`
- BGE-M3 trace: `eval/sec_cases/outputs/run_20260520_v2_new20_newco_pipeline_context_bge_m3_top160_object8_cloud`
- Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_new20_newco_judgment_plans_trace_seed_cloud.json`
- Judgment Plan validation: `reports/quality/sec_benchmark_v2_new20_newco_judgment_plan_trace_seed_validation_cloud.json`
- First Qwen output: `eval/sec_cases/outputs/run_20260520_v2_new20_newco_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Final output: `eval/sec_cases/outputs/run_20260520_v2_new20_newco_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud_contractfix2`
- Final post-gates: `reports/quality/cloud_v2_new20_newco_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix2_post_gates/sec_benchmark_post_gates_summary.json`
- Cloud logs:
  - `reports/logs/20260520_v2_new20_newco_bge_m3_trace_cloud.log`
  - `reports/logs/20260520_v2_new20_newco_bge_m3_judgment_plan_qwen9b_5090_cloud.log`

## Results

- BGE-M3 trace: 10/10 `context_prepared`, about 42.6 sec cloud wall time.
- Judgment Plan: 10 plans, 10 drivers, 0 proxy drivers, 2 downgrade plans; validation 10/10 pass.
- Qwen9B: 10/10 `answered_qwen9b`, 0 fallback, 0 ledger repairs.
- Runtime:
  - Qwen run total elapsed: 473.0866 sec.
  - Run summary model-load phase: 37.2860 sec.
  - vLLM weights loading: 12.6467 sec.
  - Model memory after load: 16.8 GiB.
  - Per-case elapsed range: about 30.6-65.2 sec.
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - gold mean score pct: 0.88
  - answer-ledger: 10/10 pass, 41 exact-value hits
  - metric-role term: 10/10 pass
  - named-fact: 10/10 pass, 77 named tokens, 0 unsupported, 0 warnings
  - ledger-missing consistency: 10/10 pass, false missing count 0
  - caveat/claim: 10/10 pass, 10/10 caveats covered, 0/10 disallowed violations
  - v2 semantic: 10/10 pass
  - answer-vs-Judgment-Plan: 10/10 pass
  - metric-source grounding: 10/10 pass, 127 metric refs
  - ledger-unit: 69/69 pass
  - trap gate skipped: no traps in this case-filtered new-company slice
  - gold-vs-pipeline skipped: pipeline-context-only run
  - abstract judgment skipped: no rubric entries for these new-company cases

## Deterministic Fixes

- Added weak Judgment Plan caveat attachment for key points that use weak-plan support.
- Sanitized unsupported named labels in summary text.
- Replaced awkward unsupported-label placeholders with natural generic wording.
- Replayed the first run's `raw_model_outputs.jsonl`; no Qwen generation rerun was needed for contractfixes.

## Governance

- Hypothesis: after reviewed-gold and ledger gates, the 10 new-company slice should pass the locked BGE-M3 + trace-aware Judgment Plan + RTX 5090 Qwen9B route without fallback or ledger repair.
- Decision target: 10/10 Qwen answers and all active deterministic post-gates pass.
- Result: target met.
- Ceiling: this is a new-company slice, not a full mixed 20-company benchmark claim.
- Next step: construct a mixed 20-company benchmark pack combining original-company regression cases and the 10 new-company cases, then rerun cloud BGE-M3/Qwen post-gates.
