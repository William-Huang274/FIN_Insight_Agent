# 266 公开源 S5-S0 物化与非美披露缺口收口

## Prompt

用户提供 EDINET API key，要求写入本地 `.env`，继续补全剩余公开源缺口，并把 S5-S0 信息强度矩阵的数据落实；D 盘空间不足时改用 Z 盘。

## Decision

本轮把“能下载/清洗的官方或公司一手文件”先落地为 staging，但不越级进入 agent runtime：

- EDINET key 已配置到本地 ignored `.env`，但 EDINET v2 official API smoke 返回 `401`，判定为 key 无效、未激活或订阅状态不对；不能把 EDINET 官方源标成已完成。
- TW MOPS、HKEX、CNINFO 使用各自官方门户/API 路径下载年度报告。
- JP EDINET 官方源仍 blocked；只把 Advantest / Tokyo Electron 可验证的公司 IR 年报或 integrated report 作为 `company_ir_reports` fallback 下载，不能冒充 `jp_edinet_api`。
- 所有新增 raw / processed 下载都落到 `Z:\FIN_Insight_Agent_data\...`，避免继续挤占 D 盘。
- S5-S0 矩阵从“信息强度评级”推进到“物化状态矩阵”：每个公开源必须说明是否已有 cleaned text、resolver/inventory、structured facts、parser gate 或 blocked gap。

## Work Completed

- 本地 `.env` 写入 `EDINET_API_KEY`，并确认 `.env` 被 Git ignore；日志和 manifest 只记录变量名，不记录 key 值。
- 更新 `scripts/data_expansion/download_global_public_disclosures.py`：
  - 支持 `--cache-root` / `--processed-root`，可把 raw / processed disclosure staging 重定向到 Z 盘。
  - 收紧公司 IR 年报候选选择：排除 1H、interim、correction、section/chapter、overview 等误选；支持中文年报词、民国年、integrated report / annual securities report 匹配。
- 更新 `scripts/data_expansion/download_non_us_portal_public_disclosures.py`：
  - 增加 TW MOPS 年报 portal 下载。
  - 增加 HKEXnews issuer report search 下载。
  - 增加 CNINFO annual report query 下载。
  - 统一输出 cleaned text / metadata / manifest summary。
- 更新 `scripts/data_expansion/build_non_us_supply_chain_disclosure_coverage_summary.py`：
  - 纳入 DART、EU/company IR、MOPS、HKEX/CNINFO、JP company IR fallback manifests。
  - 把 EDINET 剩余缺口明确标为 `edinet_api_key_invalid_or_key_backed_smoke_failed`。
- 新增 `scripts/data_expansion/build_public_source_strength_materialization_report.py`：
  - 读取 S5-S0 信息强度配置、公开源 inventory adapter、SEC structured facts、SEC annual staging、非美 disclosure manifests。
  - 输出逐 source 的 materialization matrix、summary 和内部报告。
- 新增/更新 tests：
  - `tests/test_non_us_portal_public_disclosures.py`
  - `tests/test_global_public_disclosure_download_tasks.py`
  - `tests/test_non_us_supply_chain_disclosure_coverage_summary.py`
  - `tests/test_public_source_strength_materialization_report.py`
- 更新 `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`，把 DART/MOPS/HKEX/CNINFO/company IR fallback 的 downloader 状态与 parser pending 边界写回 profile。

## Results

非美供应链主披露 staging：

- source plan rows：`69`
- companies：`15`
- downloaded / cleaned rows：`47`
- downloaded companies：`12`
- unique downloaded documents：`38`
- downloaded bytes：`286,341,064`
- cleaned text chars：`24,114,298`
- gap rows：`22`
- gap companies：`5`

Profile 覆盖：

- KR DART：`18/18` rows downloaded/cleaned，覆盖 `000660.KS`、`005930.KS`、`373220.KS`。
- EU/company IR：`3/3` rows downloaded/cleaned，覆盖 `IFX.DE`。
- TW MOPS：`12/12` rows downloaded/cleaned，覆盖 `2308.TW`、`2317.TW`、`2382.TW`、`3231.TW`。
- HKEX：`3/3` rows downloaded/cleaned，覆盖 `1211.HK`。
- CNINFO：`3/3` rows downloaded/cleaned，覆盖 `300750.SZ`。
- JP company IR fallback：`8/30` rows downloaded/cleaned，覆盖 `6857.T`、`8035.T` 的部分 annual securities / integrated report；其余 `22` rows 保持 gap。
- JP EDINET official：官方 `jp_edinet_api` 仍 `30/30` rows blocked，因为 key-backed smoke 失败，fallback 不计入官方源完成度。

S5-S0 materialization：

- source count：`32`
- materialized source count：`9`
- materialized sources：`census_data_api`、`cninfo_portal`、`company_ir_reports`、`gleif_api`、`hkexnews_portal`、`kr_dart_openapi`、`openfigi_api`、`sec_edgar_apis`、`tw_mops_portal`
- inventory/runtime rows：`515`
- SEC CompanyFacts rows：`2,790,261`
- Tier2 SEC annual chunks：`30,600`
- Tier2 SEC annual ledger facts：`392,015`
- non-US disclosure downloaded rows：`47`
- non-US cleaned text chars：`24,114,298`
- EDINET official gap rows：`30`

Durable outputs：

- `data/manifests/non_us_supply_chain_primary_disclosure_coverage_v0_1.jsonl`
- `data/manifests/non_us_supply_chain_primary_disclosure_coverage_summary_v0_1.json`
- `data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl`
- `data/manifests/public_source_strength_materialization_summary_v0_1.json`
- `docs/internal/vnext_20260610/public_source_strength_materialization.zh-CN.md`

Private generated data：

- raw disclosure downloads：`Z:\FIN_Insight_Agent_data\raw_private\global_public_disclosures\...`
- cleaned text / metadata：`Z:\FIN_Insight_Agent_data\processed_private\public_sources\global_public_disclosures\...`

## Validation

- `python -m pytest tests\test_non_us_portal_public_disclosures.py tests\test_global_public_disclosure_download_tasks.py tests\test_non_us_supply_chain_disclosure_coverage_summary.py tests\test_public_source_strength_materialization_report.py` -> pass
- `python -m py_compile scripts\data_expansion\download_non_us_portal_public_disclosures.py scripts\data_expansion\download_global_public_disclosures.py scripts\data_expansion\build_non_us_supply_chain_disclosure_coverage_summary.py scripts\data_expansion\build_public_source_strength_materialization_report.py` -> pass
- EDINET official smoke -> `401` invalid/inactive subscription key; official source remains blocked.

## Follow-up

- Obtain or activate a valid EDINET API key, then rerun JP EDINET official document search/download and XBRL/PDF route selection.
- Build table-aware parsers for DART/MOPS/HKEX/CNINFO/company IR PDFs before promotion into evidence/chunk/vector/ledger runtime.
- Promote only source-specific, parser-verified facts: regulator filings and exchange annual reports can support disclosed company facts; company IR fallback can support company-authored context but not official regulator filing claims.
- Wire `public_source_strength_materialization_matrix_v0_1.jsonl` into the next Agent Graph / Skill planning pass, so agents see source availability, strength tier, claim boundary, and parser gate instead of raw source names.

## Safety Notes

- No secret value is written to tracked files, manifests, metadata, or worklogs.
- `.env` stays local and ignored.
- JP company IR fallback rows are deliberately kept separate from `jp_edinet_api` official gaps to avoid overstating official-source coverage.
