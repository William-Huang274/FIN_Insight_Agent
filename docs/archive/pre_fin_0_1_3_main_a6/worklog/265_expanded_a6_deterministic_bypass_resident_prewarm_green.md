# 265 Expanded A6 Deterministic Bypass / Resident Prewarm Green

Date: 2026-06-08

## Prompt

继续解释并验证为什么要先修 Research Lead 输出长度、Universe sector-depth ref validation、SEC/reranker prewarm，再继续 A6。用户确认后，继续把 Milvus semantic、SEC reranker、exact lookup 和 4-case smoke 跑到可交接状态。

## Decision

- 先不扩跑剩余 20-case。A6 当前最小质量门槛仍是 4-case smoke：exact lookup、standard memo、scope decision、sector-depth 都必须同时通过真实检索、scope/gap contract、token 和 latency gate。
- exact lookup 不应再消耗 Research Lead LLM；Research Lead 只负责非 deterministic query 的专业 scope decision。
- Milvus semantic 必须作为显式 typed recall supplement 真实接入；空 collection、dry-run 或 missing vector-kind 都不能算通过。
- SEC/reranker prewarm 需要和 Milvus warmup 一起纳入 Workbench runtime profile，否则 case latency 会被冷启动/IO 抖动污染。

## Changes

- `src/sec_agent/research_lead_llm.py`
  - 新增 deterministic exact lookup LLM bypass，默认开启。
  - exact lookup 通过 deterministic activation / evidence plan 进入 `sec_operator + renderer`，Research Lead diagnostics 标记 `bypassed=true`、`call_count=0`、`total_tokens=0`。
- `src/sec_agent/langgraph_orchestrator.py`
  - 让 no-call bypass diagnostics 可以作为 `all_calls_ok=true` 进入 eval audit。
- `src/sec_agent/mcp_tool_registry.py`
  - 将 `interactive` / resident alias 规范到 `in_process`，避免 SEC search 在常驻 worker 中退回 subprocess 并重复加载 BGE。
- `src/sec_agent/multi_agent_runtime.py`
  - SEC text route 默认不再因为全局 `build_runtime_ledger=true` 构建 runtime ledger；只有 `ledger_first` / explicit override 才启用，避免 sector-depth 普通 SEC text search 多出数十秒 ledger 构建。
- `scripts/workbench/run_expanded_a6_eval.py`
  - prewarm summary 记录 tool error。
  - SEC prewarm 将 `BGE_DEVICE=auto` 解析为实际 `cuda/cpu`，不再把 `auto` 直接传给 reranker。
- Tests / fixtures
  - exact lookup fixture 不再要求 Research Lead LLM pass。
  - 增加 deterministic bypass、context-runner alias、runtime-ledger gating 和 Workbench prewarm device tests。

## Cloud Runs

### Exact bypass

Run ID: `20260608_expanded_a6_exact_msft_deterministic_bypass_v0_6`

- Result: `1/1` pass.
- `fin_full_exact_msft_capex_zh`: `3231 ms`, `0` tokens, `2` tool calls.
- Research Lead: `call_count=0`, `bypassed=true`, `all_calls_ok=true`.

### Sector-depth environment diagnostics

- `20260608_expanded_a6_sector_correct_manifest_market_smoke_v0_8`
  - Functional retrieval passed after correcting SEC manifest and market snapshot path, but failed latency at `468798 ms`.
  - Root cause: context runner alias still fell to subprocess, reloading BGE/Milvus path.
- `20260608_expanded_a6_sector_inprocess_no_text_ledger_smoke_v0_9`
  - Latency improved to `286262 ms`, under the `300000 ms` sector gate.
  - Failed only Milvus semantic checks because `MILVUS_COLLECTION_NAME` was empty.
- `20260608_expanded_a6_sector_collection_embedding_fixed_smoke_v0_10`
  - Milvus prewarm succeeded, but child saw `api_key_present=false`; this run is invalid as a quality result.
- `20260608_expanded_a6_sector_collection_embedding_key_fixed_smoke_v0_11`
  - Result: `1/1` pass.
  - Sector-depth elapsed `256921 ms`, total tokens `72417`, tool calls `11`.
  - Milvus calls `2`, Milvus context rows `68`, SEC candidates pre-rerank `128`.

### Full 4-case smoke

Run ID: `20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14`

- Result: `4/4` pass.
- Workbench summary: `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_4case_prewarm_device_fixed_smoke_v0_14_summary.json`
- Total LLM tokens: `153437`.
- Total tool calls: `23`.
- Milvus calls: `2`.
- Milvus context rows: `69`.
- SEC pre-rerank candidates: `408`.
- SEC candidates sent to BGE: `408`.
- Max case elapsed: `274427 ms`.
- Scope/gap contract failures: `0`.
- Performance failures: `0`.
- Real retrieval required cases: `2/2`.
- Real Specialist quality required/pass: `1/1`.

Case details:

- `fin_full_exact_msft_capex_zh`: pass, `4674 ms`, `0` tokens, Research Lead bypassed, `0` Milvus calls.
- `fin_full_standard_nvda_amd_market_zh`: pass, `84872 ms`, `46226` tokens, SEC candidates `64`.
- `fin_full_scope_nvda_basic_fundamental_zh`: pass, `128433 ms`, `37125` tokens, Milvus rows `24`.
- `fin_full_sector_ai_infra_depth_zh`: pass, `274427 ms`, `70086` tokens, Universe tokens `11334`, Milvus rows `45`, SEC candidates `268`.

Prewarm after device fix:

- `sec_search_filings`: status `ok`, cache hit `true`, elapsed `52 ms`.
- `sec_milvus_semantic_search`: status `ok`, elapsed `1273 ms`.
- Resident worker PID during accepted run: `27833`.

## Verification

- Local targeted:
  - `python -m pytest -q tests\test_workbench_expanded_a6_eval.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_operator_permissions.py` -> `35 passed`
- Local broader A6/regression set:
  - `python -m pytest -q tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_universe_relationship_llm.py tests\test_multi_agent_langgraph_routing.py tests\test_sec_agent_langgraph_orchestrator.py tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_multi_agent_operator_permissions.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_milvus_multi_query_batch_probe.py tests\test_milvus_retrieval_ab_design.py tests\test_research_skills.py` -> `182 passed`
- Cloud:
  - `py_compile` passed for synced Workbench script and test.
  - Direct prewarm probe after fix confirmed SEC prewarm `bge_device=cuda`, status `ok`, row_count `8`.

## Remaining Work

- Research Lead standard case still needed `2` calls in v0_14; reduce double-call / repair cost before broader 10-20 case gate.
- Universe Relationship sector-depth still needed `2` calls; sector-depth pack ref normalization remains useful for first-call stability.
- Current Milvus path is resident Milvus Lite over CPU index. CUDA is used for BGE encode/rerank, not GPU ANN. GPU index / FAISS-GPU sidecar remains a separate serving optimization.
- A6 is now green for the 4-case smoke, but not yet a full expanded promotion. Next step can be low-concurrency remaining-case diagnostic using Workbench trace/token/runtime reports, then decide whether to promote.

## Safety

- Runtime provider credential and cloud password were not written to repository files.
- Raw LLM responses were not saved.
- Cloud temp runner scripts under `/tmp` may contain runtime paths only; durable repo logs contain no secrets.
