# SEC Benchmark v1.1 reviewed4 ADS/BGE-M3 Audit

Date: 2026-05-19

## Scope

本轮目标是把第四个 v1.1 reviewed case 收进当前 pipeline，并继续固定 `pipeline_context` 的 final selector 为 BGE-M3，而不是 BM25-only。

新增 reviewed case:

- `ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001`
- Companies: GOOGL, META
- Years: 2023, 2024, 2025
- Reviewed numeric facts: 18
- Reviewed text context rows: AI/technical infrastructure investment caveat, capex attribution caveat, operating leverage/cost pressure caveat

本轮仍是 case-filtered diagnostic pass，不是 full noisy benchmark，也不是 v2 泛化结论。

## BGE-M3 Lock

当前 pipeline-context policy:

- BM25 / ObjectBM25 / requirement BM25 只作为 candidate generators。
- `BAAI/bge-reranker-v2-m3` 是 final context selector。
- `pipeline_context + --context-reranker none` 仍要求显式 `--allow-bm25-only-pipeline`，否则不可作为主线。

本轮最终 trace:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_context_bge_m3_top160_object8_local`
- `trace_count=4`
- `status_counts.context_prepared=4`
- `max_context_rows=160`
- `object_top_k=8`
- `context_reranker_top_k=160`
- `effective_context_reranker=bge`
- `context_reranker_model=BAAI/bge-reranker-v2-m3`
- `bm25_only_allowed_for_this_run=false`

ADS trace spot-check:

- 18/18 ADS target values appear in the BGE-selected context pack after numeric-object query expansion.
- The previously missing GOOGL 2025 advertising revenue value `294,691` is now present.
- Selected context includes GOOGL/META advertising revenue, operating income, capex/PPE purchase rows, plus AI infrastructure and attribution caveats.

## Artifacts

Reviewed gold artifacts:

- `eval/sec_cases/reviewed_gold_context/ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001.jsonl`
- `eval/sec_cases/reviewed_gold_facts/ADS_AI_INFRA_GROWTH_QUALITY_2023_2025_DIAG_001.json`
- `reports/quality/sec_benchmark_v1_1_reviewed_gold_partial_approval.json`

Deterministic reviewed4 validation:

- `reports/quality/sec_benchmark_v1_1_gold_gate_reviewed4_semiconductor_capex_subscription_ads_ai_infra.json`
- `reports/exact_value_ledgers/sec_benchmark_v1_1_reviewed_exact_value_ledger.json`
- `reports/quality/sec_benchmark_v1_1_reviewed4_ledger_unit_gate.json`
- `reports/quality/sec_benchmark_v1_1_reviewed4_derived_metric_gate.json`

Final clean true-Qwen output:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_displayfix`

Final clean post-gates:

- `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_qwen9b_5090_sanitized_displayfix_post_gates/sec_benchmark_post_gates_summary.json`
- `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_qwen9b_5090_sanitized_displayfix_post_gates/sec_benchmark_derived_metric_gate.json`

Answer/Judgment Plan artifacts:

- Trace-aware plan seed: `reports/evidence_packs/sec_benchmark_v1_1_reviewed4_judgment_plans_trace_seed.json`
- Plan validation: `reports/quality/sec_benchmark_v1_1_reviewed4_judgment_plan_trace_validation.json`
- Plan-injected true-Qwen output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090_sanitized`
- Final planfix output: `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_vllm_5090_planfix`
- Final planfix post-gates: `reports/quality/local_v1_1_reviewed4_pipeline_bge_m3_judgment_plan_trace_seed_qwen9b_5090_planfix_post_gates/sec_benchmark_post_gates_summary.json`
- Direct answer-vs-plan gate: `reports/quality/sec_benchmark_v1_1_reviewed4_answer_vs_judgment_plan_trace_seed_qwen9b_5090_planfix.json`

Intermediate clean namedfix output:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_namedfix`
- Reason superseded by displayfix: all deterministic gates passed, but one ADS key point had nested parentheses around negative capex display values. The displayfix output applies deterministic prose cleanup without rerunning the model.

Superseded output:

- `eval/sec_cases/outputs/run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized`
- Reason: first reviewed4 synthesis answered 4/4, but named-fact gate failed on subscription case because model introduced unsupported `NRR` / `Evidence Text` tokens. Do not use this run for promotion.

## Results

Reviewed gold gates:

- Gold gate: 4/4 pass, `can_enter_gate=true`
- Exact-value ledger: 69 rows
- Ledger unit gate: 69/69 pass
- CAPEX/FCF derived metric gate: 12/12 pass

RTX 5090 true-Qwen synthesis:

- Output: `run_20260519_v1_1_reviewed4_pipeline_bge_m3_qwen9b_vllm_5090_sanitized_displayfix`
- Answer status: `answered_qwen9b=4`
- Fallback answers: 0
- Ledger repairs: 0
- Total elapsed: 292.8049 sec
- Model load: 32.0934 sec
- Hardware profile: `rtx5090_32gb`
- Runtime env applied: `TORCHDYNAMO_DISABLE=1`, `VLLM_USE_FLASHINFER_SAMPLER=0`
- GPU KV cache size: 342,528 tokens
- Available KV cache memory: 10.78 GiB

Per-case synthesis:

- Semiconductor durability: 52.4232 sec, score 8.8
- CAPEX/FCF table: 76.0179 sec, score 8.8
- Subscription visibility: 70.27 sec, score 8.8
- ADS/AI infrastructure: 61.9382 sec, score 8.8

Post-gates on final displayfix output:

- `qwen_answer_ratio=1.0`
- `answer_ledger_gate_pass=true`, 4/4 pass, exact-value hits 18
- `metric_role_term_gate_pass=true`, 4/4 pass
- `table_cell_gate_pass=true`, 36/36 valid cells
- `named_fact_gate_pass=true`, unsupported named tokens 0
- `ledger_missing_consistency_gate_pass=true`, false missing statements 0
- `ledger_unit_gate_pass=true`, 69/69 pass
- `abstract_judgment_gate_pass=true`, but 4/4 skipped because these v1.1 cases do not yet have abstract rubrics
- CAPEX/FCF derived metric gate: 12/12 pass

Skipped by design for the displayfix baseline:

- Trap gate: skipped because this was a four-case non-trap run.
- Gold-vs-pipeline gate: skipped because gold and pipeline dirs intentionally point to the same case-filtered run.
- Answer-vs-Judgment-Plan gate: skipped only for the displayfix baseline; the later planfix run below enables and passes this gate.

## Bug Fixed During Audit

The first reviewed4 true-Qwen output failed named-fact gate:

- Failure case: `SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001`
- Unsupported tokens: `NRR`, `Evidence Text`
- Root cause: the model wrote an unsupported Snowflake NRR trend in a caveat, and copied the prompt label `Evidence Text` into final prose.

Fix:

- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - prompt now explicitly says named products, KPIs, acronyms, and English labels must be supported by current cited evidence or ledger.
  - normalize stage now runs a named-fact sanitizer using the same support logic as the named-fact gate.
  - unsupported named facts are deleted or generalized rather than allowing them into final prose.
- `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py`
  - resident-vLLM system prompt carries the same named-fact constraint.
  - score notes now record `named_fact_contract_sanitized_count`.

Proof:

- Failed first run post-gate:
  - `named_fact_gate_pass=false`
  - unsupported token count: 2
- Final namedfix run post-gate:
  - `named_fact_gate_pass=true`
  - unsupported token count: 0
- Subscription final score notes:
  - `ledger_text_contract_sanitized_count:6`
  - `named_fact_contract_sanitized_count:4`

## ADS Output Audit

ADS case final answer covers the intended axes:

- Advertising revenue growth for GOOGL and META.
- Operating income / operating leverage comparison.
- Capex / technical infrastructure pressure.
- Caveat that SEC evidence does not allow attributing all capex to advertising growth or quantifying AI's exact contribution.

Presentation fix:

- The intermediate namedfix output had nested parentheses around negative capex values, for example `( ( 27,045 )（百万美元） (metric_id) )（百万美元）`.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py` now canonicalizes already ledger-bound display prose after `_canonicalize_ledger_value_support`.
- Final displayfix output rewrites this to `( 27,045 )（百万美元） (metric_id)` and preserves ledger metric-id support.
- Displayfix post-gates remain clean: answer-ledger 4/4, named-fact unsupported tokens 0, ledger-unit 69/69, table-cell 36/36, derived FCF 12/12.

## Answer/Judgment Plan Follow-Up

Initial diagnosis:

- The ledger-only reviewed4 Judgment Plan seed passed plan gate, but existing displayfix answers failed answer-vs-plan 0/4 because the seed was too narrow: it only grouped ledger rows by ticker and did not plan qualitative SEC evidence such as segment comparability, export/supply-chain risk, consumption/subscription caveats, technical-infrastructure capex caveats, or Reality Labs profitability caveats.
- A plan-injected RTX 5090 true-Qwen rerun answered 4/4, but still failed the ledger-only answer-vs-plan gate because prompt injection alone did not force all driver evidence and proxy strength to stay inside the plan.

Fix:

- `scripts/validate_sec_benchmark_judgment_plan.py` now allows supporting evidence IDs from either the reviewed ledger or the current BGE-M3 trace. This is required because Judgment Plans must cover qualitative evidence, not just exact-value source rows.
- `scripts/build_sec_benchmark_judgment_plan.py` now accepts `--trace-run-dir` and builds trace-aware plan seeds. For ADS and semiconductor peer-comparison cases it creates task-aware drivers; for other cases it enriches ticker drivers with trace evidence from the BGE-M3 context pack.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py` and `scripts/run_sec_benchmark_vllm_synthesis_from_traces.py` now pass the active Judgment Plan into normalization. Table cases with a plan bind their prose drivers to plan drivers so proxy FCF rows do not get promoted into generic `strong` prose.
- Follow-up tightening completed: trace-aware plan evidence selection no longer carries a broad top-trace fallback. ADS, semiconductor, and generic ticker drivers now use bounded criterion/topic term matching; generated answer drivers and key_points are clamped back to the matched plan driver support IDs, strength, and caveats. Auto-added ledger boundary key_points cite only the selected metrics' ledger source evidence.

Final planfix result:

- Plan seed: 4/4 pass, 12 drivers, `can_enter_gate=true`
- Plan validation warnings: 8 `supporting_evidence_id_not_seen_in_trace` warnings remain; these are reviewed-ledger source evidence IDs accepted by the validator, not broad trace expansion.
- Plan-injected true-Qwen run: 4/4 `answered_qwen9b`
- Planfix post-gates:
  - `qwen_answer_ratio=1.0`
  - `answer_vs_judgment_plan_gate_pass=true`, 4/4 pass
  - `answer_ledger_gate_pass=true`, 4/4 pass, exact-value hits 20
  - `metric_role_term_gate_pass=true`, 4/4 pass
  - `table_cell_gate_pass=true`, 36/36 valid cells
  - `named_fact_gate_pass=true`, unsupported named tokens 0, warning count 0
  - `ledger_missing_consistency_gate_pass=true`, false missing statements 0
  - `ledger_unit_gate_pass=true`, 69/69 pass
  - CAPEX/FCF derived metric gate: 12/12 pass

Support-scope audit:

- Broad trace evidence stuffing was removed from the plan builder.
- Replayed planfix output remains 4/4 `answered_qwen9b`.
- Post-clamp support sizes are bounded in the final answers: semiconductor driver evidence counts 3/3, subscription 2/3/2, ADS 2/1/2, and auto-added ledger key_points no longer carry 19-20 evidence IDs.

## Decision

Current decision: diagnostic-only pass.

The BGE-M3 reranker path is validated for v1.1 reviewed4 under the current gates. The final planfix output is the better continuation point for Answer/Judgment Plan work; the displayfix output remains the clean no-plan baseline.

- This remains a four-case reviewed diagnostic run, not a full noisy benchmark or v2 generalization result.

## Next Step

Recommended next sequence:

1. Start Answer Plan on the reviewed4 BGE-M3 path rather than switching retrieval back to BM25-only.
2. Before v2 pilot, add required-caveat and disallowed-claim validators.
3. Then create a small v2 pilot manifest with representative generalization cases rather than jumping directly to 40 cases.
