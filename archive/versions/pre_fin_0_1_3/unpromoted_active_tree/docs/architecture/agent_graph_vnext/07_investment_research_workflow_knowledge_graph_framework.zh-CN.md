# 投研工作流知识图谱升级框架

本文件是对 `投研工作流知识图谱框架.docx` 的工程化整理，并合并后续关于“专家 agent 升级为次级 agent”和“产品边细化到规格/公开订货视角”的讨论。

核心判断：只看财报做不出像样的研报工作流。财报回答的是已经发生的收入、利润、现金流和会计确认；研报还必须回答业务现在怎么样、产品竞争力怎么样、需求和供给有没有变化、渠道和客户有没有变化、市场预期有没有错、融资环境是否影响估值和扩张。

因此，数据库矩阵和 agent graph 的下一阶段目标不是更大的财报 RAG，而是五层图谱加一层工作流治理：

```text
Layer 0: Entity / Identifier Master
Layer 1: Business Operating Graph
Layer 2: Capital / Ownership / Financing Graph
Layer 3: Macro / Industry Driver Graph
Layer 4: Evidence / Claim / Gap Layer
Layer 5: Workflow Runtime Layer
```

其中 Layer 0 解决跨源身份和别名，Layer 1-3 承载投研对象和关系，Layer 4 控制证据、反证和缺口，Layer 5 决定 agent 如何读取、分发、验证和记忆这些对象。

## 1. 先定义对象，不先定义来源

知识图谱不能从“还能爬什么数据源”开始，而要从研报问题需要哪些对象开始。至少需要这些核心对象：

```text
Company
 -> Segment
 -> Product / Service
 -> Product KPI
 -> Customer / Channel
 -> Supplier / Partner
 -> Capacity / Production Asset
 -> Region
 -> Competitor
 -> Regulatory Status
 -> Technology / Patent / R&D
 -> Financing / Ownership / Capital Structure
 -> Macro / Industry Driver
```

真正有价值的是对象之间的关系：

- 公司 -> 产品 -> 收入、销量、出货、订阅数、ARPU、ASP。
- 公司 -> 客户 -> 收入暴露、大客户依赖、合同。
- 公司 -> 供应商 -> 供给约束、成本、产能。
- 公司 -> 行业变量 -> 利率、需求、库存、价格周期。
- 公司 -> 融资结构 -> 债务到期、利率敏感性、回购、增发。
- 公司 -> 投资人 -> 13F 持仓、内部人交易、大股东变化。

这意味着目标不是做一个“产品销量库”，而是构造两张业务图谱，再用 Claim Evidence Layer 控制每条结论的证据强度。

## 2. 业务知识矩阵的来源和边界

### A. 公司自己披露：业务图谱主锚点

来源包括：

- 10-K / 10-Q
- 8-K
- 20-F / 6-K
- S-1 / F-1
- Investor Day
- Earnings call transcript
- IR presentation
- Press release
- Product page
- Annual report business section
- Segment footnote
- Risk factor
- MD&A
- backlog / orders / deliveries / subscribers disclosure

能支持：

- 公司有哪些业务线。
- 公司如何划分 segment。
- 产品/服务名称。
- 主要收入来源。
- 客户集中度。
- 订单、backlog、交付、订阅等公司披露 KPI。
- 产能、工厂、地区。
- 风险因素。
- 管理层对需求、库存、价格、竞争的解释。

边界：

- 公司没披露的产品销量、客户级出货量、SKU 利润率，公开源不能硬推。
- official product page 可以证明产品存在、定位、功能和公司推广方向；没有数字时不能支持销量或收入。

### B. 官方监管/产品数据库：补产品状态和业务事件

医药/医疗器械：

- ClinicalTrials.gov
- openFDA
- FDA approvals / labels / recalls / adverse events

能支持 pipeline 产品存在、临床阶段、适应症、试验状态、监管事件、召回和不良事件信号。不能支持商业放量、销售额、市场份额、疗效确定性或未来审批成功。

汽车：

- NHTSA vPIC
- NHTSA recalls / complaints
- EPA fuel economy

能支持车型识别、车辆安全事件、召回、质量风险信号。不能直接支持销量、利润率、订单或交付量。

政府合同/国防/公共部门客户：

- USAspending
- SAM.gov
- 政府采购公告
- awarded contract data

能支持公司是否获得政府合同、合同金额、授予机构、合同时间和客户类型。不能直接等同最终收入确认，仍要回到财报、订单披露或 backlog 验证。

### C. 行业/宏观/贸易数据：补业务外部环境

来源包括：

- FRED
- BEA
- BLS
- Census
- EIA
- USITC / Census trade
- Fed SLOOS

能支持利率环境、信用环境、需求周期、库存周期、行业产量、能源价格、进出口趋势、区域经济和融资条件。

边界：

- 这些数据永远是 `context / driver / macro condition`。
- 不能直接升级为 company fact。
- 中间必须有 `Company -> Exposure -> Driver`，否则不能从宏观变量跳到公司结论。

### D. 技术、研发、IP、招聘和产品信号

来源包括：

- PatentsView / USPTO
- OpenAlex
- 公司招聘页面
- GitHub / developer docs
- 产品文档
- 技术白皮书
- 标准组织

能支持公司在哪些技术方向布局、研发主题变化、专利密度、产品技术路线和生态合作方向。

边界：

- 只能作为 `technology signal / lead discovery`。
- 不能直接支持商业化成功、销售收入或护城河确定成立。

### E. 渠道、终端需求和产品热度 proxy

来源包括：

- 电商平台
- App Store / Google Play 排名
- 网页流量
- Google Trends
- 社媒声量
- 评论数据
- 招聘数量
- 渠道库存新闻
- 第三方行业 tracker

公开源可以做 proxy，但不能默认当事实。图谱里必须标记：

```text
observed_channel_signal
not_total_company_sales
not_claim_authority
```

示例边界：

- 京东销量或评价数只能说明京东渠道样本表现。
- App ranking 只能说明 app relative popularity。
- Google Trends 只能说明搜索热度。
- 招聘只能说明扩张或投入信号。
- 这些都不能直接写成“公司销量增长”。

很多高质量终端需求数据属于商业边界，例如 Sensor Tower、Similarweb、data.ai、NielsenIQ、Euromonitor、GfK、IDC、Counterpoint、Canalys、PitchBook、Crunchbase、FactSet Supply Chain、Bloomberg SPLC。没有这些商业数据时，系统必须暴露 `commercial_gap`，不能用弱 proxy 兜底。

## 3. 投融资情况必须拆成四类

### A. 公司自身融资能力：债务、股权、现金流

这是最接近基本面研报的资本结构层。

来源包括：

- 10-K / 10-Q debt footnote
- cash flow from financing activities
- 8-K financing events
- S-1 / S-3 / F-1 / F-3
- 424B prospectus
- credit agreement exhibits
- bond offering documents
- debt maturity table
- share repurchase authorization
- dividend policy
- convertible notes
- lease obligations

需要抽取：

- cash
- total debt
- net debt
- interest expense
- weighted average interest rate
- debt maturity schedule
- credit facility size
- available liquidity
- covenants
- share repurchase
- dividends
- equity issuance
- convertible debt

这层回答：公司缺不缺钱、有没有债务墙、高利率是否压利润、还能不能回购、扩张靠经营现金流还是融资、融资成本是否上升。

### B. 公开市场债券和信用状况

来源包括：

- FINRA TRACE
- 公司债价格/收益率
- credit spread
- bond maturity
- rating action
- CDS，通常是商业数据

公开可得部分可以支持公司债交易活跃度、收益率变化、信用利差变化和市场对信用风险的定价。完整历史、评级、CDS 和债券估值曲线常进入商业数据边界。

### C. 股东和机构投资图谱

来源包括：

- SEC Form 13F
- Schedule 13D / 13G
- Form 3 / 4 / 5 insider transactions
- proxy statement

能支持机构持仓变化、大股东变化、主动投资者进入、内部人买卖、股权激励/期权相关交易和所有权集中度。

边界：

- 13F 有滞后。
- 13F 主要是 long positions。
- 13F 不等于实时资金流。
- 13F 不覆盖所有空头、衍生品和海外持仓。

因此这层是 `lagged ownership graph`，不能写成实时资金正在流入。

### D. 私募融资、创业公司融资、战略投资

来源包括：

- Form D
- 公司公告
- 新闻稿
- 被投企业官网
- PitchBook / Crunchbase / Preqin，商业数据

公开源能支持某公司、子公司或私企是否有私募发行、发行金额、security type、offering date 和部分 investor type 信息。

边界：

- 不能完整替代 PitchBook / Crunchbase。
- 估值信息常缺。
- 投资人细节常缺。
- 全球覆盖有限。
- 轮次标签不统一。

应标记为：

```text
private_financing_lead
not_complete_private_market_database
```

## 4. 投研问题驱动的核心 schema

不要做公司百科图谱，而要做投研问题驱动图谱。

### Layer 0: Entity / Identifier Master

跨源 join 的基础必须先硬起来，否则后续会把 ticker、法律实体、品牌、子公司、产品归属和证券标识混在一起。

核心对象：

```text
Company
LegalEntity
Security
Brand
ProductAlias
IndustryClassification
ExchangeIdentifier
```

建议字段：

```yaml
entity_id: string
issuer_id: string | null
legal_name: string
ticker: string | null
exchange: string | null
cik: string | null
lei: string | null
figi: string | null
isin: string | null
cusip: string | null
sedol: string | null
company_domain: string | null
ir_domain: string | null
subsidiaries: list[string]
brands: list[string]
product_aliases: list[string]
source_priority: list[string]
resolution_confidence: string
```

来源优先级：

- SEC company submissions：CIK、filing history、issuer identity。
- GLEIF：LEI、legal entity、部分 parent/child 关系。
- OpenFIGI：security identifier mapping。
- 公司 IR / 年报：官方名称、子公司、品牌、地区。
- Wikidata：低权重 alias candidate，只能辅助。

这层只做 resolver，不证明经营事实。

### Company

```yaml
entity_id: string
ticker: string
cik: string | null
lei: string | null
exchange: string | null
sector: string | null
industry: string | null
reporting_currency: string | null
```

### BusinessSegment

```yaml
segment_id: string
company_id: string
segment_name: string
revenue: number | null
operating_income: number | null
margin: number | null
period: string
source_id: string
```

### Product

```yaml
product_id: string
company_id: string
product_name: string
segment_id: string | null
product_category: string | null
launch_status: string | null
official_url: string | null
source_strength: string
```

### OperatingMetric

```yaml
metric_id: string
company_id: string
product_id: string | null
segment_id: string | null
metric_name: string
value: number | string | null
unit: string | null
period: string | null
source_id: string
disclosure_type: company_disclosed | official_context | public_proxy | commercial_gap
```

### CustomerRelationship

```yaml
company_id: string
customer_entity_id: string | null
relationship_type: string
revenue_exposure: number | string | null
contract_value: number | string | null
period: string | null
confidence: string
source_id: string
```

### SupplierRelationship

```yaml
company_id: string
supplier_entity_id: string | null
input_product: string | null
dependency_type: string
evidence_type: string
confidence: string
source_id: string
```

### CapitalStructure

```yaml
company_id: string
cash: number | null
debt: number | null
net_debt: number | null
maturity_bucket: string | null
coupon: string | null
interest_rate_type: fixed | floating | mixed | unknown
covenant_flag: boolean | null
source_id: string
```

### OwnershipPosition

```yaml
investor_id: string
company_id: string
shares: number | null
value: number | null
filing_date: date
report_period: string
form_type: 13F | 13D | 13G | Form3 | Form4 | Form5 | proxy
lag_policy: string
```

### MacroDriver

```yaml
driver_id: string
series_id: string
variable_name: string
value: number | null
date: date
frequency: string
source_id: string
```

### Claim

```yaml
claim_id: string
claim_text: string
supported_by: list[string]
contradicted_by: list[string]
gap_type: string | null
confidence: string
as_of_date: date
```

每条 node 和 edge 都必须带：

```yaml
source_id: string
source_strength: S5 | S4 | S3 | S2 | S1 | S0
as_of_date: date
period: string | null
gate_status: candidate | parser_verified | promoted | rejected | gap_only
claim_scope: list[string]
exact_value_authority: boolean
```

否则图谱会变成一堆看似合理、但无法审计的关系。

### Layer 4: Evidence / Claim / Gap Layer

最终研报不是直接输出 fact，而是输出 claim。必须把原子事实、上下文、反证和缺口聚合到 Claim Evidence Ledger。

`SourceArtifact`：

```yaml
source_id: string
raw_url: string | null
local_path: string | null
file_type: html | pdf | xbrl | json | csv | text
retrieved_at: datetime
source_as_of_date: date | null
checksum: string
parser_version: string
license_policy: string | null
robots_policy: string | null
access_method: string
document_id: string | null
```

`AtomicFact`：

```yaml
fact_id: string
source_id: string
entity_id: string
metric_id: string
value: number | string
unit: string | null
period: string | null
citation_anchor: string | null
gate_status: string
```

`ClaimEvidenceLedger`：

```yaml
claim_id: string
run_id: string
ticker: string
claim_text: string
claim_type: string
supporting_evidence_ids: list[string]
contradicting_evidence_ids: list[string]
source_strength: string
confidence: string
as_of_date: date
claim_status: supported | weakly_supported | contradicted | gap_exposed
required_gate_results: list[string]
```

`GapLedger` 必须类型化，而不是只存数量：

```text
not_disclosed
not_found
parser_failed
source_boundary_blocked
period_gap
unit_gap
alias_gap
commercial_gap
conflict_gap
staleness_gap
coverage_gap
```

### 数据治理辅助层

这些层不一定都进入 KG 主图，但必须存在于 evidence-governed runtime：

- `As-of / Vintage Layer`：区分 fiscal period end、filing date、accepted date、reported date、observation date、retrieved_at、macro vintage、parser_run_at。
- `Reconciliation Ledger`：解决多源、单位、期间、taxonomy、amendment、segment 和 rounding 冲突，决定最后哪个值能进入 claim。
- `Metric / Product Ontology`：统一 financial metric、product KPI、alias、unit、period rule、allowed source type 和 cannot_infer_from。
- `Source Capability Router`：根据 query intent、ticker、industry、metric type、claim type 和 required authority 决定 primary / secondary / context / forbidden sources 和 gap policy。
- `Gate Registry / Gate History`：保存 source boundary、citation span、period alignment、unit normalization、numeric consistency、metric mapping、entity resolution、claim support、contradiction、staleness、commercial gap 等 gate 的定义和运行结果。
- `Derived Metric Layer`：保存 YoY、QoQ、margin、FCF、net debt、ROIC、ASP、ARPU、take rate 等派生指标，并强制保存 input_fact_ids。
- `Analyst View / Research Memory`：保存 company profile、segment model、product KPI view、earnings change view、risk factor view、bull/bear debate、thesis tracker，并能反查 evidence。

## 5. Source hierarchy 的业务图谱解释

### S5：公司级事实

来源：

- SEC filing
- Company IR
- Annual report
- Official earnings release
- Official product KPI disclosure
- Debt footnote
- Offering prospectus

能支持公司收入、利润、债务、订单、产品 KPI、资本结构。

### S4：公司自有业务上下文

来源：

- 公司官网产品页
- 产品文档
- 投资者日材料
- press release
- official blog

能支持产品存在、产品定位、功能变化和战略方向。如果没有数字，不能支持销量或收入。

### S3：官方监管/行业对象

来源：

- ClinicalTrials
- openFDA
- NHTSA
- USAspending
- PatentsView
- Census trade

能支持产品监管状态、政府合同、专利/技术方向、贸易背景和行业活动。

### S2：宏观/行业背景

来源：

- FRED
- BEA
- BLS
- EIA
- Census
- Fed SLOOS

能支持资金环境、利率环境、行业需求背景、能源/贸易/就业/通胀。

### S1：发现线索

来源：

- news
- GDELT
- Common Crawl
- social
- job postings
- reviews
- search trend

只能做 lead discovery、signal 和 follow-up verification，不能直接进入核心 claim。

## 6. 两张主图谱

### Business Operating Graph

回答：

- 公司靠什么业务赚钱？
- 业务增长来自哪个产品、地区、客户？
- 增长是价格、销量、mix、渠道、产能还是周期驱动？

核心节点：

```text
Company
Segment
Product
KPI
Customer
Channel
Supplier
Capacity
Region
Competitor
RegulatoryEvent
TechnologySignal
```

核心边：

```text
Company -reports_segment-> Segment
Segment -contains_product-> Product
Product -has_kpi-> OperatingMetric
Company -sells_to-> Customer
Company -depends_on-> Supplier
Company -has_capacity-> Asset
Product -regulated_by-> RegulatoryBody
Company -competes_with-> Competitor
```

### Capital & Ownership Graph

回答：

- 公司融资能力怎么样？
- 资本市场怎么定价它？
- 谁在买卖它？
- 债务压力大不大？
- 高利率对它伤害多大？

核心节点：

```text
Company
DebtInstrument
EquityOffering
CreditFacility
Investor
Insider
Fund
Bond
MacroRate
CreditSpread
```

核心边：

```text
Company -issued-> DebtInstrument
Company -filed_offering-> EquityOffering
Company -has_credit_facility-> CreditFacility
Investor -holds-> Company
Insider -traded-> Security
Bond -priced_at-> Yield
Company -sensitive_to-> MacroRate
```

这两张图合起来，才接近真正研报工作流。

## 7. 产品边细化：从产品存在到产品规格和可比维度

产品不是普通网页文本，而是业务事实的一部分。当前产品图谱如果只回答“公司有哪些产品、披露了什么产品 KPI”，还不足以支撑历史产品对比、竞品比较和产品到财务判断。

因此在 Business Operating Graph 下新增：

```text
ProductFamily
ProductModel
ProductSpec
ProductGenerationEdge
CompetitiveComparableEdge
ChannelOffer
FieldInquiryNote
```

### ProductFamily

产品线或药品、车型、软件平台家族。例如 iPhone、H100、Model Y、Keytruda、Azure AI。

### ProductModel

具体型号、SKU、配置、地区版本、generation。例如 iPhone 16 Pro 256GB、H200 SXM、Model Y Long Range。

### ProductSpec

规格参数项，包括数值、单位、配置、适用地区、发布日期、来源。例如算力、功耗、内存、带宽、续航、剂量、适应症、尺寸、价格、订阅层级、API 限额。

### ProductGenerationEdge

连接上一代、当前代、下一代产品，支持历史产品对比和代际改进判断。

### CompetitiveComparableEdge

连接本公司产品和竞品，必须记录可比维度，不能只靠名称相似。

### ChannelOffer

公开订货、电商、分销商目录、公开报价页中的价格、库存状态、交期、配置、地区、时间。

边界：

- 可支持 price context、availability context、configuration context。
- 不能支持公司总销量、真实 sell-through、market share、company ASP 或 channel inventory。

### FieldInquiryNote

用户或 analyst 以正常终端用户、采购员、经销商调研视角询问公开销售渠道后提供的记录。

边界：

- 可作为定性渠道线索、报价/交期样本、待验证 lead。
- 不能作为权威产品事实或公司级经营结论。
- 必须记录提供者、时间、询问对象、原始截图/邮件/记录可用性、适用范围和可信度。

## 8. 公开采购视角：public_buyer_observer

这里允许的是正常市场调研视角，不是身份冒充或权限绕过。Agent skill 和 prompt 必须使用 `public_buyer_observer` 这类角色描述。

允许：

- 像普通终端用户、采购员、开发者或经销商调研人员一样访问公开网页。
- 搜索公开产品页、公开报价页、公开电商页面、公开 B2B 分销商目录、公开 documentation 和公开 support/pricing 页面。
- 记录公开可见的价格、库存、配置、交期、型号、地区和更新时间。
- 消费用户提供的真实询问记录，并按 FieldInquiryNote 降权处理。

禁止：

- 假冒资质、公司身份、经销商身份、医生身份、采购授权或监管身份。
- 绕过登录、付费墙、dealer portal、内部系统、验证码或权限控制。
- 提交虚假表单、创建虚假账号、实际下单、接受合同或触发商业承诺。
- 把公开订货页面、评论、排名、搜索热度写成销量、份额、渠道库存或公司 ASP。

## 9. 次级 Agent 如何使用知识图谱

专家 agent 应升级为围绕子图谱工作的次级 agent。它们不只是写 memo 分段，而是主动围绕一个 KG slice 做检索、抽取、归一、比较、暴露缺口，并输出 ClaimCard。

### Research Lead

Research Lead 仍然只做 meta-planning：

- 识别问题类型、ticker、行业 schema、universe 和研究深度。
- 读取 source inventory、KG inventory、playbook registry 和 gap summary。
- 选择次级 agent、source family、web scope、图谱切片和 barrier。
- 输出 evidence requirement plan 和 sub-agent task cards。
- 不直接写行业结论，不替 specialist 判断产品优劣。

### fundamental_subagent

消费 Segment、OperatingMetric、FinancialFact、CapitalStructure。

负责收入、利润、现金流、capex、库存、债务、流动性和管理层披露。

禁止用 channel proxy 或宏观序列证明公司财务事实。

### product_technology_subagent

消费 ProductFamily、ProductModel、ProductSpec、ProductKPI、RegulatoryEvent、TechnologySignal、ChannelOffer。

负责产品 taxonomy、规格参数、代际提升、竞品可比项、官方产品证据、公开订货/渠道表面信号。

输出：

- `ProductSpecPack`
- `ProductEvidenceClaimCards`

禁止把产品页、订货页、电商排名、评论或 benchmark 直接写成销量、市占率或利润率。

### industry_supply_chain_subagent

消费 CustomerRelationship、SupplierRelationship、CapacityAsset、RegionExposure、MacroDriver、TradeDriver。

负责产业链传导、周期、供应约束、客户/供应商关系和行业变量。

禁止把 hypothesis edge 写成 confirmed customer revenue 或 confirmed supplier exposure。

### capital_ownership_subagent

消费 CapitalStructure、DebtInstrument、CreditFacility、EquityOffering、OwnershipPosition、InsiderTransaction。

负责融资能力、债务墙、利率敏感度、回购/增发、13F/13D/G、insider 变化。

必须标注 13F lag，不得写成实时资金流。

### risk_counterevidence_subagent

消费所有已验证 ClaimCard、contradiction、gap register。

负责反证、source-boundary misuse、unsupported thesis 和商业数据缺口。

禁止新增事实或绕过上游 gate。

## 10. 具体落地顺序

不要一上来做全行业大图谱。按投研价值排序。

### P-1：统一 entity 和 source governance

在继续扩图谱前，先补：

- Entity / Identifier Master
- Raw Source Artifact Store
- Source Strength Policy
- Source Capability Router
- typed Gap Ledger
- Claim Evidence Ledger

目标是先保证公司、证券、产品、品牌、来源和缺口不会乱配。

### P0：公司业务线和产品-KPI 图谱

先做：

```text
Company -> Segment -> Product -> KPI
```

来源：

- 10-K business section
- segment footnote
- MD&A
- earnings release
- IR presentation
- product pages
- press releases

目标不是全覆盖，而是对每家公司明确：

- 哪些 KPI 公司披露。
- 哪些 KPI 没披露。
- 哪些 KPI 只能 proxy。
- 哪些 KPI 是 commercial_gap。

在 P0 上追加产品规格层：

```text
Product -> ProductModel -> ProductSpec
ProductModel -> ProductGenerationEdge
ProductModel -> CompetitiveComparableEdge
ProductModel -> ChannelOffer
```

### P1：资本结构和融资能力图谱

做：

```text
Company -> Debt -> Maturity -> Interest Expense -> Liquidity
Company -> Buyback / Dividend / Equity Issuance
```

来源：

- 10-K / 10-Q
- 8-K
- S-3 / S-1 / 424B
- cash flow financing section
- debt footnote

这能让研报从业务增长扩展到资金环境对估值和扩张的影响。

### P2：Ownership / Investor Graph

做：

```text
Investor -> Holding -> Company
Insider -> Transaction -> Company
Activist / 13D -> Company
```

来源：

- 13F
- 13D/G
- Form 3/4/5
- proxy

必须加：

- report_period
- filing_date
- lag_days
- holding_type
- not_realtime_flag

### P3：行业/宏观 driver layer

做：

```text
Sector -> Driver -> MacroSeries
Company -> Exposure -> Driver
```

示例：

- Banks -> yield curve / loan growth / credit losses
- Semis -> capex cycle / server demand / inventory
- Autos -> rates / consumer credit / production / incentives
- Homebuilders -> mortgage rate / permits / housing starts
- Energy -> oil price / gas price / rig count / inventory

来源：

- FRED
- BEA
- BLS
- EIA
- Census
- Fed SLOOS

### P4：行业垂直 source adapter

按行业补，不要横向乱补：

- Healthcare -> ClinicalTrials + openFDA
- Auto -> NHTSA + EPA + delivery disclosures
- Defense/Gov IT -> USAspending
- Tech/IP -> PatentsView + OpenAlex
- Trade-sensitive manufacturing -> Census trade / USITC
- Energy -> EIA
- Banking -> FDIC / call reports

### 行业、主营模式和公司规模微调

行业插件不只是 source list，还要定义对象、KPI、gates 和 gap policy。首批应覆盖：

- 半导体 / 硬件 / 电子
- 软件 / SaaS / 互联网平台
- 消费品 / 零售 / 电商
- 汽车 / 新能源车 / 工业设备
- 医药 / 生物科技 / 医疗器械
- 银行 / 保险 / 金融服务
- 能源 / 公用事业 / 材料
- 国防 / 政府 IT / 工程服务

主营模式也要影响图谱对象：

- 实物产品型公司：Product、SKU/Model、Production、Shipment、Inventory、Channel、Supplier、Capacity、ASP、Warranty/Recall。
- 订阅服务型公司：Subscriber、ARR/MRR、Retention、Pricing、Cohort、CustomerSegment、RPO/Billings。
- 平台/交易撮合型公司：GMV、TPV、TakeRate、Buyer/Seller、Liquidity、TransactionFrequency、MarketplaceCategory。
- 项目制/工程制公司：Contract、Backlog、Book-to-bill、Milestone、RevenueRecognition、CostOverrun、Customer。
- 资源/大宗商品公司：Asset、Reserve、Production、RealizedPrice、CostCurve、Hedge、Capex。

公司规模也要影响 gap policy：

- 大型成熟上市公司：公开源可较强，但 consensus、供应链交易、实时资金流仍是商业缺口。
- 中小上市公司：强化 business model validation、liquidity runway、customer concentration、going concern risk、insider transactions。
- 高成长亏损公司：强化 cash runway、gross margin trajectory、unit economics、dilution risk、convertible/equity financing。
- 私营 / Pre-IPO 公司：默认大量暴露 `private_company_disclosure_gap`。
- 非美公司：优先 primary disclosure parser，覆盖 CNINFO、HKEX、EDINET、DART、TW MOPS 和 company IR reports。

## 11. Agent Graph 接入方式

新增 KG 接入点不替换 G1-G11，而是作为下一阶段功能包接入：

```text
Research Lead
 -> KG Inventory Selector
 -> Plan Reflection Gate
 -> Evidence Operators
 -> Evidence Fusion Selector
 -> KG Object Builder
 -> Sub-agent Dispatch
      |-- Fundamental Subagent
      |-- Product / Technology Subagent
      |-- Industry / Supply Chain Subagent
      |-- Capital / Ownership Subagent
      |-- Risk / Counterevidence Subagent
 -> Claim Card Store
 -> Thesis Adjudicator
 -> Verifier
 -> Memo Writer
```

`KG Object Builder` 是新的同步 barrier。它只把 parser/gate 后的对象和边交给 sub-agent，不允许 sub-agent 直接把 raw webpage、raw search result 或 Milvus chunk 写进 ClaimCard。

Milvus 仍然只是 typed semantic recall supplement：

- 可以召回产品页、datasheet、manual、filing paragraph、IR section。
- 不能作为 ProductSpec、OperatingMetric 或 CapitalStructure 的 exact-value authority。
- 规格、价格、库存、交期等结构化字段必须由 parser 从 snapshot 或结构化源中抽取，并通过 unit/period/region/source gate。

## 12. 后续工程拆分

K1-K8 是图谱和 sub-agent 工程拆分；D1-D11 是数据治理底座工程拆分。两者应并行规划，但 runtime promotion 必须先满足对应 D 层 gate。

### K1 KG Matrix Registry

- 定义 Operating KG、Capital & Ownership Graph、Claim Evidence Layer 的 node/edge schema。
- 把 source family 和 KG object type 映射起来。
- 通过条件：Research Lead 能看到 KG inventory，不看到 raw rows。

### K2 Product Spec Ontology

- 增加 ProductFamily、ProductModel、ProductSpec、GenerationEdge、ComparableEdge、ChannelOffer、FieldInquiryNote。
- 按行业 playbook 配产品规格维度。
- 通过条件：产品规格必须带单位、配置、地区、时间和来源。

### K3 Public Buyer Observer Source Policy

- 增加公开采购视角 source class、allowed/forbidden actions、claim scope。
- 接入公开订货、电商、分销商、公开报价和 pricing/docs surface。
- 通过条件：任何 ChannelOffer 都不能支持 sales/share/ASP/company inventory。

### K4 Product / Technology Subagent Upgrade

- 把 product specialist 升级为 sub-agent，输出 ProductSpecPack 和 ClaimCard。
- 增加代际比较、竞品比较和 product-to-financial bridge slots。
- 通过条件：sub-agent 不能把弱 proxy 提权；不能没有可比维度就做竞品判断。

### K5 Capital & Ownership Graph

- 接入 SEC debt footnote、offering、credit agreement、13F、13D/G、Form 3/4/5、proxy。
- 建 CapitalStructure、DebtInstrument、OwnershipPosition、InsiderTransaction。
- 通过条件：13F 必须带 report period、filing date、lag policy；债务数据必须带 maturity/coupon/rate type/source。

### K6 Macro Exposure And Vertical Adapters

- 建 CompanyExposureToDriver，阻断 macro -> company conclusion 直连。
- 把 ClinicalTrials/openFDA/NHTSA/USAspending/PatentsView/OpenAlex/FDIC/Census/USITC/EIA 映射成对象和事件。
- 通过条件：宏观、监管、专利、招聘、GitHub、clinical status 都不能直接证明公司销售成功。

### K7 Verifier And Reflection Gates

- Verifier 增加 product page != sales、channel offer != sell-through、13F != realtime flow、macro != company fact、patent != commercial success、FieldInquiryNote != authority fact。
- Reflection second pass 只能修 parser/schema/source reachability，不允许用弱 proxy 兜底。
- 通过条件：每个 rejected promotion 都进入 phase-verified rejected 或 bounded gap。

### K8 End-to-end KG Subagent Gate

- 设计 10-20 个跨行业 case，覆盖产品规格、代际比较、竞品比较、资本结构、持仓、宏观 exposure、公开采购视角。
- 通过条件：核心 thesis 只由合规 ClaimCard 支撑；低强度信号只写成 context/gap；不能出现 source-boundary violation。

### D1-D11 Data Governance Runtime

最近一轮最高优先级不是继续堆公开源，而是把系统从 data warehouse 升级成 evidence-governed research runtime：

1. `D1 Claim Evidence Ledger`
2. `D2 Typed Gap Ledger`
3. `D3 Entity / Security Master`
4. `D4 Raw Source / Provenance Store`
5. `D5 As-of / Vintage Layer`
6. `D6 Reconciliation Ledger`
7. `D7 Metric / Product Ontology`
8. `D8 Source Capability Router`
9. `D9 Gate Registry / Gate History / Eval Matrix`
10. `D10 Derived Metric Layer`
11. `D11 Analyst View / Research Memory`

## 13. 必须避免的错误

- 把所有公开网页都塞进 Milvus。
- 把产品页当成销售证据。
- 把公开价格写成公司 ASP。
- 把电商可售状态写成渠道库存或 sell-through。
- 把宏观数据强行映射到公司结论。
- 把 13F 当实时资金流。
- 把专利、招聘、GitHub、developer docs 写成商业成功。
- 把 user-provided FieldInquiryNote 写成独立权威事实。
- 为了覆盖更多公司而放宽 parser、source gate 或 claim scope。

正确路径是：

```text
网页/新闻/搜索结果 -> lead
lead -> official/company/regulatory verification
verification passed -> evidence
evidence -> claim
```

## 14. 成功标准

1. Agent 能稳定区分产品事实、产品规格、渠道信号、财务 KPI、行业 context、资本结构和商业数据缺口。
2. Product / Technology sub-agent 能输出产品代际和竞品可比表，但只在规格维度和来源足够时生成。
3. Fundamental sub-agent 能引用产品事实解释财务变化，但不会把弱 proxy 写成 revenue driver。
4. Capital / Ownership sub-agent 能提供融资、债务、持仓和 insider context，并正确标注 lag。
5. Industry / Supply Chain sub-agent 能通过 exposure edge 使用宏观和行业变量，而不是直接跳到公司结论。
6. Research Lead 基于 KG inventory 和 playbook 分配任务，而不是靠泛泛行业常识。
7. Memo Writer 只消费 verified ClaimCard 和 bounded gap register。
