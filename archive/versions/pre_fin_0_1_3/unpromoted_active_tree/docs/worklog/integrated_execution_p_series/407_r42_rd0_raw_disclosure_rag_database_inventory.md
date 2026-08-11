# 407 R42 RD0 Raw Disclosure / RAG / Database Inventory

日期：2026-06-27

## 问题

用户要求按 24 文档开始下一步。24 的第一步是 RD0：把当前 raw / processed / index / manifest / DB / graph asset 统一盘点成机器可读 inventory，避免继续靠人工目录审计或聊天记忆判断数据底座状态。

## 决策

本轮先做 RD0，不继续扩大爬虫、不改 agent graph、不跑 full-chain。原因：

- 当前最核心缺口是数据主账本分散，而不是单个数据源缺少脚本。
- RD1/RD2/RD3 都需要先知道现有资产、schema、row count、主键、lineage 和 mainline/diagnostic 状态。
- Inventory 本身不应提权任何事实，只作为后续 raw provenance / parser ledger / fact mart / graph store 的基座。

## 完成工作

- 新增 `src/sec_agent/raw_disclosure_data_inventory.py`。
  - 生成 raw disclosure / processed / manifest / graph / authority inventory rows。
  - 生成 BM25/ObjectBM25/SQLite FTS/Dense/Milvus RAG index inventory rows。
  - 生成 Workbench / eval store / duckdb / object store runtime database inventory rows。
  - 区分 `missing_required_path_count` 和 `missing_optional_configured_path_count`，避免把可选空 object-store root 误报为阻断缺口。
- 新增 `scripts/data_expansion/build_raw_disclosure_rag_database_inventory.py`。
- 新增 `tests/test_raw_disclosure_data_inventory.py`。
- 物化 RD0 产物：
  - `data/manifests/raw_disclosure_data_inventory_v0_1.jsonl`
  - `data/manifests/rag_index_inventory_v0_1.jsonl`
  - `data/manifests/runtime_database_inventory_v0_1.jsonl`
  - `data/manifests/raw_disclosure_rag_database_inventory_summary_v0_1.json`
  - `docs/internal/vnext_20260610/rd0_raw_disclosure_rag_database_inventory.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`，记录 RD0 落地状态。
- 更新 `docs/worklog/00_internal_master_checklist.md`，把 RD0 标为完成。

## 结果

最新 RD0 summary：

- status: `pass`
- raw disclosure inventory rows: `31`
- RAG index inventory rows: `19`
- runtime database inventory rows: `11`
- RAG records total: `6,386,029`
- database table count total: `18`
- missing required path count: `0`
- missing optional configured path count: `1`

唯一 optional missing 是 `data/object_store`，状态为 `configured_root_may_be_empty`。这不是 RD0 阻断；RD1/RD3 接 ObjectStore 或 MinIO 时再确定实际目录/服务。

## 验证

- `python -m pytest tests/test_raw_disclosure_data_inventory.py -q`：`3 passed`
- `python -m py_compile src/sec_agent/raw_disclosure_data_inventory.py scripts/data_expansion/build_raw_disclosure_rag_database_inventory.py`：通过
- `python scripts/data_expansion/build_raw_disclosure_rag_database_inventory.py`：通过并物化 RD0 inventory

## 后续

- RD1：Bronze Raw Source Provenance Store。下一步要把 runtime-ready rows 反向追到 raw file / URL snapshot / API response / fetch attempt。
- RD2：Silver Parser / Chunk / Table / Metric Ledger。需要把 parser version、input checksum、row count、drop reason、chunk/table/cell quality 和 rejection taxonomy 入账。
- RD3：Gold Fact / Signal Mart。把现有 financial facts、product facts/signals、customer deployment、capital/ownership/liquidity、macro/industry driver 统一成长期事实/信号主表。
