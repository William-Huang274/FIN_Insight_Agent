# 263 Expanded A6 Postfix Smoke Performance Gate

日期：2026-06-08

## 问题

继续执行 4-case 复盘后的下一步：先确认 exact lookup 不再误走 Milvus，再重跑 A6 4-case smoke，判断是否可以进入剩余 case 的低并发运行。

## 修复

本轮补了三处代码修复：

- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - `_query_contract(case)` 写入 `case_id`、`category`、`expected_execution_mode`，避免 LangGraph 内部 compiler 丢失 fixture 的执行模式。
- `src/sec_agent/langgraph_orchestrator.py`
  - compile evidence / retrieval plan 时从 query contract 回填 `category` 和 `expected_execution_mode`。
- `src/sec_agent/retrieval_plan.py`
  - `_semantic_recall_forbidden_for_requirement(...)` 从 `case.query_contract` fallback 读取 execution metadata。
  - deterministic / exact lookup 禁止 `milvus_semantic`，但不再把普通“精确数值”基本面 requirement 误判为 exact-only，避免破坏 NVIDIA semantic recall。

新增回归：

- `tests/test_sec_agent_retrieval_plan.py::test_retrieval_plan_suppresses_milvus_when_exact_mode_only_exists_in_query_contract`

## 验证

本地：

- `python -m py_compile src\sec_agent\retrieval_plan.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py`
- `python -m pytest -q tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_multi_agent_operator_permissions.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_langgraph_routing.py tests\test_milvus_multi_query_batch_probe.py tests\test_milvus_retrieval_ab_design.py`
  - 结果：`104 passed`

云端：

- 同步修复文件到 `/autodl-fs/data/fin_agent_milvus_bge_m3`。
- 云端 `py_compile` 通过。
- 云端 venv 无 pytest；用 inline route-compiler check 验证 exact query-contract metadata 只生成 `ledger_first`。
- exact-only 真实 smoke 通过：`milvus_tool_calls=0`、`total_tool_calls=1`、`max_case_elapsed_ms=28602`。

## 4-case Postfix 结果

Run ID：

- `20260608_expanded_a6_multi_query_milvus_full_chain_smoke_postfix_v0_2`

Summary：

- `/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260608_expanded_a6_multi_query_milvus_full_chain_smoke_postfix_v0_2_summary.json`

结果：

- Status：`fail`
- Cases：`1/4` pass
- Tool calls：`24`
- Milvus tool calls：`3`
- Milvus context rows：`249`
- SEC pre-rerank candidates：`704`
- BGE candidates：`704`
- Total LLM tokens：`206678`
- Avg tokens / case：`51669.5`
- Max case elapsed：`339354 ms`
- Scope/gap contract failed cases：`0`
- Performance failed cases：
  - `fin_full_standard_nvda_amd_market_zh`
  - `fin_full_sector_ai_infra_depth_zh`
  - `fin_full_scope_nvda_basic_fundamental_zh`

Case 结论：

- exact MSFT capex：通过，`25035 ms`、`1` tool call、`0` Milvus calls。
- standard NVDA/AMD：只因 latency fail，`185140 ms`，超过 standard `180000 ms` gate。
- sector AI infra：只因 latency fail，`339354 ms`，超过 deep-research `300000 ms` gate。
- scope NVIDIA fundamental：latency + Memo token fail，`196631 ms`，scope/gap contract 仍通过。

## 判断

- exact lookup 误走 Milvus 的 bug 已修。
- performance gate 已经按预期抓出慢 case。
- 当前 A6 不能进入剩余 case 并发 quality gate。
- Milvus 本身不是当前主要瓶颈；Milvus 单次调用约 1-2 秒，主要成本在 LLM 编排：
  - Research Lead standard/scope 仍常见 `2` calls；
  - Memo Writer 是最大 token bucket，本轮 `48043` tokens；
  - Sector-depth Universe Relationship 用了 `3` calls；
  - Specialist / Memo / Verifier 当前仍基本串行。

## 后续

- [ ] 优先压 Research Lead 双调用和 sector-depth `length` retry。
- [ ] 压 Memo Writer 输入/修复成本，尤其 NVIDIA scope 的 `memo_tokens_lte` fail。
- [ ] 检查 Universe Relationship 为什么 sector-depth 用 `3` calls，再决定是否调 schema 或 repair 策略。
- [ ] A6 summary 增加 resident worker/cache-hit/per-tool resident elapsed metadata。
- [ ] 只有当修复后 4-case 至少 standard/scope 稳定过 performance gate，才把剩余 case 作为质量 gate 跑；否则只能作为 pressure diagnostic 低并发跑。
