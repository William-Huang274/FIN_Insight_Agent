# 265 非美供应链主披露下载与清洗

## Prompt

用户要求在下一阶段矩阵工程中补上此前未完成的非美供应链企业披露文件下载；不要只做规划，直接把公开可得数据下载并清洗，然后报告剩余缺口。

## Decision

本轮优先落地已经具备官方 API / 官方 IR 可达性的 profile：

- `kr_dart_business_report`：使用 OpenDART API，通过已通过 mapping gate 的 `dart_corp_code` 下载正式 `사업보고서` package。
- `eu_regulated_annual_report`：复用官方公司 IR 下载器，并为 PDF 增加 cleaned text staging。

MOPS、HKEX、CNINFO 暂不以公司 IR fallback 冒充交易所/监管路径；EDINET 仍缺 `EDINET_API_KEY`。所有下载结果仍为 staging，不能进入主线 vector / ledger / agent runtime，直到 table-aware parser、source-boundary gate 和 promotion policy 通过。

## Work Completed

- 更新 `scripts/data_expansion/download_global_public_disclosures.py`：
  - 新增 `.env` 加载，但 summary 只记录加载的变量名。
  - 实现 `kr_dart_business_report` OpenDART document package 下载。
  - 使用 DART filing list 选择 fiscal year 对应的 `사업보고서`，排除 quarterly / semiannual。
  - 下载官方 zip，记录 redacted `document.xml?crtfc_key=REDACTED` URL、sha256、byte count、rcept_no 和 report name。
  - 从 zip package 直接生成 cleaned text，默认不落盘重复 XML 解包文件，避免 D 盘空间耗尽。
  - 为公司 IR PDF/HTML 下载后增加 best-effort cleaned text staging。
- 更新 `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`：
  - DART profile 从 key-blocked 改为 `implemented_dart_openapi_document_download`。
  - parser 状态改为 cleaned-text staging 已实现、table parser pending。
- 新增 `scripts/data_expansion/build_non_us_supply_chain_disclosure_coverage_summary.py`。
- 新增 `tests/test_non_us_supply_chain_disclosure_coverage_summary.py`。
- 更新 `tests/test_global_public_disclosure_download_tasks.py`，覆盖 DART report selection、URL redaction、zip/text cleaning 和 pending profile fallback。

## Results

真实下载与清洗：

- DART / South Korea：
  - task rows：`18`
  - companies：`3` (`000660.KS`, `005930.KS`, `373220.KS`)
  - years：`2023`、`2024`、`2025`
  - downloaded / cleaned：`18/18`
  - unique documents：`9`
  - downloaded bytes：`11,210,578`
  - cleaned text chars：`12,569,042`
- EU / Infineon：
  - task rows：`3`
  - companies：`1` (`IFX.DE`)
  - years：`2023`、`2024`、`2025`
  - downloaded / cleaned：`3/3`
  - unique documents：`3`
  - downloaded bytes：`15,476,160`
  - cleaned text chars：`1,677,498`

覆盖汇总：

- source plan rows：`69`
- companies：`15`
- downloaded / cleaned rows：`21`
- downloaded companies：`4`
- unique downloaded documents：`12`
- cleaned text chars：`14,246,540`
- gap rows：`48`
- gap companies：`11`

剩余缺口：

- `jp_edinet_annual_securities_report`：`30` rows / `5` companies，缺 `EDINET_API_KEY` 与 key-backed smoke。
- `tw_mops_annual_report`：`12` rows / `4` companies，缺 MOPS profile-specific report lookup/downloader。
- `hkex_annual_report`：`3` rows / `1` company，缺 HKEXnews issuer report search/downloader。
- `szse_cninfo_annual_report`：`3` rows / `1` company，缺 CNINFO security report search/downloader。

Tracked manifests：

- `data/manifests/tier2_global_public_disclosure_kr_dart_download_clean_v0_1.jsonl`
- `data/manifests/tier2_global_public_disclosure_kr_dart_download_clean_summary_v0_1.json`
- `data/manifests/tier2_global_public_disclosure_eu_ifx_download_clean_v0_1.jsonl`
- `data/manifests/tier2_global_public_disclosure_eu_ifx_download_clean_summary_v0_1.json`
- `data/manifests/non_us_supply_chain_primary_disclosure_coverage_v0_1.jsonl`
- `data/manifests/non_us_supply_chain_primary_disclosure_coverage_summary_v0_1.json`

Private generated data:

- raw zip / PDF / metadata：`data/raw_private/global_public_disclosures/...`
- cleaned text / metadata：`data/processed_private/public_sources/global_public_disclosures/...`

## Validation

- `python -m pytest tests\test_non_us_supply_chain_disclosure_coverage_summary.py tests\test_global_public_disclosure_download_tasks.py -q` -> `17 passed`
- `python -m py_compile scripts\data_expansion\build_non_us_supply_chain_disclosure_coverage_summary.py scripts\data_expansion\download_global_public_disclosures.py` -> pass
- `python scripts\data_expansion\download_global_public_disclosures.py --profile kr_dart_business_report --execute --timeout 60 ...` -> pass, `18/18`
- `python scripts\data_expansion\download_global_public_disclosures.py --profile eu_regulated_annual_report --ticker IFX.DE --execute --timeout 40 ...` -> pass, `3/3`
- `python scripts\data_expansion\build_non_us_supply_chain_disclosure_coverage_summary.py` -> pass_with_gaps

## Follow-up

- Obtain/configure `EDINET_API_KEY`, then implement EDINET document search/download and XBRL/PDF route selection.
- Implement MOPS/HKEX/CNINFO profile-specific official downloaders with issuer-code mapping, report-type filters, stale-result guards, checksums, and source-gap rows.
- Add DART / PDF table-aware parser before promoting any non-US disclosure text into evidence/chunk/vector/ledger runtime.
- Deduplicate DART annual/business report aliases at promotion time, since current source plan intentionally keeps both English report-type aliases.

## Safety Notes

- No API key values are written to tracked manifests or metadata; DART URLs are redacted as `crtfc_key=REDACTED`.
- Raw and cleaned disclosure content stays under ignored private data directories.
- During the first DART run D: reached `0` free bytes; the failed partial DART staging from this turn was deleted and regenerated with zip-only raw storage.
