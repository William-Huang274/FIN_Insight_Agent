# 18 Exact-Slot Data Layer Completion Plan

日期：2026-06-18

## 目标修正

本阶段目标不是让每个公司都有一批 `context_only` 行，也不是让 source coverage gate 粗略 pass。

本阶段目标是：在接入 runtime / full-chain agent 前，先把 603 公司数据层补到可审计的 exact-slot 口径：

1. 每个公司按 lane / product family / source role 建立应有 slot。
2. 每个 slot 必须有 source-specific parser 输出的结构化字段。
3. 每个 slot 必须带 issuer / product / counterparty / period / unit / value / date / URL / citation 等该 source role 所需字段。
4. 每个 slot 必须声明 `allowed_claims` 和 `forbidden_claims`。
5. 只有 source role 自身可证明的事实可以提权；proxy 只能提权为 proxy exact，不得提权为收入、销量、份额、ASP、库存、sell-through 或商业 tracker 结论。
6. 真正 data gap 只能在公开、免费、可得路径全部尝试并审计后暴露，包括普通 HTTP、Playwright/browser rendering、sitemap、official docs/PDF/catalog、public API、local exchange/regulator/company IR、trusted external sources。

## R1-R5 前审计基线

以下是 R1-R5 开始前的 source-coverage / product-route 审计基线，保留用于解释为什么需要 exact-slot gate；当前执行结果以下方 `2026-06-18 R1-R5 执行 closeout` 为准。

- `company_public_source_coverage_matrix_v0_1`：
  - company_count: `603`
  - requirement_count: `4,418`
  - pass_requirement_count: `587`
  - repair_queue_count: `3,831`
  - public_interface_ready_company_count: `1`
  - partial_public_interface_company_count: `363`
  - public_interface_gap_company_count: `239`
- `family_source_route_plan_v0_1`：
  - route_plan_count: `2,917`
  - runtime_family_row_available: `411`
  - runtime_company_row_available: `419`
  - seed_available_not_materialized: `1,059`
  - not_materialized: `1,028`
  - open routes: `2,087`
- `company_product_slots_v0_1`：
  - product_slot_count: `6,454`
  - family-bound runtime slots: `6,454`
  - official_surface_slot: `4,432`
  - filings_taxonomy_slot: `1,899`
  - product_kpi_exact_slot: `114`
  - bounded_context_slot: `9`
- `company_reported_product_operating_metric_runtime_rows_v0_1`：
  - runtime rows: `5,976`
  - runtime tickers: `186`
  - product KPI exact company coverage in product slots: `77` companies
  - no product KPI exact slot: `526` companies

结论：产品槽位和关系图谱基础已经跑通，但 company-level / source-role exact-slot 覆盖仍远未完成。当前不能把 `context_only` row 当成数据层完成。

## R1-R5 前 repair queue 基线

以下 repair queue 是 R1-R5 之前的 company/source-role 队列，已被本轮 exact-slot coverage matrix 和 closeout ledger 重算；保留用于对照。

| requirement_id | open count | seed available | priority | 主要含义 |
| --- | ---: | ---: | --- | --- |
| `trusted_external_context` | 567 | 0 | medium/low | 主流财经媒体、行业协会、官方社媒/博客等可信外部验证源缺少公司级结构化 slot。 |
| `macro_official_context` | 566 | 500 | medium/low | FRED/BLS/BEA/Census/EIA 等 driver 有 seed，但还没按公司/行业/family 全量 materialize 成 driver/exposure exact slots。 |
| `hiring_capacity_proxy` | 515 | 0 | low | 公开 ATS/job board 缺 company/product/family 级岗位 exact proxy slot。 |
| `public_order_proxy` | 421 | 0 | medium | USAspending、SAM.gov、EU TED、local tender/public award 等订单/采购 proxy 缺 company/counterparty/product exact slot。 |
| `primary_company_disclosure` | 417 | 417 | high | SEC/FSD/company IR/local exchange filings 还没补成公司级披露 exact slots，尤其非美和产品经营指标。 |
| `supply_chain_official_relationship` | 266 | 0 | medium | 官方客户/供应商/伙伴/订单新闻缺 relationship exact slot。 |
| `energy_utility_context` | 211 | 210 | medium/low | EIA/FERC/state utility/regulator/asset route 需要公司/资产/driver exact slot。 |
| `platform_review_proxy` | 179 | 0 | low | G2/Capterra/StackShare/major platform review/ranking exact proxy slot 缺失。 |
| `channel_offer_proxy` | 142 | 0 | low/medium | CDW/Amazon/JD/Apple/major distributor/channel offer SKU/price/spec exact proxy slot 缺失。 |
| `developer_ecosystem_proxy` | 132 | 0 | low/medium | GitHub/npm/PyPI/HuggingFace package/repo/model exact proxy slot 缺失。 |
| `technology_research_proxy` | 103 | 99 | medium/low | OpenAlex/PatentsView seed 有，但需要 issuer/product/topic resolver 和 exact proxy slot。 |
| `app_rank_store_proxy` | 98 | 0 | low | App Store/Google Play/app marketplace exact proxy slot 缺失。 |
| `financial_regulatory_context` | 73 | 73 | medium | FDIC/FRED/bank regulatory entity mapping和 institution-to-issuer exact slot 未补齐。 |
| `regulated_product_context` | 66 | 66 | medium | ClinicalTrials/openFDA/CMS sponsor/product/condition exact slot 未补齐。 |
| `official_product_surface` | 59 | 59 | high | 仍有少量 official product/source parser slot 未补齐或未绑定。 |
| `auto_product_identity_context` | 16 | 11 | medium | NHTSA vPIC make/model/year/issuer exact slot 未补齐。 |

按 lane：

- V7 Energy / Utilities / Industrials: `1,424` open requirements
- V3 Software / Cloud / Developer Products: `715`
- V8 Retail / CPG / Restaurants / Travel: `459`
- V4 Pharma / Biotech / Medtech: `444`
- V1 Semiconductors / AI Infrastructure: `346`
- V6 Banks / Financials: `271`
- V5 Auto / Mobility: `118`
- V2 Consumer Hardware: `54`

## Exact-Slot 定义

`exact slot` 不是所有数据都能证明公司财务结论，而是每个 source role 对自己能证明的事实有精确字段。

### L1 Company Disclosure Exact Slot

来源：

- SEC / FSD / XBRL / 10-K / 10-Q / 20-F / 6-K / annual report / company IR / local exchange filing。

必须字段：

- `ticker`
- `issuer_name`
- `source_document_id`
- `filing_type`
- `filing_date`
- `period`
- `statement_or_section`
- `metric_name`
- `value`
- `unit`
- `currency_or_scale`
- `product_or_segment`
- `citation_span`
- `source_url`
- `parser_status=value_unit_period_product_citation_parser_pass`

可支持：

- 公司披露的收入、成本、三表科目、产品/segment KPI、产量、交付量、backlog、subscribers、AUM、capacity 等。

禁止：

- 未披露产品收入、市场份额、真实销量、渠道库存、sell-through。

### Official Product / Spec Exact Slot

来源：

- 公司官网产品页、docs、catalog、datasheet、IR product deck、official ecommerce/product page。

必须字段：

- `ticker`
- `issuer_name`
- `product_family`
- `product_name`
- `model_or_sku_or_indication`
- `spec_name`
- `spec_value`
- `unit`
- `availability_or_launch_status`
- `source_url`
- `snapshot_at`
- `issuer_binding_status`
- `product_binding_status`
- `parser_status=source_specific_product_spec_parser_pass`

可支持：

- 产品存在、型号、规格、定位、官方可售/发布状态、产品族对比。

禁止：

- 产品销售、ASP、市场份额、库存、sell-through。

### Macro / Official Driver Exact Slot

来源：

- FRED/BLS/BEA/Census/EIA/FERC/state regulator 等。

必须字段：

- `series_id`
- `driver_name`
- `geography`
- `industry_or_asset_scope`
- `period`
- `value`
- `unit`
- `source_url`
- `issuer_exposure_basis`
- `ticker`
- `product_family`

可支持：

- 行业周期、利率、能源价格、发电/需求、消费/贸易、宏观 exposure。

禁止：

- 单公司收入、利润、销量或份额推断。

### Supply Chain / Order Exact Slot

来源：

- 公司官方客户/供应商/伙伴新闻、public tender/contract/award、政府采购、公开招投标。

必须字段：

- `ticker`
- `issuer_role`
- `counterparty_name`
- `counterparty_role`
- `relationship_type`
- `product_or_service`
- `event_or_award_id`
- `event_date`
- `amount`
- `currency`
- `jurisdiction_or_buyer`
- `source_url`
- `issuer_binding_status`
- `counterparty_binding_status`

可支持：

- 单项关系、公开 award/order/tender/partner 存在，若金额公开可支持该单项金额。

禁止：

- 公司总订单、backlog、出货、allocations、客户集中度。

### Developer Ecosystem Exact Proxy Slot

来源：

- GitHub/npm/PyPI/HuggingFace/marketplace 官方公开 API。

必须字段：

- `ticker`
- `product_or_project`
- `artifact_type`
- `artifact_id`
- `artifact_url`
- `metric_name`
- `value`
- `unit`
- `snapshot_at`
- `issuer_binding_status`
- `product_binding_status`

可支持：

- repo/package/model 活跃度、版本、stars/downloads/forks/last update 等 proxy。

禁止：

- 收入、客户采用、护城河或产品成功结论。

### Channel Offer Exact Proxy Slot

来源：

- 大型电商/分销商/公开报价站，如 Amazon/JD/Tmall/CDW/Digi-Key/Mouser/Arrow/official store。

必须字段：

- `ticker`
- `brand`
- `product_name`
- `sku_or_mpn`
- `retailer_or_distributor`
- `price`
- `currency`
- `availability`
- `specs`
- `snapshot_at`
- `source_url`
- `issuer_binding_status`
- `product_binding_status`

可支持：

- SKU、配置、报价、可售/缺货状态、公开渠道存在。

禁止：

- ASP、sell-through、渠道库存、市场份额。

### App / Review / Platform Exact Proxy Slot

来源：

- Apple App Store、Google Play、G2、Capterra、StackShare、major platform rankings。

必须字段：

- `ticker`
- `app_or_product_id`
- `platform`
- `rating`
- `review_count`
- `rank_or_category`
- `version`
- `release_or_update_date`
- `source_url`
- `snapshot_at`
- `issuer_binding_status`
- `product_binding_status`

可支持：

- app/listing/rating/review/rank/version proxy。

禁止：

- 下载量、收入、市场份额，除非平台官方直接披露。

### Hiring / Capacity Exact Proxy Slot

来源：

- company career page、Greenhouse、Lever、Workday、Ashby、SmartRecruiters 等公开 ATS。

必须字段：

- `ticker`
- `job_id`
- `job_title`
- `department`
- `location`
- `posted_at`
- `product_or_function_tags`
- `source_url`
- `snapshot_at`
- `issuer_binding_status`
- `product_binding_status`

可支持：

- 岗位/地理/职能/产品方向招聘 proxy。

禁止：

- 需求、收入、产能、订单或 headcount 结论。

### Regulated Product / Auto / Financial / Energy Exact Slot

来源：

- ClinicalTrials/openFDA/CMS/NHTSA/FDIC/EIA/FERC/state regulator。

必须字段按 source-specific API 定义：

- healthcare: `sponsor`, `product`, `condition`, `trial_id/application_id/procedure_code`, `phase/status/date`
- auto: `manufacturer`, `make`, `model`, `model_year`, `vehicle_type`
- financial: `institution_id`, `metric`, `period`, `value`, `unit`, `issuer_entity_map`
- energy: `plant/utility/asset`, `series_or_asset_id`, `period`, `value`, `unit`, `issuer_entity_map`

可支持：

- 监管/产品身份/官方指标 exact context。

禁止：

- 商业成功、销售、份额或盈利能力。

## Repair 顺序

### R1: Exact-Slot Gate 先行

先新增 `ExactSlotContractRegistry` 和 `CompanyExactSlotCoverageMatrix`，不能继续只用 context coverage。

通过条件：

- 每个 requirement 有 schema、required fields、allowed/forbidden claims。
- 当前 manifests 能被审计成：
  - `exact_slot_ready`
  - `context_only_not_exact`
  - `parser_gap`
  - `resolver_gap`
  - `source_gap`
  - `commercial_or_company_undisclosed_gap`
- 任何 `context_only_not_exact` 不能进入 exact slot。

### R2: High Priority L1 + Official Surface

先补：

- `primary_company_disclosure=417`
- `official_product_surface=59`

原因：

- 这是后续产品 KPI、财务分析、融资图谱最重要的底座。

通过条件：

- US issuer 优先走 SEC/FSD/XBRL/filing parser。
- non-US issuer 走 company IR/local exchange/regulator/annual report。
- official product pages 必须解析到 product/spec exact slot，不只是 URL/context。
- 找不到时必须有 issuer-level repair ledger，列明尝试的 official / regulator / exchange / IR / browser route。

### R3: Seed-Available Public Official API

补：

- `macro_official_context=566`（seed available 500）
- `energy_utility_context=211`（seed available 210）
- `financial_regulatory_context=73`
- `regulated_product_context=66`
- `technology_research_proxy=103`（seed available 99）
- `auto_product_identity_context=16`

通过条件：

- 每个 API 输出 source-specific exact slot。
- 必须有 issuer/product/asset/entity resolver。
- 只支持对应官方/proxy claim，不支持公司财务推断。

### R4: Seed-Missing But Crawlable L2/L3

补：

- `trusted_external_context=567`
- `supply_chain_official_relationship=266`
- `public_order_proxy=421`
- `hiring_capacity_proxy=515`
- `channel_offer_proxy=142`
- `developer_ecosystem_proxy=132`
- `app_rank_store_proxy=98`
- `platform_review_proxy=179`

策略：

- 建 source locator，不靠泛搜一把抓。
- 每个 source role 配 whitelist / domain policy / platform adapter。
- Playwright/browser rendering 允许用于公开页面。
- 每条抓取结果必须进 exact proxy slot；否则为 parser/resolver/source gap。

通过条件：

- 每家公司/产品族有对应 source route 的 locator attempt ledger。
- 成功 row 必须 source-specific parser pass。
- 不允许把网页正文摘要作为 exact slot。

### R5: Product KPI Exact Slot

当前问题：

- `526` 家公司没有 product KPI exact slot。
- 已有 `5,976` product operating metric rows 覆盖 `186` tickers，但只有 `77` 家公司在 product slots 里达到 exact KPI slot。

策略：

- 回到公司披露文件和 IR 表格，按 industry/family 做 KPI parser。
- 对没有披露产品级 KPI 的公司，暴露 `company_undisclosed_product_kpi_gap` 或 `commercial_tracker_gap`。
- 不允许用官网产品页、新闻、招聘、渠道、宏观 proxy 填 product KPI exact。

通过条件：

- 每个 company-product-family 都有：
  - exact product KPI slot；或
  - audited company-undisclosed/commercial gap。
- gap 必须有尝试 ledger。

## 不能做的事

- 不把 `official_surface_slot` 当成产品表现 exact KPI。
- 不把 `context_only=true` row 当成 exact slot。
- 不把新闻/招聘/渠道/宏观/研究 proxy 写成收入、销量、份额、ASP、库存或 sell-through。
- 不以 lane-level pass 替代 company-level pass。
- 不以 company-level source row 替代 product-family exact slot。
- 不把 seed 缺失直接写 final gap；必须先 locator / crawler / browser / API / IR / regulator route。

## 与 Runtime 的关系

runtime 接入必须等数据层通过以下 gate：

1. `CompanyExactSlotCoverageMatrix` 生成并能解释每个缺口。
2. `ProductKPIExactSlotCoverage` 明确每个 company-product-family 的 exact/gap 状态。
3. `SourceRoleExactSlotCoverage` 明确每个 L2/L3 route 的 exact proxy/gap 状态。
4. `Research Lead` 只能读取 exact-slot matrix 和 audited gaps；不能直接把 `context_only` row 当证据。

## 当前判断

### 2026-06-18 R1-R5 执行 closeout

本轮已把 R1-R5 从“规划”推进到可审计数据层产物：

- R1 gate 已落地：
  - `src/sec_agent/exact_slot_contracts.py` 定义 L1/L2/L3 source-role exact-slot contract；
  - `scripts/data_expansion/build_exact_slot_coverage_matrix.py` 生成 `CompanyExactSlotCoverageMatrix` / `SourceRoleExactSlotCoverage` / rejected attempts；
  - `exact_slot_gap_ledger_v0_1.jsonl` 记录每个未 ready requirement 的 gap class、source gate status 和 repair seed。
- R2 L1 + official surface 已补强：
  - `sec_financial_statement_metric_runtime_rows_v0_1.jsonl` 从 SEC CompanyFacts / FSD 投影 `6,606` 条 parser-verified 三表/财务科目 exact rows，覆盖 `587/603` 公司；
  - `official_product_surface` exact ready `310/310` applicable requirements，产品页/官方 surface 仍只支持产品存在、规格、定位、URL catalog，不支持销售、份额、ASP、库存、sell-through 或未披露产品 KPI。
- R3 官方/API exact/proxy rows 已接入：
  - `macro_official_context` exact ready `603/603`；
  - `energy_utility_context` `216/216`；
  - `financial_regulatory_context` `77/77`；
  - `technology_research_proxy` `111/111`。
- R4 crawlable L2/L3 已真实跑过并进入 exact/gap ledger：
  - `trusted_external_context` `603/603`；
  - `public_order_proxy` `299/438`；
  - `supply_chain_official_relationship` `183/276`；
  - `app_rank_store_proxy` `75/103`；
  - `platform_review_proxy` `129/182`；
  - `hiring_capacity_proxy` `43/526`；
  - `channel_offer_proxy` `4/148`；
  - `developer_ecosystem_proxy` `5/137`；
  - `regulated_product_context` `32/68`；
  - `auto_product_identity_context` `10/17`。
- R5 product KPI closeout 已落账：
  - `product_kpi_exact_slot_closeout_v0_1.jsonl` 覆盖 `603/603` 公司；
  - `77` 家有 company-disclosed `product_kpi_exact_slot`；
  - `526` 家为 `product_kpi_exact_gap`，原因是公司未披露产品级 KPI exact row，或只有 official surface / filings taxonomy / proxy context，不能替代 product KPI。

最新 exact-slot matrix：

- company_count: `603`
- all_required_exact_ready_company_count: `85`
- partial_exact_ready_company_count: `518`
- no_exact_ready_company_count: `0`
- exact_slot_row_count: `27,276`
- exact_slot_gap_count: `1,131`
- exact rows by layer: `L1=20,523`、`L2=4,195`、`L3=2,541`
- companies with any exact row by layer: `L1=587`、`L2=603`、`L3=420`

最新 R5 closeout：

- `exact_slot_gap_closeout_v0_1.jsonl`: `1,131` rows
- `exact_slot_gap_closeout_summary_v0_1.json`: `status=pass`
- `unclassified_closeout_count=0`
- closeout_class:
  - `public_source_exhausted_gap=957`
  - `resolver_gap=151`
  - `parser_or_source_profile_gap=16`
  - `not_applicable_or_source_gap=7`
- 主要 closeout reason:
  - `greenhouse_lever_ashby_smartrecruiters_no_bound_public_job_rows=464`
  - `usaspending_no_recipient_bound_award_or_api_fetch_gap=232`
  - `cdw_channel_search_no_verified_sku_price_availability_match=144`
  - `no_verified_project_to_issuer_product_resolver_for_broad_developer_artifacts=132`
  - `itunes_search_no_seller_bound_app_or_platform_listing=81`
  - `clinicaltrials_openfda_no_sponsor_or_applicant_bound_record=36`
  - `non_us_or_uncovered_sec_companyfacts_requires_local_exchange_or_ir_table_parser=16`
  - `nhtsa_make_model_not_applicable_or_no_make_bound_record=7`

解释口径：

1. `no_exact_ready_company_count=0` 表示 603 家公司都至少有一类 parser-backed exact slot 或 audited source route，不再是完全空白。
2. `L2=603` 表示每家公司都有 L2 trusted / official / macro context exact slot。
3. `L1=587` 表示非美或未覆盖 SEC CompanyFacts 的 `16` 家仍需要当地交易所 / company IR / 年报表格 parser，不能用官网或 proxy 兜底。
4. `L3=420` 表示公开免费 proxy 源能为 420 家提供至少一条可提权为 proxy exact 的 row；其余公司已经有 attempts 或 resolver boundary，不能伪造 exact proxy。
5. R1-R5 的通过条件现在是：所有 ready row 可被 contract 验证，所有剩余 gap 有 closeout ledger，且 closeout row 不能进入 ClaimCard 或核心 thesis。不是声明所有产品 KPI、渠道、招聘、订单、developer、app、监管和非美披露都能被公开免费源填满。

### 2026-06-19 R6-R9 执行 closeout

本轮按用户指定的四步顺序继续补 L1 / L3 覆盖，不把脚本缺陷或 requirement 误配伪装成公开数据缺口：

- R6 `L1-non-US-disclosure-parser` 已落地：
  - 新增 `scripts/data_expansion/build_non_us_l1_financial_statement_metric_runtime_rows.py`，把非美 / 未覆盖 SEC CompanyFacts 的 local exchange、company IR、annual report 表格和已知 parent segment disclosure 转成 L1 `company_reported_financial_statement_metric` exact rows；
  - 运行结果：`target_ticker_count=16`、`covered_target_ticker_count=16`、`runtime_row_count=88`、`uncovered_target_ticker_count=0`；
  - row source：`company_ir_reports=87`、`company_reported_product_operating_metrics=1`；
  - metric families：`revenue=15`、`operating_income=16`、`net_income=11`、`assets=14`、`liabilities=13`、`equity=8`、`gross_profit=11`；
  - `primary_company_disclosure` 在最新 exact-slot matrix 中达到 `603/603 exact_slot_ready`。
- R7 `L3-requirement-recalibration` 已落地：
  - `financial_regulatory_context`、`energy_utility_context` 这类官方/监管上下文允许按 contract 同时计入 `L2/L3` proxy/context 层，但仍不能支持 issuer revenue、sales volume、market share、ASP、库存或 sell-through；
  - 对 `V6 Banks / Financials` 删除明显不适用的 app / platform review proxy requirements，避免把“不该要求的数据”误报成公司缺口；
  - exact-slot row 现在保留 `contract_layer_ids`，coverage matrix 按 contract layer 聚合，避免多层官方/proxy row 被错误只计一层。
- R8 `L3-lane-adapter-batches` 已落地到本轮 minimum gate 所需范围：
  - `scripts/data_expansion/build_broad_official_careers_context_rows.py` 扩展 official careers / ATS adapter，支持 Workday、Greenhouse、Lever、Jibe API、Phenom embedded job JSON、SuccessFactors HTML search table；
  - domain locator 改为优先 `jobs.<domain>` / `careers.<domain>`，dedupe 改为新行覆盖旧 schema 行，job rows 缺 posted date 时使用 snapshot date，避免结构化字段缺失导致可用 row 被拒；
  - exact-slot coverage matrix 默认读取 `non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl` 和 `broad_official_careers_context_rows_v0_1.jsonl`。
- R9 `L3-minimum-coverage-gate` 已落地并通过：
  - 新增 `scripts/data_expansion/build_l3_minimum_coverage_gate.py`，要求每家公司 `L3 >= 1`，并要求 priority / deep-research 公司达到 `>=2` 个 independent source roles；
  - priority/deep role 统计按 `L2/L3` independent roles 计算，排除 `primary_company_disclosure`，避免把财报披露当成外部验证源；
  - 最新结果：`status=pass`、`company_count=603`、`base_fail_company_count=0`、`priority_fail_company_count=0`、`l3_zero_company_count=0`、`l3_one_company_count=0`、`l3_gt_one_company_count=603`、`low_coverage_company_count=0`；
  - independent role distribution：`3=94`、`4=162`、`5=210`、`6=124`、`7=12`、`9=1`。

最新 R6-R9 exact-slot matrix：

- company_count: `603`
- status: `gap`，原因是全量 source-role / product-KPI requirements 仍有公开源边界；这不是 R9 minimum coverage 失败。
- all_required_exact_ready_company_count: `10`
- no_exact_ready_company_count: `0`
- exact_slot_row_count: `28,864`
- exact_slot_gap_count: `1,152`
- companies with exact rows by layer: `L1=603`、`L2=603`、`L3=603`
- exact slot counts by layer: `L1=21,590`、`L2=5,795`、`L3=5,642`
- ready source roles:
  - `primary_company_disclosure=603/603`
  - `trusted_external_context=603/603`
  - `macro_official_context=603/603`
  - `public_order_proxy=382/515`
  - `official_product_surface=310/310 applicable`
  - `energy_utility_context=216/216`
  - `supply_chain_official_relationship=201/276`
  - `platform_review_proxy=124/182`
  - `technology_research_proxy=111/111`
  - `financial_regulatory_context=77/77`
  - `app_rank_store_proxy=74/103`
  - `hiring_capacity_proxy=65/603`
  - `regulated_product_context=32/68`
  - `auto_product_identity_context=10/17`
  - `developer_ecosystem_proxy=5/137`
  - `channel_offer_proxy=4/148`

解释口径：

1. R6-R9 解决的是 `L1=16` 家非美/未覆盖财报披露空洞，以及 `L3=0/1` 的 minimum external/proxy coverage 问题。
2. R9 通过不等于所有 source role 都 full covered；仍有 role-specific gaps，例如 hiring、channel、developer、regulated product、app/review、public order 的公司级 exact proxy 缺口。
3. 这些剩余缺口必须继续按 exact-slot gap ledger / role-specific adapter 修，不能在 full-chain runtime 里用弱网页摘要兜底。
4. 下一步接 runtime 时，Research Lead 应读取 exact-slot matrix + R9 minimum gate + gap ledger，先知道每家公司能用哪些 L1/L2/L3 exact/proxy rows，再决定是否触发 targeted repair 或暴露 public/commercial gap。
