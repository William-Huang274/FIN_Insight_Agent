# R54 Secondary Market / Capital Feedback 技术计划

日期：2026-06-28

状态：living technical registry draft。本文是 R54 的 active source of truth，后续二级市场、资金面、信用融资、资本动作、估值 price-in、宏观跨资产和衍生品数据源增删、parser 状态、图谱边和 eval gate 变化都应回写本文或其拆分出的子台账。

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`
- `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`
- `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/architecture/agent_graph_vnext/28_r53_research_to_quant_lab_technical_plan.zh-CN.md`

## 1. 定位

R54 不是替代基本面、产品和行业研究的“行情模块”。它的定位是：

```text
把二级市场资金面、预期面、信用融资、资本动作、宏观/跨资产和衍生品风险定价，变成可审计、可边界化、可被 Research Lead / Workpaper / R53 使用的 Capital Feedback Layer。
```

它回答的问题是：

- 市场是否已经把好消息或坏消息 price in；
- 谁在买、谁在卖、是否机构拥挤或被动资金推动；
- 信用市场是否比股票市场更悲观；
- 公司是否会利用高股价融资、回购、并购或稀释；
- short interest、options、volatility 和 liquidity 是否会改变短中期价格路径；
- 利率、美元、商品、行业 ETF、同行和上下游资产是否改变行业 beta 或估值环境；
- 这些市场信号能否转成 R53 的 `SignalObservation` / `FeatureSpec`，并被回测或事件研究验证。

R54 不做：

- 用资金面信号冒充公司基本面改善；
- 用 options / futures / short interest 直接生成买卖建议；
- 用实时或商业授权数据伪装为公开免费源；
- 把滞后 13F、N-PORT、COT 当成实时资金流；
- 在没有 point-in-time / vintage / as-of time 的情况下进入 R53 回测。

## 2. Living Registry 维护原则

R54 必须是长期维护文档，因为其数据源和图谱关系会持续变化：

- 公开网页、交易所页面和 API 可能改版；
- 免费源和商业源边界可能变化；
- parser 可用性、频率、延迟和字段稳定性需要通过测试持续确认；
- 新增行业、市场或资产类别后，source role 和 graph edge 也会扩展；
- full-chain eval 发现某个 pack 无效、过噪或误提权时，必须回写 source status 和 authority rule。

### 2.1 Source lifecycle

每个数据源进入 R54 必须有状态：

| 状态 | 含义 | 是否可进入 runtime pack |
| --- | --- | --- |
| `planned` | 已纳入规划但未验证 locator / fetcher / parser | 否 |
| `candidate_verified` | 官方文档或人工验证可访问，但未接 parser | 否 |
| `parser_ready` | fetcher / parser / schema 已有 deterministic test | 仅可 smoke |
| `runtime_ready` | 已有 point-in-time row、lineage、authority gate、eval case | 是 |
| `parser_debt` | 公开源可得，但当前 parser / route 未吃到 | 否，必须修 |
| `public_boundary` | 公开免费源无法提供所需字段或频率 | 可作为 gap |
| `commercial_gap` | 需要商业授权或实时市场数据 | 不得伪装为公开源 |
| `deprecated` | 源失效、质量差、授权不清或被替代 | 否 |

### 2.2 Source registry 最小字段

R54 后续应维护独立 `SecondaryMarketSourceRegistry`，字段至少包括：

| 字段 | 说明 |
| --- | --- |
| `source_id` | 稳定源 ID |
| `pack_role` | 属于哪个 R54 pack |
| `asset_scope` | equity / fund / bond / option / future / FX / commodity / index |
| `market_scope` | US / CN / HK / JP / EU / global |
| `issuer_bound` | 是否能绑定 issuer / ticker / security |
| `instrument_bound` | 是否能绑定具体 security / option contract / futures contract |
| `frequency` | intraday / daily / weekly / monthly / quarterly / filing-event |
| `lag_policy` | T+0 / delayed / filing lag / reporting lag / unknown |
| `fields` | 可解析字段 |
| `locator` / `fetcher` / `parser` | route 实现状态 |
| `authority_class` | market_expectation / capital_feedback / exact_filing_fact / proxy / gap |
| `forbidden_claims` | 禁止推断范围 |
| `status` | source lifecycle 状态 |
| `last_verified_at` | 最近验证时间 |
| `eval_case_refs` | 覆盖该源的 deterministic / full-chain eval |

## 3. 和现有系统的关系

```text
FundamentalStatementPack
 -> 公司值不值钱、盈利/现金流/资产负债质量如何

ProductIntelligenceGraph / ProductEvidencePack
 -> 产品、客户部署、供应链、竞争关系是否支撑业务变化

R54 SecondaryMarketCapitalFeedback
 -> 市场是否愿意给这个价格、资金是否拥挤、信用和资本动作是否反过来影响公司

R53 Research-to-Quant
 -> 把上述判断变成可检验 SignalObservation / FeatureSpec / FactorCard
```

R54 是 `DimensionEvidencePortfolio` 的独立维度，不应该塞进 market specialist 的散装 rows。Research Lead 应把它和基本面、产品、行业、风险并列使用：

```text
fundamental thesis
 + product / industry evidence
 + secondary-market / capital-feedback evidence
 + counter-thesis / gap
 -> JudgmentState
 -> Workpaper / Memo / FactorHypothesis
```

## 4. Pack Taxonomy

### 4.1 `SecondaryMarketCapitalFlowPack`

数据：

- price、return、relative return、drawdown；
- volume、dollar volume、turnover；
- realized volatility；
- market reaction around events；
- benchmark / sector / peer relative performance。

判断：

- 股价是否已经提前反应；
- 走势是公司 alpha、行业 beta，还是宏观 risk-on / risk-off；
- 好消息是否可能已 price in。

当前基础：

- 已有 `MarketLiquidity` / market liquidity rows，覆盖 603/603；
- 仍缺稳定 `free_float`、turnover、bid-ask、event-window reaction schema。

### 4.2 `OwnershipAndHolderPack`

数据：

- 13F institutional holdings；
- N-PORT fund holdings；
- ETF holdings / weights；
- 13D/G beneficial ownership；
- insider Form 3/4/5。

判断：

- 谁在买、谁在卖；
- 是否机构拥挤；
- 是否被动资金推动；
- 是否出现 activist、大股东或 insider 变化。

边界：

- 13F / N-PORT 是滞后披露，只能做 lagged ownership context；
- insider filing 可以作为 filing-event exact fact，但不能直接推断管理层绝对态度；
- ETF / fund flow 如果没有完整申赎和持仓时点，只能做 positioning context。

当前基础：

- 已有 13F lagged ownership context、13D/G、Form 3/4/5 metadata；
- 需要补全 holdings amount / shares / percentage / report_period / filing_lag / issuer mapping。

### 4.3 `CreditFundingPack`

数据：

- debt instruments、coupon、maturity、principal；
- credit facility、loan rate、covenant；
- bond yield / spread；
- credit rating / outlook；
- CDS 或 proxy；
- convertible bond terms。

判断：

- 公司融资成本是否上升；
- 债务市场是否比股票更悲观；
- 是否有 maturity wall / refinancing pressure；
- 股价高低是否影响再融资窗口。

边界：

- 公司披露 debt / credit facility 是强 filing fact；
- 债券市场价格、CDS、rating 可能需要商业源或授权，公开源下要写清延迟和覆盖。

当前基础：

- 已有 debt instrument / credit facility / working capital rows；
- 缺公司债市场价格、spread、rating history、CDS、convertible market price。

### 4.4 `CorporateActionPack`

数据：

- buyback authorization / actual repurchase；
- S-1 / S-3 / 424B / ATM offering；
- convertible / debt offering；
- M&A；
- equity compensation / dilution；
- insider buy / sell；
- proxy vote / compensation context。

判断：

- 公司是否趁高股价融资；
- 是否存在稀释压力；
- 是否有回购托底；
- 管理层和董事会资本配置动作如何改变股东回报。

边界：

- offering filing event 不等于最终融资完成；
- buyback authorization 不等于实际执行；
- insider selling 必须结合 10b5-1、vesting、tax withholding 和历史行为。

当前基础：

- 已有 offering / insider / proxy / 13D-G filing-event metadata；
- 需要补 offering terms、actual repurchase amount、insider shares/price/code、proxy compensation/vote parser。

### 4.5 `LiquidityAndPositioningPack`

数据：

- ADV、dollar volume、turnover；
- bid-ask spread；
- free float；
- short interest；
- borrow cost / securities lending proxy；
- block trades / lockup expiration；
- options OI / put-call / skew。

判断：

- 股票是否容易交易；
- 是否拥挤；
- 是否有 short squeeze / gamma squeeze / liquidity squeeze 风险；
- 大涨大跌是否有资金结构解释。

边界：

- short interest 滞后，不能当实时空头仓位；
- borrow cost / real-time securities lending 多数商业化；
- options 只能说明风险定价和仓位 proxy，不能证明基本面。

当前基础：

- 已有 price/volatility/drawdown；
- 缺 FINRA short interest、borrow cost、bid-ask、free float、options positioning。

### 4.6 `ValuationPriceInPack`

数据：

- PE、PB、PS、EV/EBITDA、FCF yield；
- market cap、enterprise value；
- shares outstanding / diluted shares；
- historical valuation percentile；
- peer valuation；
- implied growth / PEG / DCF sensitivity；
- event-window valuation reaction。

判断：

- 好消息是否已经反映；
- 估值扩张来自基本面还是流动性；
- 如果业绩下修，风险来自 earnings cut 还是 multiple compression。

边界：

- valuation 必须说明分母口径、期间、TTM / NTM / FY；
- consensus-based NTM 多数属于商业数据，公开源下只能用已披露或自算口径。

当前基础：

- 财务事实和价格快照已有；
- 缺稳定 shares / EV / market cap / historical percentile / peer valuation panel。

### 4.7 `ExpectationNarrativePack`

数据：

- guidance；
- earnings surprise；
- analyst revision / consensus revision；
- management commentary；
- product release；
- customer deployment / order signal；
- news / policy / conference / search trend。

判断：

- 市场现在相信什么；
- 叙事有没有变化；
- 预期是在上修还是下修；
- 股价反应是事实兑现还是新故事出现。

边界：

- sell-side consensus / revisions 通常商业化；
- 新闻和搜索热度必须标注 source authority，不能直接提权为基本面事实；
- 社媒/论坛只能低权重，用于 clue 或 sentiment context。

当前基础：

- 已有管理层披露、产品图谱、部署/proxy、政策/监管 rows；
- 缺 consensus/revision/surprise 和统一 narrative-change detector。

### 4.8 `EventCatalystPack`

数据：

- earnings date；
- investor day；
- product launch；
- FDA / clinical milestone；
- shareholder meeting；
- dividend / ex-date；
- index rebalance；
- lockup expiration；
- convertible maturity / call / put event；
- policy meeting / regulatory decision。

判断：

- 近期有没有催化剂；
- 市场是否在提前交易事件；
- 事件后是否有 sell-the-news 风险。

边界：

- 事件日历必须区分 confirmed date、estimated date、filing-derived date；
- 不能把事件存在本身写成方向性结论。

### 4.9 `PolicyRegulatoryPack`

数据：

- industry policy；
- enforcement / penalty；
- antitrust；
- reimbursement / healthcare policy；
- export control；
- subsidies；
- monetary / real estate / refinancing rules；
- A 股减持、再融资、交易制度变化。

判断：

- 政策是否强化或压制公司逻辑；
- 是否改变行业估值；
- 是否改变资金偏好。

边界：

- 政策文本是事实，影响路径是 thesis driver，需要明确推理链和反方。

### 4.10 `CrossAssetReadThroughPack`

数据：

- peer / competitor price reaction；
- supplier / customer stocks；
- sector ETF / factor ETF；
- bonds / credit；
- FX；
- commodities；
- rates；
- indexes。

判断：

- 是公司自身 alpha 还是板块 beta；
- 上下游是否提前反应；
- 宏观或商品价格是否改变利润率和估值。

边界：

- correlation 不等于 causation；
- read-through edge 必须有 source、reason、time window、confidence。

### 4.11 `DerivativesMarketSignalPack`

数据：

- index futures、rate futures、commodity futures；
- VIX futures / term structure；
- CFTC COT；
- single-stock / ETF options OI、volume、put-call、IV、skew、implied move；
- index options volatility regime。

判断：

- 市场如何定价未来不确定性；
- 事件前是否定价了大幅波动；
- 宏观/商品/利率预期是否改变行业 beta；
- 是否存在拥挤或 squeeze risk。

边界：

- 免费源通常只能做延迟、日频或周频；
- 实时 OPRA、dealer gamma、borrow、深度盘口多数是商业数据；
- options / futures 只进入 `market_expectation_proxy` 或 `derivatives_positioning_signal`。

## 5. Object Model

R54 统一输出 `CapitalFeedbackSignal`，再汇总成各 pack。

### 5.1 `CapitalFeedbackSignal`

| 字段 | 说明 |
| --- | --- |
| `signal_id` | 稳定 ID |
| `issuer_id` / `ticker` | 公司或证券映射 |
| `instrument_id` | equity / bond / option / future / ETF / index / FX / commodity |
| `pack_role` | ownership / credit / liquidity / valuation / derivative / policy 等 |
| `signal_type` | e.g. `short_interest_change`、`buyback_authorization`、`valuation_percentile` |
| `value` / `unit` | 可选数值 |
| `period` / `asof_date` / `available_at` | PIT 时间字段 |
| `source_id` / `source_refs` | 来源与 citation |
| `frequency` / `lag_policy` | 数据频率与延迟 |
| `authority_class` | `exact_filing_fact` / `market_expectation_proxy` / `capital_feedback_signal` / `context_only` / `gap` |
| `claim_boundary` | 可以支持什么、不支持什么 |
| `quality_flags` | stale、estimated、delayed、thinly_traded、partial_coverage 等 |

### 5.2 Pack container

每个 company / ticker 应能生成：

```text
SecondaryMarketCapitalFeedbackPack
  -> SecondaryMarketCapitalFlowPack
  -> OwnershipAndHolderPack
  -> CreditFundingPack
  -> CorporateActionPack
  -> LiquidityAndPositioningPack
  -> ValuationPriceInPack
  -> ExpectationNarrativePack
  -> EventCatalystPack
  -> PolicyRegulatoryPack
  -> CrossAssetReadThroughPack
  -> DerivativesMarketSignalPack
  -> DataAvailabilityGap
```

Pack 不要求每个子包都满，但必须显示缺口类型：

- `not_applicable`；
- `not_yet_materialized`；
- `parser_debt`；
- `public_boundary`；
- `commercial_gap`；
- `source_unverified`。

## 6. Authority Boundary

R54 的 evidence promotion 不按“强/弱”一刀切，而按可支持的 claim scope 分类。

| Authority | 可以支持 | 禁止 |
| --- | --- | --- |
| `exact_filing_fact` | 公司已披露回购、融资、债务、insider filing、13D/G filing event | 直接推断市场实时买卖或长期投资建议 |
| `lagged_positioning_context` | 13F / N-PORT / COT 等滞后持仓背景 | 当成当前资金流 |
| `market_expectation_proxy` | options / futures / IV / skew / implied move / curve 反映市场风险定价 | 当成基本面事实 |
| `capital_feedback_signal` | 股价、融资窗口、信用、回购、稀释对公司资本结构的反馈 | 证明产品销量或收入增长 |
| `valuation_price_in_signal` | 估值分位、peer premium、implied growth、event reaction | 证明业绩会达成 |
| `cross_asset_read_through` | 行业 beta、上下游、商品/利率/FX 对公司影响路径 | 单独证明公司 alpha |
| `context_only` | 低频、延迟、覆盖不足或无法 issuer-bound 的背景 | 核心 thesis 提权 |

## 7. Graph Edges

R54 应新增或强化的图谱边：

```text
institution_or_fund -> held_by -> issuer_or_security
insider -> transacted -> security
issuer -> affected_by -> buyback / offering / M&A / dilution
issuer -> financed_by -> debt / convertible / credit_facility
issuer -> refinancing_risk_from -> maturity_wall / rate_level / credit_spread
ticker -> short_interest_signal -> market_positioning
ticker -> options_positioning_signal -> event_risk_pricing
ticker -> valued_by -> valuation_multiple
rate_future -> discount_rate_expectation -> growth_equities / banks / real_estate
commodity_future -> input_cost_or_demand_proxy -> industry_or_company
vix_curve -> volatility_regime -> equity_market_liquidity
cross_asset_peer -> read_through_to -> ticker_or_industry
policy_event -> valuation_or_funding_regime_shift -> industry_or_company
```

每条边必须带：

- `edge_type`；
- `direction`；
- `source_refs`；
- `asof_time`；
- `authority_class`；
- `confidence`；
- `forbidden_claims`；
- `supersedes` / `valid_until`。

## 8. Agent 消费方式

### 8.1 Research Lead

Research Lead 必须读取 R54 pack 来回答：

- 研究问题是否只看了业务面而忽视 price-in；
- 当前股价和估值是否已经反映 thesis；
- 是否存在资金拥挤、short squeeze、流动性风险；
- 公司是否可能因为股价或信用环境而改变融资、回购、并购、资本结构；
- 哪些 R54 缺口是可公开补源，哪些是商业数据 gap。

### 8.2 Market / Capital Specialist

Specialist 不再散装抓行权价、成交量、13F 或新闻，而应输出结构化：

```text
CapitalFeedbackSignal[]
PackSummary
GapLedger
ClaimBoundary
```

### 8.3 Memo / Workpaper

Memo Writer 只能消费 JudgmentState / MemoLogicPlan 中已经整理过的 R54 判断。正文应写：

- 市场价格和资金面如何影响判断；
- 哪些结论是 filing fact；
- 哪些只是 positioning / expectation proxy；
- 哪些需要商业数据或后续监控。

不能写：

- “call OI 高，所以股票一定上涨”；
- “13F 持仓增加，所以当前机构正在买”；
- “short interest 高，所以基本面差”。

### 8.4 R53 Research-to-Quant

R54 是 R53 的主要 feature/event/regime 来源之一：

- liquidity / turnover / volatility 进入 universe 和 cost gate；
- ownership / short / options / valuation 进入 feature candidate；
- corporate action / event catalyst 进入 event study；
- rate / commodity / VIX / FX 进入 regime 或 cross-asset factor；
- all inputs 必须有 `available_at` 和 lag policy。

## 9. v0.1 / v0.2 实施顺序

### R54.0 Framework And Registry

目标：冻结 R54 pack、signal、source registry、authority 和 graph edge contract。

通过条件：

- 29 文档和 source registry schema 可表达 11 个 pack；
- 每个 pack 有 forbidden claims；
- R53/R58/R60 消费边界明确。

### R54.1 Current Asset Inventory

目标：审计当前已有 market liquidity、capital、ownership、debt、offering、insider、working-capital rows 能覆盖哪些 R54 pack。

通过条件：

- 603 公司生成 `SecondaryMarketCapitalFeedbackCoverageProfile`；
- 每个 company / pack 标注 `ready / partial / gap / not_applicable`；
- 不把已有散装 rows 自动视为 runtime-ready。

### R54.2 Valuation And Price-In Core

目标：先补 shares、market cap、EV、multiples、peer / historical percentile 和 event reaction。

通过条件：

- 估值口径有 TTM / fiscal / asof；
- peer group 可追溯；
- missing / stale / commercial consensus gap 显式暴露。

### R54.3 SEC Capital Action Parser

目标：补 Form 3/4/5、13D/G、S-3/424B/offering、buyback、proxy parser。

通过条件：

- filing event、terms、amount、share/price、period、citation 可绑定；
- authorization 与 actual action 分开；
- 10b5-1 / tax withholding / vesting 等 insider 边界能记录。

### R54.4 Ownership / Short / Positioning

目标：补 13F / N-PORT / ETF / FINRA short interest / free float / borrow candidate。

通过条件：

- 滞后字段和 report period 进入 schema；
- short interest 不被当实时空头仓位；
- borrow cost 如不可公开获取则进入 commercial gap。

### R54.5 Derivatives And Futures Proxy

目标：接 OCC / CFTC / CME / exchange delayed futures/options proxy。

通过条件：

- contract / expiry / strike / underlying / asof 可绑定；
- COT 周频 lag 明确；
- options / futures 只进入 expectation / positioning / regime。

### R54.6 Cross-Asset / Macro / Policy Mapping

目标：把利率、美元、商品、VIX、sector ETF、peer / supply-chain read-through 映射到行业和公司。

通过条件：

- 每条 mapping edge 有经济逻辑、方向、来源和反方；
- correlation-only 边不能直接提权；
- 能被 Research Lead 用于 thesis / counter-thesis。

### R54.7 Runtime Integration And Eval

目标：接入 DimensionEvidencePortfolio、LeadReviewCheckpoint、MemoLogicPlan、R53 SignalObservation 和 R60 eval。

通过条件：

- 至少 10 个覆盖 AI/Semis、Banks、Energy/Utilities、SaaS、Healthcare 的 deterministic cases；
- 2 个 full-chain case 能看到 R54 pack 进入判断但不越权；
- eval 能抓出 options/13F/short/valuation 的 forbidden claim。

## 10. 数据源初始台账

这里记录第一版候选源。`status` 是规划状态，不代表已经接入。

| Pack | Source family | 候选源 / 当前资产 | 目标字段 | status |
| --- | --- | --- | --- | --- |
| CapitalFlow | internal market liquidity rows | 已有 MarketLiquidity rows | price、return、volume、volatility、drawdown | `partial_runtime_ready` |
| CapitalFlow | exchange / quote history | 交易所/公开延迟价格源，需逐源验证 | OHLCV、turnover、benchmark return | `planned` |
| Ownership | SEC 13F | 已有 lagged ownership context，需 holdings mart 深化 | holder、issuer、shares、value、period、filing_lag | `partial_runtime_ready` |
| Ownership | SEC 13D/G | 已有 metadata，需 schedule/detail parser | owner、issuer、percentage、event | `partial_runtime_ready` |
| Ownership | SEC Form 3/4/5 | 已有 metadata，需 XML/detail parser | insider、shares、price、transaction code、10b5-1 flag | `parser_debt` |
| Ownership | N-PORT / ETF holdings | 公开源需验证 | fund holdings、ETF weight、period | `planned` |
| Credit | SEC debt footnote / credit facility | 已有 debt / credit rows | coupon、maturity、principal、rate、facility size | `partial_runtime_ready` |
| Credit | bond price / spread / rating | 公开可得性需验证，多数可能商业化 | yield、spread、rating、CDS proxy | `planned` |
| CorporateAction | SEC offerings | 已有 filing-event metadata，需 terms parser | offering type、amount、security、date、dilution | `parser_debt` |
| CorporateAction | buyback | 公司披露/10-Q/10-K/proxy | authorization、actual repurchase、avg price | `planned` |
| Liquidity | FINRA short interest | 候选公开源 | short interest、days-to-cover、report date | `planned` |
| Liquidity | borrow cost / securities lending | 多数商业化 | borrow fee、availability | `commercial_gap_candidate` |
| Valuation | financial + market cap derived | 当前财务 + price rows 可派生部分 | PE/PB/PS/EV/EBITDA/FCF yield | `planned` |
| Expectation | company guidance / surprise | filings / press release / transcripts，consensus 多为商业 | guidance、surprise、revision | `partial_planned` |
| Event | filing / earnings / regulatory calendar | SEC / company IR / clinical/FDA rows | event type、date、confidence | `planned` |
| Policy | official regulatory / policy | 现有 public source rows + 行业 policy routes | policy event、industry impact | `partial_planned` |
| CrossAsset | product / supply-chain graph + ETF/commodity/rates | 已有 ProductGraph，缺 price mapping | read-through edge、beta context | `planned` |
| Derivatives | OCC options data | 候选公开源 | volume、OI、put/call、expiry、strike | `planned` |
| Derivatives | CFTC COT | 候选公开源 | futures positioning by trader class | `planned` |
| Derivatives | CME delayed futures | 候选公开源 | futures price、settlement、volume、OI、curve | `planned` |

## 11. Eval Gates

R54 必须有专门 eval，不能只靠 memo 观感：

| Gate | 检查 |
| --- | --- |
| `source_registry_gate` | 每个 runtime row 能追到 source registry、fetcher、parser、authority mapper |
| `pit_gate` | market / ownership / derivative row 有 asof / available_at / lag policy |
| `forbidden_claim_gate` | 13F、short、options、futures、valuation 不越权成基本面事实 |
| `coverage_profile_gate` | 603 公司 pack coverage 明确 ready / partial / gap |
| `graph_edge_gate` | R54 graph edge 有 source、direction、confidence、validity |
| `research_lead_consumption_gate` | Lead 能区分 price-in / positioning / capital-feedback / gap |
| `r53_feature_gate` | R53 只能消费 PIT-valid R54 signals |
| `memo_surface_gate` | 输出能自然解释市场资金面，而不是堆字段或满篇 caveat |

## 12. S8 Runtime Closeout（2026-06-29）

R54 第一版 runtime 已在 R53-R60 S8 中落地，closeout 为 `S8_L4_scope_pass`。

### 12.1 已落地对象

- `SecondaryMarketSourceRegistry`：`15` 条 source registry rows，覆盖 market snapshot、lagged ownership、13D/G、Form 3/4/5、offering/proxy metadata、debt footnote、FSD working capital、valuation planned source、derivatives planned source、credit-market planned source、short/borrow planned source、non-US holder/corporate-action planned routes。
- `CapitalFeedbackPack`：`603` 个 issuer pack，范围锁定为当前 runtime market snapshot universe。
- `CapitalFeedbackSignal`：`13,107` 条 bounded signal。
- `CapitalFeedbackGapItem`：`2,443` 条 typed gap。
- `CapitalFeedbackGraphEdge`：`4,221` 条 issuer -> capital-feedback-role graph edge。
- `CapitalFeedbackQualityGate`：`10` 条 S8 L4 scope gate。
- S1 主账本事件：S8 通过 `WorkpaperEvent` 写入 `secondary_market_capital_feedback_pack_ready`。

### 12.2 已接入的 pack role

| Pack role | 当前状态 | 说明 |
| --- | --- | --- |
| `secondary_market_capital_flow` | `runtime_ready` | 603/603 有 delayed price / return / volatility / drawdown context。 |
| `liquidity_and_positioning` | `partial_runtime_ready` | 603/603 有 price/volatility/working-capital liquidity context，但 short interest / borrow cost / free float / ETF flow 仍是 gap。 |
| `ownership_and_holder` | `partial_runtime_ready` | 13F lagged ownership context、13D/G metadata 已进入 pack；16 个 issuer 仍需 holder route / non-US adapter typed gap。 |
| `credit_funding` | `partial_runtime_ready` | debt instrument、credit facility、working-capital liquidity rows 已进入 pack；market credit spread / CDS / rating history 对 603 issuer 仍是 typed gap。 |
| `corporate_action` | `partial_runtime_ready` | SEC offering、Form 3/4/5、proxy、13D/G metadata 作为 filing-event context 进入 pack；15 个 issuer 需要 local/non-US corporate-action adapter。 |
| `valuation_price_in` | `typed_gap_ready` | 当前市场快照缺稳定 market cap / EV / PE / EV-sales / EV-EBITDA denominator，603 issuer 均以 valuation typed gap 记录。 |
| `derivatives_market_signal` | `typed_gap_ready` | 不伪造 options / futures / COT 信号；603 issuer 均以 public/parser/commercial boundary typed gap 记录。 |

### 12.3 关键边界

- 13F / holder rows 是 `lagged_positioning_context`，禁止写成实时资金流或当前买盘。
- SEC 13D/G、Form 3/4/5、offering、proxy rows 在 S8 中主要是 metadata / filing-event context，除非后续 source-specific parser 抽到 amount / shares / terms，否则不能写成交易金额、持股比例、回购金额或融资完成。
- Yahoo chart rows 是 delayed market context，只能支持价格反应、波动、回撤、流动性方向讨论，不能支持基本面、产品需求、资金流或投资建议。
- Debt / credit facility / working-capital rows 保留 filing / financial-statement exact authority，但不能推出市场利差、CDS、rating 或再融资渠道通畅。
- S8 对 SEC event `all_tickers` 做 runtime universe 过滤：只给 market snapshot universe 内 `603` 个 issuer 建 pack；`6,655` 个 universe 外 SEC event ticker 被记录为 scope-filtered 诊断计数，避免污染 issuer coverage。

### 12.4 后续 R54 backlog

- `R54.2`：补稳定 issuer-bound valuation panel，包括 shares、market cap、EV、TTM denominator、peer group 和 historical percentile。
- `R54.3`：补 SEC source-specific capital-action parser，把 offering amount / security terms、Form 4 shares / price / transaction code、buyback authorization / actual repurchase 从 metadata 推进到 exact/event rows。
- `R54.4`：补 delayed short interest、free float、ETF/factor flow、N-PORT / ETF holdings；borrow cost 和 securities lending 若无授权继续保留 commercial gap。
- `R54.5`：补 CFTC / CME / OCC / exchange delayed derivatives/futures proxy，所有 rows 必须有 contract / underlying / asof / lag policy，且只能进入 expectation / positioning / regime。
- `R54.6`：补 cross-asset / macro / policy mapping edge，把 rates、commodity、FX、VIX、sector ETF、peer/supply-chain read-through 接入 graph，并防止 correlation-only 提权。
- `R54.7`：接入 Research Lead / DimensionEvidencePortfolio / R53 FeatureSpec / R60 eval 的消费门控，验证 R54 pack 能进入判断但不越权。

## 13. 当前开放问题

1. R54 v0.1 是否优先做 Valuation + SEC capital action + 13F/short，还是同步启动 derivatives。
2. market data 是否先用当前已物化 rows 派生，还是先建设统一 price/security master。
3. 非美市场持仓、short、ETF、corporate action 是否放到 v0.2。
4. borrow cost、real-time options、CDS、complete bond pricing 是否直接标为 commercial gap，还是先找可公开 proxy。
5. R54 pack 是先作为 `DimensionEvidencePortfolio` 新维度接入，还是先由 Market/Capital Specialist 内部试运行。
6. ValuationPriceInPack 是否需要先定义 peer group registry，否则 historical/peer valuation 会不稳定。
7. 与 R53 联动时，第一版是否只允许 feature availability audit，不允许真实 factor validation。

## 14. 草案结论

R54 的核心不是“多接行情源”，而是把二级市场、资金面和资本反馈从散装市场数据变成可审计的研究维度。

第一阶段应先保护五个地基：

1. `SecondaryMarketSourceRegistry`：长期维护源、parser、授权、延迟和状态。
2. `CapitalFeedbackSignal`：统一 signal schema，明确 PIT、authority 和 forbidden claims。
3. `SecondaryMarketCapitalFeedbackPack`：把 11 个 pack 接入 Research Lead，而不是散装 rows。
4. `CapitalMacroGraph` / `MarketFeedbackGraph`：让市场、信用、资本动作、宏观和公司之间形成可解释边。
5. R60 eval gate：持续检查 price-in、positioning、derivatives 和 13F 等信号不越权。

做完 R54 后，FinSight 的研究框架才会从“公司业务和产品是否好”扩展为：

```text
业务是否好
 + 产品和行业是否支撑
 + 市场是否已经定价
 + 资金是否拥挤
 + 信用和资本动作是否反向影响公司
 + 宏观/跨资产/衍生品是否改变风险收益
```
