# 共享上下文与协作机制

## 上下文分层

vNext 使用三层上下文：

```text
Global Context
Role Context
Private Operator Context
```

### Global Context

所有 agent 可见：

- `user_query`
- `query_contract`
- `activation_plan`
- `selected_playbook_ids`
- `source_inventory_brief`
- `source_boundary_registry`
- `coverage_summary`
- `bounded_gap_register`
- `claim_card_schema`
- `run_trace_summary`

### Role Context

按 agent 分配：

| Agent | Role context |
|---|---|
| Research Lead | inventory brief、playbook registry、query context、available source families |
| Plan Reflection | Lead plan、inventory、playbook、source boundaries |
| Coverage Reflection | fused evidence summary、missing requirements、tool trace、gap register |
| Fundamental | SEC ledger/text、company-disclosed product facts |
| Product / Technology | product graph、official product surface、public proxy、product gaps |
| Industry / Supply Chain | industry rows、relationship rows、public context |
| Market | market snapshot、valuation context |
| Risk | sampled all-source bounded rows、claim cards、gap register |
| Adjudicator | claim card store、coverage summary、gap register |
| Memo Writer | verified judgment plan、approved claim cards、gap register |
| Verifier | memo draft、claim cards、refs、source boundaries |

### Private Operator Context

只给 operator / tool：

- filesystem paths
- DuckDB / SQLite / BM25 / Milvus handles
- exact route args
- API key env var names
- snapshot output dirs
- raw query traces

Private context 不进入 specialist prompt。

## Research Lead Inventory 输入

Lead 必须拿到 `inventory_brief_v0.2`，但不能拿 raw rows。

字段：

- universe coverage: ticker/company/industry_schema。
- source family availability。
- source family authority。
- form/year/filing coverage。
- product evidence counts。
- product fact exact-authority counts。
- public source context counts。
- known gap type counts。
- freshness / as_of / materialized_at。
- Milvus availability and location: cloud / local / unavailable。
- playbook candidates。
- web scope policy ids。

## Agent Data View 升级

当前 `build_agent_data_view(...)` 已经执行 role-specific row selection。vNext 需要把它升级成明确合同：

```text
AgentDataViewV0.3
 - global_context_ref
 - role_context
 - bounded_evidence_rows
 - source_family_bundle
 - assigned_task_card
 - required_claim_slots
 - forbidden_claim_scopes
 - bounded_gap_refs
 - context_digest
```

## 异步与同步机制

vNext Graph 采用 fan-out / barrier 模式。

```text
1. Lead planning                         sync
2. Plan Reflection Gate                  sync
3. Evidence retrieval fan-out            async
   - SEC / exact ledger
   - product graph
   - market
   - industry
   - relationship
   - public context
   - approved web repair
4. Evidence Fusion Barrier               sync
5. Coverage & Gap Reflection             sync
6. Targeted repair fan-out               async, only if gated
7. Delta Audit Barrier                   sync
8. Specialist fan-out                    async
9. Claim Card Store Barrier              sync
10. Thesis / Counter-thesis Adjudicator  sync
11. Memo + Verifier repair loop          sync
12. Presenter                            sync
```

## 并行原则

- Evidence operators 可并行，因为它们只写各自 source-family row bundles。
- Specialist 可并行，因为它们消费 frozen evidence bundle，不互相聊天。
- Reflection / Fusion / Delta Audit / Claim Store / Adjudicator 是同步屏障。
- Memo Writer 和 Verifier 保持同步 repair loop，避免 memo 基于未验证状态发布。

## 共享状态写入规则

- Operator 只能 append source-specific rows / tool observations / source gaps。
- Evidence Fusion 只写 fused bundle 和 authority labels。
- Reflection 只写 gap diagnosis / repair request / bounded-answer flag。
- Specialist 只写 claim cards。
- Adjudicator 只写 judgment plan。
- Memo Writer 只写 memo draft。
- Verifier 只写 verification report / repair request。

任何节点不得覆盖上游 raw artifact 或改写 source authority。
