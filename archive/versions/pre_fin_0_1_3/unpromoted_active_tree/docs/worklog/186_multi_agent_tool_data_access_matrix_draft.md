# 186 Multi-agent 工具与数据访问矩阵草稿

日期：2026-05-30
分支：`codex/api-model-call-architecture`
状态：初版规划，尚未进入代码实现
关联文档：`185_multi_agent_investment_research_framework_draft.md`

## 背景

185 已经定义了 multi-agent 投研工作流的角色分工，但还需要明确每个 agent 能调用哪些工具、能访问哪些数据、能否决定召回/重排 route、能否触发二次检索，以及哪些 agent 只能检查上游结果。

本文件先定义初版权限矩阵。目标不是把能力锁死，而是避免后续 multi-agent 实现中出现以下问题：

- 每个 agent 都能随意查所有数据，导致成本、延迟和上下文失控。
- 写作型 agent 绕过 coverage / verifier 直接检索新事实。
- 检查型 agent 修改业务观点，越过职责边界。
- 工具调用由脚本散落控制，无法审计每个 agent 的实际权限。
- route、rerank、source tier 和数据库访问权限没有清晰归属。

## 权限等级

### 工具调用权限

| 等级 | 含义 |
| --- | --- |
| `none` | 不能调用工具，只能消费上游 state 或 artifact 摘要 |
| `inspect_only` | 只能读取 artifact / coverage / trace / state，不触发新检索 |
| `request_only` | 只能提出 evidence requirement 或 tool request，由 compiler / validator 执行 |
| `bounded_execute` | 可以通过 MCP registry 执行受限工具调用 |
| `orchestrate_subgraph` | 可以触发一个受限 subgraph，例如 Evidence Operator 或 second-pass retrieval |

### 数据访问权限

| 等级 | 含义 |
| --- | --- |
| `summary_only` | 只能看压缩摘要、coverage summary、ledger summary |
| `artifact_ref` | 可看 artifact path/digest/row count，但不读取原文 |
| `bounded_rows` | 可读取裁剪后的 evidence rows / ledger rows / market rows |
| `database_query` | 可通过受控工具查询 DuckDB / SQLite / BM25 / ObjectBM25 |
| `raw_source_read` | 可读取原始披露文件或大文本；默认不开放给 agent |

### Route 决策权限

| 等级 | 含义 |
| --- | --- |
| `none` | 不决定 route |
| `suggest_business_need` | 只能提出业务证据需求，例如“需要最新 10-Q capex 和 8-K 管理层解释” |
| `compile_physical_route` | 可把需求编译为 `ledger_first`、`filing_text`、`8k_commentary`、`market_snapshot` 等 route |
| `adjust_budget` | 可调整 candidate/rerank/source budget，但必须受全局上限约束 |
| `execute_route` | 可执行 route 工具调用 |

初版原则：模型 agent 主要拥有 `suggest_business_need`，物理 route 编译由 deterministic compiler 完成。只有 Evidence Operator subgraph 的工具节点拥有 `execute_route`。

## Agent 权限矩阵 v0.1

| Agent | 工具权限 | 数据权限 | Route 权限 | 可用工具 | 不允许 |
| --- | --- | --- | --- | --- | --- |
| Research Lead Agent | `request_only` | `summary_only` + source inventory | `suggest_business_need` | source inventory reader、relationship inventory summary、run state summary | 直接查 BM25/BGE、直接读原始 filing、直接调用 market/industry DB |
| Universe / Relationship Agent | `request_only` | relationship graph summary + source inventory | `suggest_business_need` | relationship graph lookup、company universe inventory、sector pack metadata | 直接输出财务结论、直接扩大到全市场、凭关系图推断收入/利润 |
| SEC Operator | `bounded_execute` | `database_query` via tool | `execute_route` | `sec_search_filings`、`sec_query_exact_value_ledger` | 调 market/industry 工具、写投资结论、绕过 source policy |
| 8-K Operator | `bounded_execute` | `database_query` via tool | `execute_route` | `sec_search_filings` with `8k_commentary` | 把管理层口径写成审计事实、替代 10-K/10-Q ledger |
| Market Operator | `bounded_execute` | `database_query` via tool | `execute_route` | `market_get_snapshot` | 用市场价格覆盖 SEC 财务事实、不给 `as_of_date` |
| Industry Operator | `bounded_execute` | `database_query` via tool | `execute_route` | `industry_get_snapshot` | 把行业数据写成公司财务事实、替代公司披露 |
| Web / News Operator | `bounded_execute` | `bounded_rows` with timestamp/source | `execute_route` | future `web_search` / `news_search` | 无来源网页摘要、无时间戳新闻、凭搜索结果覆盖 SEC ledger |
| Coverage / Reflection Agent | `orchestrate_subgraph` | `bounded_rows` + coverage + source gaps | `suggest_business_need` for second pass | run artifact inspect、coverage matrix、source gaps、second-pass request compiler | 直接写 memo、直接放宽 coverage、重复调用同一工具 |
| Fundamental Analyst | `none` or `inspect_only` | `bounded_rows` | `none` | ledger/context summary reader | 新检索、改 route、引入新事实 |
| Industry / Supply Chain Analyst | `none` or `inspect_only` | `bounded_rows` + relationship summaries | `none` | industry/relationship summary reader | 新检索、扩大 universe、凭关系推财务数值 |
| Market / Valuation Analyst | `none` or `inspect_only` | `bounded_rows` + market summaries | `none` | market summary reader | 新检索、替代 SEC 事实 |
| Risk / Counterevidence Analyst | `inspect_only` | `bounded_rows` + risk/source gaps | `none` | risk evidence reader、coverage summary | 新检索、改写 evidence requirements |
| Judgment Plan Aggregator | `inspect_only` | analyst outputs + coverage + verifier constraints | `none` | run artifact inspect | 新检索、忽略冲突 |
| Memo Writer Agent | `none` | verified summaries only | `none` | no tools in first version | 新检索、读取原始数据、绕过 verifier |
| Verifier Agent | `inspect_only` | `bounded_rows` + ledger + rendered answer + gates | `none` | claim verifier、ledger support checker、artifact inspect | 生成新投资观点、扩大范围、触发新检索 |
| Renderer | `none` | final memo + boundary summaries | `none` | no tools | 改写事实、隐藏 source boundary |

## 工具和数据源初版归属

### SEC / Filing

| 数据/工具 | 主要使用者 | 访问方式 | 边界 |
| --- | --- | --- | --- |
| `sec_search_filings` | SEC Operator、8-K Operator | MCP registry / bounded execute | 必须带 ticker/year/form/source tier/route 约束 |
| `sec_query_exact_value_ledger` | SEC Operator、Verifier | MCP registry / bounded execute or inspect | 只支持结构化财务事实，不支持管理层叙事 |
| BM25 index | Retrieval tool handler | tool 内部 | Agent 不直接访问路径 |
| ObjectBM25 / SQLite FTS object store | Retrieval tool handler | tool 内部 | Agent 不直接访问路径 |
| raw SEC filing text | 不开放给模型 agent | batch parser / chunker | 只在离线构建时读取 |

### Market

| 数据/工具 | 主要使用者 | 访问方式 | 边界 |
| --- | --- | --- | --- |
| `market_get_snapshot` | Market Operator、Verifier | MCP registry / bounded execute | 必须返回 `snapshot_id` 和 `as_of_date` |
| market DuckDB / evidence rows | Market tool handler | tool 内部 | 只能支持市场反应、估值语境、事件窗口 |
| FMP valuation fields | Market Operator | 通过 snapshot tool | 不能覆盖 SEC ledger 数值 |

### Industry

| 数据/工具 | 主要使用者 | 访问方式 | 边界 |
| --- | --- | --- | --- |
| `industry_get_snapshot` | Industry Operator | MCP registry / bounded execute | 只用于行业背景和解释 |
| industry_snapshot DuckDB | Industry tool handler | tool 内部 | 不能支持公司特定财务事实 |
| EIA / FRED / FDA / CMS source-family | Industry tool handler | batch download + snapshot query | 必须保留 provider、route、frequency、as_of / period |

### Relationship Graph

| 数据/工具 | 主要使用者 | 访问方式 | 边界 |
| --- | --- | --- | --- |
| company relationship graph | Universe Agent、Industry/Supply Chain Analyst | summary lookup / bounded rows | 只能作为研究范围和假设，不直接作为财务事实 |
| sector depth packs | Universe Agent、Research Lead | inventory summary | 不能替代实际 source coverage |

### Run Artifact

| 数据/工具 | 主要使用者 | 访问方式 | 边界 |
| --- | --- | --- | --- |
| `run_inspect_artifacts` | Coverage / Reflection、Verifier、Workbench | inspect-only | 读取状态、coverage、ledger、gates、checkpoint summary |
| `run_read_artifact` | Debug / audit only | bounded bytes + allowlist | 默认不开放给 Memo Writer |

## Agent Activation Plan Schema 草案

Lead Agent 应输出一个可校验的激活计划：

```json
{
  "execution_mode": "focused_answer",
  "model_policy_hint": {
    "research_lead": "balanced",
    "memo_writer": "balanced",
    "verifier": "strong"
  },
  "activate_agents": [
    "research_lead",
    "sec_operator",
    "coverage_reflection",
    "memo_writer",
    "verifier"
  ],
  "skip_agents": [
    {
      "agent": "universe_relationship",
      "reason": "User specified a focused company scope and no supply-chain question."
    },
    {
      "agent": "industry_operator",
      "reason": "No industry-level claim requested."
    }
  ],
  "allowed_source_families": [
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing"
  ],
  "max_second_pass_rounds": 1,
  "max_tool_calls_total": 6
}
```

Validator 必须检查：

- `execution_mode` 是否允许。
- `activate_agents` 是否存在且与 `execution_mode` 匹配。
- 被跳过 agent 是否有 reason。
- `allowed_source_families` 是否在 source inventory 中。
- tool budget 是否低于全局上限。
- 是否出现用户未授权的范围扩张。

## Route 决策流程

推荐流程：

```text
Research Lead / Universe / Reflection
  -> EvidenceRequirementPlan
  -> deterministic route compiler
  -> RetrievalPlan
  -> tool validator
  -> Evidence Operator tool calls
```

职责边界：

- 模型提出“需要什么证据”。
- compiler 决定“怎么查”：`ledger_first`、`filing_text`、`8k_commentary`、`market_snapshot`、`industry_snapshot`。
- tool validator 检查 source tier、ticker/year/form、budget、重复调用和数据可达性。
- Operator 执行工具。

模型不直接决定：

- BM25 index 路径。
- ObjectBM25 / SQLite FTS 路径。
- BGE 模型路径。
- DuckDB 物理路径。
- 任意未注册工具。

模型可以建议：

- 哪类证据更重要。
- 哪些公司、年份、source tier 应覆盖。
- 是否需要二次检索。
- 哪些缺口会影响结论强度。

## 死循环和重复调用控制

所有 agent 调用和工具调用都要写入 `tool_call_ledger`：

```json
{
  "turn_id": "turn_001",
  "agent_id": "coverage_reflection",
  "tool_name": "sec_search_filings",
  "arguments_digest": "sha256:...",
  "input_artifact_digests": ["sha256:..."],
  "output_artifact_digest": "sha256:...",
  "row_count": 12,
  "source_gap_count": 0,
  "coverage_delta": {
    "closed_gaps": 2,
    "new_gaps": 0
  },
  "elapsed_ms": 1800
}
```

中止规则：

- 相同 `agent_id + tool_name + arguments_digest` 在同一 turn 内重复出现，阻断。
- 二次检索没有新增 rows、没有关闭 coverage gap，阻断。
- repair 后 verifier failure 没减少，阻断。
- 超过 `max_tool_calls_total`，阻断。
- 超过 `max_second_pass_rounds`，阻断。
- 超过 `max_graph_steps`，阻断。

阻断后的状态：

- `loop_break_reason`
- `last_successful_node`
- `bounded_answer_allowed`
- `missing_requirements`
- `user_visible_boundary_summary`

## 模型档位建议

| Agent | 默认档位 | 理由 |
| --- | --- | --- |
| Research Lead | balanced | 需要规划和裁剪路径，但不一定需要最强模型 |
| Universe / Relationship | balanced | 需要关系推理，但输出可 schema 校验 |
| Evidence Operator | fast or no LLM | 多数情况下只执行工具，不需要强模型 |
| Coverage / Reflection | balanced | 需要判断证据是否足够和是否补查 |
| Fundamental Analyst | balanced | 局部分析，证据已裁剪 |
| Industry / Supply Chain Analyst | balanced or strong | 复杂产业链问题可升档 |
| Market / Valuation Analyst | balanced | 结构化 market rows 为主 |
| Risk / Counterevidence Analyst | balanced or strong | 需要发现反证和冲突 |
| Memo Writer | strong | 负责最终表达和综合 |
| Verifier | strong or specialized checker | 负责审稿和识别 unsupported claims |
| Renderer | no LLM or fast | 格式化为主 |

档位名称应是抽象 profile，例如 `fast`、`balanced`、`strong`，由 runtime 映射到 DeepSeek 或其他供应商模型。不要在 graph 节点里写死 `deepseek-pro`。

## 初版实现建议

### Step 1：先落权限表和 schema

- 新增 agent registry。
- 每个 agent 声明：
  - allowed tools
  - allowed data views
  - route authority
  - model profile
  - max tool calls
  - skill id

### Step 2：Lead Agent 只输出激活计划

- 暂不让它直接调工具。
- validator 检查激活计划。
- 根据 `execution_mode` 路由到轻量 / 标准 / 深度路径。

### Step 3：Evidence Operator 使用 MCP registry

- SEC / 8-K / market / industry 统一走 tool registry。
- 每个 tool call 写入 `tool_call_ledger`。
- 重复调用和预算上限先做确定性检查。

### Step 4：Reflection 接入二次检索控制

- Reflection 只输出 second-pass request。
- compiler 和 validator 决定能否执行。
- 执行后必须有 coverage delta，否则停止循环。

### Step 5：Workbench 展示权限和调用轨迹

- 显示本轮激活了哪些 agent。
- 显示哪些 agent 被跳过和原因。
- 显示每个 agent 调用了哪些工具、耗时、row count、source gaps。
- 显示 loop break reason。

## 当前决策

- Agent 默认不直接访问数据库路径或索引路径。
- 能决定物理 route 的不是 LLM agent，而是 route compiler。
- Lead Agent 决定是否激活 subgraph / node，但该决定必须经过 schema 和 source inventory 校验。
- Memo Writer 不允许调用检索工具。
- Verifier 不允许生成新投资观点。
- Coverage / Reflection 可以发起二次检索请求，但不能直接绕过 compiler 执行。
- 所有模型和工具调用都必须有预算和重复调用中止机制。

## 本次记录

- 本文档仅为初版权限规划。
- 未运行测试。
- 未修改运行链路代码。
