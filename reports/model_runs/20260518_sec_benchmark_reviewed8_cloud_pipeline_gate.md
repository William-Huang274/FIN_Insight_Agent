# Model Run: 20260518_sec_benchmark_reviewed8_cloud_pipeline_gate

## Summary
- Purpose: Put the reviewed Cloud L4 diagnostic case into the real Qwen pipeline-context path, then rerun reviewed8 plus trap post-gates with `min_qwen_answer_ratio=1.0`.
- Status: diagnostic-only pass.
- Run type: inference + deterministic reprocess + evaluation gates.
- Timestamp: 2026-05-18.
- Environment: cloud RTX 4090 resident vLLM for Qwen3.5-9B; local deterministic reprocess and post-gates.

## Code And Command
- Entry points:
  - `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - `scripts/run_sec_benchmark_post_gates.py`
- Cloud command:
```bash
/root/miniconda3/bin/python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8 \
  --output-dir eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200_summaryshort \
  --mode pipeline_context \
  --case-id CLOUD_PROFITABILITY_2023_2025_DIAG_001 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json \
  --max-model-len 32768 \
  --max-tokens 4200 \
  --structured-json \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 1
```
- Final gate command:
```bash
python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_gold_reference_qwen9b_mixed \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260518_reviewed8_summaryshort_consistency_plus_traps_pipeline_gate_bundle \
  --output-dir reports/quality/local_reviewed8_summaryshort_consistency_plus_traps_pipeline_gate_bundle_post_gates \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json
```
- Key code changes:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`: summary-short contract for ledger cases.
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`: false-missing ledger consistency sanitizer for `not_found/limitations`.
  - `scripts/validate_sec_benchmark_ledger_missing_consistency.py`: standalone report gate for false-missing ledger contradictions.
  - `scripts/run_sec_benchmark_post_gates.py`: default integration for the ledger missing consistency gate.
- Seeds: vLLM default seed 0; decoding temperature 0.0.

## Inputs
- Cases: reviewed8 SEC benchmark non-trap set plus 2 anti-hallucination trap cases in the final bundle.
- Pipeline traces: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_context_traces_top8`.
- Gold reference: `eval/sec_cases/outputs/run_20260518_reviewed8_gold_reference_qwen9b_mixed`.
- Ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`, 35 rows.
- Abstract rubric: `eval/sec_cases/abstract_judgment_rubric_v0_1.json`.
- Leakage guard: case-filtered diagnostic run only; no expansion to noisy full benchmark.

## Model Parameters
- Model: Qwen3.5-9B from `data/models_private/modelscope/Qwen/Qwen3___5-9B`.
- Backend: resident vLLM structured JSON.
- `max_model_len`: 32768.
- `max_tokens`: 4200.
- `dtype`: float16.
- `gpu_memory_utilization`: 0.90.
- `max_num_seqs`: 1.
- `structured_json`: true.

## Outputs
- Failed diagnostic before prompt fix: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200`.
- Cloud raw Qwen run: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200_summaryshort`.
- Local consistency reprocess: `eval/sec_cases/outputs/run_20260518_reviewed8_pipeline_cloud_qwen9b_vllm_structured_4200_summaryshort_consistency`.
- Reviewed8 gold reference: `eval/sec_cases/outputs/run_20260518_reviewed8_gold_reference_qwen9b_mixed`.
- Reviewed8 plus trap bundle: `eval/sec_cases/outputs/run_20260518_reviewed8_summaryshort_consistency_plus_traps_pipeline_gate_bundle`.
- Post-gates: `reports/quality/local_reviewed8_summaryshort_consistency_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`.

## Results
- Cloud single-case raw run: `answer_status_counts={"answered_qwen9b": 1}`.
- Final bundle: `answer_status_counts={"answered_qwen9b": 8, "answered_contract_fallback": 2}`.
- True Qwen gate: `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0` for eligible non-trap outputs.
- Post-gates:
  - `trap_gate_pass=true`
  - `gold_vs_pipeline_pass=true`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `named_fact_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`
  - `ledger_unit_gate_pass=true`
- Abstract judgment: `checked_case_count=8`, `required_dimension_count=30`, `covered_required_dimension_count=30`.
- Answer ledger: `case_count=10`, `pass_count=10`, `exact_value_hit_count=31`, no failures.
- Named fact: `case_count=10`, `pass_count=8`, `skip_count=2`, `unsupported_token_count=0`.
- Ledger missing consistency: `case_count=10`, `pass_count=10`, `missing_statement_count=5`, `false_missing_statement_count=0`.

## Interpretation
- The first Cloud pipeline failure was JSON truncation, not a factual evidence failure: Qwen tried to enumerate too many exact values and long metric IDs inside `summary`.
- The summary-short contract fixed JSON conformance while preserving evidence support in `decision_drivers/key_points`.
- The model still produced one self-contradictory missing-evidence statement after valid JSON: it cited AWS/Google 2023 operating income metric IDs but also said those values were missing. The deterministic consistency sanitizer removed those false-missing claims and retained the real caveat that Microsoft Cloud operating income is missing.
- Manual review of the final Cloud answer: it covers AWS and Google Cloud revenue/operating income trends, treats Microsoft Cloud as broad revenue proxy plus gross-margin disclosure, and downgrades direct profitability comparison because operating-income scope is not comparable.

## Experiment Governance
- Hypothesis: A short-summary evidence contract plus deterministic ledger consistency check will let the Cloud L4 pipeline case pass as true Qwen output without ledger fallback.
- Decision target: reviewed8 non-trap eligible outputs must have `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, and all deterministic post-gates pass.
- Baseline: reviewed7 plus trap bundle passed; Cloud pipeline single-case failed before prompt fix with `finish_reason=length` and `answered_qwen9b_ledger_repair`.
- Stop conditions: any ledger repair, trap failure, answer-ledger failure, metric-role failure, named-fact failure, abstract-rubric failure, or qwen ratio below 1.0 blocks promotion.
- Decision label: diagnostic-only proceed.
- Mainline decision: accepted as the current case-filtered SEC benchmark pipeline gate; not promoted to full benchmark.

## Runtime Efficiency
- Cloud raw run timings: `load_model_sec=75.1668`, `total_elapsed_sec=240.4659`.
- Output decode was slow but acceptable for a single-case diagnostic on RTX 4090.
- Bottleneck: resident vLLM model load and structured JSON decode for long evidence prompt.
- Next optimization: keep resident process for multi-case runs or batch case-filtered reviewed cases; do not use per-case HF loading for larger slices.

## Safety Notes
- No secrets are recorded here.
- The final bundle still includes 2 trap cases through explicit contract fallback; trap fallback is excluded from true-Qwen eligible ratio.
- The false-missing sanitizer is narrow and deterministic. It removes only missing/caveat statements that contradict a current-case ledger row by ticker, year, and metric family.
- Next step should be another reviewed diagnostic case rather than immediate noisy full-set expansion. The explicit ledger/not_found consistency report gate is now active in post-gates.
