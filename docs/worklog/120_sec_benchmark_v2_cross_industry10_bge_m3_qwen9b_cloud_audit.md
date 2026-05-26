# SEC Benchmark v2 Cross-Industry10 BGE-M3 + Qwen9B Cloud Audit

Date: 2026-05-20

## Scope

在已通过 `new20_mixed` 的基础上，新增一组披露结构差异更大的 10家公司 case，并走完整云端路线：

- 金融/支付：`JPM`, `V`
- 医药：`JNJ`, `LLY`
- 工业：`CAT`, `GE`
- 消费：`WMT`, `PG`
- 能源：`XOM`, `CVX`

该 slice 包含 6 个 numeric exact-value cases 和 4 个 text-only cases。目标是验证 30-company SEC 语料下，BGE-M3 pipeline context + trace-aware Judgment Plan + RTX 5090 Qwen9B 是否仍能保持 `qwen_answer_ratio=1.0` 和 deterministic gates 全绿。

## New Artifacts

- Seed builder: `scripts/build_sec_benchmark_v2_cross_industry10_seed.py`
- Reviewed-gold builder: `scripts/build_sec_benchmark_v2_cross_industry10_reviewed_gold.py`
- Case manifest: `eval/sec_cases/test_cases_v2_cross_industry10_seed.jsonl`
- Review approval: `reports/quality/sec_benchmark_v2_cross_industry10_review_approval.json`
- Exact-value ledger: `reports/exact_value_ledgers/sec_benchmark_v2_cross_industry10_reviewed_exact_value_ledger.json`
- Local Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_cross_industry10_judgment_plans_trace_seed.json`
- Cloud BGE trace: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_pipeline_context_bge_m3_top160_object8_cloud`
- Cloud Judgment Plan: `reports/evidence_packs/sec_benchmark_v2_cross_industry10_judgment_plans_trace_seed_cloud.json`
- Cloud Qwen output: `eval/sec_cases/outputs/run_20260520_v2_cross_industry10_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_cloud`
- Cloud post-gates: `reports/quality/cloud_v2_cross_industry10_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates/sec_benchmark_post_gates_summary.json`
- Cloud log: `reports/logs/20260520_v2_cross_industry10_bge_m3_judgment_plan_qwen9b_5090_cloud.log`

## Entry Gates

- Reviewed seed: 10 cases.
- Reviewed context: 62 rows.
- Reviewed exact facts: 39 rows.
- Text-only cases: 4 (`JPM`, `JNJ`, `XOM`, `CVX`).
- Mainline gold gate: 10/10 pass, 0 blockers, 0 warnings.
- Exact-value ledger: 39 rows.
- Ledger-unit gate: 39/39 pass, 0 failures, 0 warnings.
- Local Judgment Plan gate: 6/6 pass for numeric cases; 4 text-only cases skipped by design because they have no ledger rows.

## Cloud Run

- BGE-M3 trace: 10/10 `context_prepared`; stage wall time about 44 sec.
- Trace-aware Judgment Plan:
  - 6 plans.
  - 6 drivers.
  - 0 proxy drivers.
  - Validation: 6/6 pass.
  - Non-blocking warnings: 15 `supporting_evidence_id_not_seen_in_trace`, caused by ledger provenance ids not appearing verbatim in final BGE trace rows.
- Qwen9B synthesis:
  - 10/10 `answered_qwen9b`.
  - 0 fallback outputs.
  - 0 ledger repairs.
  - Total elapsed: 366.7974 sec.
  - Model load phase: 57.2505 sec; vLLM log reports weights loaded in 26.63 sec and model memory of 16.8 GiB.
  - Available KV cache after load: 10.78 GiB; vLLM reported 342,528 GPU KV-cache tokens.
  - Per-case generation elapsed range from log: 25.0135-39.5535 sec.
  - Observed output speed: about 39-40 output tokens/sec after warmup.

## Final Post-Gates

Final run: `cloud_v2_cross_industry10_pipeline_bge_m3_judgment_plan_qwen9b_5090_post_gates`.

- `qwen_answer_ratio=1.0`
- scored count: 10
- mean score pct: 0.88
- answer-ledger: 10/10 pass, 26 exact-value hits
- metric-role term: 10/10 pass
- table-cell: 10 skipped; this slice has no table-output cases
- named-fact support: 10/10 pass, 65 named tokens, 0 unsupported, 0 warnings
- ledger-missing consistency: 10/10 pass, false missing count 0
- abstract judgment: 10 skipped; this slice has no abstract-rubric entries
- caveat/claim: 10/10 pass, 10/10 required caveats covered, 0/10 disallowed violations
- v2 semantic contract: 10/10 pass
- answer-vs-Judgment-Plan: 6/6 checked pass, 4 text-only skipped
- metric-source grounding: 10/10 pass, 74 metric references checked
- ledger-unit: 39/39 pass
- trap gate: skipped by design for the non-trap-only slice
- gold-vs-pipeline: skipped by design because this is pipeline-context-only

## Decision

The new cross-industry 10-company slice passes the cloud BGE-M3 + Judgment Plan + RTX 5090 Qwen9B diagnostic route. It provides stronger generalization evidence than the prior tech-heavy 20-company universe because it adds bank, payments, pharma, industrial, retail, consumer staples, and energy disclosures.

This is still diagnostic-only. The next stronger claim should merge these 10 cases into a mixed regression pack with prior original/new20 cases and traps, then rerun cloud BGE-M3/Qwen post-gates on the combined pack.

## Safety Notes

- No SSH password, token, or temporary credential was written to repo files.
- Remote results were synchronized back to local under the same relative paths.
- The old `sec_benchmark_v2_cross_industry10_reviewed_gold_partial_approval.json` stale local artifact was removed; the accepted approval artifact is `sec_benchmark_v2_cross_industry10_review_approval.json`.
