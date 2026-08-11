# Model Run: 20260608_expanded_a6_4case_prewarm_device_fixed_deepseek_v0_5

## Summary

- Purpose: Validate the expanded A6 4-case full-chain smoke after deterministic exact lookup bypass, resident SEC/Milvus cache fixes, Milvus collection/embedding wiring, and SEC prewarm device fix.
- Status: accepted 4-case A6 smoke diagnostic; not yet expanded full-chain promotion.
- Run type: inference smoke + retrieval/operator runtime validation.
- Timestamp: 2026-06-08.
- Environment: cloud workspace `/autodl-fs/data/fin_agent_milvus_bge_m3`; resident MCP worker on `http://127.0.0.1:8765`; single RTX 4090-class instance; DeepSeek credentials supplied only through transient environment.

## Code And Command

- Workbench wrapper: `scripts/workbench/run_expanded_a6_eval.py`.
- Chain runner: `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Accepted run ID: `20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14`.
- Accepted summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14_summary.json`.
- Diagnostic lineage:
  - `20260608_expanded_a6_exact_msft_deterministic_bypass_v0_6`: exact lookup bypass pass.
  - `20260608_expanded_a6_sector_inprocess_no_text_ledger_smoke_v0_9`: sector latency under gate, Milvus failed because collection was empty.
  - `20260608_expanded_a6_sector_collection_embedding_key_fixed_smoke_v0_11`: sector-depth pass after Milvus collection / embedding / key environment fix.
  - `20260608_expanded_a6_4case_collection_embedding_key_fixed_smoke_v0_12`: `3/4`, failed only exact performance by `880 ms`; exact-only v0_13 then passed in `3059 ms`, showing cold IO/cache noise.
- Code changes in this run:
  - Deterministic exact lookup Research Lead LLM bypass.
  - Resident MCP context-runner alias normalization.
  - Runtime ledger build gating for non-ledger SEC text routes.
  - Workbench SEC prewarm actual device resolution and prewarm error visibility.
- Local verification: broader A6/regression subset `182 passed`.

## Inputs

- Case set:
  - `fin_full_exact_msft_capex_zh`
  - `fin_full_standard_nvda_amd_market_zh`
  - `fin_full_scope_nvda_basic_fundamental_zh`
  - `fin_full_sector_ai_infra_depth_zh`
- SEC evidence manifest: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1/records.jsonl`.
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`.
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`.
- Combined ledger: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/indexes/ledger/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`.
- Market evidence pack: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/market/processed/evidence_packs/20260606_market_yahoo_chart_tier1_tier2_1y_v0_1_3m_market_evidence.jsonl`.
- Market snapshot: `20260606_market_yahoo_chart_tier1_tier2_1y_v0_1`, as-of `2026-06-05`.
- Industry rows: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/industry/processed/20260606_industry_fred_eia_tier1_tier2_merged_v0_1/industry_evidence_rows.jsonl`.
- Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`.
- Milvus collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`.
- Milvus embedding model: `/autodl-fs/data/fin_agent_milvus_bge_m3/models/bge-m3-local`.
- BGE reranker model: `/autodl-fs/data/fin_agent_milvus_bge_m3/modelscope_cache/BAAI/bge-reranker-v2-m3`.

## Outputs

- Workbench summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14_summary.json`.
- Chain artifact root: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/artifacts/20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14/`.
- Per-case summaries: each case directory contains `multi_agent_summary.json`, `langgraph_native_summary.json`, `langgraph_node_checkpoints.json`, and `real_chain_case_score.json`.

## Results

- Gate: `pass`.
- Cases: `4/4`.
- Total tool calls: `23`.
- Total LLM tokens: `153437`.
- Avg tokens per case: `38359.25`.
- Max case elapsed: `274427 ms`.
- Workbench elapsed: `502493 ms`.
- Child elapsed: `492649 ms`.
- Scope/gap contract failures: `0`.
- Performance failures: `0`.
- Real retrieval required/pass: `2/2`.
- Real Specialist quality required/pass: `1/1`.
- SEC candidates pre-rerank: `408`.
- SEC candidates sent to BGE: `408`.
- Milvus tool calls: `2`.
- Milvus context rows: `69`.

Case-level metrics:

| Case | Status | Elapsed ms | Tokens | Tool calls | Retrieval notes |
| --- | --- | ---: | ---: | ---: | --- |
| `fin_full_exact_msft_capex_zh` | pass | `4674` | `0` | `2` | Research Lead bypassed, SEC exact ledger + 8-K search, `0` Milvus calls |
| `fin_full_standard_nvda_amd_market_zh` | pass | `84872` | `46226` | `4` | SEC candidates `64`, market rows present |
| `fin_full_scope_nvda_basic_fundamental_zh` | pass | `128433` | `37125` | `6` | Milvus rows `24`, scope/gap contract pass |
| `fin_full_sector_ai_infra_depth_zh` | pass | `274427` | `70086` | `11` | SEC candidates `268`, Milvus rows `45`, Universe Relationship `2` calls |

Prewarm:

- Status: `pass`.
- `sec_search_filings`: `ok`, cache hit `true`, row_count `8`, elapsed `52 ms`.
- `sec_milvus_semantic_search`: `ok`, row_count `4`, elapsed `1273 ms`.
- Resident worker cache after prewarm: interactive module loaded, Milvus embedding/client cache `1/1`, SEC search result cache `7`.

## Interpretation

- The A6 4-case smoke is now green under real retrieval and real LLM execution.
- deterministic exact lookup is fixed: it no longer spends Research Lead tokens and no longer invokes Milvus.
- Milvus semantic recall is now actually wired into scope/sector cases with the correct collection and BGE-M3 embedding model.
- SEC prewarm bug was not retrieval quality; it was an invalid `bge_device=auto` payload. After resolving to `cuda`, prewarm status is `ok`.
- Remaining cost is primarily LLM sequencing and sector-depth Research Lead/Universe calls. This is acceptable for 4-case smoke but not enough to claim 10-20 case expanded promotion.

## Runtime Efficiency

- Exact lookup path is effectively hot-path ready at `4674 ms` and `0` tokens in the accepted 4-case run.
- Sector-depth is under the `300000 ms` latency gate at `274427 ms`.
- Prewarm hot cache is fast in the accepted run, but the first same-profile SEC prewarm after device fix still took about `91 s` due resident-side resource/cache warmup. Keep this separate from timed case latency.
- Milvus Lite remains CPU-index based. CUDA is used for BGE rerank/embedding, not for Milvus ANN.

## Governance

- Decision: proceed from A6 4-case smoke to low-concurrency remaining-case diagnostic, not direct promotion.
- Stop condition: if remaining cases expose material scope/gap failures or sector-depth latency climbs above `300000 ms`, return to Research Lead/Universe cost and ref-validation fixes before broader concurrency.
- Serving note: keep resident worker and prewarm profile active for any Workbench-run A6 diagnostic; cold subprocess SEC search is no longer representative.

## Safety

- No API key, cloud password, or temporary credential is stored in this ledger.
- Raw LLM responses were not saved.
- This ledger references cloud artifact paths only.
