# Model Run: 20260519_sec_benchmark_v2_pilot_plus4_bge_m3_qwen9b_5090

## Summary

- Purpose: run the v2 pilot plus4 reviewed batch through locked BGE-M3
  pipeline-context retrieval, trace-aware Judgment Plan prompt injection, RTX
  5090 true-Qwen synthesis, and deterministic post-gates.
- Status: diagnostic-only completed.
- Run type: BGE-M3 retrieval trace + Judgment Plan seed/gate + cloud vLLM
  inference + deterministic semantic-validator cleanup + post-gates.
- Timestamp: 2026-05-20 00:05-00:14 Asia/Shanghai on the remote host.
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote RTX
  5090 32GB repo `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command

- Git commit: local workspace is dirty; many SEC benchmark artifacts are
  untracked.
- Remote backup before plus4 sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus4_sync_before_qwen_235810.tgz`
- BGE reranker local model path:
  `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`.
- Credentials are omitted from this record.

Key commands:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local \
  --object-top-k 8 \
  --evidence-top-k 4 \
  --max-context-rows 160 \
  --context-reranker bge \
  --context-reranker-model /root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3 \
  --context-reranker-top-k 160 \
  --context-reranker-batch-size 8 \
  --context-reranker-max-length 2048 \
  --context-reranker-doc-max-chars 6000

/root/miniconda3/bin/python scripts/build_sec_benchmark_judgment_plan.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/evidence_packs/sec_benchmark_v2_pilot_plus4_judgment_plans_trace_seed.json \
  --report-path reports/quality/sec_benchmark_v2_pilot_plus4_judgment_plan_trace_seed_report.json

/root/miniconda3/bin/python scripts/validate_sec_benchmark_judgment_plan.py \
  --plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus4_judgment_plans_trace_seed.json \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local \
  --output-path reports/quality/sec_benchmark_v2_pilot_plus4_judgment_plan_trace_seed_gate.json

/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local \
  --output-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus4_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_5090_semanticfix2_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus4_judgment_plans_trace_seed.json \
  --skip-gold-vs-pipeline-gate \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`.
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`.
- Reviewed context/facts: `eval/sec_cases/reviewed_gold_context/` and
  `eval/sec_cases/reviewed_gold_facts/`.
- BGE reranker: local ModelScope cache for `BAAI/bge-reranker-v2-m3`.
- Qwen model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

## Outputs

- BGE-M3 context trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local`.
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus4_judgment_plans_trace_seed.json`.
- Judgment Plan report:
  `reports/quality/sec_benchmark_v2_pilot_plus4_judgment_plan_trace_seed_report.json`.
- Judgment Plan gate:
  `reports/quality/sec_benchmark_v2_pilot_plus4_judgment_plan_trace_seed_gate.json`.
- Qwen output:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`.
- Final post-gates:
  `reports/quality/local_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_5090_semanticfix2_post_gates/sec_benchmark_post_gates_summary.json`.
- Remote log:
  `reports/logs/20260519_v2_pilot_plus4_bge_m3_judgment_plan_qwen9b_5090.log`.

## Results

- BGE-M3 trace: 10/10 `context_prepared`.
- BGE-M3 policy:
  - `effective_context_reranker=bge`
  - `context_reranker_model=/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`
  - `bm25_only_allowed_for_this_run=false`
  - candidate generators: `evidence_bm25`, `object_bm25`,
    `requirement_bm25`
- Judgment Plan seed: 9 plans, 12 drivers, 1 proxy driver, 2 plans with
  downgrades, 0 skipped.
- Judgment Plan gate: 9/9 pass, with 5 non-blocking
  `supporting_evidence_id_not_seen_in_trace` warnings.
- Qwen synthesis:
  - `answered_qwen9b`: 9
  - `answered_contract_fallback`: 1 trap
  - Qwen ledger repairs: 0
  - model load: 39.354 sec
  - total synthesis elapsed: 473.2397 sec
- Final post-gates:
  - `qwen_answer_ratio=1.0`
  - trap gate: pass
  - answer-ledger: pass, 45 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0; 1 non-blocking warning
  - ledger-missing consistency: pass, false missing count 0
  - abstract judgment: pass, 4/4 required dimensions on the checked case
  - caveat/claim: pass, 22/22 required caveats covered and 0/24 disallowed
    claim violations
  - v2 semantic contract: pass, 9/9 checked cases
  - answer-vs-Judgment-Plan: pass, 9/9 checked cases
  - metric-source grounding: pass, 9 checked cases, 36 checked locations,
    138 metric references
  - ledger-unit: pass, 86/86
  - gold-vs-pipeline: skipped by design for this pipeline-context-only run

## Deterministic Fixes

`scripts/validate_sec_benchmark_v2_semantic_contracts.py` was tightened after
the raw post-gate pass found two false positives:

- Percentage-rate checks now inspect the local text around the specific
  percentage metric ID, preventing a same-sentence `total_value` amount from
  being attributed to the percentage metric.
- RPO/billings direct-revenue checks now target explicit recognized-revenue or
  direct-revenue language instead of generic `收入`.
- Chinese and English separation caveats such as `区分`, `严格区分`, and
  `separate` now satisfy the proxy/direct caveat guard.

No Qwen rerun was needed after these validator fixes.

## Runtime Efficiency

- Full remote script wall time: about 8.7 minutes from deterministic gate start
  to post-gate completion.
- BGE trace elapsed: about 41 seconds.
- Qwen model load: 39.354 seconds.
- Qwen synthesis elapsed: 473.2397 seconds for 10 trace rows.
- Observed GPU memory during Qwen: about 30.5 GiB used on RTX 5090 32GB.
- vLLM profile applied:
  - `max_model_len=65536`
  - `max_tokens=6000`
  - `gpu_memory_utilization=0.92`
  - `max_num_seqs=1`
  - `dtype=float16`
  - `TORCHDYNAMO_DISABLE=1`
  - `VLLM_USE_FLASHINFER_SAMPLER=0`

## Experiment Governance

- Hypothesis: adding the AMZN AWS reviewed numeric case should not break the
  locked BGE-M3 + trace-aware Judgment Plan + Qwen9B path.
- Decision target: all nine reviewed non-trap outputs must be true Qwen
  outputs and pass active post-gates, while the one trap must pass refusal
  smoke.
- Ceiling: this is still a staged diagnostic v2 expansion, not a full noisy
  benchmark or full MVP claim.
- Baseline: v2 plus3 BGE-M3 + Qwen9B run with metric-source grounding gate.
- Stop condition: any non-trap fallback, ledger repair, caveat/claim failure,
  semantic-contract failure, answer-vs-plan failure, or metric-source grounding
  failure blocks expansion.
- Decision label: diagnostic-only proceed.
- Mainline decision: plus4 can proceed to the next reviewed case build; do not
  claim full v2 benchmark completion.

## Caveats And Next Step

- Initial BGE-M3 loading with `BAAI/bge-reranker-v2-m3` failed because the
  remote host could not reach Hugging Face. The successful run used the existing
  local ModelScope cache and preserved BGE-M3 as the final selector.
- The remote launch script had Windows line endings; it emitted a harmless
  command-not-found after the post-gate `done` line. The run outputs and
  final post-gates were already written, and the status file was corrected.
- Next step: build
  `AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001` from the
  comparable AMZN/GOOGL cloud subset, then rerun deterministic gates before the
  next pipeline-context Qwen run.
