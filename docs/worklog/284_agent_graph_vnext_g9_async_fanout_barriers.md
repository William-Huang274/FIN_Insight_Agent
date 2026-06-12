# Agent Graph vNext G9 Async Fan-out / Barrier Graph

## Problem

G8 固化了 Global / Role / Private context，但 graph 仍以单节点串行方式执行 evidence operators 和 specialists。vNext 需要让可并行的部分以 fan-out / barrier contract 运行，同时保留现有同步路径可回退：

- Evidence operators 可按 source family / operator owner 分片并行。
- 任一 source family/operator shard 失败不能污染其他 source family。
- Specialist 可并行消费 frozen evidence bundle，最终按 deterministic order 合并。
- Evidence Fusion、Claim Card Store、Adjudicator 继续作为同步 barrier。

## Decision

- 默认 graph 行为不变。
- Evidence operator fan-out 通过 `multi_agent_context.evidence_operator_fanout=true` 启用。
- Specialist LLM fan-out 通过 `SEC_AGENT_SPECIALIST_FANOUT=1` 启用；默认仍串行。
- 不把 fan-out 失败变成弱 proxy fallback；失败 shard 只写 source gap 和 failed observation。
- Barrier summary 写入 graph state 和 summary artifact，供后续 G11 end-to-end gate 检查。

## Work Completed

- `src/sec_agent/multi_agent_runtime.py`
  - 新增 `build_evidence_operator_fanout_plan(...)`。
  - 新增 `execute_evidence_operator_fanout_plan(...)`。
  - Fan-out plan 按 `(source_family, operator_owner, tool_name)` 生成 shards，并保留 source route ids。
  - 每个 shard 独立执行 `execute_evidence_operator_plan(...)`；异常被隔离为 shard-level failed observation + source gap。
  - Merge 按 `shard_index` deterministic append，输出 `fanout_barrier`。
- `src/sec_agent/langgraph_orchestrator.py`
  - `execute_evidence_operators` 节点支持 `evidence_operator_fanout` feature flag。
  - `SecAgentGraphRuntimeState` 和 checkpoint key list 加入 fan-out/barrier 字段。
  - `optional_specialist_subgraph` 写入 `specialist_fanout_barrier`。
  - `aggregate_judgment_plan` 写入 `claim_card_store_barrier` 和 `adjudicator_barrier`。
  - Summary artifact 增加 `graph_barriers`。
- `src/sec_agent/specialist_llm.py`
  - `route_specialists_from_env(...)` 支持 `SEC_AGENT_SPECIALIST_FANOUT=1`。
  - 并行结果按 active specialist order deterministic merge。
  - 单个 specialist exception 会转为 fail route result，不阻断其他 specialist。
- Tests
  - Evidence fan-out 单测覆盖 source-family shard、异常隔离、deterministic merge、failed gap boundary。
  - LangGraph 单测覆盖 feature-flag evidence fan-out barrier、specialist / claim-card / adjudicator barrier。

## Result And Evidence

- `python -m pytest tests/test_multi_agent_operator_permissions.py::test_evidence_operator_fanout_isolates_failed_source_family_and_merges_deterministically tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_records_evidence_fanout_barrier_when_enabled tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_standard_path_runs_specialists -q`
  - `3 passed`
- `python -m pytest tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_specialist_llm.py -q`
  - `93 passed`
- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_contracts.py -q`
  - `62 passed`
- `python -m compileall -q src/sec_agent`
  - pass
- `python -m compileall -q src scripts/cloud scripts/eval_multi_agent`
  - pass
- `git diff --check`
  - pass
- `python -m pytest -q`
  - `819 passed`

## Boundaries

- G9 不改变 Evidence Fusion authority rules。
- Fan-out shard failure is a gap, not a fallback.
- Default graph remains sync-compatible unless feature flags are enabled.
- Tool budgets are still enforced by the existing operator plan per shard; production budget optimization remains a later scheduler concern.

## Follow-Up

- G10：Milvus runtime switch should become a first-class capability gate rather than just a source-family route.
- G11：end-to-end gate should assert `graph_barriers` and no unsupported core thesis across fan-out-enabled runs.
