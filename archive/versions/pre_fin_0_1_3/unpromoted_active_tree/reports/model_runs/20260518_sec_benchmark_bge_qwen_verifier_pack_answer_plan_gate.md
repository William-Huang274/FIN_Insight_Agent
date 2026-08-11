# Model Run: 20260518_sec_benchmark_bge_qwen_verifier_pack_answer_plan_gate

## Summary

- Purpose: 回答 BGE/Qwen reranker + verifier-filtered evidence pack 是否足够继续进入 Answer Plan / Judgment Plan。
- Status: diagnostic-only completed.
- Run type: historical result audit + deterministic artifact build + validation gate.
- Timestamp: 2026-05-18.
- Environment: local `D:\FIN_Insight_Agent`; no new model inference was run in this step.

## Evidence Reviewed

- Reranker baseline: `reports/model_runs/20260516_phase2_object_reranker_baseline_compare.md`.
- Verifier-filtered evidence pool eval: `reports/metrics/sec_tech_10k_calibrated_evidence_pool_human_gold_eval.json`.
- Expanded/full-chain diagnostics:
  - `reports/model_runs/20260516_phase2_expanded_v0_2_full_chain_quality_eval.md`.
  - `reports/model_runs/20260516_phase2_cell_level_retrieval_and_strict_quality_gate.md`.
  - `reports/model_runs/20260516_phase2_vllm_2b_cell_verifier_full.md`.
  - `reports/model_runs/20260517_phase2_driver_pack_ledger_synthesis_qwen9b_complex6.md`.

## Result Interpretation

- BGE reranker was the strongest tested object reranker over the same object BM25 top25 pool: direct P@5 `0.6174`, relevant P@5 `0.8609`, false@5 `0.6957`, nDCG@5 `0.9458`, direct/relevant coverage `1.0`.
- Qwen3-Reranker-0.6B official path also beat BM25, but was slower and weaker than BGE on this eval: direct P@5 `0.5478`, nDCG@5 `0.8857`.
- Verifier-filtered citation pool was useful as an evidence source: reviewed citation precision `0.9286`, broad relevance precision `1.0`, reject rate `0.0`, with `3/73` aspects missing.
- The later full-chain blocker was not reranker relevance alone. The blocking issues were table/metric-family context, numeric relation consistency, cell/table output contracts, and calibrated abstract judgment.

## Decision

- Decision label: proceed, but only as a gated candidate/evidence-pack source.
- BGE/Qwen reranker + verifier-filtered evidence pack is good enough to inform candidate evidence and plan seeds.
- It is not good enough to replace the current reviewed9 mainline directly until metric-family/table-context and judgment-plan validators gate the intermediate artifact.

## Work Completed

- Added `scripts/build_sec_benchmark_judgment_plan.py`.
- Added `scripts/validate_sec_benchmark_judgment_plan.py`.
- Added optional `--judgment-plan-path` prompt injection to:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`.
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`.
- Built a deterministic seed Judgment Plan for:
  - `CLOUD_PROFITABILITY_2023_2025_DIAG_001`.
  - `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`.

## Commands

```powershell
python scripts\build_sec_benchmark_judgment_plan.py --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 --output-path reports\evidence_packs\sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json --report-path reports\quality\sec_benchmark_v1_reviewed_complex2_judgment_plan_seed_report.json

python scripts\validate_sec_benchmark_judgment_plan.py --plan-path reports\evidence_packs\sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json --trace-run-dir eval\sec_cases\outputs\run_20260518_reviewed8_pipeline_context_traces_top8 --trace-run-dir eval\sec_cases\outputs\run_20260518_platform_recurring_pipeline_context_traces_top8 --output-path reports\quality\sec_benchmark_v1_reviewed_complex2_judgment_plan_validation.json

python -m py_compile scripts\build_sec_benchmark_judgment_plan.py scripts\validate_sec_benchmark_judgment_plan.py scripts\run_sec_eval_synthesis_qwen9b_backend.py scripts\run_sec_benchmark_vllm_synthesis_from_traces.py
```

## Outputs

- Judgment Plan seed: `reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json`.
- Seed report: `reports/quality/sec_benchmark_v1_reviewed_complex2_judgment_plan_seed_report.json`.
- Validation report: `reports/quality/sec_benchmark_v1_reviewed_complex2_judgment_plan_validation.json`.

## Gate Results

- Seed report: `plan_count=2`, `driver_count=6`, `proxy_driver_count=2`, `plans_with_downgrades=2`.
- Judgment Plan validation: `can_enter_gate=true`, `pass_count=2`, `fail_count=0`, `driver_count=6`.
- Remaining warning: `supporting_evidence_id_not_seen_in_trace=7` for platform case. These IDs exist in the reviewed ledger but were not all present in that trace topK context; final synthesis must treat ledger evidence as an allowed support source, not only trace topK rows.

## Follow-Up

- Run true Qwen9B synthesis for the two complex reviewed cases with `--judgment-plan-path`.
- Add a final answer-vs-plan validator to detect new core judgments outside the validated plan.
- Decide whether to reduce trace warnings by forcing ledger source rows into context packing or by explicitly documenting ledger-only support as acceptable.
