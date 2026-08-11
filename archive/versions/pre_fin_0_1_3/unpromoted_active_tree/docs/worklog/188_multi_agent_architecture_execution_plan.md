# 188 Multi-agent 架构更新执行文档

日期：2026-05-30
分支：`codex/api-model-call-architecture`
最近提交：`92148b1 Add multi-source SEC agent platform foundation`
状态：执行计划，已按 185/186 重新对齐 Step 8+，并随 Step 1-12 / Step 9 实现持续校准
关联文档：`185_multi_agent_investment_research_framework_draft.md`、`186_multi_agent_tool_data_access_matrix_draft.md`、`187_handoff_multi_agent_framework_next.md`

## 定位

185 已经定义 multi-agent 投研工作流的角色、主链路、模型档位、循环中止和 skill 拆分原则。186 已经定义每个 agent 的工具权限、数据权限、route 决策权限和 tool-call ledger 草案。187 已经把下一步最小闭环收敛为：先做路由、权限和中止机制，不一次性实现所有 specialist agent。

本文件用于冻结接下来架构更新的执行顺序、代码落点、实现方式和测评规则。它不是新的架构愿望清单，而是 v0.2 multi-agent 改造的实施手册。

## 总体原则

1. 保留当前单链路作为默认可回滚路径，multi-agent router 初期必须通过配置或独立 graph builder 开启。
2. 先实现 schema、registry、validator、ledger 和 mock routing，再接真实 LLM。
3. Research Lead 只输出业务层激活计划和证据需求，不直接决定物理索引路径。
4. 物理 route 继续由 deterministic compiler 编译，Evidence Operator 通过 MCP registry 执行。
5. Memo Writer 不调用检索工具，Verifier 不生成新投资观点，Reflection 不绕过 compiler 执行二次检索。
6. 所有模型输出先过 schema 和权限校验，再进入 LangGraph 下游节点。
7. 循环中止规则是架构功能，不是调试补丁；duplicate call、预算超限和无增益 second pass 都必须可测试。
8. Specialist Analyst、Universe / Relationship 深度接入、web/news 工具先作为后续阶段，不阻塞第一批合同和路由测试。

## 185/186 落地映射补充

本节补齐 185/186 中更细的 multi-agent 设计如何落成代码、prompt、权限 gate 和数据边界。后续实现不得只按 Step 列表推进；每一步都必须回到本节检查是否破坏 role-specific skill、agent 权限矩阵和工具/数据源归属。

### A. Role-specific Skill 落地矩阵

185 的原则是：所有模型型 agent 共享一份 evidence boundary core skill，每个 role 再注入短 skill，不把完整长文档塞给每个 agent。188 后续实现按下表落地：

| Skill | 对应 agent | Prompt 文件 / loader | 当前落地状态 | 输出合同 | Gate |
| --- | --- | --- | --- | --- | --- |
| `shared_evidence_boundary` | 所有模型型 agent | `shared_evidence_boundary_skill_v0_1.md` / `research_skill_prompt()` | 已落地 | 所有模型输出的 source-boundary 前置规则 | skill 文本不得包含私有路径、凭据、未注册工具；所有 LLM route prompt 必须包含 shared core |
| `research_lead_planning` | Research Lead | `research_lead_planning_skill_v0_1.md` | 已落地 | `AgentActivationPlan` | Lead 不得选择物理 index / BM25 path / DuckDB path；真实 5-case activation gate 必须通过 |
| `coverage_reflection` | Coverage / Reflection | `coverage_reflection_skill_v0_1.md` | 已落地 | `CoverageReflectionReport` / second-pass requests | Reflection 只输出 second-pass request，不直接执行 route；无增益 second pass 必须中止 |
| `memo_writer` | Memo Writer | `memo_writer_skill_v0_1.md` | 已落地 core，真实 multi-agent memo 待接 | `MemoDraft` / rendered memo | Memo Writer 只消费 verified judgment plan，不消费 raw context 或触发检索 |
| `verification` | Verifier | `verification_skill_v0_1.md` | 已落地 core | `VerificationReport` / specialist verification | Verifier 不生成新观点、不扩范围、不触发检索 |
| `fundamental_analysis` | Fundamental Analyst | Step 11B/12 新增 prompt 文件 | 待拆细；当前 parser 先用短 role instruction | `SpecialistMemolet` | supported observation 必须有 SEC/ledger evidence refs；不能使用 market/industry 替代公司披露 |
| `market_valuation_analysis` | Market / Valuation Analyst | Step 11B/12 新增 prompt 文件 | 待拆细；当前 parser 先用短 role instruction | `SpecialistMemolet` | 必须保留 `snapshot_id` / `as_of_date` 语境；不能覆盖 SEC 财务事实 |
| `risk_counterevidence` | Risk / Counterevidence Analyst | Step 11B/12 新增 prompt 文件 | 待拆细；当前 parser 先用短 role instruction | `SpecialistMemolet` | unsupported named facts 必须进 `unsupported_claims` 或 `conflicts` |
| `relationship_universe` | Universe / Relationship | Step 14 新增 prompt 文件 | 未接真实 LLM | `UniverseRelationshipPlan` | 关系图只能支持 scope/hypothesis，不能支持公司财务事实 |
| `evidence_operator_tool_use` | SEC/8-K/Market/Industry Operator | 如需模型化 operator 再新增；初版 operator 为 deterministic tool node | 暂不接 LLM | MCP tool observation | Operator 不拼物理路径，所有调用经 MCP registry + ledger |
| `judgment_plan_aggregation` | Judgment Plan Aggregator | Step 13 新增短 skill 或 deterministic aggregator | 当前 deterministic aggregator 已保留冲突 | `MultiAgentJudgmentPlan` | 冲突不得平均、不得覆盖；unsupported claims 不得进入 Memo Writer |

执行细节：

- `research_skills.py` 必须维护 `SKILL_FILES` 和 `ROLE_SKILLS`，skill id 与 `agent_registry.skill_ids` 对齐。
- 新增任何模型型 agent 前，先新增或确认其 skill id、输出 schema、validator、prompt 注入测试。
- Specialist skill 初期允许先用短 role instruction，但进入真实 Specialist LLM diagnostic 前必须拆成正式 prompt 文件，并补 `tests/test_research_skills.py`。
- Prompt 不得包含 chain-of-thought 要求，不展示内部逐步推理链；只要求 brief rationale、evidence refs、unsupported claims 和 confidence。

### B. 186 Agent 权限矩阵到代码的映射

186 的权限矩阵不应停留在文档表格，必须映射为 registry 字段、validator 和 runtime gate：

| 186 字段 | 代码字段 / gate | 说明 |
| --- | --- | --- |
| 工具权限 | `agent_registry.tool_permission` + `validate_agent_registry()` + `validate_operator_tool_call()` | `none` / `inspect_only` / `request_only` / `bounded_execute` / `orchestrate_subgraph` 必须被代码枚举检查 |
| 数据权限 | `agent_registry.allowed_data_views` + role input builder | `summary_only`、`source_inventory`、`bounded_rows`、`verified_summary` 等决定每个节点能看到什么 payload |
| Route 权限 | `agent_registry.route_authority` + compiler boundary | Lead/Universe/Reflection 只 suggest business need；物理 route 由 compiler 生成；只有 operator 执行 route |
| 可用工具 | `agent_registry.allowed_tools` + MCP registry | tool name 必须存在于 MCP contract；operator 只能调用自己的 allowlist |
| 不允许项 | registry hard rules + node tests | Memo Writer/Renderer 必须无工具；Verifier inspect-only；Research Lead 不得有 retrieval tools |
| 模型档位 | `agent_registry.model_profile` + `AgentActivationPlan.model_policy_hint` | 使用抽象 `none` / `fast` / `balanced` / `strong`，不在 graph 节点写死供应商模型 |
| 预算 | `agent_registry.max_tool_calls` + `LoopBudget` / `ToolCallLedger` | 总工具预算、单 agent 预算、repair、second-pass 都必须可审计 |
| skill id | `agent_registry.skill_ids` + `research_skills.py` | registry 声明的 skill 必须能加载；未知 skill fail closed |

硬规则：

- Research Lead：`request_only`，只能看 summary/source inventory/run artifact ref；不调用 retrieval tools。
- Universe / Relationship：`request_only`，只输出 relationship scope/evidence needs；不能输出财务结论。
- SEC / 8-K / Market / Industry Operator：`bounded_execute`，只通过 MCP registry 调工具，不直接读物理路径。
- Coverage / Reflection：`orchestrate_subgraph`，只发 second-pass request，不绕过 compiler。
- Specialist Analyst：`inspect_only` 或 `none`，只消费 bounded rows / summaries，不检索、不改 route。
- Judgment Plan Aggregator：`inspect_only`，只整理 analyst outputs / coverage / verifier constraints，不检索、不忽略冲突。
- Memo Writer：`none`，只消费 verified summaries / judgment plan，不读 raw rows、不检索。
- Verifier：`inspect_only`，检查 claim support/source boundary，不生成新观点、不触发检索。
- Renderer：`none`，只格式化最终答案，不改写事实。

每个权限规则至少要有一个对应测试：

- registry 层：`tests/test_multi_agent_agent_registry.py`
- activation 层：`tests/test_multi_agent_activation_plan.py`
- runtime operator 层：`tests/test_multi_agent_operator_permissions.py`
- specialist/memo 层：`tests/test_multi_agent_contracts.py`、`tests/test_multi_agent_langgraph_routing.py`

### C. 工具和数据源归属落地矩阵

186 的工具和数据源归属决定了每个 source family 能支持什么 claim，以及由哪个 agent 通过什么方式访问：

| Source / Tool | 执行 agent | 下游可见数据视图 | 支持的 claim scope | 禁止用法 | Runtime gate |
| --- | --- | --- | --- | --- | --- |
| `sec_search_filings` | `sec_operator` / `eight_k_operator` | `bounded_rows` / artifact refs | filing text、管理层解释、风险因素、8-K commentary | 模型直接读 BM25/ObjectBM25 path；8-K commentary 写成审计事实 | `validate_operator_tool_call()` + `ToolCallLedger` + source tier boundary |
| `sec_query_exact_value_ledger` | `sec_operator` | `bounded_rows` / ledger rows | 公司披露的结构化财务事实 | 支持管理层叙事或市场反应 | ledger row role / metric family validator |
| `market_get_snapshot` | `market_operator` | market summary rows | 市场反应、估值、事件窗口、相对收益 | 覆盖 SEC 财务事实；缺 `snapshot_id` / `as_of_date` 仍放行 | `validate_tool_observation_boundary()` |
| `industry_get_snapshot` | `industry_operator` | industry summary rows | 宏观、行业、商品、监管、需求背景 | 支持公司特定收入/利润/现金流事实 | `allowed_claim_scope=industry_context_only` |
| relationship graph lookup | future relationship operator / Universe | relationship summary rows | scope expansion、peer/customer/supplier hypothesis | 凭关系图推导财务数值；无证据扩大全市场 | `UniverseRelationshipPlan` validator |
| run artifact inspect | Coverage / Reflection、Verifier、Workbench | summary/ref only | checkpoint、coverage、ledger、gates、trace inspection | Memo Writer 读 raw artifact；把 debug artifact 当事实证据 | artifact allowlist + bounded bytes |
| raw filing / raw private data | no model agent | 不开放 | 离线 parser/build 阶段 | 在线 agent 直接读取 | 不进入 agent data views |

数据视图裁剪规则：

- `summary_only`：Research Lead / Universe 只看 source inventory、scope summary 和 artifact refs。
- `bounded_rows`：Specialist / Verifier 可看已经裁剪的 evidence rows，但不能拿到物理路径或无限文本。
- `database_query`：只存在于 bounded operator tool 内部，模型 agent 不直接访问。
- `verified_summary`：Memo Writer 的主输入，只能来自 Judgment Plan + verifier constraints。
- `tool_trace_summary`：Coverage / Reflection / Workbench 可见，用于审计和二次检索决策。

Gate：

- 任一 node 输出如果把 source family 用错 claim scope，必须被 verifier 或 deterministic gate 降级/阻断。
- Workbench trace 只显示 refs、row counts、source gaps、digest、boundary summary，不显示 raw evidence 全文或私有路径。
- 任何新增工具先进入 MCP contract 和 agent registry，再进入 runtime node；不能在 graph 节点内临时调用脚本或数据库。

### D. 185 主链路到 LangGraph 节点的映射

185 的主链路应按以下节点 / subgraph 保持职责隔离：

```text
load_session_state
-> research_lead_plan
-> validate_activation_plan
-> optional universe_relationship_expand
-> compile_evidence_requirements
-> compile_retrieval_plan / compile_multi_agent_retrieval_plan
-> execute_evidence_operators
-> coverage_reflection
-> optional_second_pass
-> optional_specialist_subgraph
-> aggregate_judgment_plan
-> pre_memo_specialist_verification
-> memo_writer
-> verifier
-> renderer
-> persist_session_state
```

当前实现中 `pre_memo_specialist_verification` 已内嵌在 `aggregate_judgment_plan` 到 `memo_writer` 之间；后续如果节点复杂化，可拆成显式 node。

## 冻结的初版决策

### Execution Mode

初版只保留 185 的四档：

| 模式 | 初版含义 | 备注 |
| --- | --- | --- |
| `deterministic_lookup` | 单指标查询、状态查看、artifact inspection、明确来源检查 | 不新增 `artifact_inspection` 模式，先归入此类 |
| `focused_answer` | 单公司或少数公司、主题明确、source 范围明确 | 可调用对应 Evidence Operator 和 Coverage |
| `standard_memo` | 多公司比较、基本面 + 管理层解释 + 市场反应 | 可激活少量 analyst stub，但初版不强制真实 specialist |
| `deep_research` | 产业链、上下游、跨行业、relationship expansion | 初版只验证激活和边界，不一次性跑完整深度链路 |

Follow-up 不新增独立 execution mode；使用 graph state 中的 `turn_context.is_followup=true` 或 ContextManager summary 作为 Lead Agent 输入。

### Agent Activation

`AgentActivationPlan.activate_agents` 使用 agent id，不让模型直接选择 subgraph id。Subgraph 由 deterministic router 根据 execution mode 和 agent registry 派生，避免模型绕过权限边界。

Lead Agent 可以建议业务证据优先级和轻量预算 hint，但不能直接写入物理 `candidate_budget`、`rerank_budget` 或索引路径。物理预算由 route compiler 在全局上限内计算和 clamp。

### Feature Flag

第一批实现应提供一个禁用默认值，例如：

```text
SEC_AGENT_ENABLE_MULTI_AGENT_ROUTER=0
```

默认路径继续走现有 `plan_query -> validate_query_contract -> compile_retrieval_plan -> execute_retrieval_routes` 链路。只有测试和显式 smoke 开启 multi-agent router。

## 执行步骤

### Step 0：基线确认和文档冻结

目标：

- 确认当前分支、最近提交、未提交文件和 worklog 入口。
- 不改运行代码，先把 188 作为执行依据。

检查项：

- `git status --short --branch`
- `git log -1 --oneline`
- 读取 185/186/187 和 `docs/worklog/README.md`

验收：

- 188 写清楚代码落点、测试策略和 stop/proceed 规则。
- README 和 master checklist 有 188 入口。
- 无真实模型调用、无数据构建、无运行链路改动。

### Step 1：AgentActivationPlan schema 和 validator

建议新增：

- `src/sec_agent/agent_contracts.py`
- `tests/test_multi_agent_activation_plan.py`

核心对象：

```python
SCHEMA_VERSION = "sec_agent_agent_activation_plan_v0.1"

class ExecutionMode(str, Enum):
    DETERMINISTIC_LOOKUP = "deterministic_lookup"
    FOCUSED_ANSWER = "focused_answer"
    STANDARD_MEMO = "standard_memo"
    DEEP_RESEARCH = "deep_research"

@dataclass
class SkippedAgent:
    agent_id: str
    reason: str

@dataclass
class AgentActivationPlan:
    schema_version: str
    execution_mode: str
    activate_agents: list[str]
    skip_agents: list[SkippedAgent]
    allowed_source_families: list[str]
    model_policy_hint: dict[str, str]
    max_tool_calls_total: int
    max_second_pass_rounds: int
    max_repair_rounds: int
    reasoning_summary: str
```

Validator 必须检查：

- `execution_mode` 属于允许枚举。
- `activate_agents` 全部存在于 agent registry。
- 每个被跳过的可选 agent 都有非空 `reason`。
- 每个 execution mode 至少包含所需核心 agent。
- `allowed_source_families` 存在于 source inventory 或当前工具合同。
- `model_policy_hint` 只能使用 `fast`、`balanced`、`strong`、`none` 等抽象 profile。
- 总工具预算、二次检索轮数和 repair 轮数不超过全局上限。
- Focused 查询不能无理由扩大到 full universe。
- Memo Writer、Verifier、Renderer 不能出现在会执行检索工具的权限路径中。

验收测试：

- 合法 plan 通过。
- 未知 agent、未知 source family、非法 mode、预算超限、skip reason 为空都失败。
- Memo Writer 带检索工具权限时失败。
- `deep_research` 激活关系/产业链范围但未提供 inclusion rationale 时失败或降级为需要澄清。

### Step 2：Agent Registry 和权限校验

建议新增：

- `src/sec_agent/agent_registry.py`
- `tests/test_multi_agent_agent_registry.py`

实现方式参考 `src/sec_agent/mcp_contracts.py`：用代码中的稳定 registry 作为主合同，并提供 export/validate 方法。不要先散落多个 JSON 文件。

每个 registry entry 至少包含：

```python
{
    "agent_id": "research_lead",
    "role": "Research Lead Agent",
    "tool_permission": "request_only",
    "allowed_tools": ["run_inspect_artifacts"],
    "allowed_data_views": ["summary_only", "source_inventory"],
    "route_authority": "suggest_business_need",
    "model_profile": "balanced",
    "max_tool_calls": 0,
    "skill_ids": ["shared_evidence_boundary", "research_lead_planning"],
    "input_schema": "ResearchLeadInputV0",
    "output_schema": "AgentActivationPlanV0"
}
```

初版 registry 应覆盖：

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

权限硬规则：

- `memo_writer.allowed_tools == []`
- `renderer.allowed_tools == []`
- `verifier.tool_permission == inspect_only`
- `research_lead.tool_permission == request_only`
- Evidence Operator 只允许调用自己 source family 的 MCP 工具。
- 没有初版 agent 拥有 `raw_source_read`。
- `execute_route` 只允许 Evidence Operator 工具节点拥有。

验收测试：

- Registry 无重复 id。
- Registry 中每个 tool 都存在于 MCP tool contracts 或被明确标记为 future/disabled。
- 权限矩阵和 186 不冲突。
- Export payload 不包含本地私有路径或凭据。

### Step 3：ToolCallLedger、LoopBudget 和中止机制

建议新增：

- `src/sec_agent/tool_call_ledger.py`
- `tests/test_multi_agent_tool_call_ledger.py`

核心对象：

```python
@dataclass
class ToolCallRecord:
    turn_id: str
    agent_id: str
    tool_name: str
    arguments_digest: str
    input_artifact_digests: list[str]
    output_artifact_digest: str
    row_count: int
    source_gap_count: int
    coverage_delta: dict[str, int]
    elapsed_ms: int
    status: str

@dataclass
class LoopBudget:
    max_graph_steps: int = 24
    max_tool_calls_total: int = 12
    max_tool_calls_per_agent: int = 4
    max_second_pass_rounds: int = 2
    max_repair_rounds: int = 2
    max_same_tool_same_args: int = 1
```

实现细节：

- `arguments_digest` 使用 stable JSON：排序 key、移除时间戳/输出目录等 volatile 字段、统一 ticker 大小写。
- `agent_id + tool_name + arguments_digest` 在同一 turn 内重复出现时返回 `duplicate_tool_call_blocked`。
- Tool call 先 `can_call_tool()`，再执行 MCP handler，最后 `record_tool_call()`。
- 二次检索后必须计算 `coverage_delta.closed_gaps`、新增 row count、source gap 变化。
- 无新增 rows 且无 closed gaps 时，设置 `loop_break_reason=no_incremental_evidence`。
- repair 后 verifier failure 没减少时，设置 `loop_break_reason=repair_no_progress`。

验收测试：

- 相同参数重复调用被阻断。
- 同一工具不同 ticker/year 不被误判为重复。
- 工具总预算和单 agent 预算分别生效。
- Second pass 预算耗尽后不能继续触发检索。
- 无 coverage delta 的 second pass 进入 bounded answer，而不是继续循环。

### Step 4：Research Lead mock / deterministic fixture 路由

建议新增：

- `src/sec_agent/multi_agent_router.py`
- `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`
- `tests/test_multi_agent_routing_fixtures.py`

第一阶段不接真实 LLM。先用 deterministic fixture 或 mock Lead 输出 `AgentActivationPlan`，验证路由和权限。

建议 fixture：

| Case | Prompt 类型 | 期望 mode | 必须激活 | 禁止激活 |
| --- | --- | --- | --- | --- |
| `ma_msft_capex_lookup` | 单公司单指标单期间 | `deterministic_lookup` | `sec_operator` or direct lookup renderer | `universe_relationship`, specialist agents |
| `ma_amzn_margin_focused` | 单公司基本面解释 | `focused_answer` | `research_lead`, `sec_operator`, `coverage_reflection`, `memo_writer`, `verifier` | `universe_relationship` unless reason exists |
| `ma_nvda_amd_market_standard` | peer + 市场反应 | `standard_memo` | SEC/8-K/market operators, coverage, memo, verifier | raw source read |
| `ma_ai_capex_supply_chain_deep` | 产业链/跨行业 | `deep_research` | `universe_relationship`, industry/market/SEC operators, coverage | unbounded full universe |
| `ma_run_coverage_inspect` | 查看已有 run coverage | `deterministic_lookup` | `run_inspect_artifacts` path | Evidence Operator retrieval |

验收：

- Fixture exact mode accuracy 为 100%。
- Forbidden agent activation 为 0。
- 每个 skip agent 都有 reason。
- 每个 fixture 的预算低于全局上限。

### Step 5：LangGraph state 和条件分支接入

建议更新：

- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/graph_state.py`
- `tests/test_sec_agent_langgraph_orchestrator.py`
- 可新增 `tests/test_multi_agent_langgraph_routing.py`

状态新增字段：

```python
agent_activation_plan: dict[str, Any]
agent_registry_snapshot: dict[str, Any]
tool_call_ledger: list[dict[str, Any]]
loop_budget_state: dict[str, Any]
agent_trace: list[dict[str, Any]]
loop_break_reason: str
bounded_answer_allowed: bool
```

建议节点演进：

```text
load_session_state
-> research_lead_plan
-> validate_activation_plan
-> route_by_execution_mode
-> compile_evidence_requirements
-> evidence_operator_subgraph
-> coverage_reflection
-> optional_second_pass
-> optional_specialist_subgraph
-> aggregate_judgment_plan
-> memo_writer
-> verifier
-> renderer
-> persist_session_state
```

为了降低风险，初版可以新增 `build_multi_agent_orchestration_graph()`，保留现有 `build_native_orchestration_graph()` 不变。等 smoke 和 regression 通过后，再考虑合并节点命名。

分支策略：

- `deterministic_lookup`：只走工具 lookup / artifact inspect / renderer，不进入 full memo。
- `focused_answer`：只执行必要 source family，不激活 Universe 和 specialist。
- `standard_memo`：允许激活 Fundamental、Market、Risk 的轻量 stub，但可以先不接真实 LLM。
- `deep_research`：初版验证 Universe activation、scope guard 和预算，不伪装完整产业链结论。

验收：

- 旧 graph builder 的测试不回归。
- 新 graph builder 能用 mock nodes 跑完四种 mode。
- `native_stop_after_node` / checkpoint 机制仍能保存新状态字段摘要。
- 状态 artifact 不写入大 payload 或私有路径内容，只写 refs、摘要和 digest。

### Step 6：Evidence Operator subgraph 和 MCP registry 桥接

建议更新：

- `src/sec_agent/mcp_tool_registry.py`
- `src/sec_agent/retrieval_plan.py`
- `src/sec_agent/langgraph_orchestrator.py`
- `tests/test_sec_agent_mcp_runtime_tools.py`
- `tests/test_multi_agent_operator_permissions.py`

实现方式：

1. Research Lead / Reflection 输出业务层 `EvidenceRequirementPlan`。
2. `build_retrieval_plan()` 编译为 route tasks。
3. Tool validator 检查 agent 权限、source tier、route、budget 和重复调用。
4. Evidence Operator 通过 `invoke_mcp_tool()` 执行 `sec_search_filings`、`sec_query_exact_value_ledger`、`market_get_snapshot`、`industry_get_snapshot`。
5. 工具输出统一写回 graph state：rows、artifact refs、candidate counts、source gaps、elapsed_ms。
6. `tool_call_ledger` 记录每个调用。

禁止实现：

- Agent node 直接读取 BM25/ObjectBM25/DuckDB 本地路径。
- Shell 脚本包完整 DAG 后再解析最后 artifact。
- Memo Writer 或 Verifier 临时发起新检索。

验收：

- 同一 `EvidenceRequirementPlan` 在 CLI mock、Workbench mock、MCP registry 中得到一致 route intent。
- SEC Operator 不能调用 market/industry 工具。
- Market Operator 返回 `snapshot_id` 和 `as_of_date`，缺失则不能支持市场 claim。
- Industry Operator 输出只进入背景/解释，不支持公司财务事实。

### Step 7：Coverage / Reflection 二次检索闭环

建议更新：

- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/retrieval_plan.py`
- `tests/test_multi_agent_reflection_second_pass.py`

结构化输出：

```json
{
  "sufficiency_level": "partial",
  "missing_requirements": [],
  "source_available": true,
  "second_pass_requests": [],
  "needs_user_clarification": false,
  "bounded_answer_allowed": true,
  "confidence_by_claim_type": {}
}
```

执行规则：

- 第一轮 coverage 后必调 Reflection。
- 二次检索只针对缺口 source family，不重跑全部 operator。
- Second pass request 仍需通过 route compiler 和 tool validator。
- 执行后必须重新计算 coverage。
- 若 closed gaps 为 0 且新增 rows 为 0，停止循环并允许 bounded answer。

验收：

- “建议补查 10-Q/8-K”类 fixture 能触发一次 second pass。
- Source 不存在时不触发工具调用，进入 bounded answer 或 clarification。
- 超过 `max_second_pass_rounds` 后停止。
- 同一工具同一参数不会被二次调用。

### Step 8：185/186 角色、skill、权限矩阵对齐

业务目标：

- 把 185/186 中定义的全部 agent 角色、role-specific skill、工具权限、数据权限和 route 权限先冻结为代码合同。
- 不让后续 LLM route 或 graph node 凭 prompt 约定越权；所有角色边界必须能由 registry / validator / test 检查。

必须覆盖的 185/186 角色：

| 角色族 | Agent id | 初版状态 | 必须具备的边界 |
| --- | --- | --- | --- |
| Lead | `research_lead` | 已落地 | request-only，只输出 activation / evidence requirements，不接触物理 route |
| Universe | `universe_relationship` | 合同已落地，真实 route 待 Step 14 | relationship evidence 只支持 scope / hypothesis |
| Evidence Operators | `sec_operator`、`eight_k_operator`、`market_operator`、`industry_operator` | 已落地 | bounded_execute，只经 MCP registry / compiler 执行 |
| Reflection | `coverage_reflection` | 已落地 | orchestrate_subgraph，只发 second-pass request |
| Specialists | `fundamental_analyst`、`industry_supply_chain_analyst`、`market_valuation_analyst`、`risk_counterevidence_analyst` | 四类 specialist 均已进入 registry / skill / contract；Universe 真实 route 仍待 Step 14 | inspect-only 或 none，只消费 bounded rows，不检索 |
| Aggregator | `judgment_plan_aggregator` | 合同初版已落地 | inspect-only，保留冲突和 unsupported，不生成新事实 |
| Writer / verifier / renderer | `memo_writer`、`verifier`、`renderer` | 已落地基础权限 | Memo/Renderer 无工具；Verifier inspect-only，不生成新观点 |

实现要求：

- `agent_registry.skill_ids` 必须全部能由 `research_skills.py` 加载；未知 skill id fail closed。
- 每个模型型 agent 注入 `shared_evidence_boundary` + 自己的短 role skill，不把 185/186 全文塞进 prompt。
- Registry 必须显式记录 `tool_permission`、`allowed_data_views`、`route_authority`、`allowed_tools`、`source_families`、`model_profile`、`max_tool_calls`、`skill_ids`。
- 对 185/186 中出现但暂不启用的角色，必须选择一种方式：要么进入 registry 并受 feature flag / activation gate 控制，要么在 188 中明确标记为 deferred，并说明阻塞条件。

当前对齐状态：

- 已补齐 Lead、Reflection、Memo Writer、Verifier、Fundamental、Industry/Supply-Chain、Market-Valuation、Risk-Counterevidence、Universe、Evidence Operator、Judgment Aggregator、Renderer 的 role-specific skill prompt 和 loader 映射。
- Specialist LLM 已改为 `research_skill_prompt(agent_id)` 注入正式 skill。
- 原 gap 已处理：185/186 中的 `Industry / Supply Chain Analyst` 已进入 registry、activation gate、skill prompt、SpecialistMemolet contract、bounded fixture 和 graph specialist list。Step 14 剩余工作是 Universe / Relationship 真实扩展和 relationship graph 数据源接入。

Gate：

```text
pytest tests/test_research_skills.py tests/test_multi_agent_agent_registry.py -q
```

Stop 条件：

- 文档中存在 agent / skill / data source，但 registry 或 loader 没有对应合同。
- Specialist、Memo Writer、Verifier 获得 retrieval tool authority。
- Prompt 要求模型自行选择物理 route、索引路径、数据库路径或私有文件。

### Step 9：EvidenceRequirementPlan 与 data-view builder

业务目标：

- 把 185 的“Research Lead / Universe / Reflection 提出证据需求，compiler 决定怎么查”落成显式中间合同。
- 当前 `AgentActivationPlan` 只解决“激活谁”，还不够表达“每个 claim 需要什么证据、source family、ticker、period、operator owner”。Step 9 必须补上这个业务合同。

建议新增 / 更新：

- `src/sec_agent/multi_agent_contracts.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/langgraph_orchestrator.py`
- `tests/test_multi_agent_evidence_requirements.py`

核心合同：

```json
{
  "schema_version": "sec_agent_evidence_requirement_plan_v0.1",
  "requirements": [
    {
      "requirement_id": "req_fundamental_revenue",
      "claim_family": "company_reported_financial_fact",
      "tickers": ["NVDA"],
      "period_roles": ["annual", "quarterly"],
      "source_families": ["primary_sec_filing"],
      "operator_owner": "sec_operator",
      "required_fields": ["revenue", "gross_margin"],
      "priority": "primary",
      "reason": "Needed for fundamental comparison"
    }
  ],
  "source_boundary_notes": [],
  "unsupported_requirements": []
}
```

实现要求：

- Lead / Universe / Reflection 只能输出 business-level requirements。
- Deterministic compiler 把 requirements 编译为 existing `RetrievalPlan` / MCP tool calls。
- Data-view builder 根据 registry 的 `allowed_data_views` 裁剪每个 agent 输入：
  - Lead / Universe：summary / inventory / refs。
  - Operators：database_query 只在 tool 内部。
  - Specialists / Verifier：bounded rows / coverage summary。
  - Memo Writer：verified judgment summary only。
- Bounded rows 必须剥离物理路径、raw全文、private data marker，只保留 evidence ref、source family、ticker、period、summary、必要数值和 snapshot context。

Gate：

```text
pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_operator_permissions.py -q
```

当前实现状态：

- 已新增 `build_multi_agent_evidence_requirement_plan()`，复用现有 `EvidenceRequirementPlan` schema 并补充 `source_families`、`operator_owners`、`claim_families`、`route_intents` 和 planner boundary。
- 已新增 `validate_multi_agent_evidence_requirement_plan()`，检查 source family / operator owner 与 deterministic route mapping、activation allowed source families、agent registry source ownership 是否一致。
- 已新增 `build_agent_data_view()`，按 registry `allowed_data_views` 裁剪 Lead / Specialist / Memo Writer / Verifier / Operator 输入，剥离 raw text、物理路径和 private data marker。
- `compile_evidence_requirements` graph node 现在把 `evidence_requirement_plan` 写入 graph state，并用 multi-agent compiler 生成 retrieval plan。

Stop 条件：

- Lead / Universe 直接写 route name、BM25 path、DuckDB path、candidate budget。
- Memo Writer 输入仍包含 raw context rows。
- Market / industry / relationship rows 被标记为可支持公司披露财务事实。

### Step 10：Research Lead 真实 LLM 从 activation 扩展到 evidence requirements

业务目标：

- 真实 Lead LLM 不只做 execution mode 和 agent activation，还要输出初始 EvidenceRequirementPlan 草案。
- 该草案只表达业务需求，不决定物理 route。

当前状态：

- 真实 Research Lead LLM activation route 已通过 5-case DeepSeek 诊断 gate。
- 已扩展为兼容 `activation_plan + evidence_requirement_plan` 的 ResearchLeadOutput：旧 activation-only gate 仍可通过；新 EvidenceRequirementPlan 进入 Step 9 validator。
- 缺省不强制真实 LLM 必须输出 evidence requirements；可通过 `RESEARCH_LEAD_REQUIRE_EVIDENCE_REQUIREMENTS=1` 或诊断脚本参数开启硬门控。缺失时允许 deterministic compiler fallback，并在 routing trace 标记。

实现要求：

- 扩展 Lead output schema 或新增 sibling schema：`AgentActivationPlan` + `EvidenceRequirementPlan`。
- 保留现有 activation gate 作为硬前置，不破坏已通过的 5-case routing fixture。
- Lead evidence requirements 必须经过 validator：source family、operator owner、claim family、scope、budget、用户授权范围。
- Repair 失败时 fail closed；允许 deterministic requirements compiler 作为显式 fallback，但必须在 trace 中标记。

Gate：

```text
pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_evidence_requirements.py -q
python scripts/eval_multi_agent_research_lead_activation.py --strict --require-evidence-requirements
```

Stop 条件：

- Lead LLM 把 business requirement 写成物理 route。
- 简单 deterministic lookup 被扩展成 full universe。
- EvidenceRequirementPlan 无法解释 source boundary 或 operator owner。

### Step 11：Coverage / Reflection 与 second-pass 闭环业务化

业务目标：

- Reflection 不是一个泛泛的“再检查一下”，而是 185 中的证据充足性决策节点。
- 它必须判断 sufficient / partial / insufficient，决定是否 second-pass、clarification 或 bounded answer。

当前状态：

- 已有 loop budget、duplicate call guard、no-gain second pass guard 和 mock graph 接入。
- 已完成 Reflection 缺口到 EvidenceRequirementPlan `requirement_id` / `task_id` 的绑定。
- 已完成 source-family gap、operator owner、route intent、claim family 到 `CoverageReflectionReport` 和 second-pass request 的传递。
- 已完成 second-pass request 回编成 EvidenceRequirementPlan，再走 deterministic retrieval-plan compiler 的接口；Reflection 不直接执行物理 route。

实现要求：

- Reflection 输入：coverage matrix、source gaps、tool ledger summary、EvidenceRequirementPlan。
- Reflection 输出：`CoverageReflectionReport`，包含 `missing_requirements`、`source_available`、`second_pass_requests`、`bounded_answer_allowed`、`needs_user_clarification`。
- Second-pass request 必须回到 deterministic compiler，再由 operator 执行。
- 执行后必须比较新增 rows、ledger facts、closed gaps、sufficiency level；无增益则停止。

Gate：

```text
pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_tool_call_ledger.py -q
```

当前验证：

- 2026-05-30 本地已通过 `pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_tool_call_ledger.py -q`，结果 `17 passed`。
- 受影响 graph / EvidenceRequirementPlan 测试已通过 `pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_evidence_requirements.py -q`，结果 `11 passed`。
- 全量回归已通过 `pytest -q`，结果 `328 passed`。

Stop 条件：

- Reflection 直接调用工具或绕过 compiler。
- 二次检索重跑所有 source family。
- 无新增 rows / closed gaps 仍继续循环。

### Step 12：Specialist Analysis Subgraph 诊断接入

业务目标：

- 把 185 的 Specialist map-reduce 先做成可验证的中间判断层，而不是直接接最终写作。
- Specialist 只输出局部 memolet、证据强度、反证条件和 unsupported claims。

当前状态：

- Fundamental / Industry-Supply-Chain / Market-Valuation / Risk 四类 SpecialistMemolet parser、repair、fail-closed 已落地。
- 真实 Specialist LLM 诊断脚本和 4-case bounded fixture 已落地；真实 strict run 依赖环境变量中的模型 key，不把 key 写入文档或 fixture。
- Industry / Supply Chain Analyst 已能消费 `industry_snapshot` 和 `relationship_graph` bounded summaries；relationship graph 的真实 Universe 扩展仍归 Step 14。

实现要求：

- Specialist input 必须来自 data-view builder 的 bounded rows，不得读 raw context / physical path。
- 每个 specialist 独立 prompt，shared evidence boundary + role skill。
- 支持 fake/injected LLM、真实 diagnostic-only LLM 和 graph feature flag 三种模式。
- 真实 LLM 诊断只验证 memolet，不接 Memo Writer、不跑 full chain。
- Risk analyst 的 unsupported/conflict 输出必须保留到 Judgment Plan。

Gate：

```text
pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_contracts.py -q
python scripts/eval_multi_agent_specialist_memolet.py --strict
```

Stop 条件：

- Specialist tool call 不被拒绝。
- Supported observation 缺 evidence refs 或引用未知 refs 仍通过。
- Unsupported named facts 被写成 supported observation。
- Industry / supply-chain relationship 被用来支持公司财务数值。

### Step 13：Judgment Plan、Memo Writer、Verifier 业务闭环

业务目标：

- 把 185 的“局部 analyst -> judgment plan -> memo writer -> verifier -> repair/bounded answer”做成真正的业务闭环。
- Step 13 不追求最终 LLM 文采，而是先保证冲突、source boundary、unsupported claims 和 memo constraints 在 graph state 中不可丢失。

进入条件：

- Step 8 digest gate 无未解释角色缺口，或缺口被明确延期且测试可见。
- Step 9 EvidenceRequirementPlan / data-view builder 至少有 deterministic fixture。
- Step 12 Specialist memolet fixture-backed gate 通过；真实 Specialist LLM 可为 diagnostic-only，不能阻塞 deterministic mainline。

建议新增 / 更新：

- `src/sec_agent/multi_agent_contracts.py`
- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/prompts/skills/judgment_plan_aggregation_skill_v0_1.md`
- `src/sec_agent/prompts/skills/memo_writer_skill_v0_1.md`
- `src/sec_agent/prompts/skills/verification_skill_v0_1.md`
- `tests/test_multi_agent_judgment_memo_verifier.py`

实现要求：

1. Judgment Plan Aggregator
   - 输入：specialist memolets、coverage/reflection report、EvidenceRequirementPlan、source gaps、tool ledger summary、verifier constraints。
   - 输出：`MultiAgentJudgmentPlan`，至少包含 `supported_claims`、`conflicts`、`unsupported_claims`、`source_boundary_notes`、`memo_constraints`、`memo_writer_allowed`。
   - 冲突不得平均、不得覆盖；unsupported 不得丢弃。
   - 当前已落地：`aggregate_specialist_judgment_plan()` 会汇总 supported / conflict / unsupported，并补充 `source_boundary_notes`、`memo_constraints`、`memo_writer_allowed`。

2. Memo Writer
   - 只消费 `verified_judgment_plan` / verified summaries，不消费 raw rows，不检索。
   - 如果 `memo_writer_allowed=false`，输出 bounded blocked answer，而不是写完整 memo。
   - 输出必须带 source boundary、evidence strength、counterevidence / caveats、missing evidence。
   - 当前已落地：deterministic `build_multi_agent_memo_draft()` 只消费 `verified_judgment_plan` / `verified_summary`；若 `memo_writer_allowed=false`，输出 bounded blocked answer。

3. Verifier
   - 检查 Memo Writer output 的 claim support、evidence refs、period role、source family、market `as_of_date`、industry/relationship misuse、unsupported named facts。
   - Verifier 不生成新观点、不扩范围、不触发检索。
   - 可输出 repair instruction；repair 仍失败则 bounded answer。
   - 当前已落地：`verify_multi_agent_memo_draft()` 阻断 raw rows、tool calls、unsupported claim text、market/industry/relationship source-family misuse，并输出 inspect-only repair instruction。

Gate：

```text
pytest tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_contracts.py tests/test_multi_agent_langgraph_routing.py -q
```

当前验证：

- 2026-05-30 本地已通过 `pytest tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_contracts.py tests/test_multi_agent_langgraph_routing.py -q`，结果 `19 passed`。
- 全量回归已通过 `pytest -q`，结果 `335 passed`。

Stop 条件：

- Memo Writer 需要重新检索才能写。
- Verifier 要求新事实或新增观点。
- Judgment Plan 丢弃 specialist conflict。
- Unsupported claims 进入 rendered answer。
- Market / industry / relationship source 被用于支持公司披露财务事实。

### Step 14：Universe / Relationship 与 Industry / Supply Chain Analyst

业务目标：

- 落实 185 的产业链、上下游、客户/供应商、替代风险和行业链条功能。
- Relationship graph 只能支持研究范围和假设，再驱动 EvidenceRequirementPlan，不能直接支持财务事实。

实现要求：

- 新增或完善 `industry_supply_chain_analyst` registry entry、skill、memolet contract 和 data-view builder。
- Universe Agent 输出 `UniverseRelationshipPlan`：included / excluded tickers、relationship type、direction、evidence refs、scope guard、inclusion rationale。
- Relationship expansion 经过 source inventory、budget、scope guard 和 validator。
- Industry / Supply Chain Analyst 只能消费 industry / relationship bounded summaries，输出传导假设、需要验证的 metric、source boundary 和 caveats。

当前状态：

- `industry_supply_chain_analyst` registry / skill / memolet / data-view builder 已在 Step 8/9/12 落地。
- `UniverseRelationshipPlan` 已扩展 included / excluded tickers、scope guard、budget、relationship-level inclusion rationale、metrics to check、evidence source needed。
- validator 已阻断无证据扩展 ticker、source inventory 外 ticker、relationship budget 超限、relationship graph 支持财务事实。
- relationship plan 可生成 business-level evidence requirements；不包含 physical route、tool name 或路径。

Gate：

```text
pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q
```

当前验证：

- 2026-05-30 本地已通过 `pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q`，结果 `15 passed`。
- 扩展合同回归已通过 `pytest tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_contracts.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q`，结果 `21 passed`。
- 全量回归已通过 `pytest -q`，结果 `340 passed`。
- 2026-05-30 Step 14 closeout 已补真实 graph / LLM route：Universe Relationship expansion 已进入 graph，`relationship_graph_lookup` 接入 MCP registry，Memo Writer / Verifier LLM route 已接入，verifier repair loop 已执行 repair 后重验并保留原始违规审计。
- 最新本地全量回归已通过 `pytest -q`，结果 `358 passed`。
- 真实 DeepSeek diagnostic gate：
  - Research Lead activation + EvidenceRequirementPlan strict gate `5/5`，forbidden activation `0`。
  - Specialist memolet strict gate `4/4`，forbidden tool call `0`。
  - Universe Relationship + Memo Writer + Verifier inline smoke 均为 `pass`。
- 详细记录见 `docs/worklog/204_multi_agent_step14_real_llm_graph_closeout.md` 和 `reports/model_runs/20260530_multi_agent_step14_deepseek_graph_closeout_v0_1.md`。

Stop 条件：

- Universe 无证据扩大到全市场。
- 关系图或行业数据被 Memo Writer 用来支持公司财务数值。
- Relationship expansion 导致 tool budget 失控。

### Step 15：Multi-agent full graph feature flag 和 Workbench 产品化

业务目标：

- 让完整 multi-agent path 可以在 Workbench / CLI 中以 feature flag 试运行，但默认旧链路仍可回滚。
- Trace 面向用户只展示可审计摘要，不展示内部逐步推理链、raw evidence 全文或私有路径。

Feature flags：

- `SEC_AGENT_MULTI_AGENT_GRAPH=enabled`
- `SEC_AGENT_MULTI_AGENT_LEAD_ROUTER=deterministic|llm`
- `SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER=mock|llm|off`
- `SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER=mock|llm|off`
- `SEC_AGENT_MULTI_AGENT_MEMO_ROUTER=mock|llm|off`

Workbench 必须能 inspect：

- activation plan
- EvidenceRequirementPlan
- operator observations / tool ledger
- coverage / reflection report
- specialist memolets
- judgment plan
- memo verification / repair or bounded fallback
- loop break and source boundary summary

Gate：

```text
pytest tests/test_workbench_artifacts.py tests/test_workbench_profiles.py tests/test_multi_agent_langgraph_routing.py -q
```

Stop 条件：

- Workbench 因旧 run 缺新 artifact 报错。
- Multi-agent graph 成为默认且无法关闭。
- Trace 泄漏 raw evidence、私有路径或模型逐步推理链。

2026-05-30 执行状态：

- 已通过 `pytest tests/test_workbench_artifacts.py tests/test_workbench_profiles.py tests/test_multi_agent_langgraph_routing.py -q`，结果 `15 passed`。
- Workbench profile 已覆盖 `SEC_AGENT_MULTI_AGENT_GRAPH`、`SEC_AGENT_MULTI_AGENT_LEAD_ROUTER`、`SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER`、`SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER`、`SEC_AGENT_MULTI_AGENT_MEMO_ROUTER`。

### Step 16：真实 multi-agent graph smoke 和 release gate

业务目标：

- 只在合同、权限、data-view、specialist、judgment/memo/verifier gates 全绿后，做少量真实模型 graph smoke。
- 不跑 full238，不把 diagnostic smoke 描述成生产质量。

建议 smoke：

1. `focused_answer`：单公司管理层解释，不激活 specialist 或只激活 Risk verifier。
2. `standard_memo`：NVDA / AMD peer memo，激活 Fundamental / Market / Risk。
3. `deep_research`：AI capex relationship scope，只验证 Universe / scope guard / EvidenceRequirementPlan，不声称完整产业链结论。

通过标准：

- Graph completed 或 bounded partial，不能假成功。
- Tool budget、repair budget、second-pass budget 均可审计。
- Memo / rendered answer 不包含 unsupported specialist claims。
- Deterministic gates 和 verifier gate 无阻断项。
- 模型、配置、token、latency、失败原因写入 model-run ledger。

Stop / rollback：

- 任一真实 smoke 出现 unsupported facts、source boundary 违规、预算失控或旧链路回归，multi-agent graph 保持 diagnostic-only。
- 关闭 feature flags 回到 native graph。

2026-05-30 执行状态：

- 真实 DeepSeek `deepseek-v4-pro` 3-case graph smoke 通过 `3/3`。
- focused case：`focused_answer`、`claim_verification=pass`、rendered answer 非空。
- standard case：`standard_memo`，specialist verification fail 被 bounded block，`claim_verification=pass`，无 unsupported 泄漏。
- deep case：`deep_research`，Universe validation `pass`，relationship graph lookup 接入，post-fix budget probe `loop_break_reason=""`、`tool_call_count=11`。
- 详细记录见 `docs/worklog/205_multi_agent_step15_16_graph_smoke_and_chain_eval.md` 和 `reports/model_runs/20260530_multi_agent_step16_deepseek_graph_smoke_v0_1.md`。

### Step 17：真实 LLM 分层链路评测

业务目标：

- 从 Step16 的少量 graph smoke 扩展到可重复的 per-agent / per-layer eval。
- 同时覆盖 185/186 要求的 Role-specific Skill、agent 权限矩阵、工具与数据源归属、Universe / Relationship route、Specialist memolet、Memo Writer / Verifier repair loop。
- 仍保持 diagnostic-only，不把 bounded dry-run evidence 的通过结果宣传为生产级 memo 质量。

测试用例设计：

1. detailed probe / focused：单公司管理层解释，验证 Research Lead、SEC / 8-K operator、Memo Writer、Verifier，且不错误激活 Universe / Specialist。
2. detailed probe / deep relationship：AI capex / supplier / cloud capex 关系链，验证 Universe Relationship LLM、relationship graph lookup、Industry / Market / Risk / Fundamental specialist 路由、tool ownership、bounded specialist block。
3. single-turn exact lookup：只应走 deterministic lookup / SEC operator，不应升级到 deep research。
4. single-turn standard memo：peer + market + risk 的标准 memo，验证 specialist route results 和 bounded fallback。
5. multi-turn t1：初始 standard memo scope，验证 conversation context 写入和 stale ticker 禁止。
6. multi-turn t2：在同一 conversation 下扩展到 AI infrastructure relationship，验证 scope revision、Universe route 升级和 relationship graph evidence。

评测标准：

- Research Lead：真实 LLM called、validator pass、execution mode match、required agents present、forbidden agents absent、direct tool call count 为 0。
- Universe / Relationship：需要时 LLM called、`relationship_graph_lookup` called、validator pass、relationship claim 只支持 scope/hypothesis。
- Evidence Operators：expected tool names called、agent/tool ownership valid、tool budget 不超限、无 duplicate / budget loop break。
- Specialists：expected route results present、schema valid、unsupported block bounded。
- Memo / Verifier：memo status 必须是允许状态；claim verification pass；bounded answer 必须非空；Verifier 只以 hard boundary errors 阻断，并允许一轮 bounded repair 后复验。
- Payload safety：summary 不含 raw evidence、`sk-` marker、`raw_private` marker；不保存 raw LLM response。

2026-05-30 执行状态：

- 新增 fixture：`tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`。
- 新增 runner：`scripts/eval_multi_agent_real_llm_chain.py`。
- Detailed probe `codex_real_llm_chain_detailed_probe_v0_1`：`2/2 passed`。
- Single + multi-turn repaired gate `codex_real_llm_chain_single_multi_v0_2`：`4/4 passed`。
- Full 6-case final gate `codex_real_llm_chain_full6_v0_3`：`6/6 passed`，`total_tool_calls=35`，`pass_rate=1.0`。
- Deterministic chain performance final `codex_v0_5`：`7/7 passed`。
- Full regression：`371 passed`。
- 详细记录见 `docs/worklog/206_multi_agent_real_llm_layered_chain_eval.md` 和 `reports/model_runs/20260530_multi_agent_real_llm_layered_chain_eval_v0_1.md`。

### Step 18：Specialist 真实 evidence rows 质量评测

业务目标：

- 把 Specialist layer 从 dry-run bounded rows 升级到真实 artifact / evidence rows。
- 评估 Specialist 是否能在真实 ledger、market snapshot、industry snapshot、relationship graph、coverage gap 证据上保持职责边界。
- 仍不允许 Specialist 直接调用工具；工具调用仍归 Evidence Operator。

实现方式：

- fixture 只记录 artifact path、source type、filters、质量期望，不复制 raw filing 全文。
- runner 在执行时 materialize bounded rows：
  - `runtime_ledger_json`：真实 Exact-Value Ledger rows。
  - `market_evidence_jsonl`：真实 market snapshot rows。
  - `industry_evidence_jsonl`：真实行业数据 evidence rows。
  - `relationship_graph_lookup`：真实 relationship / sector-depth lookup rows。
  - `coverage_matrix_json`：真实 coverage gap rows。
- materialized rows 都带 `metadata.real_evidence_row=true` 和 source artifact path。
- Specialist LLM request 仍只接收 bounded rows、coverage summary、source boundaries、known evidence refs。

Gate：

```text
python scripts/eval_multi_agent_specialist_real_evidence_quality.py --materialize-only --strict
pytest tests/test_multi_agent_specialist_real_evidence_eval.py tests/test_multi_agent_specialist_llm.py -q
python scripts/eval_multi_agent_specialist_real_evidence_quality.py --run-id codex_specialist_real_evidence_deepseek_v0_1 --strict
```

通过标准：

- materialize-only：4/4 cases pass，所有 rows 标记为真实 evidence rows。
- LLM quality：4/4 cases pass。
- supported observations 只能引用 known evidence refs。
- source families 不越权。
- Market specialist 不把 market snapshot 当公司基本面事实。
- Industry / Relationship specialist 保留 hypothesis/context-only 边界。
- Risk specialist 对 coverage gap 中的缺失 operating-income support 输出 unsupported/conflict。
- direct tool call count 必须为 0。

2026-05-30 执行状态：

- 新增 `scripts/eval_multi_agent_specialist_real_evidence_quality.py`。
- 新增 `tests/fixtures/multi_agent_specialist_real_evidence_cases_v0_1.jsonl`。
- 新增 `tests/test_multi_agent_specialist_real_evidence_eval.py`。
- `pytest tests/test_multi_agent_specialist_real_evidence_eval.py tests/test_multi_agent_specialist_llm.py -q`：`14 passed`。
- `python scripts/eval_multi_agent_specialist_real_evidence_quality.py --materialize-only --run-id codex_specialist_real_evidence_materialize_v0_3 --strict`：`4/4 passed`，materialized rows `28`。
- 真实 DeepSeek strict gate `codex_specialist_real_evidence_deepseek_v0_1`：`4/4 passed`，materialized rows `28`，`total_latency_ms=77725`，`total_tokens=16574`，direct tool call `0`。
- 详细记录见 `docs/worklog/207_multi_agent_specialist_real_evidence_quality_eval.md` 和 `reports/model_runs/20260530_multi_agent_specialist_real_evidence_deepseek_v0_1.md`。

## 测评规则

### 1. Contract Unit Gate

建议命令：

```text
pytest tests/test_multi_agent_activation_plan.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_tool_call_ledger.py -q
```

通过标准：

- Schema validator 测试 100% 通过。
- Registry 权限测试 100% 通过。
- Loop budget / duplicate call 测试 100% 通过。

Stop 条件：

- Memo Writer 可调用检索工具。
- Evidence Operator 可跨 source family 调工具。
- Duplicate same tool + same args 未被阻断。
- 预算超限仍继续执行。

### 2. Routing Fixture Gate

建议命令：

```text
pytest tests/test_multi_agent_routing_fixtures.py -q
```

通过标准：

- 5/5 fixture mode exact match。
- 必须激活的 agent 全部出现。
- 禁止激活的 agent 全部缺席。
- Skip reason 完整率 100%。
- 每个 plan 均能通过 validator。

Stop 条件：

- 简单单指标问题进入 `deep_research`。
- 单公司 focused 问题无理由激活 Universe。
- Artifact inspection 触发真实检索。

### 3. Graph Smoke Gate

建议命令：

```text
pytest tests/test_multi_agent_langgraph_routing.py tests/test_sec_agent_langgraph_orchestrator.py -q
```

通过标准：

- 四种 execution mode 的 mock graph 能跑到预期终点。
- `stop_after_node` 和 checkpoint artifact 仍可用。
- 新 state 字段不会破坏旧 state hydration。
- Deep research 未实现部分不会伪装成功，应清楚返回 bounded/partial 状态。

Stop 条件：

- 新 graph 破坏现有 native graph 测试。
- Checkpoint 写入大 payload 或原始证据全文。
- Loop break 后仍继续进入同一工具调用。

### 4. MCP / Operator Permission Gate

建议命令：

```text
pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_multi_agent_operator_permissions.py -q
```

通过标准：

- MCP tool contracts 仍全部有效。
- Operator 权限 wrapper 能拦截未授权工具。
- Tool call ledger 能记录 status、row_count、source gaps 和 elapsed_ms。
- Market / industry 输出的 source boundary 被保留。

Stop 条件：

- Agent 绕过 MCP registry 直接读物理索引。
- Market claim 缺少 `as_of_date` 仍被 verifier 放行。
- Industry row 被用于支持公司财务事实。

### 5. Reflection Second-pass Gate

建议命令：

```text
pytest tests/test_multi_agent_reflection_second_pass.py tests/test_sec_agent_retrieval_plan.py -q
```

通过标准：

- 缺口 source 可用时触发 second pass。
- Source 不可用时不调用工具，进入 bounded answer 或 clarification。
- Second pass 后 coverage delta 被记录。
- 无增益 second pass 中止。

Stop 条件：

- Reflection 自行执行物理 route。
- Second pass 重跑全部 source family。
- 无新增证据仍持续循环。

### 6. Workbench Trace Gate

建议命令：

```text
pytest tests/test_workbench_artifacts.py tests/test_workbench_backend.py -q
```

通过标准：

- 旧 run 没有 multi-agent artifact 时仍能 inspect。
- 新 run 可 inspect activation plan、agent trace、tool ledger 和 loop break。
- 用户可见 summary 不暴露内部逐步推理链。

Stop 条件：

- Workbench API 因缺失新 artifact 报错。
- Trace 中包含私有本地大文件内容而不是 refs/digest。

### 7. Existing Regression Gate

在 multi-agent 合同层通过后，再跑核心回归：

```text
pytest tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_mcp_runtime_tools.py tests/test_sec_agent_retrieval_plan.py tests/test_sec_agent_langgraph_orchestrator.py tests/test_sec_benchmark_eval_mixed_context.py tests/test_industry_source_snapshot.py tests/test_sec_agent_ledger_store.py tests/test_workbench_artifacts.py tests/test_workbench_backend.py tests/test_workbench_job_runner.py tests/test_workbench_profiles.py tests/test_bm25_retriever.py -q
python -m compileall -q apps scripts src
```

通过标准：

- 不引入旧链路回归。
- Compileall 通过。
- 任何真实模型调用单独记录，不混入纯 deterministic gate。

### 8. Real LLM Activation Diagnostic Gate

只有在运行环境明确具备可用模型配置时执行。

建议最小评估：

- 5-case activation fixture。
- 只调用 Research Lead。
- 不执行真实 full chain。

通过标准：

- Mode exact match 5/5。
- Forbidden activation 0。
- Plan validator 5/5。
- Schema repair 次数可见，且单 case 不超过 2 次。

未通过处理：

- 标记 Lead LLM 为 `diagnostic-only`。
- 保留 deterministic router 作为 v0.2 mainline。
- 不继续接 Specialist LLM。

### 9. 185/186 Digest Gate

每次新增 agent、tool、source family、skill 或真实 LLM route 前执行。该 gate 不是额外功能，而是防止实现偏离 185/186 设计。

建议命令：

```text
pytest tests/test_research_skills.py tests/test_multi_agent_agent_registry.py tests/test_multi_agent_contracts.py tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_langgraph_routing.py -q
```

人工检查项：

- 新 agent 是否已在 registry 声明 `tool_permission`、`allowed_data_views`、`route_authority`、`allowed_tools`、`source_families`、`model_profile`、`max_tool_calls`、`skill_ids`。
- 新 skill 是否是短 role-specific skill，而不是把 185/186 全文塞进 prompt。
- 新 source family 是否有明确 owner operator、allowed claim scope、禁止用法和 verifier/deterministic gate。
- 新 LLM route 是否有 JSON schema、validator、repair 上限、direct tool-call rejection 和 fail-closed 路径。
- Workbench trace 是否只展示 refs/digest/counts/boundary summary。

Stop 条件：

- 文档中有 role / source / tool 归属，但代码 registry 没有对应字段或测试。
- Prompt 直接要求模型自行决定物理 route、索引路径、数据库路径或新检索。
- Specialist、Memo Writer 或 Verifier 出现 retrieval tool authority。
- Market / industry / relationship source 被用于支持公司披露财务事实。
- Unsupported claims 或 relationship hypotheses 未经 verifier 就进入 Memo Writer。

## 产物和文件落点

第一批建议产物：

| 类型 | 路径 |
| --- | --- |
| Agent 合同 | `src/sec_agent/agent_contracts.py` |
| Agent registry | `src/sec_agent/agent_registry.py` |
| Multi-agent downstream contracts | `src/sec_agent/multi_agent_contracts.py` |
| Tool call ledger | `src/sec_agent/tool_call_ledger.py` |
| Multi-agent router | `src/sec_agent/multi_agent_router.py` |
| Research Lead LLM route | `src/sec_agent/research_lead_llm.py` |
| Specialist LLM route | `src/sec_agent/specialist_llm.py` |
| LangGraph 接入 | `src/sec_agent/langgraph_orchestrator.py` |
| Graph state artifact | `src/sec_agent/graph_state.py` |
| Skill loader | `src/sec_agent/research_skills.py` |
| Skill prompts | `src/sec_agent/prompts/skills/*_skill_v0_1.md` |
| Workbench artifact inspect | `src/sec_agent/workbench/artifacts.py` |
| Backend inspect API | `apps/workbench/backend/app.py` |
| Unit tests | `tests/test_multi_agent_*.py` |
| Fixtures | `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl` |

## Stop / Proceed 规则

Proceed 到真实 LLM：

- Contract Unit Gate、Routing Fixture Gate、Graph Smoke Gate 全绿。
- Existing Regression Gate 无新增失败。
- Workbench trace 能 inspect。

Proceed 到 Specialist Analyst：

- Research Lead activation plan 已稳定。
- Reflection second pass 有预算、去重和无增益中止。
- Verifier 能拦截 unsupported named facts。
- Standard memo path 至少有一个 mock graph 和一个真实或 fixture-backed smoke。

Stop 或 Pivot：

- 单指标问题频繁误入 deep research。
- Loop guard 无法阻断重复工具调用。
- Tool 权限无法通过 registry 统一检查。
- Memo Writer 或 Verifier 需要新检索才能工作，说明上游证据合同还没打稳。
- Existing Regression Gate 出现与 multi-agent 改造相关的旧链路失败。

## 回滚策略

- 保留现有 native graph builder 和旧 interactive pipeline。
- Multi-agent graph 使用新 builder 或 feature flag 开启。
- 新 state 字段必须可选，旧 run inspection 不能依赖它们。
- 新 artifacts 只附加，不改写旧 artifact schema 的必填字段。
- 如果 multi-agent router 不稳定，关闭 feature flag 即可回到旧链路。

## 安全和隐私规则

- 文档、registry、trace 和 fixture 不写入运行凭据、私有供应商凭据或 SSH 密码。
- 不把 `data/raw_private/`、`data/processed_private/`、`data/indexes/`、`.env`、大型 eval 输出或私有 market/industry 数据纳入测试 fixture。
- Trace 记录 artifact refs、digest、row count 和 source gaps，不记录原始私有全文。
- 真实模型评估若执行，需要记录配置摘要和结果，但不记录凭据值。

## 本次记录

- 本文档把 185/186/187 收敛为 v0.2 multi-agent 架构更新执行计划。
- 本文档只规划实现和测评规则，未修改运行链路代码。
- 未运行代码测试、模型调用、数据构建或 benchmark。
