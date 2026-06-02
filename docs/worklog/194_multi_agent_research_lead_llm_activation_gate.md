# 194 Multi-agent Research Lead LLM Activation Gate

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：188 Step 10 已实现并通过真实 DeepSeek activation fixture gate；Specialist / Universe 真实 LLM 接入仍未开始
关联文档：`188_multi_agent_architecture_execution_plan.md`、`193_multi_agent_graph_runtime_trace_pre_llm_gate.md`

## 问题

用户提供 DeepSeek API key，要求从 188 Step 10 开始接入真实 Research Lead LLM 并测试。Step 10 的边界是：只接 Lead Agent，不接全部 specialist；Lead 输出必须是 `AgentActivationPlan` JSON；解析或校验失败最多 repair 2 次；repair 仍失败必须 fail closed；真实 5-case activation fixture 需要达到 mode `5/5` 且 forbidden activation `0`，才允许进入 graph smoke。

## 已完成

### 1. LLM Gateway JSON Output

更新：

- `src/sec_agent/llm_gateway.py`

变更：

- `chat_completion()` 新增可选 `response_format` 参数。
- Research Lead 路由使用 `{"type": "json_object"}` 请求 JSON 输出。
- 仍保持现有 DeepSeek / OpenAI-compatible / qwen_vllm 调用结构，不记录或返回 API key。

### 2. Research Lead LLM 路由

新增：

- `src/sec_agent/research_lead_llm.py`
- `tests/test_multi_agent_research_lead_llm.py`

能力：

- `ResearchLeadLLMConfig`
- `route_research_lead_activation_llm()`
- `extract_activation_plan_json()`

实现方式：

- Prompt 注入 `shared_evidence_boundary` + `research_lead_planning` skill。
- Prompt 注入静态 agent registry、mode rule、per-mode budget rule 和 `AgentActivationPlan` schema hint。
- Lead 只能输出业务层 activation plan，不允许 tool call。
- 解析支持纯 JSON、```json fenced JSON``` 和文本中首个 balanced JSON object。
- 每次输出都进入 `validate_agent_activation_plan()`，校验 agent/source/model/budget/scope/registry permission。
- schema repair 最多 2 次，默认不启用 deterministic fallback。
- repair 仍失败时返回 `status=fail`、`activation_plan={}`、`rejected_plan` 和 failure summary，不静默扩大范围。
- 只有显式设置 `allow_deterministic_fallback=True` 时才返回 deterministic fallback，并标记 `source=research_lead_llm_v0.1+deterministic_fallback`。

测试覆盖：

- 有效 JSON 通过。
- fenced JSON 解析通过。
- invalid JSON 后 repair 通过。
- repair budget 用尽后 fail closed，不默认 fallback。
- Lead 直接 tool call 被拒绝，必须 repair。

### 3. 真实 5-case 诊断脚本

新增：

- `scripts/eval_multi_agent_research_lead_activation.py`

能力：

- 读取 `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`。
- 对每个 case 调真实 Research Lead LLM。
- 记录 sanitized run summary：
  - activation plan
  - validation summary
  - routing trace
  - token / latency summary
  - failure reason
- 不保存 raw LLM response。
- 不保存 API key。
- 输出目录默认：`eval/sec_cases/outputs/multi_agent_activation_diagnostic/<run_id>/activation_diagnostic.json`。

Gate 对齐 188：

- hard gate：
  - LLM route pass
  - validation pass
  - mode exact match
  - required agents present
  - forbidden activation 0
- diagnostic checks：
  - per-fixture `max_tool_calls_total_lte`

### 4. Graph Smoke Trace 修复

更新：

- `src/sec_agent/langgraph_orchestrator.py`
- `tests/test_multi_agent_langgraph_routing.py`

发现：

- 真实 Lead LLM 注入 graph 后能完成 focused path，但最终 state 未保留 `agent_activation_validation`，因为 `SecAgentGraphRuntimeState` TypedDict 漏了该字段。

修复：

- 增加 `agent_activation_validation`。
- 增加 `multi_agent_routing_trace`。
- graph routing 测试新增 validation / routing trace 断言。

## 真实 DeepSeek 诊断结果

命令形态：

```text
DEEPSEEK_API_KEY=<runtime-only> python scripts/eval_multi_agent_research_lead_activation.py --llm-backend deepseek --base-url https://api.deepseek.com --chat-completions-path /chat/completions --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --strict
```

最终 run：

- Run ID: `20260530T093743Z_multi_agent_research_lead_activation_deepseek_v4_pro_v0_1`
- Output: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260530T093743Z_multi_agent_research_lead_activation_deepseek_v4_pro_v0_1/activation_diagnostic.json`
- Backend: `deepseek`
- Model: `deepseek-v4-pro`
- Raw response saved: `false`
- API key saved: `false`

结果：

```text
gate_status=pass
case_count=5
pass_count=5
all_checks_pass_count=5
mode_correct_count=5
validation_pass_count=5
llm_route_pass_count=5
required_agent_pass_count=5
budget_pass_count=5
forbidden_activation_count=0
total_latency_ms=107367
total_tokens=21103
failures=[]
diagnostic_warnings=[]
```

说明：

- 第一次真实诊断中 mode `5/5`、forbidden `0`、validation `5/5` 已满足 188 hard gate，但 focused / standard 两条超过 fixture 建议预算。
- 已加强 prompt 的 per-mode budget rule 后复跑，最终达到 `all_checks_pass_count=5`。

## Graph Smoke 结果

命令形态：

```text
DEEPSEEK_API_KEY=<runtime-only> python <inline focused graph smoke with route_research_lead_activation_llm>
```

最终 graph smoke：

- Output dir: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260530T093743Z_multi_agent_research_lead_activation_deepseek_v4_pro_v0_1_graph_smoke_r1`
- Status: `completed`
- Execution mode: `focused_answer`
- Activation validation: `pass`
- Routing mode: `focused_answer`
- Node count: `12`
- `multi_agent_summary.json`: exists

说明：

- 该 smoke 只验证真实 Lead LLM 可注入现有 multi-agent mock graph，并进入 validate / operator dry-run / reflection / memo stub / verifier stub / renderer 路径。
- 没有接入真实 specialist LLM。
- 没有执行真实 MCP handler。

## 本地验证

已运行：

```text
pytest tests/test_multi_agent_research_lead_llm.py -q
5 passed

pytest tests/test_multi_agent_activation_plan.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_tool_call_ledger.py tests/test_research_skills.py -q
47 passed

pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_research_lead_llm.py -q
9 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_industry_source_snapshot.py tests/test_sec_agent_ledger_store.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_workbench_job_runner.py tests/test_workbench_profiles.py tests/test_bm25_retriever.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_research_skills.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_research_lead_llm.py -q
159 passed

python -m compileall -q apps scripts src
```

收尾时已执行完整 regression gate 和编译检查，均通过。

## 安全说明

- API key 只作为当前 shell 的运行时环境变量使用。
- 未写入 `.env`、源代码、worklog、model run ledger 或 eval output。
- 诊断输出保存 `api_key_env` 名称和 `api_key_present` 布尔值，不保存明文 key。
- `ToolCallLedger` 已有敏感字段摘要屏蔽；本步骤没有把 key 放入 tool argument。
- 已对本次候选代码 / 文档 / model-run 记录执行敏感词扫描；命中仅为预期的 `api_key_env` 字段名和 token 统计字段，没有明文 `sk-...` key、私钥或密码。
- 已对 `eval/sec_cases/outputs/multi_agent_activation_diagnostic` 执行 `sk-*` / private-key marker 扫描，无命中。

## 下一步

建议先保留 deterministic router 作为默认 mainline，把真实 Lead LLM 标记为可选 diagnostic / graph-smoke route。进入 Step 11 前需要新增明确 feature flag 和测试面：

- Lead LLM graph smoke 扩展到 5-case。
- Specialist Analyst 真实 LLM 输出 schema。
- Universe / Relationship source family 的真实 relationship graph 合同。
- Verifier 对 analyst memolet 的 source-boundary gate。
