# FIN 0.1 第二层 Agent Core / Orchestration / Skill 执行草稿

日期：2026-07-19
状态：`discussion_draft / not_execution_authority / not_release_admission`
上位草稿：`FIN_0_1_NEXT_STAGE_PRODUCT_MAINLINE_EXECUTION_DRAFT_20260719.zh-CN.md`
关联主线：`PM-EP0 / PM-EP1 / PM-EP2`、`PM-G1 / PM-G2 / PM-G3 / PM-G5`

## 1. 文档目的

本草稿只回答第二层问题：如何把仓库中已经存在但与 FIN 0.1 Workbench 断连的 Multi-Agent、LangGraph、Agent Registry、Skill Registry、Tool Controller 和 information-economy 能力，迁入唯一产品运行时。

本草稿不是“把旧 Agent 原样接上”，也不是批准重写第二套 Agent。目标是：保留有价值的角色、权限、Skill、预算和判断资产，重构固定编排、状态和 handoff，使它们消费当前 canonical Case / DecisionSurface，并输出统一 ResearchRun / Artifact / EventTrace。

> 2026-07-19 S1-T04 执行更新：本草稿仍不是执行权威；active Program Backlog 已接受一个完整 NVDA“需求真实性与持续性” `agent_fixture_shadow` cell。现有单一 `Fin01ResearchRuntime` 现在消费历史 LangGraph 从 Lead planning 到 Tool/Graph fixture observation、Specialist、Judgment aggregation、Writer、Verifier、Renderer 和 persist 的完整节点路径，记录 9 个 Run-scoped 结构化事件，并提交共享同一 Attempt/ResearchRunVersion 的 manifest、Evidence、Numeric、Judgment、Workpaper、Report、Trace 7 个 immutable artifacts。Agent/Skill versions 继续 content-addressed；model/provider/network/external tool/业务 Case mutation 均为 0。该结果只证明 fixture-shadow 编排接通，不证明真实 Agent 研究质量；Workbench projection 仍待 T05。

## 2. 当前事实基线

### 2.1 已实现资产

- `src/sec_agent/agent_registry.py`：17 个 Agent contract，包含 Lead、Universe、Evidence operators、Coverage、五类 specialist、Aggregator、Writer、Verifier 和 Renderer；
- `src/sec_agent/langgraph_orchestrator.py`：17 节点 Multi-Agent graph，覆盖 planning、retrieval、reflection、second pass、specialist、judgment、writer、verification 和 persistence；
- `src/sec_agent/research_skills.py`：16 个版本化 Skill 文件、20 个 role bindings；
- `src/sec_agent/multi_agent_router.py`：`deterministic_lookup / focused_answer / standard_memo / deep_research` 路由和 loop budget；
- `src/sec_agent/tool_controller.py`：bounded tool step 与 tool trace；
- `src/sec_agent/agent_information_economy.py`：fan-out、重复上下文、信息转移和有效产出评估；
- 现有 registry 自校验为 `pass`；T03 已关闭 `product_technology_analyst` 的只读 `relationship_graph` source-family 合同漂移，T04 又验证 fixture relationship dependency injection 不会先触发真实 MCP lookup；含 T02-T04、Agent/Skill、LangGraph、canonical runtime 与 mainline manifest 的独立复核后相关回归为 `102 passed`。

### 2.2 当前产品主链

Workbench 当前默认仍由 `apps/workbench/backend/application/local_research_service.py` 执行固定十-cell P36 本地预览：8 次 object BM25、1 次 Gold SQL、1 次 research-graph SQL，再确定性生成 numeric、repair、judgment、workpaper 和 writer projection。T04 已让 backend API / single runtime 的显式 `agent_fixture_shadow_entry` 完成一个完整 fixture cell，但尚未增加 Workbench profile/event/artifact UI。

该链当前明确为：

- `bounded_local_deterministic_preview`；
- `model_calls=0`、`network_calls=0`、`external_tool_calls=0`；
- deterministic profile 不消费历史 Registry/LangGraph；独立 Agent shadow profile 已消费版本化 Agent/Skill registry 和 early LangGraph slice；
- 不证明 Agentic Research、Agentic Search、真实 Human Senior Review 或 release admission。

2026-07-21 S2 增量：`bounded_agent_internal` 已在同一 NVDA 单 Cell 上形成一个 DeepSeek segmented-v4 live succeeded Run；S2-T04 随后只读验收同一 Run 的 9 类 canonical Artifact。Run-scoped evaluation EvidenceVersion、typed numeric gap、Specialist/Lead Judgment、no-source Writer 与 deterministic integrity / semantic fidelity / financial coherence / visual delivery 四层 Verifier 全部通过；canonical DB 与 object tree 摘要在验收前后不变，T04 新增 model/provider/network call=`0/0/0`。该结果不等于 live Evidence head promotion，不接受 material gain，也不替代 S2-T05 owner product review。

2026-07-21 S2-T05 增量：T03 live store 原先并没有独立 deterministic Run，comparison Artifact 的 `runs_must_be_distinct=true` 只是要求而非已完成证据。T05 先修复未来 comparison readiness 语义，再在同一 isolated evaluation store 中以同一 exact input 物化零调用 deterministic Run，与既有 Agent Run 形成不同 ResearchRun 和精确 Artifact 绑定。独立九维产品复核认为 Agent 的新增价值限于机制粒度、边界、gap/WWC 和报告可审性；没有新来源、支持性数值或长期持续性证明。技术比较已通过，owner product acceptance 仍必须由用户本人明确给出；未进入 S2-T06、S3、release 或 production。

### 2.3 核心断点

当前不是“Agent 代码不存在”。T04 已关闭 single runtime、Agent/Skill selection trace 和 complete fixture graph consumption 的 S1 后端断点；剩余断点是：

1. T05 尚未把 Profile、9 类结构化 Agent/Skill/Tool/Graph/Writer/Verifier 事件、7 个 exact artifacts 和 typed stop reason 投影到中文 Workbench；
2. 历史 graph 后半段仍以大型 SEC-oriented state 推进；T04 只以一个 selected Cell 的 deterministic fixture task/result 适配证明节点可接通，真实模型上下文与研究质量仍待 S2；
3. Agent/Skill selection/injection/consumption 与 fixture Specialist/Writer/Verifier 已有 Run trace，但真实 Specialist model invocation、真实 Tool/Graph authority 和信息增量仍为 0；
4. deterministic 与 Agent shadow 已有不同 Run/Artifact，独立 model runner 继续保持隔离，不能借 T04 自动获得 S2 权限。

## 3. 第二层目标运行结构

```text
Workbench Case action
  -> Fin01ResearchRuntime
  -> ExecutionProfile
       deterministic_fallback
       agent_fixture_shadow
       bounded_agent_model       [separately authorized only]
  -> ResearchRun
  -> Lead compiles/reads DecisionSurface cells
  -> Agent/Skill selection
  -> EvidenceRequest or structured SubagentTask
  -> structured result / typed stop
  -> ArtifactManifest + EventTrace
  -> Workbench read models
```

### 3.1 `Fin01ResearchRuntime`

唯一产品执行边界，至少接收：

- exact `case_id / case_version`；
- exact `DecisionSurfaceContractVersion`；
- `ExecutionProfileVersion`；
- actor / permission / budget snapshot refs；
- model、tool、data、skill、graph capability refs；
- idempotency、expected version 和 correlation refs。

至少返回：

- `ResearchRun` identity 和状态；
- selected execution mode；
- artifact manifest；
- structured event trace；
- typed stop / failure；
- next product action。

Workbench、CLI、provider runner 和历史 graph 均不得绕过该边界建立第二套产品 Run。

### 3.2 `ExecutionProfileVersion`

首轮只允许三种有明确真值标签的 profile：

| Profile | 用途 | 当前权限 |
| --- | --- | --- |
| `deterministic_fallback` | 保留现有 P36 本地只读产品能力和回归基线 | 允许 fixture/shadow/internal |
| `agent_fixture_shadow` | 让历史 Agent 资产消费当前 Case/cell fixture，不产生 release authority | 允许 fixture/shadow/internal |
| `bounded_agent_model` | 经单独批准的有限模型运行 | 本草稿不授权 |

profile 必须固定 Agent/Skill/Tool/Graph/model/data policy refs，不能只保存一个自由文本模式名。

### 3.3 `ResearchRun`

`ResearchRun` 是一次产品研究执行的 exact identity，不等于 Case，也不等于某个 LangGraph checkpoint。至少绑定：

- Case/version、DecisionSurface/version；
- execution profile/version；
- input digest；
- selected cell versions；
- agent/skill/tool/graph configuration digests；
- start/stop/terminal status；
- artifact manifest digest；
- event trace head；
- parent/fallback/supersession refs。

2026-07-20 S2-T03 v4 增量冻结：对同一 Case/input 的不同非 VT1 execution，`WorkUnit` canonical identity 必须额外绑定 request `idempotency_key` 作为 `execution_identity`；Attempt 从 distinct WorkUnit 派生，ResearchRun 再从 distinct Attempt 派生。相同 execution identity 必须幂等复用，不同 identity 必须在同一 shared store 中形成不同 WorkUnit/Attempt/ResearchRun；后台分派也必须按本次 request `idempotency_key` 精确选取 pending WorkUnit，不得依赖“同类型仅一个 pending”的旧假设。VT1 的单 fixture WorkUnit 语义保持不变。该增量只修 exact lineage，不签发模型运行权限。

### 3.4 `EventTrace`

前端展示结构化运行事件，不展示模型私有思维链。最小事件类型：

- `run_started / run_stopped / run_failed / run_completed`；
- `cell_selected / cell_skipped / cell_blocked`；
- `agent_selected / agent_started / agent_completed / agent_failed`；
- `skill_selected / skill_injected / skill_skipped`；
- `tool_requested / tool_invoked / tool_observed / tool_rejected`；
- `graph_queried / graph_candidate_returned`；
- `evidence_request_created / structured_result_submitted`；
- `typed_stop_recorded / fallback_selected`。

每个事件必须带 run、cell、attempt、causation、actor/capability version 和 artifact refs；不得把自由文本 CoT 当 trace。

### 3.5 `Research Lead` 与 Agentic Research 合同

#### 3.5.1 当前事实与目标状态

当前 FIN 0.1 Workbench 的十-cell 主路径仍是 `bounded_local_deterministic_preview`；历史 Lead/Multi-Agent、Skill Registry 和 Agentic Graph 尚未被统一 Runtime 消费。因此，本节定义的是下一阶段目标合同，不是当前已实现能力。只有 Runtime 实际消费、node-level 测试和产品 Run 轨迹都成立后，才可把状态从 `documented` 推进到 `runtime_injected / node_level_consumed`。

#### 3.5.2 Agentic Research 的必要闭环

Lead 必须在同一个 exact `ResearchRun` 内形成以下闭环：

```text
approved initial plan
  -> dispatch specialist / skill / evidence request
  -> observe structured result
  -> update cell and cross-cell research state
  -> continue / reorder / reopen / repair / bounded stop
  -> cross-cell synthesis
  -> WriterAdmission recommendation
```

仅拥有动态权限、调用模型或调用工具，不足以证明 Agentic Research。完成证明必须显示：不同 observation 会产生不同 next action；研究轨迹由证据强度、冲突、gap、预算和边际信息价值改变，而不是把固定节点改名后继续顺序执行。

#### 3.5.3 Lead 的结构化决策输出

Lead 至少输出并版本绑定：

- `LeadPlan`：本 Run 的研究目标、优先 Cell、依赖和停止条件；
- `CellDispatch`：下一步选择的 Cell、Agent、Skill 和原因码；
- `EvidenceRequest`：缺失证据、来源边界、freshness 和回答标准；
- `ObservationAssessment`：结果是否回答问题、支持强度、冲突和 gap；
- `ReplanDecision`：继续、重排、重开、拆分建议或 bounded stop；
- `RepairDecision`：最早错误产物、目标 owner 和 repair scope；
- `CrossCellConflict`：一个 Cell 的 observation 对其他 Cell 判断的影响；
- `StopDecision`：完成、证据不足、预算停止、权限停止或等待人工；
- `LeadSynthesis`：需求、价值捕获和反证之间的因果关系；
- `WriterAdmissionRecommendation`：是否具备进入 no-source Writer 的材料。

这些对象必须通过结构化 `EventTrace` 展示选择、观察、状态转换和停止原因；不得持久化或展示模型私有思维链。

#### 3.5.4 动态权限与固定边界

Lead 在已批准 Case scope 和 Runtime policy 内可以：

- 根据 Cell 状态、gap、冲突、预算和信息增益重排研究顺序；
- 选择已准入的 Agent、Skill、Tool/Data capability；
- 发出结构化 EvidenceRequest、补证、交叉验证和 bounded repair 请求；
- 在跨 Cell 冲突出现时建议重开已完成 Cell；
- 在证据充分、继续研究价值低或触发 typed stop 时停止；
- 形成跨 Cell synthesis 和 WriterAdmission 建议。

Lead 不可以：

- 改变 Case 的用户目标、证券/公司范围、as-of、权限或预算上限；
- 直接执行未准入 Tool、网络、付费模型或商业数据调用；
- 直接晋升 Evidence、覆盖 Numeric 确定性结果或伪造 source lineage；
- 绕过 Evidence Gate、Human Review、release gate 或 production authority；
- 给 Writer 增加 source/tool 权限；
- 直接修改 canonical Case、release head 或已签名 artifact；
- 用自由文本推理替代结构化 decision/result/stop objects。

`L2-D02-DecisionSurfaceMutationAuthority` 已冻结为 `bounded_run_overlay_with_human_versioned_material_revision`。Lead 可以在 accepted DecisionSurface 之上自主改变运行顺序、状态和调查分支，但不能原地改写 accepted DecisionSurface；任何顶层或语义性变化必须形成 versioned revision proposal，并经过 Human Review。

#### 3.5.5 FIN 0.1 首个三-cell Agent 纵向

| Cell ID | 中文定位 | 核心问题 | 主要能力证明 |
| --- | --- | --- | --- |
| `demand_signal` | 需求真实性与持续性 | AI 基础设施需求是否真实、公司特定且可持续 | Agentic Search、官方/客户/跨链证据判断、freshness 与边界 |
| `revenue_capture` | 价值与利润捕获 | 需求能否转化为目标公司的收入、毛利、营业利润和现金经济性 | SQL/Numeric、分部归因、定价/组合、`cannot_infer` |
| `thesis_counterevidence` | 瓶颈、反证与 What-Would-Change | 什么会削弱或推翻当前判断，何种新事实会改变结论 | Graph、反证搜索、repair、typed gap 和重开条件 |

三者构成最小因果链：`需求真实 -> 公司捕获价值与利润 -> 风险不足以推翻判断`。选择这三个 Cell 是为了同时验证检索、数字、Graph/反证和 Lead 跨 Cell 编排，不代表三个 Cell 已覆盖完整十-cell 机构级研究。

#### 3.5.6 Agentic Research 最小验收证明

至少用同一合同下的四类 observation 证明轨迹分叉：

1. 强且新鲜的需求证据使 Lead 关闭 `demand_signal` 并进入 `revenue_capture`；
2. 过期、泛化或非公司特定证据使 Lead 发出更精确 EvidenceRequest，而不是直接晋升判断；
3. 收入/利润数字冲突使 Lead 发起 Numeric Repair，并在无法归因时记录 `cannot_infer`；
4. Graph 或反证结果破坏前序假设时，Lead 提出重开相关 Cell，而不是继续 Writer。

验收必须比较实际 `ResearchRun` 的 plan、dispatch、observation、replan、repair、stop 和 artifact lineage。单一 happy path、静态 fixture 顺序、模型调用计数或文字自述均不能证明 Agentic Research。

#### 3.5.7 `L2-D02`：DecisionSurface 修改权限

FIN 0.1 采用三层对象：

| 层级 | 对象 | 修改权限 |
| --- | --- | --- |
| 已批准研究合同 | `AcceptedDecisionSurfaceVersion` | 不可原地修改；只能经 Human Review 产生新版本 |
| 当前运行计划 | `RunDecisionOverlayVersion` | Lead 可在 accepted scope 内自主更新 |
| 重大范围变化 | `DecisionSurfaceRevisionProposal` | Lead 提议，Human 批准或退回 |

`RunDecisionOverlayVersion` 必须绑定 exact DecisionSurface、ResearchRun、parent overlay、causation event 和 input/result refs。它不是第二套 planning authority，也不能改变 canonical contract digest。

Lead 可以自主：

- 重排三个 Cell 的优先级和调度顺序；
- 更新 `queued / active / waiting_observation / sufficient / reopened / blocked / cannot_infer / stopped_budget / waiting_human` 运行状态；
- 在总预算和 profile 上限不变时重新分配 Cell 预算；
- 在已有顶层 Cell 下创建 bounded `InvestigationBranch`，记录 parent cell、子问题、原因、预期结果、预算和 stop condition；
- 在既有 source/evidence policy 内新增补证、交叉验证、反证和 Numeric Repair 请求；
- 因跨 Cell 冲突重开已完成 Cell；
- 对可选研究 bounded stop，并对 mandatory Cell 给出 `sufficient` 或带边界的 `cannot_infer` disposition；
- 建议进入 Writer、继续 Repair 或等待 Human。

Lead 必须提出 `DecisionSurfaceRevisionProposal`，不能自主执行：

- 新增、删除、拆分或合并顶层 mandatory Cell；
- 改变 Cell 核心问题、owner、materiality、mandatory EvidenceSlot 或 dependency semantics；
- 删除必需证据、弱化 source authority/freshness/Numeric 标准或放宽 forbidden substitution；
- 改变 Case 研究目标、公司/证券 universe、as-of、语言或交付范围；
- 提高预算、改变 permission/model/tool/data profile 或扩大外部调用权限；
- 改写已签名 artifact、Evidence promotion、Numeric 结果、Human Review 或 release authority。

重大修改流程为：

```text
accepted DecisionSurface vN
  -> ResearchRun bound to vN
  -> Lead detects material plan change
  -> pause current Run with typed reason
  -> DecisionSurfaceRevisionProposal + exact diff
  -> Human accept / return
       return  -> resume old Run under vN
       accept  -> append DecisionSurface vN+1
               -> close old Run as superseded_by_plan_revision
               -> create child ResearchRun bound to vN+1
```

新 Run 可以按 exact refs 复用仍有效的旧 Evidence、Numeric 和其他 immutable artifacts，但必须重新判断它们对 vN+1 的 applicability；不得重写旧 artifact 的原始归属。

Workbench 必须同时显示 accepted plan 与 current run overlay。普通重排、补证、repair 和 reopen 通过结构化事件呈现，不触发人工审批；只有 material revision 显示计划差异并请求批准。UI 必须持续显示 DecisionSurface version、ResearchRun、execution profile、Lead action reason 和 fallback/Agent 模式，不展示模型私有思维链。

FIN 0.1 的三个顶层 Cell 足够宽，Lead 通过 InvestigationBranch 获得研究弹性；首版不允许自主扩张顶层 Cell，以避免 scope drift、状态爆炸和 Human Review 失去 exact binding。后续版本如需开放自动顶层 Cell 生成，必须作为新的合同版本和独立产品决策处理。

#### 3.5.8 `L2-D03`：Agent Topology 与 Handoff

`L2-D03-AgentTopologyAndHandoff` 已冻结为 `stable_domain_specialists_with_lead_mediated_handoffs`。Cell 是研究问题，不等于 Agent；FIN 0.1 不按一个 Cell 一个 Agent 扩张角色，而是由稳定专业角色按 Cell、InvestigationBranch 和 observation 动态参与。

现有 17 个 Agent definitions 按产品运行职责重分类：

| 分类 | 保留对象 | FIN 0.1 运行定位 |
| --- | --- | --- |
| 决策 Agent | `research_lead` | 规划、调度、观察、replan、跨 Cell synthesis 和 stop |
| Domain Specialist | `fundamental_analyst`、`product_technology_analyst`、`industry_supply_chain_analyst`、`market_valuation_analyst`、`risk_counterevidence_analyst` | 由 Lead 条件性激活，提交结构化专业判断或研究请求 |
| Downstream Agent | `memo_writer`、`verifier` | Writer 只消费 admitted artifacts；Verifier inspect-only |
| Evidence Operator | `universe_relationship`、`sec_operator`、`eight_k_operator`、`market_operator`、`industry_operator`、`web_evidence_operator` | 由 Tool Planner/Runtime 调度的受限检索能力，不作为平级判断 Agent |
| Deterministic Service | `coverage_reflection`、`judgment_plan_aggregator`、`renderer` | 分别吸收到 sufficiency gate、Judgment Assembler 和 presentation service |

首个三-cell 的默认映射为：

| Cell | Primary Specialist | Conditional Specialist |
| --- | --- | --- |
| `demand_signal` | `product_technology_analyst` | `industry_supply_chain_analyst`、`fundamental_analyst` |
| `revenue_capture` | `fundamental_analyst` | `product_technology_analyst`、`market_valuation_analyst` |
| `thesis_counterevidence` | `risk_counterevidence_analyst` | `industry_supply_chain_analyst`、`market_valuation_analyst` |

Primary 不代表每次无条件调用。Lead 必须根据当前 observation、gap、冲突和信息增益给出激活原因；Conditional Specialist 只有在跨领域问题真实出现时才进入。每个 Cell 先限制一个 Primary 路径，同一 InvestigationBranch 最多并行两个回答不同问题的 Specialist；不得用全量 fan-out 模拟 Multi-Agent。

Lead 到 Specialist 的 `SpecialistTaskVersion` 至少绑定：

- exact ResearchRun、DecisionSurface、Cell 和 InvestigationBranch refs；
- decision question、current thesis、known contradiction 和 gap；
- scoped Evidence/Numeric/Graph/context refs；
- allowed Agent/Skill/Tool/Data profile；
- expected output schema、budget、deadline 和 stop condition；
- causation event、attempt 和 idempotency refs。

Specialist 只能提交结构化 `JudgmentProposal / EvidenceRequest / CounterevidenceProposal / RepairRequest / TypedStop`。事实和数字必须引用 admitted Evidence 或 exact Numeric artifact；没有足够依据时必须返回 gap 或 `cannot_infer`，不能直接改变 Cell disposition。

Specialist 之间不得私下互调或建立隐藏循环。所有 handoff 统一经过：

```text
Lead dispatch
  -> SpecialistTaskVersion
  -> role-scoped ContextEngine projection
  -> SpecialistResultVersion
  -> Runtime/schema/permission validation
  -> Lead ObservationAssessment
  -> next dispatch / repair / stop
```

Specialist 可以建议调用另一专业角色，但只有 Lead 能创建下一份 SpecialistTask。Judgment Assembler 负责确定性合并结构，不拥有研究判断 authority；跨 Cell synthesis 仍由 Lead 负责。

Workbench 主界面显示 Lead plan、活动 Cell/branch、selected Specialist、selection reason、Skill/Data capability、结果类型和下一动作；完整输入输出进入 Inspect。UI 不采用平级 Agent 聊天室，也不把内部自由文本 CoT 作为产品事件。

`L2-D03` 只冻结产品拓扑和 handoff 语义，不证明现有 17-node graph 已完成该重构；Runtime adapter、role reclassification、结构化 task/result 和动态激活仍待实现与测试。

#### 3.5.9 `L2-D04`：Skill Runtime Contract

`L2-D04-SkillRuntimeContract` 已冻结为 `versioned_runtime_consumed_skillpacks_with_policy_separation`。Skill 是版本化研究方法，不是 Agent、Tool、权限、记忆或独立执行入口；仅存在 Markdown、静态 role binding 或 Prompt 中出现 Skill 名称，均不能证明 Skill 已进入产品 Runtime。

FIN 0.1 将现有 Skill 语义分为：

| 分类 | 代表内容 | Runtime 规则 |
| --- | --- | --- |
| Mandatory Policy | evidence boundary、Writer no-source、Numeric exactness、permission/budget/tool boundary、forbidden substitution | 始终生效，不允许 Lead 或用户选择关闭 |
| Role Core Skill | Lead planning、Fundamental、Product/Technology、Supply Chain、Market/Valuation、Risk/Counterevidence、Writer、Verifier | 随 exact AgentDefinitionVersion 固定加载 |
| Optional Task Skill | investment workflow、evidence sufficiency、relationship/graph、后续 numeric reconciliation/source triangulation | Lead 只能从 ExecutionProfile allowlist 中按任务选择 |
| Service/Operator Rule | operator tool use、coverage reflection、judgment aggregation、renderer | 分别迁入 Operator policy、Sufficiency Gate、Judgment Assembler、Presentation Service |

`SkillDefinitionVersion` 至少包含：

- skill id、version、canonical digest、purpose 和 maturity status；
- applicable Agent/Cell/task types 和 preconditions；
- required context、input/output schemas 和 expected structured fields；
- capability requirements、forbidden actions 和 budget hint；
- compatibility、prompt template ref、eval refs 和 supersession lineage。

Skill 的 capability requirements 只能约束“需要什么”，不能授予 Agent 原本没有的 Tool、数据、模型、网络、预算或 Evidence authority。

每份 `SpecialistTaskVersion` 默认绑定一个 Role Core Skill，并最多允许两个 Optional Task Skills。Lead 可以因 observation 改变下一份 Task 的 Optional Skill、在前置条件不满足时跳过，或建议用户批准 Profile 外能力；Lead 不得在运行中编写 Skill、切换未冻结版本、加载 allowlist 外 Skill或借 Skill 扩大权限。

Runtime 必须按以下流程消费 Skill：

```text
Lead selects admitted Agent
  -> Runtime resolves exact Core Skill
  -> Lead proposes Optional Skills from profile allowlist
  -> compatibility / precondition / permission preflight
  -> ContextEngine compiles bounded SkillPackVersion
  -> SpecialistTask binds SkillPack digest
  -> Agent submits structured result
  -> Runtime validates required output fields and boundaries
  -> EventTrace records selected / injected / consumed / skipped
```

ContextEngine 不得无差别拼接完整 Skill Markdown。`SkillPackVersion` 只包含当前任务所需的方法步骤、输出要求和不可绕过边界，并绑定 source Skill versions、编译策略、token budget 和 content digest。冲突优先级固定为 `Mandatory Policy > Agent permission > Role Core Skill > Optional Task Skill`；不可解析冲突必须 fail closed。

三个 Cell 的初始 Skill 映射为：

| Cell | Primary Method | Optional Method |
| --- | --- | --- |
| `demand_signal` | Product/Technology Analysis | Evidence Sufficiency、Relationship/Graph |
| `revenue_capture` | Fundamental Analysis | Numeric Reconciliation、Evidence Sufficiency |
| `thesis_counterevidence` | Risk/Counterevidence | Relationship/Graph、Source Triangulation |

Supporting Specialist 始终使用自己的 Role Core Skill，不因进入另一个 Cell 而伪装成该 Cell 的 Primary Specialist。

Skill Runtime 完成证明必须同时包括：exact Skill version/digest 进入 Task、SkillPack 被真实输入消费、EventTrace 留痕、输出满足 Skill 结构要求、不同 observation 触发不同 Optional Skill，以及前置条件不满足时产生明确 skip。Registry validation、Markdown 存在、Prompt 字符串匹配或单一 happy path 均不构成完成证明。

`L2-D04` 只冻结 Skill 语义和选择边界；现有 `research_skills.py` 仍主要是静态 Markdown loader，尚未实现上述 SkillDefinitionVersion、SkillPack、preflight 或 runtime-consumption proof。

## 4. 历史资产裁决

| 裁决 | 资产 | 要求 |
| --- | --- | --- |
| retain | Agent 角色、权限、source family、model profile、budget、Skill 内容、Writer no-source、Verifier、information economy | 保留语义和已有测试价值 |
| refactor | 固定 graph 顺序、大型 mutable state、role-to-prompt 静态绑定、自由文本 handoff | 改成 Case/cell/gap 驱动和 exact refs |
| absorb | historical LangGraph、P36 deterministic service、DeepSeek/provider runner | 作为 Runtime 内部 execution adapters，不再各自成为产品入口 |
| retire_after_parity | 绕过 Runtime 的独立 top-level runner、重复 planning/synthesis 主线、只服务旧入口的 projection | 只有迁移 parity 和 rollback 验证后才退役，不先删除 |

`relationship_graph` registry/test 分歧必须在 runtime freeze 时按当前 TECH owner contract 裁决；不得为了单纯测试变绿而静默删能力或无依据更新测试。

## 5. 下一步建设顺序

### L2-EP0：Runtime 与配置对象冻结

1. 冻结 `Fin01ResearchRuntime` protocol；
2. 冻结 `ExecutionProfileVersion / ResearchRun / ArtifactManifest / EventTrace`；
3. 冻结 `AgentDefinitionVersion / SkillDefinitionVersion` 最小运行字段；
4. 完成历史资产 retain/refactor/absorb/retire manifest；
5. 裁决 registry/test 的 `relationship_graph` 分歧。

完成条件：合同可被 deterministic 与 Agent 两类 adapter 同时实现，且不存在第二套 Case/Run authority。

### L2-EP1：Deterministic compatibility adapter

1. 把现有 `P36LocalResearchService` 包装成 `deterministic_fallback`；
2. 保持当前只读、零模型、零网络、零 evidence promotion 边界；
3. 为现有 numeric/judgment/workpaper/writer projection 分配统一 Run/Artifact/Trace identity；
4. Workbench 通过 Runtime 读取同等结果，不直接调用独立研究链。

完成条件：现有产品能力无回归，UI 明确显示 `deterministic_fallback`。

### L2-EP2：Historical LangGraph shadow adapter

1. 将历史 graph 放入 `agent_fixture_shadow` adapter；
2. 输入从旧 query/state 改为 exact Case、DecisionSurface 和 selected cell refs；
3. 输出只允许结构化 result、typed stop、artifact refs 和 events；
4. 禁止直接修改 canonical Case、Evidence、Judgment 或 release head。

完成条件：同一 fixture Case 可以选择 deterministic 或 Agent shadow profile，并产生不同但可比较的 Run。

### L2-EP3：Agent / Skill Registry runtimeization

1. 将静态 Agent contract 映射为 `AgentDefinitionVersion`；
2. 将 Skill 从 Markdown loader 升级为带 purpose、precondition、input/output、applicability、permission、budget 和 compatibility 的 `SkillDefinitionVersion`；
3. Runtime 必须记录 selected、injected、invoked、skipped 及原因；
4. Workbench 可选择允许的 profile/capability，但不能越过权限、Evidence Gate 或 writer no-source。

完成条件：Agent/Skill 使用可以从 exact Run 重建，仓库存在不再等同于产品已激活。

### L2-EP4：三-cell 动态 Agent 主链

首轮只迁移：

1. 需求真实性与持续性；
2. 价值与利润捕获；
3. 瓶颈、反证与 What-Would-Change。

每个 cell 由 Lead 根据 cell status、gap、budget 和 stop condition 动态决定：选择哪个 Agent、加载哪个 Skill、是否提交 EvidenceRequest、是否请求 repair、何时 bounded stop。不得为了模拟动态性而把原固定节点改名后继续全量顺序执行。

完成条件：三个 cell 都真实经过 Agent profile，且各自具有可解释的 selection、handoff、result 和 stop trace。

### L2-EP5：Workbench 统一入口与运行呈现

1. Workbench 只能经统一 Runtime start/read/cancel/reopen；
2. 运行页显示 plan、cell、agent、skill、tool/graph event、typed stop 和 next action；
3. 不展示模型私有 CoT；
4. deterministic fallback 与 Agent 结果使用不同且持续可见的运行标签；
5. 用户不能把 fallback 结果误认为模型/Agent research。

完成条件：浏览器刷新后仍能恢复 exact Run、模式和 trace。

### L2-EP6：从三-cell 扩展到 10-20 cells

只有第二层 Gate 全部通过后，才按 DecisionSurface priority 扩展剩余 P36 cells。扩展只复用既有 Runtime、Agent、Skill 和 trace 合同，不为每个 cell 新建 runner 或 graph family。

完成条件：10-20 cells 共用同一调度和 artifact lineage；新增 cell 主要是 policy/config/skill 差异，不复制主链。

## 6. 第二层完成 Gate

以下条件必须同时成立：

1. Workbench 发起的 canonical Case 产生唯一 `ResearchRun`；
2. 三个目标 cells 真正经过 `agent_fixture_shadow` 或经单独授权的 Agent profile；
3. Agent、Skill、Tool、Graph 都有 `selected / invoked / completed / failed-or-skipped` 结构化记录；
4. Specialist 只提交结构化 judgment、EvidenceRequest、repair proposal 或 typed stop；
5. Writer 没有 source/tool 权限，也没有从 Runtime 外补事实；
6. deterministic fallback 与 Agent 运行在 UI、API 和 artifacts 中明确区分；
7. 所有结果可追溯到同一个 Case、Run、输入版本和配置 digest；
8. deterministic compatibility、Agent shadow three-cell、stale/wrong-profile/unauthorized 和 browser restore 最小测试通过。

通过本 Gate 只证明第二层 fixture/shadow/internal 产品主线完成，不证明真实 Agent 研究质量、Agentic Search、RG1、Human Senior Review、release 或 production readiness。

## 7. 防循环停止规则

- 不先把历史 LangGraph 全部修到“理想状态”再接产品；先完成三-cell runtime vertical；
- 只修阻断三-cell current path、身份一致性、权限/数据安全或 truth-in-presentation 的问题；其余历史 graph 问题进入 named backlog；
- 不因审计新增 graph family、runner family、gate family 或全量 adversarial matrix；
- 三-cell Gate 未通过前不扩展第四个 Agentic cell；
- deterministic fallback 必须持续可用，Agent adapter 失败不得破坏现有 Case；
- 一项问题在同一根因上重复出现时，停止局部补丁，回到 adapter/contract 根因处理；
- paid model、network、commercial data、真实业务 Case mutation和 release 继续要求独立授权。

## 8. 下一层接口

第二层只负责谁被调度、使用什么 Skill、如何 handoff 和如何记录运行。第三层负责 `EvidenceRequest -> Tool Planner -> RAG/SQL/Graph candidates -> Evidence Gate/typed gap`。第二层不得把旧检索函数包装成 specialist 私有工具，也不得自行决定 evidence promotion。

第三层讨论草稿：`FIN_0_1_LAYER_3_AGENTIC_SEARCH_EVIDENCE_EXECUTION_DRAFT_20260719.zh-CN.md`。
