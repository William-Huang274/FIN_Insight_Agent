# 187 Handoff: Multi-agent 投研工作流下一步

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：准备在新窗口继续设计和实现 multi-agent 结构

## 当前 Git 状态

已提交：

- `92148b1 Add multi-source SEC agent platform foundation`
- 该提交包含多源 SEC Agent 平台基础：Workbench、MCP 工具合同、LangGraph 编排、retrieval plan、行业/market/ledger 工具、测试和文档。

当前未提交文档改动：

- `docs/worklog/README.md`
- `docs/worklog/185_multi_agent_investment_research_framework_draft.md`
- `docs/worklog/186_multi_agent_tool_data_access_matrix_draft.md`
- 本交接文档：`docs/worklog/187_handoff_multi_agent_framework_next.md`

这些改动目前只是文档，不包含密钥、密码、私有数据、索引或运行输出。

## 已完成的关键设计

### 1. 单 agent 问题复盘

已在 `185_multi_agent_investment_research_framework_draft.md` 中记录：

- 单 agent 能把开放式投研问题转成 SEC/10-Q/8-K/market/industry 证据约束链路。
- 主要问题是角色冲突、planner/scope 错误传播、上下文压力、二次补查没有完全进入图内闭环、报告深度受限。
- Multi-agent 不是为了展示架构名词，而是为了模拟投研工作流：定题、找证据、交叉验证、识别反证、形成观点、审稿。

### 2. Multi-agent 角色草案

已定义角色：

- `Research Lead Agent`
- `Universe / Relationship Agent`
- `Evidence Operator Agents`
- `Coverage / Reflection Agent`
- `Specialist Analyst Agents`
- `Verifier Agent`
- `Memo Writer Agent`
- `Renderer`

核心职责边界：

- Lead 负责投资问题和激活路径，不直接检索。
- Universe 负责关系/产业链展开，不输出财务结论。
- Evidence Operators 负责受控工具调用，不写观点。
- Reflection 负责证据充足性和二次检索，不写 memo。
- Specialist Analysts 负责局部分析，不发布最终答案。
- Verifier 负责审稿，不生成新观点。
- Memo Writer 只消费 verified judgment plan 和证据摘要，不重新检索。

### 3. 调用裁剪和模型档位

已在 185 中新增：

- `execution_mode`
  - `deterministic_lookup`
  - `focused_answer`
  - `standard_memo`
  - `deep_research`
- `agent_activation_plan`
- `model_policy_hint`

设计原则：

- Lead Agent 必须判断是否需要激活 Universe、Specialist、Market、Industry 等 subgraph。
- 简单确定性任务不走深度研究。
- 模型档位不写死为某个供应商模型，使用 `fast / balanced / strong` profile。
- 简单任务可用更快、更便宜的模型，例如 DeepSeek flash 类模型；复杂规划、最终 memo 和 verifier 可使用强模型。

### 4. 死循环中止策略

已在 185/186 中记录：

- `max_graph_steps`
- `max_tool_calls_total`
- `max_tool_calls_per_agent`
- `max_second_pass_rounds`
- `max_repair_rounds`
- `max_same_tool_same_args`
- `max_runtime_seconds`

同时定义：

- 工具调用 digest 去重。
- 二次检索无新增 rows / 无 coverage delta 时停止。
- repair 后 verifier failure 没减少时停止。
- 中止后仍输出当前证据能支持的观点和边界，不空答。

### 5. Agent 工具与数据权限矩阵

已新建 `186_multi_agent_tool_data_access_matrix_draft.md`。

当前规划包括：

- 工具调用权限：
  - `none`
  - `inspect_only`
  - `request_only`
  - `bounded_execute`
  - `orchestrate_subgraph`
- 数据访问权限：
  - `summary_only`
  - `artifact_ref`
  - `bounded_rows`
  - `database_query`
  - `raw_source_read`
- Route 决策权限：
  - `none`
  - `suggest_business_need`
  - `compile_physical_route`
  - `adjust_budget`
  - `execute_route`

初版原则：

- 模型 agent 主要提出业务证据需求。
- Deterministic compiler 负责编译物理 route。
- Evidence Operator subgraph 的工具节点执行 route。
- Memo Writer 不允许调用检索工具。
- Verifier 不允许生成新投资观点。
- Agent 默认不直接访问数据库路径或索引路径。

## 需要新窗口继续确认的问题

### A. Lead Agent 输出 schema

下一步应先冻结一个 `AgentActivationPlan` schema。建议字段：

```json
{
  "execution_mode": "focused_answer",
  "activate_agents": [],
  "skip_agents": [],
  "allowed_source_families": [],
  "model_policy_hint": {},
  "max_tool_calls_total": 6,
  "max_second_pass_rounds": 1,
  "reasoning_summary": ""
}
```

需要讨论：

- `execution_mode` 是否就是四档，还是需要增加 `chat_followup` / `artifact_inspection`。
- `activate_agents` 应该用 agent id 还是 subgraph id。
- Lead 是否允许建议 `candidate_budget` / `rerank_budget`，还是只允许建议业务证据需求。

### B. Agent registry

建议下一步做一个静态 agent registry 配置，不急着跑真实 multi-agent。

每个 agent 记录：

- `agent_id`
- `role`
- `allowed_tools`
- `allowed_data_views`
- `route_authority`
- `model_profile`
- `max_tool_calls`
- `skill_id`
- `input_schema`
- `output_schema`

### C. Skill 拆分

185 里建议先做：

- `shared_evidence_boundary_skill`
- `research_lead_planning_skill`
- `coverage_reflection_skill`
- `memo_writer_skill`
- `verification_skill`

后续再拆：

- `relationship_universe_skill`
- `fundamental_analysis_skill`
- `industry_supply_chain_analysis_skill`
- `market_valuation_analysis_skill`
- `risk_counterevidence_skill`
- `evidence_operator_tool_use_skill`

需要确认每个 skill 的长度、注入方式和是否按模型档位裁剪。

### D. LangGraph 结构

当前建议：

- 每个核心角色是 LangGraph node。
- 有并行/循环/工具组的角色做 subgraph：
  - `evidence_operator_subgraph`
  - `reflection_second_pass_subgraph`
  - `specialist_analysis_subgraph`
  - `verification_repair_subgraph`
  - `universe_expansion_subgraph`
- 单次 LLM 调用只是 node 内部实现细节，不应游离在 graph 外。

下一步应画出 v0.2 初版 graph：

```text
load_session_state
-> research_lead_plan
-> validate_activation_plan
-> route_by_execution_mode
-> evidence_operator_subgraph
-> coverage_reflection
-> optional_second_pass
-> optional_specialist_subgraph
-> memo_writer
-> verifier
-> renderer
-> persist_session_state
```

### E. Tool-call ledger

186 已定义草案。下一步可以实现或先写 schema：

```json
{
  "turn_id": "",
  "agent_id": "",
  "tool_name": "",
  "arguments_digest": "",
  "input_artifact_digests": [],
  "output_artifact_digest": "",
  "row_count": 0,
  "source_gap_count": 0,
  "coverage_delta": {},
  "elapsed_ms": 0
}
```

它是 break loop、Workbench trace 和调试 multi-agent 的基础。

## 建议的新窗口第一步

不要直接实现所有 agent。建议从以下最小闭环开始：

1. 新增 agent registry 和 schema 文件。
2. 新增 `AgentActivationPlan` dataclass / validator。
3. 新增一个 Research Lead mock / deterministic fixture 测试，验证：
   - 简单数值问题走 `deterministic_lookup`。
   - 单公司普通分析走 `focused_answer`。
   - 多公司 memo 走 `standard_memo`。
   - 产业链问题走 `deep_research`。
4. 新增 loop budget / duplicate tool call ledger 的纯单元测试。
5. 再决定是否把 Research Lead LLM call 接入现有 graph。

这样能先把路由、权限和中止机制打稳，再让模型参与。

## 当前重要文件

架构文档：

- `docs/worklog/180_langgraph_native_orchestration_plan.md`
- `docs/worklog/181_v0_2_research_agent_platform_roadmap.md`
- `docs/worklog/184_mcp_multi_agent_contract_and_research_skills_plan.md`
- `docs/worklog/185_multi_agent_investment_research_framework_draft.md`
- `docs/worklog/186_multi_agent_tool_data_access_matrix_draft.md`

MCP / 工具合同：

- `src/sec_agent/mcp_contracts.py`
- `src/sec_agent/mcp_tool_registry.py`
- `src/sec_agent/mcp_server.py`
- `configs/mcp/sec_agent_mcp_tool_contracts_v0_1.json`

LangGraph / state：

- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/graph_state.py`
- `scripts/cloud/sec_agent_graph_runner.py`

Retrieval / route：

- `src/sec_agent/retrieval_plan.py`
- `scripts/run_sec_benchmark_eval.py`
- `src/sec_agent/ledger_store.py`
- `src/sec_agent/industry_snapshot.py`

Workbench：

- `apps/workbench/backend/app.py`
- `src/sec_agent/workbench/`

Tests:

- `tests/test_sec_agent_langgraph_orchestrator.py`
- `tests/test_sec_agent_mcp_runtime_tools.py`
- `tests/test_sec_agent_retrieval_plan.py`
- `tests/test_workbench_*.py`

## 验证状态

上一轮提交前已跑：

```text
pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_industry_source_snapshot.py tests/test_sec_agent_ledger_store.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_workbench_job_runner.py tests/test_workbench_profiles.py tests/test_bm25_retriever.py -q
106 passed

python -m compileall -q apps scripts src
```

185/186/187 是后续新增文档，未运行代码测试。

## Continuation Prompt

可在新窗口直接复制：

```text
继续 FIN_Insight_Agent 的 multi-agent 投研工作流设计与实现。当前分支是 codex/api-model-call-architecture，最近提交是 92148b1 Add multi-source SEC agent platform foundation。请先阅读 docs/worklog/185_multi_agent_investment_research_framework_draft.md、docs/worklog/186_multi_agent_tool_data_access_matrix_draft.md 和 docs/worklog/187_handoff_multi_agent_framework_next.md。

当前目标不是一次性实现所有 agent，而是先把 multi-agent 的路由、权限和中止机制打稳。请根据 185/186：
1. 设计 AgentActivationPlan schema 和 validator；
2. 设计 agent registry，记录每个 agent 的 allowed_tools、allowed_data_views、route_authority、model_profile、max_tool_calls、skill_id；
3. 设计 tool_call_ledger / loop budget / duplicate tool call break 机制；
4. 先用 mock 或 deterministic fixture 写单元测试，验证简单问题不会触发 deep_research，全链路不会重复调用同一工具，Reflection 二次检索有预算和无增益中止；
5. 暂时不要把所有 specialist agent 接入真实链路，先保证 Research Lead 的 activation plan 能被校验并驱动 LangGraph 条件分支。

注意：不要写入任何 API key、SSH 密码或私有数据；不要用规则替代模型做投研判断，规则只做 schema、权限、source inventory、预算、漂移和幻觉风险校验。
```

## 安全说明

- 本文档未包含 API key、SSH 密码、云端密码或私有供应商 token。
- 本文档未包含私有 SEC / market / industry 数据内容。
- 后续实现应继续避免把 `data/raw_private/`、`data/processed_private/`、`data/indexes/`、`eval/`、`reports/quality/` 或 `.env` 写入 Git。
