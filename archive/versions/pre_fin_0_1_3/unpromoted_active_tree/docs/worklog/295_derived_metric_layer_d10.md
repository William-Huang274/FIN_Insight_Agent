# D10 Derived Metric Layer Runtime Projection

## Prompt

用户要求继续按 `07`、`08` 文档执行顺序推进。D9 Gate Registry / Gate History / Eval Matrix 完成后，下一步是 D10 Derived Metric Layer，用来把 YoY / QoQ growth、margin、FCF、net debt、inventory days、revenue per unit、ASP / ARPU / take rate 等派生指标从普通事实层中拆出来，并保存公式和 lineage。

## Decision

本轮落地 per-run runtime projection：

- D10 只从 D6 `reconciliation_ledger` 的 resolved preferred values 取输入。
- D10 必须读取 D9 `gate_registry_eval_matrix`，若输入 fact 有 blocking gate，则不生成派生值，只写 `skipped_derivations`。
- D10 不估算缺失输入，不把 public proxy、market snapshot、Milvus 或上下文行提权为派生事实。
- D7 ontology 只补充必要输入 fact：`operating_cash_flow`、`cost_of_revenue`、`inventory`；`gross_margin`、`operating_margin`、`ASP` 等仍只能由 D10 formula 生成。

## Work Completed

- 新增 `src/sec_agent/derived_metric_layer.py`。
  - schema version：`sec_agent_derived_metric_layer_v0.1`。
  - calculation version：`deterministic_reconciled_fact_formula_v0.1`。
  - 输出 `input_facts`、`derived_metrics`、`skipped_derivations`、summary 和 validation。
  - 每条 derived metric 保存 `formula`、`input_fact_ids`、`calculation_version`、`value`、`unit`、`gate_status`、`explainability_trace`。
  - 当前支持 gross margin、operating margin、free cash flow、free cash flow margin、net debt、inventory days、take rate、ARPU、ASP、YoY / QoQ growth。
- 更新 `src/sec_agent/metric_product_ontology.py`。
  - 增加 `financial_metric:operating_cash_flow`、`financial_metric:cost_of_revenue`、`financial_metric:inventory`。
- 更新 `src/sec_agent/langgraph_orchestrator.py`。
  - persist 顺序变为 D4/D5 -> D7/D6 -> D9 -> D10。
  - 写出 `derived_metric_layer.json`。
  - `artifact_refs`、`multi_agent_summary.json` 和 `langgraph_node_checkpoints.json` 暴露 D10 summary。
- 新增 `tests/test_derived_metric_layer.py`。
  - 覆盖正常公式派生、输入 gate blocking、graph artifact persist。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 和 `00_internal_master_checklist.md`。

## Result And Evidence

- Syntax check：`python -m py_compile src\sec_agent\derived_metric_layer.py src\sec_agent\metric_product_ontology.py src\sec_agent\langgraph_orchestrator.py` 通过。
- Targeted D10 tests：`python -m pytest tests\test_derived_metric_layer.py -q`，`3 passed`。
- D7-D10 targeted regression：`python -m pytest tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py tests\test_derived_metric_layer.py -q`，`8 passed`。
- D1-D10 artifact regression：`python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py tests\test_derived_metric_layer.py -q`，`18 passed`。
- Graph contract regression：`python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_contracts.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_evidence_requirements.py -q`，`79 passed`。
- G11 / barrier / Milvus related regression：`python -m pytest tests\test_multi_agent_real_llm_chain_eval.py tests\test_multi_agent_operator_permissions.py tests\test_project_inventory_source_inventory.py -q`，`52 passed`；`python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_evidence_requirements.py -q`，`50 passed`。
- Full regression：`python -m pytest -q`，`843 passed`。

## Boundaries

- 当前 D10 是 artifact-backed per-run projection，不是 SQL-backed formula registry。
- 当前 D10 还没有前移到 Memo Writer / ClaimCard fact selection；Memo 是否使用 derived metric 仍需 D10.1。
- 当前公式只支持确定性、低歧义公式；ROIC、复杂 working-capital、segment-only mixed margin 等需要更完整 balance sheet / invested capital ontology 后再接。
- ASP / ARPU / take rate 只在公司披露 revenue 和对应 unit / subscribers / GMV 都是 D6 resolved exact facts 时生成；公开价格、排名、流量或行业 proxy 不会生成公司 ASP。

## Follow-up

- D10.1：把 Derived Metric Layer 接入 Memo Writer / ClaimCard fact selection。
- D10.1：补 formula registry / derived output SQL store、artifact-to-database parity test。
- D11：Analyst View / Research Memory 应引用 Claim Evidence Ledger、Gap Ledger 和 D10 derived metrics，但不能把 view 当原始事实来源。
