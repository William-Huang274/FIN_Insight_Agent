# SEC Benchmark v2 Pilot Plus4 AMZN BGE-M3 Qwen9B 5090 Audit

## Summary

Date: 2026-05-19 / 2026-05-20 Asia/Shanghai

This entry closes the v2 pilot plus4 run. The run kept BGE-M3 as the fixed
pipeline-context final selector over BM25/ObjectBM25 candidates, added the AMZN
AWS numeric case into the active pipeline batch, built a trace-aware Judgment
Plan, ran RTX 5090 resident Qwen3.5-9B synthesis, and passed final deterministic
post-gates after tightening two v2 semantic validator false positives.

The result is diagnostic-only. It supports continuing staged v2 expansion, but
it is not a full v2 benchmark or full noisy-benchmark claim.

## Governance

- Hypothesis: the plus3 BGE-M3 + Judgment Plan + Qwen9B path should survive the
  AMZN AWS numeric case without falling back to BM25-only or contract fallback
  on non-trap cases.
- Decision target: nine reviewed non-trap outputs must be true Qwen answers and
  all active post-gates must pass; the YouTube wrong-attribution trap must pass
  refusal smoke.
- Ceiling: plus4 diagnostic only; no full v2 benchmark claim and no gold-context
  Qwen synthesis claim.
- Stop condition: any non-trap fallback, ledger repair, semantic-contract hard
  failure, caveat/claim violation, answer-vs-plan failure, or metric-source
  grounding failure blocks the next expansion.
- Decision label: diagnostic-only proceed.

## Inputs

- Cases: `eval/sec_cases/test_cases_v2_pilot_plus4_seed.jsonl`
- New reviewed case: `AMZN_AWS_NUMERIC_2023_2025_001`
- Exact-value ledger:
  `reports/exact_value_ledgers/sec_benchmark_v2_pilot_plus4_reviewed_exact_value_ledger.json`
- BGE-M3 local model path on remote:
  `/root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3`
- Remote environment:
  `/root/autodl-tmp/FIN_Insight_Agent` on single RTX 5090 32GB
- Hardware profile: `rtx5090_32gb`

## Work Completed

- Synced plus4 scripts, manifests, reviewed gold context/facts, quality reports,
  and ledger files to the remote 5090 workspace.
- Created a remote backup before sync:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_backups/20260519_v2_pilot_plus4_sync_before_qwen_235810.tgz`
- Re-ran plus4 deterministic gates on remote:
  - readiness 10/10
  - reviewed-gold mainline 9/9
  - trap smoke 1 pass, 9 skipped
  - exact-value ledger 86 rows
  - ledger-unit 86/86
- Generated BGE-M3 pipeline-context trace:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_context_bge_m3_top160_object8_local`
- Built and gated trace-aware Judgment Plan:
  `reports/evidence_packs/sec_benchmark_v2_pilot_plus4_judgment_plans_trace_seed.json`
- Ran RTX 5090 true-Qwen synthesis:
  `eval/sec_cases/outputs/run_20260519_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_vllm_5090`
- Ran final post-gates:
  `reports/quality/local_v2_pilot_plus4_pipeline_bge_m3_judgment_plan_qwen9b_5090_semanticfix2_post_gates/sec_benchmark_post_gates_summary.json`

## Results

- BGE trace: 10/10 `context_prepared`.
- BGE policy:
  - final selector: BGE-M3
  - candidate generators: `evidence_bm25`, `object_bm25`, `requirement_bm25`
  - `bm25_only_allowed_for_this_run=false`
- Judgment Plan: 9 plans, 12 drivers, 1 proxy driver, 2 plans with downgrades,
  0 skipped; gate 9/9 pass.
- Qwen synthesis:
  - `answered_qwen9b`: 9
  - `answered_contract_fallback`: 1 trap
  - `qwen_answer_ratio=1.0`
  - no Qwen ledger repairs
- Final post-gates:
  - trap: pass
  - answer-ledger: pass, 45 exact-value hits
  - metric-role term: pass
  - table-cell: pass, 12/12 valid AAPL cells
  - named-fact: pass, unsupported token count 0
  - ledger-missing consistency: pass
  - abstract judgment: pass
  - caveat/claim: pass, 22/22 required caveats, 0/24 disallowed violations
  - v2 semantic contract: pass, 9/9 checked cases
  - answer-vs-Judgment-Plan: pass, 9/9 checked cases
  - metric-source grounding: pass, 36 checked locations and 138 metric refs
  - ledger-unit: pass, 86/86
  - gold-vs-pipeline: skipped by design because this is pipeline-context only

## Deterministic Validator Cleanup

The first post-gate pass surfaced two v2 semantic false positives:

- ADBE: percentage-rate metrics were flagged because the same sentence also
  contained a total-value dollar amount.
- PANW: a sentence saying RPO/billings must be strictly separated from
  recognized revenue was flagged as if RPO was treated as revenue.

`scripts/validate_sec_benchmark_v2_semantic_contracts.py` was tightened so the
percentage-rate check uses text local to the percentage metric ID, the
visibility-metric revenue check targets explicit recognized/direct-revenue
language, and Chinese/English separation caveats count as proxy caveats. Qwen
was not rerun; only deterministic post-gates were rerun.

## Runtime Notes

- The first BGE-M3 attempt failed because the remote host could not reach
  Hugging Face. The successful run used the existing local ModelScope cache.
- Qwen model load: 39.354 sec.
- Qwen synthesis elapsed: 473.2397 sec.
- GPU memory during Qwen: about 30.5 GiB on RTX 5090 32GB.
- Remote script wall time: about 8.7 minutes from deterministic gate start to
  post-gate completion.
- A Windows-line-ending artifact in the temporary remote launch script caused a
  harmless post-`done` status failure after reports had already been written;
  the remote status file was corrected.

## Decision

Plus4 passes as a staged diagnostic expansion. AMZN AWS did not introduce a
post-gate failure, and BGE-M3 remains the final context selector rather than a
BM25-only route.

Proceed to build
`AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001` from the reviewed
cloud-profitability AMZN/GOOGL subset before the next pipeline-context Qwen run.

## Safety Notes

- No password, private token, or temporary credential was written to project
  logs.
- The historical RTX 4090 profile was not deleted or overwritten.
- The initial failed post-gate directory is preserved separately from the final
  `semanticfix2_post_gates` directory for auditability.
