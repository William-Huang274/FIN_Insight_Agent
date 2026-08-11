# 299 D12.1b/c Full Governance Store And Reader

## Prompt

用户要求继续往 D12.1b、D12.1c 做：在 D12.1a 已把 D1 / D2 / D9 落到 SQLite 后，继续补齐剩余 D3-D8 / D10 / D11 的数据库化，并把 claim/gap/gate history 的跨 run reader 接入 graph。

## Decision

本轮继续沿用显式 DB path 策略：

- 不设置隐藏默认数据库。
- 只有调用方显式传入 `d_series_governance_db_path` / `d_series_database_path` 时，graph 才会读取或写入 D-series governance SQLite。
- 首跑 DB 文件不存在时，`load_session_state` 不创建空库，也不伪造 reader context；persist 阶段负责 schema migration、backfill 和 parity。

D12.1b 的目标是让 D12 closeout gate 在显式 DB path 下可以对 D1-D11 全部 required stores 判定 `database_ready`。

D12.1c 的目标是给 D1 / D2 / D9 先接入 DB-default reader，因为 claim/gap/gate history 是后续 Research Lead、反思、专家 agent 共享上下文最先需要的跨 run 记忆。

## Work Completed

- 扩展 `src/sec_agent/d_series_database_store.py` 到 `sec_agent_d_series_governance_store_v0.2`。
- 新增全 D-series API：
  - `backfill_d_series_governance_artifacts`
  - `parity_check_d_series_governance_artifacts`
  - `materialize_d_series_governance_store`
  - `read_d_series_governance_counts`
  - `read_claim_gap_gate_research_context`
- 保留 D12.1a API 向后兼容：
  - `backfill_d1_d2_d9_governance_artifacts`
  - `parity_check_d1_d2_d9_governance_artifacts`
  - `materialize_d1_d2_d9_governance_store`
  - `read_d1_d2_d9_governance_counts`
- 新增 D3-D8 / D10 / D11 tables：
  - D3：`entity_master`、`security_identifier_map`、`entity_alias_history`、`unresolved_entity_references`
  - D4：`raw_source_documents`、`raw_source_checksums`、`raw_source_parser_runs`、`source_license_robots_policy`
  - D5：`asof_vintage_records`、`macro_vintage_observations`、`market_snapshot_asof`、`filing_amendment_lineage`
  - D6：`reconciliation_candidates`、`reconciliation_groups`、`reconciliation_conflict_gaps`
  - D7：`metric_product_ontology_metrics`、`metric_product_alias_registry`、`metric_product_manual_review_queue`
  - D8：`source_capability_policy`、`source_route_decisions`、`commercial_gap_policy`
  - D10：`derived_metric_formula_registry`、`derived_metric_outputs`、`derived_metric_input_lineage`
  - D11：`analyst_research_memory_entries`、`analyst_view_index`、`thesis_tracker`
- graph persist 从 `materialize_d1_d2_d9_governance_store` 切到 `materialize_d_series_governance_store`。
- graph `load_session_state` 新增 D12.1c reader：
  - 显式 DB path 且文件存在时调用 `read_claim_gap_gate_research_context`。
  - reader context 写入 `d_series_claim_gap_gate_reader_context`。
  - 同步注入 `multi_agent_context["d_series_claim_gap_gate_reader_context"]`。
  - `multi_agent_summary.json` 和 `langgraph_node_checkpoints.json` 暴露 reader status、claim/gap/gate counts。
- 扩展 `tests/test_d_series_database_store.py`：
  - D1/D2/D9 materializer 向后兼容。
  - full D1-D11 materialization parity。
  - D12 closeout gate 在 full materialization 后 `11` 层 ready、`0` pending、`d_series_closeout_allowed=true`。
  - claim/gap/gate reader 跨 run 查询。
  - graph 两轮运行：第一轮写库，第二轮 load 阶段读取上一轮 gap/gate context。

## Result And Evidence

- `python -m py_compile src\sec_agent\d_series_database_store.py src\sec_agent\langgraph_orchestrator.py tests\test_d_series_database_store.py` -> pass。
- `python -m pytest tests\test_d_series_database_store.py -q` -> `4 passed`。
- `python -m pytest tests\test_d_series_database_closeout.py tests\test_d_series_database_store.py -q` -> `7 passed`。
- D1-D12 artifact regression:
  - `python -m pytest tests\test_claim_evidence_gap_ledgers.py tests\test_entity_master_source_capability_router.py tests\test_provenance_vintage_layers.py tests\test_metric_product_ontology_reconciliation.py tests\test_gate_registry_eval_matrix.py tests\test_derived_metric_layer.py tests\test_analyst_view_layer.py tests\test_d_series_database_closeout.py tests\test_d_series_database_store.py -q` -> `28 passed`。
- Graph regression:
  - `python -m pytest tests\test_sec_agent_langgraph_orchestrator.py tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_reflection_second_pass.py tests\test_multi_agent_judgment_memo_verifier.py tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_operator_permissions.py tests\test_multi_agent_activation_plan.py tests\test_milvus_retrieval_ab_design.py -q` -> `165 passed`。
- Full suite:
  - `python -m pytest -q` -> `853 passed`。

当前效果：

- 无显式 DB path：旧行为保持，D12 gate 不会伪造 materialization。
- 显式 DB path：persist 阶段物化 D1-D11；D12 gate 可通过。
- 第二次运行同一个显式 DB path：`load_session_state` 能读取前序 run 的 claim/gap/gate context，并把它放进 shared `multi_agent_context`。

## Follow-up

- D12.1d：把 D3-D8 / D10 / D11 的跨 run read path 也升级为 DB-default reader，并在实际 runtime nodes 中消费，而不只是 closeout/parity。
- D11.1：Analyst View / Research Memory 需要加入 staleness、supersession、dedupe，以及 Milvus cloud/local vector drilldown parity。
- 当前 D4 object-store 是 SQL lineage metadata，不复制原始文件；原文档/raw object 的存放仍由现有 `raw_url` / `local_path` / checksum / parser run lineage 管理。
