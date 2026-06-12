# D11 Analyst View / Research Memory Runtime Projection

## Prompt

用户要求继续按 `07`、`08` 文档执行顺序推进。D10 Derived Metric Layer 完成后，下一步是 D11 Analyst View / Research Memory，让 Research Lead 未来可以先读结构化 analyst view，再 drill down 到 evidence。

## Decision

本轮落地 per-run runtime projection：

- Analyst View 只能作为索引 / 规划输入，不能作为原始事实来源。
- View / memory entry 只能引用 D1 Claim Evidence Ledger、D2 Typed Gap Ledger 和 D10 Derived Metric Layer 的 id。
- D11 validation 显式拒绝 `supporting_evidence_ids`、`input_source_ids`、`source_ids` 等 raw refs 出现在 view / memory entry 中。
- 长期记忆、跨 run retrieval、dedupe、staleness、supersession 和 DB / vector / graph store 留给 D11.1 / D12。

## Work Completed

- 新增 `src/sec_agent/analyst_view_layer.py`。
  - schema version：`sec_agent_analyst_view_research_memory_v0.1`。
  - 输出 `analyst_views` 和 `research_memory_entries`。
  - 支持 `company_profile_view`、`segment_model_view`、`product_kpi_view`、`earnings_change_view`、`risk_factor_view`、`bull_bear_debate_view`、`thesis_tracker`。
  - 每个 view 保存 `claim_ids`、`gap_ids`、`derived_metric_ids`、`drilldown_refs`、`source_layers`、`summary_signals` 和 `evidence_policy`。
  - 每个 memory entry 保存 view id 与 ledger drilldown refs，状态为 `run_scoped_candidate`。
- 更新 `src/sec_agent/langgraph_orchestrator.py`。
  - persist 顺序变为 D4/D5 -> D7/D6 -> D9 -> D10 -> D11。
  - 写出 `analyst_view_research_memory.json`。
  - `artifact_refs`、`multi_agent_summary.json` 和 `langgraph_node_checkpoints.json` 暴露 D11 summary。
- 新增 `tests/test_analyst_view_layer.py`。
  - 覆盖正常 view/memory projection。
  - 覆盖 raw source refs validation fail。
  - 覆盖 graph artifact persist、summary 和 checkpoint。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 和 `00_internal_master_checklist.md`。

## Result And Evidence

- Syntax check：`python -m py_compile src\sec_agent\analyst_view_layer.py src\sec_agent\langgraph_orchestrator.py` 通过。
- Targeted D11 tests：`python -m pytest tests\test_analyst_view_layer.py -q`，`3 passed`。
- D1-D11 artifact regression：`python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py tests\test_derived_metric_layer.py tests\test_analyst_view_layer.py -q`，`21 passed`。
- Graph contract regression：`python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_contracts.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_evidence_requirements.py -q`，`79 passed`。
- Full regression：`python -m pytest -q`，`846 passed`。

## Boundaries

- 当前 D11 是 artifact-backed per-run projection，不是长期 research memory store。
- 当前 D11 不会自动进入 Research Lead planning prompt；D11.1 需要显式接入 lead data view / planning input。
- 当前 D11 不会支持跨 run supersession / stale memory 判断；这些需要 D12 SQL / DB-backed closeout。
- Analyst View 不能支持 claim；下游必须 drill down 到 Claim Evidence Ledger、Typed Gap Ledger 或 Derived Metric Layer。

## Follow-up

- D11.1：把 Analyst View 接入 Research Lead planning input 和 AgentDataView。
- D11.1：补 research memory SQL / vector / graph store、cross-run dedupe、staleness、supersession。
- D12：补 D1-D11 artifact-to-database parity tests，尤其是 memory-to-ledger drilldown parity。
