# 192 Multi-agent Deterministic Routing Fixtures

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 4 已实现并通过目标单测
关联文档：`188_multi_agent_architecture_execution_plan.md`、`189_multi_agent_activation_plan_schema.md`、`190_multi_agent_agent_registry_contract.md`、`191_multi_agent_tool_call_ledger_loop_budget.md`

## 问题

188 Step 4 要求先用 Research Lead mock / deterministic fixture 验证 multi-agent activation routing，不接真实 LLM。目标是确认简单问题不会误入 deep research、标准 memo 会激活必要 operator / analyst、run artifact inspection 不会触发真实检索，并且所有输出都通过 Step 1 validator、Step 2 registry 和 Step 3 budget 上限。

本步骤仍不接真实模型、不执行真实 MCP handler、不改变现有默认运行链路。

## 实现决策

新增：

- `src/sec_agent/multi_agent_router.py`
- `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`
- `tests/test_multi_agent_routing_fixtures.py`

Router 标记为：

- `source=deterministic_research_lead_mock_v0.1`

它只用于 Step 4 deterministic routing 和后续 LangGraph mock 接入前置测试，不代表最终 Research Lead LLM。

## Router 输出

`route_multi_agent_activation()` 返回：

- `schema_version`
- `source`
- `activation_plan`
- `validation`
- `routing_trace`
- `loop_budget`

其中 `activation_plan` 会直接经过：

- `validate_agent_activation_plan()`
- `agent_registry_by_id()`
- `allowed_source_families()`
- `LoopBudget` 默认上限

## 覆盖的 Fixture

新增 5 条 fixture：

| Case | 预期 mode | 关键断言 |
| --- | --- | --- |
| `ma_msft_capex_lookup` | `deterministic_lookup` | 激活 `sec_operator` + `renderer`，不激活 Universe / Specialist / Memo Writer |
| `ma_amzn_margin_focused` | `focused_answer` | 激活 Lead、SEC、8-K、Coverage、Memo、Verifier、Renderer，不激活 Universe / Specialist |
| `ma_nvda_amd_market_standard` | `standard_memo` | 激活 SEC、8-K、Market、Fundamental、Market/Valuation、Risk、Judgment Aggregator、Memo、Verifier |
| `ma_ai_capex_supply_chain_deep` | `deep_research` | 激活 Universe、SEC、8-K、Market、Industry 和全部初版 analyst / writer / verifier |
| `ma_run_coverage_inspect` | `deterministic_lookup` | 只允许 run artifact inspection，不激活 evidence retrieval operators |

## 验收覆盖

测试覆盖：

- 5/5 fixture execution mode exact match。
- 每个 fixture 的 required agents 均激活。
- Forbidden agent activation 为 0。
- 每个 skip agent 都有非空 reason。
- 每个 plan 的预算不超过 fixture 上限和全局上限。
- Run artifact inspection 的 `allowed_source_families == ["run_artifact"]`，且不激活 SEC / 8-K / Market / Industry operator。
- Deep research 带 `relationship_scope_rationale` 和 `relationship_graph` source family。
- 强制 `context.execution_mode=standard_memo` 时仍能通过 validator。

## 验证

已运行：

```text
pytest tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
31 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
35 passed

python -m compileall -q src/sec_agent/multi_agent_router.py src/sec_agent/tool_call_ledger.py src/sec_agent/agent_registry.py src/sec_agent/agent_contracts.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py
```

未运行：

- 未运行真实 LLM 调用。
- 未运行 full-chain SEC agent。
- 未运行旧链路完整 regression gate。
- 未执行真实 MCP tool handler。
- 未构建数据、索引或 benchmark artifact。

## 后续

下一步按 188 Step 5 实现 feature-flagged multi-agent LangGraph builder / state 接入：

- 保留现有 `build_native_orchestration_graph()` 不变。
- 新增 multi-agent graph 或 feature flag 路径。
- Graph state 新增 `agent_activation_plan`、`agent_registry_snapshot`、`tool_call_ledger`、`loop_budget_state`、`agent_trace`、`loop_break_reason`、`bounded_answer_allowed`。
- 使用 Step 4 deterministic router 做 mock graph smoke，不接真实 Research Lead LLM。

## 安全说明

- 本步骤未写入 API key、SSH 密码、私有 token 或私有数据路径内容。
- Fixture 全部为公开公司 ticker 和 synthetic prompt，不包含私有数据或 artifact 内容。
