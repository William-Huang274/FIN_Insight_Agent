# D12 D-series Database Closeout Gate v0.1

## Prompt

用户确认继续推进 D 系列最后阶段。前面 D1-D11 都已经以 per-run JSON / artifact-backed runtime projection 落地，但用户之前明确提醒：D4.1 / D5.1 等 SQL / 数据库部分可以暂时不做，但 D 系列全部做完后，需要上数据库的部分必须补齐，不能遗漏。

## Decision

本轮先落地可执行的 closeout gate，而不是一次性把 D1-D11 全部迁进数据库：

- Gate 需要逐层列明 DB 要求、schema objects、migration id、backfill job、parity test 和 reader default policy。
- 当前没有真实 DB materialization，因此 D12 gate 应显示 `blocked`，`d_series_closeout_allowed=false`。
- `blocked` 是正确状态：它防止把 per-run JSON artifacts 误宣称为 D 系列 fully closed。
- 实际 schema migrations、backfill jobs、parity tests 和 DB-default readers 作为 D12.1。

## Work Completed

- 新增 `src/sec_agent/d_series_database_closeout.py`。
  - schema version：`sec_agent_d_series_database_closeout_gate_v0.1`。
  - 注册 D1-D11 共 11 个 required DB-backed layers。
  - 每层包含 `store_kind`、`schema_objects`、`migration_id`、`backfill_job`、`parity_test`、`reader_default_policy`。
  - 支持读取可选 `d_series_database_materialization` 状态；只有 migration applied、backfill complete、parity pass、reader default database 四项都满足时，该层才算 `database_ready`。
- 更新 `src/sec_agent/langgraph_orchestrator.py`。
  - persist 顺序变为 D4/D5 -> D7/D6 -> D9 -> D10 -> D11 -> D12。
  - 写出 `d_series_database_closeout_gate.json`。
  - `artifact_refs`、`multi_agent_summary.json` 和 `langgraph_node_checkpoints.json` 暴露 D12 summary。
- 新增 `tests/test_d_series_database_closeout.py`。
  - 覆盖未 materialize 时 gate blocked。
  - 覆盖 materialization 全部 pass 时 closeout allowed。
  - 覆盖 graph artifact persist、summary 和 checkpoint。
- 更新 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 和 `00_internal_master_checklist.md`。

## Result And Evidence

- Syntax check：`python -m py_compile src\sec_agent\d_series_database_closeout.py src\sec_agent\langgraph_orchestrator.py` 通过。
- Targeted D12 tests：`python -m pytest tests\test_d_series_database_closeout.py -q`，`3 passed`。
- D1-D12 artifact regression：`python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py tests\test_derived_metric_layer.py tests\test_analyst_view_layer.py tests\test_d_series_database_closeout.py -q`，`24 passed`。
- Graph contract regression：`python -m pytest tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_contracts.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_evidence_requirements.py -q`，`79 passed`。
- Full regression：`python -m pytest -q`，`849 passed`。

## Current Gate Status

- 当前 D12 gate status：`blocked`。
- 当前 `d_series_closeout_allowed=false`。
- 当前 pending required DB layers：D1-D11 全部 11 层。
- 这是预期状态，因为本轮没有实现真实 SQL / object-store materialization。

## Boundaries

- 本轮没有创建真实数据库表。
- 本轮没有写入 SQL migration 文件。
- 本轮没有实现 backfill job 或 parity test 的执行脚本。
- 本轮没有把任何 agent 的跨 run 读取默认切到 DB 层。

## Follow-up

- D12.1：实现 SQL / object-store schema migrations。
- D12.1：实现 artifact -> database backfill jobs。
- D12.1：实现 artifact-to-database parity tests。
- D12.1：将跨 run claim/gap/source/vintage/gate/derived/memory 读取默认切到 DB 层。
