# Agent Graph vNext G10 Milvus Runtime Switch

## Problem

G9 已经把 evidence operators 和 specialists 改成可 fan-out / barrier 的形态，但 Milvus 仍只是一个 retrieval route。vNext 需要把 Milvus 变成一等 runtime capability：

- 云端 Milvus、本地 Milvus Lite 和不可用状态必须在 inventory / graph summary 中显式呈现。
- Research Lead / Retrieval Plan 可以选择 `milvus_semantic`，但只能作为 semantic recall supplement。
- 没有绑定 URI / DB path / collection 时不能 mock 成可用，也不能调用 operator。
- Milvus rows 不得升级为 exact-value authority；exact 数字仍必须走 ledger / SEC structured / verified product runtime facts。

## Decision

- 新增 `milvus_runtime_capability(...)`，统一归一化 `cloud_available`、`local_available`、`unavailable`。
- `milvus_semantic` route 执行前增加 runtime capability gate；没有绑定 runtime 时直接登记 skipped observation + source gap。
- Graph summary 只暴露 public runtime metadata，不暴露 URI、DB path 或 credential-like 字段。
- Claim boundary 固定为 `semantic_recall_supplement_not_exact_value_authority`。

## Work Completed

- `src/sec_agent/multi_agent_runtime.py`
  - 新增 `milvus_runtime_capability(...)` 和 public capability projection。
  - `tool_arguments_from_route(...)` 为 `milvus_semantic` route 注入 runtime status/location/bound policy。
  - `execute_evidence_operator_plan(...)` 在 Milvus route 前执行 capability gate；runtime unavailable / not bound 时写 source gap，而不是调用 operator 或走 fallback。
- `src/sec_agent/langgraph_orchestrator.py`
  - Evidence operator execution context 透传 `project_inventory.milvus_runtime`。
  - Summary artifact 增加 sanitized `milvus_runtime` block，保留 status/location/collection/vector count/schema digest/fallback routes/claim boundary。
- `src/sec_agent/project_inventory.py`
  - Milvus inventory brief 增加 `schema_digest` 和 `claim_boundary`，保持 private path 不进入 prompt-facing brief。
- Tests
  - 覆盖 cloud available but unbound 的 capability state。
  - 覆盖 unbound Milvus route skipped + source gap。
  - 覆盖 bound local route 仍能作为 semantic recall supplement 执行。
  - 覆盖 inventory brief 不泄露 private path，并保留 cloud/local/unavailable metadata。

## Result And Evidence

- `python -m pytest tests/test_multi_agent_operator_permissions.py::test_milvus_runtime_capability_requires_bound_runtime_for_execution tests/test_multi_agent_operator_permissions.py::test_milvus_semantic_route_skips_when_runtime_not_bound tests/test_multi_agent_operator_permissions.py::test_milvus_semantic_route_arguments_require_typed_vector_filter tests/test_multi_agent_operator_permissions.py::test_evidence_operator_plan_executes_milvus_semantic_as_recall_supplement tests/test_project_inventory_source_inventory.py::test_inventory_brief_v02_exposes_milvus_web_and_playbook_without_private_paths tests/test_multi_agent_evidence_requirements.py::test_plan_reflection_gate_rejects_milvus_when_runtime_unavailable tests/test_multi_agent_langgraph_routing.py::test_multi_agent_graph_stops_on_plan_reflection_gate_failure -q`
  - `7 passed`
- `python -m pytest tests/test_multi_agent_operator_permissions.py tests/test_project_inventory_source_inventory.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_research_lead_llm.py tests/test_sec_agent_retrieval_plan.py -q`
  - `165 passed`
- `python -m compileall -q src scripts/cloud scripts/eval_multi_agent`
  - pass
- `git diff --check`
  - pass
- `python -m pytest -q`
  - `821 passed`

## Boundaries

- G10 does not rebuild or migrate the Milvus collection.
- Cloud Milvus remains the expected high-volume runtime unless the user chooses to run local Milvus Lite.
- Local no-Milvus state is explicit unavailable/not-bound, not a synthetic fallback.
- Milvus evidence can support relationship discovery, paraphrase recall, and hard-to-keyword text recall, but not exact numbers, market share, product sales, consensus, or valuation claims.

## Follow-Up

- G11：运行 10-20 case end-to-end gate，覆盖 exact/focused/standard/deep/multi-turn、product/public/web/Milvus boundaries、fan-out barriers 和 bounded gaps。
