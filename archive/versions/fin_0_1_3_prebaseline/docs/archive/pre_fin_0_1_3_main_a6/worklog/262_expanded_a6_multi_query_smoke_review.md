# 262 Expanded A6 Multi-query Milvus 4-case Smoke Review

日期：2026-06-07

## 问题

用户要求在继续跑剩余 A6 case 前，先复盘当前 4-case smoke 的实际问题，覆盖效率、链路各节点输出质量，以及是否适合用并发继续压当前 Workbench 后端。

本轮不继续跑剩余 case，先把 4-case 结果定性为 diagnostic-only。

## 结果概览

云端 run：

- Run ID：`20260607_expanded_a6_multi_query_milvus_full_chain_smoke_v0_1`
- Summary：`/autodl-fs/data/fin_agent_milvus_bge_m3/reports/quality/workbench_eval/summaries/20260607_expanded_a6_multi_query_milvus_full_chain_smoke_v0_1_summary.json`
- Gate：历史 scorer 下 `pass`
- Cases：`4/4`
- Tool calls：`25`
- Milvus tool calls：`5`
- Milvus context rows：`390`
- SEC pre-rerank candidates：`200`
- BGE candidates：`200`
- Total LLM tokens：`174400`
- Avg tokens / case：`43600`
- Child elapsed：`742125 ms`
- Wrapper elapsed：`755705 ms`
- Max case elapsed：`331403 ms`

该结果证明 full-chain 功能上可以跑通 resident MCP、SEC retrieval、Milvus typed semantic recall、scope decision、gap escalation、Specialist、Memo 和 Verifier；但不能作为 expanded A6 promotion。

## Case 级问题

1. `fin_full_exact_msft_capex_zh`
   - 通过，但误调用 `sec_milvus_semantic_search`。
   - Research Lead route reason 明确写了不需要 semantic/text routes，说明问题在 retrieval compiler 的 semantic preservation 规则过宽。
   - deterministic renderer 输出了 4 个候选 metric，而不是单指标答案。

2. `fin_full_scope_nvda_basic_fundamental_zh`
   - 通过，`145.570s`、`38170` tokens。
   - scope decision 正确选择不扩展；Fundamental / Market / Risk 的 gap requests 被保留下来。
   - 输出质量边界合理，但 memo chars/token 偏低，说明上游 token 花费和最终可读结论之间仍不够经济。

3. `fin_full_standard_nvda_amd_market_zh`
   - 通过，`224.346s`、`49152` tokens。
   - 标准 memo 在历史 scorer 下因为缺少默认 performance limit 而未失败；修复后应被 latency gate 捕获。
   - 主要耗时来自 Research Lead、operator 外层路径、Specialist 和 Memo Writer。

4. `fin_full_sector_ai_infra_depth_zh`
   - 通过，`331.403s`、`76813` tokens、`13` tool calls。
   - scope expansion 和 gap escalation 行为正确，Universe / Industry / Market / Risk 都保留了 blocking/material gaps。
   - 质量审计标记 `high_total_token_cost`、`low_memo_chars_per_token`、`memo_surface_says_evidence_thin`。
   - 该 case 是当前 expanded A6 的效率瓶颈，不适合直接扩大到高并发。

## 链路节点复盘

- Research Lead：scope/gap 字段基本可用，但 sector-depth 和 standard cases 耗时明显；`length` retry 在 sector-depth 中出现，说明 prompt/schema 仍有压缩空间。
- Universe / Relationship：AI infra case 能输出 required expansion 和 excluded ticker rationale，但仍出现 repair，且 39s 级别耗时偏高。
- Evidence Operators：resident worker 已避免每次冷启动，但外层 SEC search artifact/context 处理仍重；sector-depth second pass 又增加 135 rows 和约 65s。
- Milvus：multi-query batch probe 已接入，低并发功能可用；当前 Milvus Lite 是 CPU index，只能说 resident/cache 生效，不能说 CUDA vector search 已生效。
- Specialist：gap requests 和 source boundary 方向正确；但 standard/sector 的 token 成本偏高，需要后续压缩激活面和输入投影。
- Memo / Verifier：最终答案能保留 bounded/gap 信息，但 memo surface 相对 token 花费偏薄；Verifier token 已低于 Memo，但仍需保障 unresolved gaps 不被包装掉。
- Eval scorer：历史 performance gate 口径不够硬，导致 224s standard 和 331s sector-depth 仍 pass。

## 已完成修复

- `src/sec_agent/retrieval_plan.py`
  - 对 deterministic / exact lookup requirement 禁止补 `milvus_semantic`。
  - 当 route reason 明确写 no semantic / no Milvus / no text retrieval 时，不再强行保留 semantic recall。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - 增加 mode-level 默认 performance limits，避免 fixture 未写 limit 时超时仍 pass。
- `src/sec_agent/langgraph_orchestrator.py`
  - deterministic exact renderer 从 top4 改为 top1，单指标问题只输出一个主结果。

## 验证

本地：

- `python -m py_compile src\sec_agent\retrieval_plan.py src\sec_agent\langgraph_orchestrator.py scripts\eval_multi_agent\eval_multi_agent_real_llm_chain.py`
- `python -m pytest -q tests\test_sec_agent_retrieval_plan.py tests\test_multi_agent_real_llm_chain_eval.py tests\test_workbench_expanded_a6_eval.py tests\test_multi_agent_operator_permissions.py tests\test_sec_agent_mcp_runtime_tools.py tests\test_multi_agent_langgraph_routing.py tests\test_milvus_multi_query_batch_probe.py tests\test_milvus_retrieval_ab_design.py`
  - 结果：`103 passed`

云端：

- 修复文件已同步到 `/autodl-fs/data/fin_agent_milvus_bge_m3`。
- 云端 `py_compile` 通过。
- 未在修复后重跑 4-case，也未运行剩余 case。

## 决策

- 本轮 4-case 是功能诊断通过，不是 expanded A6 promotion。
- 剩余 case 不应马上高并发运行。
- 下一步优先重跑修复后的 4-case，确认：
  - exact lookup 不再触发 Milvus；
  - single metric renderer 只输出一个主结果；
  - standard / sector-depth 超过默认 latency gate 时会被明确标记；
  - scope/gap contract 仍通过。
- 如果修复后 4-case 行为干净，再用 Workbench 后端低并发 `2` 跑剩余 case，用 backend trace/token/runtime/report 体系测试性能。

## 后续

- [ ] 在云端重跑修复后的 4-case A6 smoke。
- [ ] 把 resident worker/cache-hit metadata 显式写入 A6 summary。
- [ ] 用 Workbench backend job runner 以并发 `2` 跑剩余 A6 case，并观察 resident worker log、backend trace、token/runtime 统计和失败类型。
- [ ] 如果并发 `2` 稳定，再考虑并发 `3`；在 Milvus Lite CPU index 未替换前不做高并发或 CUDA vector-search 宣称。
- [ ] 将 Research Lead / Universe 长 prompt、operator second-pass 和 Specialist 输入投影列为 A6 后续成本优化对象。
