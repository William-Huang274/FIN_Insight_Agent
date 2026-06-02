# 185 Multi-agent 投研工作流框架草稿

日期：2026-05-30
分支：`codex/api-model-call-architecture`
状态：架构草稿，尚未进入代码实现

## 背景

单 agent 链路已经验证了 FinSight-Agent 的核心方向：把开放式投研问题转成可执行、可检查、有证据边界的研究工作流。当前链路已经能使用 SEC 10-K/10-Q、8-K 业绩新闻稿、市场快照、行业数据、Exact-Value Ledger、coverage matrix、deterministic gates、ContextManager 和 Workbench 入口。

但随着 full238、行业数据、市场快照、未来外网搜索和产业链关系图接入，单 agent 同时承担 planner、检索决策、证据充足性判断、写作和验证，会出现明显上限：

- 角色冲突：同一个模型既写结论又审查自己，容易弱化证据缺口。
- 范围传播风险：planner 或 scope 一旦错，检索、ledger、coverage 和 synthesis 都会在错误范围内工作。
- 上下文压力：SEC、8-K、market、industry、relationship graph 和多轮会话全部塞进一个 prompt，token 成本高，遗漏风险高。
- 补查能力不足：模型能判断“需要补查最新 10-Q / 8-K / 市场快照”，但如果二次检索不进入图内闭环，就会把可查证据写成“建议补查”。
- 报告深度不足：真实投研问题需要投资主线、预期差、产业链交叉验证、估值语境、反证条件和催化剂，不能只输出公司财报摘要。

本阶段设计 multi-agent 的目标不是贴上“多智能体”标签，而是把投研工作拆成可检查、可并行、可恢复、可复用工具的角色分工。

## 设计目标

1. 让模型负责研究判断，程序负责证据边界。
2. 让不同 agent 承担不同投研职责，避免一个模型同时写作和自检。
3. 让 LangGraph 成为业务状态流转和条件分支的核心，而不是脚本外壳。
4. 让 MCP 工具成为 SEC、market、industry、run artifact、未来 web/news 工具的统一调用边界。
5. 让每个模型节点都有明确 skill 和输出 schema，避免长 prompt 随意堆叠。
6. 让证据不足时优先自动补查；补查后仍不足时输出当前证据能支持的判断和明确边界。
7. 让 Lead Agent 负责选择轻量路径、标准路径或深度研究路径，避免简单问题激活所有 agent 和全量数据源。
8. 让不同 agent 可选择不同模型档位，简单确定性节点优先使用更快、更便宜的模型，复杂规划和最终综合才使用更强模型。
9. 让规则脚本检查模型输出是否合法、是否漂移、是否疑似幻觉，但不替代模型做投研质量判断。

## 从单 Agent 到 Multi-agent 的职责拆分

| 角色 | 主要职责 | 不该做的事 |
| --- | --- | --- |
| Research Lead Agent | 识别投资问题、分析意图、claim 类型、研究范围和初始 EvidenceRequirementPlan | 不直接写最终报告，不直接访问物理索引 |
| Universe / Relationship Agent | 从公司或主题扩展 peer、上下游、客户、供应商、替代风险和行业链条 | 不把“相关公司名单”当成事实结论，不凭关系图推断财务数值 |
| Evidence Operator Agents | 按 source family 执行 SEC、8-K、market、industry、未来 web/news 检索和结构化取数 | 不做投资结论，不绕过 MCP/tool contract |
| Coverage / Reflection Agent | 判断证据是否足够、是否触发二次检索、是否需要澄清或降级 | 不写 memo，不用宽松 fallback 把缺口伪装成完整 |
| Specialist Analyst Agents | 对基本面、产业链、市场/估值、风险/反证等局部问题形成可验证中间判断 | 不直接发布最终答案，不引用未验证证据 |
| Verifier Agent | 检查 claim 支撑、数值、期间口径、source tier、market as_of_date 和 forbidden claims | 不生成新观点，不替代 Memo Writer |
| Memo Writer Agent | 在 verified judgment plan 和证据边界内写投研 memo | 不重新规划范围，不重新检索，不绕过 verifier |
| Renderer | 面向用户组织答案、来源边界、日期和证据强度 | 不暴露冗余内部 trace，不展示内部逐步推理链 |

## 推荐主链路

```text
User Query
  -> load_session_state
  -> Research Lead Agent
  -> Universe / Relationship Agent
  -> EvidenceRequirementPlan compiler
  -> Evidence Operator subgraph
       -> SEC Operator
       -> 8-K Operator
       -> Market Operator
       -> Industry Operator
       -> future Web/News Operator
  -> Coverage / Reflection Agent
       -> if sufficient: Specialist Analyst subgraph
       -> if insufficient and source exists: second-pass Evidence Operator subgraph
       -> if ambiguous: ask clarification or bounded answer
  -> Specialist Analyst subgraph
       -> Fundamental Analyst
       -> Industry / Supply Chain Analyst
       -> Market / Valuation Analyst
       -> Risk / Counterevidence Analyst
  -> Judgment Plan aggregator
  -> Memo Writer Agent
  -> Verifier Agent
       -> if repairable: Memo repair
       -> if not repairable: bounded answer
  -> Renderer
  -> persist_session_state
```

这条链路可以按问题复杂度裁剪。窄问题不需要全部角色都启动；宽问题、产业链问题和跨行业比较才进入完整多角色路径。

## 调用裁剪和模型选择

Lead Agent 的第一项职责不是“尽量深入研究”，而是判断本轮问题应该走哪条路径。它必须输出 `execution_mode` 和 `agent_activation_plan`，由 schema validator 校验后进入 LangGraph 条件分支。

建议初版 `execution_mode`：

| 模式 | 适用问题 | 激活范围 | 默认模型档位 |
| --- | --- | --- | --- |
| `deterministic_lookup` | 单一数值、已知 artifact、状态查看、简单来源检查 | 工具节点 + renderer，通常不需要综合型 LLM | 规则脚本或轻量模型 |
| `focused_answer` | 单公司/少数公司、单一主题、明确 source 范围 | Research Lead、对应 Evidence Operator、Coverage、Memo Writer、Verifier | Lead/Reflection 用快速模型，Memo 可用中档模型 |
| `standard_memo` | 多公司比较、基本面 + 管理层解释 + 市场反应 | Lead、Evidence Operators、Coverage、少量 Specialist、Verifier、Memo Writer | Lead 用中档模型，Memo/Verifier 可用强模型 |
| `deep_research` | 产业链、跨行业、relationship expansion、复杂预期差 | Lead、Universe、全 Evidence subgraph、Specialist map-reduce、Verifier | Lead/Memo/Verifier 用强模型，局部 analyst 可用中档模型 |

模型选择不应写死为某个供应商或某个模型。每个 agent 应读取 `model_policy`：

```json
{
  "default_fast": "deepseek-flash or equivalent",
  "default_balanced": "deepseek-chat or equivalent",
  "default_strong": "deepseek-pro or equivalent",
  "agent_overrides": {
    "research_lead": "balanced",
    "coverage_reflection": "balanced",
    "memo_writer": "strong",
    "verifier": "strong"
  }
}
```

原则：

- 不需要推理和写作的确定性任务，不调用强模型。
- 需要复杂 scope、产业链展开、证据冲突判断和最终 memo 的节点，允许使用强模型。
- 模型选择是 runtime config，不应散落在 prompt 或脚本常量中。
- 所有模型输出都必须经过 schema validator，再进入下游工具。

## 规则校验边界

规则脚本的职责是保证模型输出可执行、可审计、不过界，而不是替模型写投研观点。

应该检查：

- JSON/schema 是否合法。
- `execution_mode` 是否在允许枚举内。
- `agent_activation_plan` 是否只激活存在的 node/subgraph。
- `tool_call` 是否使用允许工具、允许 source tier、允许字段。
- 公司、年份、披露文件、source family 是否存在于 source inventory。
- route 预算、二次检索轮数、token 预算是否超过上限。
- 模型输出是否漂移到用户未授权范围，例如把 focused ticker 扩成 full universe。
- 模型是否试图凭记忆写未检索事实。

不应该检查：

- 不应硬编码“哪个行业更重要”。
- 不应替代 Lead Agent 判断投资问题类型。
- 不应因为某个模型结论“不够深”而改写结论。
- 不应在证据不足时静默补默认范围；应让 Reflection 输出二次检索或 bounded answer。

如果校验失败，优先进入同模型 schema repair / retry；仍失败则 fail closed 或请求用户澄清。不要用 heuristic 业务兜底掩盖 planner 失败。

## 循环中止策略

Multi-agent 引入 tool loop 和 second-pass retrieval 后，必须防止模型陷入多次调用、重复检索或自我修复死循环。中止策略应进入 graph state，并在 Workbench / trace 中可见。

### 硬性预算

建议初版预算：

| 预算项 | 默认上限 | 说明 |
| --- | --- | --- |
| `max_graph_steps` | 24 | 单轮用户请求最多 LangGraph node transition 次数 |
| `max_tool_calls_total` | 12 | 单轮所有 MCP/tool 调用总数 |
| `max_tool_calls_per_agent` | 4 | 单个 agent 最多工具调用数 |
| `max_second_pass_rounds` | 2 | 二次检索最多轮数 |
| `max_repair_rounds` | 2 | schema repair / memo repair 最多轮数 |
| `max_same_tool_same_args` | 1 | 相同工具 + 相同参数不得重复调用 |
| `max_runtime_seconds` | 配置化 | 本地/云端可不同，超时进入 partial state |

### 重复检测

每次工具调用都记录：

- `agent_id`
- `tool_name`
- normalized arguments digest
- input artifact digests
- output artifact digest
- row counts / source gaps / candidate counts

如果同一 agent 对同一 digest 重复调用同一工具，graph 应中止该分支并把状态标记为 `duplicate_tool_call_blocked`。

### 无增益检测

二次检索或 repair 后必须比较：

- 新增 context rows 数量。
- 新增 ledger facts 数量。
- coverage gap 是否减少。
- sufficiency level 是否提升。
- verifier failure 是否减少。

如果连续一轮无增益，停止该循环，进入 bounded answer 或 clarification，而不是继续扩大检索。

### 中止后的用户体验

中止不等于空答。最终输出应遵循：

- 当前证据能支持什么。
- 哪些 claim 证据不足。
- 系统已尝试补查哪些证据类型。
- 如果继续研究，需要新增哪类数据或用户澄清什么范围。

后台 trace 保留详细 loop break 原因；面向用户只做自然语言边界说明，不展示内部逐步推理链。

## Agent 调用逻辑

### Research Lead Agent

调用时机：

- 每个新的用户问题默认调用。
- 多轮 follow-up 也调用，但输入应包含上一轮 session summary、active scope、用户新约束和当前 source inventory。
- 如果用户只是请求 `/answer`、`/state`、查看 artifact，则不调用。

主要输出：

- `analysis_intent`
- `investment_question_type`
- `claim_types`
- `execution_mode`
- `agent_activation_plan`
- `model_policy_hint`
- `scope_mode`: `focused_peer | sector_representative | full_universe | relationship_expansion`
- `initial_tickers`
- `evidence_requirement_plan`
- `confidence_policy`
- `clarification_needed`

调用边界：

- 它可以判断“需要比较哪些业务问题”，但不能决定物理索引路径。
- 它可以请求 source tier，但必须经过 source inventory 和 schema validator。
- 它可以决定是否调用 Universe、Specialist、Market、Industry 等 subgraph，但该决策必须由规则校验检查是否符合用户问题和 source inventory。
- 它可以建议模型档位，但 runtime `model_policy` 拥有最终执行权。

### Universe / Relationship Agent

调用时机：

- 用户只给出单家公司但问题涉及“前景、竞争、产业链、影响、需求、估值、AI、云、能源、银行周期”等需要外部参照的问题。
- 用户明确问 peer、上下游、供应链、客户、替代风险、行业传导。
- Research Lead 输出 `scope_mode=relationship_expansion` 或 `sector_representative`。
- Coverage / Reflection 发现单公司证据不足以回答产业链或市场预期问题。

可跳过场景：

- 用户只问单个公司某个披露指标，例如“MSFT 2025 capex 是多少”。
- 用户明确限制“不展开 peer，只看这家公司”。

主要输出：

- `relationship_scope`
- `included_tickers`
- `excluded_tickers`
- `relation_type`
- `direction`
- `financial_link_type`
- `metrics_to_check`
- `evidence_source_needed`
- `confidence`
- `caveats`

设计要点：

- 它输出的是“为什么纳入和需要查什么”，不是直接输出结论。
- 关系图可以作为 evidence requirement 的输入，但不能替代 SEC / market / industry 证据。

### Evidence Operator Agents

调用时机：

- Research Lead / Universe Agent / Reflection Agent 输出可执行 evidence requirements 后调用。
- 每个 source family 可并行调用。
- 二次检索时只调用缺口对应的 source family，不重跑全部工具。

建议拆分：

| Operator | 调用条件 | 主要工具 |
| --- | --- | --- |
| SEC Operator | claim 涉及审计财务事实、10-K/10-Q、分部、风险因素、MD&A、现金流、资本配置 | `sec_search_filings`、`sec_query_exact_value_ledger` |
| 8-K Operator | claim 涉及管理层解释、guidance、订单、需求、业绩新闻稿、最新季度叙事 | `sec_search_filings` with `8k_commentary` |
| Market Operator | claim 涉及市场反应、估值、相对收益、事件窗口、预期差 | `market_get_snapshot` |
| Industry Operator | claim 涉及行业背景、宏观指标、能源、电力、医疗、消费、金融周期 | `industry_get_snapshot` |
| Web / News Operator | claim 涉及 SEC/market/industry 未覆盖的近期事件、供应链新闻、监管事件 | future controlled web/news search |

工具控制方式：

- Operator agent 不应直接拼索引路径。
- LLM 只提出 evidence requirement 或 tool arguments 的业务层字段。
- Retrieval compiler 把业务需求编译成 MCP tool call / route call。
- 物理检索、预算、去重、BGE rerank、DuckDB 查询由工具层执行。

### Coverage / Reflection Agent

调用时机：

- 第一轮 Evidence Operator 完成后必调。
- 二次检索完成后再次调用。
- Specialist Analysts 输出中间判断后可轻量调用一次，检查是否存在新的 unsupported claim。

主要输出：

- `sufficiency_level`: `sufficient | partial | insufficient`
- `missing_requirements`
- `source_available`
- `second_pass_requests`
- `needs_user_clarification`
- `bounded_answer_allowed`
- `confidence_by_claim_type`

决策逻辑：

```text
if evidence sufficient:
  continue to Specialist Analysts / Memo Writer
elif missing source exists and second_pass_budget remains:
  issue second-pass retrieval requests
elif user intent ambiguous:
  ask clarification
else:
  allow bounded answer with explicit evidence boundary
```

注意：

- 二次检索触发原因和结果写入后台 trace。
- 最终答案可以自然说明“系统补充检查了最新 10-Q / 8-K / 市场快照后形成判断”，但不单独堆一个割裂的“二次检索证据列表”。

### Specialist Analyst Agents

调用时机：

- 宽范围、多公司、多行业、产业链或估值问题。
- Research Lead 输出多个 `analysis_intent`。
- EvidenceRequirementPlan 涉及多个 claim family。
- 单轮 context_rows 很多，需要 map-reduce。

可跳过场景：

- 单一数值查询。
- 单一 company / metric / period 的窄解释。

建议初版四类：

| Specialist | 关注点 | 典型触发 |
| --- | --- | --- |
| Fundamental Analyst | 收入、利润率、现金流、capex、RPO、分部、期间口径 | 基本面变化、peer comparison |
| Industry / Supply Chain Analyst | 上下游、客户/供应商、需求传导、瓶颈、行业数据 | NVDA/云 capex/能源/医疗/银行周期 |
| Market / Valuation Analyst | 价格反应、相对收益、估值、事件窗口、预期差 | market snapshot 或估值问题 |
| Risk / Counterevidence Analyst | 反证、风险因素、管理层叙事可信度、证据冲突 | 所有需要投资判断的问题 |

输出要求：

- 每个 analyst 只输出局部判断、证据强度、反证条件和不可支持的 claim。
- 不写完整报告。
- 不引用没有进入 evidence pack / ledger / market / industry snapshot 的事实。

### Verifier Agent

调用时机：

- Memo Writer 输出后必调。
- Specialist Analyst 输出可选轻量 verifier。
- 规则 gates 发现可修复问题后，可调用 verifier 生成修复指令。

主要检查：

- 数值是否来自 ledger 或明确 evidence object。
- 10-K、10-Q、8-K、market snapshot、industry snapshot 权重是否混用。
- QTD / YTD / TTM / annual 是否混淆。
- market snapshot 是否展示 `as_of_date`。
- 管理层口径是否被写成审计事实。
- 行业数据是否只用于背景和解释，而不是公司财务事实。
- 是否存在 unsupported named facts。

### Memo Writer Agent

调用时机：

- Coverage / Reflection 允许生成答案后。
- Judgment Plan aggregator 已整理 analyst outputs 后。
- 不在证据不足且未经过 Reflection 决策时调用。

输入：

- `verified_judgment_plan`
- `ledger_rows`
- `evidence_summaries`
- `market_snapshot_summaries`
- `industry_snapshot_summaries`
- `coverage_matrix`
- `sufficiency_report`
- `verifier_constraints`

输出：

- 面向用户的投研 memo。
- 包含结论、依据、证据强度、反证条件、来源边界和日期。
- 不暴露内部逐步推理链。

## Node、Subgraph 和单次 LLM 调用的划分

### 应做成 LangGraph Node 的部分

这些阶段需要 checkpoint、状态可审计、失败恢复或条件分支，应做成正式 node：

- `load_session_state`
- `research_lead_plan`
- `validate_query_contract`
- `universe_relationship_expand`
- `compile_evidence_requirements`
- `compile_retrieval_plan`
- `execute_evidence_operators`
- `assess_coverage`
- `assess_sufficiency`
- `run_specialist_analysts`
- `aggregate_judgment_plan`
- `memo_writer`
- `verify_claims`
- `run_deterministic_gates`
- `render_answer`
- `persist_session_state`

### 应做成 Subgraph 的部分

这些阶段内部有多步、并行、循环或可裁剪路径，适合做 subgraph：

1. `evidence_operator_subgraph`
   - SEC route
   - 8-K route
   - market route
   - industry route
   - future web/news route
   - merge / dedupe / route attribution

2. `reflection_second_pass_subgraph`
   - sufficiency check
   - second-pass request compile
   - route execution
   - coverage rebuild
   - loop guard

3. `specialist_analysis_subgraph`
   - fundamental analyst
   - industry/supply-chain analyst
   - market/valuation analyst
   - risk/counterevidence analyst
   - analyst output verifier

4. `verification_repair_subgraph`
   - claim verifier
   - deterministic gates
   - repair instruction
   - bounded answer fallback when not repairable

5. `universe_expansion_subgraph`
   - relationship graph lookup
   - source inventory intersection
   - inclusion/exclusion explanation
   - evidence requirement generation

### 可以是单次 LLM 调用的部分

单次 LLM 调用适合低风险、无工具循环、输出可 schema 校验的场景：

- Research Lead 的初始 plan。
- Universe Agent 的初始 relationship expansion draft。
- Coverage / Reflection 的 sufficiency assessment。
- Specialist Analyst 的局部 memolet。
- Memo Writer 的最终 memo draft。

但这些单次调用仍应是 LangGraph node 内部的实现细节，而不是游离在 graph 外的脚本调用。node 负责记录输入摘要、输出 schema、token、耗时、模型名和 artifact ref。

## 工具调用和脚本控制边界

推荐原则：

- 业务编排由 LangGraph 控制。
- 工具合同由 MCP registry 控制。
- 物理检索由 retrieval compiler 和工具 handler 控制。
- 脚本保留为 CLI / smoke / batch build / adapter，不再决定业务流程。

当前过渡方式：

```text
Agent node
  -> structured tool request
  -> MCP tool registry
  -> existing Python adapter / script function
  -> artifact + observation
  -> graph state
```

不推荐：

```text
Agent node
  -> shell script runs entire DAG
  -> parse final artifact
```

原因：

- 后者会让 multi-agent 变成“多个名字包一个旧脚本”，无法真正做条件分支、二次检索、checkpoint 和角色隔离。
- 脚本仍可存在，但应被降级为工具实现或运维入口。

## Skill 设计

每个模型型 agent 都应该有任务特化 skill，但不应该每个 agent 都塞一份完整长文档。推荐：

### Shared Core Skill

所有 agent 共享，内容包括：

- source tier 权重和边界。
- SEC / 8-K / market / industry / web evidence 的可支持 claim。
- period role 规则。
- market `as_of_date` 规则。
- 证据不足时的降级原则。
- 不凭模型记忆补事实。

### Role-specific Skill

每个模型角色再注入短 skill：

| Skill | 对应角色 | 内容 |
| --- | --- | --- |
| `research_lead_planning_skill` | Research Lead | 投资问题分类、claim types、EvidenceRequirementPlan schema、scope_mode |
| `relationship_universe_skill` | Universe / Relationship Agent | 产业链关系类型、纳入/排除逻辑、关系证据边界 |
| `evidence_operator_tool_use_skill` | Evidence Operator | 工具参数含义、source tier 不混用、何时用 ledger-first / filing_text / 8k / market / industry |
| `coverage_reflection_skill` | Coverage / Reflection | sufficiency level、二次检索触发、澄清和 bounded answer 决策 |
| `fundamental_analysis_skill` | Fundamental Analyst | 收入、利润率、现金流、capex、RPO、行业特定财务指标 |
| `industry_supply_chain_analysis_skill` | Industry / Supply Chain Analyst | 上下游传导、瓶颈、客户/供应商、行业数据使用边界 |
| `market_valuation_analysis_skill` | Market / Valuation Analyst | 市场反应、估值、事件窗口、预期差、不能替代 SEC 财务事实 |
| `risk_counterevidence_skill` | Risk / Counterevidence Analyst | 反证条件、风险因素、管理层叙事可信度、冲突处理 |
| `verification_skill` | Verifier | claim support、数值校验、source boundary、unsupported named facts |
| `memo_writer_skill` | Memo Writer | 投研 memo 结构、证据强度表达、边界表达、用户可读性 |

执行上可以先实现少量核心 skill：

1. `shared_evidence_boundary_skill`
2. `research_lead_planning_skill`
3. `coverage_reflection_skill`
4. `memo_writer_skill`
5. `verification_skill`

等 specialist subgraph 稳定后，再拆行业/估值/风险 skill。

## 初版调用策略

为避免一开始过度复杂，建议 v0.2 multi-agent 初版采用三档路径。

### Path A：窄问题轻量路径

触发：

- 单公司、单指标、单期间、明确披露源。

链路：

```text
Research Lead
-> SEC / Market / Industry single operator
-> Coverage check
-> Memo Writer or direct answer renderer
-> Verifier
```

不调用：

- Universe Agent
- Specialist subgraph
- 多路二次检索，除非证据缺口明确且 source exists。

### Path B：标准投研 memo 路径

触发：

- 多公司 peer comparison。
- 基本面 + 管理层解释 + 市场反应。
- 用户要求“分析表现、趋势、前景、估值分歧”。

链路：

```text
Research Lead
-> optional Universe Agent
-> Evidence Operator subgraph
-> Coverage / Reflection
-> Fundamental + Market + Risk analysts
-> Judgment Plan
-> Memo Writer
-> Verifier
-> Renderer
```

### Path C：产业链 / 跨行业深度路径

触发：

- 产业链、上下游、供应链、客户/供应商、行业传导。
- full_universe / sector_depth / relationship_expansion。
- 多行业比较或主题研究。

链路：

```text
Research Lead
-> Universe / Relationship subgraph
-> Evidence Operator subgraph by source family and sector
-> Coverage / Reflection with second-pass loop
-> Specialist Analyst map-reduce
-> Cross-agent Verifier
-> Memo Writer
-> Final Verifier + Renderer
```

## 风险和约束

1. Multi-agent 可能增加 token 和延迟。
   - 需要 node-level token telemetry、cache、summary artifact 和按路径裁剪 agent。

2. Agent 间可能互相重复检索。
   - 需要 EvidenceRequirementPlan 合并、route cache、physical search op 去重和 artifact reuse。

3. Specialist Analyst 可能产生彼此冲突的观点。
   - 冲突不应被平均；Judgment Plan aggregator 应保留冲突并交给 Verifier / Memo Writer 表达。

4. Universe Agent 容易扩大范围。
   - 必须有 source inventory、coverage budget、scope_mode 和 inclusion rationale。

5. Tool calling 不应退化成脚本跑全 DAG。
   - 工具调用必须返回 bounded observation 和 artifact refs，让 graph 决定下一步。

## 分阶段落地建议

### Phase 1：合同先行

- 固定 multi-agent graph state schema。
- 固定每个 agent 的输入、输出、触发条件和 allowed tools。
- 把 shared skill 和 Research Lead / Reflection / Memo Writer skill 落成 prompt 文件。

验收：

- 不跑真实 full chain，也能用 mock 工具验证 agent routing。

### Phase 2：Research Lead + Reflection 接入现有链路

- 先不拆 Specialist Analysts。
- Research Lead 输出 EvidenceRequirementPlan。
- Reflection 根据 coverage 决定是否二次检索。

验收：

- “建议补查 10-Q/8-K”类问题能自动触发二次检索。
- 窄问题不会误触发 Universe Agent。

### Phase 3：Evidence Operator subgraph 标准化

- 把 SEC、8-K、market、industry 工具统一进入 MCP registry。
- Workbench 和 CLI 复用同一 registry。
- 记录 tool observation、artifact refs、candidate counts。

验收：

- 同一 EvidenceRequirementPlan 在 CLI、Workbench、MCP client 中得到一致工具调用结果。

### Phase 4：Specialist Analyst map-reduce

- 先实现 Fundamental、Market/Valuation、Risk 三个 analyst。
- Industry/Supply Chain analyst 等 relationship graph 稳定后接入。

验收：

- 宽问题输出不再把所有证据塞给一个 synthesis prompt。
- 每个 analyst output 都可被 verifier 检查。

### Phase 5：Universe / Relationship 深度接入

- 建立 relationship graph source family。
- 让 Universe Agent 根据关系图和 source inventory 生成可审计研究范围。
- 接入产业链深度 eval。

验收：

- 用户问 NVDA 或云 capex 时，系统能提出上下游交叉验证路径，并说明纳入逻辑和证据边界。

## 当前决策

- Multi-agent 应先作为 LangGraph 原生业务编排设计，而不是多个脚本或多个最终 prompt。
- Agent 应优先做成 graph node；有循环、并行和复用需求的部分做 subgraph；单次 LLM 调用只是 node 内部实现。
- 每个模型型 agent 需要独立短 skill，但应共享一份 evidence boundary core skill。
- 工具调用应走 MCP registry / tool contract，脚本只作为 adapter 或批处理入口。
- 第一阶段应优先做 Research Lead、Coverage / Reflection、工具 registry 复用和 state schema，而不是一次性堆齐所有 specialist agent。

## 本次记录

- 本文档仅为架构草稿。
- 未运行测试。
- 未修改运行链路代码。
