# 195 Multi-agent Step11 Contract Gate

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：Step 11 前置合同切片已实现；真实 Specialist / Universe LLM 尚未接入
关联文档：`188_multi_agent_architecture_execution_plan.md`、`194_multi_agent_research_lead_llm_activation_gate.md`

## 问题

用户要求继续下一步。188 的 Step 11 是 Specialist 和 Universe 深度接入，但直接接真实 LLM 前需要先补齐可测合同：Lead LLM 必须有显式 feature flag，Specialist / Universe 输出必须有 schema，Judgment aggregator 必须保留冲突，Verifier 必须能在 Memo Writer 前阻断 unsupported specialist claims。

## 已完成

### 1. Lead LLM Feature Flag / Profile Wiring

更新：

- `src/sec_agent/research_lead_llm.py`
- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/workbench/profiles.py`
- `tests/test_multi_agent_research_lead_llm.py`
- `tests/test_workbench_profiles.py`

新增：

- `SEC_AGENT_MULTI_AGENT_LEAD_ROUTER`
  - `deterministic` / empty / `off`：默认 deterministic router。
  - `llm` / `deepseek` / `api`：启用真实 Research Lead LLM route。
- `research_lead_llm_config_from_env()`
- `route_activation_from_env()`
- `build_multi_agent_orchestration_graph_from_env()`

Workbench profile 新增非敏感运行配置：

- `SEC_AGENT_MULTI_AGENT_GRAPH`
- `SEC_AGENT_MULTI_AGENT_LEAD_ROUTER`

说明：

- 默认 mainline 不变，仍是 deterministic router。
- Lead LLM 只有显式设置 feature flag 时才进入 graph route。
- Profile 只保存 env var 名称和非敏感开关，不保存 API key。

### 2. Specialist / Universe Contract

新增：

- `src/sec_agent/multi_agent_contracts.py`
- `tests/test_multi_agent_contracts.py`

新增合同：

- `sec_agent_specialist_memolet_v0.1`
- `sec_agent_universe_relationship_plan_v0.1`
- `sec_agent_multi_agent_judgment_plan_v0.1`
- `sec_agent_specialist_verification_v0.1`

Specialist memolet 规则：

- 只允许 `fundamental_analyst`、`market_valuation_analyst`、`risk_counterevidence_analyst`。
- `evidence_boundary` 必须是 `bounded_rows_only`。
- Specialist 不允许 `tool_calls` / `tool_observations`。
- supported observation 必须有 `evidence_refs`。
- 可传入 `known_evidence_refs` 阻断未知引用。
- confidence 统一归一到 `unknown` / `low` / `medium` / `high`。

Universe relationship plan 规则：

- source family 必须是 `relationship_graph`。
- `full_universe` / `sector_representative` 需要 `relationship_scope_rationale`。
- 每条 relationship 必须有 `evidence_refs`。
- relationship type 限定在 peer / competitor / customer / supplier / sector / macro_sensitive / other。

### 3. Judgment Aggregator 和 Verifier Gate

更新：

- `src/sec_agent/langgraph_orchestrator.py`
- `tests/test_multi_agent_langgraph_routing.py`

新增能力：

- `aggregate_specialist_judgment_plan()` 保留 supported claims、unsupported claims、conflicts，不做平均观点。
- `verify_specialist_outputs_for_memo()` 生成 `memo_writer_allowed`。
- Graph 的 aggregation 阶段提前生成 `specialist_verification`。
- 默认 Memo Writer 在 `memo_writer_allowed=false` 时返回 `blocked_by_specialist_verification`，不会消费 unsupported specialist claims。
- Verifier 节点复用 aggregation 前生成的 specialist verification。
- `multi_agent_summary.json` 新增 specialist summary：
  - output count
  - verification status
  - memo writer allowed
  - unsupported claim count

## 测试

已运行：

```text
pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_langgraph_routing.py tests/test_workbench_profiles.py -q
24 passed

pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_industry_source_snapshot.py tests/test_sec_agent_ledger_store.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_workbench_job_runner.py tests/test_workbench_profiles.py tests/test_bm25_retriever.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_research_skills.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_tool_call_ledger.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_contracts.py -q
170 passed

python -m compileall -q apps scripts src
```

收尾时已执行完整相关 regression gate 和编译检查，均通过。

## 未做

- 未接真实 Specialist Analyst LLM。
- 未接真实 Universe / Relationship LLM。
- 未启用 relationship graph 数据源。
- 未执行真实 MCP handler 或 full-chain SEC graph。
- 未运行新的真实模型 inference，因此本条不新增 model-run ledger。

## 下一步

建议继续按 Step 11 拆小步：

1. 为 Fundamental / Market-Valuation / Risk 三个 analyst 接入 fake LLM parser + schema repair 测试。
2. 用 bounded evidence rows 构造 2-3 条 specialist fixture，验证 supported / unsupported / conflict 输出。
3. 再接真实 Specialist LLM 诊断，不接 Universe。
4. Universe / Relationship 等 relationship graph source family 稳定后再做深度产业链路径。

## 安全说明

- 本步骤未使用 API key。
- 新 profile 字段只记录 feature flag 和路由模式。
- 新合同不保存 raw evidence、私有数据路径或模型原始响应。
- 已对本次候选文件执行敏感词扫描；命中仅为预期的 `api_key_env` 字段名、环境变量名和 token 统计字段，没有明文 `sk-...` key、私钥或密码。
