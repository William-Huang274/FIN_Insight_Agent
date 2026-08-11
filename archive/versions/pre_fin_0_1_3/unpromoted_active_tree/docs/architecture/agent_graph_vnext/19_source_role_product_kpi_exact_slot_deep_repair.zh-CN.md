# 19 Source-Role / Product-KPI Exact Slot Deep Repair

日期：2026-06-19

## 背景

R6-R9 已经关闭 L1 / L3 minimum coverage：

- `primary_company_disclosure=603/603 exact_slot_ready`
- `L3 zero=0`
- `L3 one=0`
- `priority_fail=0`

但这只表示每家公司都有可用 L1/L2/L3 证据层，不表示每个 source-role、每个产品 KPI 槽位都补齐。

当前仍有两类深层缺口：

1. source-role 细分缺口：
   - `hiring_capacity_proxy`
   - `channel_offer_proxy`
   - `developer_ecosystem_proxy`
   - `regulated_product_context`
   - `public_order_proxy`
   - `supply_chain_official_relationship`
   - app/review/auto 等其他适用角色
2. product-KPI exact-slot 缺口：
   - company-disclosed product / business line / segment KPI exact rows 不应被 product slot graph 口径漏掉；
   - 但 geography / broad region / non-product rows 也不能冒充产品 KPI。

## 本阶段目标

本阶段目标不是把任何网页摘要都拉进来，而是继续把能被公开、免费、可得来源证明的事实转成 exact/proxy slots：

1. 对每个 source-role gap 给出公司级原因：
   - requirement 不适用；
   - locator 未找到；
   - public endpoint 无数据；
   - fetched 但 parser 抽不出 required fields；
   - fetched 但 issuer/product/counterparty binding 不足；
   - 公开源理论上没有，只能 commercial tracker 或暴露 gap。
2. 对每个 product-KPI gap 给出公司级原因：
   - 公司已披露产品/产品线 KPI，但旧 slot/closeout 未计入；
   - 公司披露的是业务 segment KPI，可用于基本面/业务分析，但不能冒充产品级 KPI；
   - 公司披露的是 geography / region / customer group，不算 product KPI；
   - 公司没有披露 product/segment KPI，公开 proxy 也不能提权，只能暴露 public/commercial gap；
   - 可能存在 IR deck / annual report table / local exchange / PDF footnote 深挖空间，需要继续 parser/locator。
3. 对 adapter 深挖空间优先修脚本，不允许把脚本/requirement 问题写成公开源边界。

## Product KPI 口径

### A. Product / Product-Line KPI Exact Slot

可进入产品/产线 section 的强证据：

- 产品、产品族、治疗药物、车型、SKU、品牌、产品线、业务线；
- 必须来自公司披露；
- 必须有 `value/unit/period/product_or_segment/citation/source_url`；
- 支持产品收入、出货、交付、backlog、subscribers、AUM、capacity、utilization、ASP、product margin 等公司披露事实。

### B. Business Segment Operating Metric

可进入基本面/业务 segment 分析，但不直接作为产品 exact slot：

- reportable segment；
- customer group；
- business unit；
- financial product/service line；
- broad platform/service grouping。

它能支撑“业务结构/收入 mix/利润驱动”，但不能直接推导 SKU、产品规格、渠道、销量、市场份额。

### C. Non-Product / Geography / Context Metric

只能作为背景或基本面辅助：

- geographic region；
- country/continent；
- corporate/other/reconciliation；
- generic “products and services” without product-family binding；
- percentage-only row without revenue/volume denominator。

它不能提升 product-KPI exact slot。

## 执行顺序

### S1 Product-KPI Coverage Reconciliation

先修 `product_kpi_exact_slot_closeout` 的漏计问题：

- 读取 `company_reported_product_operating_metric_runtime_rows_v0_1.jsonl`；
- 对 parser-verified runtime KPI rows 按 `product_node_type` / product text 分类；
- closeout 里同时输出：
  - `product_kpi_exact_ready`
  - `business_segment_metric_ready`
  - `geographic_or_non_product_metric_only`
  - `company_undisclosed_product_kpi_gap`
  - `adapter_or_parser_deep_repair_needed`
- 不再只依赖 `company_product_slots_v0_1` 的 `product_kpi_exact_slot` 状态。

通过条件：

- 旧 `77` 家 ready 与 runtime `186` ticker 差异必须被解释清楚；
- 每个 ticker 只能因明确分类进入 product ready / segment ready / non-product / gap；
- 文档和 summary 给出分类计数。

### S2 Product-KPI Deep Parser / Locator Repair

在 S1 后，对仍是 `adapter_or_parser_deep_repair_needed` 的公司按来源深挖：

- SEC / FSD / XBRL / HTML tables；
- IR deck / annual report PDF；
- local exchange / regulator filings；
- company KPI tables / product revenue tables；
- 只提升 parser-verified rows。

通过条件：

- 每条新增 row 进入 runtime exact-slot contract；
- 不能用官方产品页、招聘、渠道、新闻、宏观 proxy 填 product KPI。

### S3 Source-Role Requirement Applicability Audit

对高缺口 source-role 重新判断适用性：

- `hiring_capacity_proxy` 是否适用于所有公司；
- `developer_ecosystem_proxy` 是否只适用于 software/cloud/developer-tool/AI platform/open-source-heavy companies；
- `channel_offer_proxy` 是否只适用于有公开渠道 SKU / reseller / ecommerce 的产品族；
- `regulated_product_context` 是否只适用于 pharma/medtech/auto/regulated device 等；
- `public_order_proxy` / `supply_chain_official_relationship` 是否按行业/公司类别要求。

通过条件：

- 不适用 requirement 不再计为 company gap；
- 适用但未补的 company 保留 adapter/locator/gap cause。

### S4 Source-Role Adapter Deep Repair

优先按缺口大、信息强度高、可自动化程度排序：

1. hiring / official careers：扩 Workday/Jibe/Phenom/SuccessFactors/Greenhouse/Lever/Ashby/SmartRecruiters/site XML。
2. public order / supply chain：USAspending、EU TED、SAM、official customer/supplier/news pages。
3. developer ecosystem：GitHub/npm/PyPI/HuggingFace，通过 official docs/package/repo seed 绑定，避免 blind search。
4. channel offer：CDW、Digi-Key、Mouser、Arrow、Amazon/JD/official store，只记录 SKU/price/availability snapshot。
5. regulated product：ClinicalTrials、openFDA、NHTSA、CMS，按 sponsor/applicant/make/model resolver。

通过条件：

- ready_count 提升；
- rejected attempts 有具体 source / parser / binding reason；
- 剩余 gap 能按公司说明“为什么公开源找不到或不能提权”。

## Runtime Boundary

- closeout / gap rows 不能进入 ClaimCard。
- proxy exact row 只能支持自身 source-role 事实，不得提权为销售、收入、份额、ASP、库存、sell-through。
- product-KPI exact slot 只能来自公司披露或监管/交易所等公司正式披露路径。

## 2026-06-19 本轮执行结果

### 已修复的问题

1. `technology_research_proxy` 的 OpenAlex 尝试记录缺失：
   - 原问题：OpenAlex adapter 已经真实跑过，但只写 rows/summary，没有写 attempt ledger，导致 22 条 gap 被误判为 `adapter_or_locator_deep_repair_needed`。
   - 修复：`build_v1_openalex_technology_research_context_rows.py` 新增 `v1_openalex_technology_research_attempts_v0_1.jsonl` 持久化；closeout ledger 接入 `openalex_api` attempts。
   - 结果：22 条 technology gap 全部从“未做 adapter”变成 `openalex_no_issuer_topic_bound_research_proxy`，即 OpenAlex API 可访问，但 company/product-family alias 下没有可绑定 issuer-topic works。
2. `developer_ecosystem_proxy` 真实覆盖不足：
   - 原问题：只有 AMZN/CRM/GOOGL/MSFT/NVDA 默认 probe；71 条 developer gap 多数是 resolver gap。
   - 修复：新增 `developer_ecosystem_official_seed_registry_v0_1.jsonl`，只放可解释的官方 GitHub/npm/PyPI/HuggingFace URL；adapter 新增 seed registry、attempt ledger、merge 输出和 closeout 读取。
   - 结果：developer exact ready 从 `5` 提升到 `31`，developer gap 从 `71` 降到 `45`。
3. `official_product_surface` catalog rows 未被 exact matrix 读取：
   - 修复：exact matrix 纳入 `official_product_catalog_context_rows_v0_1.jsonl`，contract 接受 `official_product_catalog_parser_pass`。
   - 结果：`official_product_surface` gap 为 `0`，ready 为 `559`。
4. Product-KPI closeout 口径过粗：
   - 修复：product KPI closeout 读取 runtime rows 并区分 product-family exact、business/segment exact、geography/non-product only、gap。
   - 结果：不再把 official product page / taxonomy surface 当成 product KPI，也不把 geography / generic rows 冒充产品 KPI。

### 当前 source-role exact-slot 状态

最新 `exact_slot_coverage_matrix_v0_1`：

- `company_count=603`
- `all_required_exact_ready_company_count=370`
- `partial_exact_ready_company_count=233`
- `no_exact_ready_company_count=0`
- `exact_slot_gap_count=303`
- `unclassified_closeout_count=0`
- `l3_zero_company_count=0`
- `l3_one_company_count=0`
- `l3_gt_one_company_count=603`

剩余 source-role gap 的公司级原因已经落入 `exact_slot_gap_closeout_v0_1.jsonl`：

| requirement | gap | closeout reason |
| --- | ---: | --- |
| `developer_ecosystem_proxy` | 45 | 44 家缺官方 docs/package/repo 到 issuer/product 的 verified resolver；1 家官方 seed 尝试失败或未绑定 |
| `channel_offer_proxy` | 58 | CDW public search/product pages 尝试后无 issuer/product-bound SKU price/availability；下一步若继续深挖需按 family 接 Digi-Key/Mouser/Arrow/Amazon/JD/official store |
| `hiring_capacity_proxy` | 49 | 48 家 Greenhouse/Lever/Ashby/SmartRecruiters 公开端点无 issuer-bound job rows；1 家 ATS endpoint 有数据但 issuer binding 未过 |
| `regulated_product_context` | 36 | ClinicalTrials/openFDA 公开 API 尝试后无 sponsor/applicant-bound row |
| `public_order_proxy` | 33 | USAspending 尝试后无 recipient-bound award row 或 API fetch gap；非美/local tender 仍需按司法辖区单独 adapter |
| `app_rank_store_proxy` | 31 | iTunes public search/lookup 无 seller-bound app/listing |
| `technology_research_proxy` | 22 | OpenAlex 公开 API 尝试后无 issuer-topic-bound research proxy row |
| `platform_review_proxy` | 21 | iTunes/App Store 公开源无 seller-bound review/listing proxy |
| `supply_chain_official_relationship` | 6 | USAspending / public award route 无可绑定关系 row |
| `auto_product_identity_context` | 2 | NHTSA vPIC 对相关 ticker 无 make/model exact row 或 requirement 不适用 |

这里的 `public_source_exhausted_gap` 只表示当前已接入的免费公开 route 真实尝试后无 exact row；它不等于商业 tracker 不存在。需要商业 tracker 的主要仍是真实销量、份额、sell-through、渠道库存、ASP、处方量、POS、app revenue 等。

### 当前 product-KPI 状态

最新 `product_kpi_deep_gap_diagnostic_v0_1`：

- `product_family_exact_ready_ticker_count=136`
- `business_or_segment_exact_ready_ticker_count=43`
- `product_or_business_kpi_ready_ticker_count=179`
- `geographic_or_non_product_only_ticker_count=7`
- `product_kpi_exact_gap=417`
- `strict_candidate_gap_ticker_count=301`
- `no_candidate_gap_ticker_count=116`

剩余 417 家不是一个单一原因：

| class | ticker count | 含义 |
| --- | ---: | --- |
| `parser_candidate_found_but_not_runtime_promotable` | 301 | 抽到了候选，但严格 gate 不能提权；主要是 geographic/non-product、segment schema 未区分、百分比/变化值、local sentence relation 未验证 |
| `product_surface_or_taxonomy_available_no_company_kpi_candidate` | 101 | 有官网产品面或 taxonomy，但当前 SEC/公开披露扫描没有 company-disclosed product KPI 候选 |
| `non_us_local_or_ir_parser_required` | 15 | 非美公司需要 local exchange / company IR / annual report PDF table parser 深挖 |

当前不能做的事：

- 不允许用官网产品页、招聘、订单、渠道、OpenAlex、app/review、宏观数据替代公司披露 product KPI；
- 不允许把地理收入、泛化 “Products and Services”、百分比变化值、未验证句子关系提权；
- 对剩余 301 家候选，下一步只能按 source-specific table / period / region / product-binding verifier 深挖，不能批量放宽 gate。

### 下一步若继续深挖的优先级

1. Product-KPI 301 家候选：
   - 先做 source-specific table verifier，把 `strict_candidates_are_business_segment_metrics` 和 `strict_candidates_mostly_geographic_or_non_product` 拆成 `segment_ready`、`region_only`、`not_product` 三类；
   - 对 `sentence_local_verifier_*` 只做 local citation / sentence relation verifier，不批量提升。
2. 非美 15 家 product KPI：
   - 按交易所/IR annual report PDF table parser 做局部深挖。
3. Developer 45 家：
   - 只从 company official docs / developer page / package metadata 生成 seed，不做 GitHub blind search 提权。
4. Channel / app / review / public-order：
   - 需要按 product family 接更细 marketplace / distributor / local tender adapter；否则只能保留当前 route 的公开源耗尽边界。

## 2026-06-19 R12 Source-Role / Product-KPI v0.5 深修结果

本节 supersede 上一节的 `303` gap 中间态，作为当前 accepted closeout。

### 本轮修复的脚本漏斗

1. Product-KPI v0.5 promotion：
   - 默认从 full strict repair facts 读取，而不是只读 sentence subset。
   - 仅在 row label、currency revenue、period、source table context、issuer/product binding 均通过时提升 product/category/product-line revenue。
   - geography revenue、customer/channel row、non-product row、percentage/change cell 继续拒绝，不能填 product-KPI exact slot。
   - 结果：`product_family_exact_ready_ticker_count=161`，`business_or_segment_exact_ready_ticker_count=44`，`product_or_business_kpi_ready_ticker_count=205`，`product_kpi_exact_gap=388`。
2. ClinicalTrials regulated parser：
   - 原漏斗：`query.spons` 返回 collaborator-bound trial 时只看 lead sponsor，ABT/MRNA/GSK/ARGX/A 等被误判为无 sponsor-bound row。
   - 修复：ClinicalTrials 接受 lead sponsor / collaborator / organization 任一 alias-bound row；openFDA 仍要求 applicant/sponsor-bound。
   - 结果：`regulated_product_context` gap 从 `36` 降到 `11`。
3. USAspending public-order parser：
   - 原漏斗：把 ticker 和多个 alias 一次性塞入 `recipient_search_text`，导致 AMAT/CRM/IDXX/FTV/MRVL/ONTO/COR 等被无关或空结果挤掉。
   - 修复：移除 ticker 噪声，补 legal/subsidiary alias，并改成逐 alias 查询、逐 alias 验证、合并 rows。
   - 结果：`public_order_proxy` gap 从 `33` 降到 `19`，`supply_chain_official_relationship` gap 从 `6` 降到 `4`。
4. iTunes app/review parser：
   - 原漏斗：只用 holding company legal name 搜索，BKNG/MELI/WBD/LYV/RCL/TTWO 等品牌 app 搜不到。
   - 修复：为 app/review route 增加官方品牌/子公司 alias 轮询，但仍要求 seller/artist-bound listing。
   - 结果：`app_rank_store_proxy` gap 从 `31` 降到 `9`；`platform_review_proxy` gap 从 `21` 降到 `11`。
5. Official careers / hiring locator：
   - 原漏斗：多数 hiring gap 没跑 official careers locator，且 CRM/SBUX/EME/FFIV/GOOGL domain cache 缺失或错误。
   - 修复：补 domain overrides，并 targeted 跑 Workday/Jibe/Phenom/SuccessFactors/Greenhouse/Lever/Ashby/SmartRecruiters/official careers pages。
   - 结果：`hiring_capacity_proxy` gap 从 `49` 降到 `43`。
6. Channel offer CDW matcher：
   - 原漏斗：CDW 里 issuer-bound broad batch probe 因 product family 词没出现在标题中被过度拒绝。
   - 修复：允许 broad batch 下的 brand-only match，但继续拒绝 accessory/protection/compatible third-party rows。
   - 结果：`channel_offer_proxy` gap 从 `58` 降到 `53`。

### 最新 source-role exact-slot 状态

最新 `exact_slot_coverage_matrix_v0_1`：

- `company_count=603`
- `all_required_exact_ready_company_count=435`
- `partial_exact_ready_company_count=168`
- `no_exact_ready_company_count=0`
- `exact_slot_gap_count=203`
- `unclassified_closeout_count=0`

剩余 gap：

| requirement | gap | 当前原因 |
| --- | ---: | --- |
| `channel_offer_proxy` | 53 | CDW route 无可绑定 SKU/price/availability；下一步需要 family-scoped Digi-Key/Mouser/Arrow/Amazon/JD/official-store adapters |
| `hiring_capacity_proxy` | 43 | 已跑 public ATS + official careers；未取得 issuer-bound public job rows，或站点无稳定公开 job row/API |
| `developer_ecosystem_proxy` | 29 | 缺 verified official docs/package/repo seed；不允许 GitHub/npm blind search 提权 |
| `technology_research_proxy` | 22 | OpenAlex 查询后无 issuer-topic-bound research proxy；下一步若深挖应接 PatentsView/assignee resolver |
| `public_order_proxy` | 19 | USAspending 逐 alias 查询后仍无 recipient-bound row；非美/local tender 需单独司法辖区 adapter |
| `platform_review_proxy` | 11 | iTunes 品牌/公司 alias 搜索后仍无 seller-bound review/listing |
| `regulated_product_context` | 11 | ClinicalTrials/openFDA 无 sponsor/collaborator/applicant-bound row；provider/distributor 多数不能强行提权 |
| `app_rank_store_proxy` | 9 | iTunes 品牌/公司 alias 搜索后仍无 seller-bound app listing |
| `supply_chain_official_relationship` | 4 | USAspending / public award route 无可绑定关系 row |
| `auto_product_identity_context` | 2 | NHTSA vPIC 无 make/model exact row 或 requirement 不适用 |

### 最新 Product-KPI 状态

最新 `product_kpi_deep_gap_diagnostic_v0_1`：

- `product_family_exact_ready_ticker_count=161`
- `business_or_segment_exact_ready_ticker_count=44`
- `product_or_business_kpi_ready_ticker_count=205`
- `geographic_or_non_product_only_ticker_count=10`
- `product_kpi_exact_gap=388`
- `strict_candidate_gap_ticker_count=272`
- `no_candidate_gap_ticker_count=116`

剩余 `388` 家的解释：

| class | ticker count | 含义 |
| --- | ---: | --- |
| `parser_candidate_found_but_not_runtime_promotable` | 272 | 候选存在，但主要是 geographic/non-product、business segment schema 未拆、percentage/change cell、local sentence relation 未验证，不能作为 product KPI exact |
| `product_surface_or_taxonomy_available_no_company_kpi_candidate` | 101 | 有官网产品面或 taxonomy，但 SEC/公开披露扫描没有 company-disclosed product KPI 候选 |
| `non_us_local_or_ir_parser_required` | 15 | 非美公司仍需 local exchange / company IR / annual report PDF table parser 深挖 |

### 最新边界

- `public_source_exhausted_gap` 只代表当前已接入免费公开 route 真实尝试后没有 exact row，不代表商业 tracker 不存在。
- `resolver_gap` 代表缺 official seed / issuer-product resolver，不允许 blind search 提权。
- Product-KPI exact 仍只允许公司披露 / 监管或交易所正式披露路径；L2/L3 proxy 不得填收入、销量、份额、ASP、库存、sell-through。

## 2026-06-19 R13 Company Gap Docket 一轮落地

本轮把剩余 gap 从 summary count 下钻成逐公司、逐 source-role / Product-KPI 的 `CompanyGapDocket`，避免后续继续靠聊天记忆判断哪些 gap 该修、哪些可最终暴露。

### 输出

- docket rows: `data/manifests/company_gap_docket_v0_1.jsonl`
- adapter cluster queue: `data/manifests/company_gap_adapter_cluster_queue_v0_1.jsonl`
- summary: `data/manifests/company_gap_docket_summary_v0_1.json`
- report: `docs/internal/vnext_20260610/vertical_lanes/company_gap_docket.zh-CN.md`

### Gate 结果

- `docket_count=591`
- `source_role_gap_docket_count=203`
- `product_kpi_gap_docket_count=388`
- `unique_gap_company_count=434`
- `cluster_count=15`
- `unclassified_docket_count=0`

这代表当前所有剩余 source-role gap 和 Product-KPI gap 都已经进入可执行 docket，不再是笼统的 “缺口”。每条 docket 都包含：

- `ticker / company / lane / requirement`
- `family_ids / family_names`
- `cluster_id / adapter_family / priority`
- `source_ladder`
- `pass_condition`
- `final_gap_allowed_only_after`
- `sample_attempts_or_candidates`

### 下一批 adapter cluster

| cluster | dockets | priority | 含义 |
| --- | ---: | --- | --- |
| `product_kpi_source_specific_table_verifier` | 272 | high | 候选存在但不能提权；下一步做 table / period / product binding verifier |
| `channel_offer_distributor_marketplace_adapter` | 53 | high | CDW 不够；下一步按 family 接 official store / Amazon / JD / Digi-Key / Mouser / Arrow |
| `developer_ecosystem_official_seed_locator` | 29 | high | 缺 official docs/repo/package seed；下一步只从官方 seed 开始，不做 blind search |
| `product_kpi_non_us_ir_local_exchange_parser` | 15 | high | 非美公司需 local exchange / IR annual report / PDF table parser |
| `public_order_local_tender_and_recipient_adapter` | 12 | high | USAspending 后仍缺；需按 jurisdiction 接 SAM.gov / EU TED / Canada / Japan 等 |
| `regulated_product_context_regulatory_api_adapter` | 9 | high | ClinicalTrials/openFDA 后仍缺；需 FDA device / EMA / other regulatory route |
| `public_order_non_us_local_tender_adapter` | 7 | high | 非美采购/订单源需要 local tender adapter |
| `supply_chain_official_relationship_resolver` | 4 | high | 供应链关系需 official news / counterparty official / contract disclosures |
| `regulated_product_animal_health_veterinary_adapter` | 2 | high | ZTS/IDXX 类 animal-health 需 veterinary regulatory route |
| `product_kpi_ir_deck_annual_report_locator` | 101 | medium | 有产品面/taxonomy 但当前披露扫描无 KPI；需 IR deck / annual report locator 后再 final gap |
| `hiring_capacity_site_specific_public_jobs_adapter` | 43 | medium | public ATS/official careers 仍缺；需 site-specific job parser 或公开源边界审计 |
| `technology_research_patents_assignee_resolver` | 22 | medium | OpenAlex 后仍缺；需 PatentsView/assignee resolver |
| `platform_review_seller_alias_adapter` | 11 | medium | App/review 需 Google Play/official app page 等 seller-bound route |
| `app_marketplace_seller_alias_adapter` | 9 | medium | 同上，偏 app listing |
| `auto_product_identity_regulatory_boundary_audit` | 2 | low | NHTSA make/model route 的边界或 make alias 修复 |

### 口径

`CompanyGapDocket` 本身不是 evidence promotion。它只是把剩余 gap 变成可执行队列。任何 gap 只有在对应 `source_ladder` 已有 attempt rows，并且仍无法通过 issuer/product/counterparty/value/unit/period/citation gate 后，才允许成为 final public-source boundary 或 commercial tracker gap。

## 2026-06-19 R14 Product-KPI Source-Specific Verifier

本轮按 1-6 修复顺序先完成第 1 步：对 `product_kpi_source_specific_table_verifier` 的 272 家公司候选逐条做 source-specific verifier，目标是把候选分成可提权 product/category/product-line metric、business segment metric、region-only、percentage/change、sentence relation 不足、operating metric 待第 2 步，而不是继续把 272 家笼统留作 Product-KPI gap。

### Runtime 产物

- verifier rows: `data/manifests/product_kpi_source_specific_verifier_v0_1.jsonl`
- ticker summary: `data/manifests/product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl`
- promotable rows: `data/manifests/product_kpi_source_specific_verifier_promotable_rows_v0_1.jsonl`
- summary: `data/manifests/product_kpi_source_specific_verifier_summary_v0_1.json`
- report: `docs/internal/vnext_20260610/vertical_lanes/product_kpi_source_specific_verifier.zh-CN.md`

### Gate 结果

- `target_ticker_count=272`
- `candidate_count=21,822`
- `candidate_ticker_count=272`
- `unclassified_candidate_count=0`
- `promotable_product_metric_count=0`
- `business_segment_metric_candidate_count=7,468`
- `operating_metric_defer_step2_candidate_count=2,232`
- `region_only_candidate_count=1,653`
- `percentage_or_change_candidate_count=5,608`
- `sentence_relation_insufficient_candidate_count=988`

分类明细：

| class | count | 处理 |
| --- | ---: | --- |
| `business_segment_metric` | 7,468 | 不作为 product KPI exact；第 2 步进入行业 operating/business metric slot |
| `business_segment_mixed_table_needs_column_group` | 1,454 | 不提权；第 2 步需要 column-group / segment schema 解析 |
| `operating_metric_defer_step2` | 2,232 | 不提权；第 2 步按行业 KPI exact slot 处理 |
| `region_only` | 1,653 | 不提权；只有 region dimension 明确支持时才可进入 region schema |
| `percentage_or_change` | 5,608 | 不提权；percentage/change cell 不能当绝对产品 KPI |
| `sentence_relation_insufficient` | 988 | 不提权；需要 sentence-local relation verifier |
| `period_or_version_conflict` | 384 | 拒绝；period/fiscal year 不一致 |
| `non_product_or_total` | 2,035 | 拒绝；Total revenue / generic revenue / non-product row |

### 结论

这 272 家不是“完全没跑”，而是候选里没有能通过严格门槛的 product/category/product-line exact metric。抽样复核显示，所谓 product node 多数是 `Total revenue`、`Total casino revenues`、percentage 表或缺 row/column exact binding 的句子候选；这些不能为产品经营表现提权。

本轮同时把 `product_kpi_source_specific_verifier_ticker_summary_v0_1` 并回 `CompanyGapDocket` 的 `source_specific_verifier_summary` 字段。后续第 2 步不再从原始 21,822 条里盲扫，而是直接消费每家公司已分类的 `business_segment_metric`、`business_segment_mixed_table_needs_column_group` 和 `operating_metric_defer_step2`。

## 2026-06-19 R14 Step 2 Industry Operating Metric Slot

第 2 步已把 Step 1 分类出的 business segment / operating metric 候选转成独立的 `industry_operating_metric_exact_slot`，但不把它们并回 Product-KPI exact。这样做的目的：

- 对金融、能源、公用事业、地产、SaaS、医疗服务、工业和零售等行业，保留 AUM、backlog、capacity、production、shipments、unit deliveries、same-store sales 等可用于基本面分析的 company-disclosed exact rows；
- 同时禁止这些 row 冒充产品收入、销量、市场份额、ASP、sell-through、渠道库存或商业 tracker 数据；
- 对 AUM / deposit / loan balance 等金融口径做行级收紧，避免把 net flows、inflows、service charges on deposit accounts 这类收入或流量口径误提权成余额型 operating metric。

### Runtime 产物

- rows: `data/manifests/industry_operating_metric_slot_rows_v0_1.jsonl`
- rejections: `data/manifests/industry_operating_metric_slot_rejections_v0_1.jsonl`
- summary: `data/manifests/industry_operating_metric_slot_summary_v0_1.json`
- report: `docs/internal/vnext_20260610/vertical_lanes/industry_operating_metric_slot.zh-CN.md`

### Gate 结果

- `runtime_row_count=1,719`
- `runtime_ticker_count=171`
- `unclassified_rejection_count=0`
- `rejection_count=7,981`

Slot 明细：

| slot | rows | 说明 |
| --- | ---: | --- |
| `business_segment_revenue` | 1,577 | company-disclosed business / segment revenue，只能支撑业务结构和基本面分析，不能当 product-family revenue |
| `capacity_utilization_or_production_volume` | 65 | 能源/工业等披露的产量、吞吐、产能或 utilization 相关行 |
| `same_store_sales_growth` | 34 | 零售/餐饮 comparable-store / same-store 增长，允许负值，但只作为增长率 |
| `backlog_or_orders` | 23 | backlog / bookings / RPO / orders 等有表格锚点的行 |
| `shipments` | 11 | shipment / production shipment / tonnes 等交付或出货行 |
| `unit_sales_or_deliveries` | 7 | sales in units / deliveries / engines / turbines 等单位销售或交付行 |
| `aum` | 2 | 仅保留 direct average/ending/total AUM 余额行；flows/inflows/outflows 被拒绝 |

当前 `deposits=0`、`loan_balance=0` 是严格 gate 的结果，不是未跑：现有候选里没有可安全证明 deposit balance / loan balance 的直接余额行；`service charges on deposit accounts` 等收入行已被拒绝。

### Rejection 口径

主要拒绝原因：

| reason | count | 含义 |
| --- | ---: | --- |
| `conflicting_values_for_industry_operating_claim` | 2,744 | 同 ticker/slot/product/period/unit 出现多个不同值，不能提权 |
| `duplicate_industry_operating_claim` | 2,133 | 重复候选，保留唯一 row |
| `business_segment_metric_not_currency_revenue_or_generic_row` | 1,225 | 不是安全的 currency revenue segment row，或为 flow/service fee/non-product/generic row |
| `backlog_metric_without_backlog_or_order_context` | 939 | 缺 backlog / order / RPO 表格锚点 |
| `production_metric_without_capacity_or_throughput_context` | 483 | 缺 capacity / throughput / production 语义 |

### 结论

Step 2 能把 `171` 家公司的经营指标 exact rows 纳入后续基本面和行业 KPI 分析，但它并不解决 Product-KPI exact gap。后续 full-chain 使用时，应把这批 row 暴露给 Fundamental / Industry / Product Specialist 的“行业经营指标”视图，并在 Memo / Verifier 中标注 `company_disclosed_industry_operating_metric` 边界，禁止写成产品销售、份额、ASP、渠道库存或 sell-through 结论。

## 2026-06-19 R14 Step 3 Non-US Local Disclosure Product-KPI Parser

第 3 步已把 `product_kpi_non_us_ir_local_exchange_parser` 从笼统的 `15` 家非美缺口拆成可提权 rows 与明确披露边界。重点不是放宽 Product-KPI gate，而是把 DART / HKEX / CNINFO / TW MOPS / JP IR / EU annual report / company official news 中能证明 `value/unit/period/product_or_segment/citation` 的行转成 L1 exact runtime rows。

### Runtime 产物

- rows: `data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl`
- rejections: `data/manifests/non_us_product_kpi_local_disclosure_runtime_rejections_v0_1.jsonl`
- summary: `data/manifests/non_us_product_kpi_local_disclosure_runtime_summary_v0_1.json`
- report: `docs/internal/vnext_20260610/vertical_lanes/non_us_product_kpi_local_disclosure_runtime.zh-CN.md`

### Gate 结果

- `target_ticker_count=15`
- `candidate_ticker_count=15`
- `runtime_row_count=70`
- `runtime_ticker_count=11`
- `covered_target_ticker_count=11`
- `uncovered_target_ticker_count=4`
- `unclassified_rejection_count=0`

Metric 明细：

| metric_family | rows | 说明 |
| --- | ---: | --- |
| `segment_revenue` | 26 | DART / HKEX / EU annual report 等披露的业务或 segment 收入 |
| `product_revenue` | 18 | CNINFO / TW MOPS 等披露的产品或产品区域收入 |
| `product_gross_margin` | 8 | CNINFO 产品毛利率表 |
| `segment_sales` | 6 | JP integrated report segment sales |
| `shipments` | 9 | TW MOPS / Quanta notebook shipments |
| `shipment_value` | 1 | DISCO shipment value |
| `backlog_or_orders` | 2 | LG Energy Solution 官方新闻稿中的 ESS backlog 与 46-Series new contracts |

Parser 明细：

| parser | rows |
| --- | ---: |
| `kr_dart_major_product_sales_table_parser_v0_1` | 12 |
| `kr_dart_semiconductor_business_segment_table_parser_v0_1` | 2 |
| `hkex_operating_segment_external_revenue_table_parser_v0_1` | 2 |
| `szse_cninfo_product_revenue_table_parser_v0_1` | 8 |
| `szse_cninfo_product_revenue_cost_margin_table_parser_v0_1` | 8 |
| `tw_mops_product_sales_volume_value_table_parser_v0_1` | 16 |
| `tw_mops_quanta_notebook_shipment_sentence_parser_v0_1` | 3 |
| `eu_annual_report_segment_revenue_table_parser_v0_1` | 10 |
| `jp_ir_integrated_report_segment_sales_panel_parser_v0_1` | 4 |
| `jp_ir_integrated_report_advantest_segment_sales_panel_parser_v0_1` | 2 |
| `jp_ir_disco_shipment_value_sentence_parser_v0_1` | 1 |
| `official_company_news_lges_product_order_backlog_parser_v0_1` | 2 |

### 剩余 4 家非美 Product-KPI 缺口

| ticker | 当前结论 | 原因 |
| --- | --- | --- |
| `2308.TW` Delta Electronics | 不提权 | 当前公开披露能看到产品/业务 mix percentage，但没有直接 product/segment exact value row；不能用 total revenue x mix 反推 |
| `2317.TW` Hon Hai Precision | 不提权 | 公司披露的是产品类别占比和总收入，缺直接产品类别收入/出货 exact row；不能用百分比推导 |
| `6723.T` Renesas | 不提权 | 官方结果页和披露有业务方向性描述，但没有 Automotive / Industrial / Infrastructure / IoT 等 exact segment/product amount |
| `8035.T` Tokyo Electron | 不提权 | 当前 integrated report 的产品类别 net sales current-year 行为 dash；旧年度产品表被 stale document gate 拒绝 |

这些剩余项当前是公开披露边界或需要更具体 IR table / local filing 深挖，不是 parser 未运行。若后续继续深挖，只能在找到公司正式披露的 direct exact row 后提权；不能用 mix、方向性描述、旧年度表或市场 proxy 代替。

### 下游接入与口径修复

本轮同时修复了两个下游误差：

1. `build_exact_slot_coverage_matrix.py` 已把 `non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl` 纳入 exact-slot observed rows。
2. `build_product_kpi_deep_gap_diagnostic.py` 现在以实际 runtime rows 为优先状态：
   - 有 product-family runtime row -> `product_kpi_exact_ready`
   - 只有 business/segment runtime row -> `business_segment_metric_ready`
   - 保留 `source_product_kpi_closeout_status` 用于审计旧 closeout 状态

最新 diagnostic / docket 状态：

- `product_family_exact_ready_ticker_count=133`
- `business_or_segment_exact_ready_ticker_count=83`
- `product_or_business_kpi_ready_ticker_count=216`
- `product_kpi_exact_gap=377`
- `non_us_local_or_ir_parser_required=4`
- `company_gap_docket.product_kpi_gap_docket_count=377`

这里 product-family ready 数低于 Step 1/2 的旧口径，是因为 diagnostic 现在按 runtime row 的 `product_node_type` 重新归类，部分旧 closeout 中的 product-ready 被更正为 business/segment-ready。总的 product-or-business KPI 可用公司数提升到 `216`，但真正产品族 exact 与业务 segment exact 的边界更清楚。

### 验收

- `python -m pytest tests\test_non_us_product_kpi_local_disclosure_runtime_rows.py -q` -> `11 passed`
- `python -m pytest tests\test_product_kpi_deep_gap_diagnostic.py tests\test_non_us_product_kpi_local_disclosure_runtime_rows.py -q` -> `13 passed`
- `python scripts\data_expansion\build_non_us_product_kpi_local_disclosure_runtime_rows.py --download-official-reports --strict` -> `status=pass`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`
- `python -m pytest tests\test_non_us_product_kpi_local_disclosure_runtime_rows.py tests\test_non_us_l1_financial_statement_metric_runtime_rows.py tests\test_exact_slot_contracts.py tests\test_product_kpi_deep_gap_diagnostic.py tests\test_company_gap_docket.py -q` -> `30 passed`

## 2026-06-19 R14 Step 4 Channel / Distributor Family Adapter

第 4 步已把 `channel_offer_distributor_marketplace_adapter` 从只依赖 CDW 的窄路径，扩成 official-domain / issuer-linked 的 family-scoped channel / distributor / store locator 路径。这里新增的是 L3 bounded context row，不是价格、库存或 sell-through exact authority。

### Runtime 产物

- rows: `data/manifests/family_channel_distributor_context_rows_v0_1.jsonl`
- attempts: `data/manifests/family_channel_distributor_attempts_v0_1.jsonl`
- summary: `data/manifests/family_channel_distributor_context_summary_v0_1.json`
- report: `docs/internal/vnext_20260610/vertical_lanes/family_channel_distributor_context.zh-CN.md`

### 新增 exact-slot contract

`src/sec_agent/exact_slot_contracts.py` 新增 `public_channel_distributor_locator` slot：

- `requirement_id=channel_offer_proxy`
- `source_id=channel_distributor_locator`
- `authority_scope=public_channel_or_distributor_presence_snapshot`
- 必需字段：`ticker/source_url/fact_label/channel_name/product_or_segment`
- 必需绑定：issuer-bound
- 禁止提权：`price`、`ASP`、`channel_inventory`、`sell_through`、`sales_volume`、`revenue`、`market_share`

因此这批 rows 只能回答“公司公开披露或官方站点存在何种 channel / distributor / dealer / store locator”，不能回答渠道价格、库存、销量、份额或需求。

### Gate 结果

最新 real run：

- `target_ticker_count=62`
- `row_count=30`
- `new_or_existing_success_ticker_count=19`
- `unmaterialized_ticker_count=43`
- `attempt_count=700`

Locator 类型：

| locator_type | rows |
| --- | ---: |
| `store_locator` | 10 |
| `distributor_locator` | 8 |
| `official_store_or_shop` | 5 |
| `dealer_locator` | 4 |
| `official_channel_link` | 3 |

已 materialize ticker：

`6752.T`, `CAT`, `COST`, `DE`, `DLTR`, `EMR`, `IFX.DE`, `INTC`, `LOW`, `LULU`, `ROST`, `SMCI`, `TGT`, `TJX`, `TSCO`, `ULTA`, `WMT`, `WOLF`, `XPEV`。

### 质量修复

本轮修复了一个重要 reproducibility 问题：builder 不能只以当前 `company_gap_docket_v0_1.jsonl` 为目标源，因为已经修复的 ticker 会从 docket 消失，导致 rerun 时 `--replace-output` 把已 materialize rows 清空。现在 `build_family_channel_distributor_context_rows.py` 同时读取 `company_public_source_coverage_matrix_v0_1.jsonl` 作为 channel requirement 目标全集，确保 rerun 可复现。

同时新增以下防误提权 gate：

- official domain / issuer-linked domain 绑定；
- blocked / captcha / client challenge / 404 / redirect-only 页面拒绝；
- 仅 URL 路径命中 `/distributors` 不提权，必须正文或 title 也有 locator / channel 语义；
- attempts 写入 `source_id=channel_distributor_locator`，让 closeout 能区分“只跑 CDW”与“已跑 official locator ladder”。

### 最新矩阵状态

`build_exact_slot_coverage_matrix.py` 已纳入 `family_channel_distributor_context_rows_v0_1.jsonl`：

- `exact_by_source_id.channel_distributor_locator=30`
- `exact_by_slot_kind.public_channel_distributor_locator=30`
- `channel_offer_proxy.ready_count=26`
- `channel_offer_proxy.gap_count=36`
- `exact_slot_gap_count=186`

剩余 `36` 家 channel gap 不是静默漏跑，`build_exact_slot_gap_closeout_ledger.py` 已全部写成：

- `closeout_reason=official_channel_distributor_locator_no_bound_channel_row`

剩余 ticker：

`1211.HK`, `AMD`, `AZO`, `BBY`, `CASY`, `CMI`, `CRDO`, `DECK`, `DG`, `DIOD`, `DOV`, `FTV`, `GE`, `GPC`, `HD`, `IEX`, `ITW`, `KMB`, `KR`, `KVUE`, `LCID`, `LI`, `MNST`, `MPWR`, `MRVL`, `NIO`, `ORLY`, `PH`, `QCOM`, `RIVN`, `ROK`, `SNA`, `SWK`, `TPR`, `TSLA`, `WAB`。

这些剩余项后续若继续深挖，需要 source-specific Playwright / official store / Digi-Key / Mouser / Arrow / Amazon / JD / distributor locator 适配器；在没有 issuer/product-family bound row 前不能写成 channel offer evidence。

### 验收

- `python -m py_compile scripts\data_expansion\build_family_channel_distributor_context_rows.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> pass
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --replace-output --strict --workers 12 --timeout-s 8 --max-seeds-per-ticker 12 --max-links-per-seed 6 --max-rows-per-ticker 2` -> `status=pass`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`
- `python -m pytest tests\test_family_channel_distributor_context_rows.py tests\test_exact_slot_contracts.py tests\test_exact_slot_gap_closeout_ledger.py tests\test_company_gap_docket.py tests\test_product_kpi_deep_gap_diagnostic.py -q` -> `25 passed`

## 2026-06-19 R14 Step 5 Developer Official Seed Locator

第 5 步已把 `developer_ecosystem_official_seed_locator` 从“宽泛搜索 GitHub/npm/PyPI/HuggingFace”收紧为 official-seed-first 路径：只有公司官网、官方 docs/dev pages、官方 product surface，或 GitHub profile 明确绑定公司官方域名时，才允许把 repo/package seed 交给 developer ecosystem parser。没有 official seed 的公司继续暴露 resolver gap，不能 blind search 提权。

### Runtime 产物

- seed rows: `data/manifests/developer_ecosystem_official_seed_locator_v0_1.jsonl`
- attempts: `data/manifests/developer_ecosystem_official_seed_locator_attempts_v0_1.jsonl`
- seed summary: `data/manifests/developer_ecosystem_official_seed_locator_summary_v0_1.json`
- parser rows: `data/manifests/developer_ecosystem_context_rows_v0_1.jsonl`
- parser attempts: `data/manifests/developer_ecosystem_attempts_v0_1.jsonl`
- parser summary: `data/manifests/developer_ecosystem_context_summary_v0_1.json`
- report: `docs/internal/vnext_20260610/vertical_lanes/developer_official_seed_locator.zh-CN.md`

### Locator Gate

最新 official seed locator real run：

- `target_ticker_count=45`
- `seeded_ticker_count=22`
- `seed_row_count=22`
- `seed_url_count=62`
- `unseeded_ticker_count=23`
- `unclassified_target_count=0`
- `attempt_count=751`

已通过 official seed 的 ticker：

`6723.T`, `ANET`, `APP`, `AVGO`, `CIEN`, `CRDO`, `CTSH`, `FICO`, `FTNT`, `GDDY`, `GEN`, `IFX.DE`, `KEYS`, `MSI`, `ON`, `PTC`, `S`, `STX`, `SWKS`, `TEL`, `TOST`, `VRSN`。

官方 seed 发现方式：

- `github_org_profile_verified_official_domain=22`

也就是说当前提权条件不是“GitHub 搜到项目”，而是“GitHub org/profile 或官网页面能绑定 issuer 官方域名”。本轮同时修复了以下误提权风险：

- 拒绝 `github.com/orgs/...`、`github.com/solutions/...`、`github.com/topics/...` 等非 repo / 非 official seed 路径；
- 拒绝 `tree/blob` 子路径作为 seed；
- 移除过宽的 alias + domain-stem profile 判定，避免短账户名或第三方项目被误认为公司官方 seed；
- official product surface URL 先于通用官网路径扫描，避免小预算时错过已知 developer/doc 页面。

### Parser Gate

`build_developer_ecosystem_context_rows.py` 已接入 located seed rows，并重新 materialize：

- `context_row_count=118`
- `parser_backed_row_count=118`
- `ticker_count=62`
- `provider_counts.github=110`
- `provider_counts.npm=4`
- `provider_counts.pypi=3`
- `provider_counts.huggingface=1`
- `developer_ecosystem_proxy_requirement.status=pass`
- `entity_bound_row_count=118`
- `product_mentioned_in_snapshot=118`
- `issuer_mentioned_in_snapshot=118`

这批 rows 是 L3 developer ecosystem proxy，只能支撑“官方开发者生态、SDK、代码样例、package/repo 存在”的方向性产品/技术背景，不得写成收入、销量、市场份额、客户采用率、moat 或商业成功。

### 最新矩阵状态

`build_exact_slot_coverage_matrix.py` 已纳入 located developer ecosystem parser rows：

- `developer_ecosystem_proxy.ready_count=62`
- `developer_ecosystem_proxy.gap_count=14`
- `exact_by_source_id.developer_ecosystem_github_npm_pypi_huggingface=113`
- `exact_slot_gap_count=171`
- `all_required_exact_ready=458`

剩余 `14` 家 developer gap：

`APH`, `CDNS`, `CDW`, `COHR`, `DIOD`, `FN`, `GLW`, `IT`, `LITE`, `MTSI`, `Q`, `RMBS`, `ROP`, `WOLF`。

这些不是静默漏跑：当前 official seed locator 没找到可验证的公司官方 docs/repo/package seed，或官方 profile/domain 绑定不足。后续若继续深挖，需要从公司官网 developer/docs/product pages、官方 package metadata、或 token-authenticated GitHub API 重新验证 issuer/product binding；不能用第三方 repo、宽泛关键词搜索或非官方镜像替代。

### Closeout 修复

本轮刷新了旧 closeout 文件的 stale 统计，并新增回归测试，确保只有当前 `exact_slot_gap_ledger_v0_1.jsonl` 中的 ticker/requirement 才能生成 closeout row。刷新后：

- `exact_gap_count=171`
- `closeout_row_count=171`
- `developer_ecosystem_proxy=14`
- `unclassified_closeout_count=0`
- 旧的 `developer_ecosystem_materialized_row_failed_exact_slot_contract=15` 不再出现在当前 closeout 中。

最新 company gap docket：

- `source_role_gap_docket_count=171`
- `product_kpi_gap_docket_count=377`
- `docket_count=548`
- `developer_ecosystem_official_seed_locator.company_count=14`
- `unclassified_docket_count=0`

### 验收

- `python -m py_compile scripts\data_expansion\build_developer_official_seed_locator.py scripts\data_expansion\build_developer_ecosystem_context_rows.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py` -> pass
- `python scripts\data_expansion\build_developer_official_seed_locator.py --strict --workers 32 --timeout-s 5 --max-source-pages-per-ticker 10 --max-seeds-per-ticker 3 --max-repos-per-org 12` -> `status=pass`
- `python scripts\data_expansion\build_developer_ecosystem_context_rows.py --replace-output --strict --timeout-s 10 --fetch-retries 1 --max-rows-per-probe 4` -> `status=pass`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`
- `python -m pytest tests\test_developer_official_seed_locator.py tests\test_developer_ecosystem_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py -q` -> `16 passed`

## 2026-06-19 R14 Step 6 Public Order / Regulated / Supply-Chain Repair

第 6 步把 `public_order_proxy`、`regulated_product_context`、`auto_product_identity_context` 和 `supply_chain_official_relationship` 从混合缺口拆成 source-specific rows / attempts / jurisdiction closeout。重点不是用弱 proxy 填洞，而是把能从公开官方源绑定的关系物化，不能绑定的写清楚 source boundary。

### Regulated / Auto 修复

`build_targeted_regulated_auto_official_api_context_rows.py` 新增：

- openFDA device 510(k) parser：覆盖 `WST` 以及 DHR/MTD/RVTY 等 device applicant alias；
- NHTSA manufacturer fallback：覆盖 `PCAR` make/manufacturer identity；
- route applicability 修正：`COR/HSIC/MCK/HCA` 等 healthcare distributor/provider 不再冒用 clinical/openFDA regulated-product route；`WST` 切到 medtech device route。

真实运行结果：

- `required_ticker_count=72`
- `success_ticker_count=69`
- `row_count=151`
- remaining: `IDXX`, `ZTS`, `XPEV`

剩余边界：

- `IDXX` / `ZTS`：ClinicalTrials/openFDA 当前无 sponsor/collaborator/applicant-bound rows；animal-health/veterinary 需要后续专门监管路径，不能用人用药/普通 FDA route 硬套。
- `XPEV`：NHTSA vPIC make/manufacturer route 没有可绑定 exact make/model row；当前写为 `not_applicable_or_source_gap`。

### Public Order 修复

`build_broad_public_contract_award_context_rows.py` 修复 recipient matcher：

- 旧逻辑允许任意 substring，存在 `Oklo` 命中 `TOKLO TECHNOLOGIES`、短 alias 污染等风险；
- 新逻辑改成 token-sequence match，并保留逐 alias 查询；
- `MCK` timeout 后用更长 timeout 单独 rerun，成功 materialize。

同时 `build_exact_slot_gap_closeout_ledger.py` 把 public order closeout 按司法辖区拆开：

- US issuer：`usaspending_no_recipient_bound_award_or_api_fetch_gap`；
- HK/TW/JP/FPI/ADR：`*_public_order_local_tender_adapter_required`；
- 这类 non-US/local gap 不再伪装成 USAspending 缺口，后续必须接 local tender / regulator award / exchange filing / official contract disclosure adapter。

最新 public-order exact-slot 状态：

- `public_order_proxy.ready_count=106`
- `public_order_proxy.gap_count=53`
- 其中 `33` 条为 USAspending 尝试后无 recipient-bound award row；
- `20` 条为 HK/TW/JP/FPI/ADR/local tender adapter required。

### Supply-Chain 官方关系修复

新增 `build_targeted_supply_chain_official_relationship_rows.py`：

- 只接受 issuer alias 与 counterparty alias 同时出现在官方页面；
- 输出 `supplier_customer_official_news` rows；
- rows 只支持 `official_supply_chain_relationship_context` / `verification_lead`；
- 明确禁止 shipment、allocation、order volume、revenue、market share、backlog、share inference。

真实 materialized ticker：

`2317.TW`, `2382.TW`, `3231.TW`, `8035.T`, `AMKR`, `ASML`, `CAMT`, `FORM`, `SMCI`。

对应官方源包括 NVIDIA / ASML / Amkor / Camtek / FormFactor / Tokyo Electron 官方新闻或产品/认证页面。`AMKR` 从不稳定的 IR endpoint 改为 Amkor 官方 Lightmatter partnership 页面；`SMCI` 从 Supermicro 403 press release 改为 NVIDIA 官方新闻稿。

最新 supply-chain exact-slot 状态：

- `supplier_customer_official_news=9`
- `supply_chain_official_relationship.ready_count=20`
- `supply_chain_official_relationship.gap_count=1`

唯一剩余：

- `AEHR`：当前公开材料多为 unnamed customer / unnamed AI accelerator / customer class，不能绑定 named counterparty；USAspending route 也无 recipient-bound award row，因此保留 source-exhausted gap，不能用 unnamed customer 代替官方供应链关系。

### 最新矩阵 / Docket

刷新顺序必须是：

1. `build_product_family_source_route_plan.py`
2. `build_company_public_source_coverage_matrix.py`
3. `build_exact_slot_coverage_matrix.py`
4. `build_exact_slot_gap_closeout_ledger.py --strict`
5. `build_product_kpi_deep_gap_diagnostic.py --strict`
6. `build_company_gap_docket.py --strict`

注意：第 4 和第 6 不能并行，否则 docket 可能读到旧 closeout 文件。

最新结果：

- `exact_slot_gap_count=195`
- `all_required_exact_ready_company_count=445`
- `partial_exact_ready_company_count=158`
- `no_exact_ready_company_count=0`
- `source_role_gap_docket_count=195`
- `product_kpi_gap_docket_count=377`
- `docket_count=572`
- `unclassified_closeout_count=0`
- `unclassified_docket_count=0`

剩余 source-role gap：

| requirement | gap | 当前原因 |
| --- | ---: | --- |
| `public_order_proxy` | 53 | `33` 条 USAspending 无 recipient-bound award；`20` 条需要 HK/TW/JP/FPI/ADR/local tender adapter |
| `hiring_capacity_proxy` | 44 | public ATS / official careers 无 issuer-bound job rows 或站点需 site-specific parser |
| `channel_offer_proxy` | 36 | CDW + official locator 后仍无 issuer/product-bound SKU/channel row |
| `technology_research_proxy` | 23 | OpenAlex 无 issuer-topic row，1 条 PatentsView seed 未 materialize |
| `developer_ecosystem_proxy` | 15 | 缺 verified official docs/repo/package seed，不能 blind search |
| `app_rank_store_proxy` / `platform_review_proxy` | 20 | iTunes/App Store 无 seller-bound listing/review |
| `regulated_product_context` | 2 | IDXX/ZTS 需要 animal-health/veterinary route 或暴露监管公开源边界 |
| `auto_product_identity_context` | 1 | XPEV NHTSA make/model route 无 exact row 或不适用 |
| `supply_chain_official_relationship` | 1 | AEHR 无 named official counterparty-bound public relationship row |

### 验收

- `python -m py_compile scripts\data_expansion\build_targeted_supply_chain_official_relationship_rows.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py` -> pass
- `python scripts\data_expansion\build_targeted_supply_chain_official_relationship_rows.py --replace-output --strict --timeout-s 20 --sleep-s 0.05 --tickers 2317.TW 2382.TW 3231.TW 8035.T AMKR ASML CAMT FORM SMCI` -> `row_count=9`, `attempt_status_counts.materialized=9`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`
- `python -m pytest tests\test_targeted_regulated_auto_official_api_context_rows.py tests\test_broad_public_contract_award_context_rows.py tests\test_targeted_supply_chain_official_relationship_rows.py tests\test_exact_slot_contracts.py tests\test_exact_slot_gap_closeout_ledger.py tests\test_company_gap_docket.py tests\test_product_kpi_deep_gap_diagnostic.py tests\test_product_family_source_routes.py tests\test_company_public_source_coverage_matrix.py -q` -> `39 passed`

## 2026-06-20 R14 Continuation: Regulated / Channel / Developer / Technology Repair

本轮继续按“能用公开、免费、可绑定 exact slot 的数据就接入；不能绑定的写清楚 source boundary”的原则补 source-role gap。结果不是把 L3 proxy 当成销售证据，而是把可验证的官方/公开源转成 bounded runtime rows，并同步 `exact_slot_coverage_matrix`、`exact_slot_gap_closeout` 和 `company_gap_docket`。

### Animal-Health Regulated Route

`build_targeted_regulated_auto_official_api_context_rows.py` 增加 FDA Animal Drugs @ FDA `advancedSearch` sponsor/product parser：

- `ZTS`: `Apoquel®`, `Simparica TRIO®` 等产品可绑定 Zoetis sponsor/application rows；
- `IDXX`: `IDEXX Pharmaceuticals, Inc.` sponsor row 可绑定 animal-drug application context；
- rows 使用 `source_id=fda_animal_drugs_api`，只支持 `regulated_product_context` / `verification_lead`；
- 明确禁止销量、处方量、使用率、市占率、安全事件发生率、收入推断。

验收后：

- `fda_animal_drugs_api=3`
- `regulated_product_context.gap_count=0`
- `XPEV` 仍保留 `auto_product_identity_context=1`，原因是当前 NHTSA make/model route 没有可绑定 exact row 或不适用。

### Family Channel / Distributor Locator Repair

`build_family_channel_distributor_context_rows.py` 增加两类修复：

- verified official / brand locator seeds：Best Buy store directory、Kroger store search、O'Reilly locations、Lucid locations、Snap-on StoreLocator、Fluke where-to-buy、Stanley where-to-buy、Tapestry brand stores、Rivian spaces、Rockwell partner locator、AMD authorized distributor 等；
- 同 URL raw-cache guard：如果 live fetch 遇到 403 / challenge / empty page，只允许复用同 URL 已存在的非阻挡 raw；不会把挑战页写成 evidence。

最新真实运行：

- `family_channel_distributor_context_rows_v0_1.row_count=62`
- `new_or_existing_success_ticker_count=35`
- `channel_offer_proxy.ready_count=40`
- `channel_offer_proxy.gap_count=22`

这些 rows 仍只是 `channel_distributor_locator_context`：可证明公开渠道/门店/经销商入口存在，不能证明价格、ASP、库存、sell-through、收入、销量、需求或市场份额。

### Developer Ecosystem Repair

对剩余 developer gap 做官方 seed locator 探测后，只发现 `NOW` 能通过 ServiceNow official GitHub profile 绑定到 `servicenow.com`，并 materialize `ServiceNow/BrowserGym`, `ServiceNow/ServiceNowDocs`, `ServiceNow/eva`, `ServiceNow/Fast-LLM`, `ServiceNow/PipelineRL`。

最新状态：

- `developer_ecosystem_context_rows_v0_1.context_row_count=123`
- `ticker_count=63`
- `developer_ecosystem_proxy.ready_count=63`
- `developer_ecosystem_proxy.gap_count=14`

剩余 `APH/CDNS/CDW/COHR/DIOD/FN/GLW/IT/LITE/MTSI/Q/RMBS/ROP/WOLF` 等没有 verified official docs/repo/package seed，不能用 blind GitHub search 提权。

### Technology Research Proxy Repair

用 `FamilySourceRoutePlan` 重跑 OpenAlex issuer-topic probes，`per-page=15` 后新增 `CDNS`, `LAC`, `MSFT`, `NOW`, `SNPS`, `TEL` 的 issuer-topic-bound research proxy rows。

最新状态：

- `v1_openalex_technology_research_context_rows_v0_1.context_row_count=25`
- `technology_research_proxy.ready_count=61`
- `technology_research_proxy.gap_count=17`

剩余 OpenAlex gap 的真实原因是 API 有返回但无法通过 issuer-topic binding，或需要 PatentsView/assignee resolver。它们不能作为产品发布、销量、收入、市占率或 durable moat 证明。

### Product-KPI Verifier复核

本轮复核了 `product_kpi_source_specific_verifier_v0_1` 的 `21,822` 个 strict candidates：

- `business_segment_metric=7,468`
- `percentage_or_change=5,608`
- `operating_metric_defer_step2=2,232`
- `non_product_or_total=2,035`
- `region_only=1,653`
- `business_segment_mixed_table_needs_column_group=1,454`
- `sentence_relation_insufficient=988`
- `period_or_version_conflict=384`
- `promotable_product_category_or_product_line_metric=0`

结论：当前 Product-KPI exact gap 不是简单漏跑。大量候选是 segment / geography / percentage / mixed financial table / sentence relation insufficient。下一步若继续提升 Product-KPI，必须修 product taxonomy 与 table-column-group verifier，不能把 business segment 或 region-only rows 冒充 product exact KPI。

### Latest Matrix

最新刷新顺序：

1. `python scripts\data_expansion\build_exact_slot_coverage_matrix.py`
2. `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict`
3. `python scripts\data_expansion\build_company_gap_docket.py --strict`

最新结果：

- `exact_slot_gap_count=136`
- `all_required_exact_ready_company_count=484`
- `partial_exact_ready_company_count=119`
- `no_exact_ready_company_count=0`
- `source_role_gap_docket_count=136`
- `product_kpi_gap_docket_count=377`
- `docket_count=513`
- `unique_gap_company_count=412`
- `unclassified_closeout_count=0`
- `unclassified_docket_count=0`

剩余 source-role gap：

| requirement | gap | 当前原因 |
| --- | ---: | --- |
| `hiring_capacity_proxy` | 41 | public ATS / official careers 无 issuer-bound job rows 或站点需 site-specific parser；BILL/ESTC 已通过 Greenhouse API 补齐 |
| `public_order_proxy` | 36 | `16` 条 USAspending 无 recipient-bound award；`20` 条 HK/TW/JP/FPI/ADR/local tender adapter required |
| `channel_offer_proxy` | 19 | 官方 locator / brand store / channel route 后仍无 bound row，多数为官网阻挡、品牌/经销商路径未绑定或需 marketplace SKU parser |
| `technology_research_proxy` | 17 | OpenAlex 无 issuer-topic-bound row 或需要 PatentsView assignee resolver |
| `developer_ecosystem_proxy` | 13 | 缺 verified official docs/repo/package seed，不能 blind search；CDNS/ServiceNow 已补 |
| `platform_review_proxy` | 4 | iTunes/App Store 无 seller-bound listing/review；HST 已补 |
| `app_rank_store_proxy` | 4 | iTunes/App Store 无 seller-bound app/platform listing；HST 已补 |
| `supply_chain_official_relationship` | 1 | AEHR 无 named official counterparty-bound public relationship row |
| `auto_product_identity_context` | 1 | XPEV NHTSA make/model route 无 exact row 或不适用 |

### 2026-06-20 R14 Continuation

本轮只提升真实 parser-backed rows，未把 URL seed、blocked page、blind search、segment/geography/percentage 候选冒充 exact slot：

- Developer ecosystem：新增 CDNS verified official seed（Cadence / Fidelity Pointwise GitHub repos），`developer_ecosystem_proxy.gap_count=13`。
- App / platform：新增 HST `Host Hotels & Resorts, Inc.` seller-bound iTunes listing，`app_rank_store_proxy.gap_count=4`、`platform_review_proxy.gap_count=4`。
- Hiring：新增 `ATS_TOKEN_OVERRIDES`，BILL 使用 Greenhouse `billcom`，ESTC 使用 Greenhouse `elastic`；`hiring_capacity_proxy.gap_count=41`。
- Public order：新增 verified recipient aliases，GE / J / LEU / FORM / INTU materialize USAspending public-award rows；`public_order_proxy.gap_count=36`。HUBS 探测仍无稳定 recipient-bound row，DOV/AEHR/AMKR/IOT 等相似名称结果被拒绝。
- Channel：对 AZO/CASY/DG/HD/GPC/DECK/PH/DIOD/MRVL 等官方 locator 进行 browser-like request probe，主要返回 Akamai / DataDome / Cloudflare / Access Denied 403；不把 blocked page 或仅 URL existence 提权。
- Product-KPI：复核 `21,822` 个 verifier candidates 仍无 strict promotable product/category/product-line metric。剩余主要是 geography / business segment / percentage-change / mixed table / sentence relation insufficient，不做弱提权。

### 2026-06-20 Sequential Repair Step 1: Careers Site-Specific Adapters

验收口径：只有 official ATS / official careers API 返回 `title + location` 的 issuer-bound public job row 才进入 `hiring_capacity_proxy`；普通 careers landing page、blocked page、blind token search、issuer mismatch 均不提权。

本步修复：

- `build_broad_official_careers_context_rows.py` 增加 verified Workday direct ATS URLs：
  - `ADSK -> autodesk.wd1.myworkdayjobs.com/Ext`
  - `CRM -> salesforce.wd12.myworkdayjobs.com/External_Career_Site`
  - `MSI -> motorolasolutions.wd5.myworkdayjobs.com/Careers`
  - `OTIS -> otis.wd5.myworkdayjobs.com/REC_Ext_Gateway`
  - `TMUS -> tmobile.wd1.myworkdayjobs.com/External`
- 新增 Ashby public job-board parser，但 live probe 中 `PWR -> quanta` 被判定为非 Quanta Services issuer mismatch，不写入 direct URL，也不 materialize。
- 补充 unit tests，验证 direct ATS URL 优先级和 Ashby JSON parser 可进入 `hiring_capacity_proxy` exact slot。

真实运行结果：

- targeted live materialization 对 `ADSK/CRM/MSI/OTIS/TMUS` 写出 Workday rows。
- `hiring_capacity_proxy.gap_count` 从 `41` 降至 `36`。
- `exact_slot_gap_count` 从 `136` 降至 `131`。
- `all_required_exact_ready_company_count` 从 `484` 升至 `488`。
- `source_role_gap_docket_count` 从 `136` 降至 `131`。
- `docket_count` 从 `513` 降至 `508`。

剩余 `hiring_capacity_proxy=36` 的公司仍需更细 parser 或公开源边界审计：`ADP/AKAM/CHTR/CMG/CRWD/CSCO/CTSH/DRI/EBAY/EME/ETN/FFIV/FIX/FTNT/GOOGL/HON/HUBS/IBM/INTU/LII/MELI/MSFT/ORCL/PCOR/PWR/ROP/S/SBUX/SE/SHOP/T/TEAM/TT/VRT/VZ/YUM`。

注意：`build_exact_slot_gap_closeout_ledger.py` 必须先于 `build_company_gap_docket.py` 顺序运行；并行运行会让 docket 读取旧 closeout，造成已修复 tickers 仍留在 docket。

### Verification

- `python -m py_compile scripts\data_expansion\build_family_channel_distributor_context_rows.py`
- `python -m pytest tests\test_family_channel_distributor_context_rows.py tests\test_exact_slot_contracts.py -q` -> `20 passed`
- `python -m py_compile scripts\data_expansion\build_developer_official_seed_locator.py scripts\data_expansion\build_developer_ecosystem_context_rows.py`
- `python -m pytest tests\test_developer_official_seed_locator.py tests\test_developer_ecosystem_context_rows.py -q` -> `11 passed`
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --strict --workers 12 --timeout-s 12 --max-seeds-per-ticker 12 --max-links-per-seed 6 --max-rows-per-ticker 2` -> `row_count=62`
- `python scripts\data_expansion\build_developer_ecosystem_context_rows.py --tickers NOW --located-seed-path data\manifests\_tmp_developer_seed_probe_rows.jsonl --timeout-s 12 --fetch-retries 1 --max-rows-per-probe 4 --strict` -> `ticker_count=63`
- `python scripts\data_expansion\build_v1_openalex_technology_research_context_rows.py --from-family-route-plan ... --per-page 15 --max-rows-per-company 3 --strict` -> `technology rows=25`
- `python -m pytest tests\test_broad_official_careers_context_rows.py -q` -> `3 passed`
- `python -m py_compile scripts\data_expansion\build_broad_official_careers_context_rows.py tests\test_broad_official_careers_context_rows.py` -> pass
- `python scripts\data_expansion\build_broad_official_careers_context_rows.py --tickers ADSK CRM MSI OTIS TMUS --workers 8 --max-career-pages 1 --max-jobs-per-company 2 --timeout-s 10 --strict` -> Workday rows materialized
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`

## 2026-06-20 Sequential Repair Step 2: Channel Locator Adapters

验收口径：只有 official / issuer-linked locator、official store、verified distributor 页面真实返回并被 parser 解析为 `channel_distributor_locator` row，才能降低 `channel_offer_proxy`。搜索结果摘要、URL 存在、blocked page、403/567 challenge、stale 404 cache、issuer/domain mismatch 均不得提权。

本步修复：

- `build_family_channel_distributor_context_rows.py` 增加 BYD / Li Auto / ITW-MillerWelds / Credo verified manual seeds 和 domain overrides。
- 增加 Arrow trusted distributor seeds，用页面正文 issuer binding + distributor/channel context gate 物化 `DIOD` / `MPWR`。
- 增加 `DOV` / `IEX` / `MRVL` / `PH` / `WAB` 官方 locator / sales office / parts-service seeds，并扩大 manual verified page parse window。
- 新增 `--browser-fallback`：仅 manual verified seed 静态 HTML 无 row 时调用本机 Chrome/Edge Playwright 渲染，attempt ledger 标记 `live_browser_fetch`；用于 Li Auto 这类客户端渲染官方页面。
- 加强 stale output filter，禁止 404 / access-denied cached row 留在 output rows。

真实运行结果：

- `channel_offer_proxy.gap_count` 从本阶段初始 `19` 降至 `8`。
- `channel_offer_proxy.ready_count=54`。
- `family_channel_distributor_context_rows_v0_1.row_count=82`。
- `exact_slot_gap_count=120`。
- `all_required_exact_ready_company_count=494`。
- `source_role_gap_docket_count=120`。
- `docket_count=497`。

剩余 `channel_offer_proxy=8`：

`AZO`、`CASY`、`DECK`、`DG`、`GPC`、`HD`、`MNST`、`NIO`。

当前边界：

- `AZO/CASY/DG/HD/GPC/DECK/MNST`：官方 locator / store route 在 urllib 与系统 Chrome Playwright 下仍返回 Akamai / Cloudflare / DataDome / Access Denied / request rejected 等防护响应；不能用搜索摘要或 URL 存在提权。
- `NIO`：official location route 返回非标准 `567` / rendering protection；当前 runtime 没有稳定可复现 parser-backed row。
- 这些剩余项需要 site-specific API、稳定 browser materialization、或官方可抓取替代页面；在此之前只能保留 `official_channel_distributor_locator_no_bound_channel_row`。

验收：

- `python -m pytest tests\test_family_channel_distributor_context_rows.py -q` -> `16 passed`
- `python -m py_compile scripts\data_expansion\build_family_channel_distributor_context_rows.py tests\test_family_channel_distributor_context_rows.py` -> pass
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --tickers 1211.HK CRDO ITW LI --workers 4 --timeout-s 20 --max-seeds-per-ticker 4 --max-links-per-seed 6 --max-rows-per-ticker 2 --strict` -> `1211.HK` / `ITW` materialized
- `python scripts\data_expansion\build_family_channel_distributor_context_rows.py --tickers CRDO LI --workers 1 --timeout-s 25 --max-seeds-per-ticker 3 --max-links-per-seed 6 --max-rows-per-ticker 2 --browser-fallback --strict` -> `CRDO` / `LI` materialized
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`

## 2026-06-20 Sequential Repair Step 3: PatentsView / Assignee Technology Resolver

验收口径：只有 PatentsView / PatentSearch 返回的 assignee alias + product/topic 双绑定专利记录，才能进入 `technology_research_proxy`。专利关键词命中、URL 存在、缺 issuer assignee、缺 product/topic、API/key 不可用均不能提权；输出只能作为 L3 IP / technology activity proxy，不能支持产品发布、销量、收入、市占率或 moat 结论。

本步修复：

- 新增 `build_v1_patentsview_technology_research_context_rows.py`，按 company/product-family gap docket 生成 PatentsView PatentSearch 查询。
- parser gate 要求 assignee 绑定 issuer alias，同时 patent title/abstract/CPC snapshot 绑定产品或 family topic。
- 无 key / API 不可用时写入 `v1_patentsview_technology_research_attempts_v0_1.jsonl`，不生成 context row。
- `build_exact_slot_coverage_matrix.py` 默认 observed rows 接入 `v1_patentsview_technology_research_context_rows_v0_1.jsonl`。
- `build_exact_slot_gap_closeout_ledger.py` 默认 attempts 接入 PatentsView，并把 technology closeout 从 OpenAlex-only 拆为 OpenAlex / PatentsView 不同边界。

真实运行结果：

- 当前本地 runtime 没有 `PATENTSVIEW_API_KEY` / `USPTO_PATENTSVIEW_API_KEY`。
- `build_v1_patentsview_technology_research_context_rows.py --replace-output --strict` 写入 `17` 条 attempt，`missing_patentsview_api_key=17`，`context_row_count=0`。
- 刷新后 `technology_research_proxy.ready_count=61`，`gap_count=17`；这些 gap 的 closeout reason 已变为 `patentsview_api_key_missing_or_patentsearch_unavailable`。
- `exact_slot_gap_count=120`，`source_role_gap_docket_count=120`，`product_kpi_gap_docket_count=377`，`docket_count=497`。

剩余边界：

- PatentsView route 已落 runtime，但当前缺 key / 可用 PatentSearch API，不能把专利 URL 或关键词检索结果冒充 assignee-bound row。
- 后续如果提供 key 或切到 USPTO ODP bulk downloads，需要继续使用同一 assignee/topic gate；仍只能写 technology proxy，不得写产品收入、销量、市占率、销售或 durable moat。

验收：

- `python -m py_compile scripts\data_expansion\build_v1_patentsview_technology_research_context_rows.py tests\test_v1_patentsview_technology_research_context_rows.py scripts\data_expansion\build_exact_slot_coverage_matrix.py scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py tests\test_exact_slot_gap_closeout_ledger.py` -> pass
- `python -m pytest tests\test_v1_patentsview_technology_research_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py -q` -> `11 passed`
- `python scripts\data_expansion\build_v1_patentsview_technology_research_context_rows.py --replace-output --strict` -> `attempt_count=17` / `context_row_count=0`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`

## 2026-06-20 Sequential Repair Step 4: Public-Order / Local Tender Adapters

验收口径：只有 recipient / supplier-bound public award、tender、contract row，且具备 `award_id + award_amount + award_start_date + awarding_agency + source_url`，才能进入 `public_order_proxy`。政府门户存在、公司名模糊命中、经销商/地方实体误配、非结构化页面、无金额/日期/agency 的新闻或网页均不提权。

本步修复：

- `build_broad_public_contract_award_context_rows.py` 修复 recipient alias 去重：不再用去公司后缀后的 normalized key 吞掉后缀敏感查询字符串。
- 新增 verified recipient aliases：`ASML`, `CAMT`, `HMC`, `HUBS`, `PATH`, `PWR`, `TM`。
- row 增加 `matched_recipient_alias`，方便后续审计 recipient 是通过哪个 alias 绑定 issuer。
- 对 `TM` 加 `STRICT_RECIPIENT_ALIAS_ONLY_TICKERS`，禁止自动加入宽泛 `Toyota Motor`，清掉 `OKINAWA TOYOTA MOTOR CO.LTD.` 这类误配风险。
- 新增 `build_local_public_tender_context_rows.py`：
  - HK：官方 `digitalpolicy.gov.hk` SOA-QPS awarded service contracts CSV parser。
  - TW：PCC e-procurement official route attempt。
  - JP：JETRO procurement official route attempt。
  - 如果没有 supplier-bound award id / amount / date / agency，只写 attempt，不写 row。
- `build_exact_slot_coverage_matrix.py` 接入 `local_public_tender_context_rows_v0_1.jsonl`。
- `build_exact_slot_gap_closeout_ledger.py` 接入 `local_public_tender_attempts_v0_1.jsonl`，并把 local tender 已尝试但无结构化 award row 的情况从 `needs_local_tender_adapter` 改成 public boundary。
- `build_company_gap_docket.py` 同步把 local tender attempted gaps 标为 `attempt_backed_public_boundary_after_local_tender_attempt`。

真实运行结果：

- USAspending 全量重建：`success_ticker_count=133`，`row_count=652`。
- Local tender smoke：`target_ticker_count=7`，`attempt_count=7`，`row_count=0`；HK/TW/JP 当前公开路线没有可提权 supplier-bound award row。
- `public_order_proxy.ready_count=134`，`gap_count=25`。
- `exact_slot_gap_count=109`，`all_required_exact_ready_company_count=503`，`source_role_gap_docket_count=109`，`docket_count=486`。

新增 / 修复的 public-order rows 示例：

- `ASML -> ASML US LLC` Department of Commerce awards。
- `CAMT -> CAMTEK, INC.` Department of Defense awards。
- `HMC -> AMERICAN HONDA MOTOR CO., INC.` awards。
- `HUBS -> HUBSPOT, INC.` Department of Defense award。
- `PATH -> UIPATH INC` GSA / DoD awards。
- `PWR -> PAR ELECTRICAL CONTRACTORS, LLC` awards。
- `TM -> TOYOTA MOTOR CORPORATION` awards；宽 alias 误配已清理。
- `2308.TW -> DELTA ELECTRONICS MANUFACTURING CORP` USAspending rows。

剩余边界：

- `19` 家仍需 jurisdiction / recipient boundary audit：`AEHR`, `AMKR`, `BILL`, `CCJ`, `CRDO`, `CSIQ`, `DNN`, `DQ`, `ENLT`, `ENPH`, `JKS`, `NXT`, `OKLO`, `PCAR`, `RUN`, `SEDG`, `SHOP`, `SMR`, `UROY`。
- `6` 家 local HK/TW/JP route 已 attempt-backed：`1211.HK`, `2317.TW`, `2382.TW`, `3231.TW`, `6752.T`, `8035.T`。
- 这些 local route 只有在后续找到稳定 official local exchange / regulator / procurement API / company contract disclosure 且字段齐全时才能提权。

验收：

- `python -m pytest tests\test_broad_public_contract_award_context_rows.py -q` -> `5 passed`
- `python -m pytest tests\test_local_public_tender_context_rows.py tests\test_broad_public_contract_award_context_rows.py tests\test_exact_slot_gap_closeout_ledger.py -q` -> `16 passed`
- `python scripts\data_expansion\build_broad_public_contract_award_context_rows.py --replace-output --workers 12 --timeout-s 20 --limit 5 --strict` -> pass
- `python scripts\data_expansion\build_local_public_tender_context_rows.py --replace-output --strict` -> pass
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`

## 2026-06-20 Sequential Repair Step 5: Product-KPI Verifier Decomposition

验收口径：`Product-KPI exact slot` 只接受公司披露的 product / category / product-line 或已定义行业 operating metric exact row，且必须有 value / unit / period / product / citation。business segment、region-only、percentage/change、mixed column group、sentence-relation-insufficient、generic total / non-product rows 均不能填 Product-KPI exact slot。

本步修复：

- `build_product_kpi_deep_gap_diagnostic.py` 接入 `product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl`。
- deep diagnostic 行新增 verifier candidate count、class counts、decision counts、top reasons、dominant verifier class/reason。
- 将原来 `272` 家 strict-candidate Product-KPI gap 从单一 `parser_candidate_found_but_not_runtime_promotable` 拆成可执行类：
  - business segment only
  - business segment column-group required
  - industry operating metric required
  - percentage/change only
  - period/version conflict
  - region/geography only
  - sentence relation insufficient
  - non-product/generic total
- `build_company_gap_docket.py` 新增对应 Product-KPI cluster rule，使后续 repair 能按类分批，而不是把 `272` 家放在一个大桶里。

真实运行结果：

- `product_kpi_source_specific_verifier`: `target_ticker_count=272`，`candidate_count=21,822`，`unclassified_candidate_count=0`，`promotable_product_metric_count=0`。
- `product_kpi_deep_gap_diagnostic`: `status=pass`，`unclassified_count=0`，`product_family_exact_ready_ticker_count=133`，`business_or_segment_exact_ready_ticker_count=83`，`product_or_business_kpi_ready_ticker_count=216`。
- `company_gap_docket`: `status=pass`，`docket_count=486`，`source_role_gap_docket_count=109`，`product_kpi_gap_docket_count=377`，`cluster_count=20`，`unclassified_docket_count=0`。

Product-KPI gap 最新分布：

- `product_surface_or_taxonomy_available_no_company_kpi_candidate=101`
- `verifier_business_segment_only_candidates=107`
- `verifier_percentage_or_change_only_candidates=72`
- `verifier_operating_metric_requires_industry_slot=32`
- `verifier_business_segment_column_group_required=18`
- `verifier_region_or_geography_only_candidates=15`
- `verifier_non_product_or_total_candidates=12`
- `verifier_sentence_relation_insufficient=9`
- `verifier_period_or_version_conflict=7`
- `non_us_local_or_ir_parser_required=4`

边界：

- 本步没有降低 `product_kpi_gap_docket_count`，因为没有剩余候选通过 Product-KPI exact gate。
- 这不是未修，而是防止把 business segment / geography / percentage / sentence weak relation 冒充产品 KPI。
- 后续报告生成时，business segment 和 typed operating metric 可以进入基本面 / business mix / 行业 operating metric 分析，但不能作为“产品线收入 / 出货 / ASP / backlog”等 Product-KPI exact proof。

验收：

- `python -m py_compile scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py scripts\data_expansion\build_company_gap_docket.py tests\test_product_kpi_deep_gap_diagnostic.py tests\test_company_gap_docket.py` -> pass
- `python -m pytest tests\test_product_kpi_deep_gap_diagnostic.py tests\test_company_gap_docket.py tests\test_product_kpi_source_specific_verifier.py -q` -> `9 passed`
- `python scripts\data_expansion\build_exact_slot_coverage_matrix.py` -> validation `pass`
- `python scripts\data_expansion\build_exact_slot_gap_closeout_ledger.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_product_kpi_source_specific_verifier.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_product_kpi_deep_gap_diagnostic.py --strict` -> `status=pass`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`
