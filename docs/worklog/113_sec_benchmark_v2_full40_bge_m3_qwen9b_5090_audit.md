# SEC Benchmark v2 Full40 BGE-M3 + Qwen9B Audit

## Prompt

After plus8, expand to the full 40-case SEC benchmark before adding more
companies. Run the complete full40 BGE-M3 + Judgment Plan + RTX 5090 Qwen9B
pipeline and report the result.

## Decision

Proceed after deterministic upstream gates, because the full40 manifest now has
reviewed artifacts for all 34 non-trap cases and approved trap contracts for all
6 trap cases.

This remains a diagnostic benchmark route, not a broad-company generalization
claim, because the SEC universe is still the current 10-company set.

## Work Completed

- Built and approved the full40 reviewed set:
  - 40 total cases
  - 34 reviewed non-trap cases
  - 6 pipeline traps
  - 262 exact-value ledger rows
- Ran deterministic entry gates:
  - readiness/BM25 smoke: 40/40 pass
  - all40 mainline gold gate: 40/40 pass
  - trap6 smoke gate: 6/6 pass
- Ran full40 BGE-M3 pipeline-context trace:
  `eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_context_bge_m3_top160_object8_local`.
- Built trace-aware Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_full40_judgment_plans_trace_seed.json`.
- Ran RTX 5090 Qwen9B synthesis and deterministic contract replay:
  `eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1`.
- Ran final post-gates:
  `reports/quality/local_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates/sec_benchmark_post_gates_summary.json`.
- Added deterministic hardening surfaced by the first full40 post-gate run:
  - trap fallback now covers manifest-native `required_caveats` and
    `required_not_found`
  - abstract rubric negation handling now covers direct negation variants
  - percentage-rate semantic validation now uses the local metric-id clause
  - answer-vs-plan weak-support validation recognizes local caveat terms such
    as `无法`, `未提供`, `缺乏`, `not disclosed`, and `limited`

## Result

Final `contractfix1` post-gates pass:

- Qwen usage:
  - 34/34 eligible non-trap outputs answered by Qwen9B
  - 6/6 traps answered by contract fallback
  - `qwen_answer_ratio=1.0`
  - Qwen ledger repairs: 0
- Quality gates:
  - trap: pass
  - answer-ledger: 40/40 pass, 98 exact-value hits
  - metric-role term: 40/40 pass
  - table-cell: 96/96 valid cells across 3 table cases
  - named-fact: 34 pass, 6 traps skipped, 0 unsupported tokens
  - ledger-missing consistency: 40/40 pass, false missing count 0
  - abstract judgment: 17/17 checked cases pass, 56/56 required dimensions
  - caveat/claim: 67/67 required caveats, 0/88 disallowed violations
  - v2 semantic contract: 38/38 checked cases pass
  - answer-vs-Judgment-Plan: 24/24 checked cases pass
  - metric-source grounding: 34 pass, 430 metric references checked
  - ledger-unit: 262/262 pass
- Gold-vs-pipeline was skipped by design because this run is pipeline-context
  only.

Runtime:

- BGE-M3 trace local wall time: about 1021.9 sec, including first local HF model
  load/download.
- Qwen9B first cloud run: 1466.9654 sec total, including 38.7782 sec model
  load.
- Deterministic raw replay after contractfix1: 3.5607 sec.

## Evidence

- Model run ledger:
  `reports/model_runs/20260520_sec_benchmark_v2_full40_bge_m3_qwen9b_5090.md`.
- Final output:
  `eval/sec_cases/outputs/run_20260520_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix1`.
- Final post-gate summary:
  `reports/quality/local_v2_full40_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix1_post_gates/sec_benchmark_post_gates_summary.json`.
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_full40_reviewed_exact_value_ledger.json`.

## Next Step

Do not keep adding cases from the same 10-company universe as the main evidence
of generalization. The next benchmark expansion should add more SEC companies,
then rebuild filings, evidence objects, structured objects, BM25/object indexes,
reviewed gold artifacts, and BGE-M3/Qwen gates for the new universe.
