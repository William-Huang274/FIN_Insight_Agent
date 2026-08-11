# Agent Graph vNext G5 Web Evidence Operator

## Problem

上一阶段 G4 已把 second pass 拆成 diagnosis / repair plan / hard gate / delta audit，但 `request_live_web_snapshot` 仍被硬编码阻断。G5 目标是按 `docs/architecture/agent_graph_vnext/02_live_web_evidence_policy.zh-CN.md` 落地受控联网证据入口：联网不能成为自由搜索能力，必须从结构化 repair request 进入 allowlist、snapshot、source classifier、parser/authority gate，并默认写入 `live_public_web_context` context-only rows。

## Decision

- 新增 `web_evidence_operator`，权限为 `bounded_execute`，只允许调用 `web_evidence_snapshot`。
- 新增 `live_public_web_context` physical route，不通过 Research Lead / Specialist / Verifier 暴露直接联网能力。
- 新增默认 web source scope registry 和 `validate_web_evidence_request(...)`，由 second-pass hard gate 统一检查 policy id、domain、source class 和 claim type。
- `web_evidence_snapshot` 当前实现为 deterministic snapshot adapter：不泛搜，只把已通过 gate 的 URL/request 规范化为 snapshot-bound context row。真实 search/fetch 可在同一 tool contract 后续替换。

## Work Completed

- Runtime / graph:
  - `src/sec_agent/multi_agent_runtime.py`
    - 新增 `WEB_SOURCE_SCOPE_REGISTRY_SCHEMA_VERSION`、`WEB_EVIDENCE_REPAIR_REQUEST_SCHEMA_VERSION`、`WEB_EVIDENCE_SNAPSHOT_SCHEMA_VERSION`。
    - 新增 `default_web_source_scope_registry()` 和 `validate_web_evidence_request()`。
    - `gate_second_pass_repair_plan()` 取消 G4 的 `live_web_operator_not_enabled_until_g5` 硬阻断，改为 web request validation fail-closed。
    - `live_public_web_context` route 接入 `ROUTE_OPERATOR_TOOL` / `ROUTE_SOURCE_FAMILY` / `ROUTE_COST_TIER` / source-family route compiler / tool args / boundary / dry-run / result rows。
    - `validate_tool_observation_boundary("web_evidence_snapshot", ...)` 要求 snapshot id、as-of、citation/url、source_class，且所有 web rows 必须 `context_only=true`、`exact_value_authority=false`。
  - `src/sec_agent/langgraph_orchestrator.py`
    - second-pass hard gate 传入由 source inventory / activation plan 过滤后的 web scope registry，避免默认 policy 隐式全开。
- Agent / MCP contracts:
  - `src/sec_agent/agent_contracts.py`、`src/sec_agent/agent_registry.py`
    - 新增 `web_evidence_operator` 和 `web_evidence_snapshot` allowlist。
  - `src/sec_agent/mcp_contracts.py`
    - 新增 `web_evidence_snapshot` MCP contract，明确 search snippet、社媒、弱电商 proxy、SEC/product fact overwrite 禁止项。
  - `src/sec_agent/mcp_tool_registry.py`
    - 新增 deterministic `_invoke_web_evidence_snapshot` handler。
- Compiler:
  - `src/sec_agent/retrieval_plan.py`
    - 新增 `live_public_web_context` allowed route / source tier / budget / source-tier / section handling。
    - 显式保留 `url`、`domain`、`source_class`、`claim_types`、`web_scope_policy_ids` 等 structured request fields。
- Tests:
  - 新增/更新 operator permission、reflection second-pass、agent registry、MCP contract、retrieval plan tests。

## Result And Evidence

- `python -m pytest tests/test_multi_agent_operator_permissions.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_agent_registry.py tests/test_sec_agent_mcp_contracts.py tests/test_sec_agent_retrieval_plan.py -q`
  - `73 passed`
- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_project_inventory_source_inventory.py tests/test_multi_agent_research_lead_llm.py -q`
  - `72 passed`
- `python -m compileall -q src/sec_agent`
  - pass
- `git diff --check`
  - pass

## Boundaries

- `live_public_web_context` rows are context/lead only by default.
- Ecommerce source class can support SKU / price / availability / surface presence, not shipments, share, sell-through, channel inventory, margin, or revenue.
- Social source classes cannot support financial facts.
- Search snippets cannot enter evidence rows without snapshot binding.
- Web rows cannot overwrite SEC exact-value ledger rows or `company_product_evidence_graph` runtime facts.

## Follow-Up

- G6 should add `product_technology_analyst` and route product taxonomy / product KPI / public proxy / commercial gap claim cards through the evidence-fusion boundary.
- A later implementation can bind the real fetch/snapshot backend behind `web_evidence_snapshot` without changing agent permissions.
