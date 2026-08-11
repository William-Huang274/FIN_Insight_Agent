# Agent Graph vNext 总体框架

## 背景

上一阶段已经完成 Tier1+Tier2 扩容、公开源 S5-S0 物化、产品 KPI fact layer 修复、`company_product_evidence_graph` 和 `public_source_context` runtime wiring。最新 evidence fusion context rows 显示：

- `company_product_evidence_graph`：`14,642` rows，其中 `5,976` rows 为 `runtime_fact_allowed` 且具备 exact-value authority。
- `public_source_context`：`25` rows，exact-value authority 为 `0`，只能作为 resolver / context / lead。
- product evidence gaps：`2,979`，其中大量是公开源无法补齐、需要 commercial tracker 或暴露为 gap 的项目。

因此下一阶段 Agent Graph 的核心不是继续扩大普通 RAG，而是让 graph 原生理解证据强度、来源边界和可修复缺口。

## 当前模式基线

现有 multi-agent graph 已具备这些节点：

```text
load_session_state
 -> research_lead_plan
 -> validate_activation_plan
 -> universe_relationship_expand
 -> route_by_execution_mode
 -> compile_evidence_requirements
 -> execute_evidence_operators
 -> coverage_reflection
 -> optional_second_pass
 -> optional_specialist_subgraph
 -> aggregate_judgment_plan
 -> memo_writer
 -> verifier
 -> renderer
 -> persist_session_state
```

现有 native graph 已具备 retrieval、market/industry snapshot、exact ledger、coverage、second pass、judgment、verify、render。

这些基础不应推倒重写。vNext 应在现有 graph 上加显式合同：

- `Evidence Fusion Selector`
- `Product / Technology Specialist`
- `Claim Card Store`
- `Bounded Gap Register`
- `Plan Reflection Gate`
- `Reflection Repair Loop`
- `Web Evidence Operator`
- `Playbook Registry`
- `Shared Context Contract`

## 目标图

```text
User Query
 -> Context / Saved Run Resolver
 -> Research Lead
 -> Plan Reflection Gate
 -> Question Triage / Mode Gate
      |-- exact_value / focused_answer
      |     -> Retrieval Plan Builder
      |     -> Evidence Operators
      |     -> Evidence Fusion Selector
      |     -> Numeric Verifier
      |     -> Presenter
      |
      |-- standard_memo / deep_research
            -> Hypothesis Builder
            -> Universe & Relationship Scope
            -> Retrieval Plan Builder
            -> Evidence Operators
            -> Evidence Fusion Selector
            -> Coverage & Gap Reflection
            -> Targeted Repair Loop if gated
            -> Specialist Dispatch
            -> Claim Card Store
            -> Thesis vs Counter-thesis Adjudicator
            -> Judgment Plan
            -> Memo Writer
            -> Verifier / Editor
            -> Presenter or Bounded Answer
```

## Research 模式

`Research Lead` 输出必须包含：

- `research_mode`: `deterministic_lookup | focused_answer | standard_memo | deep_research`
- `industry_schema`
- `selected_playbooks`
- `focus_tickers`
- `search_scope_tickers`
- `required_source_families`
- `allowed_gap_policy`
- `reflection_policy`
- `web_scope_policy_ids`
- `activate_agents`
- `agent_priorities`
- `evidence_requirement_plan`

Lead 不直接调用工具、不读 raw evidence、不写分析结论。

## Evidence Authority 层级

vNext graph 内部必须把 source authority 写入所有 evidence bundles 和 claim cards：

| Authority | 来源 | 可支持的结论 |
|---|---|---|
| `primary_exact_value` | SEC/global filing table parser、exact ledger、官方结构化披露 | reported financial / product KPI fact |
| `company_disclosed_context` | filing text、8-K、IR material、官方产品页 | 管理层说法、产品 taxonomy、披露上下文 |
| `context_or_proxy` | market/industry/public source context、官方宏观/监管数据 | 行业背景、proxy、方向性验证 |
| `lead_only` | search result、resolver candidate、unverified page | 只生成下一步检索候选 |
| `gap_only` | commercial tracker gap、public unavailable、schema backlog | 缺口暴露，不能写成事实 |

## 禁止降级项

- 不允许用电商排名、评论数、搜索热度替代销量、市占率、渠道库存。
- 不允许用 public source context 证明公司产品销售、利润率、市场份额。
- 不允许用 Milvus semantic recall 替代 exact ledger。
- 不允许让 Memo Writer 联网或读取 raw rows。
- 不允许把 parser/schema backlog 包装成“方向性结论”。

## vNext 成功标准

1. Lead 能基于 inventory + playbook 做正确分发，而不是靠泛化行业常识。
2. Coverage / Reflection 能区分 retrievable gap、parser/schema gap、commercial tracker gap、public unavailable gap。
3. Second pass 只执行 targeted repair，并有 delta audit。
4. Specialist 并行产 claim cards；adjudicator 明确 bull / bear / gap。
5. Memo 只消费 verified judgment plan，source-boundary violation 由 verifier 阻断。
