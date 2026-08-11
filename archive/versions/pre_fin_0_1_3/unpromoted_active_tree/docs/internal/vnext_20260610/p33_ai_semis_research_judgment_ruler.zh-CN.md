# P33 AI/Semis Gold Case Research Judgment Ruler

日期：2026-07-06

## 1. 文档定位

本文档是 P33 AI/Semis gold workpaper 的研究质量尺子，不是普通工作日志，也不是 memo 模板。

它解决一个具体问题：后续不能只判断 agent 节点是否跑通、字段是否存在、gate 是否为 pass，而要判断每个节点是否真的逼近一个金融研究员应该形成的分析链条。

使用方式：

1. Research Lead、specialist、JudgmentCard、MemoLogicPlan、Memo Writer、Verifier 和 Workbench dogfood 都必须用本文档作为质量参照。
2. 如果节点输出通过工程 gate 但没有回答本文档的关键问题，应标为 `research_quality_gap`，不能直接进入下一阶段 closeout。
3. 本文档中的公司、产品和行业事实不是最终事实库。具体事实必须由 source route、parser、evidence row、graph edge 或 typed gap 支撑。
4. 本文档允许后续根据真实 source / parser / run artifact 更新，但必须记录 supersession 原因。

## 2. Gold Case 核心问题

当前 AI/Semis gold case 不是泛泛回答“AI 需求强不强”，而是要回答：

> AI 基建需求是否真实转化为 accelerator、server OEM、foundry / packaging、HBM、semicap 公司的高质量收入和利润？哪些链条已经有证据，哪些只是 demand proxy，哪些存在 margin dilution、supply bottleneck、capex digestion、export control 或 price-in 风险？

初始覆盖范围：

- Accelerator / platform：NVDA、AMD、GOOGL TPU。
- Server OEM / AI server：DELL，必要时对照 HPE、SMCI、ODM 线索。
- Hyperscaler demand pool：MSFT、AMZN、GOOGL、META。
- Foundry / packaging / HBM / semicap read-through：TSM、ASML、AMAT、LRCX、KLAC、HBM 供应链。

## 3. 研究员应先形成的分析链条

一个合格的 buyside-style workpaper 不应该把证据并排罗列，而应该围绕以下链条组织判断：

```text
AI workload / model scaling / cloud capex
 -> accelerator product capability and supply allocation
 -> cloud/OEM/customer deployment and order/backlog signal
 -> server OEM revenue quality and gross-margin bridge
 -> foundry / packaging / HBM / semicap capacity and cycle read-through
 -> market expectation / price-in / valuation / positioning
 -> counter-thesis and what would change the view
```

这条链条对应的核心判断不是单点结论，而是几组可被证据约束的判断：

1. AI capex 是真实 demand pool，还是已经进入 digestion / over-ordering 风险。
2. NVDA 的产品和生态优势是否仍构成 supply bottleneck / pricing power / customer pull。
3. AMD / TPU 的替代威胁是价格、性能、供给、软件生态还是客户自研策略层面的威胁。
4. DELL AI server 是高质量利润增量，还是 GPU pass-through 造成的低毛利放量。
5. Hyperscaler capex 能不能传导到 DELL / SMCI / ODM / NVDA / semicap，而不是只停留在 demand pool。
6. ASML / AMAT / LRCX / KLAC 受益的是 AI 先进制程、HBM、packaging、memory/foundry/logical cycle，还是 broader wafer fab equipment cycle。
7. 当前市场价格是否已经反映这些利好，主要风险来自基本面、估值、资金面、政策还是供应链。

## 4. 必需研究 Lane

### 4.1 Product / Architecture

必须回答：

- 产品是什么：GPU、accelerator、AI server、TPU、networking、rack-scale system、semicap equipment。
- 规格和架构如何：compute、memory capacity、memory bandwidth、interconnect、power、rack/system architecture、software ecosystem。
- 代际变化如何：上一代到下一代的性能、功耗、成本、系统形态变化。
- 与竞品/替代品相比强在哪里、弱在哪里。

强证据：

- 官方 product page、datasheet、whitepaper、developer docs、cloud instance docs、MLPerf 等可追溯 benchmark。

中等证据：

- 官方 presentation、validated partner/OEM configuration、credible industry benchmark summary。

Proxy：

- 新闻、渠道报价、开发者生态活跃度、招聘、专利/论文、供应链传闻。

不能外推：

- 产品规格和 benchmark 不能直接推出 revenue、share、shipment、ASP 或 gross margin。

失败条件：

- 只因为没有 SKU revenue / shipment 就说产品层无法判断。
- 只写“NVDA/AMD/GOOGL 都在 AI 芯片”，没有规格、架构、生态、部署或替代关系。

### 4.2 Customer Deployment / Adoption

必须回答：

- 谁部署、采用、配置或销售了哪些产品。
- 部署是云实例、企业客户、OEM 配置、官方 case、公开订单还是渠道上架。
- 这个部署信号能支持 demand validation，还是只能做 context。

强证据：

- issuer / customer / partner 官方公告，cloud instance catalog，OEM official configuration，合同或订单披露。

中等证据：

- 官方案例、官方 blog、公开 tender / award、监管或采购数据库。

Proxy：

- 新闻、渠道上架、review、招聘、论坛或社媒。低权重使用。

不能外推：

- deployment / adoption signal 不能直接推出 revenue、margin、share 或 backlog，除非披露了金额、数量、合同期和产品映射。

失败条件：

- 把 hyperscaler capex 当成 DELL/NVDA 确认订单。
- 把 relationship graph same-family 或 peer group 当作客户部署证据。

### 4.3 Supply Chain / Bottleneck / Read-through

必须回答：

- 谁是需求方、谁是供应方、谁是瓶颈。
- 传导链是 GPU -> server OEM，还是 cloud capex -> data center supply chain，还是 HBM / CoWoS / foundry -> GPU supply。
- 半导体设备公司受益的具体环节是什么。

强证据：

- 官方供应/客户关系、合同、capacity commentary、orders/bookings/backlog、公开客户集中度。

中等证据：

- 产业链公司一致口径的 IR / earnings commentary、监管文件、官方技术/产能披露。

Proxy：

- industry snapshot、同业周期、设备订单方向、供应链新闻。

不能外推：

- peer group 只能支持 scope，不是主证据。
- supply-chain read-through 不能直接变成单家公司收入精确增长。

失败条件：

- 只写 ASML/AMAT/LRCX/KLAC 同属 semicap。
- 没有区分 EUV、process control、deposition/etch、services、memory/foundry/logic cycle。

### 4.4 Financial Quality / Fundamental Bridge

必须回答：

- AI server / data center / accelerator 暴露如何进入收入。
- 是 revenue tailwind，还是 margin drag。
- gross margin、operating margin、working capital、inventory、backlog conversion、capex、cash flow 如何变化。
- 同业和上下游是否支持该财务判断。

强证据：

- 公司披露的 segment revenue、gross margin、operating income、backlog/order、capex、cash flow、working capital、management commentary。

中等证据：

- segment/业务线口径、客户/产品组合 commentary、可比公司披露。

Proxy：

- demand pool、客户部署、供应链关系、行业快照。

不能外推：

- hyperscaler capex 不能直接证明 DELL margin 改善。
- AI server revenue 增长不能自动说明质量高；必须看 gross margin、GPU pass-through、backlog conversion 和 cash conversion。

失败条件：

- memo 只写 DELL 受益于 AI server demand，但没有回答是否改善利润质量。
- 上游已有 DELL margin / operating income / working-capital rows，memo 仍说财务数据缺失。

### 4.5 Market Expectation / Price-in / Capital Feedback

必须回答：

- 市场是否已经 price in。
- 估值、成交、short interest、holder/flow、credit/corporate action 是否支持或反驳基本面判断。
- 这些信号是市场预期还是公司基本面。

强证据：

- 公司资本动作、债务/信用、13F/insider、流动性、估值、股价反应、事件窗口。

中等证据：

- lagged holder rows、行业 ETF / peer price reaction、market snapshot。

Proxy：

- 新闻热度、社交媒体、搜索趋势。

不能外推：

- 市场/持仓/衍生品信号不能冒充基本面事实或投资建议。

失败条件：

- 完全不讨论 price-in。
- 把市场 proxy 写成公司经营事实。

### 4.6 Risk / Counter-thesis

必须覆盖：

- Capex digestion / overbuild。
- Export control / China exposure。
- Customer concentration。
- Margin dilution。
- Supply bottleneck。
- Product delay / deployment delay。
- Pricing pressure。
- Substitution risk：AMD / TPU / ASIC / in-house accelerator。
- Evidence missing but theoretically retrievable。

失败条件：

- 风险只写“数据不足，需要继续观察”。
- counter-thesis 没有对应证据、机制或触发条件。

## 5. 节点级研究质量尺子

### 5.1 Research Lead

必须产出：

- `initial_view`：有边界的初始判断，不是任务列表。
- `thesis_path`：从产品、客户、供应链、财务、市场到反证的链条。
- `required_item_plan`：每个必答项要谁回答、需要什么证据。
- `evidence_role_plan`：强事实、中等证据、proxy、typed gap 的边界。
- `writer_order`：最终 workpaper 如何组织。
- `repair_plan`：哪些缺口理论上能找，哪些是 commercial / bounded。

Research Lead 失败条件：

- 只派发 specialist，没有提出“AI server 是否改善 DELL 利润质量”等核心问题。
- 把 demand pool 当成公司订单。
- 没有把 product architecture、customer deployment、supply-chain 和 financial bridge 连接起来。

### 5.2 Evidence Operators / Fusion

必须证明：

- 每条 evidence row 能追到 required item。
- 每条 row 有 authority、claim scope、cannot infer。
- product / deployment / supply-chain / financial / market rows 分层明确。
- 找到文件但抽不到数字时，必须标 parser_gap 并说明抽取失败点。

失败条件：

- `missing_requirement_count=0`，但关键 lane 只有 context/proxy。
- `product_runtime_fact_count=0` 仍直接让产品分析进入 gold closeout。
- ASML/TSM FPI / local disclosure route 未跑就写 public source absent。

### 5.3 Coverage Reflection

必须做两类判断：

- Coverage：有没有覆盖必答项。
- Depth：证据深度是否足以支撑研究判断。

失败条件：

- 只因为每个 required item 有 row 就通过。
- 不区分 exact fact、company-disclosed context、relationship hypothesis、industry proxy。

### 5.4 Specialist

每个 specialist 必须输出 judgment candidate，而不是证据摘要。

统一字段：

```text
judgment
required_item_answered
business_mechanism
evidence_refs
graph_edge_refs
product_or_financial_bridge
confidence
counter_read
cannot_infer
what_would_change_view
```

Specialist 失败条件：

- 输出“找到了哪些材料”，但没有形成判断。
- product specialist 不比较架构 / 规格 / 部署 / 替代。
- fundamental specialist 不回答收入质量和 margin bridge。
- industry specialist 只讲 peer group，不讲 read-through。
- risk specialist 只写泛化风险。

### 5.5 Aggregate / JudgmentState

必须完成：

- 把 specialist 判断合并成 thesis path。
- 显示支持、反证、冲突和 gap。
- 把产品、财务、客户、供应链、市场映射到同一个判断链条。

失败条件：

- Claim/Judgment 数量很多，但没有主判断。
- relationship graph 只以背景存在，没有投资含义。
- unsupported claims 被隐藏，而不是成为反证或 gap。

### 5.6 MemoLogicPlan / Memo Writer

writer 只能负责表达，不负责重新研究。

必须写成：

- 开头直接给判断。
- 每个维度先给判断，再给证据和边界。
- 解释“为什么这样看”。
- 说明“哪里可能错”。
- 说明“什么会改变判断”。

失败条件：

- 通篇是证据整理。
- 通篇是“数据不足，不能判断”。
- 插入内部字段、机制标签或模板化话术。
- 没有回答用户的核心问题。

## 6. AI/Semis Gold Workpaper 最低通过标准

一个 AI/Semis gold workpaper 至少要回答以下问题：

1. AI capex 是否能支持真实需求池判断？
2. NVDA / AMD / TPU 的产品和架构竞争关系是什么？
3. 客户部署 / cloud instance / OEM 配置是否支持 adoption？
4. DELL AI server 是利润改善还是低毛利放量？
5. GPU supply、HBM、CoWoS、foundry、semicap 的 read-through 链条是否成立？
6. ASML / AMAT / LRCX / KLAC 的受益逻辑分别是什么？
7. 当前市场预期和 price-in 风险是什么？
8. 主要反证和触发条件是什么？
9. 哪些缺口是公开源可继续 repair，哪些是 commercial gap？
10. 哪些判断只能 bounded，哪些可以作为高置信 thesis driver？

如果这些问题没有被回答，不能因为：

- Research Lead pass；
- specialist pass；
- JudgmentCard 数量够；
- MemoLogicPlan validation pass；
- writer 有输出；

就把 P33-3 记为 gold case 通过。

## 7. 后续执行要求

下一步继续 P33-3 时，必须先做以下 no-paid 对照：

1. 用本文档审计 accepted aggregate r7：
   - 哪些 gold questions 已被 JudgmentCards 支撑；
   - 哪些只有 proxy；
   - 哪些完全缺；
   - 哪些是 parser/source route 问题。
2. 用本文档审计 Memo Writer payload preflight：
   - writer 是否真的收到上述判断材料；
   - 是否还只是收到 evidence dump；
   - 56k prompt chars 中有多少是判断材料，多少是低价值上下文。
3. 如果审计发现关键 lane 只有 context/proxy，先补 source route / parser / specialist skill，不直接跑 paid writer。
4. 只有当 `ResearchJudgmentRulerAudit.status=pass_or_bounded_pass` 后，才允许单节点 paid Memo Writer rerun。

## 8. 当前已知风险

- 当前 P33 evidence fusion 曾显示 `product_runtime_fact_count=0`，即产品规格/架构更多是 context/proxy 而非 company-product exact facts。这不能直接挡住所有产品判断，但会限制技术竞争结论的强度。
- 当前 accepted specialist / aggregate 证明已有 JudgmentCards 和 MemoLogicPlan，但还没有证明最终 prose 能变成高质量 analyst workpaper。
- 如果后续只继续优化 writer 表面，而不修产品/财务/部署/供应链的分析桥，输出仍可能像搜索结果总结。
