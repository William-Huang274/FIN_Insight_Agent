# 反思机制与 Second Pass 设计

## 设计判断

Reflection 不应只放在一个最终汇总点，也不应散落到每个模型节点。它应该放在会改变后续路径的 checkpoint 上。

vNext 使用四类 reflection：

| Reflection | 插入点 | 目的 | 能否触发 repair |
|---|---|---|---|
| `plan_reflection` | Research Lead 之后 | 检查行业、模式、source family、playbook、web policy 是否偏航 | 可以要求 Lead 重出 plan |
| `coverage_gap_reflection` | Evidence Fusion 之后 | 诊断证据缺口、source authority、是否可修复 | 可以触发 coverage second pass |
| `claim_thesis_reflection` | Claim Card Store 之后 | 检查核心 claim、counter-thesis、citation、authority misuse | 可以触发 quality second pass |
| `verifier_reflection` | Memo Writer 之后 | 检查 memo 是否越界、数字漂移、unsupported claim | 只能发 repair request，不新增事实 |

## Second Pass 新定义

Second pass 不再表示“再调用一次模型或工具”。它应表示：

```text
Reflection Diagnosis
 -> Repair Plan Builder
 -> Hard Gate
 -> Targeted Repair Executor
 -> Delta Auditor
 -> Evidence Fusion Selector
```

### Reflection Diagnosis

输出 gap 类型：

- `exact_value_missing`
- `product_binding_missing`
- `product_kpi_parser_gap`
- `region_schema_gap`
- `period_column_group_gap`
- `source_specific_table_gate_gap`
- `citation_weak`
- `counterevidence_missing`
- `commercial_tracker_gap`
- `public_unavailable_gap`
- `web_source_candidate_missing`
- `milvus_semantic_recall_gap`

Diagnosis 只能描述缺口，不生成新事实。

### Repair Plan Builder

将 gap 转为可执行动作：

- `query_exact_ledger`
- `query_sec_table_or_text`
- `query_product_evidence_graph`
- `query_public_source_context`
- `query_market_or_industry_snapshot`
- `query_relationship_graph`
- `run_source_specific_parser_repair`
- `request_live_web_snapshot`
- `route_to_bounded_gap_register`

Repair plan 必须引用原始 requirement / claim / evidence refs。

### Hard Gate

Hard gate 检查：

- source family 是否在 activation plan 允许范围内。
- 当前 gap 是否 retrievable。
- 是否超过 max second-pass rounds / max tool calls。
- requested source 是否具备 claim authority。
- web request 是否匹配 playbook source scope allowlist。
- repair 是否会用弱 proxy 替代强事实。

不通过则直接进入 `Bounded Gap Register`。

### Targeted Repair Executor

Executor 可以是 SEC operator、product evidence query、public context query、web evidence operator、parser repair job 或 Milvus semantic supplement。Executor 不写 memo、不做判断。

### Delta Auditor

Delta audit 输出：

- 新增 evidence row 数。
- 新增 exact-authority row 数。
- 关闭的 gap ids。
- 被提权的 claim ids。
- 仍未关闭的 gap ids。
- 是否触发 bounded answer。

没有 delta 的 second pass 不能继续循环。

## Coverage Second Pass 与 Quality Second Pass

### Coverage Second Pass

在 specialist dispatch 之前触发。目标是让 specialist 看到足够的 frozen evidence bundle。

触发条件：

- required source family missing 但 source inventory 显示可查。
- exact-value requirement 缺 ledger / filing quote。
- product taxonomy / product KPI 缺 binding。
- relationship scope 缺确认边或缺 hypothesis boundary。

### Quality Second Pass

在 claim card / judgment plan 后触发。目标是防止 memo 建立在 unsupported core thesis 上。

触发条件：

- core claim 无 evidence ref。
- bull/bear evidence 明显不平衡。
- claim card 将 context-only source 当 fact。
- numeric claim 缺 exact ledger 或 official table。
- memo-required claim 缺 citation。

## 停止条件

任一条件满足即停止：

- second pass 已达到预算。
- delta audit 显示无新增 authority-bearing evidence。
- gap 被判定为 commercial tracker gap。
- gap 被判定为 public unavailable under current policy。
- gap 需要尚未实现的 parser/schema。
- source policy 禁止使用当前候选来源。

停止后写入 `Bounded Gap Register`，不得由 memo writer 自行兜底。
