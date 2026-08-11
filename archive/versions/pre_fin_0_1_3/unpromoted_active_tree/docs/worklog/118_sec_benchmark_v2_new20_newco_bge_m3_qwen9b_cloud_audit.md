# SEC Benchmark v2 New20 NewCo BGE-M3 + Qwen9B Cloud Audit

Date: 2026-05-20

## Scope

Run the 10 new-company reviewed-gold seed cases through the full cloud route:

- BGE-M3 pipeline-context retrieval on the RTX 5090 cloud host.
- Trace-aware Judgment Plan.
- RTX 5090 Qwen9B vLLM synthesis.
- Deterministic post-gates.

This route covers the new-company slice `AVGO/CSCO/INTC/QCOM/TXN/AMAT/MU/INTU/ADP/CRWD`. It is case-filtered and non-trap-only, so trap and gold-vs-pipeline parity gates are intentionally skipped in the final post-gate run.

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl`
- Reviewed ledger: `reports/exact_value_ledgers/sec_benchmark_v2_new20_newco_reviewed_exact_value_ledger.json`
- Reviewed facts/context from worklog 117.
- Cloud structured/index corpus: 20-company SEC universe, with BM25/ObjectBM25 indexes already built on cloud.
- BGE-M3 model: cloud ModelScope cache at `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`.
- Qwen9B model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

## Commands And Outputs

- BGE-M3 trace:
  `eval/sec_cases/outputs/run_20260520_v2_new20_newco_pipeline_context_bge_m3_top160_object8_cloud`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_new20_newco_judgment_plans_trace_seed_cloud.json`
- First Qwen run:
  `eval/sec_cases/outputs/run_20260520_v2_new20_newco_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Final deterministic replay:
  `eval/sec_cases/outputs/run_20260520_v2_new20_newco_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud_contractfix2`
- Final post-gates:
  `reports/quality/cloud_v2_new20_newco_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix2_post_gates/sec_benchmark_post_gates_summary.json`
- Logs:
  - `reports/logs/20260520_v2_new20_newco_bge_m3_trace_cloud.log`
  - `reports/logs/20260520_v2_new20_newco_bge_m3_judgment_plan_qwen9b_5090_cloud.log`

## Results

- BGE-M3 trace: 10/10 `context_prepared`; cloud wall time about 42.6 sec.
- Judgment Plan:
  - 10 plans.
  - 10 drivers.
  - 0 proxy drivers.
  - 2 plans with downgrades.
  - Validation: 10/10 pass.
  - Non-blocking warning: 23 `supporting_evidence_id_not_seen_in_trace` warnings because some plan support ids came from ledger source provenance rather than final trace rows.
- Qwen9B synthesis:
  - 10/10 `answered_qwen9b`.
  - 0 fallback outputs.
  - 0 ledger repairs.
  - Qwen run total elapsed: 473.0866 sec.
  - Model load phase: 37.2860 sec in run summary; vLLM log reports weights loading at 12.6467 sec and 16.8 GiB model memory.
  - Per-case elapsed range: about 30.6-65.2 sec.
  - Observed generation speed: about 40 output tokens/sec in vLLM progress logs.
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - scored count: 10
  - mean score pct: 0.88
  - answer-ledger: 10/10 pass, 41 exact-value hits
  - metric-role term: 10/10 pass
  - named-fact support: 10/10 pass, 77 named tokens checked, 0 unsupported tokens, 0 warnings
  - ledger-missing consistency: 10/10 pass, false missing count 0
  - caveat/claim: 10/10 pass, 10/10 required caveats covered, 0/10 disallowed violations
  - v2 semantic contract: 10/10 pass
  - answer-vs-Judgment-Plan: 10/10 pass
  - metric-source grounding: 10/10 pass, 127 metric references checked
  - ledger-unit: 69/69 pass
  - table-cell gate: skipped for all 10 because these cases do not require cell-table outputs
  - abstract-judgment gate: skipped for all 10 because no abstract rubric entries are defined for this new-company slice
  - trap gate: skipped by design for the non-trap-only case-filtered run
  - gold-vs-pipeline: skipped by design because this is pipeline-context-only

## Contractfix Notes

The initial post-gate run showed one deterministic answer-vs-plan failure on INTC: a weak-plan key point used strong local wording without repeating the local caveat. The fix added deterministic weak-plan caveat attachment to key points and replayed existing raw Qwen outputs.

The second replay also cleaned deterministic named-fact sanitizer text:

- Summary text is now sanitized for unsupported named labels.
- Unsupported English labels are replaced with natural generic wording instead of the older `未被当前引用证据支持的命名事实` phrase.
- The final `contractfix2` post-gates pass with named-fact warning count reduced from 1 to 0.

No Qwen generation rerun was needed for contractfix1/contractfix2; both used `raw_model_outputs.jsonl` from the first cloud run.

## Decision

The 10 new-company reviewed slice passes the full BGE-M3 + Judgment Plan + RTX 5090 Qwen9B diagnostic route on cloud. It is valid to use as the current new-company benchmark slice result.

This is still not a full 20-company mixed benchmark claim, because the run used only the 10 new-company seed cases and no original-company regression cases in the same manifest. The next stronger test is a mixed 20-company benchmark pack that combines selected original full40 cases with the 10 new-company cases, then reruns cloud BGE-M3/Qwen post-gates.

## Security Note

No SSH password, token, or temporary credential was written to repo files.
