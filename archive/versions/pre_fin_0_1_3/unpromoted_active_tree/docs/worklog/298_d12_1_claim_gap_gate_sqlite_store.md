# 298 D12.1 Claim / Gap / Gate SQLite Store

## Prompt

用户要求继续 D 系列数据库化工作，并明确 D4.1 / D5.1 这类 SQL / DB-backed 补账后续不能忘。当前轮先按 D12 closeout gate 的顺序，把可先物化且对 agent 研报证据链最关键的 D1 / D2 / D9 落到真实数据库合同。

## Decision

本轮不把 D1-D11 一次性全迁完，先做 D12.1a：

- D1 Claim Evidence Ledger：公司 claim、supporting / contradicting refs、gap refs、gate refs。
- D2 Typed Gap Ledger：typed gap events、source attempts、commercial data requirements。
- D9 Gate Registry / History / Eval Matrix：gate registry、per-run gate history、eval matrix。

物化入口必须显式传入 `d_series_governance_db_path` 或 `d_series_database_path`。没有显式路径时 graph 不写隐藏默认库，D12 gate 继续保持 `blocked`，避免把 per-run JSON artifact 误当成 DB closeout。

## Work Completed

- 新增 `src/sec_agent/d_series_database_store.py`。
  - `migrate_d_series_governance_store`
  - `backfill_d1_d2_d9_governance_artifacts`
  - `parity_check_d1_d2_d9_governance_artifacts`
  - `materialize_d1_d2_d9_governance_store`
  - `d_series_materialization_state_from_report`
  - `read_d1_d2_d9_governance_counts`
- SQLite schema 覆盖：
  - `claim_evidence_claims`
  - `claim_evidence_support_refs`
  - `claim_evidence_gap_refs`
  - `claim_evidence_gate_refs`
  - `typed_gap_events`
  - `typed_gap_source_attempts`
  - `typed_gap_commercial_requirements`
  - `gate_registry`
  - `gate_history`
  - `gate_eval_matrix`
- graph persist 顺序改为：
  - D4/D5
  - D6/D7
  - D9
  - D10
  - D11
  - D12.1 optional database materialization
  - D12 database closeout gate
- 有显式 DB path 时写出 `d_series_database_materialization_report.json`，并把 D1 / D2 / D9 三层 materialization 状态传给 D12 closeout gate。
- `multi_agent_summary.json` 和 `langgraph_node_checkpoints.json` 新增 D12.1 materialization 摘要字段。
- 新增 `tests/test_d_series_database_store.py`，覆盖 store parity、D12 closeout readiness、graph optional materialization。
- 更新 `docs/architecture/agent_graph_vnext/08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 和 master checklist，把 D12.1 拆成 D12.1a / D12.1b / D12.1c。

## Result And Evidence

- `python -m py_compile src\sec_agent\d_series_database_store.py src\sec_agent\langgraph_orchestrator.py` -> pass。
- `python -m pytest tests\test_d_series_database_store.py tests\test_d_series_database_closeout.py -q` -> `5 passed`。
- `python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py tests\test_derived_metric_layer.py tests\test_analyst_view_layer.py tests\test_d_series_database_closeout.py tests\test_d_series_database_store.py -q` -> `26 passed`。
- `python -m pytest tests\test_sec_agent_langgraph_orchestrator.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_reflection_second_pass.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_operator_permissions.py tests\test_multi_agent_activation_plan.py tests\test_milvus_retrieval_ab_design.py -q` -> `165 passed`。
- `git diff --check` -> pass。
- `python -m pytest -q` -> `851 passed`。

当前效果：

- 未显式提供 DB path：D12 gate 行为不变，`database_ready_layer_count=0`，`pending_required_database_layer_count=11`。
- 显式提供 DB path：D1 / D2 / D9 三层 schema migration、backfill、parity、reader default status 均达标，D12 gate 显示 `database_ready_layer_count=3`、`pending_required_database_layer_count=8`。
- D 系列整体 closeout 仍不能通过，因为 D3-D8 / D10 / D11 尚未完成 DB/object/vector store 与 DB-default reader。

## Follow-up

- D12.1b：补 D3-D8 / D10 / D11 的 SQL / object-store / vector-store schema、backfill、parity。
- D12.1c：把 D1 / D2 / D9 的跨 run agent reads 从 per-run artifact 查询升级为 DB-default reader。
- D11.1 需要和 Milvus runtime switch 联动：云端 Milvus / 本地 Milvus 的 collection schema、vector lineage、claim/gap/derived drilldown parity 需要单独落库和测试。
