# 240 Global Public Disclosure Company IR Download Smoke

## Prompt

用户要求继续下一步，并提醒除美国外证券市场披露合同不要按单家公司写死口径；后续新增同地区或同交易所公司时，规则应从 profile 层继承。

## Reasoning And Decision

- 上一轮只生成了 `69` 条全球公开披露 dry-run 下载任务，`document_downloaded_count=0`，还不能进入证据库。
- 本轮先实现一个可复用的 `company_ir_official_report_download` 策略，用于 profile 层声明为“先走公司官方 IR 年报页”的市场/发行人。
- 该策略不写死 Infineon 或任一单家公司，只按任务行中的 `source_locator_urls` 发现候选 PDF，并按 fiscal year / report type 选择正式年报。
- 其他监管平台型 profile（DART、MOPS、EDINET、HKEX、CNINFO）仍保持未实现状态，避免把不同市场的搜索/下载口径混在一起。

## Work Completed

- 更新 `scripts/data_expansion/download_global_public_disclosures.py`：
  - 新增 `--execute`、`--timeout`、`--user-agent` 参数。
  - 实现 `company_ir_official_report_download`。
  - 支持官方 IR 页面、年报/报告页、HTML PDF 链接、AEM/product-document JSON 候选发现。
  - 写入 `locator_metadata.json`，包括 source URL、content type、byte count、sha256、候选数、选中候选和下载时间。
  - 对同一 `source_locator_urls` 增加候选缓存，同一家公司多年度任务只抓一次候选列表。
  - 收紧候选打分，降低 sustainability / remuneration / presentation / half-year / press 等附件或非正式年报的优先级。
  - 修复 `assetDamPath` 已经包含 PDF 文件名时重复拼接文件名导致 404 的问题。
- 更新 `tests/test_global_public_disclosure_download_tasks.py`：
  - 增加正式年报优先级测试。
  - 增加 AEM JSON PDF URL 拼接测试。
  - 增加同一 IR locator 多年度候选缓存测试。

## Result And Evidence

真实下载 smoke：

```powershell
python scripts\data_expansion\download_global_public_disclosures.py --profile eu_regulated_annual_report --ticker IFX.DE --execute --timeout 20 --queue-output data\manifests\tier2_global_public_disclosure_eu_ifx_profile_download_smoke_v0_1.jsonl --summary-output data\manifests\tier2_global_public_disclosure_eu_ifx_profile_download_smoke_summary_v0_1.json
```

结果：

- status：`pass`
- task count：`3`
- document downloaded：`3`
- downloaded bytes：`15,476,160`
- issues：`0`
- 选中 URL：
  - 2023：`https://www.infineon.com/assets/row/public/documents/corporate/investors/annual-reports/2023/2023-infineon-annual-report-v01-00-en.pdf`
  - 2024：`https://www.infineon.com/assets/row/public/documents/corporate/investors/annual-reports/2024/2024-infineon-annual-report-01-00-en.pdf`
  - 2025：`https://www.infineon.com/assets/row/public/documents/corporate/investors/annual-reports/2025/2025-annual-report-v01-00-en.pdf`

产物：

- `data/manifests/tier2_global_public_disclosure_eu_ifx_profile_download_smoke_v0_1.jsonl`
- `data/manifests/tier2_global_public_disclosure_eu_ifx_profile_download_smoke_summary_v0_1.json`
- 原始 PDF 和 metadata 写入 `data/raw_private/global_public_disclosures/eu_regulated/IFX_DE/...`，不进入 Git。

验证：

```powershell
python -m pytest tests\test_global_public_disclosure_download_tasks.py -q
python -m pytest tests\test_sp500_constituent_download.py tests\test_universe_tier_builder.py tests\test_supply_chain_supplement_manifest.py tests\test_global_public_disclosure_source_plan.py tests\test_global_public_disclosure_source_plan_audit.py tests\test_global_public_disclosure_download_tasks.py tests\test_entity_resolution_contract.py tests\test_relationship_edge_schema.py tests\test_relationship_edge_extractor.py -q
python -m compileall scripts\data_expansion src\sec_agent\entities src\sec_agent\relationships
git diff --check
```

结果：

- download task tests：`7 passed`
- layered data source targeted tests：`29 passed`
- compileall：pass
- `git diff --check`：pass

## Follow-Up

- 继续实现 profile-specific downloader：
  - `kr_dart_business_report`
  - `tw_mops_annual_report`
  - `jp_edinet_annual_securities_report`
  - `hkex_annual_report`
  - `szse_cninfo_annual_report`
- 每个 profile 都必须写入 source URL、checksum、metadata 和 source gap。
- 下载成功的非美年报仍只是 raw/staging 主披露原料；进入 evidence / chunk / BM25 / ObjectBM25 / BGE / Milvus 前必须先经过 parser、chunk S0、exact-value ledger 和 source-boundary gate。

## Safety Notes

- 本轮没有写入 API key、SSH 密码或私有 token。
- `--execute` 是显式参数；默认仍是 dry-run。
- 原始 PDF 位于 `data/raw_private`，按仓库规则不提交。
