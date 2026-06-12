# 277 Agent Graph vNext G3 Evidence Fusion Selector

## Prompt

按 `docs/architecture/agent_graph_vnext/06_implementation_sequence_and_acceptance_gates.zh-CN.md` 继续执行 G3：把 Evidence Fusion Selector 升级为显式 graph barrier，统一 product / public / market / industry / relationship / Milvus rows 的 authority labeling，并生成第一版 Bounded Gap Register。

## Decision

- Evidence Fusion 不做 retrieval、不修复缺口、不替代 downstream reflection；它只把已有 rows 投影为可审计 authority bundle。
- `runtime_ledger_rows` 和 `company_product_evidence_graph` 中 `promotion_status=runtime_fact_allowed` 的 rows 可进入 exact/product KPI fact scope。
- `public_source_context`、`market_snapshot`、`industry_snapshot`、`relationship_graph`、`live_public_web_context`、`milvus_semantic` 永不提供 exact-value authority。
- `source_gaps` 和 product gap rows 进入 `BoundedGapRegister`，缺口必须显式保留为 public repair candidate、commercial tracker gap、parser/schema gap 等，不允许 generic fallback 或 proxy fact 兜底。

## Work Completed

- 在 `src/sec_agent/multi_agent_runtime.py` 新增：
  - `EVIDENCE_FUSION_BUNDLE_SCHEMA_VERSION = sec_agent_evidence_fusion_bundle_v0.1`
  - `BOUNDED_GAP_REGISTER_SCHEMA_VERSION = sec_agent_bounded_gap_register_v0.1`
  - `build_evidence_fusion_bundle(...)`
  - authority projection helpers 和 bounded gap classification helpers。
- 在 `src/sec_agent/langgraph_orchestrator.py` 新增 `evidence_fusion_selector` 节点，插入顺序为：
  - `execute_evidence_operators -> evidence_fusion_selector -> coverage_reflection`
- 扩展 graph state / checkpoint keys：
  - `product_evidence_rows`
  - `public_source_context_rows`
  - `evidence_fusion_bundle`
  - `bounded_gap_register`
- summary artifact 新增：
  - `evidence_fusion` row / authority / violation counters
  - `bounded_gap_register` gap type / source family counters
- 补测试覆盖：
  - product runtime facts 可提权为 `company_disclosed_product_kpi_fact`
  - public source rows 即使输入误带 `exact_value_authority=True` 也被强制降权
  - Milvus semantic rows 被标为 semantic supplement，不能支持 exact values
  - gap register 去重和 commercial / parser-schema gap 分类
  - graph 中 Evidence Fusion 在 Coverage Reflection 前执行，并写入 summary。

## Verification

- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_agent_registry.py tests/test_project_inventory_source_inventory.py tests/test_multi_agent_specialist_llm.py::test_agent_data_view_routes_product_evidence_and_public_source_context_rows -q`
  - `59 passed`
- `python -m compileall src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py`
  - passed
- `python -m pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_specialist_llm.py tests/test_project_inventory_source_inventory.py -q`
  - `80 passed`
- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q`
  - `73 passed`

## Follow-up

- G4 should consume `evidence_fusion_bundle` and `bounded_gap_register` in Reflection Diagnosis / Repair Plan Builder / Delta Auditor.
- Delta Auditor must stop second-pass loops when new rows do not add authority-bearing evidence.
- Public/web/proxy rows should continue to be context or lead-only until source-specific parser/promotion gates exist.
