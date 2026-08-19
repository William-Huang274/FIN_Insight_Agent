# FIN 0.1.3 多角色 Agent 拓扑与 Preview 审计

## 一、这次审计回答什么

这次不再用“Prompt 里写了几个角色”判断 Multi-Agent 是否成立，而是回答五个产品问题：

1. 当前仓库中哪些角色真的是 Agent，哪些只是工具、Evaluator、Harness 组件或标签；
2. 旧 DELL 五单元运行究竟验证了什么，没有验证什么；
3. 一个失败最早属于数据／工具、Harness、Agent 工作模式、模型判断还是 Evaluator；
4. 现有信息源足以激活哪些研究角色，哪些角色必须因数据边界暂不激活；
5. 怎样运行一次真正有独立角色、工具执行、反馈、重规划和终止的 Preview。

机器可读的权威分类见 `configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json`。

## 二、什么才算真正 Agent

真正 Agent 至少同时具备：独立研究目标、独立会话状态、可选择的受限工具、自己的工作底稿、能接收结构化失败反馈，以及在反馈后修改计划或判断的权限。少任何一项，都不能仅凭“调用了模型”或“名字里有 specialist”计为 Agent。

因此，旧五单元准确说是“同一个 Provider 下的五个固定研究节点”，不是五个独立 Agent：

- 五个节点没有独立 `AgentSession`，上下文也不是各自长期维护；
- 没有在执行前分别提出研究意见，再由 Lead 协调；
- `submit_evidence_request` 在模型循环内只登记为 `recorded_not_executed`，不会立即调用 S1；
- Verifier 的失败出现在完整报告之后，没有回到最早的研究角色形成自然修正；
- Writer 是本地确定性拼装器，不是一个负责结构与叙事的独立 Agent；
- Planner 和 Synthesis 都是一次性调用，没有共同维护一个持续的研究计划。

旧五单元仍然有价值：它证明五种研究问题可以在同一 Case 中运行，也暴露了跨单元事实可见性、因果归因和综合冲突。但它不能证明 Multi-Agent 协作、上下文连续性或反思循环。

## 三、五类对象必须彻底分开

### 1. Agent

本次 Preview 激活研究负责人、需求质量、经营表现、价值获取、现金转换、供应链／关系、独立反方和实验性 Writer。每个研究角色都要先给出独立计划意见，执行自己的工具请求，形成工作底稿；Lead 只能协调，不能替专业角色写答案。

### 2. 工具

S1 本地检索、官方来源接入、S2 SQL／NumericFact、reviewed Evidence reader、全案事实存在性目录和确定性 renderer 都是工具。它们负责“找到、读出、计算、绑定或渲染”，不负责形成研究观点。检索与数据库在无人使用时都无法返回正确结果，就属于工具故障，不能归因于 Agent。

### 3. Evaluator

L1 金融事实校验、八维内容质量、多角色协作、paired gain 和 qualified-human 都是 Evaluator。Evaluator 可以拒绝输出并说明原因，但不能替研究员重写观点。只有失败反馈回到最早责任角色，Evaluator 才属于闭环的一部分。

### 4. 纯标签角色

`financial_specialist`、`supply_specialist`、`relationship_specialist`、`risk_specialist`、`capital_specialist`、`valuation_specialist` 等当前主要存在于 EvidenceRequest 的 `requester_role` 字段。它们没有独立会话、工具选择和输出，因此目前只是路由标签。Preview 会把有真实任务和资料的标签合并或升级成 Agent；估值、资本和独立行业研究因生产数据路线不足暂不激活，不能用空角色凑数。

### 5. Harness

Harness 管理身份、截至日、来源与期间、Candidate 到 Evidence 的晋升、NumericFact、Skill／Graph 选择、反馈路由、上下文压缩、停止、capture 和最终引用渲染。Harness 不应代替模型形成 thesis，也不应把每一次 DeepSeek 表达失败固化成核心 Runtime 分支。

## 四、当前信息源能支持什么

当前对象库以 DELL、MU、NVDA、MSFT、TSM 的 SEC 文件和少量业绩会为主。它可以较好支持：

- Dell 公司层经营表现和现金流；
- Dell AI 订单、AI 服务器收入、backlog 和客户数的官方来源可见事实；
- 公司层利润率、营运资金和现金事实；
- TSM、MU、NVDA 的部分供给与需求背景；
- 发行人风险因素和一定程度的上下游反证。

它不能自然支持：

- 完整行业需求与市场份额；
- Dell 特定的 HBM／先进封装分配、良率、产能释放时点；
- 取消、推迟、重复下单和 backlog 账龄；
- 产品级价格—数量—配置—利润桥；
- 完整 PIT 估值和商业订单数据。

所以 Preview 会激活需求、经营、价值、现金、供应关系和反方角色，但不会激活独立估值 Agent，也不会把行业和商业数据缺失评价成 Agent 不会研究。

## 五、旧五单元的关键问题如何分层

### 案例一：AI 订单、收入与 backlog 被写成“缺失”

源材料里已经有 AI 订单、AI 服务器收入和 backlog；需求单元也成功引用。经营单元却称相应事实不存在，Synthesis 又把它升级为跨单元冲突。

这不是单一模型问题：

- **数据／S2：** `orders`、`backlog` 仍显示 typed gap，结构化产品 KPI 覆盖不足；
- **Harness：** 旧上下文没有强制区分“本单元没加载”和“全案不存在”；
- **Agent 编排：** 角色之间没有事实存在性对账，也没有把冲突反馈给经营角色；
- **模型：** 模型反驳了自己本单元已经选中的来源可见事实；
- **Evaluator：** Verifier 正确发现了问题，但发现得太晚且不能触发局部修正。

处置不能是只改 Prompt。Preview 必须给每个角色一个 `CaseFactPresence` 工具，并在跨角色综合前强制对账；产品 KPI 的结构化权威继续作为 S2 的明确缺口，不冒充 SEC CompanyFacts。

### 案例二：Agent 提出行业补证，但路线只支持 SEC

这首先是 S1 路由与来源能力问题。即使 Planner 想找行业资料，如果实际工具只会在 SEC／本地对象里查，返回空结果也不能证明 Agent 规划无效，更不能宣称公开信息不存在。Preview 会把工具的可执行范围先告诉角色，无法执行的路线形成基础设施 FeedbackReceipt。

### 案例三：AI 利润归因过强

现有资料可以证明公司收入、利润率和经营利润变化，也有管理层对 AI 产品盈利目标的表述；但缺少产品到分部再到公司利润的审计桥。这一错误主要位于模型判断和角色方法，同时 Harness 应保证因果桥状态在所有相关角色中可见。Skill／Graph 可以提醒模型检查机制，却不能创造缺失证据。

### 案例四：EvidenceRequest 只登记、不执行

这是 Agent 编排与工具接入的项目缺陷，不是模型问题。真正 Preview 中，模型提交的合法请求必须触发一次真实 S1／S2 本地执行，并把 `EvidenceResponse` 或准确的工具失败返回同一个角色；否则所谓多轮只是伪多轮。

## 六、真正 Preview 的运行形态

Preview 采用以下事件序列：

1. 每个专业 Agent 在独立会话中读取同一任务边界，给出本角色计划意见、关键命题、所需工具和停止条件；
2. Research Lead 读取这些独立意见、Case readiness 和当前工具能力；
3. Lead 只合并结构与依赖，形成覆盖全部 required slot 的研究计划；
4. 专业 Agent 实际调用 S1／S2／Evidence／CaseFactPresence 工具；
5. 工具失败按最早责任层生成 `FeedbackReceipt`，资料不足与工具失败严格分开；
6. 专业 Agent 根据反馈修改查询、判断或保留真实 gap；
7. 独立反方 Agent 挑战其他工作底稿，Lead 只把挑战路由给受影响角色；
8. 只重跑受影响角色，未受影响角色复用不可变工作底稿；
9. Writer 从已验证工作底稿选择报告结构，不得新增事实；
10. Verifier 和内容 Evaluator 检查；可修失败回到原角色一次；
11. Lead 形成 `StopDecision`，保存 checkpoint、每个 Agent 的局部状态和完整 capture。

每个模型节点的 TokenBudgetBasis 以任务目的、可见材料规模、输出责任、结构负担、质量风险、历史运行和截断策略为依据，不能只因为省钱或更快就缩短。

## 七、Preview 结果应该怎样评价

Preview 不是看“跑完没报错”，而要同时回答：

- 数据／工具层是否把已有材料完整、正确、可追溯地交给角色；
- Harness 是否正确区分事实、角色可见性、gap 和工具故障；
- 每个 Agent 是否提出了与职责不同的独立意见；
- 反馈是否真的改变了查询、计划或判断；
- 多角色是否减少旧五单元的假缺失、因果越界和通用反方；
- Writer 是否把多个工作底稿组织成有实质内容、可伸缩的报告；
- 相对旧固定 workflow，质量增益是否值得更多上下文和调用成本。

本次 Preview 即使成功，也只证明当前 DELL 资料边界下的多角色工作模式可行；它不自动签发 S1、S3、qualified-human、S4 或 release。

## 八、零调用 Gate 的实际结果

零调用 `v1.2` 已证明六个专业角色都能获得非空的、按角色隔离的权威视图；Supply／Relationship 从错误的 0 条恢复为 10 条 reviewed Evidence。修复不是放宽证据门，而是把 exact reviewed Evidence reader 与 dynamic candidate retrieval 分开：动态检索只能提供候选与执行回执，不能擦除或晋升既有 Evidence。

仍未关闭的最早缺陷位于 S1 工具层：当前 reviewed Pack 有多条上游／关系资料，但动态检索仍不能稳定把这些目标召回到对应 EvidenceRequest。该缺陷保留为独立 S1 工作，不阻止在既有 reviewed authority 上做诊断性 Multi-Agent Preview，也不能因 Preview 能读到资料而宣称动态检索或 S1 已通过。

Live Gate 已实现独立 AgentSession、专业意见、Lead 协调、角色底稿、结构化挑战、FeedbackReceipt、checkpoint/resume、局部修正、独立 Evaluator、StopDecision 和条件式 Writer。执行 authority 只能在干净实现提交后签发，并限制为 0 外部来源网络、0 Candidate promotion、0 产品发布；每个模型节点都必须带任务级 TokenBudgetBasis。

## 九、R5／R6 对 Preview 编排的修正

Research Lead 的职责规模显著大于单个 Specialist，不能把“形成综合分析”和“严格结构化交卷”塞进一次 completion。R4／R5 证明合理路径是：可见分析 → 片段 checkpoint → actionable feedback → 最多一次 continuation → 完整分析 checkpoint → non-thinking strict submission。分析与交卷仍由同一角色拥有，但它们使用不同责任、上下文和 TokenBudgetBasis。

R6 不再重跑六个 Specialist 或 Lead 分析，只复用经 digest 验证的成功前缀并从严格 Lead submission 恢复。后续角色仍必须各自运行并留下独立会话、工具回执、挑战和修改记录；复用 checkpoint 不能把 Preview 偷换成单一 Lead 报告，也不能让 Harness 替 Agent 生成观点。

## 十、R6 暴露的 Lead 合同容量与反馈问题

R6 两次 strict submission 均返回 13 个协调问题、11 条信息边界和 9 条停止条件。旧 Tool Schema 分别限制为 8／10／8，本地 Validator 却统一限制为 10，且失败反馈只暴露错误码。这是 Harness 合同编译和反馈协议问题，不是 S1 数据或 Provider transport 问题。

不能用本地截断把计划压回旧常数。当前 13 个 facet、7 个 required slot 和 6 类工具权限决定 Lead 确实需要比单一 Specialist 更大的控制面。新策略按拓扑派生三类容量，并作为 Schema、Validator、分析 Prompt、submission Prompt 的共同来源；角色／facet／工具拓扑变化时只重新编译策略，不允许各层手写新上限。

合同失败必须生成可行动回执：列出全部字段、实际数量、规则和允许范围；模型只修改结构映射，不重做研究或增加事实。R6 Attempt 02 已在新合同下零调用验证并形成内容寻址 Lead checkpoint，R6 本身仍是 immutable failure。后续运行从 checkpoint 之后开始，不能再次调用已经成功的 Specialist 计划、Lead 分析或 Lead submission。
