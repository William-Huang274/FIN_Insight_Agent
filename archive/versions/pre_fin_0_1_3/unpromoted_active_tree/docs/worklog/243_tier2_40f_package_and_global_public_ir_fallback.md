# 243 Tier2 40-F Package And Global Public IR Fallback

## Prompt

用户确认可以继续做 Tier2，并说明未来 full ledger 本地化直接从云端下载成品，不再在本地重建 full ledger。

## Work Completed

- 补齐 40-F 年报包：
  - `src/connectors/sec_edgar_connector.py`
  - `src/connectors/sec_filing_manifest.py`
  - `src/ingestion/section_splitter.py`
  - 对 40-F 自动 materialize `40-F.annual_package.html`，包含 Annual Information Form、audited financial statements、MD&A。
  - 支持 CCJ 这类 exhibit index 没有描述但文件名为 `dex991/dex992/dex993` 的加拿大 40-F。
  - manifest 优先读取 metadata 中的 `local_html_path`，确保下游读 annual package 而不是 wrapper。
- 补齐测试：
  - `tests/test_sec_40f_annual_package.py`
  - `tests/test_sec_20f_section_splitter.py`
- 重建 Tier2 SEC staging：
  - chunks / evidence / structured objects / BM25 / SQLite FTS / exact-value ledger。
  - 新 summary：`data/manifests/tier2_supply_chain_sec_annual_staging_assets_summary_v0_2.json`。
- 给 global-public 下载器增加显式 company IR fallback gate：
  - `scripts/data_expansion/download_global_public_disclosures.py`
  - 默认仍不回退；只有传 `--allow-company-ir-fallback` 且任务允许 `company_ir` 时，才走官网 IR 候选发现。
  - 年报类任务必须命中 annual/business/integrated/securities report 词；不会再只靠年份+PDF 误选 interim PDF。

## Results

- 40-F materialization：
  - CCJ / TECK 2023-2025 共 `6` 份 40-F 全部生成 `40-F.annual_package.html`。
  - 40-F zero-chunk 从 `6` 降为 `0`。
  - Tier2 SEC chunks 从 `28165` 增至 `30600`。
  - 40-F chunks：`2435`。
- Tier2 SEC rebuilt assets：
  - evidence：`30600`
  - structured tables：`48977`
  - structured metrics：`421828`
  - structured claims：`240694`
  - ledger facts：`392015`
  - chunk quality audit：`pass`
- Retrieval smoke：
  - CCJ 40-F BM25 能命中 nuclear fuel cycle / customers / Westinghouse 业务证据。
  - TECK / ARM ledger revenue smoke 能命中金额行。
  - CCJ revenue ledger 仍有百分比行排在金额行前，需要后续 currency/value-role ranking gate。
- Samsung global-public fallback smoke：
  - v0.1 暴露问题：官网候选曾误选 `2023_Half_Interim_Report.pdf`。
  - 已修复 scoring。
  - v0.3 正确拒绝 interim PDF，结果为 `no_matching_document_candidate`，并覆盖 metadata，避免旧错误下载状态被误读。

## Gates

- `python -m pytest tests\test_sec_40f_annual_package.py tests\test_sec_20f_section_splitter.py -q`：`6 passed`
- `python -m pytest tests\test_global_public_disclosure_download_tasks.py -q`：`10 passed`
- `python -m compileall src\connectors\sec_edgar_connector.py src\connectors\sec_filing_manifest.py src\ingestion\section_splitter.py scripts\data_expansion\download_global_public_disclosures.py`：pass
- chunk quality audit：`20260606_tier2_supply_chain_sec_annual_chunk_quality_v0_2` pass

## Remaining Gaps

- 40-F AIF 仍有 front matter / table-of-contents 噪声，当前可以做 staging 检索，但 mainline promotion 前应继续细化 Canadian annual parser。
- 20-F/40-F exact-value ledger 需要 currency/value-role 排序，防止 revenue 这类查询首位出现百分比行。
- DART / MOPS / EDINET / HKEX / CNINFO profile-specific downloader 仍未完成；company IR fallback 只是显式开启的 staging-only 兜底。
- 非 SEC global-public parser/chunk/index/Milvus 还没有接入。

## Safety Notes

- 没有写入 API key、SSH 密码或私有 token。
- 原始 SEC HTML、非 SEC PDF、BM25、SQLite FTS、ledger、eval outputs 都是本地 generated/private 资产，不应进入公开仓库。
- full ledger 本地化后续按用户决策直接从云端下载成品。
