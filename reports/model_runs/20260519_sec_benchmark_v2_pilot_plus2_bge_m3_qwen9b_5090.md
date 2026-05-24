# Model Run: 20260519_sec_benchmark_v2_pilot_plus2_bge_m3_qwen9b_5090

## Summary

- Purpose: run the v2 pilot plus2 reviewed batch through locked BGE-M3
  pipeline-context retrieval, trace-aware Judgment Plan prompt injection, RTX
  5090 true-Qwen synthesis, and deterministic post-gates.
- Status: diagnostic-only completed
- Run type: BGE-M3 retrieval trace + Judgment Plan seed + cloud inference +
  deterministic contractfix + post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote RTX
  5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Git commit: local workspace is dirty; remote path is not a git repo.
- Remote backup before plus2 sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus2_sync_before_qwen_211242`
- Remote backup before contractfix script sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus2_contractfix_scripts_212656`
- Key commands, with credentials omitted:

```bash
python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus2_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus2_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus2_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus2_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus2_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus2_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus2_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix_source_evidence_alias_zhterms \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix_source_evidence_alias_zhterms \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus2_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix_source_evidence_alias_zhterms_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus2_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus2_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus2_seed.jsonl`
- BGE trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_context_bge_m3_top160_object8_local`
- Ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus2_reviewed_exact_value_ledger.json`
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus2_judgment_plans_trace_seed.json`
- BGE reranker: `BAAI/bge-reranker-v2-m3`
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`
- Hardware profile: `rtx5090_32gb`

## Outputs

- Raw Qwen output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- Final deterministic output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_contractfix_source_evidence_alias_zhterms`
- Post-gates:
  `reports/quality/local_v2_pilot_plus2_pipeline_bge_m3_judgment_plan_qwen9b_5090_contractfix_source_evidence_alias_zhterms_post_gates/sec_benchmark_post_gates_summary.json`
- Remote synthesis log:
  `reports/logs/20260519_v2_pilot_plus2_bge_m3_judgment_plan_qwen9b_5090_synthesis.log`
- Worklog audit:
  `docs/worklog/96_sec_benchmark_v2_pilot_plus2_bge_m3_qwen9b_5090_audit.md`

## Results

- BGE trace prepared 8/8 with BGE-M3 as final selector and
  `bm25_only_allowed=false`.
- Judgment Plan seed: 7 plans, 10 drivers, 1 trap skipped.
- Raw synthesis answer status:
  - `answered_qwen9b`: 7
  - `answered_contract_fallback`: 1
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap gate: pass
  - answer-ledger: pass, exact-value hits 21
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0
  - ledger-missing consistency: pass, false missing count 0
  - caveat/claim: pass, 16/16 required caveats and 0/17 violations
  - v2 semantic contract: pass, 7/7 checked cases
  - answer-vs-Judgment-Plan: pass, 7/7 checked cases
  - ledger-unit: pass, 70/70
  - abstract judgment: skipped, no v2 abstract rubrics
  - gold-vs-pipeline: skipped because this was pipeline-context only

## Experiment Governance

- Hypothesis: BGE-M3 final selection over BM25/ObjectBM25 candidates plus
  trace-aware Judgment Plan support should handle a plus2 v2 batch covering
  `period_change_amount` and stricter local peer-comparison support.
- Decision target: no eligible Qwen fallback, no ledger repair, and all
  applicable deterministic gates pass.
- Ceiling: eight-case pilot plus2 only, not full v2 generalization.
- Baseline: six-case v2 pilot BGE-M3 + Judgment Plan pass.
- Stop conditions: semantic-contract hard failure, table-cell miss,
  caveat/claim miss, named-fact miss, trap-refusal failure, or answer-vs-plan
  failure blocks v2 expansion.
- Decision label: diagnostic-only proceed.

## Runtime Efficiency

- Total raw synthesis elapsed: 367.1228 sec
- Model load: 38.4139 sec
- GPU profile: RTX 5090 32GB, `max_model_len=65536`,
  `max_tokens=6000`, `gpu_memory_utilization=0.92`, `max_num_seqs=1`,
  `dtype=float16`
- Runtime env:
  `TORCHDYNAMO_DISABLE=1`,
  `VLLM_USE_FLASHINFER_SAMPLER=0`
- Runtime caveat: vLLM still logs `SM 12.x requires CUDA >= 12.9`; it did not
  block this run.

## Caveats And Next Step

- The final pass required deterministic contractfix from saved raw outputs; no
  Qwen rerun was needed.
- Two one-sided peer-support warnings remain on the older GOOGL/META privacy
  case and should guide the next Answer Plan/output organization pass.
- Next decision should expand another small reviewed v2 batch or design a
  broader gold-set coverage matrix before any full noisy benchmark.
