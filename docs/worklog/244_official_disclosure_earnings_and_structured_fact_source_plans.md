# 244 Official Disclosure Earnings And Structured Fact Source Plans

## Prompt

用户纠正数据源扩容边界：美股官方披露 `10-K / 10-Q / 8-K`、市场和行业数据此前在 full238 / RAG 审计中已经跑通，可以复用并直接接入；需要重新开始做的是非美官方披露、公司业绩材料和结构化财务事实。

## Decision

- 不重建美股 SEC 表单、市场快照和行业快照的新合同。
- 美股 SEC `8-K Item 2.02 / EX-99.1` earnings release 继续复用既有 SEC 8-K earnings 管线。
- 非美公司 IR earnings release / investor presentation、新的 SEC CompanyFacts/Submissions、非美官方报告财务表格事实进入新的 source plan。
- 新 plan 只生成 staging 合同，不下载大文件、不覆盖主线索引。

## Work Completed

- 更新 source family：
  - `company_earnings_release`
  - `sec_companyfacts_structured_fact`
  - `sec_submissions_metadata`
  - `global_public_structured_financial_fact`
- 更新 EvidenceObject source contract，允许：
  - `earnings_release`
  - `investor_presentation`
  - `financial_fact`
  - `company_authored_earnings_material`
  - `company_authored_presentation`
  - `company_reported_structured_fact`
- 新增业绩材料配置：
  - `configs/data_sources/company_earnings_material_profiles_v0_1.yaml`
- 新增结构化财务事实配置：
  - `configs/data_sources/structured_financial_fact_sources_v0_1.yaml`
- 新增 source-plan builder：
  - `scripts/data_expansion/build_company_earnings_material_source_plan.py`
  - `scripts/data_expansion/build_structured_financial_fact_source_plan.py`
- 将新 source plan 挂入 staging registry：
  - `configs/data_sources/layered_staging_datasets_v0_1.yaml`
- 更新执行文档：
  - `docs/architecture/layered_data_source_expansion_plan.zh-CN.md`
  - `docs/architecture/layered_data_source_expansion_execution_plan.zh-CN.md`

## Results

公司业绩材料 source plan：

- 输出：`data/manifests/company_earnings_material_source_plan_v0_1.jsonl`
- Summary：`data/manifests/company_earnings_material_source_plan_summary_v0_1.json`
- 状态：`pass`
- 计划行：`888`
- 公司：`603`
- 复用 SEC 8-K earnings 管线：`588`
- 非美 company IR material locator：`300`
- source family：`sec_8k_earnings_release=588`、`company_earnings_release=150`、`company_presentation=150`

结构化财务事实 source plan：

- 输出：`data/manifests/structured_financial_fact_source_plan_v0_1.jsonl`
- Summary：`data/manifests/structured_financial_fact_source_plan_summary_v0_1.json`
- 状态：`pass`
- 计划行：`1221`
- 公司：`603`
- SEC API 下载计划：`1176`
- 非美官方报告财务表格派生计划：`45`
- exact-value ledger candidates：`633`

## Gates

- `python -m pytest tests\test_company_earnings_material_source_plan.py tests\test_structured_financial_fact_source_plan.py tests\test_evidence_schema_global_public.py -q`：`10 passed`
- `python -m compileall scripts\data_expansion\build_company_earnings_material_source_plan.py scripts\data_expansion\build_structured_financial_fact_source_plan.py src\evidence\schema.py`：pass

## Remaining Gaps

- 非美官方披露 DART / MOPS / EDINET / HKEX / CNINFO profile-specific downloader 仍未完成。
- 非美 company IR earnings material 目前是 locator plan，尚未实现下载、解析、chunk 和 evidence 构建。
- SEC CompanyFacts/Submissions 目前是 API 下载计划，尚未 materialize 成 raw JSON 或 normalized financial fact rows。
- 非美结构化事实依赖官方报告 parser、checksum 和 table-boundary audit，通过前不得进入 exact-value ledger。

## Safety Notes

- 未写入 API key、SSH 密码、私有 token 或云端凭据。
- 新生成 manifest 是 source contract；raw documents、financial fact stores、ledger 和 vector index 仍应作为 private/generated artifacts 管理。
