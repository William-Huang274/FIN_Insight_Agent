# 191 Multi-agent Tool-call Ledger And Loop Budget

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 3 已实现并通过目标单测
关联文档：`188_multi_agent_architecture_execution_plan.md`、`190_multi_agent_agent_registry_contract.md`

## 问题

188 Step 3 要求实现 `ToolCallLedger`、`LoopBudget`、重复工具调用阻断、总预算 / 单 agent 预算、second-pass 无增益中止和 repair 无进展中止。目标是先把 multi-agent 工具循环的中止合同独立打稳，后续 Evidence Operator、Reflection 二次检索和 LangGraph state 都复用同一套 ledger。

本步骤仍不接真实 MCP handler、不执行 full-chain、不改变现有默认运行链路。

## 实现决策

新增：

- `src/sec_agent/tool_call_ledger.py`
- `tests/test_multi_agent_tool_call_ledger.py`

核心对象：

- `ToolCallRecord`
- `LoopBudget`
- `ToolCallLedger`

核心函数：

- `normalize_tool_arguments()`
- `stable_tool_arguments_digest()`

## 已实现能力

### Stable arguments digest

`stable_tool_arguments_digest(tool_name, arguments)` 使用 stable JSON 和 `sha256:<16hex>` 摘要。

归一化规则：

- 排序 dict key。
- 移除 volatile 字段，例如 `output_dir`、`output_root`、`run_id`、`timestamp`、`trace_path`、`created_at`、`updated_at`。
- 统一 ticker / filing type / period role 大小写。
- 对 `tickers`、`years`、`filing_types`、`source_tiers`、`metric_families`、`period_roles` 等无序列表去重和排序。
- 保留业务字段，例如 `query`、ticker、year、source tier、route 相关参数。

### Tool-call budget

`ToolCallLedger.can_call_tool()` 在执行工具前检查：

- `max_tool_calls_total`
- `max_tool_calls_per_agent`
- `max_same_tool_same_args`
- 同一 turn 内 `agent_id + tool_name + arguments_digest` 重复调用

阻断时返回：

- `tool_budget_exhausted`
- `agent_tool_budget_exhausted`
- `duplicate_tool_call_blocked`

并同步设置 ledger 的 `loop_break_reason`，方便后续 graph state 持久化。

### Second-pass loop budget

`record_second_pass_result()` 实现：

- `max_second_pass_rounds` 检查。
- 记录 `second_pass_rounds`。
- 如果新增 rows 为 0 且 `coverage_delta.closed_gaps` 为 0，则设置：
  - `loop_break_reason=no_incremental_evidence`
  - `bounded_answer_allowed=True`
- second-pass 预算耗尽时返回 `second_pass_budget_exhausted`。

### Repair loop budget

`record_repair_result()` 实现：

- `max_repair_rounds` 检查。
- 如果 repair 后 verifier failure 没减少，则设置：
  - `loop_break_reason=repair_no_progress`

### Graph-step budget

`record_graph_step()` 实现：

- `max_graph_steps` 检查。
- 超限返回 `graph_step_budget_exhausted`。

### Serialization

`ToolCallRecord`、`LoopBudget`、`ToolCallLedger` 均支持 `to_dict()` / `from_dict()`，后续可直接进入 LangGraph state artifact。

## 测试

新增测试覆盖：

- Digest 忽略 volatile 字段并归一化 ticker / year。
- 相同 tool + 相同参数重复调用被阻断。
- 同一工具不同 ticker/year 不被误判为重复。
- 总工具预算和单 agent 工具预算分别生效。
- second pass 预算耗尽后不能继续触发检索。
- 无新增 rows 且无 closed gaps 时进入 bounded answer。
- 有新增 rows 或 closed gaps 时不触发 no-gain break。
- repair 无进展时设置 `repair_no_progress`。
- graph step budget 生效。
- ledger dict round-trip 保留 records 和 loop state。

## 验证

已运行：

```text
pytest tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
26 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py -q
30 passed

python -m compileall -q src/sec_agent/tool_call_ledger.py src/sec_agent/agent_registry.py src/sec_agent/agent_contracts.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py
```

未运行：

- 未运行真实 LLM 调用。
- 未运行 full-chain SEC agent。
- 未运行旧链路完整 regression gate。
- 未执行真实 MCP tool handler。
- 未构建数据、索引或 benchmark artifact。

## 后续

下一步按 188 Step 4 实现 Research Lead mock / deterministic fixture 路由：

- `src/sec_agent/multi_agent_router.py`
- `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`
- `tests/test_multi_agent_routing_fixtures.py`

Step 4 应使用 Step 1 的 activation validator、Step 2 的 agent registry 和 Step 3 的 budget 上限，验证四档 execution mode 的 deterministic routing。

## 安全说明

- 本步骤未写入 API key、SSH 密码、私有 token 或私有数据路径内容。
- Digest 逻辑会移除 volatile 输出目录和运行 id，但不会读取或写入私有数据文件。
- 测试全部使用内存 fixture，不访问 `data/raw_private/`、`data/processed_private/`、`data/indexes/` 或 `.env`。
