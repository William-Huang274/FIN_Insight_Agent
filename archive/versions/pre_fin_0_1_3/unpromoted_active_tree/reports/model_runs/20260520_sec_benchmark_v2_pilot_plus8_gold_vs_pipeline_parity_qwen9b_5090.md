# Model Run: 20260520_sec_benchmark_v2_pilot_plus8_gold_vs_pipeline_parity_qwen9b_5090

## Summary

- Purpose: close the plus8 post-freeze validation gap by running reviewed
  gold-context true-Qwen outputs and activating the gold-vs-pipeline parity gate.
- Status: diagnostic-only completed.
- Run type: gold-context trace + RTX 5090 Qwen9B inference + deterministic
  post-gates.
- Timestamp: 2026-05-20 15:34-15:45 Asia/Shanghai on the remote RTX 5090 host.
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus remote RTX
  5090 32GB workspace. Credentials are omitted.

## Code And Command

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl`.
- Gold context dir: `eval/sec_cases/reviewed_gold_context`.
- Ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json`.
- Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json`.
- Model: `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Hardware profile: `rtx5090_32gb`.

Key commands, with connection details omitted:

```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_eval.py \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --gold-context-dir eval/sec_cases/reviewed_gold_context \
  --mode gold_context \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_trace \
  --context-reranker none

TORCHDYNAMO_DISABLE=1 /root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_trace \
  --output-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json \
  --hardware-profile rtx5090_32gb \
  --structured-json \
  --mode gold_context

/root/miniconda3/bin/python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_qwen9b_vllm_5090 \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090 \
  --cases-path eval/sec_cases/test_cases_v2_pilot_plus8_seed.jsonl \
  --output-dir reports/quality/local_v2_pilot_plus8_gold_vs_pipeline_parity_post_gates \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus8_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v2_pilot_plus8_judgment_plans_trace_seed.json \
  --min-qwen-answer-ratio 1.0
```

## Inputs

- Frozen alias: `v2_plus8_mvp_diagnostic_freeze`.
- Manifest: 15 cases, with 13 reviewed non-trap cases and 2 pipeline-only traps.
- Pipeline comparison run:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`.
- Expanded abstract rubric:
  `eval/sec_cases/abstract_judgment_rubric_v0_1.json`.

## Outputs

- Gold-context trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_trace`.
- Gold-context Qwen output:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_qwen9b_vllm_5090`.
- Gold-vs-pipeline post-gates:
  `reports/quality/local_v2_pilot_plus8_gold_vs_pipeline_parity_post_gates/sec_benchmark_post_gates_summary.json`.
- Closeout:
  `reports/quality/sec_benchmark_v2_pilot_plus8_post_freeze_validation_hardening_closeout.json`.

## Results

- Gold-context trace: 13 `context_prepared`, 2 traps skipped as unsupported for
  gold-context mode.
- Gold-context Qwen: 13/13 reviewed non-trap cases answered by Qwen.
- Runtime: model load 38.8141 sec, total elapsed 597.8509 sec.
- Gold-vs-pipeline gate: 13 comparable cases, 13 pass, 0 fail,
  `can_enter_gate=true`.
- Full post-gates:
  - `gold_vs_pipeline_gate_skipped=false`
  - `gold_vs_pipeline_pass=true`
  - `qwen_answer_ratio=1.0`
  - trap, answer-ledger, metric-role, table-cell, named-fact,
    ledger-missing consistency, expanded abstract judgment, caveat/claim,
    v2 semantic, answer-vs-plan, metric-source grounding, and ledger-unit gates
    all passed.
- Expanded abstract judgment: 13/13 checked non-trap cases passed, 43/43
  required dimensions covered, 2 traps skipped.

## Decision

The plus8 post-freeze validation-hardening gap is closed. The pack remains an
MVP diagnostic freeze, not the full 40-case v2 benchmark.

## Safety Notes

- No password, private token, or temporary credential is recorded in this file.
- Do not mix future plus9 or full-v2 expansion results into this frozen plus8
  parity result.
