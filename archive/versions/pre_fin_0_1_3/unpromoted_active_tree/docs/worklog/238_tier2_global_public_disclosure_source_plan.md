# 238 Tier2 Global Public Disclosure Source Plan

## Prompt

用户同意继续推进非美公开披露接入。上一轮已经确认 Samsung、SK hynix、Hon Hai / Foxconn、CATL 等非美上市公司不应作为 source gap，而应走全球公开主披露路径。

## Reasoning And Decision

- 不直接写一个通用下载器。KR DART、TW MOPS、JP EDINET、HKEX、CNINFO、公司 IR 的检索方式和许可边界不同，先做统一 source-plan，后续按 profile 分别实现下载和解析。
- source-plan 是后续下载、缓存、parser、chunk、relationship edge 候选抽取的合同输入。
- 默认只规划年度类报告；季度/中期报告通过 `--include-interim` 单独打开，避免一开始下载面失控。

## Work Completed

- 新增 profile 配置：
  - `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`
- 新增 source-plan 构建器：
  - `scripts/data_expansion/build_global_public_disclosure_source_plan.py`
- 新增测试：
  - `tests/test_global_public_disclosure_source_plan.py`
- 生成 source-plan 产物：
  - `data/manifests/tier2_global_public_disclosure_source_plan_v0_1.jsonl`
  - `data/manifests/tier2_global_public_disclosure_source_plan_summary_v0_1.json`
- 更新执行文档和 master checklist。

## Result And Evidence

构建命令：

```powershell
python scripts\data_expansion\build_global_public_disclosure_source_plan.py
```

结果：

- source-plan status：`pass`
- plan rows：`69`
- companies：`15`
- years：`2023`、`2024`、`2025`
- report type counts：
  - `annual_report=30`
  - `annual_securities_report=15`
  - `business_report=9`
  - `integrated_report=15`
- profile counts：
  - `kr_dart_business_report=18`
  - `tw_mops_annual_report=12`
  - `jp_edinet_annual_securities_report=30`
  - `hkex_annual_report=3`
  - `szse_cninfo_annual_report=3`
  - `eu_regulated_annual_report=3`

验证命令：

```powershell
python -m pytest tests\test_global_public_disclosure_source_plan.py tests\test_supply_chain_supplement_manifest.py -q
```

验证结果：`4 passed`。

## Follow-Up

- 下一步实现 profile-specific 下载器：
  - KR DART：公司代码 / report name 检索。
  - TW MOPS：公司代码 / 年度报告检索。
  - JP EDINET：证券代码 / document type 检索。
  - HKEX：issuer code / headline category 检索。
  - SZSE/CNINFO：证券代码 / 报告标题检索。
  - EU：公司 IR 官方年报下载，后续补 national OAM。
- 下载成功后，生成 raw metadata、checksum、source gap JSONL。
- Parser / chunk 阶段必须输出 `source_tier=primary_company_disclosure`，不能降级为 external lead。

## Safety Notes

- 没有下载或提交原始报告文件。
- 没有写入 API key、SSH 密码或私有 token。
- source-plan 只包含公开公司、官方入口 URL、计划缓存路径和解析 profile，不包含私有数据。
