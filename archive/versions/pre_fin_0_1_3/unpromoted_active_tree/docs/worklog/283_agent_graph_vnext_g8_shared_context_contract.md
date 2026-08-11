# Agent Graph vNext G8 Shared Context Contract

## Problem

G1-G7 已经把 product/public/live-web/Milvus source family、Evidence Fusion、Bounded Gap Register、Product Specialist 和 industry playbook 接进 runtime，但 agent 间共享上下文仍主要靠各节点 prompt 约束和 role-specific bounded rows。下一步需要把 04 文档里的三层上下文边界落实到代码：

- Global Context：所有 agent 可见的 query、activation、inventory、source boundary、coverage、gap、claim schema、run trace 摘要。
- Role Context：按 agent 角色分配任务、source family bundle、claim slots 和 gap refs。
- Private Operator Context：物理路径、Milvus handle、API key env、raw traces 等不进入 specialist / memo prompt。

同时 Memo Writer 必须继续只消费 verified judgment plan / approved claim cards / gap register 摘要，不能看 raw rows 或 bounded evidence rows。

## Decision

- `AgentDataView` schema 升级到 `sec_agent_agent_data_view_v0.3`。
- 所有 role view 增加 `global_context_ref`、`role_context`、`private_context_policy`、`context_digest`。
- 对有 `bounded_rows` 权限的 agent 才暴露 `bounded_evidence_rows` 和 `source_family_bundle`；Research Lead / Memo Writer 不暴露空字段。
- Specialist request 继承 `agent_data_view_ref` 和 `role_context`，但 factual input 仍只允许来自 visible `bounded_evidence_rows` / `relationship_summary`。
- Memo Writer shared context 升级到 `sec_agent_shared_memo_context_v0.2`，只携带 coverage/source-boundary/gap refs，不携带 raw rows 或 bounded rows。

## Work Completed

- `src/sec_agent/multi_agent_runtime.py`
  - 新增 Global Context 摘要、digest/ref、source boundary registry、coverage summary、bounded gap refs、claim card schema ref、run trace summary。
  - `build_agent_data_view(...)` 输出 v0.3 contract。
  - `role_context` 显式记录 `private_operator_context_excluded`、`raw_rows_visible=false`、selected/context-only/exact-authority source families、forbidden claim scopes 和 role-specific claim slot ids。
  - Memo Writer data view 只保留 `global_context_ref` 和 `verified_summary`，不输出 full global context 或 bounded evidence fields。
  - Milvus runtime 只以 `available/location/semantic_authority_boundary` 摘要出现，private handles 被剥离。
- `src/sec_agent/specialist_llm.py`
  - Specialist request / prompt payload 增加 `agent_data_view_ref` 和 `role_context`。
  - route summary 增加 `agent_data_view_digest` / schema version，方便后续 async fan-out trace。
- `src/sec_agent/memo_llm.py`
  - `build_shared_memo_context(...)` 升级到 v0.2。
  - 增加 compact bounded gap register refs 和 prompt policy：`raw_evidence_rows=excluded`、`bounded_evidence_rows=excluded`、`private_operator_context=excluded`。
  - Memo input contract 同步记录 raw/bounded/private exclusion。
- Tests
  - Specialist data view 测试加入 private path / Milvus private handle fixture，确认不会进入 serialized view。
  - Memo Writer shared context 测试加入 bounded gap register，确认只能传 gap refs 和 exclusion policy。

## Result And Evidence

- `python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py -q`
  - `106 passed`
- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_routing_fixtures.py -q`
  - `99 passed`
- `python -m compileall -q src/sec_agent`
  - pass
- `python -m compileall -q src scripts/cloud scripts/eval_multi_agent`
  - pass
- `git diff --check`
  - pass
- `python -m pytest -q`
  - `817 passed`

## Boundaries

- G8 不改变 Evidence Fusion authority rules；public/proxy/live web/Milvus 仍不能证明 company-reported exact values。
- Global Context 是摘要和 digest，不是 raw state dump。
- Memo Writer 不能从 gap refs 推断事实；gap refs 只能写成缺口或边界。
- Private operator context 包括 filesystem paths、Milvus handles、API key env names、snapshot dirs、raw query traces，不能进 specialist / memo prompt。

## Follow-Up

- G9：把 evidence operators 和 specialists 改为 fan-out / barrier 机制，复用 `agent_data_view_ref.context_digest` 做 trace。
- G10：把 Milvus cloud/local/unavailable runtime switch 从摘要合同推进到实际 operator capability gate。
- G11：端到端 gate 覆盖 product/public/web/Milvus/context-gap/memo-writer raw-row exclusion。
