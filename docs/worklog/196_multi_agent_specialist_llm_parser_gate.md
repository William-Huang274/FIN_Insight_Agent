# 196 Multi-agent Specialist LLM Parser Gate

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：188 Step 11B 已实现；只接 fake / injected LLM parser，不调用真实 Specialist LLM
关联文档：`188_multi_agent_architecture_execution_plan.md`、`195_multi_agent_step11_contract_gate.md`

## 问题

用户要求根据 185/186 和当前实现状态，先补充 188 中 Step11 及以后具体实现步骤、执行细节和门控，然后继续下一步。188 已补充 Step11-16 的分阶段执行手册。本轮代码执行 Step11B：Specialist Analyst fake-LLM JSON parser、schema repair 和 fail-closed gate。

## 已完成

### 1. 188 Step11+ 计划补充

更新：

- `docs/worklog/188_multi_agent_architecture_execution_plan.md`

新增细化：

- Step 11：Specialist Analyst 接入前置合同和 fake-LLM parser。
- Step 12：真实 Specialist Analyst 诊断接入。
- Step 13：Judgment Aggregator、Memo Writer 和 Verifier 深化。
- Step 14：Universe / Relationship 深度接入。
- Step 15：Multi-agent full graph feature flag 和 Workbench 产品化。
- Step 16：真实 multi-agent graph smoke 和 release gate。

每一步均补充了进入条件、实现落点、输入/输出合同、执行规则、验收标准和 stop / rollback 条件。

### 2. Specialist LLM parser / repair

新增：

- `src/sec_agent/specialist_llm.py`
- `tests/test_multi_agent_specialist_llm.py`

新增能力：

- `SpecialistLLMConfig`
- `route_specialist_memolet_llm()`
- `extract_specialist_memolet_json()`

实现规则：

- 只支持三类 specialist：
  - `fundamental_analyst`
  - `market_valuation_analyst`
  - `risk_counterevidence_analyst`
- LLM 调用不传 tools。
- 如果 provider 返回 tool call，直接标记 `direct_tool_call_forbidden`，进入 repair。
- 输出必须是 `SpecialistMemolet` JSON。
- 支持纯 JSON、```json fenced JSON```、文本中首个 balanced JSON object。
- 输出走 `validate_specialist_memolet()`。
- supported observation 必须引用 `known_evidence_refs`。
- unknown evidence ref、无 evidence ref 的 supported claim、错误 agent id、tool call 都 fail。
- repair 最多 2 次；仍失败则 `status=fail`、`memolet={}`，保留 `rejected_memolet` 和 failure summary，不自动当作通过。

### 3. Prompt 边界

Specialist prompt 使用：

- `shared_evidence_boundary`
- agent-specific short role instruction

明确禁止：

- 使用模型记忆补 named facts、数字、客户/供应商名单、新闻。
- 读取或引用原始 filing 全文、BM25 path、DuckDB path 或私有路径。
- 触发工具调用。

## 测试

已运行：

```text
pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_contracts.py tests/test_multi_agent_langgraph_routing.py -q
18 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_industry_source_snapshot.py tests/test_sec_agent_ledger_store.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_workbench_job_runner.py tests/test_workbench_profiles.py tests/test_bm25_retriever.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_research_skills.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py -q
176 passed

python -m compileall -q apps scripts src
```

收尾时已执行完整相关 regression gate 和编译检查，均通过。

## 未做

- 未调用真实 Specialist LLM。
- 未把 Specialist LLM parser 接入默认 graph。
- 未新增真实 specialist fixture eval script。
- 未接 Universe / Relationship 真实 LLM。
- 未新增 model-run ledger，因为本轮没有真实模型调用。

## 下一步

下一步建议进入 Step12 前的 fixture 准备：

1. 新增 `tests/fixtures/multi_agent_specialist_memolet_cases_v0_1.jsonl`。
2. 覆盖 Fundamental / Market-Valuation / Risk 三类 bounded evidence。
3. 增加 `scripts/eval_multi_agent_specialist_memolet.py`，先用 fake 或 replay 模式跑 fixture。
4. 再用真实 DeepSeek 跑 diagnostic-only Specialist memolet eval。

## 安全说明

- 本步骤未使用 API key。
- 新 parser 不保存 raw response。
- 新测试使用 fake LLM，不产生外部请求。
- 已对本次候选文件执行敏感词扫描；命中仅为预期的 `api_key_env` 字段名、环境变量名和 token 统计字段，没有明文 `sk-...` key、私钥或密码。
