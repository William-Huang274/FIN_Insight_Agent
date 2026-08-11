# SEC Benchmark v1.1 reviewed3 BGE-M3 Audit

Date: 2026-05-19

## Scope

本轮目标是把 v1.1 第三个 reviewed case 收进当前 pipeline，并确认 `pipeline_context` 继续固定走 BGE-M3 final selector，而不是回退为 BM25-only。

新增 reviewed case:

- `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
- Companies: ADBE, SNOW, PANW
- Years: 2023, 2024, 2025
- Reviewed numeric facts: 9
- Reviewed text context rows: 18

本轮不声称 full noisy benchmark 或 v2 泛化结论；这是 v1.1 reviewed3 case-filtered diagnostic pass。

## BGE-M3 Lock

代码侧已固定:

- `scripts/run_sec_benchmark_eval.py` 默认 `--context-reranker bge`
- 默认模型: `BAAI/bge-reranker-v2-m3`
- `pipeline_context + --context-reranker none` 会直接报错；只有显式加 `--allow-bm25-only-pipeline` 才允许 BM25-only ablation。

云端 policy check:

- Command object: `pipeline_context --context-reranker none`
- Result: blocked with `ValueError: pipeline_context now requires BGE reranking by default`
- Decision: BM25/ObjectBM25/requirement BM25 只保留为 first-stage candidate generators；BGE-M3 是 final context selector。

## Artifacts

Reviewed gold artifacts:

- `eval/sec_cases/reviewed_gold_context/SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001.jsonl`
- `eval/sec_cases/reviewed_gold_facts/SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001.json`
- `reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json`

Deterministic validation:

- `reports/quality/sec_benchmark_v1_1_gold_gate_reviewed3_semiconductor_capex_subscription.json`
- `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- `reports/quality/sec_benchmark_v1_1_reviewed3_ledger_unit_gate.json`
- `reports/quality/sec_benchmark_v1_1_reviewed3_derived_metric_gate.json`

BGE trace:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_context_bge_m3_top120_local`

Clean true-Qwen output:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090_sanitized`

Clean post-gates:

- `reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates/sec_benchmark_post_gates_summary.json`
- `reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates/sec_benchmark_derived_metric_gate.json`

Superseded output:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090`
- Reason: first synthesis had a CAPEX table-case false missing statement in `limitations`; do not use for promotion.

## Results

Reviewed gold gates:

- Gold gate: 3/3 pass, `can_enter_gate=true`
- Exact-value ledger: 51 rows
- Ledger unit gate: 51/51 pass
- CAPEX/FCF derived metric gate: 12/12 pass

BGE-M3 trace:

- Trace count: 3
- Status: 3/3 `context_prepared`
- Context rows: 120 per case
- `effective_context_reranker=bge`
- `context_reranker_model=BAAI/bge-reranker-v2-m3`
- `bm25_only_allowed_for_this_run=false`

Subscription trace spot-check:

- ADBE subscription revenue values `18,284 / 20,521 / 22,904` appear in BGE-selected rows, including ranks 22 and 24 for the 2025 comparative rows.
- SNOW product revenue evidence appears in selected rows, with `Product revenue` table/context hits at ranks 10, 37, 41, 45, and 69.
- PANW subscription/support revenue evidence appears strongly, with `Subscription and support` table/object hits at ranks 6, 7, 9, 11, 12, 13, 17, and 19.

RTX 5090 true-Qwen synthesis:

- Output: `run_20260519_v1_1_reviewed3_pipeline_bge_m3_qwen9b_vllm_5090_sanitized`
- Answer status: `answered_qwen9b=3`
- Fallback answers: 0
- Ledger repairs: 0
- Total elapsed: 211.9695 sec
- Model load: 41.3767 sec
- Hardware profile: `rtx5090_32gb`
- Runtime env applied: `TORCHDYNAMO_DISABLE=1`, `VLLM_USE_FLASHINFER_SAMPLER=0`

Post-gates on clean output:

- `qwen_answer_ratio=1.0`
- `answer_ledger_gate_pass=true`, 3/3 pass, exact-value hits 10
- `metric_role_term_gate_pass=true`, 3/3 pass
- `table_cell_gate_pass=true`, 36/36 valid cells
- `named_fact_gate_pass=true`, unsupported named tokens 0
- `ledger_missing_consistency_gate_pass=true`, false missing statements 0
- `ledger_unit_gate_pass=true`, 51/51 pass
- `abstract_judgment_gate_pass=true`, but 3/3 skipped because these v1.1 cases do not yet have abstract rubrics
- CAPEX/FCF derived metric gate: 12/12 pass

Skipped by design:

- Trap gate: skipped because this was a three-case non-trap run.
- Gold-vs-pipeline gate: skipped because gold and pipeline dirs intentionally point to the same case-filtered run.
- Answer-vs-Judgment-Plan gate: skipped because v1.1 reviewed3 does not yet have Judgment Plans.

## Bug Fixed During Audit

The first true-Qwen output passed the old post-gates but inspection found a wrong CAPEX table limitation:

- It said GOOGL/META/AMZN 2024/2025 complete data were missing.
- `cell_table.cells` actually contained the full 36 reviewed cells.

Root cause:

- `validate_sec_benchmark_ledger_missing_consistency.py` did not treat `缺少` as a missing marker.
- The validator also did not catch generic `完整数据` false-missing statements when the text omitted a metric-family alias.
- Table-case backend canonicalization appended a safe note but kept model-written stale `limitations`.

Fix:

- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - table-case canonicalization now replaces `limitations` with the canonical table note only.
  - false-missing sanitizer recognizes `缺少` and generic `完整数据` contradictions.
- `scripts/validate_sec_benchmark_ledger_missing_consistency.py`
  - added the same `缺少` and `完整数据` detection.

Proof:

- Old output recheck after validator patch:
  - `reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_post_gates/sec_benchmark_ledger_missing_consistency_gate_after_patch_check.json`
  - `can_enter_gate=false`
  - fail case: `CAPEX_FCF_TABLE_2023_2025_DIAG_001`
- Clean output after backend patch:
  - `reports/quality/local_v1_1_reviewed3_pipeline_bge_m3_qwen9b_5090_sanitized_post_gates/sec_benchmark_ledger_missing_consistency_gate_local_recheck.json`
  - `can_enter_gate=true`
  - false missing statements: 0

## Decision

Current decision: diagnostic-only pass.

The BGE-M3 reranker path is now fixed and validated for v1.1 reviewed3. The clean run is suitable as the current continuation point for Answer Plan / broader generalization work, with the caveat that this remains a case-filtered benchmark run rather than a full noisy benchmark.

Next work should not switch back to BM25-only unless explicitly marked as an ablation with `--allow-bm25-only-pipeline`.

## Next Step

Recommended next sequence:

1. Add the fourth v1.1 reviewed case: `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`.
2. Before larger v2 expansion, add at least the two v2-critical validators:
   - required-caveat coverage gate
   - disallowed-claim violation gate
3. After four v1.1 cases pass, build a small v2 pilot manifest instead of jumping directly to 40 cases.
