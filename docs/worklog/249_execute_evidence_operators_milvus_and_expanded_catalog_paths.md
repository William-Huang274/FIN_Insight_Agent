# 249 Execute Evidence Operators Milvus Route And Expanded Catalog Paths

日期：2026-06-07

## Prompt

承接 `248` 后继续按 `expanded_universe_retrieval_agent_framework_v0_1.zh-CN.md` 的下一步推进：更新 `execute_evidence_operators`，加入 Milvus typed semantic route 和 expanded market/industry catalog path。

## Work Completed

- 新增 runtime route contract：
  - `milvus_semantic` 加入 retrieval-plan 白名单。
  - `milvus_semantic -> sec_operator / sec_milvus_semantic_search`。
  - source family 仍归 `primary_sec_filing`，保持 Milvus 是 SEC filing 语义补召回，不是新事实源。
  - route arguments 必须带 `vector_kinds` typed filter；默认候选为 `narrative_chunk`、`table_chunk`、`paraphrase_context`，关系/指标语境会补 `relationship_context`、`metric_row`、`table_row`。
- 新增 MCP/tool 权限合同：
  - `sec_milvus_semantic_search` 加入 MCP contract、operator allowlist 和 agent registry。
  - observation boundary 要求返回 `vector_kind_counts` 或 row-level `vector_kind`，并标记 `prohibited_claim_scope=exact_value_authority`。
  - 默认 handler 返回明确 `milvus_semantic_config_missing` / `milvus_semantic_runtime_not_bound` source gap，避免未绑定真实搜索器时 silent success。
- 扩展 market/industry catalog path wiring：
  - 新增 `MARKET_CATALOG_PATH` / `market_catalog_path` 到 Workbench profile、source bundle、source readiness、data-build artifact update、cloud interactive CLI、context-session wrapper、eval evidence-operator gate。
  - `INDUSTRY_SNAPSHOT_DB_PATH` 已进入 eval gate multi-agent context。
  - `build_project_inventory(...)` 的 `market_snapshot` block 现在也记录 `catalog_path`。
  - market MCP handler 会把 `market_catalog` 作为 artifact ref 保留，但仍以 `market_evidence_path` JSONL 返回 bounded rows。
- Planner / prompt boundary：
  - 云端 planner route 白名单和 prompt 说明加入 `milvus_semantic`。
  - prompt 明确 `milvus_semantic` 只能是 SEC filing typed semantic 补召回，不得替代 `ledger_first`。

## Verification

- 本地语法检查：
  - `python -m py_compile ...`
  - 覆盖 runtime、retrieval plan、MCP contracts/tool registry、agent registry、workbench profile/source bundle、cloud CLI、evidence-operator eval gate。
  - 结果：pass
- 本地 targeted tests：
  - `python -m pytest tests\test_multi_agent_operator_permissions.py tests\test_multi_agent_agent_registry.py tests\test_project_inventory_source_inventory.py tests\test_workbench_profiles.py -q`
  - 结果：`32 passed`
  - `python -m pytest tests\test_sec_agent_retrieval_plan.py tests\test_sec_agent_mcp_runtime_tools.py -q`
  - 结果：`23 passed`
  - `python -m pytest tests\test_workbench_job_runner.py::test_data_build_catalog_and_command_preview_are_whitelisted -q`
  - 结果：`1 passed`
- 云端同步到 `/autodl-fs/data/fin_agent_milvus_bge_m3`：
  - runtime / retrieval plan / MCP / registry / Workbench / cloud scripts / targeted tests 均已上传。
  - 云端 `PYTHONPATH=src /root/miniconda3/bin/python -m py_compile ...` pass。
  - 云端 inline contract check pass：`remote_milvus_route_contract_check: pass`。

## Decision

- Architecture 下一步第 3 项“更新 `execute_evidence_operators`，加入 Milvus typed semantic route 和 market/industry expanded catalog path”已完成到 runtime contract / wiring / diagnostic gate。
- 本轮没有把 Milvus 设为默认 full-chain 检索路径，也没有实现新的 production Milvus search handler；真实搜索能力仍以 `247` 的 retrieval-only A/B 作为证据。
- 当前主线行为是：如果 route 明确请求 `milvus_semantic` 且 runtime 注入真实 executor，则可执行；否则默认 handler 返回 source gap，要求后续显式绑定。

## Next

1. 更新 Evidence Fusion Selector，让不同 Specialist 看到不同 source-family bundle。
2. 更新 Research Lead prompt/skill，让它按成本和问题类型选择 route。
3. 更新 Specialist skill vNext，特别是 Market 和 Industry 的 source boundary。
4. 先跑 A1-A5 分层 gate，不直接跑 full-chain。
