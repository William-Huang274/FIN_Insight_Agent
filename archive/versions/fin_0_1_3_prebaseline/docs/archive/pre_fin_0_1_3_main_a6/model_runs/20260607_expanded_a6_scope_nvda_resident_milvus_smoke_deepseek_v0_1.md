# Model Run: 20260607_expanded_a6_scope_nvda_resident_milvus_smoke_deepseek_v0_1

## Summary

- Purpose: Validate A6 NVIDIA scope-decision full-chain smoke with resident BGE/Milvus MCP tools and typed Milvus semantic recall enabled.
- Status: accepted single-case A6 smoke; not yet expanded full-chain promotion.
- Run type: inference smoke + retrieval/operator runtime validation.
- Timestamp: 2026-06-07.
- Environment: cloud workspace `/autodl-fs/data/fin_agent_milvus_bge_m3`; single RTX 4090-class cloud instance; Python `.venv`; DeepSeek API via transient env only.

## Code And Command

- Entry point: `scripts/workbench/run_expanded_a6_eval.py` wrapping `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Run ID: `20260607_expanded_a6_scope_nvda_boundary_resident_milvus_v0_8_cache_hit`.
- Resident MCP worker:
  - Script: `scripts/mcp/run_sec_agent_mcp_resident_worker.py`
  - URL used by full-chain runs: `http://127.0.0.1:8765`
  - Forwarded tools: `sec_search_filings`, `sec_milvus_semantic_search`
- Code changes in this run:
  - Added resident MCP worker and forwarding.
  - Added true Milvus semantic search handler with cached embedding model and Milvus client.
  - Added semantic route preservation when case contract explicitly requests typed semantic recall.
  - Added bounded `sec_search_filings` result cache.
- Credentials: cloud login and provider runtime credentials were used only for this session and were not persisted.
- Seeds: deterministic eval gates; LLM temperature `0`.

## Inputs

- Eval case: `fin_full_scope_nvda_basic_fundamental_zh`.
- SEC evidence manifest: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`
- Combined ledger: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/indexes/ledger/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`
- Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`
- Milvus collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`
- Milvus embedding model: `models/bge-m3-local`
- BGE reranker model: `modelscope_cache/BAAI/bge-reranker-v2-m3`

## Outputs

- Workbench summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260607_expanded_a6_scope_nvda_boundary_resident_milvus_v0_8_cache_hit_summary.json`
- Runtime directory: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/runtime/20260607_expanded_a6_scope_nvda_boundary_resident_milvus_v0_8_cache_hit/`
- Resident worker log: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/runtime/resident_worker_v0_2_cache.log`

## Results

- Gate: `pass`
- Cases: `1/1`
- Tool calls: `5`
- Milvus tool calls: `1`
- Milvus context rows: `27`
- SEC pre-rerank candidates: `20`
- SEC candidates sent to BGE: `20`
- Total LLM tokens: `34,892`
- Avg LLM tokens / case: `34,892`
- Max case elapsed: `170,911 ms`
- Performance failed cases: `0`
- Scope/gap contract failed cases: `0`

Agent token usage:

- Research Lead: `5,666`
- Fundamental Analyst: `7,088`
- Market Valuation Analyst: `4,357`
- Risk Counterevidence Analyst: `7,402`
- Memo Writer: `6,816`
- Verifier: `3,563`
- Universe Relationship: `0`

Resident worker health after run:

- PID: `11057`
- Port: `8765`
- Request count: `7`
- Interactive module loaded: `true`
- Milvus embedding model cache size: `1`
- Milvus client cache size: `1`
- SEC search result cache size: `3`

## Interpretation

- The A6 NVIDIA scope case now proves the full-chain can invoke both SEC lexical/rerank retrieval and Milvus typed semantic recall under a resident worker.
- The accepted smoke supersedes earlier v0.5/v0.6/v0.7 failures for this single case, but it is not enough to promote the expanded route globally.
- The Milvus path is a typed semantic supplement only; exact numeric claims must still come from the combined ledger or bounded source rows.
- Current Milvus Lite usage keeps the embedding model and Milvus client resident, but search itself is not a GPU index path. GPU Milvus follow-up needs Milvus server GPU index or FAISS-GPU evaluation.

## Verification

- Local py_compile passed for changed MCP, resident worker, retrieval plan, and eval runner modules.
- Local regression:
  - `python -m pytest -q tests\test_multi_agent_research_lead_llm.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_operator_permissions.py`
  - Result: `91 passed`
- Cloud resident health returned `status=ok` after the accepted run.

## Runtime Efficiency

- Wall time: `174,083 ms` wrapper elapsed; `170,911 ms` max case elapsed.
- Stage bottleneck: evidence operator / SEC search outer path remains material despite resident worker.
- Direct resident cache probe showed repeated identical `sec_search_filings` can return in milliseconds, but A6 LLM route variance can still miss the result cache.
- Serving implication: resident worker removes repeat model/client load, but full-chain latency remains close to the 180s gate and should not yet be treated as production latency.

## Caveats And Next Step

- Not run: A6 10-20 case main batch.
- Known risks:
  - `sec_search_filings` result cache is not yet canonical enough for all LLM route variants.
  - Eval summary should expose resident/cache hit metadata directly.
  - Expanded market snapshot propagation still needs separate validation.
  - Milvus Lite is not CUDA ANN.
- Next decision:
  - Stabilize SEC search canonical cache key and summary telemetry.
  - Run a small 4-case A6 smoke before full 20-case A6.
  - Evaluate Milvus server GPU index or FAISS-GPU sidecar under a separate retrieval-only A/B before claiming CUDA vector search.
