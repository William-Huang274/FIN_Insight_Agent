# 183 跨主流行业数据扩容与新披露格式接入计划

Date: 2026-05-29

## 目标

本阶段的方向不是继续围绕 AI 行业扩公司，而是把 FinSight-Agent 的数据底座扩成更接近真实美股投研覆盖面的形态。AI 产业链可以作为一个高价值用例，但不能代表全局扩容策略。

需要先做三件事：

1. 定义跨主流行业的公司扩容范围，保证每个主流行业都有多家公司、多个细分方向和可比较 peer。
2. 把公司数据的下载、manifest、parser、ledger、market snapshot、index 构建和 source gap 检查流程标准化。
3. 为新披露格式建立 source-family 处理方式，尤其是外国发行人的 `20-F` / `6-K` / `40-F`。用户口中的“20-k”在 SEC 常见披露里通常应对应 `20-F` 这类 foreign private issuer annual report；如果后续确实指其他格式，再单独补 source contract。

## 数据扩容原则

- 先在当前 full78 上做数据可得性、格式、coverage、planner 和 eval smoke。
- 主扩容不围绕单一主题行业，按行业覆盖和投研任务覆盖来选公司。
- 美国 SEC filer 优先，因为可以沿用当前 10-K、10-Q、8-K、market snapshot 和 ledger 主链路。
- `full128_us` 是跨行业 baseline，不是终局；行业深度覆盖通过 `sector_depth_packs` 分批启用。
- 外国发行人单独作为新 source-family 接入，不混进 10-K/10-Q 同口径比较。
- 每次新增公司前先跑 availability probe；缺文件、缺 8-K、缺市场估值、缺 XBRL/IFRS 字段都要写进 source gap，而不是让模型补。
- 每次新增披露格式前先做 parser canary，不能因为 HTML 能下载就声称进入主链路。

新增配置入口：

- `configs/sector_depth_packs_v0_2.yaml`
- `configs/foreign_issuer_source_family_canary_v0_2.yaml`
- `configs/industry_data_source_families_v0_2.yaml`

## 阶段 0：full78 作为格式和链路测试基线

当前 full78 用来验证现有 US filer 主链路是否稳定：

| 检查项 | 当前状态 | 下一步 |
| --- | --- | --- |
| 10-K | 233/234 | 查明缺口来源，区分真实披露缺口和 manifest 问题 |
| latest 10-Q | 77/78 | 审计 LOW 缺口 |
| 8-K earnings release | 78/78 | 保持 source tier 为公司发布、未经审计材料 |
| market evidence | 78/78 | 审计 FMP 估值字段覆盖和缺口 |
| BM25/ObjectBM25 | 已构建 | 用 route retrieval 和 coverage reservation 做小范围 smoke |
| ledger | 已可用 | 继续补行业特定指标族，例如银行、保险、REIT、公用事业、能源储量和制药管线 |

full78 的用途：

- 做数据可得性审计脚本。
- 做投研 skill v1 的 planner/synthesis smoke。
- 做不新增公司情况下的跨行业 eval。
- 做新 source-family 接入前的对照基线。

## 阶段 1：美国 SEC filer 跨行业扩容

### 目标规模

建议下一轮主线扩容从 full78 扩到 `full128_us` 左右，即新增 50 家美国 SEC filer。这个规模能明显提升行业覆盖，同时仍可沿用当前 10-K/10-Q/8-K/market pipeline，不会把问题一次性变成多格式解析。

### 建议新增公司

```text
DELL, HPE, SMCI, ANET, MRVL, LRCX, KLAC, SNPS, CDNS, NOW, IBM,
CMCSA, T, VZ, EA, TTWO,
NKE, SBUX, TJX, GM, F, MAR, AZO,
MDLZ, CL, KMB, KR, TGT,
OXY, HAL, LNG, WMB, KMI, PSX,
C, WFC, GS, SCHW, COF, CB,
ABT, MDT, DHR, PFE, BMY, AMGN, GILD, HCA, SYK,
BA
```

### 行业覆盖意图

| 行业 | 新增公司 | 覆盖目的 |
| --- | --- | --- |
| 信息技术/AI 基础设施 | DELL, HPE, SMCI, ANET, MRVL, LRCX, KLAC, SNPS, CDNS, NOW, IBM | 不只看 GPU；补服务器、网络、EDA、设备、IT 服务和企业软件 |
| 通信服务 | CMCSA, T, VZ, EA, TTWO | 补有线/无线、电信资本开支、游戏和媒体内容 |
| 可选消费 | NKE, SBUX, TJX, GM, F, MAR, AZO | 补品牌消费、餐饮、折扣零售、汽车、酒店和售后 |
| 必需消费 | MDLZ, CL, KMB, KR, TGT | 补包装食品、家庭个护、食品零售和大型零售 |
| 能源 | OXY, HAL, LNG, WMB, KMI, PSX | 补上游、油服、LNG、中游和炼化 |
| 金融 | C, WFC, GS, SCHW, COF, CB | 补大型银行、投行、券商、消费信贷和保险 |
| 医疗 | ABT, MDT, DHR, PFE, BMY, AMGN, GILD, HCA, SYK | 补医疗器械、生命科学工具、制药、医院和骨科设备 |
| 工业 | BA | 在现有 CAT/GE/HON/RTX/UPS/UNP/DE 基础上补航空制造核心样本 |

### 这 50 家不是最终名单

它们是第一轮可执行的美国 SEC filer 扩容候选。是否进入 accepted universe 取决于 availability probe：

- FY2023-FY2025 10-K 是否可得。
- latest 10-Q 是否可得。
- 2026/2027 8-K earnings release 是否可得。
- 市场价格、估值字段和 benchmark return 是否可得。
- iXBRL/structured objects 是否能支持主要行业指标。

如果某家公司披露不适配或数据缺口过大，不能用同业替代规则悄悄补齐，必须在 accepted manifest 中记录 source gap 或移出第一轮。

## 阶段 1.5：Sector Depth Packs

`full128_us` 用来解决“主流行业都有基本 peer 覆盖”。但真实研报通常还需要行业深度包：同一个行业内部要能看价值链、关键驱动、反证指标和二阶传导。因此新增 `configs/sector_depth_packs_v0_2.yaml`，按行业维护候选池。

当前规划的 depth packs：

| Pack | 用途 |
| --- | --- |
| `technology_ai_infrastructure_depth` | AI/数据中心从芯片到服务器、网络、EDA、设备、电力、散热和软件的传导 |
| `financial_services_depth` | 利率、存款成本、信贷质量、资本市场、保险定价和资产管理流量 |
| `healthcare_life_sciences_depth` | 产品周期、手术量、药品商业化、专利悬崖、支付方压力和医院需求 |
| `consumer_discretionary_depth` | 消费需求、客流、同店、库存、促销、住房周期、旅游和汽车 |
| `consumer_staples_depth` | 量价、私有品牌压力、投入成本、零售库存和品牌韧性 |
| `energy_infrastructure_depth` | 商品价格、产量、储量、资本纪律、油服订单、LNG、中游和炼化 |
| `industrials_aerospace_logistics_depth` | 订单、backlog、交付、供应链、防务预算、货运和自动化 |
| `materials_depth` | 商品/input cost 周期、定价、销量、建筑、农业投入品、金属和特化 |
| `real_estate_utilities_depth` | 利率、入住率、租金、融资成本、数据中心需求、电力负荷和监管回报 |
| `communication_media_depth` | 无线/宽带竞争、用户数、ARPU、内容、广告、游戏 bookings 和杠杆 |

Depth pack 的启用规则：

1. 先跑 availability probe，不直接并入主 universe。
2. 只把通过 source contract 的公司加入 accepted pack。
3. 每个 pack 独立产出 source gap、parser report、ledger coverage report、market snapshot report 和 index build report。
4. Eval 使用 pack 级问题，不要求每次全链路都加载所有 depth packs。
5. Planner 可以请求某个 sector pack，但必须说明研究用途，例如“验证能源资本纪律”或“验证银行信贷质量”，不能只因为同属一个行业就全量展开。

## 阶段 2：主流行业关系图，而不是 AI-only 关系图

关系图应按行业族构建，不应只围绕 NVDA：

| 行业族 | 关系图问题 |
| --- | --- |
| 半导体/AI 基础设施 | GPU、ASIC、服务器、网络、EDA、设备、电力/散热、云 capex 之间如何传导 |
| 云/软件 | 云 capex、RPO、递延收入、订阅续费、销售效率和 AI monetization 如何传导 |
| 银行/金融 | 利率、存款成本、信贷质量、资本充足率、交易/投行业务和消费信贷如何传导 |
| 医疗/制药 | 核心产品放量、专利悬崖、管线、并购、医保/支付方和医院需求如何传导 |
| 消费 | 客单价、销量、同店销售、库存、促销、工资成本和品牌力如何传导 |
| 能源 | 油气价格、产量、资本开支、油服订单、LNG、中游和炼化利润如何传导 |
| 工业/航空/物流 | backlog、订单、供应链、交付节奏、成本通胀和航空周期如何传导 |
| 房地产/公用事业 | 利率、租金、入住率、融资成本、电力需求、负荷增长和监管回报如何传导 |

每个关系图节点必须记录：

```json
{
  "ticker": "string",
  "industry_group": "string",
  "sub_industry": "string",
  "role_in_value_chain": "supplier | customer | competitor | capacity_provider | demand_proxy | cost_driver | financing_proxy",
  "relationship_hypothesis": "string",
  "required_evidence": ["10-K", "10-Q", "8-K", "market_snapshot", "future_web_snapshot"],
  "primary_metric_families": ["revenue", "margin", "capex"],
  "unsupported_claims": ["string"],
  "source_gap_policy": "fail_closed | hypothesis_only | require_external_source"
}
```

## 阶段 3：新披露格式 source-family

### 当前已支持或接近支持

| Source family | 表单 | 当前处理方式 |
| --- | --- | --- |
| US annual primary filing | 10-K | 主链路已支持 |
| US interim primary filing | 10-Q | 主链路已支持 latest 10-Q |
| US company-authored unaudited filing | 8-K / Exhibit 99.x | 主链路已支持 earnings release |
| Offline market snapshot | Yahoo bars + FMP valuation | 主链路已支持 |

### 下一批需要新增的 source family

| Source family | 表单/文件 | 典型公司 | 用途 | 接入风险 |
| --- | --- | --- | --- | --- |
| Foreign private issuer annual | 20-F | TSM, ASML, ARM, SAP, NVO, TM | 外国发行人年度报告、业务和财务事实 | IFRS/本币/ADR/section 结构不同，不能直接当 10-K |
| Foreign private issuer current/interim | 6-K | TSM, ASML, ARM, SAP, NVO, TM | 季度/半年度结果、新闻稿、IR 材料 | 文件自由度高，需要 exhibit/标题选择 |
| Canadian annual | 40-F | SHOP、部分加拿大公司 | 加拿大公司年度报告 | 口径和附件结构不同，需要 canary |
| Proxy/governance | DEF 14A | US filer | 股权激励、董事会、薪酬、治理 | 不应进入财务事实 ledger，可作为 governance source |
| Investor presentation / shareholder letter | IR materials / shareholder letter | 跨行业 | 管理层叙事、业务驱动、长期目标 | 未审计、容易营销化，需要强 source tier |

对应配置：`configs/foreign_issuer_source_family_canary_v0_2.yaml`。

### 20-F / 6-K 接入原则

- 不存在“20-K”作为当前计划的标准表单；本阶段按 `20-F` / `6-K` / `40-F` 设计。
- 20-F 可以支持年度业务、风险、财务事实和经营讨论，但必须标记为 `foreign_primary_annual`，不能和 10-K 混成同一 source tier。
- 6-K 可以支持季度结果和管理层解释，但必须标记为 `foreign_company_authored_interim` 或更细 source tier，不能替代 10-Q。
- Ledger 必须支持 taxonomy 差异：US GAAP、IFRS、本币、ADR、单位和汇率边界。
- Renderer 必须显示 source family、form type、currency、period role、as-of/filing date 和可比性 caveat。

## 阶段 4：行业数据 source-family

行业数据不是公司披露，但真实研报离不开行业和宏观背景。它应该作为独立 source-family 接入，而不是让模型凭常识解释。

对应配置：`configs/industry_data_source_families_v0_2.yaml`。

第一批行业数据 source-family：

| Source family | 主要行业 | 用途 |
| --- | --- | --- |
| `industry_macro_rates_credit` | 金融、地产、公用事业、可选消费 | 利率周期、信用条件、融资成本、存款/贷款环境 |
| `industry_consumer_macro` | 可选消费、必需消费、通信服务 | 消费需求、通胀、就业和收入背景 |
| `industry_energy_commodities` | 能源、材料、工业 | 油气价格、库存、产量、LNG、炼化背景 |
| `industry_healthcare_regulatory` | 医疗 | FDA/CMS/医保支付/监管事件背景 |
| `industry_housing_real_estate_power` | 地产、公用事业、消费、工业 | 房地产周期、电力负荷、融资成本和电价背景 |
| `industry_industrial_macro` | 工业、材料、科技 | 工业生产、订单、库存和制造业活动 |

行业数据接入原则：

- 必须记录 provider、dataset_id、series_id、observation_date、as_of_date、frequency、unit、fetched_at。
- 只能解释行业或宏观背景，不能覆盖公司披露的财务事实。
- 如果行业数据与公司披露冲突，进入 conflict/reflection，不做平均。
- 先接免费、可重复、离线可缓存的数据源，例如 FRED、EIA、FDA/CMS 公共数据。
- 不要求第一步实时更新；先拉一批 snapshot，验证 source contract、normalization 和 renderer。

## 下载和处理流程

### US filer 主线

```text
company config
  -> SEC submissions probe
  -> download 10-K / latest 10-Q / 8-K earnings release
  -> manifest build
  -> section split
  -> structured object extraction
  -> Exact-Value Ledger / lightweight ledger store
  -> BM25 / ObjectBM25 / route retrieval metadata
  -> market snapshot + valuation
  -> availability and source-gap report
  -> local smoke
```

### Foreign issuer canary

```text
foreign issuer seed config
  -> SEC submissions probe for 20-F / 6-K / 40-F
  -> raw download with source_family metadata
  -> form-specific manifest
  -> form-specific section splitter
  -> XBRL/IFRS object extraction canary
  -> source-family ledger mapping
  -> source-gap report
  -> no synthesis promotion until parser/gates pass
```

### 所有新增数据都必须产出

- `manifest.jsonl`
- `source_gap.json`
- `download_log.jsonl`
- `parser_report.json`
- `ledger_coverage_report.json`
- `market_snapshot_report.json`
- `index_build_report.json`
- `readiness_report.json`

没有这些报告，不进入主链路 full-source smoke。

## 建议执行顺序

### Step 1：full78 数据可得性审计

先写审计脚本，不改主链路：

- 输入 current full78 configs 和已生成 manifest/market/index。
- 输出 `reports/quality/research_ab_full78_data_availability_v0_2.json`。
- 目标是确认当前链路的真实覆盖边界。

### 2026-05-29 sector-depth availability probe

已新增可复跑探测脚本：

```text
scripts/probe_sector_depth_source_availability.py
```

本轮 probe 只查元数据和公开端点，不下载 SEC 正文，不进入 manifest/parser/index 构建。它用于回答三个问题：

1. 每个 sector-depth pack 需要哪些 P0/P1 公司。
2. 这些公司在 SEC submissions 中是否具备所需表单元数据。
3. 行业数据 source-family 是否已有可访问的公开数据源或仍缺具体 dataset/series 映射。

最新报告：

```text
reports/quality/20260529_sector_depth_source_availability_v0_2.json
reports/quality/20260529_sector_depth_source_availability_v0_2.md
```

本轮结论：

| 项目 | 结果 |
| --- | --- |
| 公司需求 | 171 个去重 ticker/source-family requirement |
| SEC metadata | 165 available，1 partial，5 missing/error |
| Market snapshot live/local | 167 available，4 missing |
| Industry source-family | 7 available，0 个 source-family 缺定义 |
| Provider-level mapping | 2 个 EIA provider 仍需具体 endpoint/frequency/facet 映射 |

主要缺口：

| Ticker | 问题 | 处理 |
| --- | --- | --- |
| `AES` | SEC metadata 中未找到 2026/2027 earnings 8-K candidate | 保留为 partial，进入 8-K source gap；下载阶段不强行补 |
| `CTRA` | SEC ticker reference 未找到 | 复核 ticker/CIK 映射或替换能源 depth candidate |
| `HES` | SEC ticker reference 和 Yahoo chart 均不可用 | 可能已不适合作为当前上市公司样本，复核后替换 |
| `IPG` | SEC ticker reference 和 Yahoo chart 均不可用 | 复核并替换 communication/media depth candidate |
| `MMC` | SEC reference 当前映射为 `MRSH`，Yahoo `MMC` 不可用 | 更新 ticker alias/accepted ticker 前不得进入下载 |
| `PARA` | SEC reference 当前出现 `PSKY`，Yahoo `PARA` 不可用 | 更新 ticker alias/accepted ticker 前不得进入下载 |

配置修正：

- `materials_depth` 的行业数据从未定义的 `industry_commodity_macro` 改为 `industry_materials_commodities`。
- `real_estate_utilities_depth` 的行业数据从未定义的 `industry_rates_real_estate_power` 改为 `industry_housing_real_estate_power`。
- `technology_ai_infrastructure_depth` 增加 `industry_housing_real_estate_power`，用于电力负荷和数据中心供电背景。
- `industry_data_source_families_v0_2.yaml` 新增 `industry_materials_commodities`，当前使用 FRED 免费 CSV series 做 canary。

注意：8-K earnings 的 availability 是 metadata-level candidate 检查，只确认 SEC submissions 中存在 Item 2.02 或 earnings/results 相关候选；真正进入主链路前仍需跑 exhibit 选择和下载验证。

### Step 2：新增 full128_us 扩容配置

新增配置文件：

```text
configs/sec_investment_coverage_full128_us_additions_v0_2.yaml
configs/sec_investment_coverage_8k_earnings_full128_us_additions_v0_2.yaml
```

只写新增公司范围和 source contract，不写密钥和私有路径。执行时先与 full78 配置合并，再生成 accepted `full128_us` manifest；不能把 additions-only 配置单独当成 full128。

### Step 3：做 full128_us availability probe，不直接下载全量

先做 probe：

- 是否有 FY2023-FY2025 10-K。
- 是否有 latest 10-Q。
- 是否有 2026/2027 8-K earnings release。
- 是否有 market snapshot 和 FMP valuation。
- 是否有可解析 XBRL 或 HTML sections。

通过 probe 后再进入下载和构建。

### Step 4：full128_us 下载与处理

沿用当前 full78 pipeline：

- 10-K/10-Q 下载。
- 8-K earnings release 下载。
- mixed manifest。
- evidence objects。
- structured objects。
- ledger store。
- BM25/ObjectBM25。
- market snapshot。
- readiness report。

### Step 5：启用 selected sector_depth_packs

先不全开，建议顺序：

1. `financial_services_depth`
2. `healthcare_life_sciences_depth`
3. `energy_infrastructure_depth`
4. `consumer_discretionary_depth`
5. `technology_ai_infrastructure_depth`

每个 pack 单独 probe、下载、构建、smoke。通过后再进入 pack-level eval。

### Step 6：20-F/6-K canary

先选少量跨行业 foreign issuer，不进入主 universe：

```text
TSM, ASML, ARM, SAP, NVO, TM
```

目标不是立刻回答问题，而是验证 source-family：

- 20-F 下载和 section split。
- 6-K 文件筛选。
- IFRS/foreign issuer ledger mapping。
- source tier/gate/renderer 是否能区分 foreign annual/interim。

### Step 7：行业数据 source-family canary

建议优先顺序：

1. `industry_macro_rates_credit`：服务金融、地产、公用事业、消费。
2. `industry_energy_commodities`：服务能源、材料、工业。
3. `industry_consumer_macro`：服务消费和广告/媒体。
4. `industry_healthcare_regulatory`：服务医疗。

先做离线 snapshot，不接实时查询。

### Step 8：跨行业 eval

基于 full78 先跑，full128_us 准备好后再扩：

1. 科技/软件：云收入、RPO、AI monetization、利润率。
2. 金融：存款成本、信贷质量、资本充足率。
3. 医疗：产品放量、管线、专利风险、医院需求。
4. 消费：同店销售、库存、促销、毛利率。
5. 能源：油气价格、产量、capex、自由现金流。
6. 工业：订单、backlog、供应链、交付节奏。
7. 房地产/公用事业：利率、电力负荷、监管回报、融资成本。

## 对 182 的修正

`182` 中原先列出的 18 家 AI infrastructure 公司应理解为一个垂直行业 pilot，不再作为阶段 B 的主扩容路线。主扩容路线以本文件为准：

- A 阶段：先用 full78 测投研 skill 和数据可得性。
- B 阶段：先做跨主流行业的 `full128_us` 扩容。
- Depth packs：按行业独立启用，不能一次性全量混进主链路。
- 新格式阶段：独立做 20-F/6-K/40-F source-family canary。
- 行业数据阶段：独立做 FRED/EIA/FDA/CMS 等行业数据 source-family canary。
- AI supply chain：作为一个高价值 eval case，而不是唯一行业方向。

## 当前不做

- 不把 TSM/ASML/ARM 直接塞进 10-K/10-Q pipeline。
- 不用外部网页摘要替代 20-F/6-K parser。
- 不因为某行业缺公司就让模型用常识补行业数据。
- 不直接做 full200，先用 full78/full128_us 把 source contract 和 parser 流程跑稳。

## 2026-05-29 full238 数据构建与对象索引存储迁移

### 本轮问题

sector-depth 合并后，`full128_us + sector_depth` 去重范围扩大到 238 家公司。继续沿用 full30/full78 阶段的 ObjectBM25 形态会出现两个问题：

- 对象索引冷启动需要加载 `bm25.pkl` 和大量 JSON records，随着 structured objects 扩到数百万行，启动和内存压力不可接受。
- DuckDB ledger 构建尾段出现长时间 WAL checkpoint 和大批量写入，容易被误判为卡死，也会拉长全量重建时间。

这不是本机资源限制导致的单点问题，而是 full238 后数据规模已经超过了原先“全量对象 BM25 + JSON records 冷加载”的工程边界。

### 已完成

- full238 mixed manifest 已生成：
  - `data/processed_private/manifests/sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl`
- full238 evidence BM25 index 已生成：
  - `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027`
  - evidence records: `89,112`
- full238 lightweight ledger 已生成并修正 fiscal-year 范围：
  - `data/processed_private/ledger/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
  - filtered facts: `2,257,112`
  - tickers: `238`
  - fiscal years: `2023-2027`
  - form types: `10-K / 10-Q / 8-K`
- 原始未过滤 ledger 保留为：
  - `data/processed_private/ledger/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.unfiltered.duckdb`

### SQLite FTS 对象索引

新增 SQLite FTS 对象索引，替代 ObjectBM25 的冷启动路径：

- Builder:
  - `src/indexing/build_object_sqlite_fts_index.py`
  - `scripts/build_object_sqlite_fts_index.py`
- Output:
  - `data/indexes/bm25/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects/records.sqlite`
- Index metadata:
  - total object records: `3,035,688`
  - tables: `101,786`
  - metrics: `2,306,669`
  - claims: `627,233`
  - build elapsed: `191.609s`

`ObjectBM25Retriever` 现在会优先识别 `records.sqlite`：

- 不加载 `bm25.pkl`
- 不加载全量 records
- 按 ticker / fiscal_year / form_type / object_type / source_tier / section 等 metadata 过滤
- 有过滤条件时优先执行小候选池排序；需要精确文本匹配时先尝试 required-term FTS，再回退到候选池排序

### 性能验证

本地 context-only smoke，不调用 DeepSeek，不跑 BGE，仅验证 query -> evidence/object/ledger 的确定性链路：

- NVDA text case:
  - case: `NVDA_DATACENTER_2023_2025_001`
  - output: `reports/quality/local_full238_sqlite_fts_context_smoke_20260529_v1`
  - result: `context_prepared`
  - elapsed: about `9.1s`
- AMZN numeric case before filtered candidate optimization:
  - case: `AMZN_AWS_NUMERIC_2023_2025_001`
  - output: `reports/quality/local_full238_sqlite_fts_context_smoke_20260529_amzn_numeric`
  - result: `context_prepared`
  - elapsed: about `43.7s`
- AMZN numeric case after filtered candidate optimization:
  - output: `reports/quality/local_full238_sqlite_fts_context_smoke_20260529_amzn_numeric_required_fts`
  - result: `context_prepared`
  - elapsed: about `10.4s`
  - context rows: `83`
  - structured object rows: `46`
  - evidence rows: `37`

Direct object retriever sanity:

- `sqlite=True`
- `bm25_loaded=False`
- `records_loaded=0`
- `record_count=3,035,688`
- AMZN filtered object query latency dropped from ten-second level to roughly `0.02-0.9s` depending on query specificity.

Targeted tests:

- `pytest tests/test_bm25_retriever.py -q` -> `7 passed`
- `pytest tests/test_sec_agent_ledger_store.py tests/test_sec_agent_retrieval_plan.py -q` -> `17 passed`

### 当前边界

- SQLite FTS 解决的是 object store 冷启动和全局对象扫描问题，不等于已经完成 route-level retrieval 精度优化。
- Broad multi-metric object query 仍可能混入同表内相邻指标，例如 AWS revenue / operating income / capex 在同一披露块里相互靠近；最终应由 EvidenceRequirementPlan 拆成具体 metric route，并优先走 ledger / structured metric family，再让 BGE/FTS 处理解释性文本。
- 现有 `market_snapshot` 仍停留在 full78 6M evidence pack，full238 市场快照还需要单独重建，不能声称 full238 market source 已覆盖。

### 下一步

1. 在 full238 上继续推进 `EvidenceRequirementPlan -> route-local retrieval`，让模型 planner 产出的证据需求直接约束 ticker/year/source/form/metric route。
2. 把 coverage reservation 接入新的 retrieval executor，避免宽问题只按全局分数堆上下文。
3. 重建 full238 market snapshot/evidence pack 后，再跑 10-K + 10-Q + 8-K + market 的 full-source smoke。
4. 对 AMZN/JPM/V/LLY 这类跨行业数值 case 做 route-level 精度检查，区分 extraction/ledger 问题和 rerank 问题。

## 2026-05-30 full238 market snapshot 与 industry source-family route 接入

### 本轮目标

把 full238 的 SEC 口径与市场快照、行业数据口径对齐，并把已生成的行业数据从“离线产物”接入主链路 source-family route。行业数据只能作为宏观/行业背景和解释证据，不能替代公司披露、10-K/10-Q/8-K 或 Exact-Value Ledger。

### 已完成

- full238 market snapshot/evidence pack 已用 Yahoo chart + FMP key metrics partial 数据重建：
  - snapshot id: `20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1`
  - daily bars: `data/processed_private/market/bars/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_daily_bars.jsonl`
  - snapshot: `data/processed_private/market/snapshots/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_snapshot.jsonl`
  - analytics: `data/processed_private/market/analytics/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_analytics.jsonl`
  - evidence pack: `data/processed_private/market/evidence_packs/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl`
  - validation: `reports/quality/20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_market_validation.json`
- Market validation 结果：
  - snapshot rows: `238/238`
  - analytics rows: `238/238`
  - evidence rows: `238/238`
  - validator: `can_enter_market_snapshot_chain=true`
  - 注意：FMP 估值字段受免费 key/provider 限制，`market_cap/EV/EV-sales/EV-EBITDA` 当前约 `39/238`；价格、3M return、相对 QQQ return 等字段覆盖 `238/238`。
- `industry_snapshot` 已作为正式 source tier 接入：
  - `Query Contract` 允许 `industry_snapshot`，并注入行业数据边界 caveat / forbidden claims。
  - `RetrievalPlan` 支持 `industry_snapshot` route，`rerank_budget=0`，不进入 BGE；行业数据由 source-family 精确加载。
  - `sec_agent_interactive.py` 新增 `--industry-evidence-path`、`--industry-snapshot-id`、`--industry-as-of-date`，主链路增加 `attach_industry_snapshot_context` stage。
  - LangGraph native skeleton 增加 `attach_industry_snapshot` node，并支持 graph adapter `attach_industry_snapshot_for_graph`。
  - `Evidence Coverage Matrix` 增加 `industry_snapshot_coverage`，按 task 判断是否需要行业 source-family，避免每个 SEC 财务任务都被误判缺行业数据。
  - Synthesis prompt 增加 `Industry Snapshot Usage Rule`：行业数据必须绑定 industry evidence_ids，只能解释宏观/行业/监管/商品价格背景，不能覆盖公司财务事实、公司管理层口径、新闻、实时市场数据或分析师预期。

### 验证

- 编译：
  - `python -m py_compile scripts/cloud/sec_agent_interactive.py src/sec_agent/query_contract.py src/sec_agent/retrieval_plan.py src/sec_agent/coverage_matrix.py scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- 单测：
  - `pytest tests/test_sec_agent_industry_snapshot_route.py -q` -> `5 passed`
  - `pytest tests/test_sec_agent_retrieval_plan.py -q` -> `15 passed`
  - `pytest tests/test_sec_agent_10q_source_contract.py -q` -> `42 passed`
  - `pytest tests/test_sec_agent_langgraph_orchestrator.py -q` -> `30 passed`
  - `pytest tests/test_sec_agent_graph_runner.py -q` -> `1 passed`
- Native plan smoke，不调用 LLM，不跑 BGE：
  - output: `eval/sec_cases/outputs/native_industry_plan_smoke_20260530`
  - result: `status=completed`
  - routes: `filing_text=2, industry_snapshot=2, ledger_first=2`
  - node_count: `16`

### 当前边界

- `industry_snapshot.duckdb` 与 `industry_evidence_rows.jsonl` 已可作为 source-family route 使用，但当前先接入 `industry_evidence_rows.jsonl`；DuckDB 查询工具化仍是下一阶段。
- FMP 免费 key 下的估值覆盖仍不完整，不能在 full238 输出里声称所有公司都有估值倍数。
- EIA route 已在下一节补齐；历史边界是此前缺少 `EIA_API_KEY` 时，能源/电力部分主要依赖 FRED 可用序列与已生成 evidence rows。
- 本轮没有跑 DeepSeek full-source synthesis；已完成的是 deterministic route/coverage/prompt 合同与 native plan smoke。

### 下一步

1. 把 `industry_snapshot.duckdb` 封装成正式查询工具，让 planner 的 `source_families` 可以精确拉取行业 observation / evidence rows。
2. 在 full238 上跑一个中等范围 DeepSeek full-source case，检查 10-K/10-Q/8-K/market/industry 五类证据是否被正确引用、边界是否清楚。
3. 针对行业数据缺口建立 coverage report：按 sector-depth pack 标出当前有行业数据支持、只有部分支持、缺 EIA/FDA/CMS 等 key 的范围。

## 2026-05-30 EIA total-energy route 补齐

### 本轮目标

把 EIA `total-energy/data` monthly route 从“待提供 key 的 deferred provider”推进到可重复执行的正式行业数据源。EIA 数据仍属于 `industry_snapshot`，只能用于能源、商品、供需、电力/能源结构等行业背景解释，不能替代公司披露中的财务事实。

### 已完成

- `scripts/industry/10_download_industry_source_snapshot.py` 新增 `eia_v2_json` route：
  - 从运行时环境变量 `EIA_API_KEY` 读取 key，不写入配置或产物。
  - 支持 EIA v2 JSON 的 `response.data` 结构，归一化字段：`period`、`msn`、`seriesDescription`、`value`、`unit`。
  - `Not Available` 等非数值行会跳过，并在 evidence caveat 中记录跳过数量。
  - 写入 artifacts 的 `api_route` 会把 `api_key` 脱敏为 `<redacted>`。
- `configs/industry_data_api_contracts_v0_2.yaml` 新增正式 EIA route：
  - source family: `industry_energy_commodities`
  - provider: `EIA`
  - dataset: `eia/total-energy/monthly`
  - endpoint: `https://api.eia.gov/v2/total-energy/data/`
  - params: `frequency=monthly`、`data[0]=value`、按 `period desc` 排序、`length=5000`
- 新增单测：
  - `tests/test_industry_source_snapshot.py`

### 新产物

- snapshot id: `20260530_industry_sector_depth_v0_2_with_eia_total_energy`
- observations: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy/industry_observations.jsonl`
- evidence rows: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy/industry_evidence_rows.jsonl`
- DuckDB: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy/industry_snapshot.duckdb`
- metadata: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy/industry_snapshot_metadata.json`

### 数据结果

- total observations: `58,889`
- total evidence rows: `35`
- failure count: `0`
- EIA normalized observations: `4,692`
- EIA date range: `2025-10-01` to `2026-04-01`
- EIA evidence row: `industry_energy_commodities / EIA / eia/total-energy/monthly`
- 说明：EIA route 请求了最近窗口 `5,000` 行，其中 `4,692` 行是可归一化的数值记录，其余不可用值已跳过。

### 验证

- `python -m py_compile scripts/industry/10_download_industry_source_snapshot.py`
- `pytest tests/test_industry_source_snapshot.py -q` -> `1 passed`
- `pytest tests/test_industry_source_snapshot.py tests/test_sec_agent_industry_snapshot_route.py -q` -> `6 passed`
- DuckDB 检查：
  - `provider='EIA'`、`source_family='industry_energy_commodities'`、`count=4692`
  - 样例 series 包括 `ARTCBUS`、`ARTCPUS`、`AVTCBUS`、`AVTCPUS`、`CLPRPUS`、`COEXPUS`、`COIMPUS`、`COPSPUS`
- 脱敏检查：
  - 未发现真实 EIA key 写入 `configs/`、`scripts/`、`tests/`、`docs/` 或新生成的 industry snapshot 目录。

### 当前边界

- 本轮接入的是用户提供的 EIA total-energy monthly route，不等于已经完成所有 EIA 细分 endpoint。`electricity/retail-sales` 等更细的电力数据 route 仍在 deferred provider 合同中，后续可按 utilities / power load 需求继续标准化。
- 当前主链路仍默认通过 `industry_evidence_rows.jsonl` 注入行业 evidence；DuckDB observation 级查询工具化仍是下一步。

## 2026-05-30 EIA electricity retail-sales route 补齐

### 本轮目标

把 EIA `electricity/retail-sales` 作为 utilities / power demand 场景的正式行业数据源补进来。该 route 的官方语义是 `Electricity Sales to Ultimate Customers`，可提供月度售电量、售电收入、平均电价和客户数，适合解释电力需求、电价和公用事业收入环境；它不是小时级实时负荷数据，不能写成实时 power load。

### 已完成

- `scripts/industry/10_download_industry_source_snapshot.py` 的 `eia_v2_json` normalizer 从单值结构扩展为两类结构：
  - `msn + value`：用于 `total-energy`。
  - 多指标列：用于 `retail-sales`，把 `sales/revenue/price/customers` 展开为独立 observation。
- 新增 source-family：
  - `industry_utilities_power_demand`
  - allowed claim types: `power_demand_context`、`retail_electricity_price_context`、`utility_revenue_context`、`customer_count_context`
  - prohibited boundary: 不能替代公司财报收入、公司披露的 load growth 或小时级负荷事实。
- 新增正式 EIA route：
  - endpoint: `https://api.eia.gov/v2/electricity/retail-sales/data/`
  - dataset: `eia/electricity/retail-sales`
  - facets: `stateid=US`，`sectorid=ALL/RES/COM/IND/TRA/OTH`
  - data fields: `sales`、`revenue`、`price`、`customers`
  - series id pattern: `EIA_RETAIL_SALES::{stateid}::{sectorid}::{metric}`
- `sec_agent_interactive.py` 更新 source-family allowlist 和 prompt intent mapping：
  - 问到 `power/electricity/utility/load/电力/用电/公用事业/负荷/售电/电价` 时，会默认选择 `industry_utilities_power_demand`。
- `sector_depth_packs_v0_2.yaml` 的 real_estate_utilities pack 增加 `industry_utilities_power_demand`。

### 新产物

- snapshot id: `20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales`
- observations: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_observations.jsonl`
- evidence rows: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_evidence_rows.jsonl`
- DuckDB: `data/processed_private/industry_data/20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales/industry_snapshot.duckdb`

### 数据结果

- total observations: `64,529`
- total evidence rows: `36`
- failure count: `0`
- EIA `industry_energy_commodities`: `4,692` observations，date range `2025-10-01` to `2026-04-01`
- EIA `industry_utilities_power_demand`: `5,640` observations，date range `2001-01-01` to `2026-03-01`
- 最新 US all-sector 样例：
  - sales: `314,308.22665` million kWh
  - revenue: `44,562.95799` million dollars
  - price: `14.18` cents/kWh
  - customers: `166,374,115`

### 验证

- `python -m py_compile scripts/industry/10_download_industry_source_snapshot.py scripts/cloud/sec_agent_interactive.py`
- `pytest tests/test_industry_source_snapshot.py tests/test_sec_agent_industry_snapshot_route.py -q` -> `7 passed`
- 主链路 industry loader 检查：
  - 请求 `industry_utilities_power_demand` 时返回 `1` 条 EIA evidence row。
  - dataset: `eia/electricity/retail-sales`
- 脱敏检查：
  - 未发现真实 EIA key 写入 `configs/`、`scripts/`、`tests/`、`docs/` 或新生成的 industry snapshot 目录。

### 当前边界

- `retail-sales` 是月度售电/价格/客户数数据，用于投研里的 demand / price / utility revenue context；如果要分析真实小时级负荷、峰谷、区域调度或 AI data center 对电网的短期冲击，下一步应接 EIA `rto/region-data` 或相关 balancing authority 数据。
- 当前主链路仍通过 evidence row 注入 source-family；observation 级 DuckDB 工具调用仍待封装。
