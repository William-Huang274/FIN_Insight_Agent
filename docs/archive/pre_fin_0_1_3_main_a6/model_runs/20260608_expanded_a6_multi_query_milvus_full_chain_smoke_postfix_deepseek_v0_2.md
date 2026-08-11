# Model Run: 20260608_expanded_a6_multi_query_milvus_full_chain_smoke_postfix_deepseek_v0_2

## Summary

- Purpose: Rerun the expanded A6 4-case smoke after exact-route Milvus suppression, default performance gates, and deterministic exact top1 rendering fixes.
- Status: diagnostic fail; exact route fixed, but expanded A6 still blocked by performance.
- Run type: inference smoke + runtime/performance gate validation.
- Timestamp: 2026-06-08.
- Environment: cloud workspace `/autodl-fs/data/fin_agent_milvus_bge_m3`; resident MCP worker on `http://127.0.0.1:8765`; DeepSeek API via transient environment variable only.

## Code And Command

- Workbench wrapper: `scripts/workbench/run_expanded_a6_eval.py`.
- Chain runner: `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Run ID: `20260608_expanded_a6_multi_query_milvus_full_chain_smoke_postfix_v0_2`.
- Workbench summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_multi_query_milvus_full_chain_smoke_postfix_v0_2_summary.json`.
- Runtime directory: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/runtime/20260608_expanded_a6_multi_query_milvus_full_chain_smoke_postfix_v0_2/`.
- Credentials: cloud login and model provider credentials were not saved to repository or run artifacts.

## Inputs

- Case set: A6 smoke slice with exact lookup, NVIDIA scope decision, NVIDIA/AMD standard memo, and AI infrastructure sector depth.
- SEC evidence manifest: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`.
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`.
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`.
- Combined ledger: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/indexes/ledger/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`.
- Market snapshot: `20260606_market_yahoo_chart_tier1_tier2_1y_v0_1`, as-of `2026-06-05`.
- Industry rows: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/industry/processed/20260606_industry_fred_eia_tier1_tier2_merged_v0_1/industry_evidence_rows.jsonl`.
- Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`.
- Milvus collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`.

## Results

- Workbench status: `fail`.
- Cases: `1/4` pass.
- Failed cases: `3/4`, all due performance checks.
- Tool calls: `24`.
- Milvus tool calls: `3`.
- Milvus context rows: `249`.
- SEC pre-rerank candidates: `704`.
- SEC candidates sent to BGE: `704`.
- Total LLM tokens: `206,678`.
- Average LLM tokens per case: `51,669.5`.
- Child elapsed: `746,473 ms`.
- Wrapper elapsed: `752,460 ms`.
- Max case elapsed: `339,354 ms`.
- Scope/gap contract failed cases: `0`.
- Real specialist quality: `1/1` pass.

Per-case:

- `fin_full_exact_msft_capex_zh`: pass, `25,035 ms`, `1` tool call, `0` Milvus calls. The exact-route suppression and deterministic top1 rendering are fixed.
- `fin_full_standard_nvda_amd_market_zh`: fail only `performance.case_elapsed_ms_lte`, `185,140 ms` against the `180,000 ms` default standard gate.
- `fin_full_sector_ai_infra_depth_zh`: fail only `performance.case_elapsed_ms_lte`, `339,354 ms` against the `300,000 ms` deep-research gate.
- `fin_full_scope_nvda_basic_fundamental_zh`: fail `performance.case_elapsed_ms_lte` and `performance.memo_tokens_lte`, `196,631 ms`; scope/gap contract still passed.

Agent token usage:

- Research Lead: `46,845`
- Universe Relationship: `17,983`
- Fundamental Analyst: `23,872`
- Industry Supply Chain Analyst: `11,536`
- Market Valuation Analyst: `17,664`
- Risk Counterevidence Analyst: `23,281`
- Memo Writer: `48,043`
- Verifier: `17,454`

## Interpretation

- The original exact-route bug is fixed: deterministic exact lookup no longer invokes Milvus and no longer emits multiple candidate metrics.
- The new default performance gates are working: three slow cases are now correctly marked failed.
- The remaining blocker is not vector search latency. Milvus calls took about 1-2 seconds each and the resident worker stayed healthy.
- The major cost drivers are LLM calls and graph sequencing: Research Lead still commonly uses two calls, Memo Writer is the largest token bucket, Universe used three calls in the sector-depth case, and Specialist/Memo/Verifier stages execute sequentially.
- The 4-case result is not clean enough to justify running the remaining A6 cases concurrently. Doing so would mainly measure queueing/API wait and resident-worker stress under an already failing performance profile.

## Quality Review

- Quality audit issue counts:
  - `high_total_token_cost`: `2`
  - `low_claim_card_token_efficiency`: `2`
  - `low_memo_chars_per_token`: `2`
  - `memo_surface_says_evidence_thin`: `2`
  - `memo_writer_high_token_cost`: `1`
  - `memo_writer_retry_cost_present`: `1`
- Scope/gap requirements passed for all cases, so the professional scope-decision / gap-escalation contract remains intact.
- Sector-depth still relies on the current bounded relationship/sector-depth pack; this is not evidence of true 603-company relationship-edge coverage.

## Verification

- Local py_compile passed for:
  - `src\sec_agent\retrieval_plan.py`
  - `src\sec_agent\langgraph_orchestrator.py`
  - `scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py`
- Local targeted regression:
  - `python -m pytest -q tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_multi_agent_operator_permissions.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_langgraph_routing.py tests\test_milvus_multi_query_batch_probe.py tests\test_milvus_retrieval_ab_design.py`
  - Result: `104 passed`.
- Cloud py_compile passed.
- Cloud venv did not include pytest; an inline route-compiler check confirmed exact query-contract metadata compiles only `ledger_first`.
- Cloud exact-only smoke confirmed `milvus_tool_calls=0`, `total_tool_calls=1`, `gate_status=pass`.

## Runtime Efficiency

- Resident worker health after the run:
  - `request_count=26`
  - `interactive_module_loaded=true`
  - Milvus embedding/client cache sizes `1/1`
  - SEC search cache size `13`
- Current Milvus Lite path remains CPU-index based. Resident mode avoids repeated model/client load, but it is not a GPU ANN serving path.
- Concurrency recommendation: do not run remaining cases concurrently until at least the standard/scope 4-case subset passes or the gate is explicitly reclassified as a pressure diagnostic.

## Next Decision

- Do not promote expanded A6 or run the remaining case batch as a quality gate yet.
- Next optimization should target:
  - Research Lead double-call cost and schema length retries.
  - Memo Writer retry/token cost, especially for NVIDIA scope.
  - Universe Relationship repair/call count in sector-depth.
  - Optional parallel execution for independent Specialist routes only after the single-case profile is stable.
  - Summary telemetry for resident cache hit and per-tool resident elapsed metadata.
