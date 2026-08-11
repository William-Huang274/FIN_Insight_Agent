# 406 R42 Raw Disclosure / RAG / Database Recap

日期：2026-06-26

## 问题

用户澄清下一步不是只审计产品图谱，而是要“从原始的 SEC / 非美市场披露开始，基于整个 RAG、数据库（包括现在和未来打算做的）做一次整理和复盘，再去做下一步规划”。

## 判断

当前项目已经有较多数据和 runtime 能力，但数据账本仍分散：

- SEC 原文、SEC structured facts、非美 disclosure、产品/客户/资本/市场 rows 分散在 `data/raw_private`、`data/staging`、`data/processed_private`、`data/indexes`、`data/manifests`、`data/workbench_private` 和 Z 盘 Milvus artifact。
- `run_audit_store` 已能复盘单次 agent run；`d_series_database_store` 已能把 D1-D11 governance artifacts SQL 化；但 600+ 公司长期研究数据仓库还没有统一为 raw source / parser run / fact mart / graph store / retrieval registry 主账本。
- SEC 链路强于非美链路。SEC structured facts 已有 588 家、约 279 万 financial fact rows；非美 L1 financial rows 覆盖 16/16 target tickers，但 local exchange / company IR / PDF table parser 仍需要统一到 raw provenance 和 parser ledger。
- RAG 层已经有 BM25/ObjectBM25/SQLite FTS/Milvus，但索引不是事实库；检索命中必须能追溯到 raw source、parser run、authority row。

## 完成工作

- 新增 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`。
- 文档按以下链路复盘：
  - 原始 SEC / 非美披露入口。
  - raw lake、structured facts、processed chunks/evidence/objects、BM25/ObjectBM25/SQLite FTS、Milvus。
  - source authority mart、ProductRelationshipGraph、ProductProfile/ProductSpec/Product-KPI、CustomerDeployment、capital/funding/ownership、market liquidity。
  - run audit store、D-series governance DB、ObjectStore、PathRegistry。
  - Research Lead / specialist / Memo Writer 当前可消费对象与缺口。
- 在 24 文档中提出 RD0-RD7 下一阶段：
  - RD0 Data Inventory Freeze。
  - RD1 Bronze Raw Source Provenance Store。
  - RD2 Silver Parser / Chunk / Table / Metric Ledger。
  - RD3 Gold Fact / Signal Mart。
  - RD4 Graph Store v0.1。
  - RD5 RAG Index Registry 与 Retrieval Parity。
  - RD6 Agent Runtime Consumption Contract。
  - RD7 Data Quality / Release Eval Gate。

## 证据

审计中读取的关键事实：

- `data/raw_private`：约 12.9GB，包含 `company_ir`、`global_public_disclosures`、`sec`、`sec_filings`、`sec_8k_earnings`、`sec_tier1_sp500_annual`、`sec_tier2_supply_chain_annual`、`structured_financial_facts`。
- `sec_structured_facts_download_summary_v0_1.json`：588 家 CompanyFacts/submissions；financial fact rows `2,790,261`。
- `sec_financial_statement_metric_runtime_summary_v0_1.json`：runtime rows `10,146`，覆盖 `587/603`。
- `tier2_supply_chain_sec_annual_staging_assets_summary_v0_2.json`：30,600 chunks/evidence rows、48,977 tables、421,828 metrics、240,694 claims、711,499 SQLite FTS records。
- `non_us_l1_financial_statement_metric_runtime_summary_v0_1.json`：非美 L1 financial rows `88`，覆盖 `16/16` target tickers。
- `non_us_product_kpi_local_disclosure_runtime_summary_v0_1.json`：非美 product KPI rows `70`，覆盖 `11/15` target tickers。
- `configs/runtime/milvus_runtime_603_local_v0_1.json`：本地 Milvus Lite 可用，`662,908` vectors，`581` indexed tickers，边界为 semantic recall supplement。
- `r18_source_authority_data_mart_summary_v0_1.json`：source authority mart `7,181` rows。
- `product_relationship_graph_summary_v0_1.json`：`8,187` nodes、`25,251` edges、`741` parser-backed relationship edges。

## 测试

- 本轮为 docs / audit / planning 任务，未运行 pipeline、full-chain、LLM 或数据重建。
- 待运行：`git diff --check` 覆盖新增文档和索引更新。

## 后续

- 下一步应先做 RD0 机器可读 inventory，而不是先继续扩大爬虫或重写 graph。
- RD0 通过后，再推进 RD1/RD2，把 raw source 和 parser run 血缘补强；随后把 Gold Fact / Signal Mart 与 Graph Store 接入 Research Lead。
