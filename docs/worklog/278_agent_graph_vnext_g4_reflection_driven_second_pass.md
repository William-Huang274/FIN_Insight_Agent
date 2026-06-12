# 278 Agent Graph vNext G4 Reflection-Driven Second Pass

## Prompt

按 `docs/architecture/agent_graph_vnext/06_implementation_sequence_and_acceptance_gates.zh-CN.md` 继续执行 G4：把 second pass 从“二次检索调用”升级为 Reflection Diagnosis、Repair Plan Builder、Hard Gate、Targeted Repair Executor、Delta Auditor 的显式流程。

## Decision

- Coverage second pass 和 quality second pass 继续共用同一条 deterministic repair pipeline，但 artifact 中保留 `trigger`，下游可以区分 coverage gap 与 claim quality gap。
- Hard Gate 在工具执行前拦截：
  - commercial tracker gap；
  - public unavailable gap；
  - parser/schema gap；
  - live web request（留到 G5）；
  - source family 不在 activation plan 允许范围内；
  - 使用 public/market/industry/live-web 弱 proxy 替代 exact/product authority fact。
- Delta Auditor 以 G3 `evidence_fusion_bundle` 为准，只把新增 exact-authority 或 company-disclosed authority rows 视作 authority-bearing delta；只新增 context/proxy rows 时停止循环并允许 bounded answer。

## Work Completed

- 在 `src/sec_agent/multi_agent_runtime.py` 新增：
  - `build_second_pass_reflection_diagnosis(...)`
  - `build_second_pass_repair_plan(...)`
  - `gate_second_pass_repair_plan(...)`
  - `audit_second_pass_delta(...)`
  - G4 schema versions：diagnosis / repair plan / hard gate / delta audit。
- 在 `src/sec_agent/langgraph_orchestrator.py` 改造 `optional_second_pass`：
  - compilation 阶段先生成 diagnosis / repair plan / hard gate；
  - hard gate 无 executable request 时不执行工具，blocked candidates 合并进 `bounded_gap_register`；
  - 工具执行后立即重建 `evidence_fusion_bundle`；
  - delta audit 写入 `second_pass_delta_audit` 和 `second_pass_result`；
  - 无 authority-bearing delta 时设置 `no_incremental_evidence` 并允许 bounded answer。
- 扩展 checkpoint 和 summary artifact：
  - `second_pass_reflection_diagnosis`
  - `second_pass_repair_plan`
  - `second_pass_hard_gate`
  - `second_pass_delta_audit`
- 补测试覆盖：
  - retrievable SEC exact-value gap 能生成 executable repair plan；
  - commercial tracker gap 被 hard gate 送入 bounded gap；
  - parser/region schema gap 不被 public/industry proxy 兜底；
  - delta audit 对 exact-authority delta 关闭 gap，对 context-only delta 停止；
  - graph 中 commercial gap 不触发工具调用。

## Verification

- `python -m pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_langgraph_routing.py -q`
  - `42 passed`
- `python -m pytest tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_specialist_llm.py tests/test_project_inventory_source_inventory.py -q`
  - `84 passed`
- `python -m pytest tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_agent_registry.py tests/test_research_skills.py -q`
  - `74 passed`
- `python -m compileall src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py`
  - passed

## Follow-up

- G5 should add the allowlisted Web Evidence Operator and keep its default output as `live_public_web_context` context-only rows.
- Product/source-specific parser repairs remain blocked at G4 unless they already have an implemented runtime executor and promotion gate.
- Future Delta Auditor refinements can bind closed gaps to claim ids once Claim Card Store vNext is implemented.
