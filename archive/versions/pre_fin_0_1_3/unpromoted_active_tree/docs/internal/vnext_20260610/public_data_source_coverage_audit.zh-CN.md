# 公开/免费数据源覆盖审计

## 状态

- 审计日期：2026-06-10
- 策略：当前阶段不采购商业 API；优先公开、免费、官方或可审计来源。
- 产出性质：第一版覆盖审计，不等于已实现 collector/parser。

## 分类口径

| 状态 | 含义 | 工程处理 |
| --- | --- | --- |
| `no_key` | 无需 API key，可直接公开访问，但仍要遵守 rate limit、User-Agent 和 robots/terms。 | 可优先实现 collector。 |
| `no_key_limited` | 无 key 可用但限额很低，注册 key 可提高额度或稳定性。 | 可做小规模 resolver / smoke，批量任务建议配置 key。 |
| `free_key` | 免费注册 key 或账号后可用。 | 可纳入候选，但 key 只放环境变量，不写入文档或仓库。 |
| `open_bulk` | 官方开放数据集或批量下载，不一定是 API。 | 适合离线 snapshot。 |
| `official_web_no_key` | 官方网站公开下载，不一定提供稳定 API。 | 需要保留 URL、checksum、publication date 和下载策略。 |
| `official_portal_pending` | 官方门户公开，但 API 参数、下载流程或反爬边界还需验证。 | 先做 profile-specific downloader 设计。 |
| `endpoint_specific_pending` | 同一机构有公开 API/下载服务，但目标 endpoint、参数或 key 策略需逐项确认。 | 先做 endpoint-level source plan。 |
| `unofficial_provisional` | 非官方接口或社区反向接口。 | 只能做 staging / context，不作为权威事实来源。 |
| `commercial_deferred` | 商业数据或免费层不可支撑稳定覆盖。 | 当前阶段延后，不作为核心依赖。 |

## 核心结论

- 美国公开公司主披露和结构化事实覆盖最稳：SEC EDGAR、CompanyFacts、Submissions、DERA datasets 可以继续作为主证据核心。
- 非美主披露可做，但不是一个统一 API 问题：DART、EDINET 需要免费官方 key；MOPS、HKEXnews、CNINFO 更像 profile-specific official portal downloader。
- 宏观/行业公开数据覆盖充足，但大多只能支持 context claim：FRED、BLS、BEA、Census、EIA、FDIC、USITC/DataWeb 等不能直接替代公司披露。
- 医疗、专利、科研、实体解析公开来源可支撑 Product/Technology Specialist 的第一版：ClinicalTrials.gov、openFDA、CMS、PatentsView、OpenAlex、GLEIF、OpenFIGI。
- 产品、销量、出货、subscriber、backlog、procedure volume 等“产品经营指标”必须单独治理：公司披露的指标可以作为公司级事实，监管/行业/第三方公开数据多数只能作为产品状态或使用量上下文。
- 免费公开来源不能稳定替代 sell-side consensus、实时估值数据库、商业供应链数据库、海关明细商业库、信用卡/消费交易数据。

## 公司披露与结构化财务事实

| 来源 | Auth | 可获得数据 | 当前仓库状态 | Claim boundary | 下一步 |
| --- | --- | --- | --- | --- | --- |
| [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | `no_key` | submissions、companyfacts、frames、filing metadata。 | SEC primary filing、CompanyFacts、Submissions 已进入现有链路和配置。 | 公司申报事实、filing metadata、XBRL structured facts。 | 补 ownership / insider forms 到 investment graph。 |
| [SEC Financial Statement Data Sets](https://www.sec.gov/dera/data/financial-statement-data-sets) | `open_bulk` | 按季度打包的财报数字和标签。 | 可作为 bulk audit 候选，未作为主链路权威源。 | 离线结构化财务事实校验；不替代原始 filings 引用。 | 评估是否用于 ledger parity / fallback。 |
| [SEC Form 13F Data Sets](https://www.sec.gov/dera/data/form-13f-data-sets) 与 EDGAR ownership forms | `open_bulk` / `no_key` | 13F 持仓、13D/G、Form 3/4/5 insider 申报。 | vNext 规划中有 investment graph，当前未主线化。 | 滞后持仓和申报事实；不能解释实时交易意图。 | 建 `investment_graph_edges` schema。 |
| 公司 IR / 年报页面 | `official_web_no_key` | 年报、季报、presentation、earnings release。 | EU Infineon annual report smoke 已通过；非美通用 parser pending。 | 公司官方披露；需保留 URL、checksum、发布日期。 | 增加 PDF/HTML table parser 和 source-boundary audit。 |
| [DART Open API](https://opendart.fss.or.kr/guide/main.do) | `free_key` | 韩国上市公司报告、公告、company code。 | profile 已配置为 `blocked_requires_official_api_key`。 | 韩国监管披露；不是新闻或公司 IR 替代。 | 获取 key 后实现 company-code lookup 和 report downloader。 |
| [EDINET API](https://disclosure2.edinet-fsa.go.jp/week0020.aspx) | `free_key` | 日本有价证券报告、XBRL/PDF 包。 | profile 已配置为 `blocked_requires_official_api_key`。 | 日本监管披露；需 document type mapping。 | 实现 API-key-aware downloader。 |
| MOPS / HKEXnews / CNINFO official portals | `official_portal_pending` | 台湾、香港、中国大陆上市公司公告和年报。 | profile-specific scaffold pending。 | 官方披露平台事实；不能用公司 IR fallback 冒充交易所/监管来源。 | 分别验证查询参数、issuer code、category、date filter、checksum。 |

## 产品、销量、出货和运营量

这一层需要从一开始就和宏观行业数据分开。公开数据源能支持产品研究，但结论强度取决于来源类型。

| 来源 | Auth | 可获得数据 | 当前仓库状态 | Claim boundary | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 公司 filings / earnings release / shareholder letter / presentation | `official_web_no_key` / `no_key` | 产品收入、unit sales、deliveries、shipments、subscribers、ARPU、backlog、orders、same-store sales、traffic、production、throughput、company-reported procedure volume。 | SEC/8-K/IR 来源已有基础，产品经营指标 ontology 尚未单独抽取。 | 公司级产品销量/经营指标的最高权威路径；必须保留 period、unit、产品/segment、source ref。 | 新增 `company_product_operating_metric` parser/ontology，从现有 filings 和 earnings materials 中抽取。 |
| 公司官方产品页 / newsroom / developer docs | `official_web_no_key` | 产品存在、名称、规格、版本、适配平台、发布日期、可用性、use case。 | 未主线化。 | 可证明产品存在和官方定位；不能证明销量、收入贡献或客户采用。 | 新增 `official_product_status` collector，配合 Common Crawl 只做官方页面发现。 |
| [NHTSA vPIC API](https://vpic.nhtsa.dot.gov/api/) | `no_key` | 车辆 manufacturer、make、model、model year、VIN decode metadata。 | 未主线化。 | 汽车产品身份和车型上下文；不是销量或利润数据。 | 作为 auto product identity / spec context 候选。 |
| [ClinicalTrials.gov Data API](https://clinicaltrials.gov/data-api/about-api) | `no_key` | 试验登记、状态、sponsor、condition、phase、endpoint、站点。 | 未主线化。 | 管线/临床状态事实；不证明审批、销售或商业成功。 | Healthcare Product Specialist 第一批。 |
| [openFDA APIs](https://open.fda.gov/apis/) | `no_key_limited` | drug/device 监管记录、recalls、adverse events、device clearance/classification 相关记录。 | FDA canary 已存在。 | 监管/安全/产品状态上下文；不证明销售、使用量或因果安全结论。 | 建 drug/device/recall endpoint 白名单。 |
| [CMS public data](https://data.cms.gov/) | `no_key` | 医保支付、provider、利用率、catalog metadata。 | CMS catalog canary 已存在。 | 医疗使用量、支付方和 procedure context；除非能和公司披露或明确产品 identifier 对齐，否则不是公司产品销量。 | 先做 endpoint selection 和 entity/product mapping。 |
| [EIA Open Data](https://www.eia.gov/opendata/) | `free_key` | 电力零售、发电、燃料、库存、价格、负荷等。 | EIA v2 route 已配置但需 key。 | 能支持发电/电力/能源产品或服务的公开运营上下文；不能推出公司收入或盈利。 | endpoint validation 后作为 utility/energy operating context。 |
| [PatentsView API](https://patentsview.org/apis/api-endpoints) / [OpenAlex API](https://docs.openalex.org/) | `no_key` / `no_key_limited` | 专利、assignee、论文、citation、research topics。 | 未主线化。 | 技术活动和研发信号；不证明产品发布、销量或 moat。 | 放入 Product/Technology signal，不进入销量事实。 |

产品/销量研究的可达程度：

- 对披露充分的公司，可以做到产品级经营指标研究，例如汽车 deliveries、SaaS subscribers/RPO、医疗产品 revenue、能源 production/throughput、通信 subscribers/ARPU、零售 comparable sales。
- 对只披露 segment、不披露 product 的公司，只能做到 segment-level 或 product-family-level，不能编造 SKU 级销量。
- 对不披露销量的公司，公开监管/行业数据最多提供使用量或需求 proxy，必须写成 `public_product_usage_context` 或 `source_gap`。
- 对新产品发布、FDA clearance、临床试验、专利、论文等，可以做 product pipeline / technology signal 研究，但不能直接推导收入、订单或 adoption。

## 市场与估值

| 来源 | Auth | 可获得数据 | 当前仓库状态 | Claim boundary | 下一步 |
| --- | --- | --- | --- | --- | --- |
| Yahoo chart endpoint | `unofficial_provisional` | 日频价格、成交量、event window。 | 当前已用于 no-key market snapshot。 | 市场上下文和相对走势；不是官方估值事实。 | 继续 staging 使用，标清 provider 和 provisional 状态。 |
| OpenFIGI | `no_key_limited` / key optional | FIGI、ticker、exchange、security identifier mapping。 | 未主线化。 | 实体/证券标识解析；不是价格或财务事实。 | 与 GLEIF、CIK、ticker 建 entity resolution registry。 |
| 免费层 FMP / Alpha Vantage / Nasdaq Data Link 等 | `commercial_deferred` | 价格、估值、部分财务和 analyst 数据。 | FMP 曾遇到 429 和覆盖缺口。 | 当前不作为核心依赖；免费层不支撑稳定全量覆盖。 | 延后，除非后续用户明确接受商业 API。 |
| Sell-side consensus 数据 | `commercial_deferred` | 共识 EPS、收入、目标价、评级。 | 无可靠公开免费替代。 | 当前必须输出 `source_gap`。 | 不用公开来源伪造 consensus。 |

## 宏观、行业和贸易

| 来源 | Auth | 可获得数据 | 当前仓库状态 | Claim boundary | 下一步 |
| --- | --- | --- | --- | --- | --- |
| [FRED API](https://fred.stlouisfed.org/docs/api/fred/) / FRED graph CSV | API 为 `free_key`，graph CSV 可 `no_key` | 利率、通胀、就业、信用、消费、商品价格等宏观序列。 | `configs/industry_data_api_contracts_v0_2.yaml` 已使用 graph CSV no-key 路径。 | 宏观/行业上下文；不能变成公司披露事实。 | 保留 no-key CSV 优先，API key 路径作为增强。 |
| [BLS Public Data API](https://www.bls.gov/developers/) | `no_key`，注册 key 增强限制 | CPI、PPI、就业、工资、行业统计。 | 未主线化。 | 宏观/行业上下文。 | 加入 industry snapshot 候选。 |
| [BEA Data API](https://apps.bea.gov/api/signup/) | `free_key` | GDP、NIPA、PCE、industry accounts、regional data。 | 未主线化。 | 宏观/行业上下文。 | 免费 key 后实现低频 snapshot。 |
| [Census Data API](https://www.census.gov/data/developers.html) | `free_key` | 人口、零售、贸易、行业/企业统计等公开数据。 | 未主线化。 | 宏观、消费、贸易上下文；不是公司级销售事实。 | 验证目标 endpoint 和 key 策略后加入 snapshot。 |
| [EIA Open Data](https://www.eia.gov/opendata/) | `free_key` | 能源、库存、电价、电力负荷、销售、客户数。 | EIA v2 route 已配置，运行时需要 `EIA_API_KEY`。 | 能源/公用事业行业上下文；不能推出单家公司收入。 | 优先实现 monthly retail-sales / total-energy snapshot。 |
| [FDIC BankFind Suite API](https://api.fdic.gov/banks/docs/) | `no_key` | 银行机构、分支、财务、历史和监管数据。 | 未主线化。 | 银行业公开监管上下文；需与上市主体映射。 | 加入 Banking playbook 候选。 |
| USITC DataWeb / Census trade endpoints | `endpoint_specific_pending` | 贸易、关税、HS code、进口/出口统计。 | 未主线化。 | 贸易和制造业上下文；不能证明公司级客户/供应关系。 | 先验证官方 API/下载流程和 HS mapping。 |

## 医疗、产品、专利和科研信号

| 来源 | Auth | 可获得数据 | 当前仓库状态 | Claim boundary | 下一步 |
| --- | --- | --- | --- | --- | --- |
| [ClinicalTrials.gov Data API](https://clinicaltrials.gov/data-api/about-api) | `no_key` | 临床试验登记、状态、设计、终点、赞助方。 | 未主线化。 | 临床开发事实；不证明审批成功或商业销售。 | 作为 Healthcare/Product Specialist 第一批 collector。 |
| [openFDA APIs](https://open.fda.gov/apis/) | `no_key`，key optional for higher limits | 药品、器械、食品、recalls、adverse events、approvals 相关公开数据。 | FDA canary route 已在 industry config 中出现。 | 监管/安全事件上下文；adverse events 不等于因果结论。 | 建 approvals / recalls / device endpoints 白名单。 |
| [CMS public data](https://data.cms.gov/) | `no_key` | 医保支付、provider、coverage、catalog metadata。 | CMS data catalog canary 已在 industry config 中出现。 | 医疗支付和利用率上下文；需防止错误归因到单家公司。 | 选择少量 payer/procedure endpoints 做 snapshot。 |
| [PatentsView API](https://patentsview.org/apis/api-endpoints) | `no_key` | 专利、assignee、inventor、classification、citation。 | 未主线化。 | 技术活动和 IP 线索；不证明产品收入或 moat。 | 与 entity resolution registry 结合。 |
| [OpenAlex API](https://docs.openalex.org/) | `no_key`，polite pool 建议 email | works、authors、institutions、concepts、citations。 | 未主线化。 | 科研和技术趋势线索；不是公司财务事实。 | 作为 Product/Technology Specialist 辅助信号。 |

## 实体解析、关系图谱和事件线索

| 来源 | Auth | 可获得数据 | 当前仓库状态 | Claim boundary | 下一步 |
| --- | --- | --- | --- | --- | --- |
| [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api) | `no_key` | LEI、legal entity、parent/relationship reference data。 | 未主线化。 | 实体解析和法人关系；不证明商业交易关系。 | 建 R3 entity resolution registry。 |
| [OpenFIGI API](https://www.openfigi.com/api) | `no_key_limited` / key optional | FIGI/security identifier mapping。 | 未主线化。 | 证券 ID 映射；不是事实证据。 | 与 ticker、CIK、LEI 统一。 |
| Wikidata / Wikipedia | `no_key` | alias、identifier、行业和基础实体信息。 | 未主线化。 | 只作别名和候选解析，不能作金融事实来源。 | 作为低权重 resolver candidate。 |
| [GDELT](https://www.gdeltproject.org/data.html) | `no_key` | 全球新闻/事件线索、DOC API、TV/news metadata。 | 未主线化。 | `lead_only_needs_verification`；必须回到公司披露/监管/官方来源核验。 | 放在 external_event_lead，不进入主 ClaimCard。 |
| [Common Crawl Index](https://index.commoncrawl.org/) | `no_key` | 网页发现、历史 crawl URL。 | 未主线化。 | discovery only；抓到 URL 不等于可信事实。 | 只用于发现官方页面候选。 |

## 当前缺口

- 非美监管/交易所披露不是数据不可得，而是 profile-specific downloader/parser 尚未完成。
- 公开来源可以覆盖很多行业指标，但无法替代公司级 KPI、订单、客户合同金额和供应链商业数据库。
- 公开来源能覆盖一部分公司披露产品指标，但不能稳定覆盖 SKU 级销量、渠道库存、订单明细、真实客户采用率和未披露产品收入。
- 当前没有免费、稳定、可审计的 consensus 来源；所有 consensus 相关问题都应显式标为 `source_gap` 或 `commercial_deferred`。
- Product/Technology Specialist 的数据基础需要先补 ClinicalTrials、openFDA、PatentsView、OpenAlex，而不是直接写 prompt。
- Product / Sales Specialist 还需要先补 `company_product_operating_metric` ontology，从 SEC/8-K/IR 中抽取产品收入、销量、出货、subscriber、backlog、orders 等公司披露指标。
- Investment/Ownership Specialist 需要先补 SEC ownership forms、13F datasets、GLEIF/OpenFIGI entity mapping。

## 建议执行顺序

1. P0：已落第一版机器可读 registry：`configs/data_sources/public_source_coverage_v0_1.yaml`，并新增 validator/source-plan 生成脚本 `scripts/data_expansion/build_public_source_access_plan.py`。2026-06-11 运行结果：32 个 source、0 个 registry error、P1=20、P2=6、P3=5、deferred=1。
2. P1：已新增 no-key live probe 脚本 `scripts/data_expansion/probe_public_source_access.py`。2026-06-11 live smoke 通过 8/8：SEC EDGAR、FRED graph CSV、FDIC BankFind、ClinicalTrials.gov、openFDA、NHTSA vPIC、GLEIF、OpenAlex。
3. P2：接入免费 key 来源：EIA、BEA、Census、DART、EDINET、FRED API；key 只走环境变量和本地配置，不进入仓库。当前缺 `EIA_API_KEY`、`BEA_API_KEY`、`CENSUS_API_KEY`、`DART_API_KEY`、`EDINET_API_KEY`、`FRED_API_KEY`。
4. P3：已生成 MOPS、HKEXnews、CNINFO、USITC/DataWeb、USPTO PatentsView/Open Data Portal 的 validation tasks；下一步逐 profile 验证查询参数、下载 URL、checksum 和 parser blocker。
5. P4：再回到 Agent Graph / Skill：先升级 Coverage & Gap Auditor 和 Bounded Gap Register，再加新 Specialist。

## Source Boundary Hard Rules

- `macro_industry_indicator` 只能支持行业/宏观上下文。
- `company_product_operating_metric` 才能支持公司级产品销量、出货、subscriber、backlog、orders 或 product revenue；前提是公司直接披露。
- `official_product_status` 只能支持产品存在、规格、发布、监管状态或 pipeline 状态，不能支持销量或收入。
- `public_product_usage_context` 只能支持公开使用量、运营量或需求 proxy，不能直接改写成某公司的产品销量。
- `market_price_snapshot` 只能支持市场反应和价格/成交量上下文。
- `external_event_lead` 必须经官方来源核验才能进入 claim。
- `relationship_edge` 必须有 verifier status，不能由新闻或行业暴露自动升级。
- `company_reported_financial_fact` 只能来自公司主披露、SEC/监管结构化事实或官方报告 parser。
- `commercial_deferred` 不能被 prompt 改写成“没有证据但大概率正确”。
