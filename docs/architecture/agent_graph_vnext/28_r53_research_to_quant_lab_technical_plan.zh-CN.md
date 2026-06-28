# R53 Research-to-Quant Lab 技术草案

日期：2026-06-28

状态：whole-picture 技术草案。本文先冻结 Research-to-Quant Lab 在公开数据前提下的全景能力、对象模型和边界，不拆 v0.1 / v0.2 迭代节奏，不进入实现。

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`
- `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md`

参考实现 / 工具：

- [Microsoft Qlib](https://github.com/microsoft/qlib)：AI-oriented quant research pipeline，可参考数据处理、模型训练、回测、风险建模、组合优化的链路组织。
- [QuantConnect LEAN](https://www.quantconnect.com/docs/v2/lean-engine)：event-driven / multi-asset backtest 与 paper/live trading engine，可作为后续生产级 backtest adapter 参考。
- [vectorbt](https://vectorbt.dev/)：vectorized backtesting，适合高速参数扫描和大批量策略原型验证。
- [Alphalens](https://quantopian.github.io/alphalens/)：factor analysis / tear sheet，可参考 IC、分组收益、decay、turnover 等因子评价。
- [scikit-learn](https://scikit-learn.org/stable/user_guide.html)、[statsmodels](https://www.statsmodels.org/stable/tsa.html)、[PyPortfolioOpt](https://pyportfolioopt.readthedocs.io/)：分别用于常规模型、时间序列/统计检验和组合优化参考。

## 1. 定位

Research-to-Quant Lab 不是自动交易系统，也不是对外投资建议生成器。

它的定位是：

```text
把研究证据图谱转化为可检验量化假设的内部验证系统。
```

它服务机构内部研究团队：

- 从 Workpaper、ThesisDriver、EvidencePack、ProductIntelligenceGraph、CapitalMacroPack 和 MarketLiquidityPack 中提炼可计算信号；
- 构造 point-in-time feature / label / universe；
- 用 deterministic factor analysis、event study、backtest 和 risk attribution 检验研究判断；
- 生成 FactorCard，说明有效区间、失败场景、数据边界和是否值得继续观察；
- 反哺 Research Memory、Watchlist、Workpaper 和经验数据库。

它不做：

- 真实资金下单；
- 面向外部用户的交易建议；
- LLM 自动绕过 human approval 进入回测 / paper trading；
- LLM 自行生成无数据绑定的 feature、label 或 universe；
- 用回测结果包装确定性买卖结论。

## 2. Whole Picture

主链路：

```text
研究判断
 -> 可计算信号
 -> 可验证因子
 -> 事件研究 / 截面排序 / 组合回测
 -> paper portfolio monitor
 -> 反哺研究图谱和经验库
```

对象层级：

```text
SignalObservation
 -> FactorHypothesis
 -> FeatureSpec
 -> LabelSpec
 -> UniverseSpec
 -> DatasetBuildPlan
 -> PITDataset
 -> LeakageGuardResult
 -> FactorAnalysisResult
 -> BacktestResult
 -> RiskAttribution
 -> PaperTradingRun
 -> FactorCard
 -> ResearchExperienceRecord
```

关键原则：

1. LLM 只能提炼、解释和建议验证路径，不能直接产生未绑定数据的可交易规则。
2. Dataset build、backtest、paper trading 前必须 human approval。
3. 所有 feature 必须有 `source_ref`、`publish_time`、`available_time`、`asof_date`、`lag_policy` 和 `provenance`。
4. 回测结果只能作为 research validation，不能自动写成交易建议。
5. 失败、无效、过拟合、样本外失效和数据不可得都必须进入可检索经验库。

## 3. 公开数据下的信号全景

| 信号域 | 可计算对象 | 主要公开源 / 项目内原料 | 研究用途 | 边界 |
| --- | --- | --- | --- | --- |
| 价格与流动性 | momentum、reversal、volatility、volume、turnover、drawdown、gap、event reaction | 交易所 / Yahoo / Stooq / market snapshot / MarketLiquidity rows | price-in、拥挤度、短中期路径 | 不能证明基本面变化 |
| 财务基本面 | profitability、margin change、cash-flow quality、accruals、inventory、AR/AP、deferred revenue、capex、leverage | SEC CompanyFacts / FSD / 非美披露 / FundamentalStatementPack | 基本面质量和变化验证 | 必须 PIT，对 accepted time / available time 做滞后 |
| 估值与预期 | PE/PB/PS/EV/EBITDA、FCF yield、历史分位、同行分位、implied growth proxy | 价格、财报、同行 universe、公开估值数据 | 估值是否 price-in | 无 commercial consensus 时只能做弱版 price-in proxy |
| 产品与技术 | product generation、spec advantage、benchmark、architecture shift、datasheet signal | ProductIntelligenceGraph、official product surface、datasheet、benchmark proxy | 产品竞争力、代际变化、技术路线验证 | 可做 thesis driver，不冒充 SKU revenue / share |
| 客户 / 供应链 / 订单 | official deployment、customer case、public tender、OEM config、channel availability、supplier news | CustomerDeployment edges、official customer/supplier news、public procurement、channel rows | 需求真实性、read-through、采用进展 | 无 exact 披露时不能推销量、ASP、backlog、sell-through |
| 资本动作与股权结构 | buyback、offering、ATM、convertible、debt maturity、credit facility、Form 4、13D/G、13F、N-PORT | SEC filings、ownership rows、capital funding rows | 融资窗口、稀释、管理层行为、持仓拥挤 | 13F/N-PORT 滞后，不是实时资金流 |
| 宏观 / 商品 / 跨资产 | rates、yield curve、DXY、VIX、oil、natgas、copper、gold、industry ETF、up/downstream price | FRED、EIA、CFTC/CME/OCC/交易所公开数据、ETF/industry proxy | regime、成本压力、风险偏好、行业 beta | 只能作为 exposure / regime driver |
| 衍生品 | options volume/OI/IV/skew/put-call、futures curve、COT positioning | OCC、Nasdaq option chain、CFTC COT、CME delayed quotes | 市场预期、波动率定价、仓位拥挤 | 实时 OPRA / dealer gamma / borrow cost 通常商业授权 |
| 政策 / 监管 / 事件日历 | FDA/clinical、出口管制、监管处罚、产品发布、investor day、earnings date、unlock | ClinicalTrials、openFDA、SEC/IR calendar、监管公告、新闻 | event study、催化剂和风险窗口 | 事件发生不等于方向确定 |
| 文本与披露变化 | MD&A tone、risk factor diff、guidance language、capex/product/supply-chain term change | filings chunks、parser ledger、RAG / BM25 / Milvus supplement | 披露变化和管理层叙事 | 必须绑定 filing time，不得后验解释历史 |
| 图谱结构 | supplier/customer centrality、product competition/substitution、read-through path、peer contagion | ResearchGraphStore、ProductRelationshipGraph、source authority mart | 关系传播型信号、同业/上下游映射 | 图谱边要区分 parser-backed / inferred / weak signal |

公开数据可以支持：

- 基本面因子；
- 价格量价因子；
- 事件研究；
- 产品 / 技术 / 客户 / 供应链 proxy 因子；
- 宏观 / 商品 / 跨资产 exposure 因子；
- 资本动作、持仓滞后和市场流动性因子；
- 图谱关系传播信号。

公开数据很难支持：

- 实时资金流；
- 完整商业 consensus revision；
- 实时 OPRA options feed、dealer gamma、borrow cost；
- 精确订单、真实销量、渠道库存、sell-through；
- 高频交易执行质量；
- 未公开的基金实时仓位和机构内部模型。

## 4. 数据准备与清洗主线

### 4.1 Entity / Security Master

必须统一：

- issuer、security、ticker、CIK、ISIN、FIGI、交易所、币种；
- 上市 / 退市 / 并购 / 改名；
- ADR / dual listing / share class；
- 行业、vertical lane、product family、peer group。

量化验证必须避免 survivorship bias，不能只用当前仍存在的公司 universe 回测历史。

### 4.2 Market Data

必须保留：

- raw OHLCV；
- adjusted close；
- split / dividend；
- trading calendar；
- halt / zero-volume / abnormal rows；
- currency / timezone。

交易信号和收益标签必须明确使用哪种价格。价格异常处理、复权方式和交易日对齐需要写入 `DatasetBuildPlan`。

### 4.3 Fundamental PIT

对财务数据必须区分：

```text
period_end
filing_date
accepted_time
available_time
revision_time
asof_date
```

不能用 period end 后但尚未披露的数据做历史特征。amendment / restatement 必须保留 vintage。

### 4.4 Feature Store

`FeatureSpec` 至少包含：

- feature name / family / formula；
- source refs；
- input rowset；
- issuer/security binding；
- publish time / available time；
- lookback window；
- normalization；
- missing policy；
- neutralization；
- authority boundary；
- feature version。

缺失值要区分：

- company not applicable；
- company did not disclose；
- source not fetched；
- parser failed；
- public boundary；
- commercial gap。

### 4.5 Label Store

`LabelSpec` 至少包含：

- target horizon：1D / 5D / 20D / 60D / event window；
- return type：raw return / excess return / sector-neutral return / beta-neutral return；
- benchmark；
- holding period；
- rebalance calendar；
- dividend / corporate action policy；
- label availability check。

标签生成必须晚于 feature available time。

### 4.6 Leakage / Cost / Liquidity Gate

Dataset build 前必须检查：

- future data leakage；
- filing lag；
- restatement leakage；
- survivorship bias；
- universe drift；
- industry classification future version；
- label-feature overlap；
- liquidity / capacity；
- transaction cost / slippage；
- rebalance / turnover。

未过 gate 的 dataset 不能进入 backtest，只能作为 diagnostic artifact。

## 5. 方法体系

R53 不应一开始追复杂模型，而应按可解释、可审计、可回放的顺序推进。

| 方法 | 适用问题 | R53 角色 |
| --- | --- | --- |
| 传统截面因子 | value、quality、momentum、size、low-vol、profitability | baseline；判断研究因子是否有增量 |
| 事件研究 | earnings、产品发布、FDA、订单、回购、增发、监管 | 连接 EvidenceGraph / EventGraph 的第一优先方法 |
| 因子评价 | IC、Rank IC、quantile return、decay、turnover、coverage | 第一版必须具备，比组合回测更基础 |
| 规则型组合回测 | top/bottom quantile、long-short、long-only、sector-neutral | 验证 factor 是否能转成组合信号 |
| ML 排序 / 预测 | linear、ridge/lasso、tree/GBDT、learning-to-rank | 后续用于多因子组合，不能让 LLM 直接拍权重 |
| 时间序列 / regime | AR/VAR、state/regime、macro exposure | 用于宏观和跨资产环境解释 |
| 组合优化 / 风险模型 | risk parity、mean-variance、Black-Litterman、factor exposure control | 后续把 signal 变成组合，并解释风险来源 |
| paper trading monitor | 不下真实单，观察 live-like 表现 | 经过 human approval 后用于长期监控 |

第一版更适合先做：

- factor analysis；
- event study；
- 简单 vectorized portfolio backtest；
- risk attribution；
- FactorCard。

Qlib、LEAN、vectorbt、Alphalens 等可作为 adapter 或参考实现，但 R53 的核心不是“接一个库”，而是先把 PIT、lineage、approval 和 evaluation contracts 做正确。

## 6. Agent / Human 分工

### 6.1 Quant Translator Specialist

职责：

- 从 WorkpaperPack / ThesisDriver / DimensionEvidencePortfolio 中提炼 factor candidates；
- 把自然语言判断改写为 `FactorHypothesis`；
- 说明经济逻辑、适用 universe、预期方向、风险和数据需求；
- 标记该假设适合 factor analysis、event study、portfolio backtest 还是只能做 qualitative watch。

禁止：

- 自行生成无 source 的 feature；
- 自行改变 label；
- 自行绕过 PIT / leakage gate；
- 自行写买卖建议。

### 6.2 Deterministic Quant Runtime

职责：

- 构建 PIT dataset；
- 执行 leakage guard；
- 运行 factor analysis / backtest；
- 写入 run audit、artifact refs、FactorCard。

### 6.3 Human Approval

必须审批：

- factor hypothesis 是否值得进入 dataset build；
- feature / label / universe 是否合理；
- backtest plan 是否允许运行；
- FactorCard 是否进入 paper trading / watchlist / retired。

## 7. 反哺研究图谱与内部经验沉淀

用户提出：R53 的结果是否可以和其他功能中的内部经验沉淀联动，构建一个标准化、方便查阅、可审计、且像上下文库一样可被 agent 检索的数据库。

结论：应该做，而且它应是 R53 的核心输出之一，而不是附属日志。

### 7.1 为什么需要

Research-to-Quant 的价值不只在一次回测结果，而在持续积累：

- 哪些 thesis driver 历史上有效；
- 哪些只在特定 regime / sector / liquidity 条件下有效；
- 哪些看似有逻辑但回测失败；
- 哪些数据源经常导致 leakage / stale / missing；
- 哪些产品/供应链图谱边能产生稳定 read-through；
- 哪些 event 类型更适合 event study 而不是截面因子；
- 哪些 analyst judgment 被后续事实验证或否定。

这些经验如果只存在报告或聊天中，会丢失。它必须进入结构化经验库。

### 7.2 建议对象

新增长期对象：

```text
ResearchExperienceStore
FactorLifecycleLedger
QuantValidationMemory
ThesisOutcomeRecord
SignalReliabilityProfile
DataQualityExperienceRecord
```

它们和现有对象关系：

```text
WorkpaperEvent
 -> ThesisDriver
 -> FactorHypothesis
 -> BacktestResult / FactorAnalysisResult
 -> FactorCard
 -> ResearchExperienceRecord
 -> ResearchMemory / ContextEngine / GraphStore
```

### 7.3 最小 schema

`ResearchExperienceRecord`：

| 字段 | 说明 |
| --- | --- |
| `experience_id` | 稳定 ID |
| `source_run_id` | 对应 quant run / workpaper run |
| `thesis_driver_id` | 来源研究判断 |
| `factor_id` | 对应 FactorHypothesis |
| `entity_scope` | company / sector / industry / product / macro |
| `universe_spec_id` | 适用 universe |
| `time_window` | 验证区间 |
| `method` | factor analysis / event study / backtest / paper trading |
| `outcome` | supported / weak_supported / rejected / inconclusive / leakage_blocked / data_unavailable |
| `evidence_refs` | 证据来源 |
| `dataset_snapshot_id` | 数据版本 |
| `metrics` | IC、spread、return、drawdown、turnover、coverage、risk exposures |
| `failure_reason` | 失败或 blocked 原因 |
| `regime_tags` | rate regime、vol regime、sector cycle、macro state |
| `review_status` | human reviewed / auto generated / retired |
| `valid_until` | 经验有效期或下次复核时间 |

`SignalReliabilityProfile`：

- 信号源；
- signal family；
- 适用行业；
- 历史有效率；
- 失效模式；
- 典型 leakage 风险；
- 推荐使用方式；
- 禁止 claim。

### 7.4 检索和上下文联动

经验库应同时支持：

- SQL exact 查询：按 factor、universe、sector、outcome、time window 查；
- graph traversal：从产品/供应链/资本事件边追到历史验证结果；
- BM25 / vector search：查相似 thesis、相似失败案例、相似因子；
- ContextEngine 注入：Research Lead 在规划新任务时读取相关经验；
- Evidence Workbench 展示：用户能看到“过去类似 thesis 的验证结果”；
- Eval / failure ledger 联动：失败 case 进入长期样本集，不是临时日志。

### 7.5 Governance

经验库不能变成模型自我强化的垃圾堆：

- 只有通过 schema / provenance / review gate 的记录才能进入 `validated_experience`；
- 自动生成但未审阅的记录只能进入 `candidate_experience`；
- 失败记录不能删除，只能 supersede / retire；
- 经验必须有有效期和适用边界；
- 经验被下游 agent 使用时必须暴露来源和置信边界；
- 不能让历史回测好结果自动提升为当前投资建议。

### 7.6 和其他模块的联动

| 模块 | 联动方式 |
| --- | --- |
| Workpaper Builder | 在新底稿中提示相似 thesis 的历史验证结果 |
| Research Lead | 规划任务时读取相关 FactorCard / failed hypothesis / signal reliability |
| ProductIntelligenceGraph | 把 product / deployment / supply-chain signal 的历史有效性写回图谱边属性 |
| Watchlist | 对已批准 factor / thesis 做持续监控 |
| Deliverable Studio | 把 validated / rejected factor 作为 appendix 或方法说明 |
| Eval Runtime | 把失败、过拟合、leakage、样本外失效变成长期 eval cases |
| ContextEngine | 把经验作为可检索上下文，而不是塞进全局 prompt |

## 8. 当前项目可复用资产

已具备：

- RD0-RD7 raw disclosure / provenance / parser / gold mart / graph / retrieval / consumption / release gate；
- FundamentalStatementPack / financial statement rows；
- ProductIntelligenceGraph / ProductEvidencePack；
- CapitalMacroPack / capital funding ownership rows；
- MarketLiquidity rows；
- DimensionEvidencePortfolio；
- WorkpaperEvent / WorkpaperPack 规划；
- Eval / run audit / trace 规划。

R53 需要新增：

- quant artifact schema；
- PIT dataset builder；
- leakage guard；
- factor analysis runner；
- event study runner；
- simple vectorized backtest runner；
- risk attribution；
- paper trading monitor；
- FactorCard renderer；
- ResearchExperienceStore / QuantValidationMemory。

## 9. R53 / R54 / R58 / R60 边界分工

R53 不承包所有数据源、检索索引、前端交付和全流程 eval。它的职责是定义并运行 `Research-to-Quant` 的对象生命周期：把投研判断转成可验证的因子假设，再通过 point-in-time 数据集、leakage guard、验证结果和 human approval 形成可审计的 `FactorCard`。

### 9.1 分工原则

| 文档 / epic | 主职责 | 和 R53 的关系 |
| --- | --- | --- |
| R53 Research-to-Quant Lab | `FactorHypothesis`、`FeatureSpec`、`LabelSpec`、`UniverseSpec`、`DatasetBuildPlan`、`ValidationRun`、`FactorCard`、`ResearchExperienceRecord` | 拥有 quant object lifecycle、human approval、PIT / leakage / validation contract |
| R54 Secondary Market / Capital Feedback | ownership、credit/funding、corporate action、liquidity/positioning、valuation/price-in、expectation narrative、event catalyst、policy/regulatory、cross-asset、derivatives data packs | 向 R53 提供可作为 feature / event / regime 的市场和资本反馈数据；R53 不在本模块内直接实现所有 adapter |
| R58 RAG / Database / Retrieval | SQL exact、BM25、vector、graph hybrid retrieval、Feature Store / Label Store / Dataset Snapshot、index registry | 向 R53 提供可复现的数据访问、feature materialization 和 retrieval lineage |
| R60 Eval / Observability / Release Gate | leakage eval、factor eval、run trace、failure queue、gold set、dashboard、cost / latency / regression gate | 审计 R53 的输出质量、运行成本、失败生命周期和 release readiness |
| R52 Collaborative Workflow | WorkpaperEvent、Lead / specialist / human review workflow | R53 消费 `WorkpaperPack` / `ThesisDriver`，并把 FactorCard / validation result 写回 workpaper ledger |
| R55 Deliverable Studio / Dashboard Projection | Word / PPT / Markdown / dashboard / Excel 输出 | R53 只提供可引用的 FactorCard、chart data 和 appendix artifact，不直接拥有交付 UI |

### 9.2 信号域归属

R53 必须能表达下列信号域，但不要求第一版在 R53 内部直接实现全部数据源 adapter：

| 信号域 | R53 责任 | 主要数据落点 |
| --- | --- | --- |
| price / liquidity / return | 作为 baseline feature、label、cost、liquidity gate | R54 / R58 |
| fundamental accounting | 作为 value / quality / profitability / balance-sheet factor source | 已有 FundamentalStatementPack + R58 |
| valuation / price-in | 作为估值分位、implied growth、peer-relative feature | R54 |
| product / technology / deployment | 作为 product thesis、event study、graph-derived feature | ProductIntelligenceGraph + R58 |
| customer / supply-chain / order signal | 作为 event / graph edge / adoption proxy，不能自动冒充 revenue exact | ProductIntelligenceGraph + R54 / R58 |
| ownership / holder / insider | 作为 capital flow、crowding、governance / activist signal | R54 |
| credit / funding / corporate action | 作为融资成本、稀释、回购、资本结构压力 signal | R54 |
| macro / cross-asset / derivatives | 作为 regime、discount-rate、commodity-cost、volatility / positioning signal | R54 |
| policy / regulatory / event catalyst | 作为事件窗口和行业 beta 变化 signal | R54 / existing public source packs |
| text disclosure / narrative | 作为 NLP feature candidate，必须保留 source and as-of time | R58 |
| graph structure | 作为 read-through、substitution、competition、supply constraint feature candidate | ProductIntelligenceGraph + R58 |

R53 的约束是：任何信号都必须先进入 `SignalObservation` 或 `FeatureSpec`，并带上 `source_refs`、`asof_time`、`entity_scope`、`authority_class`、`claim_boundary`。如果 R54 / R58 尚无可用数据，R53 只能生成 `DataAvailabilityGap`，不能伪造 feature。

### 9.3 R53 第一版可先做什么

R53 v0.1 可以只复用当前已有数据：财报、市场流动性、产品图谱、资本/持仓的已落地 rows。它仍然必须按完整对象模型写入，避免未来补 R54 / R58 时推翻 schema。

v0.1 可以先做：

- `FactorHypothesisCandidate` 生成；
- factor analysis；
- event study；
- 简单 portfolio backtest；
- leakage / missingness / coverage gate；
- FactorCard JSON / Markdown artifact；
- candidate experience 写入。

暂不强求：

- 完整单股 options / futures / COT / ETF flow；
- 复杂组合优化；
- live paper trading；
- Workbench UI 全量编辑；
- 多市场全覆盖。

## 10. Research-to-Quant Stable Object Model

对象模型必须稳定到足以承接未来 R54 / R58 / R60 的扩展。核心原则是：事件溯源、PIT 优先、source authority 显式化、LLM proposal 与 deterministic runtime 分离。

### 10.1 主链路

```text
WorkpaperEvent
 -> ThesisDriver
 -> SignalObservation
 -> FactorHypothesisCandidate
 -> HumanApprovalDecision
 -> FactorHypothesis
 -> FeatureSpec
 -> LabelSpec
 -> UniverseSpec
 -> DatasetBuildPlan
 -> PITDatasetSnapshot
 -> LeakageGuardResult
 -> ValidationPlan
 -> FactorAnalysisResult / EventStudyResult / BacktestResult
 -> RiskAttribution
 -> FactorCard
 -> ResearchExperienceRecord
 -> ResearchMemory / ContextEngine / GraphStore
```

### 10.2 核心对象

| 对象 | 作用 | 稳定字段 |
| --- | --- | --- |
| `SignalObservation` | 把研究证据、产品图谱、市场信号统一成 quant 可读观察 | `signal_id`、`signal_family`、`entity_scope`、`source_refs`、`asof_time`、`direction_hint`、`authority_class`、`claim_boundary`、`data_gap_refs` |
| `FactorHypothesisCandidate` | LLM / analyst 提出的待审因子想法 | `candidate_id`、`source_thesis_driver_id`、`economic_logic`、`expected_direction`、`horizon`、`candidate_features`、`known_risks`、`approval_required` |
| `FactorHypothesis` | 通过 human gate 后的正式待验证假设 | `factor_id`、`approved_by`、`approved_at`、`universe_spec_id`、`feature_spec_ids`、`label_spec_id`、`method_scope`、`forbidden_claims` |
| `FeatureSpec` | 可执行 feature 定义 | `feature_id`、`input_refs`、`formula`、`transform`、`lag_policy`、`missing_policy`、`winsorize_policy`、`neutralization_policy`、`schema_version` |
| `LabelSpec` | forward return / event outcome / risk-adjusted target | `label_id`、`return_horizon`、`benchmark`、`corporate_action_adjustment`、`lookahead_guard` |
| `UniverseSpec` | 样本空间和排除规则 | `universe_id`、`market`、`sector_scope`、`liquidity_floor`、`listing_filter`、`survivorship_policy`、`rebalance_calendar` |
| `DatasetBuildPlan` | 生成 PIT dataset 的确定性计划 | `plan_id`、`feature_spec_ids`、`label_spec_id`、`universe_spec_id`、`asof_calendar`、`data_source_versions` |
| `PITDatasetSnapshot` | 可复现数据集快照 | `snapshot_id`、`plan_id`、`built_at`、`row_count`、`coverage_stats`、`artifact_uri`、`input_hash` |
| `LeakageGuardResult` | 阻止未来函数和数据泄露 | `guard_id`、`snapshot_id`、`status`、`violations`、`blocked_features`、`decision` |
| `ValidationResult` | factor analysis / event study / backtest 的统一父对象 | `validation_id`、`method`、`snapshot_id`、`metrics`、`risk_exposure`、`cost_assumption`、`failure_reason` |
| `FactorCard` | 给人审阅的因子验证报告 | `factor_card_id`、`factor_id`、`summary`、`support_level`、`charts`、`tables`、`claim_boundaries`、`next_action` |
| `ResearchExperienceRecord` | 可检索、可失效、可反哺的经验记录 | `experience_id`、`factor_id`、`outcome`、`regime_tags`、`valid_until`、`review_status`、`supersedes` |

### 10.3 存储形态

不能只保存一个大 JSON。稳定实现应拆成四层：

| 层 | 存什么 | 用途 |
| --- | --- | --- |
| SQL tables | factor、feature、label、universe、dataset、validation、approval、experience 的主索引 | exact 查询、审计、权限和版本 |
| Artifact store | dataset parquet、charts、backtest result tables、FactorCard Markdown / HTML | 大文件和可复现实验输出 |
| Graph edges | thesis -> signal -> factor -> result -> experience；product / capital / macro signal 到 factor 的来源边 | read-through、经验反哺和关系追踪 |
| Vector / BM25 index | FactorCard 摘要、失败原因、相似 thesis、human review comments | ContextEngine 检索和 analyst 复盘 |

每个对象必须有 `schema_version`、`created_at`、`source_run_id`。会被替换或失效的对象必须支持 `supersedes`、`valid_from`、`valid_until`、`retired_reason`。

### 10.4 权限与边界

- LLM 可以创建 `SignalObservation` 摘要和 `FactorHypothesisCandidate`，但不能直接批准 `FactorHypothesis`。
- Human reviewer 批准后，deterministic runtime 才能构建 `PITDatasetSnapshot`。
- Runtime 不能自行修改经济逻辑，只能按 `FeatureSpec` / `LabelSpec` 执行。
- 如果数据不可得，写 `DataAvailabilityGap`；不能用 proxy 冒充 exact feature。
- 回测好结果只能进入 `candidate_experience` 或 `validated_experience`，不能自动生成交易建议。
- 任何进入 watchlist / paper trading 的 factor 都必须有 approval event 和 rollback path。

### 10.5 为什么这样不会推翻

这个模型把未来扩展点放在对象边界上，而不是写死在某个行业或某类数据里：

- 新增 R54 二级市场数据，只是新增 `SignalObservation` 和 `FeatureSpec` input；
- 新增 R58 检索 / Feature Store，只是替换 `DatasetBuildPlan` 的 materialization backend；
- 新增 R60 eval，只是增加 `ValidationResult` / `LeakageGuardResult` 的 gate 和 dashboard；
- 新增 Qlib / vectorbt / Alphalens，只是替换 `ValidationPlan` executor adapter；
- 新增 A 股、非美、期货、期权，只是扩展 `UniverseSpec`、`InstrumentMaster` 和 feature calendar；
- 新增产品图谱 signal，只是增加 `graph_signal` family，不改变主链路。

因此 R53 先落 v0.1 也必须按这个对象模型写，哪怕第一版只填部分字段。

## 11. 仍待拆分的迭代问题

后续再拆版本节奏时只剩实现取舍，而不是基础边界问题：

1. v0.1 是否只做 factor analysis + event study，还是保留简单 portfolio backtest；
2. v0.1 是否先只支持日频美股，非美/A 股作为 v0.2；
3. FactorCard 第一版只生成 Markdown / JSON artifact，还是直接进入 Workbench UI；
4. ResearchExperienceStore 第一版用 SQLite / DuckDB，还是直接进入 Java 后端 DB schema；
5. Qlib / vectorbt / Alphalens 是作为 adapter 接入，还是先做内部 deterministic runner；
6. R54 二级市场数据没有补全前，R53 v0.1 允许验证哪些低依赖因子；
7. paper trading monitor 是 v0.1 范围，还是等 R54 / R60 后接入。

## 12. 草案结论

R53 的第一性问题不是“怎么跑一个回测”，而是：

```text
如何把投研证据图谱中的判断，转换成 point-in-time、可审计、可复现、可被人批准和复盘的量化验证对象。
```

因此后续 R53 拆分必须先保护五个地基：

1. 时间语义：publish / available / asof / label horizon。
2. 数据血缘：source / parser / feature / dataset / run / factor card。
3. 权限边界：LLM proposal、human approval、deterministic runtime。
4. 评价闭环：IC / event study / backtest / risk / paper monitor。
5. 经验沉淀：ResearchExperienceStore 可检索、可审计、可失效、可反哺。
