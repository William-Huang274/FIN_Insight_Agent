# 181 v0.2 Research Agent Platform Roadmap

## 背景

v0.1 已经证明了一个核心方向：把开放式投研问题转成可审计的证据链，而不是把财报文件直接丢给模型自由生成。当前主链路已经覆盖 SEC 10-K、最新 10-Q、8-K 业绩新闻稿、离线市场快照、Exact-Value Ledger、证据覆盖检查、二次检索、规则校验、会话状态和 Workbench 初版入口。

但如果项目继续停留在“几家公司 + 命令行 + 单条 DAG”的形态，外部观察者仍可能把它理解成一个增强版 RAG demo。下一阶段的目标应从“跑通 SEC Agent”升级为“构建可扩展的证据约束型投研 Agent 工作台”。

本文件先编排 v0.2 的自然阶段。这里的阶段不是严格串行的瀑布流程，而是几条互相支撑的工程主线：某些工作可以并行推进，某些能力必须等上游合同稳定后再接入。

## v0.2 目标

把 FinSight-Agent 从单一 SEC/市场快照问答链路升级为面向真实投研问题的 Agent 平台：

- 能从一个公司自动展开到产业链、竞争格局、客户/供应商、替代品和下游资本开支信号。
- 能让模型参与研究计划、证据需求和二次检索判断，但每一步都受工具合同、证据覆盖和规则校验约束。
- 能通过标准化工具接口被 CLI、Workbench、LangGraph 节点、未来 MCP client 或其他 agent 复用。
- 能在公司数、行业数、数据源和多轮会话增加后，仍控制 token、延迟、上下文质量和成本。
- 能把外网搜索作为有来源、有时间戳、有边界的证据层，而不是让模型凭记忆或自由浏览写结论。

## 设计原则

1. 产品问题优先于架构名词。
   - Multi-agent、MCP、外网搜索和上下文压缩都必须服务于真实投研工作流，不作为孤立功能堆叠。

2. 模型负责研究判断，程序负责证据边界。
   - 模型可以规划、解释、反思和请求补查，但不能绕过 source tier、period role、as_of_date、ledger、coverage 和 gates。

3. 所有新信息源都必须进入统一证据模型。
   - 无论是 SEC filing、8-K、市场快照、新闻、供应链图谱还是行业数据，都必须记录来源、时间、适用边界和可否支持某类 claim。

4. Token 和延迟是产品能力，不是后期优化。
   - 上下文压缩、缓存、调用预算、模型选择、候选预算和阶段耗时必须从 v0.2 开始成为可观测指标。

5. 评测先行但不阻塞探索。
   - 每条新增能力都要有小型真实用例和回归检查；但不要求所有能力等完整评测体系建完才开始试点。

## 阶段编排

阶段 A/B 已经具备单独执行价值。具体公司范围、数据可得性、投研 skill、planner 合同、关系图和 eval 落地计划见 `182_research_ab_standalone_scope_and_model_contract.md`；跨主流行业扩容、下载处理流程和 20-F/6-K/40-F 等新披露格式接入计划见 `183_cross_industry_data_expansion_and_source_format_plan.md`。本文件保留 v0.2 总路线图，不继续展开 A/B 的执行细节。

### 阶段 A：重新定义投研任务和可验证用例

这一阶段回答“产品到底要解决什么问题”。它可以马上开始，并与后续所有阶段并行更新。

参考口径：

- [SEC MD&A guidance](https://www.sec.gov/rules-regulations/2003/12/commission-guidance-regarding-managements-discussion-analysis-financial-condition-results-operations) 强调经营结果、流动性、资本资源、已知趋势、需求、承诺、事件和不确定性，这适合作为财报侧证据框架。
- [CFA Institute equity valuation framework](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/equity-valuation-applications-and-processes) 强调理解业务、预测经营表现、选择估值方法、形成结论和写出可审阅研究报告，这适合作为投研 memo 的问题框架。

核心动作：

- 把投研问题拆成任务族：
  - 单公司基本面变化。
  - 横向 peer 对比。
  - 产业链交叉验证。
  - 管理层叙事与市场反应分歧。
  - 估值与基本面分歧。
  - 证据不足时的补查和边界说明。
- 补充真实研报问题维度：
  - 投资主线：这家公司当前最重要的投资争议是什么，是增长持续性、利润率、估值重估、周期反转、竞争格局，还是现金流质量？
  - 预期差：市场当前可能已经定价了什么，SEC/8-K/市场快照中哪些证据支持或反驳这种预期？
  - 商业模式：收入是来自产品销售、订阅、交易量、资产规模、贷款余额、资本开支周期、广告预算、药品放量、能源价格，还是其他行业特定驱动？
  - 关键驱动因素：收入增长来自量、价、产品结构、客户扩张、区域扩张、并购、会计口径，还是一次性因素？
  - 分部与口径：公司是否按业务线、地区、客户类型或产品族披露，当前指标是年度、季度、年初至今还是过去十二个月口径？
  - 利润质量：毛利率、经营利润率、研发投入、销售费用、一次性调整、非 GAAP 指标和现金流之间是否一致？
  - 现金流与资本配置：经营现金流、资本开支、回购、股息、债务、递延收入、库存和应收账款是否支持管理层叙事？
  - 资产负债表风险：库存、应收账款、递延收入、商誉、债务期限、利率敏感性和流动性是否可能改变利润表读法？
  - 周期位置：当前处在上行、下行、去库存、补库存、资本开支扩张还是消化期？
  - 管理层可信度：管理层在 8-K/10-Q/10-K 中的叙事与已披露财务事实是否一致，是否存在口径变化或过度乐观？
  - 催化剂：接下来 1-4 个季度哪些事件会验证或推翻判断，例如财报、指引、客户 capex、产品发布、监管、订单、库存变化。
  - 反证条件：什么证据出现时必须降低结论强度或改变判断，而不是继续用原有叙事解释？
  - 估值语境：估值高低是由增长、利润率、风险下降、现金流改善、行业 beta、流动性还是情绪驱动？
  - 场景分析：如果核心假设上调或下调，收入、利润率、现金流、估值倍数和市场反应中哪个变量最敏感？
  - 行业差异：银行、保险、能源、制药、消费、软件、半导体、工业和公用事业不能套同一套指标，planner 必须识别行业特定指标。
  - 证据边界：哪些判断只能由 SEC filing 支持，哪些只能由管理层口径支持，哪些只能由市场快照或外部新闻作为解释候选？
- 把上述问题转成 planner 合同，而不是只写进最终 prompt：
  - `analysis_intent`：基本面变化、横向比较、估值分歧、产业链验证、风险排查、事件解释。
  - `investment_question_type`：增长、利润率、现金流、资本配置、周期、竞争、估值、催化剂、反证。
  - `claim_types`：财务事实、管理层解释、市场反应、估值语境、产业链假设、风险判断。
  - `evidence_requirement_plan`：每类 claim 需要哪些公司、年份、披露文件、指标族、期间口径、市场快照或外部证据。
  - `confidence_policy`：证据不足时先触发二次检索；补查后仍不足时，输出“当前证据能支持什么”和“还缺什么”，而不是空泛拒答。
- 为每类任务定义标准输出框架、证据需求和失败模式。
- 设计 v0.2 代表性 case：
  - NVDA AI 产业链验证。
  - AMD 追赶逻辑验证。
  - 云厂商 capex 与半导体/设备企业收入联动。
  - 软件公司从增长到盈利质量的切换，例如收入增速、递延收入、RPO、销售效率和现金流。
  - 银行信贷质量与利率周期，例如净息差、存款成本、拨备、净核销、不良贷款和资本充足率。
  - 制药管线与商业化，例如核心产品放量、专利悬崖、研发投入、并购、监管里程碑和利润率。
  - 能源周期与资本纪律，例如油气价格、产量、资本开支、自由现金流、回购和储量。
  - 消费公司需求弹性，例如同店销售、客单价、销量、促销、库存和毛利率。
- 为每个 case 追加“研究假设 -> 证据需求 -> 反证条件 -> 输出边界”四段合同：
  - 研究假设：本轮要验证的投资问题，不是泛泛总结公司。
  - 证据需求：必须覆盖的公司、年份、披露文件、管理层材料、市场快照和产业链节点。
  - 反证条件：如果证据显示相反方向，模型必须降级或改写结论。
  - 输出边界：哪些内容可以总结，哪些只能写成待补查，哪些不能输出。

交付物：

- `v0.2_research_task_taxonomy`
- `v0.2_eval_case_plan`
- 每类任务的证据需求模板和验收标准。
- planner 输出 schema 中新增投研问题类型、证据需求计划、置信度策略和反证要求。

验收标准：

- 能明确说明每个 case 为什么需要 Agent，而不是把文件上传到网页端。
- 每个 case 都能映射到至少一个真实链路能力：规划、检索、ledger、二次补查、上下文、校验或外部证据边界。
- 每个 memo 至少能覆盖“结论依据、核心假设、证据强度、反证条件、来源边界”中的大部分内容；缺项必须能被 coverage 或 gates 识别。

### 阶段 B：产业链与研究范围生成

这一阶段解决“不要孤立研究一家公司”。它应尽早启动，因为它直接决定项目是否像真实投研工具。

核心动作：

- 建立 `company_relationship_graph`：
  - 竞争对手。
  - 客户和下游买方。
  - 供应商。
  - 替代品或替代技术。
  - 行业链条位置。
  - 关键指标映射，例如 capex、RPO、库存、数据中心收入、HBM、晶圆代工、网络设备。
- 补充产业链研究问题维度：
  - 公司处在价值链哪一层：上游材料、设备、零部件、核心平台、集成商、渠道、下游客户、应用层、终端需求，还是金融/能源/医疗等行业里的资产端或负债端？
  - 需求从哪里来：终端需求、企业 IT 预算、云厂商 capex、政府/军工/医疗/金融等垂直行业需求是否能交叉验证？
  - 价值链谁受益：收入和利润在芯片、设备、代工、封装、内存、服务器、网络、云服务、应用软件之间如何分配？
  - 瓶颈在哪里：产能、先进封装、HBM、晶圆、设备交期、客户预算、能耗、数据中心建设周期，哪个环节最可能约束增长？
  - 传导是否滞后：上游设备订单、晶圆代工收入、HBM 出货、服务器 OEM 收入、云 capex 和芯片公司收入之间的时间差如何处理？
  - 客户集中度：主要客户是否少数集中，某一客户 capex 或库存变化会不会显著影响供应商收入？
  - 替代风险：客户自研芯片、开源软件、价格竞争、替代架构、监管限制会不会改变价值链分配？
  - 库存和订单：库存、backlog、RPO、递延收入、采购承诺、供应协议能否验证管理层对需求的说法？
  - 利润池迁移：行业增长时，利润是在上游卖铲子公司、平台公司、云厂商、应用公司还是终端客户侧沉淀？
  - 同步与背离：如果上游公司说需求强，但下游 capex 放缓，系统应把它识别为证据冲突而不是直接平均。
  - 地缘和监管：出口管制、供应链地区限制、客户地区结构变化会如何影响可服务市场和收入确认？
  - 价格与产能传导：上游涨价、紧缺或扩产是否会传导到下游毛利率，还是被长期合同、采购承诺或竞争吸收？
  - 二阶受益者：除了直接供应商和客户，是否还有电力、散热、光模块、EDA、测试、物流、金融服务等间接受益或受损环节？
  - 非线性关系：一个公司可能同时是客户、供应商、竞争者和替代风险来源，关系图不能只允许单一标签。
- 建立 `Research Universe Builder`：
  - 用户输入 `NVDA`，系统能展开 GPU、HBM、晶圆代工、先进封装、服务器 OEM、云厂商、网络设备、EDA、半导体设备等相关公司。
  - 用户输入“云 capex”，系统能展开 MSFT、AMZN、GOOGL、META、ORCL、NVDA、AVGO、AMD、TSM、ASML 等研究范围。
  - 用户输入“药品商业化”，系统能展开原研药企、仿制药竞争、医保/支付方、渠道、CDMO、关键适应症和监管事件。
  - 用户输入“银行信贷周期”，系统能展开大型银行、区域银行、信用卡、商业地产、利率敏感资产和宏观信用指标。
  - 用户输入“能源资本纪律”，系统能展开上游油气、油服、管道、炼化、公用事业、设备和大宗商品价格。
- 让 Universe Builder 输出可审计的关系类型，而不是只输出 ticker 列表：
  - `direct_competitor`：直接竞争者，例如 AMD、AVGO 的部分 AI ASIC/网络业务。
  - `customer_or_downstream_buyer`：客户或下游买方，例如 hyperscaler、服务器厂商、企业软件客户。
  - `supplier_or_capacity_provider`：供应商或产能提供方，例如代工、封装、HBM、设备公司。
  - `complementary_infrastructure`：互补基础设施，例如网络、光模块、数据中心电力和散热。
  - `substitution_or_internalization_risk`：替代或自研风险，例如云厂商自研芯片。
  - `macro_or_regulatory_exposure`：宏观、监管、地缘暴露。
- 为每条关系记录证据要求：
  - 关系来源：公司披露、10-K 客户/供应商描述、8-K 管理层口径、外部新闻、行业数据或人工 seed。
  - 关系强度：high / medium / low。
  - 适用问题：需求验证、供给瓶颈、竞争替代、估值分歧、风险解释。
  - 时间戳：关系是否可能过期。
  - 不可支持的 claim：例如不能仅凭供应链关系推断收入规模。
- 扩展关系图 schema，让它能服务检索和二次补查：
  - `relation_type`：竞争、客户、供应商、替代、互补、宏观暴露、监管暴露。
  - `direction`：谁影响谁，不能只记录“相关”。
  - `financial_link_type`：收入、成本、资本开支、库存、订单、利润率、估值、风险。
  - `time_scope`：当前季度、未来 1-4 季度、年度、长期结构性关系。
  - `metrics_to_check`：需要查的指标族，例如 capex、RPO、库存、订单、毛利率、经营现金流。
  - `evidence_source`：SEC、8-K、市场快照、外部新闻、行业数据、人工 seed。
  - `confidence` 和 `caveats`：关系强度、证据限制和不能支持的断言。
- 将 relationship graph 接入 planner 的 evidence requirement plan，但不让它替代 SEC/market 证据。
- 让 planner 在展开研究范围时输出“为什么纳入”和“为什么需要查”，例如：
  - 纳入 HBM 供应商不是因为“AI 相关”，而是为了验证供应瓶颈是否约束 GPU 出货和毛利率。
  - 纳入云厂商不是因为“大客户相关”，而是为了验证 capex 是否能支撑加速计算需求。
  - 纳入网络和光模块公司不是为了凑行业名单，而是为了验证数据中心扩建是否从 GPU 扩散到互连和基础设施。
  - 纳入替代芯片或自研芯片公司，是为了验证估值中隐含的竞争风险。

交付物：

- 产业链关系 schema。
- 初版 NVDA/AI infrastructure universe。
- Universe expansion 的可解释日志：为什么纳入某公司，为什么排除某公司。
- 2-3 个非 AI 行业 universe pilot，避免关系图只适配半导体链条。

验收标准：

- 用户问 NVDA 时，系统能自动提出上下游和客户侧交叉验证路径。
- 输出中能区分“直接财报证据”“管理层口径”“市场快照”“产业链关联假设”。
- Universe expansion 必须说明纳入逻辑和证据边界，不能只返回“相关公司名单”。
- 如果产业链证据与公司自身财报证据冲突，系统必须保留冲突并触发补查或降级结论。
- 如果关系图证据不足，系统应把关系标记为待验证假设，并优先触发可用证据源补查；只有现有源无法覆盖时，才转成外部搜索或用户数据需求。

### 阶段 C：LangGraph 原生多角色编排

这一阶段不是为了贴 multi-agent 标签，而是把当前脚本控制的业务节点迁移成真正可检查、可恢复、可分支的 graph 状态流。

核心动作：

- 将当前主链路中的职责拆成清晰角色：
  - Research Planner：生成研究计划和证据需求。
  - Evidence Operator：执行 SEC、8-K、market、relationship graph、未来 web search 工具。
  - Coverage / Reflection：判断证据是否足够，是否需要二次检索或追问。
  - Verifier：检查 claim、数值、source tier、period role、market as_of_date。
  - Memo Writer：只在证据和判断框架内写投研备忘录。
- 将规则判断从“业务先验替代模型”改成“节点输出校验和可靠性约束”。
- 让二次检索成为 graph 内的条件分支：
  - 证据足够：直接进入 synthesis。
  - 证据不足但可补查：模型输出补查需求，工具执行补查。
  - 补查后仍不足：输出当前证据能支持的判断，并明确缺口。
- 继续推进 checkpoint-first resume：
  - 从 artifact resume 逐步迁移到 LangGraph checkpoint。
  - Workbench 能展示每个节点状态、artifact digest、可恢复边界和失败原因。

交付物：

- Native graph 状态 schema。
- 多角色节点合同。
- 条件分支和二次检索闭环。
- Workbench 中的 graph run trace / checkpoint view。

验收标准：

- 不是 LangGraph 外壳包一个大脚本，而是业务状态通过 graph state 流动。
- 每个节点可以单独检查输入、输出、artifact refs 和失败边界。
- 至少一个真实 full-chain case 能触发二次检索并成功恢复。

### 阶段 D：工具层标准化与 MCP 接入

MCP 不应抢在工具合同之前强行做。它适合在核心工具边界稳定后，把能力开放给 Workbench、CLI、其他 agent 或外部 client。

核心动作：

- 先定义稳定工具接口：
  - `plan_research_scope`
  - `search_filings`
  - `query_exact_value_ledger`
  - `get_market_snapshot`
  - `inspect_evidence_coverage`
  - `request_second_pass_retrieval`
  - `inspect_or_resume_run`
  - `expand_company_universe`
  - `search_external_web`
- 将现有 Python 工具封装成统一 tool registry。
- 再提供 MCP server：
  - 本地模式优先。
  - 不暴露密钥。
  - 私有数据路径通过配置传入。
  - 返回结构化 observation，而不是长文本拼接。
- Workbench 调用同一套工具接口，避免 CLI、UI、LangGraph、MCP 各自维护一套逻辑。

交付物：

- Tool registry。
- MCP server 初版。
- MCP smoke：至少用一个外部 client 或本地 MCP 调用完成检索、ledger 和 coverage 检查。

验收标准：

- MCP 调用和主链路调用拿到同一类结构化结果。
- 工具输出可进入 Evidence Coverage Matrix 和后续 gates。
- 没有把 MCP 做成另一个绕过主链路的接口。

### 阶段 E：上下文压缩、成本控制和缓存

这一阶段应贯穿 B/C/D，而不是等所有能力都做完再优化。公司、行业、数据源扩容后，token 和延迟会成为第一瓶颈。

核心动作：

- 建立 Context Budget：
  - planner budget。
  - retrieval evidence budget。
  - synthesis budget。
  - session memory budget。
  - external web budget。
- 建立 Context Compressor：
  - 把 evidence rows 压缩成带 citation 的 evidence brief。
  - 保留 ticker、year、filing type、source tier、period role、metric refs、evidence refs。
  - 禁止压缩器改写精确数值。
- 建立分层记忆：
  - run-local evidence。
  - session short-term memory。
  - company memory。
  - industry/universe memory。
  - user preference memory。
- 增加 token/cost telemetry：
  - 每次模型调用的 input/output tokens。
  - 每个节点的 token budget 使用。
  - cache hit rate。
  - 被丢弃或压缩的证据行。
  - 估算成本和延迟。
- 缓存：
  - planner cache。
  - retrieval cache。
  - ledger cache。
  - market snapshot cache。
  - compressed evidence cache。

交付物：

- Context Compressor v1。
- Token/cost report。
- Workbench cost/latency panel。
- 压缩前后质量对比 eval。

验收标准：

- 在不明显损害 evidence coverage 和 answer quality 的前提下，降低 synthesis 输入 token。
- 用户多轮追问时能复用上一轮证据和压缩摘要，而不是重跑所有阶段。
- 每次 run 能解释 token 花在哪里，为什么需要或不需要更大模型。

### 阶段 F：受控外网搜索作为新证据层

外网搜索应该接，但不能让模型自由上网写金融结论。它必须作为 `external_web_snapshot` source tier 进入证据系统。

核心动作：

- 定义 web source contract：
  - query。
  - provider。
  - url。
  - title。
  - publisher。
  - published_at。
  - fetched_at。
  - as_of_date。
  - source quality。
  - allowed_claim_types。
- 定义触发条件：
  - 用户显式问最新新闻、供应链事件、监管、订单、产品发布。
  - Coverage/Reflection 判断 SEC/8-K/market 不能回答近期事件解释。
  - 产业链图谱需要外部事件验证。
- 接入 web evidence gates：
  - 外部新闻不能覆盖 SEC reported financial facts。
  - 新闻只能作为解释候选或事件证据。
  - 所有 current/latest claim 必须带 as_of/fetched 时间。
- Workbench 展示外部来源边界。

交付物：

- Web snapshot schema。
- Web search tool。
- External evidence pack。
- Web source gate。

验收标准：

- 能回答“最近三个月 NVDA 供应链有什么变化会影响未来业绩”这类问题。
- 输出能清楚区分 SEC、公司材料、市场快照和外部新闻。
- 不能把新闻、博客或模型记忆当作财务事实来源。

### 阶段 G：评测、可观测性和产品化收口

这一阶段不是最后才做，而是每个阶段都要向它交付可测试的证据。

核心动作：

- 扩展 eval：
  - 产业链交叉验证 case。
  - 多 agent / reflection case。
  - MCP tool contract case。
  - 上下文压缩质量 case。
  - 外网搜索边界 case。
  - 多轮 session memory case。
- 建立运行报告：
  - stage timing。
  - token cost。
  - source coverage。
  - checkpoint/resume status。
  - candidate/rerank budget。
  - second-pass trigger reason。
- Workbench 产品化：
  - 数据源配置。
  - session/thread 管理。
  - run trace。
  - evidence viewer。
  - cost/latency dashboard。
  - source boundary viewer。
- 文档叙事同步升级：
  - 从“SEC Agent”升级为“证据约束型投研 Agent 工作台”。
  - 强调它不是一个 API wrapper，而是有规划、工具、证据、记忆、恢复、校验和成本控制的研究系统。

交付物：

- v0.2 benchmark suite。
- readiness check。
- demo runbook。
- public docs 更新。

验收标准：

- 至少 3 个真实投研场景能从 prompt 到 memo 全链路跑通。
- 每个输出能解释用了哪些证据、哪些来源缺失、token 和耗时在哪里。
- Workbench 能让用户不用命令行完成基本配置、运行、检查和恢复。

## 阶段之间的关系

这些阶段的自然依赖关系如下：

```text
阶段 A：任务定义与评测框架
  -> 持续约束所有后续阶段

阶段 B：产业链与研究范围生成
  -> 提供更真实的问题范围
  -> 推动 retrieval、context、eval 扩容

阶段 C：LangGraph 原生多角色编排
  -> 承载二次检索、reflection、resume 和 multi-agent 形态

阶段 D：工具层标准化与 MCP
  -> 在核心工具接口稳定后开放给 UI / CLI / MCP client / 其他 agent

阶段 E：上下文压缩与成本控制
  -> 横向贯穿 B/C/D/F
  -> 防止数据源和公司扩容后 token/latency 失控

阶段 F：受控外网搜索
  -> 在 source tier / gates / context budget 有基础后接入

阶段 G：评测与产品化
  -> 每个阶段都要回流到 eval、observability 和 Workbench
```

## 建议的近期推进顺序

不是“先完整做完某阶段再进入下一阶段”，而是按最能提升项目可信度的薄切片推进：

1. v0.2-alpha：定义 3-5 个真实投研 case，并先做 NVDA 产业链 universe pilot。
2. v0.2-alpha 同步：把当前 LangGraph native resume 继续推进到 checkpoint-first session/thread 语义。
3. v0.2-alpha 同步：加 token/cost telemetry 的最小闭环，先记录不压缩。
4. v0.2-beta：把稳定工具抽成 tool registry，再接 MCP server 的最小可用版本。
5. v0.2-beta：做 Context Compressor v1，让 evidence brief 进入 synthesis。
6. v0.2-beta：接入受控 web snapshot source tier，优先服务供应链/近期事件解释。
7. v0.2-closeout：用 Workbench 跑多场景 eval，整理成公开演示与技术文档。

## 当前不做的事

- 不做没有业务边界的“角色扮演式 multi-agent”。
- 不让模型自由浏览外网并把结果直接写进财务结论。
- 不把 MCP 做成绕过主链路的第二套接口。
- 不用上下文压缩替代证据覆盖检查。
- 不为了看起来复杂而提前引入多服务部署。

## 下一步讨论入口

后续可以逐阶段过具体方案。建议先从两个问题开始：

1. v0.2 的 3-5 个代表性投研 case 应该怎么选，才能同时覆盖产业链、多源证据、上下文、多轮追问和 token 成本？
2. NVDA 产业链 universe pilot 的公司范围、关系类型和证据源应该如何定义，才能避免变成手写名单或行业百科？
