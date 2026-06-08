# Model Run: 20260608_expanded_a6_20case_first_wave_perf_cache_fix_deepseek_v0_6

## Summary

- Purpose: Diagnose and repair A6 20case first-wave backend performance failures before continuing the remaining cases.
- Status: diagnostic partial; cache fix verified, first-wave rerun submitted but not accepted because SSH became unreachable before polling results.
- Run type: inference/evaluation infrastructure diagnostic.
- Timestamp: 2026-06-08.
- Environment: cloud workspace `/autodl-fs/data/fin_agent_milvus_bge_m3`; resident MCP worker on `http://127.0.0.1:8765`; Workbench backend on `http://127.0.0.1:8775`; single RTX 4090-class instance.

## Code And Command

- Workbench eval API: `POST /api/evals/run`.
- Eval ID: `expanded_a6_full_chain_main`.
- First failed wave:
  - `20260608_a6_20case_backend_w01b_exact_jpm`
  - `20260608_a6_20case_backend_w01b_focused_amzn`
- Rerun wave submitted after cache fix:
  - `20260608_a6_20case_backend_w01c_exact_jpm`
  - `20260608_a6_20case_backend_w01c_focused_amzn`
- Code changes:
  - `scripts/cloud/sec_agent_interactive.py`
  - `src/sec_agent/mcp_tool_registry.py`
  - `src/sec_agent/mcp_resident_worker.py`
  - `src/sec_agent/multi_agent_runtime.py`
  - Workbench API `case_ids` / `prewarm_resident_tools` support from the same A6 continuation line remains active.

## Inputs

- Case IDs:
  - `fin_full_exact_jpm_credit_provision_zh`
  - `fin_full_focused_amzn_margin_management_zh`
- SEC manifest: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1/records.jsonl`.
- SEC BM25/ObjectBM25, combined ledger, market/industry evidence, and Milvus settings match the accepted A6 4-case run `20260608_expanded_a6_4case_prewarm_device_fixed_deepseek_v0_5`.

## Results

Initial backend wave `w01b`:

| Job | Case | Status | Case elapsed ms | Tokens | Failure |
| --- | --- | --- | ---: | ---: | --- |
| `20260608_a6_20case_backend_w01b_exact_jpm` | `fin_full_exact_jpm_credit_provision_zh` | fail | `267792` | `0` | `performance.case_elapsed_ms_lte` only |
| `20260608_a6_20case_backend_w01b_focused_amzn` | `fin_full_focused_amzn_margin_management_zh` | fail | `297618` | `30294` | `performance.case_elapsed_ms_lte` only |

Direct diagnosis:

- JPM exact ledger direct repeat: `680 ms`, then `74 ms`, `73 ms`; ledger is not the primary bottleneck.
- SEC 8-K result-cache repeat: first call about `56 s`, repeated identical query `6 ms`.
- Before cache fix, warm new-query SEC 8-K search still spent about `13 s` in query-plan / manifest overlay.
- After adding resident manifest / inventory / registry manifest caches:
  - Cold SEC 8-K probe: `146679 ms`, dominated by first manifest/BGE resource load.
  - Warm new-query SEC 8-K probe: `1424 ms`, with `context_cache_hit=true`, `build_query_plan=1124 ms`, `retrieve_context_for_graph=286 ms`.

Rerun wave `w01c`:

- Submitted through Workbench backend with `prewarm_resident_tools=false`.
- Status is unknown because SSH began closing before banner while polling. This run must not be promoted until backend artifacts are inspected.

## Runtime Efficiency

- BGE itself was not slow: traced `context_rerank` was roughly `100-300 ms` for the 8-K probes.
- The serving bottleneck was repeated manifest/project-inventory/overlay IO in resident SEC retrieval.
- Warm path after the fix is viable for low-concurrency 20case continuation.
- Cold path still needs an explicit resident warmup before measuring case latency.

## Governance

- Decision label: diagnostic-only until `w01c` artifacts are retrieved and scored.
- Stop condition: do not submit the remaining 18 cases while cloud SSH is unreachable or until first-wave pass/fail is known.
- Safety: provider credentials were not written to repo files or logs.
