# 23. 非财务信号提权与多维研报判断基座

更新时间：2026-06-24

## 背景

R15-R17 把 L1/L2/L3 source lane、Product-KPI exact、产品规格、客户部署、benchmark、行业经营指标和 source-route attempt ledger 逐步做实后，暴露出一个新的架构问题：**系统把“能不能当财务 exact fact”当成了几乎唯一的提权标准。**

这会导致产品、技术、供应链、客户部署、订单 proxy、行业指标、宏观/监管和市场预期信号被财务事实压制。结果是模型为了避免错判，大量写“公开源不足、不能判断”，而不是先基于可得可靠信号给出有边界的投资判断。

本阶段的修正不是放松 exact fact gate，而是建立第二套 authority：

- `ExactFactAuthority`：财务事实、产品收入、销量、ASP、份额、backlog 等 exact 值，仍只允许 parser-gated L1 / exact rows 支撑。
- `NonFinancialSignalAuthority`：官方产品规格、代际、benchmark、客户部署、供应链、监管、开发者生态、行业经营、宏观和市场预期信号。
- `ThesisDriverAuthority`：当非财务信号有可信源、实体绑定、citation 和边界时，可以支撑研报 thesis driver，但不能冒充 exact 财务事实。

## 新提权原则

### 1. 财务 exact gate 不降级

以下 claim 仍必须有 exact-value authority，不能由 L2/L3 proxy、新闻、产品页、招聘、渠道、专利、论文或弱信号直接支撑：

- 产品收入 / SKU revenue / product revenue。
- 销量 / shipment / unit sales / sell-through。
- ASP / 价格实现 / gross margin by product。
- 市场份额 / channel inventory / backlog。
- 客户订单金额 / revenue contribution。
- 公司 reported financial fact。

若只有非财务信号，ClaimCard 必须写成 bounded signal，而不是 exact KPI。

### 2. 非财务强信号可以支撑 thesis driver

满足以下条件时，非财务信号可以进入 thesis / dimension analysis：

- source strength：官方公司源、监管/政府 API、交易所/IR、可信第三方、客户/供应链官方披露，或经过 source lane allowlist 的 L3 proxy。
- binding：能绑定 issuer、product family、counterparty、industry 或 macro driver。
- citation：有 `evidence_ref` / `source_url` / `citation_span` / `raw_path`。
- boundary：明确不能支持哪些 exact claims。
- counter check：需要在 Research Lead 或 specialist 层识别反证、替代解释和 commercial tracker gap。

这类 row 的 runtime 标记为：

```json
{
  "non_financial_signal_authority": {
    "signal_authority_type": "technical_fact | customer_deployment_signal | supply_chain_signal | industry_operating_signal | ...",
    "promotion_level": "thesis_driver_allowed",
    "thesis_driver_authority": true,
    "exact_financial_fact_authority": false,
    "allowed_claim_types": ["deployment_signal", "product_capability_signal"],
    "forbidden_claim_types": ["product_revenue", "ASP", "market_share", "sell_through"]
  }
}
```

### 3. 弱信号只做 lead，不做结论

L4、论坛、自媒体、无法验证转述、未绑定来源、无 citation 的信息只能进入：

- `WeakSignalLead`
- `WeakSignalExclusionNote`
- targeted repair trigger

不能进入 core thesis、ClaimCard 或 Memo Writer 主体判断。

## Signal Card 类型

| 类型 | 典型来源 | 可支撑判断 | 禁止推断 |
| --- | --- | --- | --- |
| `TechnicalFactCard` | 官方产品页、datasheet、whitepaper、benchmark page | 产品规格、架构代际、竞品性能比较、技术路线 | 销量、收入、份额、ASP |
| `ProductGenerationSignalCard` | 官方 launch、产品页、架构资料 | 代际提升、替代周期、竞争壁垒 | 需求量和财务贡献 |
| `DeploymentSignalCard` | 客户/供应商官方新闻、云实例、公开采购、OEM 配置 | 客户采用、部署规模、需求 proxy、生态验证 | 订单金额、收入确认、客户集中度 exact |
| `SupplyChainValidationSignalCard` | 供应链官方新闻、合同披露、监管/海关/采购 | 供应链关系、产能/良率线索、交付可行性 | 公司销量、毛利、份额 |
| `IndustryOperatingMetricCard` | 公司披露的系统出货、RPO、ARR、AUM、capacity、utilization | 行业经营趋势、业务结构、产品线支撑 | SKU/product exact revenue，除非已披露 |
| `DeveloperEcosystemSignalCard` | 官方 GitHub/docs/npm/PyPI/HuggingFace | 开发者采用、技术生态、平台黏性 | 商业收入和份额 |
| `RegulatorySignalCard` | openFDA、ClinicalTrials、NHTSA、监管公告 | 审批、研发、召回、安全风险、产品存在性 | 销量、处方量、市场份额 |
| `MacroIndustryDriverCard` | FRED/EIA/Census/FDIC/BLS/BEA | 行业周期、成本、需求环境 | 单家公司具体收入/利润 |
| `MarketExpectationSignalCard` | 主流财经新闻、价格/估值快照、revision context | 预期变化、催化剂、风险偏好 | 事实发生或财务 exact |

## 数据源吸收框架

本层讨论后需要明确：数据源扩展不能只是“多接几个网站”，而要按投研/行研问题来定义 source route。每个新源进入系统前必须回答：

1. 支持哪类问题：财务、产品、行业、供应链、预期、资本结构、资金面、风险、估值。
2. 支持什么 claim：exact fact、operating metric、technical fact、deployment signal、supply-chain signal、market expectation signal、capital/funding fact、ownership context。
3. 禁止什么 claim：例如产品页不能写成销量，部署新闻不能写成收入，13F 不能写成实时买入，宏观利率不能写成公司收入。
4. 是否有实体绑定：issuer、product、customer、supplier、fund/holder、instrument、region、period、unit、citation。
5. 是否为领先信号：若是，应进入 `ThesisDriverAuthority` 或 targeted repair，而不是被降为 generic context。
6. 在关系图谱里能连到哪里：产品 -> 客户 -> 供应链 -> 产能 -> 财务桥接 -> 预期变化，或公司 -> 债务/股权/持仓 -> 资金面 -> 估值。

因此下一阶段数据源基座按 8 层吸收：

| 层 | 核心问题 | 典型来源 | Authority 口径 |
| --- | --- | --- | --- |
| 事实锚点层 | 公司到底披露了什么 | SEC/XBRL/10-K/10-Q/8-K/20-F/6-K、公司 IR、local exchange、年报、earnings release、transcript | exact fact / company disclosure authority |
| 公司经营层 | 业务是否真实运行 | 产品页、datasheet、catalog、pricing、status page、developer docs、App Store、GitHub/npm/PyPI/HuggingFace、ATS、公开采购、渠道 SKU | operating metric / technical fact / bounded proxy |
| Leading signal 层 | 市场预期可能为什么变化 | 新架构、新产品、benchmark、客户部署、供应链 ramp、云实例/OEM 配置、数据中心建设、产业会议、主流财经/产业媒体 | thesis driver signal；不得直接变成财务 exact |
| 行业/宏观/周期层 | 行业顺风还是逆风 | FRED/BLS/BEA/Census/EIA/FDIC、行业协会、监管统计、库存/价格/进出口 | macro / industry driver；不得证明单家公司财务 |
| 垂直行业专用层 | 每个行业真正看什么 | 半导体 HBM/CoWoS/云实例，医药 ClinicalTrials/openFDA，汽车 NHTSA/注册/车型，SaaS ARR/RPO/docs，金融 FDIC/call report | lane-specific source authority |
| 技术/IP/论文层 | 技术壁垒与研发路线 | PatentsView/USPTO、OpenAlex、论文、arXiv、标准组织、benchmark、开源生态 | technology research signal；不得证明商业成功 |
| 资本/融资/持仓/市场流动性层 | 钱从哪里来、谁在买卖、估值环境如何 | debt footnote、credit agreement、S-1/S-3/424B、13F/13D/13G、Form 3/4/5、DEF 14A、N-PORT、buyback、short interest、rates、credit spread、ETF/factor flows | capital fact / lagged ownership context / market liquidity driver |
| 商业 tracker 缺口层 | 公开源上限在哪里 | IDC/Gartner/Omdia、IQVIA、S&P Mobility、Circana/NielsenIQ、Sensor Tower/data.ai、consensus/revision | commercial gap；不能用公开 proxy 伪填 |

### Leading Signal Source Layer

Leading signal 的目标不是证明已发生的财务事实，而是在事实披露之前捕捉“预期可能如何形成”。它应独立建 source roles：

- `product_architecture_signal`：新架构、产品路线图、产品参数、MLPerf/SPEC/官方 benchmark。
- `yield_capacity_signal`：良率、HBM、CoWoS、先进封装、晶圆/封装产能、设备交付、产线 ramp。
- `customer_order_deployment_signal`：大客户订单、集群部署、云实例、公开采购、客户官方新闻。
- `supply_chain_ramp_signal`：TSMC、SK Hynix、Micron、Samsung、ASE、Amkor、Foxconn、Quanta、Supermicro 等上下游验证。
- `capex_buildout_signal`：hyperscaler capex、数据中心建设、用电并网、租赁、服务器采购、AI cluster 扩张。
- `market_expectation_signal`：主流财经媒体、产业媒体、管理层访谈、可信行业会议、分析师预期变化。
- `technology_ecosystem_signal`：CUDA/ROCm/TPU 生态、developer adoption、GitHub/HuggingFace/package/docs、客户迁移成本。

典型推理路径不是“信号 -> 结论”，而是：

```text
产品架构 / benchmark
-> 制造/封装/供应链可交付性
-> 客户部署 / 云实例 / OEM 配置
-> 需求可见度 / 竞争位置 / 供应约束
-> 财务桥接或预期变化
-> 反证、缺口和触发条件
```

### Capital / Funding / Ownership / Market Liquidity Layer

这层需要独立于普通财务分析，因为它既影响公司经营安全边际，也影响二级市场资金面和估值环境。

子层：

- `capital_structure_graph`：现金、短期投资、长短期债务、租赁负债、利息费用、maturity wall、covenant、credit facility、convertible、offering。
- `working_capital_liquidity`：应收账款、库存、应付账款、递延收入、operating cash flow、current ratio、quick ratio、cash conversion cycle、short-term debt / total debt。
- `ownership_control_graph`：13F、13D/13G、Form 3/4/5、DEF 14A、N-PORT/N-CEN、activist、insider transaction、buyback authorization / actual repurchase。
- `market_liquidity_driver`：price/volume/turnover、short interest、options implied volatility、ETF/factor flows、margin debt、rates、SOFR、Treasury yield curve、credit spread。
- `capital_market_event_signal`：rating change、debt refinancing、convert issuance、equity offering、M&A、dividend/buyback change、major holder change、covenant warning。

Authority 边界：

- debt footnote / credit agreement / offering filing 可以支持 exact capital fact。
- 13F 是季度滞后的 ownership context，不能写成实时资金流。
- Form 4 是 insider transaction fact，不能直接推断管理层观点。
- buyback authorization 不等于实际回购金额；实际回购需要披露行。
- 利率、credit spread、ETF/factor flow 是 market liquidity driver，不能证明公司基本面改善或恶化。

### Source Route 工程化

每个 source role 都必须走完整流水线：

```text
locator -> fetcher -> parser -> verifier -> authority mapper -> runtime row -> evidence graph
```

禁止直接把搜索结果、URL 存在、snippet、blocked page、弱转述当作完成。source gap 必须分成：

- `route_or_parser_debt`：公开源理论有，但当前 locator/fetcher/parser/verifier 没吃到。
- `signal_gap`：应有信号，但没有找到 parser-backed row。
- `signal_boundary`：有公开信息，但只能支撑方向/机制/预期，不能支撑 exact claim。
- `commercial_tracker_gap`：公开免费源确实拿不到，需要商业 tracker 或人工调研。
- `not_applicable`：该 source role 对公司/产品/行业不适用。

### Data Source / Adapter / Parser 准入矩阵

本阶段不能只写“需要哪些数据源”，还必须把每个数据源落到 adapter、parser、verifier 和 authority mapper。否则会把 URL、snippet、搜索结果、页面存在、blocked page 或弱转述拉进 evidence graph，形成半成品数据。

统一准入规则：

- `runtime_ready`：必须有 locator/fetcher/parser/verifier/authority mapper，且 row 至少包含 `issuer_or_entity_binding`、`source_role`、`source_layer`、`value_or_signal_payload`、`period_or_event_date`、`source_url/raw_path`、`citation_span_or_raw_ref`、`claim_scope`、`forbidden_claim_types`。
- `planning_only`：有可用 source route 或 seed，但还没有 parser-backed runtime row；只能进入 Research Lead source plan / targeted repair，不能进入 ClaimCard。
- `lead_only`：只有 L4、新闻线索、snippet、搜索结果、论坛/社媒、未绑定来源；只能生成 `WeakSignalLead` 或 repair attempt。
- `final_boundary`：必须有 attempt ledger 证明 locator/fetcher/parser/verifier 已尝试，且失败原因不是脚本没写、parser 漏吃或 route 没接。

当前已有和下一阶段需要统一注册的数据源如下：

| Source role | 典型来源 | 当前项目已有基础 | 下一阶段 adapter/parser 要求 | 可进入的 authority | 禁止 |
| --- | --- | --- | --- | --- | --- |
| `primary_company_disclosure` | SEC/XBRL/10-K/10-Q/8-K/20-F/6-K、earnings release、company IR、local exchange annual report | SEC/FSD、company-reported Product-KPI、non-US L1 和 local disclosure runtime rows 已有多轮 strict gate | 统一进 SourceRouteRegistry v2；补 IR deck / annual report PDF table / local exchange parser 的 route contract | exact financial fact / company disclosed Product-KPI / industry operating metric | 不得把 geography-only、percentage/change、total company、sentence relation 不足行冒充 product KPI |
| `official_product_surface` | 官方产品页、datasheet、catalog、pricing/configurator、IR product appendix | official product surface materializer、product slot graph、R17 product-family evidence canary 已有 | 对每个 product family 定义 URL locator、HTML/PDF table parser、spec normalizer、SKU/product binding verifier | technical fact / product generation / bounded product context | 不得推断销量、ASP、收入、份额、库存、sell-through |
| `technical_benchmark_signal` | MLPerf、SPEC、官方 benchmark、可信第三方 benchmark | R17 NVDA GB200 benchmark canary 已有 | 建 benchmark source allowlist、benchmark metric schema、competitor normalization、date/version verifier | competitive benchmark / product capability signal | 不得直接推断订单、收入或市场份额 |
| `customer_deployment_signal` | 客户官方新闻、supplier/customer official news、cloud instance availability、OEM configuration、公开集群部署 | R17 xAI deployment canary、targeted supply-chain official relationship rows 已有 | 建 official-customer / cloud-instance / OEM-config parser，绑定 customer、supplier、product family、event date、deployment scale boundary | deployment signal / demand visibility signal | 不得写成订单金额、收入贡献、backlog exact |
| `official_customer_order_or_deployment_event` | 公司/客户/供应商官方公告、客户案例、项目/部署/协议公告 | R21b 已从 `supplier_customer_official_news` 分拆出独立 contract，并物化 26 家 parser-backed event rows | 必须绑定 issuer、counterparty/customer、product/segment、event type/date/scale text；允许作为客户/订单/部署事件 fact 和 demand-context signal | official customer/order/deployment event fact / bounded demand signal | 不得冒充 `public_order_proxy` award exact、收入 exact、backlog exact、order book、shipment、ASP、sell-through、份额 |
| `supply_chain_ramp_signal` | TSMC/SK Hynix/Micron/Samsung/ASE/Amkor/Foxconn/Quanta/Supermicro/CoWoS/HBM/产能新闻 | V1 trusted external、targeted supply-chain rows 有基础 | 建 issuer/counterparty/product-family relationship parser、capacity/yield claim boundary、official/trusted-news source allowlist | supply-chain validation / capacity lead | 不得把供应链存在推成销量、毛利或公司份额 |
| `capex_buildout_signal` | hyperscaler capex、data center leases、power interconnect、server procurement、utility filings | 公司财务三表/SEC capex 基础已有；公开 API context 有 FRED/EIA | 建 capex row parser、customer spending capacity bridge、data-center project/utility/public-order route | capex / demand environment / customer spending capacity signal | 不得把 capex 直接写成供应商收入 |
| `public_order_proxy` | USAspending、公开采购、local tender、政府合同公告 | USAspending/broad public contract rows 和 local tender attempts 已有 | 统一 recipient/award/product binding；非美/local tender 需要司法辖区 adapter | public order proxy / demand context | 不得推断完整 commercial order book、backlog、revenue |
| `hiring_capacity_proxy` | Greenhouse/Lever/Workday/official careers/ATS | broad hiring / official careers rows 已有 | site-specific ATS parser、issuer-bound verifier、job taxonomy normalizer | hiring / capacity / operating intent signal | 不得推断 headcount、收入、订单 |
| `developer_ecosystem_proxy` | GitHub、npm、PyPI、HuggingFace、official docs/dev pages | developer ecosystem rows、official seed locator 已有 | official seed first；repo/package model card parser；publisher/issuer binding verifier | developer ecosystem / adoption signal | 不得推断 revenue、market share 或 enterprise adoption exact |
| `channel_offer_proxy` | CDW、Digi-Key、Mouser、Arrow、Amazon/JD/official store、authorized distributor | CDW/family channel rows 已有；其他 marketplace 多数未接 | 按 family 定义 distributor allowlist、SKU binding、price/availability boundary、anti-access failure reason | channel offer / SKU availability context | 不得推断 ASP、sell-through、inventory、sales volume |
| `regulated_product_context` | NHTSA、ClinicalTrials、openFDA、CMS、FDA animal/veterinary、recalls | official API projection / regulated rows 已有 | sponsor/applicant/product/vehicle/drug binding verifier；regulatory event schema | approval / trial / recall / safety / product-existence signal | 不得推断 prescriptions、sales、market share |
| `technology_research_proxy` | PatentsView/USPTO、OpenAlex、arXiv、standards org | OpenAlex/PatentsView attempts 和部分 rows 已有；credential/resolver gap 仍在 | assignee/topic/product-family resolver、paper/patent taxonomy、citation/date verifier | technology/research direction signal | 不得推断 commercial success |
| `macro_industry_driver` | FRED/EIA/FDIC/BLS/BEA/Census、行业协会、监管统计 | FRED/EIA/FDIC/official API context rows 有基础 | industry exposure bridge、ticker/segment/product-family mapping、period/unit normalizer | macro / industry driver | 不得证明单家公司收入/利润 |
| `trusted_market_expectation` | 主流财经/产业媒体、会议、management interview、guidance/news narrative | trusted news parser smoke 有基础 | source allowlist、issuer/product/event binding、article parser、expectation/catalyst taxonomy | market expectation / catalyst signal | 不得当官方事实或 exact financial value |
| `commercial_tracker_gap` | IDC/Gartner/Omdia、Visible Alpha/I/B/E/S、IQVIA、S&P Mobility、Circana/NielsenIQ、Sensor Tower/data.ai | 仅作为 gap taxonomy | 不接商用 API 时只能注册 gap 和公开 proxy 替代路径 | commercial gap / manual research gap | 禁止用公开 proxy 伪填商业 tracker exact |

AI / Semis first tranche 必须先从上述矩阵中选择 source roles 并做 registry + parser-backed row smoke。没有 parser-backed row 的源不能进入 specialist evidence bundle，只能进入 targeted repair plan。

### Data Source Admission Ledger

数据源处理阶段已经不是小阶段，必须维护独立台账，作为 Research Lead、SourceRouteRegistry、Eval 和人工审计共同读取的事实入口。台账粒度为：

```text
company x source_role x source_id
```

每行至少包含：

- 支撑面：fundamental、product/technology、industry/supply-chain、macro、capital/funding/ownership、market expectation、risk/regulatory。
- 是否公司特定：issuer/product/counterparty bound 还是行业/宏观/主题 context。
- 公司：ticker、company name、primary lane、industry schema、market region。
- 数据来源：source role、source id、source layer、sample URL / raw path / evidence refs。
- 数据概括：observed row count、parser row count、exact slot count、product family count、claim boundary。
- 是否可得：`runtime_ready_exact_or_bounded_slot`、`runtime_ready_context_or_signal`、`planning_only`、`route_or_parser_debt`、`attempt_backed_public_boundary`、`commercial_tracker_gap`。
- adapter/parser 状态：route source status、parser statuses、verifier / exact-authority violation、binding statuses。
- evidence 准入：`can_enter_evidence_bundle`；false 时只能进入 planning、targeted repair 或 gap ledger。
- next action：adapter/parser 修复、credential/access、local filing/parser、commercial tracker 或 not applicable。

本轮新增台账产物：

- `data/manifests/r18_data_source_admission_ledger_v0_1.jsonl`
- `data/manifests/r18_data_source_admission_ledger_summary_v0_1.json`
- `docs/internal/vnext_20260610/r18_data_source_admission_ledger.zh-CN.md`

台账 hard gate：

- `accepted_row_without_route_contract_count=0`
- `accepted_row_without_parser_or_verifier_count=0`
- `unbound_company_specific_accepted_row_count=0`
- `url_or_snippet_promoted_count=0`
- `forbidden_claim_violation_count=0`

后续所有 L1/L2/L3/L4 数据接入都必须先更新台账，再进入 full-chain 或 specialist evidence bundle。AI 行业只是第一批全链路验收对象，不代表 23 只覆盖 AI。

### AI / Semis 首批 source-route 接入门槛

允许先从 AI 行业做，但首批不能只做“公开源能搜到”。对每个代表 ticker / product family，至少要满足以下准入：

| 子领域 | 代表 family | 必须 source roles | 最低 runtime rows | 失败时状态 |
| --- | --- | --- | --- | --- |
| GPU / accelerator | H100/H200/B200/GB200、MI300/MI350、Gaudi、TPU | official product surface、technical benchmark、customer deployment 或 cloud/OEM config、supply-chain/capacity、capex/customer spending bridge | spec row + generation/benchmark row + deployment/supply/capex signal row | `route_or_parser_debt`，不得写成 final public boundary |
| Foundry / advanced packaging | N3/N2、CoWoS、advanced packaging、EUV layers | company disclosure、capacity/yield/capex signal、customer/supplier relationship、industry operating metric | capacity/capex/operating metric row + relationship row | `signal_gap` 或 `commercial_tracker_gap`，需 attempt ledger |
| Memory / HBM | HBM3E/HBM4、DRAM/NAND | product surface、supply-chain/customer official news、industry shipment/price proxy、capex/capacity | product/spec or official business-mix row + supply/customer signal | 不得用新闻直接推 revenue/share |
| Semicap | lithography、etch、deposition、metrology、inspection | company disclosure、product/catalog、customer/foundry capex bridge、industry operating metric | product/category row + unit/system/order/proxy row where disclosed | 未披露产品 KPI 时写 operating slot/gap |
| Networking / server OEM / power-cooling | Spectrum-X、switches、AI servers、liquid cooling、UPS/power | product surface、OEM config、public order/channel offer、customer deployment、capex/data-center buildout | product spec/offer row + deployment/order/capex context row | channel row 只能做 availability，不做 demand exact |
| EDA / IP | EDA tools、design IP、verification、compiler/software stack | company disclosure、developer/docs、customer/supplier official relationship、patent/research | product taxonomy row + ecosystem/customer/technology row | 不得用 docs/repo 推 ARR 或 market share |

首批 AI 行业验收不是“行数够”，而是：

- `route_contract_coverage=100%`：每个 required source role 都有 registry contract。
- `parser_backed_runtime_row_coverage>=最低要求`：每个代表 family 达到上表最低 rows。
- `unbound_row_count=0`：不能有未绑定 issuer/product/counterparty/period 的 row 进入 evidence bundle。
- `url_or_snippet_promoted_count=0`：URL、搜索结果、snippet、blocked page、弱新闻不能进入 ClaimCard。
- `forbidden_claim_violation_count=0`：任何 L2/L3 signal 不得支撑 revenue、ASP、share、sell-through、backlog、inventory、order value exact。
- `attempt_backed_gap_count=all_gaps`：所有缺口都必须有 attempt ledger 和 root cause，不能因为脚本没写就写公开源没有。

## 第二层与第三层通过标准

第二层和第三层不能再用“有 URL / 有 source role / 有几条 runtime rows”作为完成标准。必须同时满足三类 gate：

1. 数据覆盖 gate：目标公司、product family、source role、source id、source layer 和 public/commercial boundary 都在矩阵中可审计。
2. 解析质量 gate：进入 evidence bundle 的 row 必须 parser-backed，并有实体绑定、value 或 signal payload、period/event date、citation、claim boundary、forbidden claims。
3. 分析可用 gate：Specialist 和 Research Lead 能把 rows 组织成 dimension model，而不是 row summary；Memo 能写出判断、机制、反证和触发条件。

### 第二层：Product / KPI / Spec / Relationship Coverage Gate

第二层的目标不是继续堆产品页，而是形成可用于产品和业务真实面判断的四类数据：

- `ProductSpec`：产品参数、规格、架构、版本、性能、代际。
- `ProductKPI`：公司披露的产品/segment/operating metric，或明确的 public/commercial gap。
- `ProductRelationship`：竞争、替代、代际、上下游、客户部署、制造/代工、绑定关系。
- `ProductDeploymentSignal`：客户部署、云实例、OEM config、公开采购、渠道/分销 availability、benchmark。

公司级最低通过条件：

- `603/603` 公司必须有 `CompanyProductFamilyAssignment` 和至少一个可解释 product/business family slot；否则不能说产品层 coverage pass。
- 每家公司至少有 `official_product_surface` 或 `company_disclosed_taxonomy`，如果公开源确实没有，要有 attempt-backed `public_boundary`。
- 重点/深度研究公司至少有两个独立 source roles：例如 official product surface + technical spec，或 deployment + supply-chain relationship，或 channel offer + benchmark。

Product-family 级最低通过条件：

- 每个重点 family 必须有 schema。AI/Semis 先行 schema 包括：
  - GPU / accelerator：architecture、memory/HBM、bandwidth、interconnect、TDP/power、rack/server config、benchmark、generation edge。
  - CPU / server：core/thread、process node、socket/platform、memory channel、target workload、power envelope。
  - Server OEM / networking / power-cooling：GPU count、rack scale、switch/interconnect、cooling/power、configuration、deployment。
  - Foundry / semicap / memory / EDA-IP：process node、tool category、capacity/process applicability、customer/fab exposure、throughput/benchmark where disclosed。
- `technical_product_spec` 必须抽到 `spec_name/value/unit_or_enum/version/source_url/citation`；只抓产品页 URL 不算 spec exact。
- `product_generation_edge` 必须有 predecessor/successor 或 generation/version relation；不能只凭营销文案。
- `product_benchmark_proxy` 必须记录 benchmark source、metric name、value/unit、test context、comparison boundary。
- `customer_deployment_proxy` 必须绑定 issuer、customer/counterparty、product family、event date、deployment scope text，并明确不得推断 order value / revenue / backlog。

ProductRelationshipGraph 通过条件：

- edge 必须有 `edge_type`、source authority、confidence、evidence refs、forbidden claims。
- 核心 edge types 至少覆盖：`competes_with`、`generation_successor`、`substitutes`、`supplier_to`、`customer_deployed_by`、`bundled_with`、`fabbed_by` / `manufactured_by`。
- AI/Semis 代表链条必须能回答：NVDA/AMD/GOOGL TPU/INTC 谁与谁竞争；TSM/ASML/SK Hynix/Micron/ASE/Amkor/Quanta/DELL/SMCI/ANET/VRT 等在供应链或客户部署中处于什么位置。

Product-KPI 通过条件：

- Product-KPI 不再只有 `product_revenue exact` 一种状态，而要分为：
  - `product_kpi_exact_ready`
  - `business_segment_metric_ready`
  - `technical_spec_ready`
  - `deployment_signal_ready`
  - `channel_proxy_ready`
  - `benchmark_signal_ready`
  - `commercial_tracker_gap`
- 没有 SKU/product revenue 时，不能把分析写成“不能判断”；必须用产品规格、客户部署、benchmark、渠道 availability、供应链关系支撑 bounded thesis，并把 revenue/ASP/share/sell-through/backlog 留作 exact/commercial gap。
- 对每个 product family，所有 gap 都必须是 `route_or_parser_debt`、`signal_boundary`、`commercial_tracker_gap`、`not_applicable` 或 `attempt_backed_public_boundary`，不能有 unclassified gap。

### 第三层：Capital / Funding / Ownership / Market Liquidity Coverage Gate

第三层目标不是把资本市场 metadata 拉进来，而是形成 `CapitalFlowPack` 和条款级 parser 能力。

公司级最低通过条件：

- 每家公司应尽量有 cash、debt/short-term debt、current assets/current liabilities、operating cash flow、capex/investing cash flow、financing cash flow；非美或 SEC CompanyFacts 不覆盖时必须走 local exchange / IR annual report parser。
- 如果公司公开披露缺失，必须记录是 local filing parser debt、issuer disclosure gap、commercial source gap，还是 not applicable。

Capital event parser 通过条件：

- `securities_offering_filing_event` 当前只证明 event metadata。要进入 exact，必须解析出 amount、security type、coupon/rate、maturity、conversion terms、use of proceeds、filing date、citation。
- `insider_transaction_filing_event` 当前只证明 Form 3/4/5/144 event。要进入 exact，必须解析 shares、price、transaction code、direct/indirect ownership、post-transaction holding、event date、citation。
- `beneficial_ownership_filing_event` 当前只证明 13D/13G event。要进入 exact，必须解析 reporting person、beneficial ownership percentage、shares、event date、activist/passive boundary、citation。
- `proxy_governance_filing_event` 当前只证明 proxy/governance event。要进入 exact，必须解析 buyback authorization / actual repurchase、compensation table、vote result、board/governance event、citation。

Market / ownership / liquidity 通过条件：

- 13F 只能是 lagged ownership context；不得写成实时资金流。
- N-PORT/fund holdings、short interest、options IV/volume、ETF/factor exposure、credit spread、rates/liquidity/turnover 进入 `MarketLiquidityDriver`，不能证明公司经营事实。
- 每个 market/liquidity signal 必须有 timestamp、lag policy、instrument/entity binding 和 forbidden claims。

### FundamentalPeerStatementPanel

当前项目已有 `FundamentalStatementPack`、三表 taxonomy、industry focus policy、period changes 和 peer comparisons，但还不足以达到研报级财报分析。第三层计划必须显式补 `FundamentalPeerStatementPanel`，作为 Fundamental specialist、Capital specialist 和 MemoLogicPlan 的共同输入。

`FundamentalPeerStatementPanel` 包含：

- `ThreeStatementMetricPanel`：公司自身多期三表，覆盖 income statement、balance sheet、cash flow statement。
- `PeerComparableMetricPanel`：同行同口径同期间比较，包含 peer set 来源、口径一致性和缺失字段。
- `IndustryFinancialFocusPolicy`：按行业决定重点科目和派生指标，而不是所有公司套同一张表。
- `DerivedMetricLayer`：gross margin、operating margin、FCF margin、capex intensity、R&D intensity、current ratio、quick ratio、net debt、DSO、DPO、DIO、cash conversion cycle、working-capital drag、interest coverage、deferred revenue growth 等。
- `ProductFinancialBridge`：产品/segment/KPI、产品规格/部署信号与 revenue、gross margin、inventory、capex、deferred revenue、RPO/backlog 等科目的桥。
- `CapitalFundingBridge`：capex、OCF/FCF、cash、debt maturity、credit facility、offering/repurchase/insider/ownership event 与融资能力、稀释和风险触发的桥。
- `StatementAnomalyDetector`：库存、应收、递延收入、应付、短债、现金流、capex、融资现金流等异常变化及同行偏离。

财报分析通过条件：

- 标准 memo 必须至少覆盖三表中的两个，深度 memo 必须覆盖三表全部。
- 深度 memo 必须有同行同口径 panel；若没有同行数据，Research Lead 必须标为 `retrievable_gap` 或 `bounded_gap`，不能静默跳过。
- 行业 focus policy 必须决定重点指标：例如银行看 NII/deposits/loans/CET1/provision/NIM；SaaS 看 deferred revenue/RPO/ARR/subscriber/S&M/FCF conversion；重资产看 capex/debt maturity/interest/cash/inventory；零售餐饮看 same-store sales/inventory/lease/working capital；医药看 R&D/trial milestone/cash runway。
- 财务判断必须和产品、行业、资本三层联动：产品信号是否被 revenue/margin/capex/cash flow 支持；订单/部署是否反映到 deferred revenue/backlog/working capital；capex 是否有 OCF/FCF/debt capacity 支撑；同行库存/毛利变化是否验证产品周期。

## 专业研报范式可吸收内容

顶级投行或成熟买方报告的价值不在于格式长，而在于它们围绕“投资争议、预期差、驱动因素、反证和估值桥”组织信息。公开可参考的框架包括 CFA Research Challenge report essentials、MSCI/S&P GICS、IFRS/SASB industry metrics、FactSet RBICS/Revere、LSEG I/B/E/S、Visible Alpha KPI guides 等。它们启发的是系统结构，不代表本项目会接入这些商业数据。

### 公开成熟机构研报抽样复盘

本轮额外抽样了部分公开可访问的成熟机构材料，目的不是学习版式，而是拆解“专业报告怎样把信息变成可交易/可研究的判断结构”：

| 公开材料 | 观察到的有效结构 | 对本项目的吸收方式 |
| --- | --- | --- |
| [Goldman Sachs Top of Mind](https://www.goldmansachs.com/insights/top-of-mind) | 先定义投资者、企业和政策制定者真正关心的 macro / market debate，再组织观点和反方 | Research Lead 不能只派发“找资料”，必须先产出 `TopOfMindQuestionSet` / `InvestmentDebateContract` |
| [Morgan Stanley - Bridging a $1.5tr Data Center Financing Gap](https://www.morganstanley.com/content/dam/msdotcom/en/assets/pdfs/Research_Bridging-Data-Center-Gap.pdf) | 把 AI infrastructure demand、hyperscaler capex、cash flow、credit/private credit/ABS/CMBS 融资能力和 ROI 风险串成一条资金桥 | 新增 `CapexFundingBridge` 和 `CustomerSpendingCapacityGraph`，避免 AI infra 只写产品/订单，缺少资金约束和回报口径 |
| [Morgan Stanley - The Humanoid 100](https://advisor.morganstanley.com/john.howard/documents/field/j/jo/john-howard/The_Humanoid_100_-_Mapping_the_Humanoid_Robot_Value_Chain.pdf) | 先把主题拆成价值链和 paths to expression，再给 public equities 标注参与环节、当前参与证据、潜在受益路径和流动性 | 新增 `ThemeToExpressionGraph`、`BeneficiaryAndEnablerMap`、`ExposureConfidence`，用于 AI、robotics、EV、GLP-1 等主题型行研 |
| [UBS House View - March 2026](https://advisors.ubs.com/mediahandler/media/785564/UBS%20House%20View%20for%20March%202026.pdf) | 用 bull/base/risk case 讨论 AI capex、operating cash flow、外部融资、资产类别波动和 sector risk-reward | 强化 `ScenarioAndSensitivity`、`RiskRewardMap`、`ValueChainLayerMap`，把资金压力和风险回报写进 memo 主体 |
| [Morgan Stanley All-Asia Research / AlphaWise](https://www.morganstanley.com/asiaresearch/assets/pdf/morgan-stanley-2025-all-asia-research-brochure.pdf) | 把 primary research、survey、web intelligence、quant/data visualization 和传统宏观/行业研究结合，补宏观数据看不到的分布和压力 | 公共源策略应模拟 primary research 的形态：招聘、公开采购、App/review、渠道 SKU、官网 docs、公开问卷/监管统计作为 bounded proxy，并进入 `SourceConfidenceLedger` |

抽样结论：

- 成熟报告不是“列证据然后写结论”，而是先有 debate / theme / expression / scenario / trigger。
- 对 AI infra、半导体、机器人这类主题，产品/供应链/客户部署信号必须能进入 thesis driver；只等产品收入、销量、ASP、份额披露会错过预期形成过程。
- 对高 capex 行业，不能只看产品需求，还要看客户现金流、债务/租赁/ABS/credit capacity、shareholder return pressure、WACC 和资金市场环境。
- 对主题型行研，必须把“谁最直接受益、谁只是间接受益、谁只有潜在暴露”写成可审计图谱，而不是让模型凭语感说受益。
- 成熟机构常用的 primary/proprietary research 在本项目不能伪造；公开策略下要把可合法访问的公共 proxy 做成 bounded signal，并把需要商业源或人工调研的部分写入 gap。

因此 23 后续新增对象：

| 对象 | 目的 | 最小字段 |
| --- | --- | --- |
| `TopOfMindQuestionSet` | 把用户问题转成真正的投资争议和必须回答的问题 | `core_debate`、`why_now`、`market_assumption`、`required_dimensions`、`what_would_change_view` |
| `ThemeToExpressionGraph` | 从主题到股票/公司/产品/供应链环节的表达路径 | `theme`、`value_chain_layer`、`issuer`、`product_family`、`exposure_type`、`evidence_refs` |
| `BeneficiaryAndEnablerMap` | 区分直接受益方、基础设施/工具/供应链 enabler、潜在参与方 | `issuer`、`role`、`current_involvement`、`potential_involvement`、`confidence` |
| `ExposureConfidence` | 避免把“可能有关”写成“确定受益” | `exposure_level`、`binding_strength`、`source_strength`、`commercial_gap`、`counter_evidence` |
| `CapexFundingBridge` | 把 capex 需求、现金流、债务/租赁/融资工具和 ROI 连接起来 | `buyer_or_issuer`、`capex_need`、`operating_cash_flow`、`debt_or_lease_capacity`、`funding_gap`、`roi_risk` |
| `CustomerSpendingCapacityGraph` | 判断客户订单/部署是否有可持续资金来源 | `customer`、`supplier/product`、`capex_budget`、`cash_flow`、`financing_source`、`deployment_signal` |
| `ValueChainLayerMap` | 将产业链分层后再判断竞争/受益 | `theme`、`layer`、`subvertical`、`product_family`、`issuer_universe`、`key_kpi` |
| `CrowdingAndPositioningSignal` | 处理资金拥挤、持仓和预期反身性 | `holder_flow`、`short_interest`、`options_signal`、`price_reaction`、`revision_context` |

### 报告组织层

高质量报告不应只是证据卡拼接，而应至少显式生成以下对象：

| 对象 | 投研含义 | 数据/图谱支撑 |
| --- | --- | --- |
| `InvestmentDebate` | 市场当前在争什么，核心分歧是什么，哪些变量最可能改变观点 | consensus / guidance / price reaction / news narrative / earnings-call Q&A / gap ledger |
| `VariantPerception` | 我们和市场预期的差异在哪里，差异由什么证据支持 | estimate/revision graph、leading-signal graph、industry KPI bridge |
| `DriverTree` | 结论不是单个 claim，而是多个 driver 的因果树 | financial statement pack、product graph、supply-chain graph、macro/factor graph |
| `CatalystPath` | 哪些事件会触发重估或证伪 | earnings、product launch、investor day、trial readout、regulatory action、debt maturity、Fed/macro data |
| `ScenarioAndSensitivity` | bull/base/bear 的关键假设和敏感性 | segment/KPI model、valuation comps、rates/WACC、gross margin/volume/price/mix |
| `RiskRewardMap` | 上行/下行空间、反证、止损条件和 what-would-change-view | counter-thesis graph、risk/legal/regulatory graph、liquidity graph |
| `ValuationBridge` | 从业务判断到估值的桥，而不是直接给目标价 | DCF/multiple/SOTP、peer comps、capital cost、estimate delta |
| `SourceConfidenceLedger` | 哪些判断来自 exact fact，哪些来自 signal，哪些只是 lead/gap | authority mapper、attempt ledger、commercial gap register |

### 专业研报常用信息源形态

除 8 层数据源外，需要补一类“研报工作流源”：

- consensus / estimate / revision：I/B/E/S、Visible Alpha、FactSet、Capital IQ、Bloomberg、LSEG 等商业源；公开策略下只能用公司 guidance、公开 consensus、新闻转述、价格反应和公开模型片段做 proxy。
- company access / management read：earnings call Q&A、investor day、conference presentation、management interview、IR FAQ；必须记录 issuer-authored 或 journalist/interview boundary。
- channel checks / primary research：distributor checks、store checks、expert calls、surveys、web/app traffic、job postings、procurement、reseller SKU；公开策略下只能使用可合法访问的公开页面/API/采购公告/评论/招聘，不把它们写成 exact sales。
- industry KPI model：每个行业的关键 operating metrics。可参考 SASB industry metrics、Visible Alpha KPI guides、公司 disclosure、行业协会公开数据，形成内部 `IndustryKPIPlaybook`。
- peer/comp set source：GICS/ICB/RBICS、内部 product-family taxonomy、segment revenue exposure；单一 GICS 不够，必须叠加产品族和业务模型可比性。
- ownership/flow/positioning：13F、13D/13G、Form 4、fund holdings、short interest、ETF/factor flow、options IV；13F/基金披露有时滞，不得写成实时资金流。
- alternative / leading data：satellite、web traffic、credit card、app revenue、POS、mobility、channel inventory 等大多属于商业或受限数据；公开策略下只能暴露 commercial gap 或用低权重 proxy。

### 成熟关系图谱清单

下一阶段 KG 不应只有公司-产品关系，至少应包含：

| 图谱 | 核心节点/边 | 作用 |
| --- | --- | --- |
| `IssuerSecurityEntityGraph` | issuer、security、CIK/LEI/ISIN、subsidiary、listing、ADR/FPI、local exchange entity | 解决同一公司多市场、多证券、多披露口径 |
| `IndustryTaxonomyGraph` | GICS/ICB/RBICS-like industry、internal vertical lane、product family、business model | 解决同行可比和行业 playbook 选择 |
| `SegmentRevenueExposureGraph` | company -> segment/product/geography/end-market -> revenue/operating metric | 连接财报 segment 与真实业务暴露 |
| `ProductTechnologyGraph` | product、architecture、generation、spec、benchmark、competitor、replacement cycle | 支撑产品规格、竞品和技术路线分析 |
| `CustomerSupplierPartnerGraph` | customer、supplier、partner、OEM、foundry、distributor、relationship type、confidence、revenue dependency | 支撑供应链、客户部署和 read-through |
| `CapitalStructureInstrumentGraph` | debt instrument、credit facility、convertible、lease、maturity、rate、covenant、offering | 支撑融资成本、到期墙、稀释和再融资风险 |
| `OwnershipFlowGraph` | manager/fund/insider/activist -> holding/trade/filing -> issuer/security | 支撑股权结构、持仓变化、activist、资金面，但保留时滞边界 |
| `EstimateExpectationGraph` | guidance、consensus、revision、price reaction、implied expectation、key KPI estimate | 支撑预期差、revision 和 variant perception |
| `CatalystEventGraph` | earnings、product launch、regulatory decision、trial readout、macro release、debt maturity、lockup | 支撑 catalyst path 和 scenario timing |
| `MacroFactorExposureGraph` | rate、FX、commodity、energy、credit spread、PMI、employment、demand proxy -> company/industry exposure | 支撑宏观驱动和估值环境 |
| `RiskRegulatoryLegalGraph` | litigation、recall、FDA/NHTSA/FTC/DOJ/SEC action、safety event、cyber incident | 支撑风险和反证 |
| `GovernanceIncentiveGraph` | management、board、compensation KPI、insider ownership、capital allocation history | 支撑管理层质量和资本配置判断 |

### Agent 输出应学习的研报质量标准

Research Lead 必须先产出 `InvestmentDebateContract`，而不是直接派发“找资料”：

- 核心问题和投资争议。
- 必答维度：财务、产品、行业/供应链、资本/融资/持仓、宏观/流动性、估值、风险。
- 关键模型变量：volume / price / mix / margin / capex / working capital / WACC / multiple / share count。
- 市场预期变量：consensus、guidance、revision、positioning、implied expectation。
- 必须寻找的 leading signals 和反证。
- 哪些结论只能写成 boundary 或 commercial gap。

Specialist 必须输出 dimension model，而不是 row summary：

- Fundamental：三表 + peer + industry KPI + 产品/资本桥。
- Product/Technology：产品族、规格、代际、竞品、部署、生态和商业化桥。
- Industry/Supply Chain：客户/供应商/产能/渠道/订单 proxy 和 read-through。
- Capital/Ownership：融资成本、负债结构、营运资本、持仓、回购/发行/稀释。
- Market/Valuation：预期、估值、资金面、利率/credit spread、scenario/sensitivity。
- Risk/Counter-thesis：反证、替代解释、数据缺口、证伪触发条件。

Memo Writer 只能负责表达，但必须按以下结构组织自然语言：

```text
核心判断
-> 为什么现在重要
-> 主要驱动和证据
-> 预期差 / 市场可能没充分反映什么
-> 估值和情景桥
-> 反证、缺口和触发条件
```

## Runtime 实现状态

已新增：

- `src/sec_agent/non_financial_signal_authority.py`
  - `classify_non_financial_signal_authority`
  - `attach_non_financial_signal_authority`
  - `validate_signal_claim_authority`
- `src/sec_agent/runtime_source_context_store.py`
  - selected rows 自动附加 `non_financial_signal_authority`
  - summary 新增 `by_signal_authority_type`、`by_signal_promotion_level`、`thesis_driver_authority_row_count`
- `scripts/data_expansion/build_r17_product_family_evidence_rows.py`
  - R17 rows 物化时直接带 `signal_authority_type`、`thesis_driver_authority`、`allowed_non_financial_claims`
- `src/sec_agent/specialist_llm.py`
  - Specialist prompt 明确 `thesis_driver_authority=true` rows 可以支撑 bounded thesis driver
  - bounded rows 透传 signal authority 字段
  - Product/Technology memo-ready requirement 从“public proxy rows stay context or gap”改为“不能做 exact KPI，但强信号必须转成产品/技术/需求 proxy insight”
- `src/sec_agent/multi_agent_contracts.py`
  - ClaimCard / ThesisDriverPack 保留 `signal_authority_type`、`signal_promotion_level`、`thesis_driver_authority` 和 `claim_boundary`
- `src/sec_agent/source_route_registry_v2.py`
  - `SourceRouteContract`
  - `SOURCE_ROUTE_CONTRACTS`
  - `map_signal_authority_from_admission_row`
- `scripts/data_expansion/build_r18_data_source_admission_ledger.py`
  - 生成 `company x source_role x source_id` 数据源准入台账
  - 将 company coverage、exact-slot coverage、source-route attempt ledger 和 vertical registry 合并成可审计入口
- `scripts/data_expansion/build_r18_source_route_registry_v2.py`
  - 生成 `SourceRouteRegistry v2`
  - 生成 `SignalAuthorityMapper v0.2` coverage matrix
  - 检查 accepted evidence rows 是否都能反查 registry / required fields

当前 R17 product-family evidence 重建结果：

- `runtime_row_count=24`
- `by_signal_promotion_level.thesis_driver_allowed=24`
- `thesis_driver_authority_row_count=24`
- `public_exact_authority_violation_count=0`

这说明 NVDA H100/GB200 specs、xAI Colossus deployment、GB200 benchmark/generation、MSFT Azure metric、ASML/TEL semicap operating metrics、Hon Hai business mix 可以作为非财务/经营 thesis driver 进入分析，但仍不能替代 Product-KPI exact。

当前 R18 数据源准入台账与 registry 结果：

- `r18_data_source_admission_ledger_v0_1`
  - `company_count=603`
  - `row_count=3,746`
  - `can_enter_evidence_bundle_count=3,649`
  - `not_evidence_ready_count=97`
  - `source_role_count=16`
  - `source_id_count=25`
  - hard gate 全为 0：无 accepted row 缺 route contract、parser/verifier、company-specific binding、或 forbidden claim violation。
- `r18_source_route_registry_v2`
  - `registry_source_role_count=16`
  - `signal_matrix_row_count=3,746`
  - `evidence_bundle_allowed_count=3,649`
  - `planning_or_gap_only_count=97`
  - authority split：`exact_company_fact_authority=865`，`bounded_thesis_driver_authority=2,881`
  - hard gate 全为 0：无未注册 source role、无 evidence row 缺 registry、无 evidence row 缺 required fields、无 non-evidence row 被误标 allowed。
- 2026-06-23 修正：admission ledger 不再把同一 source role 下未观测到的 sibling `source_id` 一起展开为 evidence-ready row。新的 `3,746` 行是收紧后的 canonical row count，代表每条 source-role 只保留实际观测或 exact-slot 支撑的 source id。

2026-06-23 进一步更新：

- `SourceAuthorityCoverage` 已进入 Research Lead / LeadReviewCheckpoint 默认输入。Lead 不再只看 ClaimCards 或 exact coverage，而会读取 `r18_signal_authority_coverage_matrix_v0_2`，按维度给出可用 source role、source id、authority type、repairability、forbidden claim types 和 probe order。
- `LeadReviewCheckpoint` 现在会把“没有 ClaimCard 但 R18 matrix 显示存在 parser-backed / repairable source authority”的维度标为 `retrievable_gap`，并生成 targeted repair plan；Memo directive 同时区分 exact fact dimension、thesis-driver dimension、repair-first dimension 和 boundary-only dimension。
- AI/Semis first-tranche source-route gate 已落地并通过 deterministic strict gate：`56` 个 V1 product-family assignments 中 `56` 个 pass、`0` 个 action_required。hard gate 中 `unregistered_required_source_role_count=0`、`url_or_snippet_promoted_count=0`、`forbidden_claim_violation_count=0`。
- 本轮修复不是放宽门槛：一是修正 gate 只按 company `primary_lane_id=V1` 过滤 matrix rows 的错误，使 VRT/PWR/ETN 等跨 lane AI infrastructure suppliers 可使用自身 parser-backed disclosure/product/macro rows；二是把 AEHR 官网披露的 hyperscale AI customer production-order relationship materialize 为 `supply_chain_official_relationship` bounded row，并保持 no revenue / backlog / order-value / share inference 边界。

### 最新进度复盘

截至本轮文档更新，已经做到：

- R15-R17：603 公司 L1/L2/L3 source lane、exact-slot matrix、Product-KPI diagnostic、source-role closeout、R17 SourceRouteAttemptLedger 和 known-public canary 已形成可审计底座。
- R17：DECK current-contract Product-KPI canary 已修；NVDA/MSFT/ASML/TEL/Hon Hai new-contract canary 已进入 ProductFamilyEvidence runtime rows。
- R18/23：`NonFinancialSignalAuthority` 已进入 runtime store、R17 row builder、specialist prompt、ClaimCard / ThesisDriverPack；R17 `24/24` rows 为 `thesis_driver_allowed`。
- R18：Data Source Admission Ledger v0.1 覆盖 `603` 公司；SourceRouteRegistry v2 / SignalAuthorityMapper v0.2 覆盖 `16` source roles / `25` observed source ids。2026-06-23 已修复 source-id 误展开，canonical evidence-ready rows 为 `3,649`。
- R18：Research Lead / LeadReviewCheckpoint 已默认消费 signal authority coverage，并能把缺 ClaimCard 但有可修 source authority 的维度推进 targeted repair。
- AI/Semis：first-tranche source-route gate 已落地并 strict pass，当前为 `56/56` pass、`0/56` action_required。
- 已验证：targeted tests、R17 product-family evidence strict `status=pass`；R17 ledger strict `unclassified_count=0`、known-public canary 全覆盖；R18 admission ledger strict `status=pass`；R18 registry strict `status=pass`；R18 data mart strict `status=pass`；R18 vertical source-route gate hard gate `0`；SourceAuthorityCoverage / AI-Semis gate targeted tests 通过。

仍未完成：

- AI/Semis first-tranche source-route gate 已全绿，但这只证明首批 product-family source-route readiness，不等于 AI/Semis full-chain memo/eval 已通过。
- `LeadingSignalSourceLayer` 还未按 software / healthcare / auto / financials 等 lane 全量建真实 source routes；AI/Semis 已有首批 source-route gate 通过，后续还要补完整 signal layer contracts 和 full-chain eval。
- `Capital / Funding / Ownership / Market Liquidity Layer` 还未建 debt/offering/ownership/flow/liquidity 的 source contracts、runtime rows 和 graph edges。
- Research Lead 已消费 signal authority coverage，但 InvestmentDebateContract / DimensionModel / valuation bridge 还未把这种 coverage 转成 full-chain 级别的研究主编监督闭环。
- full-chain eval 尚未验证 Memo 是否能把 strong signals 写成有判断、有机制、有边界的报告，而不是 caveat-heavy gap prose。

## Research Lead 与 specialist 使用规则

Research Lead 需要把问题拆成多维目标，而不是只问“有没有财务 exact fact”：

- 财务/基本面：三表、会计科目、同行比较、行业重点指标。
- 产品/技术：规格、代际、产品族、竞品、性能、部署、生态。
- 行业/供应链：上下游关系、客户部署、产能、公开订单、监管/政府数据。
- 宏观/周期：利率、能源、行业需求、监管环境。
- 市场/预期：新闻、估值、revision、事件催化。
- 资本/融资/持仓/市场流动性：债务工具、融资成本、营运资本、长短债占比、机构/私募/insider 持仓、short interest、资金流、利率和 credit spread。

LeadReviewCheckpoint 必须把缺口分成：

- `exact_fact_gap`：必须 exact，但没有 disclosure / tracker。
- `signal_gap`：应有公开信号但没找到或没解析。
- `signal_boundary`：有信号，但只能作为方向/机制，不能变成 exact claim。
- `commercial_tracker_gap`：需要 IDC/IQVIA/S&P Mobility/POS/consensus 等商业数据。

Specialist 输出时：

- 有强信号：写成“信号 -> 机制 -> 对 thesis 的影响 -> 需要什么反证/确认”。
- 没 exact fact：不要把半段观点都写成“不能判断”；只在边界处说明不能推断哪些 exact 指标。
- 有弱信号：只写 targeted repair/gap，不进入核心判断。

Memo Writer 只能消费 verified ClaimCards / ThesisDriverPack / JudgmentState，不再直接解释 raw rows。但它必须把 signal cards 写成自然语言投资判断，而不是内部字段堆砌。

## Eval Gate

新增或更新的 gate：

- 非财务信号不得支持 exact product KPI / financial fact。
- `thesis_driver_authority=true` row 在 Product/Technology / Industry / Market 维度不能被自动降成 generic gap。
- Memo 正文不得把 `signal_authority_type`、`promotion_level` 这类内部字段直接渲染给用户。
- 强信号输出必须包含：
  - 结论方向；
  - 机制链；
  - cited evidence；
  - claim boundary；
  - what would change the view。
- 弱信号输出必须停在 lead/gap，不得成为 core thesis。

## 下一阶段实施规划

当前事实基线：

- 已验证：R15-R17 source-role/Product-KPI/source-route attempt ledger 和 R17 canary 可运行；R18 `NonFinancialSignalAuthority` 最小 runtime 合同通过 targeted tests；R17 product-family evidence `24/24` rows 已可作为 `thesis_driver_allowed`。
- 已验证：R17 以外全量 R18 台账行已经批量映射 signal authority，SourceRouteRegistry v2 strict pass，Research Lead / LeadReviewCheckpoint 能读取 SourceAuthorityCoverage 并触发 targeted repair。
- 已验证：AI/Semis first-tranche source-route gate `56/56` pass，R18 matrix / registry / Research Lead consumption 能支撑首批 source-route readiness。
- 未验证：Research Lead 还未以 InvestmentDebate / DimensionModel / valuation bridge 完成 full-chain 级监督；LeadingSignalSourceLayer 的完整 signal object family、Capital/Funding/Ownership/MarketLiquidityLayer、ThemeToExpressionGraph 和 CapexFundingBridge 还没有完整 runtime 合同；full-chain memo 还没证明能把强信号写成高信息密度判断。
- 工程约束：不能把公开 proxy 伪装成 exact financial/product KPI；不能用弱 fallback 隐藏 parser/source route 问题；每个 source role 必须有 locator/fetcher/parser/verifier/authority mapper/runtime row/eval gate。

### Phase 0：冻结当前可用事实基线

目标：先把当前项目的真实能力和缺口固化，不再依赖聊天记忆。

交付：

- 生成 `R18CurrentCapabilitySnapshot`：列出 accepted manifests、runtime rows、exact-slot coverage、R17/R18 tests、未完成 CG 项。
- 将 R17/R18 source authority schema 写入 registry fixture，作为后续批量升级的 contract baseline。
- 明确不作为证据的材料：closeout rows、attempt rows、blocked pages、URL-only rows、L4 leads。
- 生成 `R18DataSourceAdmissionLedger`：把 600+ 公司按 support surface、company-specific、source role/source id、availability、adapter/parser/verifier status、gap root cause 统一入账。

通过条件：

- 当前 targeted tests、R17 strict、ledger strict 和 `git diff --check` 可复现。
- snapshot 中每个未完成项都有 owner artifact、阻塞原因和下一步 gate。
- 台账覆盖 `600+` 公司，且每个 accepted evidence row 都能反查 source role、source id、parser/verifier 和 authority boundary。

### Phase 1：全量 L2/L3 `NonFinancialSignalAuthority` 批量映射

目标：把 R17 canary 的 authority 机制扩展到所有已物化 L2/L3 source-role rows。

范围：

- developer ecosystem、hiring、public order、regulated product、channel offer、supply-chain official relationship、trusted news、PatentsView/OpenAlex、macro/industry API、official product surface、app/review、channel/distributor。

交付：

- `SignalAuthorityMapper v0.2`：按 source role / layer / binding / citation / parser status 赋予 signal authority。
- `signal_authority_coverage_matrix_v0_1`：按 ticker、lane、source role、authority type、promotion level、forbidden claim types 统计。
- fail-closed verifier：任何 L2/L3 row 不能支持产品收入、销量、ASP、份额、sell-through、backlog、订单金额等 exact claim。
- `source_adapter_parser_readiness_matrix_v0_1`：每个 accepted row 必须能反查 adapter、parser、verifier、authority mapper 和 source-route attempt。

通过条件：

- 全量 L2/L3 rows `unclassified_authority_count=0`。
- `exact_financial_authority_violation_count=0`。
- `accepted_row_without_route_contract_count=0`。
- `accepted_row_without_parser_or_verifier_count=0`。
- Research Lead 可读取 signal authority summary，而不是只看 exact-slot coverage。

2026-06-23 状态：已完成 R18 matrix 构建与 Research Lead 读取；后续不再把“Research Lead 看不到 signal coverage”作为问题，剩余问题转为具体 source-route/parser repair 和 full-chain memo/eval。

2026-06-23 数据源台账更新：新增 `r18_source_authority_data_mart_v0_1`，把 `R18DataSourceAdmissionLedger` 与 `SignalAuthorityMapper v0.2` 合并成 Research Lead / eval / frontend 可共享的数据源台账视图。

- 产物：`data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl`、`data/manifests/r18_source_authority_data_mart_summary_v0_1.json`、`docs/internal/vnext_20260610/r18_source_authority_data_mart.zh-CN.md`。
- 当前结果：`company_count=603`，`row_count=3,746`，`evidence_bundle_allowed_count=3,649`，`planning_or_gap_only_count=97`。
- authority 分层：`exact_company_fact_authority=865`，`bounded_thesis_driver_authority=2,881`；admission tier 中另有 `route_or_parser_debt=27`、`attempt_backed_public_boundary=70`。
- source layer：`L1=1,131`，`L2=1,976`，`L3=639`。
- hard gate：`flag_count=0`；每条 accepted row 都有 source role、source id、source layer、claim boundary、authority mode、signal authority type、citation/ref，以及 parser/exact-slot 依据。
- 本轮修正：`channel_offer_proxy` 纳入 `channel_distributor_locator`，`auto_product_identity_context` 对非美车企接受 official model/product page，但 exact contract 只允许 V5/auto ticker allowlist 和 auto-specific product page，避免 `Automatic` / `Autodesk` / `Automation` 误入 auto identity。

该台账是后续“数据源是否真的接入”的唯一 canonical view：`can_enter_evidence_bundle=false` 的行只能进入 Research Lead planning / targeted repair / gap ledger，不能进入 ClaimCard 或 Memo 主体证据。

### Phase 2：`SourceRouteRegistry v2`

目标：把 8 层数据源、成熟研报工作流源和 source-route 工程合成一个可执行 registry。

交付：

- Registry schema：`source_role`、`source_layer`、`claim_scope`、`required_fields`、`entity_binding_keys`、`locator`、`fetcher`、`parser`、`verifier`、`authority_mapper`、`runtime_row_type`、`not_applicable_rules`、`commercial_gap_boundary`。
- 把现有 16/18/19/20/21/22/23 的 source roles 合并去重：避免 source lane、exact-slot、Product-KPI、R17 evidence 各自维护一套口径。
- 对每个 source role 标注：`exact_fact_authority`、`thesis_driver_authority`、`lead_only`、`commercial_gap_only`。
- 对每个 source role 标注当前状态：`runtime_ready`、`planning_only`、`lead_only`、`route_or_parser_debt`、`credential_or_access_blocked`、`commercial_gap_only`。

通过条件：

- 已有 runtime rows 都能反查到 registry route。
- 新增 route 没有 owner/parser/verifier 的不能进入 runtime-ready。
- Registry 能生成 Research Lead 的 source plan 和 eval required-source matrix。
- `runtime_ready` 与 `planning_only` 必须分离；不能把 seed、URL、搜索结果或 attempt ledger 当成可用 evidence row。

2026-06-23 状态：SourceRouteRegistry v2 / SignalAuthorityMapper v0.2 已落地并通过 strict gate；后续 Phase 2 只保留新增 source role 或新增 data layer 时的 registry 扩展责任。

2026-06-23 跨行业 source-route gate 更新：新增 `r18_vertical_source_route_gate_v0_1`，把 603 公司 coverage matrix 中每个 lane-required source role 对齐到 `r18_source_authority_data_mart` 的 parser-backed evidence rows。

- 产物：`data/manifests/r18_vertical_source_route_gate_rows_v0_1.jsonl`、`data/manifests/r18_vertical_source_route_gate_summary_v0_1.json`、`docs/internal/vnext_20260610/r18_vertical_source_route_gate.zh-CN.md`。
- 当前结果：`company_count=603`，`pass_company_count=534`，`action_required_company_count=69`，`requirement_count=2,701`，`passed_requirement_count=2,630`，`missing_requirement_count=71`。
- 剩余缺口 source roles：`hiring_capacity_proxy=27`、`public_order_proxy=19`、`developer_ecosystem_proxy=13`、`channel_offer_proxy=8`、`technology_research_proxy=4`。
- root cause：`source_or_adapter_gap=53`、`route_or_parser_debt=18`；hard gate `flag_count=0`，没有 coverage pass 但 mart 缺证据的同步错误。

这不是放松 source closeout，而是把过去“365 家 company coverage gap”的粗粒度状态拆到 71 个具体 source-role requirement。后续数据基座修复应继续优先处理这些 action-required requirement，并保持 URL/snippet/seed/attempt-only 不得进入 evidence bundle。

2026-06-23 R18 cross-lane repair 更新：

- 已修 route/parser：
  - `technology_research_proxy`：OpenAlex issuer alias resolver 与 ticker-level topic override 已补入，解决 `GOOGL/CRM/TXN/WDAY/ALB/FLNC/SQM/ADI/CSCO/TDY/TER/TSLA/1211.HK` 等因法律名称、产品词或 family 误映射导致的漏召回；仍保持 issuer+topic 双绑定，OpenAlex 只能作为 technology/research proxy，不能证明产品销售、收入、份额或 moat。
  - `public_order_proxy`：cross-lane gate 允许同一问题域下更强/同级的 `supply_chain_official_relationship` 满足公开订单/客户关系验证需求，但边界仍是官方供应链/客户关系，不得推断订单金额、backlog、收入或份额。
  - `hiring_capacity_proxy`：新增 `HUBS -> hubspotjobs` verified Greenhouse board token 和 `CRWD -> crowdstrikecareers` verified Workday CXS site；只接受 title/location 等 parser-backed job rows，不接受 careers landing page。
- `channel_offer_proxy`：把 `family_channel_distributor_context_rows_v0_1` 接入 company matrix，`channel_distributor_locator` 纳入 channel offer source-role；已物化的 official/dealer/distributor locator rows 只支撑 public channel presence，不支撑 ASP、库存、sell-through、销售额或份额。
- `auto_product_identity_context`：非美车企 official model/product page 可以满足 bounded vehicle identity context；同时修复 vertical lane assignment 中 `Automatic` / `Autodesk` / `Automation` 裸 substring 误分 V5 的问题，ADP/ADSK/ROK/AZO/ORLY 已回到合适 lane，BYD/NIO/LI/XPEV 通过 explicit override 保留 V5。
- `r18_data_source_admission_ledger`：multi-source requirement 只按实际观测或 exact-slot 支撑的 `source_id` 出 admission row，不再把同组未观测 source_id 误标为 evidence-ready。
- 最新 gate：`pass_company_count=534`，`action_required_company_count=69`，`missing_requirement_count=71`，hard gate `flag_count=0`。
- 最新剩余 source-role split：
  - `hiring_capacity_proxy=27`
  - `public_order_proxy=19`
  - `developer_ecosystem_proxy=13`
  - `channel_offer_proxy=8`
  - `technology_research_proxy=4`
- 最新 root cause：`source_or_adapter_gap=53`、`route_or_parser_debt=18`。
- 当前不能提权的典型边界：
  - `developer_ecosystem_proxy` 剩余多为连接器、分销、工业/光学/材料公司；locator 已尝试 official pages 与 verified GitHub profile，未找到可绑定 official repo/package/model seed，不能 blind-search GitHub 后强行绑定。
  - `channel_offer_proxy` 剩余多为零售/汽车/消费品牌，CDW 路径本身不适配；需要 AutoZone/HomeDepot/DollarGeneral/NIO/Deckers 等 official store 或 marketplace site-specific parser。只看到官网或被 403/anti-bot 阻断不能提权。
  - `PLTR/300750.SZ/373220.KS/MPWR technology_research_proxy` 经 OpenAlex alias/topic 修复后仍无稳定 issuer-topic bound rows；PatentsView/USPTO assignee resolver 或 company technical docs 才是下一步，不得用泛关键词论文提权。

2026-06-23 R19 数据源 gap closeout 更新：

- 已修复并进入 runtime 的 route/parser：
  - `hiring_capacity_proxy`：新增 Oracle HCM Candidate Experience adapter，并补 `AKAM/FTNT/HON/ORCL/VRT/YUM` 等官方招聘 API rows；新增 generic careers table parser，补 `CHTR/PCOR` 等静态职位列表页。所有招聘 rows 仍只支撑 hiring capacity / role mix proxy，不支撑收入、订单、份额或销量。
  - `developer_ecosystem_proxy`：对 `APH/CDW/COHR/DIOD/FN/GLW/IT/LITE/MTSI/Q/RMBS/ROP/WOLF` 完成 official docs/package/repo seed probe 后标记 `not_applicable_after_source_probe`；这些硬件、分销、制造、研究服务 issuer 不再被错误要求 GitHub/npm/PyPI/HuggingFace exact row，不能 blind-search 提权。
  - `channel_offer_proxy`：补 `DECK` 品牌域名绑定，允许 `hoka.com/ugg.com/teva.com` official product/store surface；修复 manual verified channel seed 在普通 HTTP 403/567/blocked 时没有触发 Playwright fallback 的设计缺陷，并补 `AZO/CASY/DG/GPC/MNST` domain override。真实重跑后 `DECK` 与 `NIO` 进入 parser-backed `channel_distributor_locator` rows。
- 最新 canonical data mart：
  - `r18_source_authority_data_mart_v0_1` strict pass：`company_count=603`，`row_count=3,729`，`evidence_bundle_allowed_count=3,660`，`planning_or_gap_only_count=69`，hard gate `flag_count=0`。
  - `exact_slot_coverage_matrix_v0_1` validation pass：`all_required_exact_ready_company_count=551`，`partial_exact_ready_company_count=52`，`exact_slot_gap_count=53`；其中 `channel_offer_proxy.ready_count=56/gap_count=6`、`hiring_capacity_proxy.ready_count=48/gap_count=18`、`technology_research_proxy.ready_count=74/gap_count=4`。
  - `r18_vertical_source_route_gate_v0_1`：`pass_company_count=557`，`action_required_company_count=46`，`missing_requirement_count=47`，hard gate `flag_count=0`。
- 当前 R18 vertical release gate 仍 action-required 的 47 条：
  - `public_order_proxy=19`：`CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN`。USAspending 与已接 local tender route 没有 recipient-bound award/order row；后续需要 jurisdiction-specific tender、customer contract、official award status 或 company/customer official relationship adapter，不能用搜索页或新闻 URL 代替订单 evidence。
  - `hiring_capacity_proxy=18`：`SE/ADP/CTSH/IBM/MSFT/ROP/S/SHOP/TEAM/VZ/EME/ETN/FIX/LII/PWR/DRI/MELI/SBUX`。多数是 official careers 存在但当前 parser 未吃到结构化 title/location rows，典型为 Eightfold、Jibe/official careers 403、site-specific careers API 或动态渲染页面；这是 route/parser debt，不得把 careers landing page 当 exact job rows。
  - `channel_offer_proxy=6`：`GPC/AZO/CASY/DG/HD/MNST`。NAPA/HomeDepot/AutoZone/DollarGeneral/Casey's 等官方 store locator 或电商页仍需要 site-specific store API / browser parser；Monster Beverage 官网未发现可绑定 locator。当前只保留 attempt-backed boundary，不把 URL 存在提权为渠道/库存/价格证据。
  - `technology_research_proxy=4`：`PLTR/300750.SZ/373220.KS/MPWR`。OpenAlex 未给出稳定 issuer-topic bound rows；本地仍缺 `PATENTSVIEW_API_KEY` / USPTO assignee resolver，不能用泛关键词论文或专利搜索结果提权。
- 口径说明：`requirement_results` 中仍会保留公司矩阵的计划性 resolver/source gaps；R18 release gate 的当前阻断口径以公司行 `missing_source_roles` 汇总为准。两者都不能进入 Memo evidence bundle，只有 `can_enter_evidence_bundle=true` 的 parser-backed rows 能进入 ClaimCard / Memo。

2026-06-23 R20 首层 source-route closeout 更新：

- 已修复并进入 runtime 的 route/parser：
  - `hiring_capacity_proxy`：新增 IBM careers search API adapter。IBM 官方 careers 页面渲染出的 search bundle 调用 `https://www-api.ibm.com/search/api/v2`，本轮 adapter 只接受该 API 返回的 title / location / department / URL 等 issuer-bound job rows；这些 rows 只能作为 hiring capacity / role-mix proxy，不能写成 headcount、收入、订单、需求、份额或产品销售。
- 最新 canonical data mart：
  - `r18_source_authority_data_mart_v0_1` strict pass：`company_count=603`，`row_count=3,729`，`evidence_bundle_allowed_count=3,674`，`planning_or_gap_only_count=55`，hard gate `flag_count=0`。
  - `exact_slot_coverage_matrix_v0_1` validation pass：`all_required_exact_ready_company_count=564`，`partial_exact_ready_company_count=39`，`exact_slot_gap_count=39`；其中 `channel_offer_proxy.gap_count=6`、`hiring_capacity_proxy.gap_count=4`、`public_order_proxy.gap_count=25`、`technology_research_proxy.gap_count=4`。
  - `r18_vertical_source_route_gate_v0_1`：`pass_company_count=570`，`action_required_company_count=33`，`missing_requirement_count=33`，hard gate `flag_count=0`。
- 当前 R18 vertical release gate 仍 action-required 的 33 条：
  - `public_order_proxy=19`：`CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN`。USAspending route 对这些公司没有 recipient-bound award row；现有 local tender / official relationship routes 也没有可绑定 buyer / supplier / product 的 parser-backed row。下一步只能继续做 jurisdiction-specific tender、company/customer official contract relationship、issuer IR customer disclosure 或监管/采购状态 adapter；不能用搜索结果、新闻 URL 或供应链传闻补公开订单 evidence。
  - `hiring_capacity_proxy=4`：`ROP/VZ/FIX/MELI`。VZ 和 MELI 已确认存在官方 careers surface，但当前动态页面/站点 API 没有稳定公开 job row 可抽；FIX 的 jobs 域名 DNS/站点不可用，官方 careers 主要导向子公司；ROP 是 operating-company 分散招聘结构，需要 subsidiary-to-issuer resolver。landing page 仍不能提权为 exact job rows。
  - `channel_offer_proxy=6`：`GPC/AZO/CASY/DG/HD/MNST`。NAPA / HomeDepot / AutoZone / DollarGeneral / Casey's 等官方 store / locator / ecommerce 页面仍需要 site-specific store API 或 browser parser；GPC NAPA 页面 403/blocked，MNST 没有发现 verified official channel locator。当前只保留 attempt-backed boundary，不把 URL 存在提权为渠道/价格/库存/销量证据。
  - `technology_research_proxy=4`：`PLTR/300750.SZ/373220.KS/MPWR`。OpenAlex issuer/topic probe 没有返回稳定 issuer-topic-bound works；PatentsView 当前仍缺 API key / assignee resolver，不能用泛关键词论文或专利搜索结果提权。
- 验证：
  - `python -m py_compile scripts\data_expansion\build_broad_official_careers_context_rows.py scripts\data_expansion\build_family_channel_distributor_context_rows.py src\sec_agent\company_public_source_coverage_matrix.py`
  - `python -m pytest tests\test_broad_official_careers_context_rows.py tests\test_family_channel_distributor_context_rows.py tests\test_company_public_source_coverage_matrix.py tests\test_exact_slot_contracts.py tests\test_r18_data_source_admission_ledger.py tests\test_r18_source_authority_data_mart.py tests\test_r18_vertical_source_route_gate.py -q` -> `67 passed`

口径更新：R20 之后首层 data-source closeout 的事实状态是 `570/603` 公司已满足 lane-required parser-backed source-role row。剩余 `33` 条不是 release hidden fallback，而是已经分解到 source role、ticker、root cause 和 next adapter 的 action-required boundary；任何 attempt-only / seed-only / URL-only / blocked page 仍不能进入 ClaimCard 或 Memo 主体证据。

2026-06-24 R21 33 条 source-route release blocker 修复更新：

- 已修复并进入 runtime 的 route/parser：
  - `public_order_proxy`：对 `CRDO/PCAR/BILL/CSIQ/JKS/SEDG/SHOP/1211.HK/6752.T/CCJ/DNN/DQ/ENLT/ENPH/NXT/OKLO/SMR/UROY/RUN` 补 targeted official supplier/customer / contract relationship rows，并把 `public_order_proxy` 的 release-gate source route 扩展为可接受 `supplier_customer_official_news` 的 bounded context。口径是“公开订单/客户/供应关系存在性 proxy”，仍禁止写成 order value、backlog、shipment、收入、份额、销量或完整 order book。
  - `hiring_capacity_proxy`：补 `ROP/VZ/FIX/MELI` 的官方 careers/ATS parser 路径，包括 VZ browser-executed Next jobs API、MELI Eightfold API、FIX Workday direct ATS、ROP/Deltek official subsidiary careers binding。rows 只支持 hiring capacity / role-mix / geography signal，不支持 headcount、收入、订单或需求 exact。
  - `channel_offer_proxy`：补 `GPC/AZO/CASY/DG/HD/MNST` 的 family channel / distributor / official-store route，增加 browser fallback 和 official / reader-proxy seed 处理。rows 只支持 public channel presence / offer / locator context，不支持 ASP、sell-through、inventory、销量、收入或市场份额。
  - `technology_research_proxy`：补 `PLTR/300750.SZ/373220.KS/MPWR` 的 official technical / R&D document route。OpenAlex/PatentsView 仍可后续增强，但本轮 release blocker 不再依赖泛关键词论文或专利搜索结果；只有 official issuer/topic-bound technical document rows 能进入 bounded technology research signal。
- 最新 canonical data mart：
  - `r18_data_source_admission_ledger_v0_1` strict pass：`company_count=603`，`row_count=3,761`，`can_enter_evidence_bundle_count=3,761`，`not_evidence_ready_count=0`，hard gate 全部为 `0`。
  - `r18_source_route_registry_v2` strict pass：`registry_source_role_count=16`，`signal_matrix_row_count=3,761`，`evidence_bundle_allowed_count=3,761`，`planning_or_gap_only_count=0`，hard gate 全部为 `0`。
  - `r18_source_authority_data_mart_v0_1` strict pass：`company_count=603`，`row_count=3,761`，`evidence_bundle_allowed_count=3,761`，`planning_or_gap_only_count=0`，`exact_company_fact_authority_count=865`，`thesis_driver_authority_count=2,896`，hard gate `flag_count=0`。
  - `r18_vertical_source_route_gate_v0_1` release pass：`pass_company_count=603`，`action_required_company_count=0`，`missing_requirement_count=0`，`requirement_count=2,688`，hard gate `flag_count=0`。
- exact-slot 边界：
  - `exact_slot_coverage_matrix_v0_1` validation pass，但 `status=gap`：`all_required_exact_ready_company_count=578`，`partial_exact_ready_company_count=25`，`exact_slot_gap_count=25`，全部为 `public_order_proxy` 的 `context_only_not_exact_slot`。
  - 这不是 release blocker，而是正确边界：官方客户/供应/合同关系可以满足 public-order / demand-context source-role gate，但不能冒充公开招标/award exact snapshot。需要 `award_id`、`award_amount`、`award_start_date`、`awarding_agency` 等字段时，仍必须暴露 exact-slot gap 或继续接 jurisdiction tender / official award API。
- 验证：
  - `python -m pytest tests/test_targeted_supply_chain_official_relationship_rows.py tests/test_family_channel_distributor_context_rows.py tests/test_broad_official_careers_context_rows.py tests/test_targeted_official_technology_document_rows.py tests/test_company_public_source_coverage_matrix.py tests/test_source_coverage_gate.py tests/test_r18_data_source_admission_ledger.py tests/test_source_route_registry_v2.py tests/test_r18_source_authority_data_mart.py tests/test_r18_vertical_source_route_gate.py tests/test_exact_slot_contracts.py -q` -> `88 passed`
  - `python -m py_compile scripts/data_expansion/build_targeted_supply_chain_official_relationship_rows.py scripts/data_expansion/build_family_channel_distributor_context_rows.py scripts/data_expansion/build_broad_official_careers_context_rows.py scripts/data_expansion/build_targeted_official_technology_document_rows.py scripts/data_expansion/build_company_public_source_coverage_matrix.py scripts/data_expansion/build_exact_slot_coverage_matrix.py scripts/data_expansion/build_r18_data_source_admission_ledger.py scripts/data_expansion/build_r18_source_route_registry_v2.py scripts/data_expansion/build_r18_source_authority_data_mart.py scripts/data_expansion/build_r18_vertical_source_route_gate.py src/sec_agent/exact_slot_contracts.py src/sec_agent/source_coverage_gate.py src/sec_agent/company_public_source_coverage_matrix.py`

口径更新：R21 后，首层 lane-required parser-backed source-role release gate 已经完成，`603/603` 公司至少满足各自 lane-required source role 的证据入口要求。但这不等于每家公司、每个产品、每个 SKU、每个产品 KPI 都完整覆盖；细粒度 Product-KPI exact、产品规格/竞品关系、capital/funding/ownership、leading-signal full-chain 使用仍按后续阶段继续做。

2026-06-24 R21b 口径收紧：`official_customer_order_or_deployment_event` 从 `public_order_proxy` / `supply_chain_official_relationship` 中拆出独立 contract。

- 新 contract 目的：允许官方客户、订单、项目、部署、协议公告作为“官方事件 fact / bounded demand signal”进入 thesis driver，但不把它冒充公开采购 award exact、收入 exact、backlog exact 或完整订单簿。
- Runtime materialization：
  - `supplier_customer_official_news` 中新增 `source_role=official_customer_order_or_deployment_event`，只有文本能绑定 event type / customer or counterparty / product or segment / event date or scale text 时才进入 event contract。
  - 本轮物化 `26` 家 event rows；`2382.TW`、`CRDO`、`DNN` 只保留在关系/上下文层，没有被提权为 event，因为当前 rows 不是明确订单、部署、项目或客户事件。
- Schema 对齐修复：
  - `official_product_surface` 接受 `sec_product_taxonomy_normalized`，否则 SEC taxonomy rows 存在但不被 company matrix 接住。
  - `regulated_product_context` 接受 `fda_animal_drugs_api`，否则 animal-health regulated rows 被漏掉。
  - issuer binding 白名单补 `issuer_subsidiary_official_domain_bound`、`macro_exposure_bridge_context`、`family_assignment_exposure_context`，否则 subsidiary careers / macro bridge / family assignment rows 无法被矩阵接住。
- 最新验收：
  - `company_public_source_coverage_matrix_v0_1`：`603` 公司；`pass=578`、`gap=25`，剩余全是 `public_order_proxy` source gap。
  - `exact_slot_coverage_matrix_v0_1`：`official_customer_order_or_deployment_event.ready_count=26`；`public_order_proxy.gap_count=25` 保持 exact-slot gap，因为没有公开采购 award exact fields。
  - `r18_data_source_admission_ledger_v0_1` / `r18_source_authority_data_mart_v0_1`：均 strict pass，`row_count=3,712`。
  - `r18_vertical_source_route_gate_v0_1`：`pass_company_count=600`、`action_required_company_count=3`，剩余 `2382.TW/CRDO/DNN` 的 `public_order_proxy` 不再被 generic relationship 混过 gate。
- 验证：
  - `python -m pytest tests/test_company_public_source_coverage_matrix.py tests/test_source_coverage_gate.py tests/test_product_family_source_routes.py tests/test_exact_slot_contracts.py tests/test_targeted_supply_chain_official_relationship_rows.py tests/test_non_financial_signal_authority.py tests/test_source_route_registry_v2.py tests/test_r18_data_source_admission_ledger.py tests/test_r18_vertical_source_route_gate.py -q` -> `64 passed`。
  - Rebuild：`build_product_family_source_route_plan.py`、`build_company_public_source_coverage_matrix.py`、`build_exact_slot_coverage_matrix.py`、`build_r18_data_source_admission_ledger.py`、`build_r18_source_route_registry_v2.py`、`build_r18_source_authority_data_mart.py`、`build_r18_vertical_source_route_gate.py`。

因此，R21b 后首层 release gate 不再按“关系上下文可替代 public order exact”宽口径通过，而是按更严格的 source-role 边界保留 3 家 action-required。下一步应继续图二第二层：产品规格 slot、产品关系图谱、强信号源扩展；再接第三层 capital/funding/ownership/market-liquidity 数据源。

2026-06-24 R22 第二层首批接线：R17 产品规格/benchmark/代际/客户部署强信号进入统一 R18 数据基座。

- 新增进入 SourceRouteRegistry / company matrix / R18 admission / authority mart 的 source roles：
  - `technical_product_spec`：官方产品规格、架构、配置、型号、版本字段；只支持产品能力/规格对比，不支持销售、收入、ASP、份额、库存、sell-through。
  - `product_generation_edge`：官方产品代际或架构切换 edge；只支持产品周期和能力代际分析，不自动推出需求或收入。
  - `product_benchmark_proxy`：官方或可信 benchmark / performance proxy；只支持能力比较，不支持采用率、销量、份额或收入。
  - `customer_deployment_proxy`：官方客户部署/项目上下文；只支持部署和需求可见度 signal，不支持订单金额、收入贡献、backlog 或 shipment。
- Parser/binding 修复：
  - `r17_product_family_evidence_runtime_rows_v0_1` rows 补 `parser_status=parser_pass`、`structured_fact_status=bounded_context_fact_materialized`、issuer/product/counterparty binding statuses。
  - `family_source_route_plan_v0_1` 动态注入上述 route，只在 runtime row 已存在的 ticker/family 上出现，不把 603 家全部硬要求化。
  - `technical_product_spec` / `product_generation_edge` 不接受泛化 `company_product_pages`，只接受明确 spec/datasheet/专用 source id；避免普通产品页误满足产品规格 role。
- 最新验收：
  - `family_source_route_plan_v0_1`：`technical_product_spec=2` routes、`product_generation_edge=2` routes、`product_benchmark_proxy=2` routes、`customer_deployment_proxy=2` routes，均来自 NVDA family assignments。
  - `company_public_source_coverage_matrix_v0_1`：四个新增 role 各 `1 pass`，均为 NVDA；没有新增全局 gap。
  - `r18_source_route_registry_v2`：`source_role_count=21`。
  - `r18_data_source_admission_ledger_v0_1`：strict pass，`row_count=3,716`；四个新增 role 各 1 条。
  - `r18_source_authority_data_mart_v0_1`：strict pass，`row_count=3,716`，`evidence_bundle_allowed_count=3,691`；四个新增 role 均 `can_enter_evidence_bundle=True`。
  - `r18_vertical_source_route_gate_v0_1`：仍为 `600/603` pass，只剩 `2382.TW/CRDO/DNN` 的 `public_order_proxy`，未因新增产品 role 引入新 release gap。
- 验证：
  - `python -m pytest tests/test_source_coverage_gate.py tests/test_product_family_source_routes.py tests/test_source_route_registry_v2.py tests/test_r18_data_source_admission_ledger.py tests/test_r18_vertical_source_route_gate.py tests/test_non_financial_signal_authority.py -q` -> `39 passed`。

R22 只证明“已有 parser-backed 产品强信号不会散落在 R17 小表外”，不代表产品规格/竞品/供应链/客户部署数据已经覆盖所有公司。下一步要按 product family source lane 批量扩展 spec slot schema、产品关系图谱和强信号源 locator/parser。

2026-06-24 R23 第三层首批接线：K5/K6 capital/funding/ownership rows 进入统一 R18 数据基座。

- 新增 source roles：
  - `capital_structure_disclosure`：SEC debt footnote / credit facility / FSD capital structure rows，支持公司披露的债务、credit facility、cash/debt/net debt、maturity/coupon/covenant context；不得推断未披露融资条款、market-implied spread 或实时再融资能力。
  - `lagged_ownership_context`：13F / ownership rows，明确 `not_realtime_flag` 和 lag policy；不得写成实时资金流、当前买盘、完整股东结构或 intraday positioning。
- 新增 projection：
  - `scripts/data_expansion/build_capital_funding_ownership_context_rows.py`
  - 输入 K5/K6 `capital_macro_source_adapter_v0_1` 的 `capital_ownership_rows.jsonl`。
  - 输出 `capital_funding_ownership_context_rows_v0_1.jsonl` / summary。
- 最新验收：
  - Projection rows：`7,956`，其中 `capital_structure_disclosure=2,956`、`lagged_ownership_context=5,000`。
  - `company_public_source_coverage_matrix_v0_1`：状态仍为 `578` pass / `25` gap，未因为资本层动态 source roles 引入全市场硬缺口。
  - `r18_source_route_registry_v2`：`source_role_count=23`。
  - `r18_data_source_admission_ledger_v0_1`：strict pass，`row_count=5,039`；其中 `capital_structure_disclosure=914`、`lagged_ownership_context=409` company/source-role rows。
  - `r18_source_authority_data_mart_v0_1`：strict pass，`row_count=5,039`，`evidence_bundle_allowed_count=5,014`。
  - `r18_vertical_source_route_gate_v0_1`：仍为 `600/603` pass，仅剩旧 `public_order_proxy=3`；资本层首批没有新增 release blocker。
- 验证：
  - `python -m pytest tests/test_capital_funding_ownership_context_rows.py tests/test_company_public_source_coverage_matrix.py tests/test_source_route_registry_v2.py tests/test_r18_data_source_admission_ledger.py tests/test_r18_vertical_source_route_gate.py tests/test_capital_macro_pack.py tests/test_capital_macro_source_adapters.py -q` -> `39 passed`。

R23 仍不是完整 capital/funding/ownership/market-liquidity layer。它只把已有 debt/credit/capital structure/13F rows 进入统一 source-authority 基座；后续还要补 offering / Form 3/4/5 / 13D/13G / N-PORT / buyback / short interest / volume-liquidity / options / credit spread / ETF-factor-flow source contracts 与 runtime rows。

2026-06-24 R24 第三层第二批接线：SEC structured financial statement 中的营运资本/流动性科目进入 capital/funding/ownership/market-liquidity 数据基座。

- 新增 source role：
  - `working_capital_liquidity`：SEC CompanyFacts / FSD 中的 AR、inventory、AP、deferred revenue、current assets/liabilities、short-term debt、cash、CFO、capex、financing cash flow 等公司披露科目；支持营运资本、现金转换周期、流动性和资本配置分析；不得证明产品需求、产品销量、ASP、市场份额、渠道库存、sell-through、backlog 或未披露融资条款。
- projector 修复：
  - `scripts/data_expansion/build_sec_financial_statement_metric_runtime_rows.py` 扩展 canonical metric family，新增 `accounts_receivable`、`inventory`、`accounts_payable`、`deferred_revenue`、`current_assets`、`current_liabilities`、`cash_and_equivalents`、`short_term_debt` 等科目。
  - 默认 `max_metrics_per_ticker` 从 `13` 调整为 `24`，避免新增财务科目被上游 cap 掉。
  - `scripts/data_expansion/build_capital_funding_ownership_context_rows.py` 将上述科目投影为 `WorkingCapitalLiquidityRow`。
- gate 修复：
  - `source_coverage_gate` 对容易被宽 `source_id` 污染的 source roles 增加 strict role matching。`capital_structure_disclosure`、`working_capital_liquidity`、`technical_product_spec` 等必须有显式 `source_role` / runtime contract / structured context，不再允许泛化 `sec_financial_statement_data_sets` 或 `company_product_pages` 误满足。
- 最新验收：
  - SEC financial statement runtime rows：`10,146` 行 / `587` 家公司；新增科目包括 `accounts_payable=472`、`accounts_receivable=456`、`inventory=343`、`deferred_revenue=383`、`current_assets=485`、`current_liabilities=485`、`cash_and_equivalents=564`、`short_term_debt=352`。
  - `capital_funding_ownership_context_rows_v0_1`：`13,185` rows，其中 `working_capital_liquidity=5,229`、`capital_structure_disclosure=2,956`、`lagged_ownership_context=5,000`。
  - `r18_source_route_registry_v2`：`source_role_count=24`，hard gate 全 0。
  - `r18_data_source_admission_ledger_v0_1`：strict pass，`row_count=6,213`，`can_enter_evidence_bundle_count=6,188`；其中 `working_capital_liquidity=1,174` company/source-role rows。
  - `r18_source_authority_data_mart_v0_1`：strict pass，`row_count=6,213`，`evidence_bundle_allowed_count=6,188`，`working_capital_liquidity_fact=1,174`。
  - `r18_vertical_source_route_gate_v0_1`：仍为 `600/603` pass；剩余 action-required 仍是旧 `public_order_proxy=3`，R24 没有新增 release blocker。
- 验证：
  - `python -m pytest tests/test_source_coverage_gate.py tests/test_company_public_source_coverage_matrix.py tests/test_source_route_registry_v2.py tests/test_capital_funding_ownership_context_rows.py tests/test_sec_financial_statement_metric_runtime_rows.py -q` -> `31 passed`。

R24 后，资本/资金层已经覆盖：公司披露 debt/credit/capital structure、13F 滞后持仓 context、营运资本/流动性科目。仍待补的是：offering/S-1/S-3/424B/8-K/exhibit financing events、Form 3/4/5 insider transactions、13D/13G activist/beneficial ownership、N-PORT/fund holdings、buyback authorization/actual repurchase、short interest、volume/turnover、options IV、credit spread、ETF/factor flows。

2026-06-24 R25 第三层第三批接线：SEC submissions metadata 资本市场 filing-event context 进入统一数据基座。

- 新增 source roles：
  - `securities_offering_filing_event`：S-1/S-3/F-1/F-3/424B/FWP 等 offering / registration filing-event metadata；只能证明 filing event、form、accession、filing date、primary document，不能证明 offering amount、security terms、dilution、coupon、maturity 或 proceeds。
  - `insider_transaction_filing_event`：Form 3/4/5/144 filing-event metadata；不能证明 shares、transaction price、ownership change 或 management intent，后续需要 XML parser。
  - `beneficial_ownership_filing_event`：SC/Schedule 13D/13G filing-event metadata；不能证明 beneficial ownership percentage、activist thesis、current buying pressure 或 complete ownership，后续需要 schedule parser。
  - `proxy_governance_filing_event`：DEF 14A / DEFA14A / PRE 14A / DFAN14A / PX14A6G filing-event metadata；不能证明 buyback amount、compensation outcome、voting result 或 governance judgment，后续需要 proxy text/table parser。
- 新增 adapter：
  - `scripts/data_expansion/build_sec_capital_market_event_context_rows.py`
  - 输入本地 `data/raw_private/sec/_reference/submissions/CIK*.json`，不联网。
  - 输出 `sec_capital_market_event_context_rows_v0_1.jsonl` / summary。
- source-layer capability 修复：
  - `sec_offering_filing_metadata`、`sec_form_3_4_5_metadata`、`sec_schedule_13d_13g_metadata`、`sec_proxy_governance_metadata` 已进入 `SourceLayerCapabilityAudit` runtime-ready context route，R18 admission 不再显示 `route_source_status=not_registered`。
- 最新验收：
  - SEC capital-market event rows：`7,584` rows / `248` tickers。
  - row split：`insider_transaction_filing_event=1,969`、`beneficial_ownership_filing_event=1,965`、`proxy_governance_filing_event=1,892`、`securities_offering_filing_event=1,758`。
  - R18 registry：`source_role_count=28`，hard gate 全 0。
  - R18 authority mart：strict pass，`row_count=7,181`，`evidence_bundle_allowed_count=7,156`。
  - Mart 中新增 company/source-role rows：`securities_offering_filing_event=236`、`insider_transaction_filing_event=246`、`beneficial_ownership_filing_event=247`、`proxy_governance_filing_event=239`。
  - R18 vertical source-route gate：仍为 `600/603` pass，仅剩旧 `public_order_proxy=3`。

R25 后，资本市场事件层已能支持“公司近期是否有证券发行/注册、insider filing、13D/13G、proxy/governance filing”这类事件级判断。下一步不是继续把 metadata 硬提权，而是为 Form 3/4/5 XML、13D/13G schedule、offering filing text、proxy buyback/compensation tables 补 source-specific parser，只有解析出 value/unit/period/citation 的字段才能进入 exact。

2026-06-24 R26 deterministic acceptance gate 已落地：

- 新增 `src/sec_agent/layer_acceptance_gates.py` 和 `scripts/data_expansion/build_r26_second_third_layer_acceptance_gates.py`，生成：
  - `r26_second_layer_acceptance_gate_summary_v0_1.json`
  - `r26_third_layer_acceptance_gate_summary_v0_1.json`
  - `r26_second_third_layer_acceptance_gate_summary_v0_1.json`
- 当前 gate 结果：
  - second layer：`pass`。
  - third layer：`pass`。
  - combined：`pass`。
- second layer 通过口径：
  - `company_product_slots_v0_1` 覆盖 `603/603` 公司。
  - ProductRelationshipGraph summary pass，`6,454` product slots、`24,237` edges，含 `COMPETES_WITH=3,358` 以及 supply/input/manufacturing dependency 等边。
  - Product-KPI closeout 覆盖 `603` 公司，且 `unclassified_count=0`；其中 `product_kpi_exact_ready=173`、`business_segment_metric_ready=52`、`geographic_or_non_product_metric_only=10`、`product_kpi_exact_gap=368`。
  - R17 strong product signal rows `24` 条进入边界校验，`technical_product_spec/customer_deployment/product_generation/product_benchmark` source roles 均存在，非财务信号没有被错误提权成 exact financial/product KPI。
- third layer 通过口径：
  - SEC FSD + non-US L1 财务 rows 覆盖 `603` 公司。
  - SEC structured financial statement rows 覆盖 AR、inventory、AP、deferred revenue、current assets/current liabilities、cash、short-term debt、OCF、capex proxy 等 working-capital/liquidity 指标。
  - `capital_funding_ownership_context` 有 `13,185` rows，含 `capital_structure_disclosure=2,956`、`lagged_ownership_context=5,000`、`working_capital_liquidity=5,229`。
  - SEC capital-market filing-event rows `7,584` 条，offering / insider / 13D-13G / proxy-governance metadata 均通过“metadata only, not exact value”边界。
  - R18 authority mart pass，hard gate 为 0。
- 新增 `FundamentalPeerStatementPanel` runtime object：
  - 由 `FundamentalStatementPack` 生成三表面板、同行可比指标面板、行业重点指标面板、派生指标、产品/资本桥、statement anomaly detector。
  - 已接入 `fundamental_analyst` data view 和 specialist request；Memo/Writer 仍不得直接把 proxy 或 closeout gap 写成 exact fact。
- 非 LLM 验收：
  - `tests/test_r26_layer_acceptance_gates.py`
  - `tests/test_financial_statement_analysis.py`
  - 相关 registry/runtime tests 均通过。

边界：R26 pass 代表 second/third layer 已有可审计 gate、runtime rows 和 panel 接口；不代表 every-company SKU revenue、unit sales、ASP、market share、sell-through、backlog 或实时资金流已可公开 exact 化。Form 3/4/5 XML、13D/13G schedule、offering terms、proxy table、N-PORT/fund flow、short interest/ETF factor flow 等仍按 R28/Phase 4 后续 parser 和数据源计划推进。

2026-06-24 R26b strict real-source readiness gate 已补上，用来修正“只过骨架、不证明真实数据源”的问题：

- 新增 `scripts/data_expansion/build_second_third_layer_real_source_readiness_gate.py`。
- 新增输出：
  - `second_third_layer_real_source_readiness_gate_summary_v0_1.json`
  - `second_third_layer_real_source_readiness_company_rows_v0_1.jsonl`
- 该 gate 不接受 `company_product_slots`、closeout rows、repair queue、URL seed 或 planning artifact 作为真实数据源；每家公司必须有：
  - `ticker`
  - `evidence_ref` / `evidence_id` / `fact_id`
  - `source_url` / `api_url` / `snapshot_url` / `raw_path` / citation URL
  - `parser_status` / `promotion_status` / `structured_fact_status` / source-specific parser marker
  - `claim_boundary` / `authority_boundary`
- 当前 strict real-source 结果：
  - overall：`pass`
  - company rows：`603/603 pass`
  - second layer actual parser source：`603/603`
  - third layer actual parser source：`603/603`
  - third layer exact financial basis：`603/603`
- second layer 真实 source 覆盖来源：
  - `official_product_surface_context_rows_v0_1` 覆盖 `453` 家。
  - `official_product_catalog_context_rows_v0_1` 覆盖 `395` 家。
  - `sec_product_taxonomy_context_rows_v0_1` 覆盖 `445` 家。
  - `company_reported_product_operating_metric_runtime_rows_v0_1` 覆盖 `214` 家。
  - `non_us_product_kpi_local_disclosure_runtime_rows_v0_1` 覆盖 `11` 家。
  - `r16_product_kpi_deep_repair_runtime_rows_v0_1` 覆盖 `8` 家。
  - `r17_product_family_evidence_runtime_rows_v0_1` 覆盖 `5` 家。
  - `targeted_official_technology_document_context_rows_v0_1` 覆盖 `4` 家。
- third layer 真实 source 覆盖来源：
  - `sec_financial_statement_metric_runtime_rows_v0_1` 覆盖 `587` 家。
  - `non_us_l1_financial_statement_metric_runtime_rows_v0_1` 覆盖 `16` 家。
  - `capital_funding_ownership_context_rows_v0_1` 覆盖 `587` 家。
  - `sec_capital_market_event_context_rows_v0_1` 覆盖 `247` 家。

边界：R26b 证明的是“600+ 公司在第二层和第三层都有 materialized、parser-backed、可追溯 source row”，不是证明所有公司都有 SKU 级收入、销量、ASP、市场份额、sell-through、backlog、订单金额或实时资金流。上述高门槛事实仍必须由公司披露、source-specific parser、商业 tracker 或后续人工/商业数据补齐，不能用普通 URL / product page / metadata 硬提权。

2026-06-24 R30/R31 更新：第二层/第三层“同等深度”不再按 source-role ready 判断，而改为逐公司五维 depth parity 矩阵。

- 新增 `second_third_layer_depth_parity_matrix_v0_1`，对 `603` 家公司逐一检查：
  - `product_kpi_depth`：公司披露的 value/unit/period/product/citation 产品或业务表现行。
  - `product_spec_depth`：官方技术规格、datasheet、架构、配置、型号、版本或可审计 technical spec 行。
  - `customer_deployment_depth`：官方客户订单、部署事件、供应链官方关系、公开采购或 customer deployment proxy 行。
  - `capital_market_detail_depth`：资本结构、债务/credit/working-capital liquidity、filing event / ownership / capital event metadata 同时具备。
  - `market_liquidity_depth`：价格、成交量、波动、相对收益等可追溯 market liquidity driver 行。
- 新增 `market_liquidity_driver_context_rows_v0_1`，用 2026-06-24 Yahoo chart 3M price/volume snapshot 为 `603/603` 公司生成 parser-backed market-liquidity rows。该源只支持价格/成交量/波动/相对收益的市场流动性上下文，不支持实时资金流、short interest、options IV、ETF/factor flow、credit spread、估值倍数或经营事实。
- 当前五维矩阵结果：
  - `market_liquidity_depth=603/603`。
  - `product_kpi_depth=234/603`，剩 `369` 家缺 company-disclosed Product-KPI exact，其中 `97` 家有 SEC taxonomy 但缺 value/unit/period/product KPI，`270` 家只有产品面/产品页但无公司披露产品 KPI，`1` 家只有 context，`1` 家有 slot 但缺 runtime value row。
  - `product_spec_depth=1/603`，剩 `602` 家缺强 technical spec depth，其中 `466` 家只有产品页/catalog 等 weak context，`136` 家缺可绑定 technical spec source/parser。
  - `customer_deployment_depth=158/603`，剩 `445` 家缺官方客户部署/订单/供应链/公开采购或 deployment proxy 行。
  - `capital_market_detail_depth=247/603`，剩 `356` 家未达到资本市场细项深度，其中 `340` 家主要是 capital event/offering/ownership parser 或覆盖缺口，`16` 家缺 accepted capital detail row。
  - `full_depth_target_met_company_count=0/603`。这不是 release 失败，而是把“同等深度”口径从“有真实源行”提高到“产品 KPI / 产品规格 / 客户部署 / 资本市场细项 / 市场流动性五维同时有可用行”后暴露出的真实 backfill queue。
- 产物：
  - `data/manifests/second_third_layer_depth_parity_summary_v0_1.json`
  - `data/manifests/second_third_layer_depth_parity_matrix_v0_1.jsonl`
  - `data/manifests/second_third_layer_depth_parity_backfill_queue_v0_1.jsonl`
  - `data/manifests/market_liquidity_driver_context_rows_v0_1.jsonl`
  - `data/manifests/market_liquidity_driver_context_summary_v0_1.json`

R30/R31 后续执行顺序：

1. `R32 product_spec_depth`：先扩 family-specific technical spec parsers，不允许普通 product page/catalog 冒充 technical spec。GPU/accelerator、CPU/server、semicap、networking、auto、SaaS、medtech、retail/CPG 等分别建 spec schema。
2. `R33 customer_deployment_depth`：把官方客户公告、deployment case study、supplier/customer official news、公开订单/采购、cloud/OEM deployment proxy 按公司和 product family 接入。
3. `R34 capital_market_detail_depth`：补 offering/S-1/S-3/424B/8-K/exhibit、Form 3/4/5、13D/13G、proxy buyback/compensation、N-PORT/fund holding/flow、short interest/options/ETF/credit spread source contracts 与 parsers。
4. `R35 product_kpi_depth`：继续 company-disclosed KPI value parser/backfill；公开源确实不披露 SKU revenue/unit/ASP/share/sell-through/backlog 时，写成 public-source/commercial-tracker gap，不用 weak proxy 填平。

2026-06-25 R32b 更新：

- 新增严格 `official_product_spec_context_rows_v0_1`：
  - 从已物化 official product pages 中抽 `technical_product_spec` / `ProductSpecSlot`。
  - 只有 parser 能得到 `spec_name/value/unit/product/citation` 才进入 strong spec。
  - trade-in、pricing、PDF/file-size、support-hour、third-party infrastructure、generic family homepage 等噪声被拒绝。
- 新增 `official_business_asset_profile_context_rows_v0_1`：
  - 面向 V7 资产/能源/工业公司，抽取 bounded `business_asset_profile_spec` / `BusinessProfileSlot`。
  - 只能支持资产容量/业务 profile context，不能证明 revenue、backlog、order value、shipments、ASP、utilization 或 market share。
- Product/Business-KPI depth 不再只认狭义产品收入：
  - `industry_operating_metric_slot_rows_v0_1` 在有 value/unit/period/segment/citation 和 row-level boundary 时进入 Product/Business-KPI depth。
  - 这覆盖 AUM、backlog/order、capacity、shipments、same-store growth、business segment revenue 等公司披露的业务表现 exact slots。
- 新增 `second_third_layer_depth_parity_gap_action_plan_v0_1`：
  - 对每家公司每个未达标维度输出 `primary_lane`、`family_scope`、`gap_class`、`source_gap_type`、`recommended_source_routes`、`attempt_policy` 和 `claim_boundary`。
  - 这是后续 R32-R35 source materialization 的执行入口，不是用来把 gap 隐藏掉。
- ProductFamilyRoutePlan 扩展：
  - 非 fallback V1-V5 family 自动带 `technical_product_spec` route。
  - V7 family 自动带 `business_asset_profile_spec` route；部分 V7 设备/电力/电池/冷却 family 也带 `technical_product_spec` route。
  - `business_asset_profile_spec` 不再允许 generic `company_product_pages` 满足，必须由专门 parser 或能源/项目 context 支撑。
- 最新五维矩阵结果：
  - `market_liquidity_depth=603/603`。
  - `product_kpi_depth=400/603`，剩 `203` 家缺 Product/Business-KPI exact。
  - `product_spec_depth=20/603`，剩 `583` 家缺 ProductSpec/Profile depth，其中 `447` 家为 parser-depth gap，`136` 家为 source/parser gap。
  - `customer_deployment_depth=158/603`，仍剩 `445` 家缺官方客户部署/订单/供应链/公开采购或 deployment proxy 行。
  - `capital_market_detail_depth=247/603`，仍剩 `356` 家未达到资本市场细项深度。
  - `full_depth_target_met_company_count=3/603`。
- 最新 ProductFamilyRoutePlan：
  - `route_plan_count=3,412`。
  - `technical_product_spec=250` route rows，其中 `21` runtime-ready，`229` not materialized。
  - `business_asset_profile_spec=211` route rows，其中 `3` runtime-ready，`208` not materialized。
  - 总体 `not_materialized=2,294`，说明下一步必须做真实 source locator/fetch/parser，不再是 gate 或文档口径问题。

2026-06-25 R33 official spec/profile source materialization 更新：

- 新增 `scripts/data_expansion/build_official_spec_source_locator.py`。
  - 从已物化 `company_product_pages` raw HTML 中抽同域官方细页候选。
  - 只产出 `official_spec_source_locator_candidates_v0_1`，状态为 `candidate_not_fetched`；候选 URL 不得进入 ClaimCard / Memo。
  - 首轮真实 locator：读取 `971` 个 official product pages、`3,412` route rows，定位 `470` 个同域候选、覆盖 `117` tickers，其中 `technical_product_spec=209`、`business_asset_profile_spec=261`。
- 新增 `scripts/data_expansion/materialize_official_spec_source_pages.py`。
  - 对 locator 候选做并发 fetch，HTML 转 clean text，PDF 用本地 `pypdf` 抽文本；失败写 attempt ledger，不伪装为 runtime row。
  - 首轮 materialization：选取 `293` 个候选，`251` 个 materialized，输出 `245` 个去重官方细页 artifact，覆盖 `104` tickers。
  - 二轮在 V8 business profile route 打开后新增 `16` 个 materialized 细页，官方细页总输出 `260` rows / `110` tickers。
- `build_official_product_spec_context_rows.py` 支持 `--additional-input`，并扩展核心技术单位：
  - 新增 `CUDA cores`、`tensor cores`、`RT cores`、`vCPU/CPU/GPU`、`threads`、`transistors`、`parameters`。
  - 支持 `billion/million/trillion parameters/transistors` 的规模词，不再漏 NVDA/AI model/semiconductor generation 关键规格。
  - 最新 `official_product_spec_context_rows_v0_1`：`242` rows / `31` tickers。
- `build_official_business_asset_profile_context_rows.py` 扩展为 V7/V8 `BusinessProfileSlot`：
  - 允许 MW/GW/kW、sq ft / square feet、rooms、properties、stores/locations/branches、sites/facilities/plants/data centers、miles/km、acres 等经营足迹单位。
  - 明确禁止 loyalty miles、年份型 count、0 asset count、bed 单位（后续应由 V4 healthcare facility adapter 单独处理）。
  - 最新清洗后 `official_business_asset_profile_context_rows_v0_1`：`56` rows / `27` tickers。
- `ProductFamilySourceRoutePlan` 扩展：
  - 对 V8 实体足迹明显的 families（retail/grocery、auto aftermarket、home improvement、homebuilding、restaurants、lodging、travel 等）增加 `business_asset_profile_spec` route。
  - 重建后 `route_plan_count=3,459`，`runtime_family_row_available=729`、`runtime_company_row_available=432`、`not_materialized=2,298`。
- 最新 depth parity：
  - `product_spec_depth=53/603`，剩 `550` 家缺口。
  - 缺口拆分为 `product_spec_parser_depth_gap=414`、`product_spec_source_or_parser_gap=136`。
  - Product/Business-KPI 仍为 `400/603`，CustomerDeployment `158/603`，CapitalMarketDetail `247/603`，MarketLiquidity `603/603`，full parity `3/603`。

R33 结论：这一轮把“官方产品页 -> 官方 spec/profile 细页 -> parser-backed runtime row”的链路接通，并修掉了明显噪声，但 product spec/profile 仍是 600+ 公司同等深度的主要短板。剩余缺口不能靠放宽 gate 解决，应继续做 family-specific locator / browser-rendered source discovery / PDF table parser / local IR deck parser，并将 healthcare bed/facility、software docs/API、semicap datasheet、cloud instance spec、retail store footprint、REIT property table 分拆为更细 adapter。

2026-06-25 R32c ProductSpec/Profile depth closure 更新：

- 新增 `company_disclosed_product_profile_context_rows_v0_1`，把 filings-first taxonomy、company-disclosed product/segment metric label、official product surface/category、official product catalog、regulated product/trial/vehicle rows、industry operating profile rows 投影为 bounded profile rows。
- 新增 runtime contracts：
  - `ProductProfileSlot`
  - `BusinessProfileSlot`
- 新增 / 接入 source roles：
  - `official_product_profile_spec`
  - `business_service_profile_spec`
- 接入位置：
  - `layer_acceptance_gates.py`：`product_spec_depth` 允许 `technical_product_spec`、`business_asset_profile_spec`、`official_product_profile_spec`、`business_service_profile_spec`。
  - `product_family_source_routes.py`：ProductFamilyRoutePlan 对 official product surface / V3-V8 service or asset families 增加 profile routes。
  - `build_product_family_source_route_plan.py` 和 `build_second_third_layer_depth_parity_matrix.py`：把 profile rows 纳入 source-route 和 depth parity 输入。
- 最新 profile projector 输出：
  - `row_count=8,880`
  - `ticker_count=603`
  - `ProductProfileSlot=8,827`
  - `BusinessProfileSlot=53`
  - 主要来源包括 `company_filing_taxonomy_candidate_profile=4,507`、`company_disclosed_product_or_segment_metric_profile=2,009`、`sec_filings_product_taxonomy_profile=1,815`、`official_product_catalog_profile=337`、`official_product_surface_category_profile=148`。
- 最新 depth parity：
  - `product_spec_depth=603/603`
  - `product_kpi_depth=400/603`，剩 `203` 家 Product/Business-KPI exact gaps。
  - `customer_deployment_depth=158/603`，剩 `445` 家 customer deployment / official order / public tender / supply-chain relationship gaps。
  - `capital_market_detail_depth=247/603`，剩 `356` 家 capital-market detail gaps。
  - `market_liquidity_depth=603/603`
  - full five-dimension parity `52/603`，backfill queue `1,004`。

R32c 边界：这次解决的是“每家公司至少有可绑定的产品/业务/资产 profile context”，不是 SKU 级收入、销量、ASP、份额、sell-through、库存、backlog、订单金额或 commercial tracker exact。`company_filing_taxonomy_candidate_profile` 是 candidate-backed bounded profile row，只能帮助 Research Lead / Product Specialist 确认公司业务和产品面，不允许在 Memo 中被写成财务事实或市场份额事实。后续 depth parity 的主战场转为 `Product/Business-KPI exact`、`CustomerDeployment` 和 `CapitalMarketDetail`。

2026-06-25 R35a Product/Business-KPI revenue-mix exact 更新：

- 新增 `company_disclosed_product_business_mix_runtime_rows_v0_1`，从 `product_kpi_source_specific_verifier_v0_1` 中抽取公司披露的产品/业务收入结构占比。
- 通过条件：
  - `source_id=company_product_kpi_facts_structured_metric_parser`
  - `metric_family=product_revenue`
  - `unit/unit_category` 或表格上下文可证明为 `percent_of_revenue`
  - value 在 `0-100`
  - 有结构化 row/column、产品或业务线绑定、period、source_url 和 citation
  - 拒绝 geography、total、customer/channel mix、growth/change、margin/expense、非 revenue mix、无结构化绑定的候选。
- 输出：
  - `row_count=1,174`
  - `ticker_count=70`
  - `structured_context_type=company_disclosed_product_business_mix_percent_fact`
  - `source_role=company_disclosed_product_kpi`
- closeout 修复：
  - `product_kpi_exact_slot_closeout_v0_1` 不再把 slot-only 标为 `product_kpi_exact_ready`；只有真实 runtime exact row 才可 ready。
  - AMT 这类“有 product slot 但无 value row”的状态降级为 gap，避免假 ready 进入后续 depth audit。
  - closeout 输入新增 `industry_operating_metric_slot_rows_v0_1` 和 `company_disclosed_product_business_mix_runtime_rows_v0_1`。
- 最新 Product/Business-KPI depth：
  - `product_kpi_depth=428/603`
  - 剩 `175` 家 Product-KPI gaps：
    - `filings_taxonomy_available_but_value_unit_period_product_kpi_absent=45`
    - `official_product_surface_available_but_company_disclosed_product_kpi_absent=129`
    - `product_context_available_but_no_company_disclosed_product_kpi_exact_slot=1`
  - full five-dimension parity `53/603`
- action plan 分类更新：
  - `source_specific_table_relation_parser_gap=22`
  - `company_disclosure_value_candidate_absent_or_locator_gap=23`
  - `classified_public_boundary_or_deep_adapter_gap=129`
  - `classified_product_kpi_boundary_or_deep_adapter_gap=1`

R35a 边界：收入结构占比可以支持“业务结构 / 产品组合 / 暴露方向”判断，但不能被写成绝对产品收入、ASP、销量、出货量、市占率、sell-through、backlog、订单金额或 commercial tracker facts。剩余 `22` 个 source-specific table relation parser gap 需要更细表格坐标/列组/period parser；剩余 `23` 个候选缺失项要继续查 IR deck、年报表格、local filing 或确认公司公开源不披露；`129` 个 official surface-only 公司不能用产品页替代 KPI。

### Phase 3：Leading Signal Source Layer 优先落 AI infra / Semis

目标：解决“产品/供应链/客户部署/市场预期信号不能进入有用判断”的核心问题。

优先 lane：

- GPU/accelerator、EDA/IP、foundry、semicap、memory/HBM、networking、server OEM、power/cooling、cloud infrastructure。

交付：

- `LeadingSignalSourceLayer` contracts：
  - `ProductArchitectureSignal`
  - `BenchmarkSignal`
  - `YieldCapacitySignal`
  - `CustomerDeploymentSignal`
  - `SupplyChainRampSignal`
  - `CapexBuildoutSignal`
  - `MarketExpectationSignal`
  - `TechnologyEcosystemSignal`
- 对 NVDA/AMD/INTC/GOOGL TPU/MSFT/AMZN/META/TSM/ASML/AMAT/LRCX/KLAC/DELL/SMCI/ANET/Vertiv 等代表公司做 first tranche。
- 将 product specs、generation edges、competitive comparable rows、customer deployment proxies、OEM/cloud instance availability、supplier/customer official news、mainstream reliable news 做成 parser-backed rows。
- 先只允许 AI/Semis 首批准入矩阵中的 `runtime_ready` rows 进入 specialist evidence bundle；未过 parser/verifier 的源只能进入 targeted repair plan。

通过条件：

- 每个 first-tranche ticker 至少有 `product_or_technology_signal`、`customer_or_supply_chain_signal`、`capex_or_market_expectation_signal` 中的 2 类可用 rows；找不到的必须是 attempt-backed boundary。
- 每个 first-tranche product family 满足 AI/Semis 首批 source-route 接入门槛；不满足时不能算该 family coverage pass。
- Product/Technology specialist 能生成“规格/代际 -> 竞品 -> 部署/供应链 -> 财务或预期桥”的 dimension model。
- Memo 不得把这些强信号写成 generic gap。

2026-06-23 首批 gate 状态：

- 已生成 `r18_ai_semis_source_route_gate_rows_v0_1` 和 summary/report。
- `assignment_count=56`，`pass_assignment_count=56`，`action_required_assignment_count=0`。
- hard gate：`unregistered_required_source_role_count=0`、`url_or_snippet_promoted_count=0`、`forbidden_claim_violation_count=0`。
- 第一批 AI/Semis source-route gate 已通过；后续 full-chain 仍必须由 Specialist / Memo / Verifier 检查这些 signals 是否被正确转成 bounded thesis driver，而不是写成产品收入、销量、ASP、份额、sell-through、backlog、订单金额或实时资金流。

2026-06-25 Customer / Deployment / Distribution depth update：

- 新增 `official_customer_deployment_surface_context_rows_v0_1`，从已经物化的 issuer official product surfaces 出发，补官方 customer/case-study/deployment/partner/ecosystem/supplier surfaces。
- 该 projector 明确把官方客户/部署/伙伴页面作为 L2 bounded thesis-driver signal：可支持客户部署、官方伙伴、供应链关系、验证线索；禁止推导 revenue、order value、backlog、shipment、ASP、sell-through、inventory、market share。
- 本轮修复了三类质量问题：
  - 不能把 URL/probe label 当成正文证据；common-path probe 必须从页面 title/body 中读到真实 customer / partner / case-study / supplier 等信号。
  - 不能让 careers、support、terms、privacy、contact、about/businesses、generic insight pages 进入 customer/deployment depth。
  - 不能使用 guess-only issuer domains。`company_name_domain_guess` 不能提权为 official host；ADP `automatic.com`、BBY `best.com` 这类错域被剔除并写入 attempt-backed boundary。
- 最新严格结果：
  - `official_customer_deployment_surface_context_rows_v0_1`: `336` rows / `126` tickers，其中 `official_customer_order_or_deployment_event=214`，`supply_chain_official_relationship=122`。
  - `second_third_layer_depth_parity_matrix_v0_1`: `customer_deployment_depth=387/603`，其中 strict customer/order/supply-chain signal `241`，bounded distribution/adoption proxy `146`。
  - 比 R30 baseline `158/603` 净提升 `229` 家；没有采用宽松 `407/603` 版本，因为该版本包含 SPA fallback / wrong-domain / label-self-proof 风险。
- 剩余 `216` 家 customer/deployment gap 的 attempt-backed 主因：
  - `action_gap_without_official_product_surface_seed=63`：没有可用 official product surface seed。
  - `no_verified_official_host_seed=20`：只有空 host 或 guess-only host，不能进入 runtime evidence。
  - `http_404=607` probe attempts：常见 official path 不存在。
  - `fetched_no_customer_or_partner_signal=65`：页面可抓但正文未出现可验证 customer/deployment/partner/supplier 信号。
  - 其余为 `http_403/http_429/http_406/http_307/http_464/fetch_failed/unsupported_content_type`，需要后续 Playwright、PDF parser、site-specific locator 或人工官方域修复。
- 当前结论：Customer/Deployment 维度已经从“只有少数公开订单/供应链 rows”升级为“官方客户/部署/伙伴 surface + 渠道/应用 adoption proxy”的严格 bounded signal 层；剩余缺口不是被隐藏，而是以 source/host/http/body-signal 分类进入下一轮修复。

### R36：三瓶颈深度修复结果

本轮针对 R35b 后最大的三个瓶颈做了一轮非 LLM 数据层修复：Product-KPI exact、Capital-market detail、ProductRelationshipGraph。目标不是把弱信号包装成强事实，而是在公开源可得范围内减少 parser / route 漏吃，同时把仍不能提权的边界写清楚。

1. Product-KPI / operating metric verifier

- 新增 column-group conflict resolver：当同一公司、同一 period / product / unit 下存在多个冲突值时，只在一个值可被兄弟 column-group 求和验证为 aggregate total 时提权该 aggregate row。
- 适用范围被限制在 `business_segment_revenue`、`backlog_or_orders`、`capacity_utilization_or_production_volume`、`unit_sales_or_deliveries`、`shipments` 等 operating metric slots。
- 不能通过求和验证的冲突仍保留 `conflicting_values_for_industry_operating_claim`，percentage/change、region-only、非产品/总表、sentence relation 不足的候选仍不得提权。
- 最新 `industry_operating_metric_slot_rows_v0_1` 为 `1,798` rows / `175` tickers，`conflict_resolved_non_aggregate_sibling=411`，`unclassified_rejection_count=0`。
- 最新 Product/Business-KPI depth 为 `432/603`，剩余 `171` 家：`official_product_surface_available_but_company_disclosed_product_kpi_absent=128`、`filings_taxonomy_available_but_value_unit_period_product_kpi_absent=42`、`product_context_available_but_no_company_disclosed_product_kpi_exact_slot=1`。这些不是缺少网页，而是公开披露没有稳定 value/unit/period/product exact slot，或需要更深的 source-specific table relation parser。

2. Capital-market detail

- `sec_capital_market_event_context` 增加 SEC submissions cache fetcher 和 603 公司 universe 映射，支持增量下载、本地 cache、并发 fetch、fetch ledger、ticker filtering。
- 修复 multi-ticker issuer 映射，避免 `BF-B` 这类 ticker 因 issuer payload 的 `tickers` 顺序被漏掉。
- 最新 SEC capital-market event metadata 为 `17,485` rows / `588` tickers：`securities_offering_filing_event=3,823`、`insider_transaction_filing_event=4,636`、`beneficial_ownership_filing_event=4,660`、`proxy_governance_filing_event=4,366`。
- 最新 CapitalMarketDetail depth 为 `587/603`。剩余 `16` 家：`15` 家为非美 / local exchange issuer，需要 local filing / IR / exchange adapter；`FDXF` 为 universe/entity 或 primary detail parser gap，当前只有 Form 3/4 metadata，缺 primary financial / working-capital / capital detail rows。
- 边界不变：SEC submissions metadata 只能证明 filing event 存在和时间，不能证明 offering amount、security terms、insider shares、beneficial ownership percentage、proxy vote、buyback amount 或 realtime flow。

3. ProductRelationshipGraph parser-backed edges

- ProductRelationshipGraph v2 接入 parser-backed relationship context rows，包括 official customer deployment、official supply-chain relationship、public order / tender context、channel / distribution context。
- 最新图谱为 `8,187` nodes / `25,251` edges / `6,521` product slots，`parser_backed_relationship_edge_count=741`。
- 新增关系边分布：`OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT=222`、`OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP=147`、`PUBLIC_ORDER_OR_TENDER_CONTEXT=273`、`CHANNEL_OR_DISTRIBUTION_CONTEXT=99`。
- 这些边用于 retrieval、specialist reasoning、read-through、竞争/供应链/客户部署上下文；不能直接推导 market share、sales、ASP、sell-through、backlog、订单金额或未披露产品 KPI。

4. 现在的二三层深度状态

- `product_spec_depth=603/603`
- `product_kpi_depth=432/603`
- `customer_deployment_depth=387/603`
- `capital_market_detail_depth=587/603`
- `market_liquidity_depth=603/603`
- full five-dimension parity 为 `279/603`，剩余 `324` 家至少一个维度未达到 depth target。

剩余 backfill queue 为 `403` 条：`customer_deployment_depth=216`、`product_kpi_depth=171`、`capital_market_detail_depth=16`。这说明当前最明显的“脚本漏吃”已经减少，但 600+ 公司同等深度仍未完成；下一轮应继续按 gap action plan 做 customer/deployment source locator、Product-KPI source-specific table parser、非美 local capital filing adapter，而不是把这些缺口用 bounded context 或 closeout rows 填平。

### R37：depth gate 校准和 operating slot 修复

R37 继续处理 R36 后的“可安全接入但 gate / parser 漏吃”问题。原则仍然是不放宽证据边界：已经 parser-backed 且具备 value / unit / period / citation / role 的 rows 可以进入对应 depth；attempt row、generic context、URL seed、产品收入伪装的 customer signal、普通损益科目伪装的 capital detail 均不得进入 depth parity。

1. CustomerDeployment operating footprint

- `CustomerDeployment` depth 新增 `business_operating_footprint_signal_ready`。
- 可接受 source roles 限于 `aum`、`backlog_or_orders`、`capacity_utilization_or_production_volume`、`production_or_throughput`、`same_store_sales_growth`、`shipments`、`unit_sales_or_deliveries`、以及 `business_asset_profile_spec`。
- 不接受 product revenue、generic business segment revenue、URL/path label、attempt-only rows 或没有 issuer/product/business binding 的 proxy。
- 最新 CustomerDeployment depth 为 `410/603`，其中 `241` strict customer/order/supply-chain signal、`146` bounded distribution/adoption proxy、`23` business operating footprint signal。

2. Non-US primary capital disclosure

- `CapitalMarketDetail` depth 新增 `non_us_primary_capital_disclosure_ready`。
- 非美 L1 财报 rows 只有在科目属于 assets、liabilities、equity、cash、debt、borrowings、capital、operating cash flow、capex、working capital 等 primary capital / balance sheet / cash-flow 维度时才可进入 capital depth。
- revenue、gross profit、operating profit、profit attributable 等普通损益科目继续只作为 financial statement rows，不满足 CapitalMarketDetail。
- 最新 CapitalMarketDetail depth 为 `601/603`：SEC capital terms / event context `587`，non-US primary capital disclosure `14`，剩 `2`。

3. Product/Business-KPI source-specific operating slot repair

- `Segment Orders` 在明确 segment / order context 下可作为 bounded `backlog_or_orders`。
- `Other sales` 只有在文本证明为 major customer type revenue disaggregation 时才可作为 `business_segment_revenue`。
- CVNA 类 `Retail units sold` 被上游误标为 `product_revenue` / USD thousands 时，按 raw text 和 row/product label 重写为 `unit_sales_or_deliveries`，单位转为 `units`，并保留 source value/unit provenance。
- 最新 `industry_operating_metric_slot_rows_v0_1` 为 `1,805` rows / `177` tickers，Product/Business-KPI depth 为 `434/603`。

4. R37 后的二三层状态

- `product_spec_depth=603/603`
- `product_kpi_depth=434/603`
- `customer_deployment_depth=410/603`
- `capital_market_detail_depth=601/603`
- `market_liquidity_depth=603/603`
- full five-dimension parity 为 `306/603`，剩余 `297` 家至少一个维度未达到 depth target。

剩余 backfill queue 为 `364` 条：`customer_deployment_depth=193`、`product_kpi_depth=169`、`capital_market_detail_depth=2`。其中 CustomerDeployment 剩余缺口没有可绑定 runtime rows，不能由 attempts 提权；Product-KPI 剩余缺口主要是公开披露无 product KPI exact slot 或需要更深 source-specific table relation parser；Capital 剩余为 Renesas non-US annual/securities report balance-sheet/cash-flow parser 和 FDXF parent-child entity boundary。R37 后 `second_third_layer_real_source_readiness_gate` 仍为 `603/603 pass`，但这只证明每家公司有真实 parser-backed L2/L3 source，不等于每家公司完成同等深度的产品 KPI、客户部署和资本细项覆盖。

5. R38：Payment / segment-growth operating slot 与 customer/capital 边界 closeout

- 新增 payment platform / payment network 经营指标 exact slot：`payment_transactions_per_active_account`、`tpv_mix_percent`、`total_payment_volume`、`processed_transactions`。这些 rows 只能支持支付 activity / TPV mix，不得当作 revenue、take rate、ASP、market share、sell-through、backlog 或 customer order value。
- 新增 `segment_revenue_growth`，只接受公司披露、带 value/unit/period/citation 的 segment 或 product-line revenue growth percentage；税率、FX、acquisition/divestiture、constant-currency bridge、纯地域表和普通 sentence relation 不能提权。
- CustomerDeployment 新增的可接受状态包括 regulated product / vehicle identity context 和 deferred revenue / contract-with-customer liability footprint，但普通 revenue、AR、inventory、generic CompanyFacts、macro official bridge、business segment revenue 不得替代 customer/order/deployment/channel/adoption 证据。
- 最新 `industry_operating_metric_slot_rows_v0_1` 为 `1,866` rows / `187` tickers，`unclassified_rejection_count=0`。
- 最新 depth matrix：
  - `product_spec_depth=603/603`
  - `product_kpi_depth=442/603`
  - `customer_deployment_depth=531/603`
  - `capital_market_detail_depth=601/603`
  - `market_liquidity_depth=603/603`
  - full five-dimension parity 为 `399/603`，剩余 `204` 家至少一个维度未达到 depth target。
- 剩余 backfill queue 为 `235` 条：`product_kpi_depth=161`、`customer_deployment_depth=72`、`capital_market_detail_depth=2`。
- 剩余边界：
  - Product-KPI 剩余主要是 `123` 家 official product surface 可得但公司未披露 product KPI exact、`37` 家 filings taxonomy 有方向但 relation parser/value-unit-period-product 仍不能安全提权、`1` 家 product context 有但 exact slot 缺失。
  - CustomerDeployment 剩余 `72` 家都有财务或宏观/官方 context rows，但没有可绑定的 customer/order/deployment/channel/adoption/regulated/contract-liability/operating-footprint rows；不能用普通会计收入或 macro bridge 糊掉。
  - Capital 剩余 `6723.T` Renesas 和 `FDXF`：前者缺非美 annual securities report BS/CF/capital tables，后者不能直接继承 FDX 母公司资本结构。
  - `second_third_layer_real_source_readiness_gate` 仍为 `603/603 pass`；这只是 source readiness，不等于 depth parity。

6. R39：Product-KPI parser / boundary 分类收紧与 Marketplace GOV 经营指标修复

- Product/Business-KPI gate 新增 `marketplace_gross_order_value` 行业经营指标槽位，用于 DoorDash / marketplace 平台公司披露的 Gross Order Value / Marketplace GOV。该槽位只能支持公司披露的 marketplace operating volume，不得写成 revenue、take rate、ASP、market share、sell-through、backlog 或 customer order value。
- 修复 GOV parser false positive：只允许 `row_label/product_or_segment/column_label` 本体命中 Marketplace GOV / GMV / gross order value；如果只是同一 citation/table 中出现 Marketplace GOV，`Adjusted EBITDA`、`GAAP gross profit`、`Contribution Profit`、`diluted shares` 等邻近行不得被提权。
- Product/Business-KPI business-segment revenue parser 新增 period-column gate：`(dollars in millions)`、`(in millions)` 等单位列不能当作事实列；业务/segment revenue 行必须和 fiscal period 对齐。
- 新增 forbidden operating context gate，拒绝把投资现金流、费用表、税率 / non-GAAP bridge、FX/acquisition/divestiture bridge、production payment obligation 提权为行业经营指标。
- 最新 `industry_operating_metric_slot_rows_v0_1` 为 `1,919` rows / `185` tickers，`unclassified_rejection_count=0`；其中 `marketplace_gross_order_value=3`，均为 DASH FY2023-FY2025 Marketplace GOV。
- 最新 depth matrix：
  - `product_spec_depth=603/603`
  - `product_kpi_depth=441/603`
  - `customer_deployment_depth=531/603`
  - `capital_market_detail_depth=601/603`
  - `market_liquidity_depth=603/603`
  - full five-dimension parity 为 `398/603`，剩余 `205` 家至少一个维度未达到 depth target。
- 最新 backfill queue 为 `236` 条：`product_kpi_depth=162`、`customer_deployment_depth=72`、`capital_market_detail_depth=2`。
- Product-KPI gap 分类现在更接近真实可修性：
  - `source_specific_table_relation_parser_gap=2`：`CME` 和 `IR`。`CME` 仍需要 source-specific Other revenues / fee-agreement table column-group parser；`IR` 是 Segment Orders 两个 segment 值丢失 segment label，需要 segment dimension/schema 修复。
  - `non_promotable_public_disclosure_boundary=11`：`ANET/AIG/CFG/MCO/ECL/LAC/NDSN/PH/PNW/MAR/MKC`。这些候选主要是 geography-only、total/non-product revenue、investment cash-flow rows、tax/FX/non-GAAP bridge、production payment obligation、regional cross-tab 或 sentence change row，公开披露存在但不能安全提权为 Product-KPI exact。
  - `company_disclosure_value_candidate_absent_or_locator_gap=23`：有 taxonomy/filing 方向，但当前公开披露扫描没有 company-disclosed value/unit/period/product KPI 候选。
  - `classified_public_boundary_or_deep_adapter_gap=122`：官方产品面存在，但公司没有披露可提权 Product-KPI exact；后续只能继续深挖 IR deck/local filing/source-specific table，仍找不到则暴露 public-source / commercial-tracker gap。
- CustomerDeployment 剩余 `72` 家复核后均只有宏观/FRED/EIA/OpenAlex、财务三表、产品收入或 business segment rows 等非 customer/deployment 信号；没有 issuer-bound customer、order、deployment、channel adoption、regulated identity、contract liability 或 operating footprint row。不能用 ordinary revenue、business segment revenue、macro bridge 替代。
- Capital 剩余 `6723.T` 和 `FDXF` 复核：
  - `6723.T` Renesas 当前只有 FY2025 Revenue、Gross profit、Operating profit、Profit attributable to owners of parent，缺 assets / liabilities / equity / cash / debt / capex / cash-flow / financing rows。
  - `FDXF` 只有 parent/segment operating income 和 Form 4 metadata；缺独立主体 debt / credit / working-capital / capital detail rows，不能继承 FDX 母公司资本结构。

7. R40：`CME` / `IR` source-specific Product-KPI closeout

- 不再把 `CME` / `IR` 留作宽泛 `source_specific_table_relation_parser_gap`：
  - `IR`：SEC Segment Results 原文表明确包含 `Industrial Technologies and Services Segment Results` 与 `Precision and Science Technologies Segment Results`，现已从表标题恢复 segment binding，并重新抽出 FY2024/FY2025 `Segment Orders`。旧 verifier 把 2024 值误标成 2025 的 rows 仍保持 rejected，不放宽 gate。
  - `CME`：SEC Cash Markets Business table 中的 `BrokerTec fixed income transaction fees`、`EBS foreign exchange transaction fees` 已按 `(amounts in millions)` 还原为 USD amount rows，作为 company-disclosed product/business-line revenue amount exact facts；费用表中的 `Licensing and other fee agreements`、Technology、Professional fees 等仍按 expense / change table boundary 拒绝。
- runtime rows：
  - `product_kpi_source_specific_verifier_promotable_rows_v0_1`：`12` 条 `CME` source-specific corrected rows。
  - `company_disclosed_product_business_mix_runtime_rows_v0_1`：`1,186` rows，其中 `company_disclosed_product_business_mix_percent_fact=1,174`，`company_disclosed_product_business_revenue_amount_fact=12`。
  - `industry_operating_metric_slot_rows_v0_1`：`1,923` rows / `186` tickers，其中 `IR` 有 `4` 条 accepted `backlog_or_orders` segment order rows。
- 最新 depth matrix：
  - `product_spec_depth=603/603`
  - `product_kpi_depth=443/603`
  - `customer_deployment_depth=531/603`
  - `capital_market_detail_depth=601/603`
  - `market_liquidity_depth=603/603`
  - full five-dimension parity 为 `400/603`，剩余 `203` 家至少一个维度未达到 depth target。
- 最新 backfill queue 为 `234` 条：`product_kpi_depth=160`、`customer_deployment_depth=72`、`capital_market_detail_depth=2`。
- `source_specific_table_relation_parser_gap=0`。剩余 Product-KPI 不是“当前已知 SEC 表 parser 小修即可提权”的状态，而是：
  - `122` 家 official product surface / product context 有，但公司公开披露未给 product-KPI exact row，或需要更深 IR deck/local filing/source-specific adapter 继续确认；
  - `23` 家 taxonomy/filing 方向存在但当前扫描没有 value/unit/period/product candidate；
  - `11` 家只有 geography、generic total、cash-flow、expense、tax/FX/non-GAAP bridge、production payment obligation 或其他 non-promotable public rows；
  - `4` 家属于更宽的 product-KPI public/commercial boundary 或 deep-adapter gap。
- CustomerDeployment `72` 复核后不是 gate 漏接：这些公司在 customer row paths 里只有宏观/FRED/EIA/OpenAlex、普通 SEC financial statement rows、产品收入或 business segment rows，没有 issuer-bound customer/order/deployment/channel adoption/regulated identity/contract-liability/operating-footprint rows。
- Capital `2` 仍保留边界：`6723.T` 需要 Renesas local/non-US BS/CF/debt/cash/capex/capital parser；`FDXF` 需要 standalone issuer capital detail 或明确 parent-child inheritance policy。

### Phase 4：Capital / Funding / Ownership / Market Liquidity Layer

目标：补齐顶级研报非常重视、当前输出薄弱的资金和融资维度，同时把三大表、同行同口径、行业财务重点指标和资本/产品桥接做成常态化基本面分析，而不是只在 memo 中零散列财务数字。

交付：

- `FundamentalPeerStatementPanel`：
  - `ThreeStatementMetricPanel`
  - `PeerComparableMetricPanel`
  - `IndustryFinancialFocusPolicy`
  - `DerivedMetricLayer`
  - `ProductFinancialBridge`
  - `CapitalFundingBridge`
  - `StatementAnomalyDetector`
- `CapitalStructureInstrumentGraph`：debt instruments、credit facility、leases、convertible、maturity、rate/coupon、covenant、offering。
- `WorkingCapitalLiquidityPack`：cash、short-term investments、AR、inventory、AP、deferred revenue、current liabilities、short-term debt、CFO、FCF、cash conversion cycle。
- `OwnershipFlowGraph`：13F、13D/13G、Form 3/4/5、DEF 14A、N-PORT、insider、activist、fund ownership。
- `MarketLiquidityDriver`：short interest、volume/turnover、options IV、rates、credit spread、ETF/factor flow。
- `CapexFundingBridge`：capex need、operating cash flow、external financing、debt/lease/private credit/securitization capacity、ROI risk。

通过条件：

- 标准 memo 至少覆盖三表中的两个，深度 memo 覆盖 income statement、balance sheet、cash flow statement 全部。
- 深度 memo 必须使用同行同口径 panel，并解释同行选择口径；缺同行数据时必须触发 retrievable/bounded gap，而不是静默跳过。
- 行业 focus policy 必须影响指标选择：银行、SaaS、重资产、零售/餐饮、医药、能源/公用事业等不能使用同一组 generic metrics。
- 派生指标必须从三表和同行面生成，包括 margin、cash conversion、working-capital、debt/liquidity、capex intensity、FCF conversion、R&D/S&M intensity 等。
- 财务判断必须和产品/行业/资本层桥接：产品规格/部署/订单信号是否被 revenue、margin、inventory、deferred revenue、capex、OCF/FCF 或 debt capacity 支撑。
- AI infra case 能明确写出 hyperscaler capex vs operating cash flow / external financing / supplier read-through 的资金桥。
- Capital specialist 不再只列 debt facts，而是产出 capital dimension model 和风险/触发条件。
- 13F/Form4/rates/flow 的时滞和边界被 verifier 检查。

### Phase 5：主题到投资表达的 KG 扩展

目标：让复杂问题不是只回答“哪个公司相关”，而是回答“主题如何表达、谁直接受益、谁间接受益、证据强度如何”。

交付：

- `ThemeToExpressionGraph`
- `ValueChainLayerMap`
- `BeneficiaryAndEnablerMap`
- `ExposureConfidence`
- `EstimateExpectationGraph`
- `CatalystEventGraph`
- `BusinessRevenueExposureGraph`

通过条件：

- 机器人 / AI infra / GLP-1 / cloud capex / auto electrification 至少各有一个 representative graph case。
- 每个 graph edge 都有 evidence refs、authority type、confidence、forbidden claims。
- Research Lead 可用该图谱生成 comp set、read-through 和 counter-thesis。

### Phase 6：Research Lead / Specialist / Memo 合同升级

目标：把 agent graph 从“证据搬运 + 写作器拼接”升级成“研究主编监督 + 维度分析模型 + 表达器”。

交付：

- `InvestmentDebateContract` / `TopOfMindQuestionSet`：核心争议、为什么现在、市场隐含预期、必答维度、反证和触发条件。
- `DimensionModel`：Fundamental、Product/Technology、Industry/Supply Chain、Capital/Ownership、Market/Valuation、Risk/Counter-thesis 各自输出机制链和判断，不输出 row summary。
- `LeadReviewCheckpoint v2`：读取 exact coverage、signal coverage、source attempt ledger、gap ledger、specialist dimension models，决定 targeted repair 或进入 MemoLogicPlan。
- `MemoLogicPlan v2`：主输入来自 InvestmentDebate + DimensionModel + JudgmentState + Valuation/Scenario bridge。

通过条件：

- Memo Writer 正文不出现内部字段，不写模板化机制串。
- 核心判断必须包含方向、核心因果链、最强证据、主要反证、边界和 what-would-change-view。
- 投资含义必须先有判断，再写如何验证；不能通篇写“数据不足所以不能判断”。

### Phase 7：Eval / Full-chain release gate

目标：用系统化 eval 防止“看起来通过、读起来没用”的问题复发。

新增 gate：

- `judgment_density_gate`：核心判断中有效 thesis driver 数、反证数、可操作触发条件数。
- `caveat_overuse_gate`：缺口说明不能压过判断主体。
- `signal_to_thesis_gate`：强信号必须被转成 bounded thesis driver。
- `dimension_balance_gate`：财务、产品、行业/供应链、资本/资金、估值/市场、风险不能严重缺项。
- `source_boundary_gate`：proxy 不得冒充 exact；commercial gap 不得被填平。
- `valuation_bridge_presence_gate`：深度研究必须有估值/情景/资金桥之一。

执行顺序：

1. 先跑 deterministic / fixture / node eval。
2. 再跑 2 个 high-activation full-chain cases：AI infra capex/supply-chain；non-US/healthcare 或 software/cloud。
3. 修 root cause 后跑 12-case successor。
4. 最后跑 20-case broader release gate 和 backend/frontend trace 检查。

通过条件：

- 2-case 不只 gate pass，还要人工读报告达到“有观点、有证据、有边界、有反证、有下一步触发”的标准。
- 12/20-case report 生成 release readiness report，列出质量、成本、时延、source gaps、commercial gaps 和失败生命周期。

### Phase 8：执行纪律

- 每个阶段先落 contract / registry / gate，再批量跑数据。
- 每个数据源接入或修复都必须更新 Data Source Admission Ledger；不能只写脚本跑通或 coverage pass。
- 公开源理论可得但 parser/source route 没吃到，标记 `route_or_parser_debt`，继续修，不允许直接 final gap。
- 公开源存在但只能支撑方向，标记 `signal_boundary`，进入 thesis driver，不冒充 exact。
- 公开免费源确实不存在或受限，标记 `commercial_tracker_gap` 或 `manual_primary_research_gap`。
- 所有阶段更新 worklog、master checklist、README；涉及数据/模型/索引/LLM 的运行要进入 run/eval ledger。
