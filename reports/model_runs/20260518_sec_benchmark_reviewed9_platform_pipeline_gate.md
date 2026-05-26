# Model Run: 20260518_sec_benchmark_reviewed9_platform_pipeline_gate

## Summary
- Purpose: Move `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001` from reviewed gold-context smoke into real pipeline-context Qwen synthesis, then combine it with the prior reviewed8 + trap bundle as reviewed9.
- Status: diagnostic-only pass.
- Run type: retrieval trace + inference + deterministic gate fixes + evaluation gates.
- Timestamp: 2026-05-18.
- Environment: local trace/gates; cloud RTX 4090 resident vLLM for Qwen3.5-9B.

## Code And Command
- Entry points:
  - `scripts/run_sec_benchmark_eval.py`
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Trace command:
```bash
python scripts/run_sec_benchmark_eval.py \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --evidence-top-k 8 \
  --object-top-k 8
```
- Final cloud inference command:
```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe \
  --mode pipeline_context \
  --case-id PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json \
  --max-model-len 32768 \
  --max-tokens 5000 \
  --structured-json \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 1
```
- Final reviewed9 gate command:
```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle \
  --output-dir reports/quality/local_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle_post_gates \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json
```
- Key changes:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`: loads the per-case abstract rubric into the final synthesis prompt as a hard compact contract.
  - `eval/sec_cases/abstract_judgment_rubric_v0_1.json`: added strict Adobe margin/profitability caveat for the platform recurring-quality case.
  - `scripts/validate_sec_benchmark_named_fact_support.py`: accepts ledger-backed company metric labels through sibling `metric_ids`, and propagates union metric IDs to summary checks.

## Inputs
- Case: `PLATFORM_RECURRING_QUALITY_2023_2025_DIAG_001`.
- Trace: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_context_traces_top8`.
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`, 50 rows.
- Reviewed9 gold reference: `eval/sec_cases/outputs/run_20260518_reviewed9_gold_reference_qwen9b_mixed`.
- Reviewed9 pipeline bundle: `eval/sec_cases/outputs/run_20260518_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle`.

## Outputs
- Initial platform pipeline diagnostic: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000`.
- Rubric prompt diagnostic: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt`.
- Final platform pipeline output: `eval/sec_cases/outputs/run_20260518_platform_recurring_pipeline_qwen9b_vllm_structured_5000_rubricprompt_strictadobe`.
- Final reviewed9 post-gates: `reports/quality/local_reviewed9_platform_strictadobe_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`.

## Results
- Pipeline trace: `context_row_count=120`, with all 9 company-year pairs present.
- Initial platform pipeline output: `answered_qwen9b`, score `8.8`, but abstract gate failed 4/6 and named-fact gate had one ledger-label false positive.
- Final platform pipeline output: `answered_qwen9b`, score `8.8`, valid JSON, `ledger_text_contract_violation_count=0`, `ledger_text_contract_sanitized_count=0`.
- Final single-case gates after strict rubric and named-summary fix:
  - `gold_vs_pipeline_pass=true`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`
  - `ledger_unit_gate_pass=true`
- Reviewed9 + 2 trap final gates:
  - `trap_gate_pass=true`
  - `gold_vs_pipeline_pass=true`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`
  - `ledger_unit_gate_pass=true`
  - `qwen_answer_ratio=1.0`
  - `qwen_ledger_repaired=0`
  - `fallback_answered=0`
  - `trap_outputs_excluded=2`

## Manual Review
- The final answer now separates three drivers: Apple Services revenue/margin improvement with non-pure-subscription caveat, Adobe subscription visibility with explicit missing margin/cost-structure caveat, and Microsoft Cloud proxy growth with gross-margin/AI infrastructure pressure caveat.
- The answer uses ledger `display_value_zh` values in key points and keeps metric IDs as sibling support.
- Remaining qualitative risk: one phrase says Apple Services includes hardware-related services. The intended caveat is narrower: Apple Services is a mixed services bundle and not pure subscription. This is acceptable for diagnostic gating but should be tightened in future prompt wording.

## Experiment Governance
- Hypothesis: Feeding the abstract rubric into final synthesis will convert the pipeline output from “safe numbers but incomplete abstract judgment” into a supported decision-level answer.
- Decision target: reviewed9 + trap bundle must pass true-Qwen ratio 1.0, no ledger repair, answer ledger, metric role, named fact, ledger missing consistency, abstract judgment, ledger unit, gold-vs-pipeline, and trap gates.
- Baseline: platform gold-context passed, but the first pipeline-context output missed the visibility-vs-growth judgment and Adobe margin caveat.
- Decision label: diagnostic-only proceed.
- Mainline decision: accepted as the current reviewed9 case-filtered pipeline gate; still not full noisy benchmark approval.

## Runtime Efficiency
- Final cloud run timings: `load_model_sec=71.729`, `total_elapsed_sec=171.5188`, generation stage about `99.77` sec.
- Bottleneck: per-run resident vLLM load plus structured JSON decode over a long pipeline prompt.
- Next optimization: keep a resident service across multiple reviewed cases or batch case-filtered runs.

## Safety Notes
- No secrets are recorded.
- This is a case-filtered benchmark gate, not a production/full-benchmark result.
- The strict Adobe margin caveat was added because manual review found a real under-calibration issue not captured by the earlier rubric.
