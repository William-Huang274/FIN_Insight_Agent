# 190 Multi-agent Agent Registry Contract

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 2 已实现并通过目标单测
关联文档：`186_multi_agent_tool_data_access_matrix_draft.md`、`188_multi_agent_architecture_execution_plan.md`、`189_multi_agent_activation_plan_schema.md`

## 问题

188 Step 2 要求把 186 的 agent 权限矩阵落成静态 registry，记录每个 agent 的工具权限、数据视图、route 权限、模型档位、最大工具调用数、skill id 和输入/输出 schema。目标是让 Step 1 的 activation validator 能基于真实 registry 做权限 fail-closed 检查，并为后续 MCP operator、Workbench trace 和 LangGraph 条件分支提供统一合同。

本步骤仍不接真实 LLM、不执行 full-chain、不改变现有默认运行链路。

## 实现决策

- 新增 `src/sec_agent/agent_registry.py`。
- 采用代码内稳定 registry，模式参考 `mcp_contracts.py`：
  - `list_agent_registry()`
  - `agent_registry_by_id()`
  - `get_agent_contract()`
  - `known_agent_ids()`
  - `allowed_source_families()`
  - `validate_agent_registry()`
  - `export_agent_registry()`
- Registry entry 固定包含：
  - `agent_id`
  - `role`
  - `description`
  - `tool_permission`
  - `allowed_tools`
  - `allowed_data_views`
  - `route_authority`
  - `model_profile`
  - `max_tool_calls`
  - `skill_ids`
  - `input_schema`
  - `output_schema`
  - `source_families`
  - `future_tools`
- `future_tools` 只用于尚未落地的 relationship graph / sector inventory 类工具，必须显式标为 `future` 或 `disabled`，不能伪装成已注册 MCP 工具。

## 覆盖的 Agent

初版 registry 已覆盖 14 个 agent：

- `research_lead`
- `universe_relationship`
- `sec_operator`
- `eight_k_operator`
- `market_operator`
- `industry_operator`
- `coverage_reflection`
- `fundamental_analyst`
- `market_valuation_analyst`
- `risk_counterevidence_analyst`
- `judgment_plan_aggregator`
- `memo_writer`
- `verifier`
- `renderer`

## 权限硬规则

当前 validator 覆盖：

- Registry 无重复 agent id。
- 所有 `allowed_tools` 必须存在于 MCP tool contracts。
- `future_tools` 必须显式标为 `future` 或 `disabled`。
- `tool_permission`、`route_authority`、`model_profile`、`allowed_data_views` 必须在允许枚举内。
- 没有 agent 拥有 `raw_source_read`。
- `memo_writer.allowed_tools == []`。
- `renderer.allowed_tools == []`。
- `verifier.tool_permission == inspect_only`，且不能持有检索工具。
- `research_lead.tool_permission == request_only`，且不能持有检索工具。
- `execute_route` 只允许 `sec_operator`、`eight_k_operator`、`market_operator`、`industry_operator`。
- Evidence Operator 只能调用自己 source family 的 MCP 工具：
  - SEC：`sec_search_filings`、`sec_query_exact_value_ledger`
  - 8-K：`sec_search_filings`
  - Market：`market_get_snapshot`
  - Industry：`industry_get_snapshot`

## 测试

新增：

- `tests/test_multi_agent_agent_registry.py`

覆盖：

- Registry 有效且覆盖 Step 2 要求的全部 agent。
- MCP 工具引用均存在，future 工具有明确状态。
- 权限矩阵硬规则与 186 / 188 一致。
- Export JSON 不包含私有路径或 secret marker。
- `validate_agent_activation_plan()` 能使用静态 registry context 通过一个 `deep_research` 激活计划。
- 人为构造的权限违规 registry 能 fail-closed。

## 验证

已运行：

```text
pytest tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
17 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
21 passed

python -m compileall -q src/sec_agent/agent_registry.py src/sec_agent/agent_contracts.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py
```

未运行：

- 未运行真实 LLM 调用。
- 未运行 full-chain SEC agent。
- 未运行旧链路完整 regression gate。
- 未构建数据、索引或 benchmark artifact。

## 后续

下一步按 188 Step 3 实现：

- `src/sec_agent/tool_call_ledger.py`
- `ToolCallRecord`
- `LoopBudget`
- stable tool argument digest
- duplicate-call blocking
- total / per-agent budget checking
- second-pass no-gain break 状态

Step 3 完成后，应让 Evidence Operator 和 Reflection 二次检索都能使用同一 ledger / budget 合同。

## 安全说明

- 本步骤未写入 API key、SSH 密码、私有 token 或私有数据路径内容。
- Registry 只保存工具名、权限、schema 名和 skill id，不保存本地索引路径、数据库路径或私有 artifact 内容。
