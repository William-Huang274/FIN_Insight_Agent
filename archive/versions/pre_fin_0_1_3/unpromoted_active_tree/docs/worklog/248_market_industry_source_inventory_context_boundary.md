# 248 Market / Industry Source Inventory Context Boundary

日期：2026-06-07

## Prompt

用户要求在同步本地、云端和工作日志进度后，按照 architecture 文档继续做未完成事项。本轮承接 `247` 的下一步：把 market/industry merged artifacts 写入 source inventory，并保持 context-only source boundary。

## Work Completed

- 扩展 `src/sec_agent/project_inventory.py`：
  - `build_project_inventory(...)` 新增可选 market/industry artifact 参数：
    - `market_evidence_path`
    - `market_snapshot_id`
    - `market_as_of_date`
    - `industry_evidence_path`
    - `industry_snapshot_db_path`
    - `industry_snapshot_id`
    - `industry_as_of_date`
    - `market_industry_manifest_summary_path`
  - inventory 现在可输出：
    - `available_source_families`
    - `source_families`
    - `market_snapshot`
    - `industry_snapshot`
    - `source_boundaries`
  - `market_snapshot` 明确为 `market_or_valuation_context_only`，不能证明公司披露财务事实，不能覆盖 SEC Exact-Value Ledger。
  - `industry_snapshot` 明确为 `industry_context_only`，不能证明公司级 revenue/margin/customer/supplier facts，不能替代公司 filings 或 ledger rows。
  - `inventory_brief(...)` 和 `inventory_prompt(...)` 都能暴露 context-only source family 和边界规则。
- 更新 `scripts/cloud/sec_agent_interactive.py`：
  - 新增 CLI/env 参数：
    - `--industry-snapshot-db-path` / `INDUSTRY_SNAPSHOT_DB_PATH`
    - `--market-industry-manifest-summary-path` / `MARKET_INDUSTRY_MANIFEST_SUMMARY_PATH`
  - `_project_inventory(...)` 透传 market/industry artifact 参数到 `build_project_inventory(...)`。
- 新增测试：
  - `tests/test_project_inventory_source_inventory.py`
  - 覆盖 market/industry artifact path 登记、`available_source_families`、brief 输出、prompt context-only 边界和 forbidden-use 规则。

## Verification

- 本地：
  - `python -m pytest tests\test_project_inventory_source_inventory.py -q`
  - 结果：`1 passed`
- 本地相关回归：
  - `python -m pytest tests\test_sec_agent_industry_snapshot_route.py tests\test_sec_agent_8k_earnings_source.py::test_query_contract_uses_inventory_8k_source_gap_reasons -q`
  - 结果：`6 passed`
- 本地语法检查：
  - `python -m py_compile src\sec_agent\project_inventory.py scripts\cloud\sec_agent_interactive.py`
  - 结果：pass
- 云端同步到：
  - `/autodl-fs/data/fin_agent_milvus_bge_m3/src/sec_agent/project_inventory.py`
  - `/autodl-fs/data/fin_agent_milvus_bge_m3/scripts/cloud/sec_agent_interactive.py`
  - `/autodl-fs/data/fin_agent_milvus_bge_m3/tests/test_project_inventory_source_inventory.py`
- 云端验证：
  - `py_compile` pass。
  - 云端 conda env 没有 `pytest`，因此用 `PYTHONPATH=src /root/miniconda3/bin/python` 运行等价内联断言脚本。
  - 结果：`remote_inline_inventory_check: pass`

## Decision

- Architecture 文档的下一步第 2 项“把 market/industry merged artifacts 写入 source inventory，保持 context-only source boundary”已完成代码和轻量验证。
- 本轮没有把 market/industry 自动提升为默认检索路径；它们只在 inventory / planner prompt / runtime args 层显式登记为 context-only source family。
- `source_tiers` 仍保留为 SEC filing 覆盖计数，不把 `market_snapshot` / `industry_snapshot` 混入 filing coverage check；context-only source 通过 `available_source_families` 暴露给 Research Lead / agent contracts。

## Next

1. 更新 `execute_evidence_operators`，加入 Milvus typed semantic route 和 expanded market/industry catalog path。
2. 更新 Evidence Fusion Selector，让不同 Specialist 看到不同 source-family bundle。
3. 继续先跑 A1-A5 分层 gate，不直接跑 full-chain。
