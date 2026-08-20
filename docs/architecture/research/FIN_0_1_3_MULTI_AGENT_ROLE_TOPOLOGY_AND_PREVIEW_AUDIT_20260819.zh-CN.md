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

## 十一、Lead checkpoint 后的运行拓扑

Lead checkpoint successor 不再经过 Planning 或 Lead-plan Provider 节点。Harness 只验证 Specialist／Lead checkpoint、重新物化当前 S1/S2 视图，并在 Research Lead Session 写入可追溯 `plan_bound` 事件；随后才激活六个 Specialist workpaper。Lead 之后可作为真正协调 Agent 消费底稿并路由挑战，但这与已经完成的 Lead-plan 节点是两个不同职责。

剩余容量严格为：六份 workpaper、一次协调、最多三次反方 repair、两轮 Evaluator、最多两次 evaluator repair 和条件式 Writer，共 15 个模型节点。每个模型节点继续使用可见分析＋严格交卷，局部失败通过 FeedbackReceipt 和 checkpoint/resume 回到原责任 Agent。数据／工具失败不得路由成模型修文，Harness 失败不得被 Evaluator 解释成研报质量问题。

## 十二、R9 协调检查点与 R10 下游拓扑

R9 补齐了此前缺失的第六份 Counter workpaper。该底稿和前五份底稿分别拥有独立 AgentSession、模型 request／response capture、validated payload digest 和工作底稿 digest；它们不是 Harness 拼出的观点。Research Lead 的协调调用也真实读取了六份底稿，并形成三条 accepted challenge 与一条 deferred challenge。

Lead 两次作出同一分流，说明失败点不在协调语义：需求、现金、供应已有当前 Evidence 支持局部修订；价值挑战需要新的 Evidence，因而延期。失败发生在提交后的项目合同校验：旧 rationale 上限 1,200 字不足以表达四条 challenge 的目标、理由和修订边界，并被错误映射成 identity invalid。

R10 将协调容量改为拓扑派生值 `min(4000, max(1200, 600 + 400 × challenge_count))`。当前四条 challenge 编译为 2,200 字；同一 compiler 同时驱动 Tool Schema 和本地 Validator。容量并非为 DeepSeek 单独放宽：它与 challenge 数相关、具有 4,000 字全局上界，并由 max+1 mutation 验证 fail closed。

新的检查点层次为：

1. R3 Specialist plan checkpoint；
2. R6 Lead plan checkpoint；
3. R8 five-workpaper checkpoint；
4. R9 Counter workpaper capture binding；
5. R9 Lead coordination capture binding；
6. R10 从 accepted challenge repairs 开始。

每层都绑定 authority、public／terminal result、capture sha256、模型 request／response digest、validated payload digest 和 Session checkpoint／resume receipt。任何内容或 lineage 漂移都拒绝恢复。R10 的最大新节点为八个，不再把已完成前缀算入模型预算，也不允许为了“完整运行”重放上游。

这一结构仍是有界 Preview，不是通用 Agent 平台完成态。它尚未证明开放外源动态检索、跨案例泛化、长期上下文压缩后的计划连续性或最终产品报告质量；这些能力必须由后续真实结果和独立验收分别证明。

## 十三、R14／R15：局部修订上下文不是完整全案上下文的复制品

R14 把三个责任层进一步分开：

- **数据／工具层**：Supply 角色可见 10 条 reviewed Evidence 和 4 个 typed gap；没有 NumericFact 是当前角色合同事实，不是检索空结果。数据层不是本次最早故障。
- **Harness 层**：局部 Supply repair 仍收到 91,182 字符 SpecialistContext，其中 whole-case truth catalog 40,655 字符、完整 Lead plan 7,119 字符。大量无关目录占用输入并增加推理搜索空间，这是最早故障。
- **Agent／模型执行层**：`thinking=max` 将 12,000 completion token 全部消耗为 reasoning、可见输出为 0。它说明该任务 profile 不合适，但不能据此说 Supply 角色无价值或 DeepSeek 不会做供应研究。

repair-scoped context 不是简单截断。它必须保持角色授权事实、数字关系、typed gap、prior workpaper、当前 challenge／feedback、RoleMethodPack、GraphContextPack、计划、工具回执与权限；只把与本次修订无直接关系的 whole-case alias 和 Lead 长叙事压成内容寻址 projection。每次 omission 都保存数量和 digest，并明确 omission 不能证明 case absence。

同一个已完成 repair 的恢复器同时接受旧完整上下文和新 repair-scoped 上下文，并继续验证原 request／capture／attempt／context／workpaper lineage。这使上下文演进不会迫使已成功节点重跑，也不会把新 schema 当作新业务答案。

R15 只从 pending Supply fresh analysis 开始，精确复用 Demand／Cash，禁止 continuation 和已完成节点重跑。task-specific high profile 隔离在 Provider adapter，核心金融合同不增加 DeepSeek 专用字段。若 R15 后再出现 successor 编排问题，必须用通用 authority compiler 取代多代 attempt-specific schema 分支，而不是继续增加 R16／R17 特例。

## 十四、R15B：恢复链必须消费 active checkpoint，而不是它的 ancestor

R15B 在 Provider 前暴露了一个独立的 S0 恢复集成错误。V2 checkpoint 已正确记录 Demand／Cash 两份完成 repair 和唯一 pending Supply，但 runtime drift 校验仍读取 V1 ancestor；V1 只含 Demand，于是把合法的两份恢复结果误判成漂移。该失败不属于数据缺失、Agent 角色无效或 DeepSeek 不遵循指令。

当前恢复合同因此明确为：lineage 验证仍可逐级读取 ancestor，但“本轮完成／pending 集合、运行计数和恢复证明”只能由 active checkpoint 决定。R15 还必须显式证明 continuation 为 0、Demand／Cash 没有重跑且 Supply 只 fresh 一次。成功结果的 known boundary 必须描述当前 R15 Supply successor，不能沿用 R11 Cash continuation 叙述。

该修复复用既有 v1.14 authority schema 和 v1.10 scope；R15B 保持不可变失败，下一次只换 attempt identity，不新增 R16／R17 schema 分支。若后续仍需要新的 successor 合同形态，必须先实现通用 authority compiler。

## 十五、R15C：分析上下文与提交校验上下文必须是同一条 lineage

R15C 越过 active checkpoint 校验后，在复验完成 repair 时再次触发 `multi_agent_bound_workpaper_digest_invalid`。逐节点回放表明 Demand 可精确复用；Cash 的模型 continuation 读取 context `51944726...37d5f`，而最终 payload 在 R14 被本地绑定到另一份 context `18d5f6ab...24063`。相同业务字段对原模型可见 context 重验可以通过，但会产生不同的派生 workpaper digest。这说明观点内容与 lineage 问题必须分开：不能把 digest 冲突说成模型观点错误，也不能因为业务字段看起来合理就关闭 fail-closed。

通用 successor 的恢复单元因此扩展为 `business payload + exact model-visible context + local validation context + capture/attempt/checkpoint lineage`。compiler 对每个节点只能给出四种状态：精确复用、仅派生 digest 的受据重绑、必须 fresh 重做、原生 pending。第二种状态必须证明移除本地派生 digest 后所有业务字段逐字不变，并对 capture-bound 原上下文走完整 validator；任何业务字段修补都升级为 fresh rerun。

authority、Project OS preflight 和 runner 必须消费同一份 execution frontier。R15C 后禁止新增 attempt-specific schema 分支；下一次 live 只有在通用 compiler、mutation、全仓门、clean push 和 fresh preflight 通过后才可签发。

## 十六、独立 Evaluator 不是第七个研究员

通用 successor 的真实运行证明 Supply Agent 已能消费局部挑战并把上游披露收窄为 speaker-attributed bounded read-through。随后 Evaluator R1 却在 31,732 prompt token 与 16,000 reasoning token 后形成 0 可见输出。失败原因不是 Supply 资料为空，而是评审消息重复装入六份完整底稿、完整全案 truth catalog、来源目录与多套 visibility matrix。

评审责任因此拆成两层：

1. 本地 L1 使用完整权威包检查公司身份、期间、引用存在性、精确数字、关系端点、跨案污染和 case-level absence；
2. 模型 Evaluator 只检查判断质量、经济机制、反方强度、WWC 和跨角色一致性，并把 finding 路由到最早责任角色；它不得重写底稿，也不必重复读取未被任何底稿使用的原始权威。

`EvaluationContentView` 必须从六份工作底稿实际引用的 Evidence／NumericFact／NumericRelation／typed gap 反向投影权威。任何引用未能同时在 Case Truth 和角色上下文解析时 fail closed；未引用材料只在本地权威包保留，省略绝不等于不存在。真实 capture 回放将消息从 116,494 bytes 降为 86,109 bytes，同时完整保留 28 Evidence、19 NumericFact、9 NumericRelation 和 11 typed gap。第一次尝试因重复原文反而增至约 136KB，已由同一回放门拒绝，证明“紧凑”必须以真实消息体和引用完整性衡量，不能凭字段名判断。

若 claim-bound 评审视图仍以同一方式耗尽推理，不再继续逐字段削减金融权威；应重新决定 Evaluator 的 reasoning profile、模型或职责边界。内容压缩不得成为掩盖评审模型不适配的永久拐杖。

## 十七、通用 successor 必须能继续任意已保存终态失败

Supply 已成为第三条完成 repair，旧 frontier 不能再把它当作 pending fresh。新的 v1.1 frontier 将 Demand、Cash、Supply 全部作为 capture-bound 完成节点，只允许从 Evaluator 继续，最大新模型节点为 `2 evaluation + 2 evaluator repair + 1 conditional Writer = 5`。

通用 predecessor 合同不再把某一个历史 failure code 或 `0 Provider` 写死为入口条件。它接受任意非空、已保存的 terminal failure，但必须同时核对 authority、public result、private terminal、failure code、Provider attempt count、scope、digest、0 external network 和 0 Candidate promotion；任一漂移都 fail closed。这是对同一执行前缀的通用恢复，不是又一条 attempt-named R16／R17 分支。

## 十八、claim-bound 仍失败后，Evaluator 必须分层而不是继续裁字段

真实 successor 已把 Evaluator prompt 从 31,732 降到 24,591 tokens，仍然出现 16,000 completion 全部为 reasoning、0 可见输出、`finish_reason=length`。Provider 响应完整，六份底稿与三条修订均已 capture-bound 复用。RC-AR-020 因而从“上下文投影待证明”升级为“全案单节点 Evaluator 任务／profile 不合格”。

新的 provider-neutral 评审拓扑固定为：完整权威上的本地 L1；六个单角色内容审查；一次只消费已审摘要的跨角色一致性审查；最多两处最早责任角色修订；只重审受影响角色并做一次跨角色复核；通过后才允许 Writer。角色级与跨角色分析使用 `high / 12,000`，交卷继续使用 non-thinking strict submission。最大 13 个新逻辑节点来自六个真实角色和两处有界修订的最坏路径，不以成本或延迟倒推。

这不是把 Evaluator 变成六个新研究员。它们不能新增 Evidence、NumericFact、因果关系或观点，只能出 finding、责任归属和是否阻断。若单角色评审仍发生同型 reasoning-only exhaustion，下一项必须是模型／profile 责任选择，不得再缩金融权威或增加 attempt-specific runner。

## 十九、分层 Evaluator 的工程实现与零调用资格

分层评审现在不是一份架构草图。Runtime 已把六个角色的最终底稿分别绑定到各自最后一次合法模型上下文：Demand、Cash、Supply 使用修订后的 capture-bound context，Operating、Value、Counter 使用原始合法 context。角色审查只能读取这一份底稿及其实际引用的 Evidence、NumericFact、NumericRelation 和 typed gap；跨角色审查只读取六份底稿摘要、角色审查结论、Lead coordination lineage 和 finding 责任面，不携带未引用的全案权威目录。

真实 capture replay 给出的角色输入规模为 11,274—18,365 字符；六个角色分别保留 2—10 条 Evidence、0—12 个 NumericFact、0—6 个 NumericRelation 和 0—4 个 typed gap。跨角色输入为 45,252 字符，但 `referenced_authority_included=false`，因为它只做一致性与责任检查。本地完整 L1 在同一六底稿上得到 0 条 absence blocking finding；缺角色、错角色、未解析 authority、排列漂移、frontier 超预算和无关角色复审六类 mutation 均 fail closed。

确定性 fake 证明：无修订路径为六次角色审查＋一次跨角色审查＋条件式 Writer，共 8 个逻辑节点；最多两处修订路径为 13；第三处修订会要求 15 个节点并被 frontier 拒绝。修订后只允许受影响角色复审，不能为了“再确认一次”重跑其余角色。该预算来自六个实际研究职责、两处质量风险处置和 Writer，而不是从成本或速度倒推。

`successor_scope_decision_v1_2` 必须同时绑定 frontier 与 `hierarchical_evaluator_zero_call_result_v1_0` 的 ref、sha256 和 result digest；authority 也必须逐字绑定同一复证。历史 monolithic scope 不需要该字段，保持可复放但不能借此执行层级路线。零调用复证使用本地 Qwen 检索物化，因此准确表述为 0 Provider 模型调用、0 网络、0付费调用，而不是“完全没有任何本地模型加载”。

这一步只证明上下文选择、lineage、预算、故障注入和恢复路径可执行。它不证明 DeepSeek 能完成自然角色审查，不证明 Writer 或报告质量，也不关闭 S1、S3、泛化、qualified-human、Workbench 或 release。

完整工程门结果为：定向 109、全仓 913、compileall、active baseline `185 Python／8 frontend／5 detectors／27 Runtime／0 forbidden`、755 份 configs、8 份 Project OS JSONL／867 行、7,473-file secret scan 与 diff check 全部通过。下一步只能在 clean commit／push 和 fresh Project OS preflight 后签发一次新 authority。
