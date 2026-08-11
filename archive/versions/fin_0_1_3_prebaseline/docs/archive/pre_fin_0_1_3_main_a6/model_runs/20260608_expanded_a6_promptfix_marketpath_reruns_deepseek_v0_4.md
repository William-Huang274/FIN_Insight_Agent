# Model Run: 20260608_expanded_a6_promptfix_marketpath_reruns_deepseek_v0_4

## Summary

- Purpose: Validate A6 prompt/memo retry fixes and corrected market evidence path before deciding whether to broaden to remaining A6 cases.
- Status: diagnostic fail; standard/scope/exact are green, sector-depth misses the latency gate by `469 ms`.
- Run type: inference smoke + runtime/performance gate validation.
- Timestamp: 2026-06-08.
- Environment: cloud workspace `/autodl-fs/data/fin_agent_milvus_bge_m3`; resident MCP worker on `http://127.0.0.1:8765`; DeepSeek credentials supplied only through transient environment.

## Code And Command

- Workbench wrapper: `scripts/workbench/run_expanded_a6_eval.py`.
- Chain runner: `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Main 4-case run ID: `20260608_expanded_a6_multi_query_milvus_full_chain_smoke_promptfix_v0_3`.
- Failed2 rerun ID: `20260608_expanded_a6_failed2_marketpath_hotfix_resident_warm_smoke_v0_4`.
- v0_3 summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_multi_query_milvus_full_chain_smoke_promptfix_v0_3_summary.json`.
- v0_4 summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_failed2_marketpath_hotfix_resident_warm_smoke_v0_4_summary.json`.

## Inputs

- Case set: A6 smoke slice; v0_4 reran only failed `standard_memo` and `sector_depth`.
- SEC evidence manifest: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`.
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`.
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`.
- Combined ledger: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/indexes/ledger/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`.
- Market evidence pack: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/market/processed/evidence_packs/20260606_market_yahoo_chart_tier1_tier2_1y_v0_1_3m_market_evidence.jsonl`.
- Industry rows: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/industry/processed/20260606_industry_fred_eia_tier1_tier2_merged_v0_1/industry_evidence_rows.jsonl`.
- Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`.
- Milvus collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`.

## Results

v0_3 full 4-case:

- Status: `fail`, `2/4` pass.
- Total LLM tokens: `166154`; previous postfix run was `206678`.
- Max case elapsed: `297621 ms`.
- Scope/gap contract failures: `0`.
- `fin_full_scope_nvda_basic_fundamental_zh`: pass, `131362 ms`, Memo Writer `1` call / `8668` tokens.
- Remaining v0_3 failures: standard performance and sector market rows / real-evidence quality, caused by wrong market path.

v0_4 failed2 rerun:

- Status: `fail`, `1/2` pass.
- Total LLM tokens: `127024`.
- `fin_full_standard_nvda_amd_market_zh`: pass, `100724 ms`, false checks `{}`.
- `fin_full_sector_ai_infra_depth_zh`: fail only `performance.case_elapsed_ms_lte`, `300469 ms` vs `300000 ms`.
- Real retrieval required: `1`; real Specialist quality passed `1/1`.

## Runtime Efficiency

- Resident worker PID after restart: `20805`.
- Milvus/BGE warmup:
  - Cold semantic warmup: `223602 ms`, cache `1/1`.
  - Hot repeat: `1648 ms`.
- v0_4 resident worker health after run: request_count `13`, Milvus embedding/client cache `1/1`, SEC search cache `6`.
- Remaining latency is primarily LLM sequencing and one-time SEC/reranker cold load if not prewarmed, not Milvus hot search.

## Repair Trace

- Standard case: Research Lead first attempt failed `required_agent_missing: coverage_reflection`, repaired on second call.
- Sector-depth:
  - Research Lead first attempt had `finish_reason=length` and `model_output_truncated`, repaired on second call.
  - Universe first attempt failed economic-link evidence-ref validation for sector-depth pack refs, repaired on second call.
- Memo Writer repair attempts: `0` in scope, standard, and sector after direct-answer label sanitization.

## Decision

- Do not promote A6 or run the remaining cases as a quality gate yet.
- A low-concurrency remaining-case run can be used as a pressure diagnostic only.
- Next optimization should target Research Lead deep output length, Universe sector-depth pack ref normalization, and canonical market-path/profile wiring.

## Safety

- No API key, cloud password, raw LLM response, or temporary credential was saved in repository artifacts.
