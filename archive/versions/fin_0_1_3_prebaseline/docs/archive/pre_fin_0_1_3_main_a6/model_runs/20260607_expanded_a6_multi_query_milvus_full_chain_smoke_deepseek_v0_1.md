# Model Run: 20260607_expanded_a6_multi_query_milvus_full_chain_smoke_deepseek_v0_1

## Summary

- Purpose: Review the first expanded A6 4-case full-chain smoke with resident MCP tools and multi-query Milvus semantic recall before broadening to the remaining cases.
- Status: diagnostic-only functional pass; not accepted as expanded full-chain promotion.
- Run type: inference smoke + retrieval/runtime evaluation.
- Timestamp: 2026-06-07.
- Environment: cloud workspace `/autodl-fs/data/fin_agent_milvus_bge_m3`; resident MCP worker on `http://127.0.0.1:8765`; DeepSeek API via transient environment variable only.

## Code And Command

- Workbench wrapper: `scripts/workbench/run_expanded_a6_eval.py`.
- Chain runner: `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`.
- Run ID: `20260607_expanded_a6_multi_query_milvus_full_chain_smoke_v0_1`.
- Workbench summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260607_expanded_a6_multi_query_milvus_full_chain_smoke_v0_1_summary.json`.
- Runtime directory: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/runtime/20260607_expanded_a6_multi_query_milvus_full_chain_smoke_v0_1/`.
- Resident worker log: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/runtime/resident_worker_v0_4_multi_query_batch.log`.
- Credentials: cloud login and model provider credentials were not saved to files.

## Inputs

- Case set: 4-case A6 smoke slice covering exact lookup, NVIDIA scope decision, NVIDIA/AMD market comparison, and AI infrastructure sector depth.
- SEC evidence manifest: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`.
- SEC BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`.
- Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`.
- Combined ledger: `/autodl-fs/data/fin_agent_milvus_bge_m3/full_source_uploads/tier1_tier2_full_source_v0_1/indexes/ledger/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1_ledger.duckdb`.
- Market snapshot: `20260606_market_yahoo_chart_tier1_tier2_1y_v0_1`, as-of `2026-06-05`.
- Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`.
- Milvus collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`.

## Results

- Historical gate result: `pass`.
- Cases: `4/4`.
- Tool calls: `25`.
- Milvus tool calls: `5`.
- Milvus context rows: `390`.
- SEC pre-rerank candidates: `200`.
- SEC candidates sent to BGE: `200`.
- Total LLM tokens: `174,400`.
- Average LLM tokens per case: `43,600`.
- Child elapsed: `742,125 ms`.
- Wrapper elapsed: `755,705 ms`.
- Max case elapsed: `331,403 ms`.
- Performance failed cases under the historical scorer: `0`, because several case modes had no default performance limits.

Per-case review:

- `fin_full_exact_msft_capex_zh`: passed, `40.516s`, `10,265` tokens, but incorrectly invoked `sec_milvus_semantic_search` despite the route reason saying semantic/text routes were not needed.
- `fin_full_scope_nvda_basic_fundamental_zh`: passed, `145.570s`, `38,170` tokens, correct no-expansion decision, with blocking/material gap requests preserved.
- `fin_full_standard_nvda_amd_market_zh`: passed, `224.346s`, `49,152` tokens, but should be treated as too slow for a standard memo under the new default gate.
- `fin_full_sector_ai_infra_depth_zh`: passed, `331.403s`, `76,813` tokens, correct required expansion and gap preservation, but too slow and too token-heavy for broad-run promotion.

Agent token usage:

- Research Lead: `40,767`
- Universe Relationship: `11,375`
- Fundamental Analyst: `24,586`
- Industry Supply Chain Analyst: `12,103`
- Market Valuation Analyst: `18,637`
- Risk Counterevidence Analyst: `23,027`
- Memo Writer: `29,720`
- Verifier: `14,185`

## Quality Review

- Functional behavior was mostly correct for scope/gap preservation, especially NVIDIA fundamental and AI infrastructure sector-depth cases.
- Exact lookup routing was wrong: a deterministic ledger-first case still received semantic recall. This was a compiler/preservation bug, not a good tool-selection decision.
- Exact lookup rendering was too broad: the deterministic renderer surfaced four candidate metrics where the case expected a single metric answer.
- The historical performance scorer was too permissive: standard and deep/sector cases could pass without explicit per-case limits.
- Sector-depth quality was bounded but expensive: Research Lead, Universe, second-pass retrieval, Specialist, and Memo Writer all contributed meaningful latency and token cost.
- Quality audit flagged high token cost, low memo chars per token, and evidence-thin memo surface on sector-depth output. These are promotion blockers, not correctness failures.
- Milvus vector-kind counts in the summary behave like matched support counts across vectors, not unique row counts. Future reports should label this to avoid overstating row diversity.

## Follow-up Fixes Already Applied

- `src/sec_agent/retrieval_plan.py`: suppresses `milvus_semantic` for deterministic/exact lookup requirements and for planner routes that explicitly say no semantic/Milvus/text retrieval is needed.
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`: adds default performance limits by mode when a fixture does not define explicit limits.
- `src/sec_agent/langgraph_orchestrator.py`: deterministic exact renderer now emits one preferred metric row instead of four.

## Verification

- Local syntax check:
  - `python -m py_compile src\sec_agent\retrieval_plan.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py`
- Local targeted regression:
  - `python -m pytest -q tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_multi_agent_operator_permissions.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_langgraph_routing.py tests\test_milvus_multi_query_batch_probe.py tests\test_milvus_retrieval_ab_design.py`
  - Result: `103 passed`.
- Cloud syntax check passed after syncing the touched files.

## Runtime Efficiency

- Resident worker after the smoke had `request_count=11`, `interactive_module_loaded=true`, Milvus embedding/client cache sizes `1/1`, and SEC search cache size `5`.
- Prewarm still cost about `55.934s` for Milvus and `119.968s` for SEC search, so resident mode avoids repeated cold starts but does not make the full chain cheap.
- Major latency sources in the 4-case smoke were LLM planning/synthesis calls, evidence operator outer path, sector-depth second pass, and sequential execution of tools/specialists inside each case.
- Current Milvus Lite path is CPU-index based. It is adequate for low-concurrency functional evaluation but does not prove CUDA vector-search acceleration.
- Serving implication: use the resident worker for remaining tests, but start concurrency at `2` and keep all calls routed through the resident process so only one process owns the Milvus Lite DB.

## Experiment Governance

- Hypothesis: resident MCP plus multi-query semantic probes should make A6 expanded full-chain evaluation functional while improving recall breadth for scope/supply-chain prompts.
- Decision target: small-batch A6 smoke must preserve scope/gap contracts, avoid forbidden tools, expose latency/token failures, and keep exact lookup deterministic before broadening to 10-20 cases.
- Ceiling: Milvus Lite CPU index and sequential graph execution limit broad-run latency; no GPU-index serving claim is allowed.
- Baseline: prior single NVIDIA A6 resident smoke and previous full238/full-source layered A1-A5 gates.
- Efficiency gate: exact lookup under `60s`, standard memo under `180s`, focused answer under `180s`, deep research under `300s`, unless a fixture deliberately overrides.
- Decision label: diagnostic-only.
- Mainline decision: do not promote or run the full remaining batch until the fixed scorer/renderer/retrieval compiler is rerun on the 4-case slice or an equivalent targeted subset.

## Caveats And Next Step

- Not run after fixes: no post-fix 4-case rerun and no remaining-case concurrent run.
- Known risks:
  - Concurrent full-chain requests through `ThreadingHTTPServer` may expose thread-safety or cache-lock issues in the resident worker.
  - Milvus Lite is still CPU index and should remain a low-concurrency evaluation path.
  - Research Lead / Universe repeated calls remain expensive.
- Next decision:
  - Rerun the 4-case smoke after the fixes and verify exact lookup has `0` Milvus calls and standard/sector latency failures are visible when they exceed default gates.
  - If clean, run the remaining A6 cases through the Workbench backend with concurrency `2`, then raise only if the resident worker log and backend traces remain clean.
