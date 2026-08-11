# 189 Multi-agent AgentActivationPlan Schema

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 1 已实现并通过目标单测
关联文档：`188_multi_agent_architecture_execution_plan.md`

## 问题

根据 188 的 Step 1，需要先落地 `AgentActivationPlan` schema 和 validator。目标是让后续 Research Lead LLM 或 deterministic fixture 产生的激活计划，在进入 LangGraph 条件分支前先经过稳定合同检查。

本步骤不接真实模型、不改现有运行链路、不实现完整 agent registry。

## 实现决策

- 新增 `src/sec_agent/agent_contracts.py`，把 Step 1 合同作为独立模块实现。
- 使用 dataclass 和纯 Python validator，不引入额外依赖。
- 暂时内置默认 agent id、source family、execution mode、model profile 和全局预算上限；Step 2 的 agent registry 完成后可通过 `agent_registry` / `known_agent_ids` 参数接入真实 registry。
- Validator 返回结构化 report，不直接修改运行 graph：
  - `status`
  - normalized `plan`
  - `errors`
  - `warnings`
- 保留 `assert_valid_agent_activation_plan()` 作为 fail-closed 辅助入口。

## 已完成

新增代码：

- `src/sec_agent/agent_contracts.py`

新增测试：

- `tests/test_multi_agent_activation_plan.py`

覆盖的规则：

- `execution_mode` 必须属于 `deterministic_lookup`、`focused_answer`、`standard_memo`、`deep_research`。
- `activate_agents` 和 `skip_agents` 只能使用已知 agent id。
- 被跳过 agent 必须有 reason。
- 每个 execution mode 必须包含所需核心 agent。
- `deterministic_lookup` 不允许激活 Universe、Specialist、Judgment Aggregator 或 Memo Writer。
- `focused_answer` 不允许无理由扩大到 full universe / 大范围 peer scope。
- `deep_research` 激活 `universe_relationship` 时必须有 relationship rationale。
- `allowed_source_families` 必须存在于默认 source family 或传入的 source inventory。
- `model_policy_hint` 只能使用抽象 profile：`none`、`fast`、`balanced`、`strong`。
- `max_tool_calls_total`、`max_second_pass_rounds`、`max_repair_rounds` 不能超过全局上限。
- 可选 `agent_registry` 输入能 fail-closed 检查：
  - Memo Writer / Renderer 不能持有工具。
  - Verifier 必须是 inspect-only，不能持有检索工具。
  - Research Lead 不能持有检索工具。
  - Evidence Operator 不能跨 source family 调工具。

## 验证

已运行：

```text
pytest tests/test_multi_agent_activation_plan.py -q
11 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_multi_agent_activation_plan.py -q
15 passed

python -m compileall -q src/sec_agent/agent_contracts.py tests/test_multi_agent_activation_plan.py
```

未运行：

- 未运行真实 LLM 调用。
- 未运行 full-chain SEC agent。
- 未运行旧链路完整 regression gate。
- 未构建数据、索引或 benchmark artifact。

## 后续

下一步按 188 Step 2 实现 `src/sec_agent/agent_registry.py`：

- 固定静态 agent registry。
- 每个 agent 声明 tool permission、allowed tools、data views、route authority、model profile、max tool calls、skill ids、input/output schema。
- 将 Step 1 validator 当前的默认 agent/source 集合改为优先读取 registry。
- 增加 registry export/validate 测试，并确保权限矩阵和 186 一致。

## 安全说明

- 本步骤未写入 API key、SSH 密码、私有 token 或私有数据路径内容。
- 新测试使用纯内存 fixture，不读取 `data/raw_private/`、`data/processed_private/`、`data/indexes/` 或 `.env`。
