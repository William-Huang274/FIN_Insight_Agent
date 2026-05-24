# Model Run: 20260519_sec_benchmark_reviewed10_pipeline_table_bundle_gate

## Summary
- Purpose: 将 reviewed10 表格 case 跑通 pipeline-context true-Qwen，并把结果合入 reviewed10 + 2 trap bundle，验证 table-cell contract、Judgment Plan gate 和现有 post-gates 是否能一起通过。
- Status: diagnostic-only completed
- Run type: retrieval trace + cloud inference + deterministic post-gates
- Timestamp: 2026-05-19
- Environment: local Windows workspace `D:\FIN_Insight_Agent` plus cloud RTX 4090 repo `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command
- Git commit: `820df59`
- Dirty files: 当前工作区已有大量未提交实验产物；本轮涉及 SEC benchmark table synthesis schema、Qwen backend prompt/normalization、table-cell validator、post-gate integration、reviewed10 outputs 和 worklog。
- Main commands:

```bash
python scripts/run_sec_benchmark_eval.py \
  --mode pipeline_context \
  --output-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20 \
  --case-id REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001 \
  --evidence-top-k 20 \
  --object-top-k 20

python scripts/run_sec_benchmark_vllm_synthesis_from_traces.py \
  --trace-run-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20 \
  --output-dir eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids \
  --case-id REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001 \
  --model-path data/models_private/modelscope/Qwen/Qwen3___5-9B \
  --max-model-len 32768 \
  --max-tokens 6000 \
  --structured-json

python scripts/run_sec_benchmark_post_gates.py \
  --gold-run-dir eval/sec_cases/outputs/run_20260519_reviewed10_gold_reference_qwen9b_mixed \
  --pipeline-run-dir eval/sec_cases/outputs/run_20260519_reviewed10_judgment_plan_table_plus_traps_pipeline_gate_bundle \
  --output-dir reports/quality/local_reviewed10_judgment_plan_table_plus_traps_pipeline_gate_bundle_post_gates \
  --min-qwen-answer-ratio 1.0 \
  --ledger-path reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json \
  --judgment-plan-path reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json
```

## Inputs
- Case: `REVENUE_INCOME_CFO_TABLE_2023_2025_DIAG_001`
- Pipeline trace: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_context_traces_top20`
- Reviewed ledger: `reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json`
- Judgment Plan seed: `reports/evidence_packs/sec_benchmark_v1_reviewed_complex2_judgment_plans_seed.json`
- Base reviewed9 bundle: `eval/sec_cases/outputs/run_20260519_reviewed9_judgment_plan_plus_traps_pipeline_gate_bundle`

## Outputs
- Pipeline true-Qwen table run: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_pipeline_qwen9b_vllm_structured_6000_table_metricids`
- Gold-context true-Qwen table run: `eval/sec_cases/outputs/run_20260519_revenue_income_cfo_gold_context_qwen9b_vllm_structured_6000_table_metricids`
- Reviewed10 gold reference bundle: `eval/sec_cases/outputs/run_20260519_reviewed10_gold_reference_qwen9b_mixed`
- Reviewed10 + 2 trap pipeline bundle: `eval/sec_cases/outputs/run_20260519_reviewed10_judgment_plan_table_plus_traps_pipeline_gate_bundle`
- Single-case post-gates: `reports/quality/local_reviewed10_revenue_table_pipeline_qwen9b_post_gates/sec_benchmark_post_gates_summary.json`
- Gold-vs-pipeline single-case gates: `reports/quality/local_reviewed10_revenue_table_gold_vs_pipeline_qwen9b_post_gates/sec_benchmark_post_gates_summary.json`
- Full bundle post-gates: `reports/quality/local_reviewed10_judgment_plan_table_plus_traps_pipeline_gate_bundle_post_gates/sec_benchmark_post_gates_summary.json`

## Results
- Top8 pipeline trace missed one Microsoft cash-flow source; top20 trace reached full source coverage for all 48 reviewed table cells.
- Compact table schema solved raw JSON truncation: true Qwen returned `answer_status=answered_qwen9b`, parsed JSON, `finish_reason=stop`, and normalized `cell_table` expanded to 48/48 ledger cells.
- Single table pipeline gates passed: answer ledger, metric-role term, table-cell, named-fact, ledger-missing consistency, abstract judgment skip/pass, and ledger-unit all passed.
- Single table gold-vs-pipeline gate passed.
- Reviewed10 + 2 trap bundle passed all configured post-gates:
  - `trap_gate_pass=true`
  - `gold_vs_pipeline_pass=true`
  - `answer_ledger_gate_pass=true`
  - `metric_role_term_gate_pass=true`
  - `table_cell_gate_pass=true`, `expected_cell_count=48`, `reported_cell_count=48`, `valid_cell_count=48`
  - `named_fact_gate_pass=true`, `unsupported_token_count=0`
  - `ledger_missing_consistency_gate_pass=true`
  - `abstract_judgment_gate_pass=true`, `covered_required_dimension_count=37/37`
  - `answer_vs_judgment_plan_gate_pass=true`, checked 2 complex planned cases
  - `ledger_unit_gate_pass=true`, `pass_count=98/98`
  - `qwen_answer_ratio=1.0`, `qwen_ledger_repaired=0`, `fallback_answered=0`

## Experiment Governance
- Hypothesis: reviewed10 table case can be made pipeline-compatible by treating table output as a compact metric-id cell contract, then deterministically expanding cells from the reviewed ledger.
- Decision target: true Qwen table output parses without fallback, table-cell gate validates 48/48 cells, and reviewed10 + 2 trap bundle keeps all existing post-gates green.
- Ceiling / upper bound: This is still case-filtered diagnostic evidence. It proves the reviewed10 boundary, not full noisy benchmark generalization.
- Baselines to beat: earlier table synthesis attempts with full duplicated cell payloads hit `finish_reason=length` and required repair/fallback behavior.
- Split and leakage guard: Uses reviewed gold facts/context and pipeline trace artifacts already in repo/cloud. No new external data or credentials are written.
- Decision label: diagnostic-only proceed to expanded reviewed gold cases.
- Mainline decision: reviewed10 SEC benchmark path is now the current case-filtered gate baseline; next promotion requires new reviewed cases and separate gates.

## Runtime Efficiency
- Pipeline true-Qwen table run: model load `61.6672s`, total elapsed `190.0554s`.
- Gold true-Qwen table run: model load `67.3577s`, total elapsed `206.0773s`.
- Runtime bottleneck: long structured JSON output for large table cells; compact `metric_id + status` table schema reduces output pressure and avoids truncation.
- Serving implication: table answers should keep model output compact and let deterministic ledger expansion fill canonical values/citations.

## Caveats And Next Step
- Not run: no full noisy benchmark, no new model training, no BGE/verifier reranker ablation in this run.
- Known risks: table-cell contract currently covers the reviewed consolidated metric table case; capex/FCF derived-cell tables and NA-heavy tables need separate reviewed cases.
- Next decision: expand reviewed gold set before claiming generalization. Priority candidates are semiconductor durability, capex/FCF table, SaaS/security subscription visibility, and ads/AI infrastructure growth-quality comparison.
