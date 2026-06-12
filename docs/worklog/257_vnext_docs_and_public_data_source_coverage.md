# 257 vNext 内部文档吸收与公开数据源覆盖审计

## Prompt

用户判断下一阶段应先做两件事：

1. 把外部 10 份规划文档吸收到当前项目，先落成内部文档。
2. 先开始数据源覆盖检查；当前不会支付商业 API 费用，因此先明确公开可得 API 能获得哪些数据，再考虑 Agent Graph 和 Skill 升级。

## Decision

本轮只做文档和覆盖审计，不修改 runtime、collector、parser、prompt 或 eval 脚本。

关键决策：

- 外部规划稿先进入 `docs/internal/`，不能直接写成当前公开能力。
- Agent Graph / Skill 升级暂缓；前置工作是 source coverage matrix 和 source registry。
- 商业 API、sell-side consensus、商业供应链/交易/海关明细等来源标为 `commercial_deferred`，不作为当前阶段主依赖。
- 公开来源按 `no_key`、`no_key_limited`、`free_key`、`open_bulk`、`official_web_no_key`、`official_portal_pending`、`endpoint_specific_pending`、`unofficial_provisional`、`commercial_deferred` 分类，避免把免费 key、无 key、官方网页、待验证门户和非官方接口混为一谈。

## Work Completed

- 新增内部规划入口：`docs/internal/README.md`。
- 新增 2026-06-10 vNext 内部目录：`docs/internal/vnext_20260610/README.md`。
- 记录外部 10 份源文件及 SHA256：`docs/internal/vnext_20260610/source_package_manifest.zh-CN.md`。
- 吸收 Skill / Playbook / Eval Gate 规划为内部合同：`docs/internal/vnext_20260610/skill_playbook_eval_contract.zh-CN.md`。
- 吸收 Agent Graph 更新方案为内部合同：`docs/internal/vnext_20260610/agent_graph_contract.zh-CN.md`。
- 新增公开/免费数据源覆盖审计：`docs/internal/vnext_20260610/public_data_source_coverage_audit.zh-CN.md`。
- 新增机器可读覆盖 registry 草案：`configs/data_sources/public_source_coverage_v0_1.yaml`，记录 source id、auth status、source family、claim boundary、collector/parser 状态和 gap type。
- 后续 2026-06-11 在此基础上新增 P0-P3 数据接入脚本与产物，详见 `258_public_source_p0_p3_ingestion_scaffold.md`。
- 更新 `docs/README.md`、`docs/architecture/README.md`、`docs/worklog/README.md` 和 `docs/worklog/00_internal_master_checklist.md`。

## Coverage Result

第一版覆盖审计结论：

- SEC EDGAR、CompanyFacts、Submissions、SEC bulk datasets 继续是美国公开公司主披露和结构化事实核心。
- 非美官方披露可做，但需要 profile-specific downloader/parser：DART、EDINET 走免费官方 key；MOPS、HKEXnews、CNINFO 需要逐站点验证查询参数和下载边界。
- FRED、BLS、BEA、Census、EIA、FDIC、USITC/DataWeb 等适合宏观/行业上下文，不支持直接公司级财务事实。
- ClinicalTrials.gov、openFDA、CMS、PatentsView、OpenAlex、GLEIF、OpenFIGI 可以作为 Product/Technology、Healthcare、Investment/Ownership 和 entity resolution 的公开数据基础。
- 用户提醒后补充产品/销量覆盖边界：公司披露的 product revenue、unit sales、deliveries、shipments、subscribers、ARPU、backlog、orders 等可以作为公司级经营指标；公司产品页、NHTSA、ClinicalTrials.gov、openFDA、CMS、EIA、PatentsView、OpenAlex 多数只能支持产品状态、监管状态、技术信号或使用量上下文，不能自动推导销量或收入。
- Yahoo chart 仍只能作为 `unofficial_provisional` market snapshot，不能提升为官方估值事实。
- 无可靠免费 consensus；相关问题必须输出 `source_gap` 或 `commercial_deferred`。

## Evidence

本轮核对了现有仓库配置和外部官方文档：

- `configs/data_sources/source_families.yaml`
- `configs/industry_data_api_contracts_v0_2.yaml`
- `configs/data_sources/global_public_disclosure_profiles_v0_1.yaml`
- SEC EDGAR APIs、FRED、BLS、BEA、Census、EIA、FDIC、ClinicalTrials.gov、openFDA、PatentsView、OpenFIGI、GLEIF、OpenAlex、GDELT、Common Crawl、DART、EDINET 等官方公开说明。

## Validation

- 本轮是文档和规划吸收，没有运行模型、下载数据或跑 full-chain eval。
- 需要在最终收口前运行文档级检查：`git diff --check`、目标文件列表检查和关键链接/标题检查。

## Follow-up

- 用 `configs/data_sources/public_source_coverage_v0_1.yaml` 驱动下一轮 collector source-plan，而不是直接扩 prompt。
- 为产品/销量研究补 `company_product_operating_metric` ontology 和 `official_product_status` / `public_product_usage_context` source-boundary gate。
- 为 Coverage & Gap Auditor 增加 `auth_gap`、`parser_gap`、`source_unavailable`、`commercial_deferred` 等缺口类型。
- 先实现 no-key/free-key collector 的最小可审计路径，再回到 Graph/Skill prompt 升级。
- 所有 key 只放环境变量或本地私有配置，不进入仓库。
