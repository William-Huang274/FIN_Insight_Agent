# 239 Global Public Disclosure Profile Rules And Download Queue

## Prompt

用户同意继续下一步，并提醒：除美国外的证券市场披露合同不要按单家公司写死口径。同一地区或交易所披露规则通常相近，合同要能支持后续新增公司。

## Reasoning And Decision

- 上一版 Tier2 非美公司行仍带 `target_reports`，虽然 source-plan 会合并 profile 默认值，但这会诱导后续新增公司时复制公司级报告口径。
- 本轮把报告类型规则迁回 `global_public_disclosure_profiles`，公司行只保留 issuer identity、listing、source locator 和可选 override。
- 新增 audit，阻止公司级 `target_reports` 回流。
- 新增 profile-aware dry-run download task queue。它只做 profile 分发和 locator metadata 准备，不下载报告文件，不宣称 evidence 已可用。

## Work Completed

- 更新 profile 合同：
  - `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`
  - 增加 `contract_policy`
  - 使用 `jurisdiction_scope`、`listing_exchange_scope`、`rule_scope=market_disclosure_system`
- 更新 Tier2 配置：
  - 移除 `global_public_disclosure_companies` 公司级 `target_reports`
- 更新 source-plan builder：
  - 报告类型来自 disclosure profile
  - 支持 `report_type_include_overrides` / `report_type_exclude_overrides`
  - override 必须有 reason
  - 遇到 deprecated `target_reports` 直接报错
- 新增 source-plan audit：
  - `scripts/data_expansion/audit_global_public_disclosure_source_plan.py`
- 新增 profile-aware dry-run 下载任务队列：
  - `scripts/data_expansion/download_global_public_disclosures.py`
- 新增测试：
  - `tests/test_global_public_disclosure_source_plan_audit.py`
  - `tests/test_global_public_disclosure_download_tasks.py`

## Result And Evidence

重建 Tier2 manifest：

- Tier2：`98` 家。
- Tier2 SEC-download eligible：`83` 家。
- Tier2 global-public disclosure：`15` 家。
- `target_report_counts={}`，说明公司行不再携带默认报告组合。

重建 source-plan：

- plan rows：`69`
- companies：`15`
- `report_type_rule_source_counts={"disclosure_profile": 69}`
- source-plan audit：`pass`

dry-run 下载任务：

- task count：`69`
- profile strategies：`6`
- document downloaded：`0`
- strategy counts：
  - `official_locator_then_disclosure_search=18`
  - `mops_company_report_lookup=12`
  - `edinet_document_search=30`
  - `hkexnews_issuer_report_search=3`
  - `cninfo_security_report_search=3`
  - `company_ir_official_report_download=3`

验证命令：

```powershell
python scripts\data_expansion\build_supply_chain_supplement_manifest.py
python scripts\data_expansion\build_global_public_disclosure_source_plan.py
python scripts\data_expansion\audit_global_public_disclosure_source_plan.py --expected-count 69 --summary-output data\manifests\tier2_global_public_disclosure_source_plan_audit_v0_1.json
python scripts\data_expansion\download_global_public_disclosures.py
python -m pytest tests\test_supply_chain_supplement_manifest.py tests\test_global_public_disclosure_source_plan.py tests\test_global_public_disclosure_source_plan_audit.py tests\test_global_public_disclosure_download_tasks.py -q
```

验证结果：`11 passed`。

## Follow-Up

- 继续实现真正的 profile-specific document fetch：
  - DART / MOPS / EDINET / HKEX / CNINFO / EU IR。
- 每个 profile 的实际下载器必须写 metadata、checksum、source URL、download status 和 source gap。
- 下载器完成前，download task queue 只能作为 locator / planning artifact，不得进入 evidence 或 vector index。

## Safety Notes

- 本轮没有下载原始报告文件。
- 没有写入 API key、SSH 密码或私有 token。
- `download_global_public_disclosures.py` 默认 dry-run；`--materialize-locators` 也只写 locator metadata，不写报告正文。
