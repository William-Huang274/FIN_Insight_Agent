# 242 Tier2 Supply Chain SEC Annual Staging Assets

## Prompt

用户确认可以开始做 Tier2，并决定未来 full ledger 本地化直接从云端下载成品，不再本地重建。

## Reasoning And Decision

- Tier2 拆成两条 staging shard：SEC 可拉取公司先复用已验证的 SEC 年报路径；非美非 SEC 公司继续走 global public disclosure profile。
- Tier2 SEC 公司不能用统一 `10-K` 口径；需要按公司 `target_forms` 选择 `10-K`、`20-F`、`40-F` 年度主表单，排除 `10-Q`、`8-K`、`6-K`。
- 20-F 不能按 10-K Item 规则切片。将 20-F 的核心披露映射到现有证据语义：`3.D -> 1A`、`4/4.B -> 1`、`5 -> 7`、`11 -> 7A`、`18 -> 8`，从而复用下游 evidence type、Specialist 和检索合同。
- 40-F 不能只读 primary wrapper；真正有价值的 Annual Information Form、MD&A、audited financial statements 通常在 exhibits 中。本轮后续补了 `40-F.annual_package.html`，把核心 exhibits 合成一个本地年报包供下游读取。

## Work Completed

- 更新 SEC 年报下载配置生成器：
  - `scripts/data_expansion/build_sec_annual_download_config.py`
  - 支持公司级 `form_types`，按 `target_forms` 保留年度主表单。
- 更新 SEC 下载器：
  - `scripts/data_sec/download_sec_filings.py`
  - 同一配置内支持逐公司不同 `form_types`。
- 更新 20-F / 断行 Item parser：
  - `src/ingestion/section_splitter.py`
  - 支持 20-F section mapping。
  - 支持 `Item` 被抽成 `Ite` / `m 1. Business` 的 10-K 断行形态。
- 更新 40-F 年报包和 parser：
  - `src/connectors/sec_edgar_connector.py`
  - `src/connectors/sec_filing_manifest.py`
  - `src/ingestion/section_splitter.py`
  - 下载/缓存命中时为 40-F materialize Annual Information Form、audited financial statements、MD&A exhibits。
  - manifest 优先读取 metadata 中的 `local_html_path`，因此 40-F 默认指向 `40-F.annual_package.html`。
  - 40-F 默认映射到 `1/1A/7/8`，不默认切 `7A`，避免 `financial instruments` 把 MD&A/财报大片内容误切走。
- 更新 evidence schema：
  - `src/evidence/schema.py`
  - `source_type` 增加 `20-F`、`40-F`。
- 新增/更新测试：
  - `tests/test_sec_annual_download_config.py`
  - `tests/test_sec_20f_section_splitter.py`
  - `tests/test_sec_40f_annual_package.py`
  - `tests/test_evidence_schema_global_public.py`
- 新增 Tier2 SEC staging registry：
  - `configs/data_sources/layered_staging_datasets_v0_1.yaml`
- 生成 Tier2 SEC staging summary：
  - `data/manifests/tier2_supply_chain_sec_annual_staging_assets_summary_v0_1.json`

## Result And Evidence

Tier2 SEC 年度主披露下载配置：

- 配置：`configs/data_sources/tier2_supply_chain_sec_annual_fy2023_2025.yaml`
- 公司：`83`
- 年份：`2023-2025`
- 年度主表单：`10-K`、`20-F`、`40-F`
- 预期任务：`249`

真实 SEC 下载：

- 成功：`226`
- 缺口：`23`
- 成功表单分布：`10-K=143`、`20-F=77`、`40-F=6`
- 缺口表单分布：`10-K=13`、`20-F=7`、`40-F=3`
- 原始缓存：`data/raw_private/sec_tier2_supply_chain_annual`

Staging 数据：

- filing manifest：`226` records
- chunks：`30600`
- evidence：`30600`
- 结构化对象：
  - tables：`48977`
  - metrics：`421828`
  - claims：`240694`
- Evidence BM25：`30600` records
- SQLite FTS 结构化对象库：`711499` records
- exact-value ledger：`392015` facts
- chunk quality audit：`pass`

20-F parser 修复效果：

- 修复前 20-F chunks：`241`
- 修复后 20-F chunks：`13316`
- DIOD 断行 10-K 修复后不再 zero-chunk。
- 40-F 修复后：`CCJ`、`TECK` 共 `6` 份 40-F 全部 materialized annual package，zero-chunk 从 `6` 降为 `0`。
- 40-F chunks：`2435`，纳入 `business_description`、`risk_disclosure`、`management_discussion`、`financial_statement_or_note`。

验证命令：

```powershell
python -m pytest tests\test_sec_annual_download_config.py tests\test_sec_20f_section_splitter.py tests\test_sec_40f_annual_package.py tests\test_evidence_schema_global_public.py -q
python -m compileall src\connectors\sec_edgar_connector.py src\connectors\sec_filing_manifest.py src\ingestion\section_splitter.py src\evidence\schema.py scripts\data_expansion\build_sec_annual_download_config.py scripts\data_sec\download_sec_filings.py
python scripts\eval_retrieval\audit_sec_chunk_quality.py --chunks-path data\staging\sec_tier2_supply_chain_annual\chunks\tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl --evidence-path data\staging\sec_tier2_supply_chain_annual\evidence\tier2_supply_chain_sec_annual_evidence_fy2023_2025_v0_1.jsonl --bm25-index-dir data\indexes\staging\bm25\tier2_supply_chain_sec_annual_fy2023_2025_v0_1 --object-bm25-index-dir data\indexes\staging\sqlite_fts\tier2_supply_chain_sec_annual_objects_fy2023_2025_v0_1 --output-dir eval\sec_cases\outputs\chunk_quality_audit --run-id 20260606_tier2_supply_chain_sec_annual_chunk_quality_v0_1
```

验证结果：

- Targeted tests：`10 passed`
- compileall：pass
- chunk quality audit：`pass`

## Follow-Up

- 40-F：annual package 已完成；后续只需要继续收紧 CCJ AIF front matter / table-of-contents 噪声。
- 20-F/40-F ledger：补 currency/value-role/ranking gate，避免 TSM/ASML/CCJ 这类 query 首位混入百分比或合同资产行。
- Global-public 非 SEC：继续实现 DART、MOPS、EDINET、HKEX、CNINFO profile-specific downloader；company IR fallback 已加显式 gate，但不能当成监管源实现完成。
- Promotion：当前仍是 `staging_only`，不能覆盖主线 index；等待 Tier2 global-public parser/source-boundary gate 和 relationship R1-R5 后再合并召回。

## Safety Notes

- 没有写入 API key、SSH 密码或私有 token。
- 原始 SEC HTML、BM25、SQLite FTS、ledger 和 eval runtime outputs 都是本地 staging/generated/private 资产，不应提交到公开仓库。
- full ledger 本地化后续按用户决定：从云端下载成品，不在本地重跑 full build。
