# PRD：FinSight B 端金融研究工作台

日期：2026-06-28

状态：产品经理向 PRD 草案。本文定义 B 端用户、工作流、功能边界、底稿与交付物要求、dashboard/watchlist/图谱交互和验收标准。本文不定义具体 runtime、API、DB schema、agent graph 实现；技术方案应另拆架构文档和交付文档。

关联产品文档：

- `docs/product/PRODUCT_20260628_finsight_tob_toc_positioning_and_product_line.zh-CN.md`
- `docs/architecture/agent_graph_vnext/25_agent_runtime_reference_stack_and_harness_context_engine_draft.zh-CN.md`

## 1. 产品定位

FinSight B 端应定位为：

```text
Evidence-backed Financial Research Workbench
可审计的金融研究工作台 / AI junior analyst layer
```

它不是通用金融聊天框，也不是直接替代 senior / PM / 投委会的自动决策系统。第一阶段目标是替代或压缩 junior analyst / associate 的底层重复工作：

- 收集公开披露、市场数据、产品数据、行业数据和用户上传材料；
- 做表格抽取、科目归类、事实核对、引用定位；
- 建证据包、研究底稿、反方证据、缺口台账；
- 生成 first draft、PPT outline、Excel appendix、客户简报；
- 支持 senior / manager 审阅、追问、改稿、批准和复盘。

核心商业承诺：

```text
降低低阶研究生产成本，
提高证据密度和流程一致性，
保留 human review、责任链和审计能力。
```

## 2. 目标用户和角色

### 2.1 机构类型

- 券商研究所；
- 买方投研团队；
- 投顾 / 财富管理；
- PE / VC / 并购 / 债券尽调团队；
- 咨询公司；
- 会计师事务所；
- 企业战略、IR、投资与财务部门。

### 2.2 用户角色

| 角色 | 目标 | 主要动作 |
| --- | --- | --- |
| Senior Analyst / PM / Manager | 定义研究问题、复核结论、形成判断 | 创建任务、审阅底稿、追问缺口、批准交付物 |
| Junior Analyst / Associate | 执行研究生产、整理数据、写初稿 | 使用系统生成底稿、修正证据、补充人工判断 |
| Compliance / Reviewer | 检查引用、边界、风险和交付质量 | 查看 trace、citation、gap、版本、审批记录 |
| Data / Knowledge Admin | 管理机构知识库、私有文档和权限 | 上传数据、配置数据源、维护模板和权限 |
| Client-facing User | 生成客户可读交付物 | 导出 brief、deck、Word/PDF、图表和 appendix |

## 3. 核心用户问题

当前 B 端研究流程的主要痛点：

1. 资料和数据分散，junior 大量时间花在找、复制、对数和整理上。
2. 研报/底稿结论常常难以追溯到原始证据。
3. 公开数据、私有材料、历史研究和市场信号没有统一证据层。
4. 多人协作时，问题定义、数据缺口、反方证据和版本记录容易丢失。
5. 输出交付物格式多样，但当前 agent 往往只输出一段长文本。
6. 只靠一次主 agent 调用加几个 specialist 并发请求，不像真实研究团队协作。

## 4. 产品形态

B 端产品主体应是工作台，而不是聊天页。

```text
Dashboard
 -> Research Task Center
 -> Input / Data Room
 -> Evidence Workbench
 -> Workpaper Builder
 -> Research-to-Quant Lab
 -> Lead Review
 -> Deliverable Studio
 -> Human Review / Approval
 -> Knowledge Base / Watchlist / Eval Trace
```

聊天或自然语言输入只作为入口之一。用户更常用的入口应包括：

- dashboard 上的任务、公司、行业、watchlist；
- 文件上传和 data room；
- 公司/行业知识库页面；
- 图谱探索页面；
- 交付物编辑器；
- 审批和评论流。

## 5. 数据与信息范围

Evidence Workbench 必须综合 25 文档中的完整研究信息范围，而不是只看当前已实现源。

### 5.1 公司基本面与披露

- SEC / 非美交易所披露；
- 10-K / 10-Q / 20-F / 6-K / annual report / IR deck；
- 三大表：利润表、资产负债表、现金流量表；
- 一级/二级/三级会计科目；
- 同行业、可比公司同口径对比；
- management discussion、风险、segment、geography、capex、working capital。

### 5.2 产品、技术、客户和供应链

- ProductIntelligenceGraph；
- 产品 profile、product family、product/service slot；
- 产品规格、架构、代际、benchmark、whitepaper、datasheet；
- 客户部署、采用、订单/项目事件、OEM config、渠道可得性；
- 竞争、替代、互补、上下游、平台依赖、read-through；
- Product-KPI exact：收入、出货、delivery、backlog、ASP、毛利、ARR/RPO、订阅数、AUM、产能、利用率等。

### 5.3 行业、政策、监管和外部验证

- 行业协会、政府/监管数据库、公开统计；
- ClinicalTrials、openFDA、NHTSA、EIA、FRED、FDIC、Census、OpenAlex、PatentsView；
- 新闻、公司官方博客、客户/供应商官方新闻；
- 招聘、开发者生态、app store、marketplace、公开采购、渠道报价；
- 只要信源足够强，可以作为 bounded thesis driver，但不得冒充 exact financial fact。

### 5.4 资本市场、资金面和二级市场

- 13F、13D/G、Form 3/4/5、N-PORT、ETF 持仓和权重；
- 回购、增发、ATM、可转债、并购、股权激励；
- 债务工具、credit facility、coupon、maturity、credit spread、评级变化；
- 成交额、换手率、short interest、free float、波动率、市场反应；
- PE/PB/PS/EV/EBITDA/FCF yield、同行估值、implied growth；
- 期权/期货、商品、利率、美元、VIX、CFTC COT、跨资产 read-through；
- 这些信号进入 market expectation / price-in / positioning / capital feedback，不直接证明基本面改善。

### 5.5 用户上传和机构私有材料

- PDF、Word、PPT、Excel、Markdown、网页链接；
- 会议纪要、访谈、专家电话、内部模型、历史 memo；
- Data room：招股书、合同、财务模型、行业报告、客户材料；
- 上传材料必须进入 provenance、权限、引用定位和版本管理。

## 6. 功能模块

### 6.1 Dashboard / Home

目标：让用户进入系统后看到任务、覆盖范围、风险、事件和待审事项，而不是空白聊天框。

必须支持：

- 我的研究任务；
- 我的 watchlist / portfolio；
- 最近公告、财报、产品、政策、资金面事件；
- 待审底稿、待确认缺口、待批准交付物；
- 成本、耗时、失败任务、质量告警；
- 团队项目空间入口。

通过标准：

- 用户能从 dashboard 进入任一公司/任务/交付物/trace；
- 每个任务状态清楚：planning、collecting、analysis、lead review、drafting、human review、approved、failed；
- 失败任务必须显示原因和下一步动作，不允许静默失败。

### 6.2 Research Task Center

目标：把自然语言问题变成可执行的研究任务，而不是让模型自由发挥。

任务类型：

- 财报/业绩点评；
- 公司深度初稿；
- 同行/竞品/产品对比；
- 事件影响分析；
- 供应链 read-through；
- 资本市场/资金面分析；
- 投研观点到量化因子验证；
- 尽调 data room 初筛；
- watchlist 定期更新；
- 客户版 brief / 投委会 memo / deck 生成。

任务创建时必须形成 `Research Objective Contract`：

- 原始问题；
- 研究对象：公司、行业、产品、事件、时间范围；
- 必答维度；
- 允许/禁止的数据源；
- 输出格式；
- 缺口处理要求；
- 人工审核人；
- 成本/时延预算；
- 通过标准。

### 6.3 Input / Data Room

目标：企业用户可以上传资料，让系统像 junior 一样读材料、切表、抽事实、做引用。

支持输入：

- PDF / DOCX / PPTX / XLSX / CSV / Markdown；
- 图片和扫描件 OCR；
- 网页链接；
- 文件夹级 data room；
- 私有笔记和会议纪要。

必须产出：

- parsed document outline；
- table/cell extraction；
- cited snippets；
- structured facts；
- source authority；
- document-level permission；
- artifact version；
- rejected/low-confidence extraction log。

### 6.4 Evidence Workbench

目标：让用户看到系统究竟找到了什么、没找到什么、哪些能用、哪些不能提权。

核心对象：

- EvidencePack；
- DataPack；
- GraphPack；
- ClaimCard；
- GapLedger；
- SourceAuthority；
- PublicEvidenceCoverageProfile；
- DimensionEvidencePortfolio。

功能：

- 按维度查看证据：基本面、产品、行业、资本市场、政策、风险；
- 查看每条证据的 source、parser、citation、authority、时间、适用边界；
- 手动降权、标记无效、要求补查；
- 对 gap 分类：retrievable gap、public-source boundary、commercial gap、not material、forbidden claim；
- 生成 evidence appendix。

### 6.5 Workpaper Builder

目标：建立合格底稿层。写作器不能直接拼 ClaimCard；必须先形成底稿。

`WorkpaperPack` 是 EvidencePack 到 Deliverable 之间的产品核心对象。

底稿必须包含：

- 研究问题和初步判断；
- 必答维度覆盖；
- 分维度证据矩阵；
- 财务三表和同行同口径对比；
- 产品/客户/供应链图谱；
- 资本市场和资金面；
- 估值和 price-in；
- 反方证据；
- 缺口和边界；
- senior review notes；
- appendix refs。

标准底稿模板：

| 模板 | 场景 | 必备内容 |
| --- | --- | --- |
| Earnings Review Workpaper | 财报/业绩点评 | 三大表、segment、guidance、management commentary、市场反应、同行对比 |
| Company Deep Dive Workpaper | 公司深度 | 业务、财务、产品、竞争、资本、估值、风险、反方 |
| Product / Competitive Workpaper | 产品或竞品对比 | product family、spec、architecture、benchmark、客户部署、供应链、竞争边 |
| Event Impact Workpaper | 产品发布、订单、政策、监管、融资 | 事件事实、影响链、受益/受损方、反方、price-in |
| Capital Feedback Workpaper | 二级市场和融资反馈 | ownership、liquidity、corporate action、credit、valuation、derivatives |
| Research-to-Quant Workpaper | 投研观点到量化验证 | thesis driver、factor hypothesis、feature/label/universe、数据可得性、回测计划、人工批准记录 |
| Data Room Diligence Workpaper | 尽调材料初筛 | 文件清单、关键条款、财务/合同/风险抽取、缺失清单 |
| Watchlist Update Workpaper | 持续监控 | 新事件、thesis driver 变化、风险变化、触发动作 |

通过标准：

- 每个核心判断都能追溯到 evidence refs；
- 每个必答维度有 status：sufficient、retrievable_gap、public_boundary、commercial_gap、not_material；
- senior 能在底稿上评论、改判断、要求补查；
- Deliverable Composer 只能从 approved 或 review-ready WorkpaperPack 生成正式交付物。

### 6.6 Graph / Visualization Workspace

目标：让图谱成为研究和解释界面，不只是后台数据结构。

至少支持：

- 公司-产品-客户-供应链关系图；
- 产品竞争/替代/代际图；
- 资本结构/债务/持仓图；
- 事件时间线；
- thesis driver map；
- evidence coverage heatmap；
- peer comparison matrix；
- watchlist risk map。

图谱边必须显示：

- edge type；
- direction；
- evidence refs；
- confidence / authority；
- last updated；
- boundary。

### 6.7 Research-to-Quant Lab

目标：把研究底稿、thesis driver、多源证据和图谱推理转成可检验的量化因子假设，并自动执行数据集构建、回测、风险归因和模拟交易监控，但不接真实资金交易，也不面向外部用户提供交易建议。

该模块面向有量化研究需求的机构内部用户。它不是自动交易员，而是研究到量化验证的过渡层：

```text
Research Workpaper / ThesisDriver
 -> FactorHypothesis
 -> FeatureSpec / LabelSpec / UniverseSpec
 -> Point-in-time Dataset
 -> BacktestPlan
 -> BacktestResult
 -> RiskAttribution
 -> PaperTradingRun
 -> FactorCard / PromotionDecision
```

必须支持的对象：

- `ThesisDriver`：来自底稿的研究观点、驱动因素、反方和证据强度；
- `FactorHypothesis`：可检验假设，说明预期方向、适用 universe、时间窗口、失效场景；
- `FeatureSpec`：特征来源、计算方法、lag、winsorize、中性化、缺失处理、可获得时间；
- `LabelSpec`：forward return、excess return、sector-neutral return、event-window return、drawdown 等；
- `UniverseSpec`：股票池、行业、市值、流动性、国家/交易所、可交易性过滤；
- `DatasetBuildPlan`：point-in-time 数据集、vintage、发布日期、system available time、leakage guard；
- `BacktestPlan`：回测区间、rebalance、持仓构建、交易成本、slippage、benchmark；
- `BacktestResult`：收益、回撤、Sharpe、IC/RankIC、turnover、capacity、hit rate；
- `RiskAttribution`：beta、sector、size、momentum、quality、growth、liquidity、event risk；
- `PaperTradingRun`：模拟组合、信号监控、虚拟成交、PnL attribution；
- `FactorCard`：因子逻辑、数据、结果、风险、失效场景、当前状态；
- `PromotionDecision`：candidate、validated、paper_trading、monitored、rejected、retired。

Human-in-the-loop 要求：

- 用户可以选择 `manual mode`：只生成候选因子和数据需求，由人工修改 FeatureSpec / LabelSpec / UniverseSpec 后再运行。
- 用户可以选择 `assisted mode`：系统自动生成候选因子和回测计划，但进入 dataset build / backtest 前必须人工批准。
- 用户可以选择 `auto candidate mode`：系统自动批量生成候选因子，但每个因子进入 paper trading 前必须人工批准。
- 系统不得默认把研究观点自动推入回测、模拟交易或长期监控。
- 系统不得把 backtest 结果直接写成买卖建议；只能写成模型验证结果、适用边界和是否进入后续观察。
- 人工可以修改、冻结、否决、降级或退休任何 FactorHypothesis / FactorCard。

硬门控：

- 无未来函数：所有特征必须有 source publish time、system available time、tradable-after 时间。
- 样本外验证：train / valid / test 时间切分，test 不用于反复调参。
- 幸存者偏差控制：股票池、退市、并购、指数成分变化必须记录。
- 交易成本和流动性：spread、成交额、换手、capacity、slippage 必须进入回测假设。
- 风险归因：区分 alpha 与 beta、sector、size、momentum、quality、growth、liquidity 暴露。
- 可解释性：每个因子必须能追溯到 thesis driver、evidence refs、feature refs 和数据版本。
- Promotion gate：回测通过只代表 validated candidate，不等于上线或交易建议。

通用场景：

- 财报因子：盈利质量、利润率变化、现金流质量、working capital、指引变化；
- 产品/技术因子：产品代际、规格优势、客户部署、供应链 read-through；
- 资本市场因子：资金流、持仓拥挤、回购/增发、信用融资、流动性变化；
- 事件因子：FDA/临床、订单、政策、监管、产品发布、投资者日；
- 宏观/跨资产因子：利率、商品、汇率、波动率、行业 beta 和风格轮动；
- 机构私有因子：用户上传 data room、内部访谈、历史 thesis 和人工标注。

通过标准：

- Research Workpaper 中的 thesis driver 能被转成一个或多个 FactorHypothesis；
- 每个 FactorHypothesis 都显示数据可得性、泄漏风险、样本范围和缺失情况；
- 人工能在 UI 中决定是否自动接入、手动调整或否决；
- 回测结果能解释有效/无效原因和风险暴露；
- Paper trading 不连接真实资金账户，不生成真实订单；
- FactorCard 能反馈到原研究底稿和 watchlist。

### 6.8 Deliverable Studio

目标：输出端不再只是 `Memo Writer`，而是多格式交付物生成和编辑。

建议命名：

```text
Deliverable Composer / Report Studio
```

支持输出：

- 长回答；
- Markdown memo；
- Word 研报；
- PPT deck；
- Excel data appendix；
- PDF brief；
- 图谱图、思维导图、关系图、时间线；
- 客户版摘要；
- 内部版底稿；
- 投委会 briefing。

职责边界：

- 可以调用文档、图表、表格、PPT、PDF、Excel 渲染工具；
- 不应绕过 Research Lead 自己查事实；
- 不应直接从 raw retrieval rows 生成结论；
- 必须使用 WorkpaperPack、JudgmentState、DeliverablePlan 和 approved evidence refs。

交付物必须支持：

- 引用和 appendix；
- 内部版 / 客户版不同口径；
- 图表和表格；
- 风险提示；
- 缺口 disclosure；
- 版本对比；
- 人工编辑。

### 6.9 Watchlist / Monitoring

目标：从一次性问答升级到持续覆盖。

监控对象：

- 公司；
- 行业；
- 产品；
- 供应链；
- 主题；
- 资本市场信号；
- 政策/监管；
- 事件日历。

触发类型：

- 财报/公告；
- 产品发布；
- 客户部署/订单；
- 监管/政策；
- 价格/成交/波动异常；
- 资金面/持仓变化；
- 信用/融资事件；
- 竞争对手变化。

输出：

- watchlist update card；
- thesis driver changed / unchanged；
- factor signal changed / unchanged；
- paper trading monitor changed / unchanged；
- needs review；
- material event；
- no action。

### 6.10 Human Review / Approval

目标：把 human/lead in the loop 做成产品功能，而不是调试阶段临时介入。

支持：

- 任务审阅；
- 证据降权；
- 结论修改；
- 补查请求；
- 交付物批注；
- 审批流；
- 历史版本；
- 责任人；
- audit trail。

必须支持 senior 对系统说：

- 这个维度证据不够，重新查；
- 这个信源不能提权；
- 这个结论写得太保守/太激进；
- 这个 gap 不重要；
- 这个结论需要反方；
- 这个交付物可以给客户。
- 这个 thesis 可以/不可以转成因子假设；
- 这个 FactorSpec 需要人工调整；
- 这个因子可以/不可以进入回测或 paper trading。

### 6.11 Admin / Governance

目标：满足 B 端部署、审计、权限和成本控制。

必须支持：

- 组织 / 项目 / 角色 / 权限；
- 私有数据隔离；
- 数据源配置；
- 模板配置；
- 模型和工具预算；
- run trace；
- eval dashboard；
- failure/gold lifecycle；
- 成本和时延统计；
- 导出审计包。

## 7. Multi-agent 产品要求

当前 fixed fanout + second pass 的模式不够像真实团队协作。B 端产品要求不是“多调用几个模型”，而是让 agent workflow 像一个可审计研究团队。

产品层面需要：

1. Research Lead 是 supervising analyst，不是一次性 dispatcher。
2. Specialist 不是孤立回答者，而是围绕同一个 WorkpaperPack 贡献维度分析。
3. Specialist 可以提出缺口、反方和补查请求。
4. Research Lead 可以中途重新分派任务、要求 targeted repair、合并或拆分任务。
5. Human reviewer 可以插入任何关键节点。
6. 所有 agent 共享同一份任务合同、证据状态、底稿状态和 gap 状态，但权限和可见范围分层。
7. agent 间通信必须形成结构化 artifacts，而不是隐藏在 prompt 聊天记录里。
8. 最终写作器只负责表达和交付物生成，不能充当事实补查者。

产品期望的协作形态：

```text
Research Objective Contract
 -> Research Lead Planning
 -> Evidence Operators / Data Room Parser / Graph Retrieval
 -> Specialist Workstreams
 -> Shared WorkpaperPack
 -> Lead Review Checkpoint
 -> Targeted Repair / Specialist Rework / Human Question
 -> JudgmentState
 -> DeliverablePlan
 -> Deliverable Composer
 -> Human Approval
```

该部分后续需要拆成独立技术方案，讨论 agent graph、共享上下文、agent communication、human-in-the-loop、async/sync、工具权限和成本调度。

## 8. MVP 切片

### 8.1 B0：产品壳与任务闭环

目标：从 dashboard 创建任务，能看到状态、底稿、证据、交付物。

包括：

- Dashboard；
- Research Task Center；
- Research Objective Contract；
- task status；
- basic evidence view；
- WorkpaperPack skeleton；
- Deliverable Composer skeleton；
- trace link。

### 8.2 B1：财报/业绩点评

目标：替代 junior 做标准 earnings review 初稿。

必须覆盖：

- 三大表；
- 同比/环比/历史趋势；
- segment/product/business line；
- 同行对比；
- management commentary；
- guidance；
- 市场反应；
- 缺口和反方。

### 8.3 B2：公司深度初稿

目标：生成可审阅的公司深度底稿和 memo。

必须覆盖：

- 业务和产品；
- 财务三表；
- 产品/客户/供应链；
- 行业和竞争；
- 资本市场/资金面；
- 估值和 price-in；
- 风险与反方；
- thesis / counter-thesis。

### 8.4 B3：产品/竞品/供应链研究

目标：让 ProductIntelligenceGraph 真正进入用户可见分析。

必须覆盖：

- 产品 family 和 spec；
- 架构/代际/benchmark；
- 竞品关系；
- 客户部署；
- 供应链 read-through；
- exact KPI 与 bounded thesis signal 分离。

### 8.5 B4：Data Room / 文件上传

目标：企业用户能上传材料并进入证据流。

必须覆盖：

- PDF/DOCX/PPTX/XLSX 解析；
- OCR；
- table/cell extraction；
- citation；
- permission；
- user-provided evidence boundary。

### 8.6 B5：Watchlist / Monitoring

目标：从一次性研究变成持续覆盖。

必须覆盖：

- 公司/行业/主题 watchlist；
- event trigger；
- thesis driver changed/unchanged；
- alert card；
- scheduled review。

### 8.7 B6：Research-to-Quant Lab

目标：让机构内部用户把研究底稿中的 thesis driver 转成可检验因子，并在人工批准下运行数据集构建、回测、风险归因和模拟交易。

必须覆盖：

- thesis driver -> FactorHypothesis；
- FeatureSpec / LabelSpec / UniverseSpec；
- point-in-time 数据可得性检查；
- leakage / survivorship / liquidity / cost gate；
- backtest result；
- risk attribution；
- FactorCard；
- human approval for auto candidate / backtest / paper trading；
- 不连接真实资金交易。

## 9. 用户验收标准

### 9.1 研究任务验收

- 用户能在 5 分钟内创建一个标准研究任务；
- 系统能生成结构化任务合同；
- 用户能看到每个节点状态和失败原因；
- 每个核心结论有 citation 或 gap；
- 用户能要求补查并看到补查结果。

### 9.2 底稿验收

- 底稿不是证据堆叠，而是按研究问题组织；
- 必答维度覆盖状态清晰；
- 反方证据和缺口可见；
- senior 能直接在底稿上 review；
- 底稿能导出为 appendix 或内部工作底稿。

### 9.3 交付物验收

- 同一底稿能生成 Word、PPT、Markdown、PDF、Excel appendix 中至少两类；
- 输出分内部版和客户版；
- 引用、图表、appendix 可追溯；
- 用户可编辑并保存版本；
- 不出现内部字段污染正文，如 raw role id、mechanism 字段、未解释的 ClaimCard 标签。

### 9.4 数据和证据验收

- 明确区分 exact fact、bounded thesis signal、proxy、gap；
- 二级市场、期权/期货、资金面、社媒/弱信号不得冒充基本面事实；
- 用户上传材料必须可追溯；
- rejected extraction 和 parser failure 必须可见；
- commercial gap 不得伪装成公开源已解决。

### 9.5 协作验收

- Research Lead 至少在 planning 和 review 两个关键节点出现；
- Specialist 输出必须进入共享底稿，而不是直接进入最终 memo；
- Human reviewer 可以插入任务、底稿、证据和交付物；
- 所有人工修改、agent 修改和版本变化可追溯。

### 9.6 量化验证验收

- 系统能从 approved 或 review-ready WorkpaperPack 中抽取 thesis driver，并生成结构化 FactorHypothesis；
- 用户可以选择 manual mode、assisted mode 或 auto candidate mode；
- assisted / auto candidate 下，dataset build、backtest、paper trading 都需要人工批准才能进入下一阶段；
- FactorSpec 必须记录 feature、label、universe、lag、vintage、system available time、tradable-after、缺失处理和 leakage guard；
- 回测必须显示交易成本、流动性、样本外、风险暴露和 benchmark；
- PaperTradingRun 只能生成模拟组合和监控记录，不能连接真实资金账户或真实订单；
- FactorCard 必须能回到原 thesis、证据、底稿和数据版本；
- rejected / retired 因子必须保留原因，不能从结果里静默消失。

## 10. 指标

产品指标：

- time to first workpaper；
- time to review-ready deliverable；
- human edit distance；
- task completion rate；
- deliverable export success rate；
- reviewer approval rate；
- repeated user task rate；
- watchlist alert usefulness。
- factor hypothesis approval rate；
- paper trading promotion rate。

质量指标：

- citation coverage；
- unsupported claim rate；
- gap classification accuracy；
- evidence authority misuse rate；
- workpaper completeness；
- readability score；
- thesis density；
- counter-thesis coverage；
- retrieval/role-visible recall。
- factor leakage violation rate；
- backtest reproducibility rate；
- factor attribution completeness。

运营指标：

- token cost per task；
- tool cost per task；
- p95 task latency；
- failed run recovery rate；
- queue wait；
- model/tool budget adherence。
- backtest runtime and queue wait；
- paper trading monitor freshness。

## 11. 非目标

第一阶段不承诺：

- 自动给出确定买卖建议；
- 自动替代投资委员会；
- 自动替代合规、审计签字或客户责任人；
- 实时交易信号；
- 高频量化执行；
- 真实资金自动交易；
- 无人工批准的自动回测 / 自动模拟交易升级；
- 把回测或 paper trading 结果直接包装成外部投资建议；
- 无人工审阅的客户正式报告；
- 用社媒/弱信号直接形成核心投资结论。

## 12. 后续需拆技术文档

本文之后至少需要拆出：

1. `TECH`：B 端工作台页面和后端 API contract。
2. `TECH`：WorkpaperPack / DeliverablePlan / Artifact schema。
3. `TECH`：Data Room ingestion、OCR、table parser、user-provided evidence boundary。
4. `TECH`：Deliverable Composer 工具权限和文档/PPT/Excel/PDF 渲染。
5. `TECH`：协作型 multi-agent graph、agent communication、LeadReview、human-in-the-loop。
6. `TECH`：watchlist / monitoring / event trigger pipeline。
7. `TECH`：Research-to-Quant Lab 的 FactorHypothesis / FeatureSpec / LabelSpec / UniverseSpec / BacktestPlan / PaperTradingRun / FactorCard schema。
8. `TECH`：point-in-time dataset builder、leakage guard、回测引擎、risk attribution 和 paper trading monitor。
9. `EVAL`：B 端产品验收 eval，覆盖底稿质量、交付物质量、证据追溯、协作行为、因子验证、回测可复现和成本。

## 13. 当前开放问题

1. B 端第一批用户应优先选券商/买方/咨询/企业战略中的哪一类？
2. 第一版默认交付物是 Word memo、PPT deck 还是 dashboard brief？
3. Human review 是轻批注模式，还是完整审批流？
4. 用户上传私有材料和公开数据证据冲突时，默认如何展示？
5. Workpaper 模板是否按任务类型内置，还是允许机构自定义？
6. Multi-agent 协作应该以 Research Lead 为中心，还是以 shared workpaper event bus 为中心？
7. Watchlist alert 是先做每日 digest，还是做实时/准实时事件流？
8. Research-to-Quant Lab 第一版是否只允许 manual / assisted mode，还是开放 auto candidate mode？
9. 回测引擎第一版使用内部 deterministic vectorized runner，还是直接接入外部专业 backtest engine？
10. Paper trading monitor 是否只做日频/周频模拟组合，还是支持事件驱动模拟？
