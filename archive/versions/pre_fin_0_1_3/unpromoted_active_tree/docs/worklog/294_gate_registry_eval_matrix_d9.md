# D9 Gate Registry / Gate History / Eval Matrix Runtime Projection

## Prompt

用户要求继续按 `07`、`08` 文档执行顺序推进。D7/D6 已完成后，下一步是 D9 Gate Registry / Gate History / Eval Matrix，用来把 source boundary、citation、period、unit、numeric、metric mapping、entity resolution、claim support、contradiction、staleness、commercial gap 等 gate 从散落的 artifact / summary 信号中收束成可审计矩阵。

## Decision

本轮先落地 per-run runtime projection，而不是直接做最终 SQL-backed gate engine：

- 先固定 gate registry、gate run record 和 eval matrix schema，否则后续 hard gate 和 DB schema 会缺少稳定 contract。
- Gate history 从 D1-D8 已落地 artifacts 投影，确保每个 gate 不是 prompt-only 规则。
- 当前 D9 只在 graph persist 阶段生成审计 artifact，不冒充 Memo Writer 前的最终阻断器。
- Pre-Memo hard gate、SQL-backed append-only history 和 eval fixture replay 作为 D9.1。

## Work Completed

- 新增 `src/sec_agent/gate_registry.py`。
  - schema version：`sec_agent_gate_registry_eval_matrix_v0.1`。
  - 注册 12 个 gates：source boundary、citation span、period alignment、unit normalization、numeric consistency、metric mapping、segment mapping、entity resolution、claim support、contradiction、staleness、commercial gap。
  - 从 `source_capability_router`、`raw_source_provenance_store`、`asof_vintage_layer`、`entity_security_master`、`metric_product_ontology_snapshot`、`reconciliation_ledger`、`claim_evidence_ledger`、`typed_gap_ledger` 生成 gate history。
  - 输出 per-gate pass / warn / fail / not_applicable eval matrix、blocking fail count、source-boundary coverage 和 weak-proxy fallback coverage。
- 更新 `src/sec_agent/langgraph_orchestrator.py`。
  - persist 阶段在 D4/D5、D7/D6、D3/D8、D1/D2 后生成 `gate_registry_eval_matrix`。
  - 写出 `gate_registry_eval_matrix.json`。
  - `artifact_refs`、`multi_agent_summary.json`、`langgraph_node_checkpoints.json` 暴露 D9 summary。
- 新增 `tests/test_gate_registry_eval_matrix.py`。
  - 覆盖 source boundary blocked route、commercial tracker gap、unit conflict、unmapped metric、supported claim、contradicted claim。
  - 覆盖 graph persist artifact、summary 和 checkpoint recoverable summary。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 和 `00_internal_master_checklist.md`。

## Result And Evidence

- Syntax check：`python -m py_compile src\sec_agent\gate_registry.py src\sec_agent\langgraph_orchestrator.py` 通过。
- Targeted D9 tests：`python -m pytest tests\test_gate_registry_eval_matrix.py -q`，`2 passed`。
- D1-D9 artifact regression：`python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py -q`，`15 passed`。
- Graph regression：`python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_contracts.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_evidence_requirements.py -q`，`79 passed`。
- Full regression：`python -m pytest -q`，`840 passed`。

## Boundaries

- 当前 D9 是 artifact-backed projection，不是最终的 online gate service。
- 当前 gate history 由单次 run state 投影，不是 SQL-backed append-only store。
- 当前 graph 仍未把所有 blocking fail 前移成 Memo Writer 前硬拦截；D9.1 需要接 pre-Memo checkpoint。
- 当前 eval matrix 有 source-boundary violation 和 weak proxy fallback coverage 检查，但还需要正式 fixture matrix 回放全部 gate 类型。

## Follow-up

- D9.1：前移 hard gate checkpoint、接 SQL-backed gate history、补 eval fixture matrix 和 D5/D6/D8/D2 统一阻断规则。
- D10：Derived Metric Layer 需要消费 D6 preferred facts 和 D9 gate status，保存 formula、input_fact_ids、calculation_version、gate_status 和 explainability_trace。
