# 193 Multi-agent Graph Runtime Trace Pre-LLM Gate

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：188 Step 5-9 已实现；停在 Step 10 真实 Research Lead LLM 接入前
关联文档：`188_multi_agent_architecture_execution_plan.md`、`189_multi_agent_activation_plan_schema.md`、`190_multi_agent_agent_registry_contract.md`、`191_multi_agent_tool_call_ledger_loop_budget.md`、`192_multi_agent_deterministic_routing_fixtures.md`

## 问题

用户要求按 188 从 Step 5 做到 Step 9，也就是停在 Step 10 接入真实 LLM 前。目标是把 deterministic/mock multi-agent 路由接入 LangGraph，打通 operator 权限桥、Reflection 二次检索合同、role-specific skill 拆分和 Workbench trace inspect，同时不替换现有默认 native graph，不执行真实 LLM。

## 已完成

### Step 5：Feature-flag / mock Multi-agent Graph

更新：

- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/graph_state.py`

新增能力：

- 新增 `MULTI_AGENT_NODE_ORDER` 和 `multi_agent_node_order()`。
- 新增 `build_multi_agent_orchestration_graph()`，保留现有 `build_native_orchestration_graph()` 不变。
- 新增 `make_multi_agent_smoke_state()`。
- Graph state 新增字段：
  - `agent_activation_plan`
  - `agent_registry_snapshot`
  - `tool_call_ledger`
  - `loop_budget_state`
  - `agent_trace`
  - `tool_observations`
  - `multi_agent_reflection_report`
  - `multi_agent_second_pass_decision`
  - `specialist_outputs`
  - `multi_agent_summary`
  - `loop_break_reason`
  - `bounded_answer_allowed`
- 新 graph 使用 Step 4 deterministic router，不接真实 Research Lead LLM。
- `deterministic_lookup` 可直接到 renderer，不强制进入 memo。
- `standard_memo` 和 `deep_research` 可进入 stub specialist / judgment / memo / verifier / renderer。
- `stop_after_node` checkpoint 摘要包含 execution mode、activated agent count、tool-call count、loop break 和 bounded answer。

### Step 6：Evidence Operator / MCP Registry Bridge

新增：

- `src/sec_agent/multi_agent_runtime.py`
- `tests/test_multi_agent_operator_permissions.py`

新增能力：

- `compile_multi_agent_retrieval_plan()`
- `execute_evidence_operator_plan()`
- `validate_operator_tool_call()`
- `tool_arguments_from_route()`
- `validate_tool_observation_boundary()`

Route 到 operator/tool 的初版映射：

- `ledger_first` -> `sec_operator` / `sec_query_exact_value_ledger`
- `filing_text` -> `sec_operator` / `sec_search_filings`
- `risk_text` -> `sec_operator` / `sec_search_filings`
- `8k_commentary` -> `eight_k_operator` / `sec_search_filings`
- `market_snapshot` -> `market_operator` / `market_get_snapshot`
- `industry_snapshot` -> `industry_operator` / `industry_get_snapshot`

边界：

- Operator 权限来自 Step 2 registry。
- Tool call 先经过 Step 3 `ToolCallLedger.can_call_tool()`，再执行 handler 或 dry-run。
- Graph mock 默认 dry-run，不调用真实 MCP handler。
- Market snapshot 缺 `snapshot_id` 或 `as_of_date` 时 boundary status 为 fail。
- Industry snapshot 明确只支持 industry context，不支持 company reported financial fact。

### Step 7：Reflection Second-pass Loop Contract

新增能力：

- `normalize_reflection_report()`
- `reflection_report_from_coverage()`
- `should_execute_second_pass()`
- `record_second_pass_outcome()`

规则：

- Coverage gap 可生成 structured `second_pass_requests`。
- Source unavailable 不触发工具调用，允许 bounded answer。
- Second-pass budget 耗尽返回 `second_pass_budget_exhausted`。
- 无新增 rows 且无 closed gaps 时设置：
  - `loop_break_reason=no_incremental_evidence`
  - `bounded_answer_allowed=True`
- 同一工具同一参数重复调用由 Step 3 ledger 阻断。

### Step 8：Role-specific Skill Split

更新：

- `src/sec_agent/research_skills.py`

新增 skill 文件：

- `src/sec_agent/prompts/skills/shared_evidence_boundary_skill_v0_1.md`
- `src/sec_agent/prompts/skills/research_lead_planning_skill_v0_1.md`
- `src/sec_agent/prompts/skills/coverage_reflection_skill_v0_1.md`
- `src/sec_agent/prompts/skills/memo_writer_skill_v0_1.md`
- `src/sec_agent/prompts/skills/verification_skill_v0_1.md`

新增 role 注入：

- `research_lead`: shared boundary + lead planning
- `coverage_reflection`: shared boundary + coverage reflection
- `memo_writer`: shared boundary + memo writer
- `verifier`: shared boundary + verification

保留旧 role：

- `planner`
- `reflection`
- `synthesis`

### Step 9：Workbench Multi-agent Trace Inspect

更新：

- `src/sec_agent/workbench/artifacts.py`

新增 artifact：

- `multi_agent_summary`
- path: `multi_agent_summary.json`

Workbench summary 现在可读：

- `execution_mode`
- activated / skipped agent counts
- tool call count
- second-pass attempts
- `loop_break_reason`
- `bounded_answer_allowed`

旧 run 没有 `multi_agent_summary.json` 时仍兼容。

## 测试

新增 / 更新测试：

- `tests/test_multi_agent_langgraph_routing.py`
- `tests/test_multi_agent_operator_permissions.py`
- `tests/test_multi_agent_reflection_second_pass.py`
- `tests/test_research_skills.py`
- `tests/test_workbench_artifacts.py`

已运行：

```text
pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_research_skills.py tests/test_workbench_artifacts.py -q
21 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_research_skills.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
72 passed

pytest tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py -q
51 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_industry_source_snapshot.py tests/test_sec_agent_ledger_store.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_workbench_job_runner.py tests/test_workbench_profiles.py tests/test_bm25_retriever.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_research_skills.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
154 passed

python -m compileall -q apps scripts src
```

## 未运行

- 未运行真实 Research Lead LLM。
- 未运行 full-chain SEC agent。
- 未执行真实 MCP tool handler。
- 未构建数据、索引或 benchmark artifact。

## Step 10 前置状态

当前已经满足 Step 10 的本地前置基础：

- deterministic activation fixtures 通过。
- static agent registry 通过。
- tool-call ledger / budget 通过。
- multi-agent mock graph 通过。
- operator permission bridge 通过。
- Reflection second-pass contract 通过。
- role-specific skills 可加载。
- Workbench 可 inspect multi-agent summary。

进入 Step 10 前仍建议执行完整 regression gate，并明确真实模型配置可用性。若真实 Lead LLM 的 5-case activation fixture 未达标，应将 Lead LLM 标记为 `diagnostic-only`，继续保留 deterministic router。

## 安全说明

- 本步骤未写入 API key、SSH 密码、私有 token 或私有数据路径内容。
- `multi_agent_summary.json` 只保存摘要、agent/tool trace、row counts、source gaps、loop break，不保存原始证据全文或内部逐步推理链。
