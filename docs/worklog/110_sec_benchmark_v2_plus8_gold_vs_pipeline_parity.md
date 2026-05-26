# SEC Benchmark v2 Plus8 Gold-vs-Pipeline Parity

## Summary

Date: 2026-05-20 Asia/Shanghai

This entry records the second post-freeze validation-hardening step for
`v2_plus8_mvp_diagnostic_freeze`: running true-Qwen gold-context outputs and
activating the gold-vs-pipeline parity gate.

## Work Completed

- Generated plus8 reviewed gold-context trace:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_trace`.
- Ran RTX 5090 Qwen9B synthesis for 13 reviewed non-trap gold-context cases:
  `eval/sec_cases/outputs/run_20260520_v2_pilot_plus8_gold_context_reviewed_qwen9b_vllm_5090`.
- Ran full post-gates with separate gold and pipeline run dirs:
  `reports/quality/local_v2_pilot_plus8_gold_vs_pipeline_parity_post_gates/sec_benchmark_post_gates_summary.json`.
- Added closeout:
  `reports/quality/sec_benchmark_v2_pilot_plus8_post_freeze_validation_hardening_closeout.json`.

## Results

- Gold-context Qwen: 13/13 reviewed non-trap cases answered by Qwen.
- Runtime: model load 38.8141 sec; total elapsed 597.8509 sec.
- Gold-vs-pipeline gate: 13 comparable cases, 13 pass, 0 fail.
- Full post-gates:
  - `gold_vs_pipeline_gate_skipped=false`
  - `gold_vs_pipeline_pass=true`
  - `qwen_answer_ratio=1.0`
  - expanded abstract judgment: 13/13 checked non-trap cases, 43/43 required
    dimensions covered
  - trap, answer-ledger, metric-role, table-cell, named-fact,
    ledger-missing consistency, caveat/claim, v2 semantic, answer-vs-plan,
    metric-source grounding, and ledger-unit gates all passed

## Decision

The plus8 post-freeze validation-hardening branch is complete. plus8 remains a
frozen MVP diagnostic pack and still must not be described as the full 40-case
v2 benchmark.

Next sound step: decide whether to design a plus9 coverage matrix or start the
full-v2 route plan.

## Safety Notes

- No password, private token, or temporary credential is written here.
- Future expansion should use a new alias/run ID and must not overwrite the
  plus8 freeze result.
