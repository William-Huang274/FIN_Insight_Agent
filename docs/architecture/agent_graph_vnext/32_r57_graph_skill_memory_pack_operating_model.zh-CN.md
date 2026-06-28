# R57 Graph / Skill / Memory Pack Operating Model

日期：2026-06-28

状态：framework-level / living technical registry。本文是 R57 的 active source of truth，用于定义 FinSight 后续如何把知识图谱、专家 skill、机构/用户/团队经验记忆做成可插拔、可版本化、可评测、可审批、可替换的能力资产。

关联文档：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md`
- `docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md`
- `docs/architecture/agent_graph_vnext/31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md`
- `docs/worklog/integrated_execution_p_series/405_product_intelligence_graph_current_structure_audit.md`

参考出处：

- Hermes Agent Skills System: `https://hermes-agent.nousresearch.com/docs/user-guide/features/skills`
- Hermes Agent Working with Skills: `https://hermes-agent.nousresearch.com/docs/guides/work-with-skills`
- MCP Specification: `https://modelcontextprotocol.io/specification/2025-06-18`
- LangGraph checkpoint / interrupt / durable execution 设计参考见 R56。

## 1. 定位

R56 解决的是 runtime stack：任务如何持续运行、暂停、恢复、调工具、注入上下文和导出 trace。

R57 解决的是能力资产层：

```text
GraphPack  决定“世界如何被结构化”
SkillPack  决定“专家如何使用这些结构化世界做判断”
MemoryPack 决定“机构、团队、用户偏好和历史经验如何影响任务规划”
```

三者必须单独成文，而不是合并进 R56：

- R56 是 runtime / harness / ContextEngine / ToolGateway。
- R57 是 graph / skill / memory 的可插拔资产模型。
- R58 才是 SQL / RAG / retrieval / index 的数据服务优化。
- R60 负责 eval / observability / failure / release gate。

## 2. 核心目标

最终系统必须允许企业内部根据业务经验快速替换、增加或禁用图谱和 skill：

```text
Tenant A: 使用半导体深度产品图谱 + 自有供应链 playbook + 自有投委会模板
Tenant B: 使用银行信贷/存款/资本充足率图谱 + 风控 playbook + 合规输出模板
Tenant C: 使用医药 pipeline / trial / approval 图谱 + 临床专家 skill
```

但可插拔不等于让模型自由改生产系统。正确模式是：

```text
Agent / Eval 提出 GraphPatch / SkillPatch / MemoryPatch
 -> Staging Registry
 -> deterministic eval
 -> gold / regression eval
 -> human approval
 -> canary
 -> promote active version
```

生产环境禁止未经评测和审批的自我改写。

## 3. 总体架构

```text
Enterprise Workflow / User Task
 -> ResearchTask
 -> Research Lead
    -> reads TenantMemory / UserMemory / TeamExperienceMemory
    -> reads Graph Capability Registry
    -> selects GraphPacks
    -> selects SkillPacks
    -> creates WorkpaperPlan
 -> Specialist Workstreams
    -> consume assigned GraphPacks / EvidencePacks
    -> execute SkillPack contract
    -> write WorkpaperEvents / ClaimCards / GapCards / ThesisDrivers
 -> LeadReview
    -> audits coverage / authority / gap / cross-specialist conflict
    -> triggers targeted repair or human question
 -> Deliverable / Dashboard / Quant
    -> consume approved WorkpaperPack only
 -> Eval / Learning Loop
    -> proposes patch candidates
    -> runs behavior eval
    -> human-approved promotion
```

## 4. GraphPack

### 4.1 定义

`GraphPack` 是一个可插拔的图谱能力包，不只是 nodes / edges 文件。

```text
GraphPack
- graph_id
- version
- owner
- tenant_scope
- node_schema
- edge_schema
- source_adapters
- parser / normalizer
- authority_policy
- query_api
- evidence_citation_policy
- allowed_claims
- forbidden_claims
- graph_projection_policy
- eval_suite
- migration / deprecation rule
```

### 4.2 图谱类型

当前和后续主要 GraphPack：

| GraphPack | 当前状态 | 主要用途 | 边界 |
| --- | --- | --- | --- |
| `ProductIntelligenceGraph` | 已 materialized / runtime wired | 产品、规格、部署、竞品、供应链、产品 KPI exact / bounded signal | spec/deployment/proxy 不能冒充 SKU 收入、销量、ASP、份额 |
| `ProductRelationshipGraph` | 已 materialized | competition / substitute / supply-chain / deployment context | 同 family 边多数是候选关系，不是竞争胜负证明 |
| `ResearchGraphStore` | 已 materialized | company / product / fact / signal / graph edge 统一关系层 | source-evidence-only 不自动提权 |
| `CapitalFundingOwnershipGraph` | 部分已有 pack / graph | 债务、融资、持仓、资本动作、ownership / insider | 13F 等滞后信息不能冒充实时资金流 |
| `SecondaryMarketCapitalFeedbackGraph` | R54 framework | 资金面、流动性、估值 price-in、期权/期货、跨资产 | market expectation / positioning signal，不是基本面 exact |
| `ThemeToExpressionGraph` | R23 framework | theme -> beneficiary / enabler / loser / supply-chain expression | 需要 exposure confidence，不能直接当买卖建议 |
| `ResearchExperienceGraph` | R53/R57 framework | 历史研究路径、失败经验、有效判断模式 | 经验不是事实证据，只能影响规划和警示 |
| `WorkpaperGraph` | R52/R56 framework | WorkpaperEvent、Claim、Gap、Review、Approval、Artifact 的任务图 | 任务状态图，不是外部事实图 |

### 4.3 GraphPack Authority

所有图谱边必须显式声明 authority：

```text
exact_fact_authority
bounded_thesis_driver_authority
context_or_navigation_authority
planning_or_gap_only
visualization_only
forbidden_for_claim
```

示例：

```text
NVDA H100 spec -> technical_fact_authority
xAI deployment news -> deployment_signal_authority
NVDA vs AMD same GPU family -> competitive_context_candidate
NVDA H100 revenue from product page -> forbidden_for_claim
```

## 5. SkillPack

### 5.1 定义

当前 `src/sec_agent/prompts/skills/*.md` 已经是 skill 原型，但最终应升级成结构化 `SkillPack`。

```text
SkillPack
- skill_id
- version
- owner
- role
- task_modes
- required_graph_capabilities
- required_inputs
- optional_inputs
- allowed_tools
- forbidden_tools
- output_schema
- reasoning_policy
- evidence_authority_policy
- forbidden_claim_policy
- examples
- negative_examples
- eval_suite
- model_route
- context_budget
- approval_policy
```

### 5.2 专家 SkillPack 层级

基础专家：

- `ResearchLeadPlanningSkill`
- `FundamentalAnalysisSkill`
- `ProductTechnologyAnalysisSkill`
- `IndustrySupplyChainSkill`
- `MarketValuationSkill`
- `CapitalFundingOwnershipSkill`
- `RiskCounterevidenceSkill`
- `MemoLogicPlanningSkill`
- `DeliverableComposerSkill`
- `QuantTranslatorSkill`

行业专家 overlay：

- `SemiconductorAIInfrastructureAnalystOverlay`
- `BankingFinancialsAnalystOverlay`
- `HealthcarePipelineAnalystOverlay`
- `EnergyUtilitiesAnalystOverlay`
- `RetailCPGChannelAnalystOverlay`
- `SoftwareCloudDeveloperAnalystOverlay`

机构自定义 overlay：

- `TenantInvestmentCommitteeStyleOverlay`
- `TenantPreferredPeerGroupOverlay`
- `TenantComplianceBoundaryOverlay`
- `TenantValuationMethodOverlay`
- `TenantDeliverableTemplateOverlay`

### 5.3 SkillPack 示例

`ProductTechnologyAnalysisSkill` 必须明确：

```text
required_graph_capabilities:
- ProductIntelligenceGraph
- ProductRelationshipGraph
- SourceAuthorityCoverage

required_inputs:
- ProductEvidencePack
- product source-family bundle
- company / product family scope

outputs:
- ProductProfileSummary
- ProductSpecComparison
- CustomerDeploymentSignals
- ProductPerformanceProxyClaims
- ProductKpiExactClaims
- ProductRelationshipClaims
- ProductGapLedger

forbidden:
- benchmark -> sales
- product page -> market share
- customer deployment -> revenue
- same-family comparable -> confirmed competitive win/loss
- channel availability -> sell-through / inventory exact
```

## 6. MemoryPack

### 6.1 定义

`MemoryPack` 不是事实库。它是规划偏好、经验、上下文习惯、团队知识和历史失败模式。

```text
MemoryPack
- memory_id
- scope: user / team / tenant / project / company / watchlist / task
- version
- retention_policy
- provenance
- confidence
- staleness
- supersession
- injection_policy
- retrieval_policy
- privacy_boundary
- eval_feedback
```

### 6.2 Memory 类型

| MemoryPack | 用途 | 禁止 |
| --- | --- | --- |
| `UserPreferenceMemory` | 用户语言、格式、常看行业、风险偏好 | 不能变成事实证据 |
| `TenantResearchMethodMemory` | 机构研究框架、投委会标准、估值偏好 | 不能覆盖 source authority |
| `TeamExperienceMemory` | 历史有效流程、失败路径、常见 parser/source gap | 不能未经 eval 改 skill |
| `CompanyCoverageMemory` | 对某公司的历史覆盖、已知 source routes、常见 gap | 不能替代最新数据 |
| `WatchlistMemory` | 监控假设、触发条件、近期事件状态 | 需要 staleness / invalidation |
| `QuantValidationMemory` | 因子假设、回测结果、失效场景 | 不能直接生成交易建议 |

### 6.3 借鉴 Hermes 的边界

Hermes 的启发点：

- memory 存短事实和用户/项目偏好；
- skills 存长流程和工具路径；
- agent 可提出 skill 更新；
- human approval gate 可控制写入。

FinSight 的约束更强：

- 金融研究结论必须可审计；
- memory 不能绕过 evidence authority；
- skill / graph 自迭代必须先进入 staging；
- 所有 promotion 必须有 eval 记录和审批记录。

### 6.4 Memory 分层

R57 不能只定义抽象 `MemoryPack`。它必须覆盖从单节点临时 scratch 到机构级长期知识的完整生命周期。

| 层级 | 生命周期 | 写入者 | 读取者 | 典型内容 | 默认注入策略 | 禁止 |
| --- | --- | --- | --- | --- | --- | --- |
| `NodeScratchMemory` | 单节点内，节点结束后默认丢弃 | 当前 node | 当前 node | 中间推理摘要、工具分页状态、局部去重 key | 不进入全局上下文 | 禁止写入事实库或跨 run 复用 |
| `RunMemory` | 单个 ResearchTask / run | Research Lead / Specialist / ToolGateway | 当前 run 内 actor | 本轮目标、已查源、失败工具、gap、repair history、human comments | 通过 WorkpaperEvent / run audit 可回放 | 禁止污染 project / tenant memory |
| `ProjectMemory` | 项目级，跨 run | LeadReview / human reviewer / approved consolidation job | 同项目任务 | 项目目标、覆盖范围、已批准假设、常用同业、历史底稿结论 | 按 project scope 检索注入 | 禁止覆盖最新 evidence |
| `CompanyMemory` | 公司级，跨项目 | approved consolidation job | company scoped tasks | 公司 source routes、常见披露结构、历史 coverage notes、已知 public boundary | ticker 命中时候选注入 | 禁止当最新事实；必须标 as-of |
| `WatchlistMemory` | watchlist / monitor 生命周期 | Watchlist task / human reviewer | watchlist / alert tasks | thesis drivers、触发条件、待观察事件、已失效 catalyst | watchlist 命中时注入触发条件 | 禁止输出未复核旧催化剂 |
| `TeamExperienceMemory` | 团队级，长期但可淘汰 | eval / reviewer / postmortem | Research Lead / specialist planner | 有效研究路径、失败样本、常见 parser/source gap、行业常见误判 | 只作为 planning / warning | 禁止直接支持事实 claim |
| `OrgPrivateMemory` | tenant / org 级 | tenant admin / approved human | tenant 内授权 actor | 机构研究标准、合规边界、内部模板、内部 source policy | tenant policy 注入 | 禁止跨 tenant 泄露 |
| `GlobalPlaybookMemory` | 全局或产品维护级 | platform maintainer | 所有授权 tenant | 通用 playbook、行业方法论、系统级 failure patterns | 低频、压缩注入或按 skill 召回 | 禁止覆盖 tenant-specific policy |

关键判断：

- `NodeScratchMemory` 和 `RunMemory` 偏 execution state。
- `ProjectMemory`、`CompanyMemory`、`WatchlistMemory` 偏研究连续性。
- `TeamExperienceMemory` 和 `GlobalPlaybookMemory` 偏方法论和失败经验。
- `OrgPrivateMemory` 是企业差异化能力资产，必须有 tenant isolation。

### 6.5 Memory Metadata Contract

所有可持久化 memory 都必须带元数据，不能只存自由文本。

```text
MemoryRecord
- memory_id
- memory_pack_id
- scope_type: node / run / project / company / watchlist / team / org / global
- scope_key
- tenant_id
- owner_actor
- source_event_ids
- provenance_refs
- authority_class: preference / procedure / experience / coverage_note / policy / warning / stale_fact_reference
- confidence
- created_at
- effective_from
- expires_at
- ttl_policy
- staleness_policy
- supersedes_memory_ids
- superseded_by_memory_id
- permission_policy
- injection_policy
- promotion_status: scratch / candidate / staged / active / deprecated / rejected
- eval_refs
- human_approval_ref
```

必须解决的问题：

- `provenance`：这条 memory 从哪个 run、哪个 WorkpaperEvent、哪个 human comment 或 eval failure 来。
- `authority`：这条 memory 是偏好、流程、经验、覆盖说明还是政策，不能混成事实。
- `TTL / staleness`：公司事实、watchlist catalyst、政策和 source route 都可能过期。
- `supersession`：新年报、新 parser、新 source adapter 或 human correction 可以替代旧 memory。
- `tenant / permission`：机构私有 playbook、内部 source 和用户偏好不能跨 tenant 注入。
- `promotion gate`：从 run 内候选进入 project / company / org / global memory 必须评测或人工批准。

### 6.6 Memory Promotion Rules

不同 memory 层的晋升条件不同：

```text
NodeScratchMemory -> RunMemory
条件：影响当前 run 后续节点，且可由 WorkpaperEvent 回放。

RunMemory -> ProjectMemory
条件：human reviewer 确认该经验对同一项目后续任务有复用价值。

RunMemory -> CompanyMemory
条件：与某公司 source route、披露结构、公开源边界或历史 coverage 相关，并有 as-of / provenance。

RunMemory -> TeamExperienceMemory
条件：多 case 重复出现，或 eval/postmortem 证明是可复用失败模式 / 有效流程。

TeamExperienceMemory -> GlobalPlaybookMemory
条件：跨 tenant / 跨行业有效，经 regression / negative cases 验证，并通过 platform approval。

ProjectMemory / CompanyMemory / WatchlistMemory -> deprecated
条件：新披露、新事件、新 parser、新人工纠正或 TTL 到期。
```

禁止的晋升：

- 单次模型自述不能晋升为 global playbook。
- 一次成功查询路径不能直接晋升为 firm-wide standard。
- 用户随口纠正不能直接覆盖 source authority。
- 旧财报事实不能无 as-of 注入为当前事实。

### 6.7 ContextEngine Lifecycle Contract

ContextEngine 不只是 `select some context`，而是可回放的上下文生命周期控制器。

```text
ContextEngine
- resolve(task, actor, node, tenant, scope)
- select(resolved_context, budget, policy)
- compress(selection, target_actor, target_task)
- inject(compressed_context, node_input)
- write(node_output, events, memory_candidates)
- consolidate(run_or_project_scope)
- invalidate(scope, reason)
```

#### resolve

解析当前任务可以访问哪些上下文：

- task / run state；
- WorkpaperEvent ledger；
- GraphPack / SkillPack / MemoryPack registry；
- role-specific EvidencePack；
- tenant / user / project / company / watchlist memory；
- tool / graph / retrieval permissions。

输出必须包括：

```text
ContextResolution
- candidate_context_refs
- permission_decisions
- excluded_context_refs
- exclusion_reasons
- tenant_boundary
- actor_boundary
```

#### select

按 actor、任务阶段和预算选择上下文：

- Research Lead 需要目标、coverage、registry、gap、high-level packs。
- Specialist 需要 role-specific pack、required graph refs、source boundaries。
- Memo / Composer 只能读 approved WorkpaperPack / MemoLogicPlan / JudgmentState。
- Verifier 需要 claim refs、evidence refs、forbidden claims、source authority。

输出：

```text
ContextSelection
- selected_refs
- dropped_refs
- selection_reason
- budget_used
- risk_flags
```

#### compress

压缩不是随意摘要，必须保留：

- source refs；
- graph pack / skill pack version；
- claim authority；
- forbidden claim boundary；
- as-of / snapshot / provenance；
- dropped-row reasons。

R57 只定义上下文压缩生命周期和压缩质量门控；检索召回、rerank、chunk expansion、query rewrite 等策略放到 R58。这里的目标不是替代 RAG，而是保证进入 prompt 的上下文既足够短，又不丢掉审计、权限和事实边界。

#### Context Compression Policy

上下文必须先分类，再压缩。不同类型的上下文允许不同的压缩方式：

| Context class | 示例 | 压缩策略 | 禁止事项 |
| --- | --- | --- | --- |
| `must_keep_exact` | 财务 exact row、Product-KPI exact、表格坐标、citation、source authority、as-of | 不压缩正文事实，只注入 row / claim / evidence ref 和必要字段 | 禁止模型摘要改写数字、单位、期间、公司、产品、来源 |
| `reference_only` | 大型 filing、PDF、网页、产品文档原文 | 不直接注入全文，只注入 artifact ref、locator、section ref | 禁止把未读取全文伪装成已读结论 |
| `extractive_compress` | SEC 段落、IR deck 段落、网页片段、新闻片段 | query / task focused extractive compression，保留原句片段和 refs | 禁止把抽取片段改写成更强结论 |
| `abstractive_handoff` | 长程 run 状态、agent 协作记录、修复历史、失败原因 | Codex / Claude Code-style handoff summary | 禁止把过程摘要当证据 |
| `structured_pack_compress` | WorkpaperPack、MemoLogicPlan、JudgmentState、ProductEvidencePack | 按 schema 裁剪、排序、聚合，只保留当前 actor 必需字段 | 禁止丢 required field、authority field、gap field |
| `memory_hint` | ProjectMemory、TeamExperienceMemory、GlobalPlaybookMemory | 短提示或按需检索；默认低频注入 | 禁止覆盖 source evidence 或 tenant policy |
| `drop` | 与当前 actor / task 无关、越权、过期、重复上下文 | 记录 dropped ref 和 reason | 禁止静默丢弃 required context |

基础原则：

- exact facts 只能被引用，不能被摘要替代。
- 过程状态可以压缩，但必须标为 process / handoff context。
- 业务判断用的核心证据必须保留 refs、authority、as-of 和 forbidden boundary。
- 压缩后的文本不能提升原始证据权重。
- 如果压缩无法保留关键字段，应降级为 ref-only injection，并让目标 actor 按需读取原文或结构化 row。

#### ContextCompressionArtifact

每次压缩必须产出可审计 artifact，而不是只返回一段压缩文本：

```text
ContextCompressionArtifact
- compression_id
- run_id
- node_id
- actor_id
- target_task
- source_context_refs
- compression_method
- context_class
- preserved_claim_ids
- preserved_evidence_refs
- preserved_memory_refs
- preserved_graph_refs
- preserved_authority_fields
- preserved_as_of_fields
- dropped_refs
- dropped_reasons
- numeric_preservation_check
- citation_preservation_check
- authority_boundary_check
- permission_boundary_check
- stale_context_check
- compressed_text_or_ref
- compressed_context_hash
- created_at
```

`compressed_context_hash` 必须进入 `ContextInjectionPlan`，这样同一次 run 后续能够复盘：模型看到的不是原始聊天历史，而是哪个压缩版本。

#### Compression Quality Gate

压缩通过条件：

- `must_keep_exact` 的 numeric / unit / period / product / issuer / citation 字段必须 100% preserved。
- 所有压缩 artifact 必须记录 dropped refs 和 dropped reasons。
- 压缩结果不得删除 `forbidden_claim_boundary`、`commercial_gap`、`bounded_gap`、`source_boundary`。
- 如果 source authority、tenant permission、as-of、snapshot id 缺失，压缩不得进入 active injection。
- Memo / Composer 只能消费 approved WorkpaperPack、MemoLogicPlan、JudgmentState、approved ClaimCards 的压缩视图，不得直接消费未经选择的大量 raw evidence。
- Verifier 必须能比较 compressed context 与 source refs，检查是否出现 compression hallucination。

#### 可借鉴模式

- Codex / OpenAI-style compaction：适合把长程任务过程压成 handoff state，降低长会话成本和延迟。
- Claude Code-style focused compact：适合在进入新阶段前由 Lead 指定压缩重点，比如只保留当前修复目标、未完成 checklist、关键文件和失败命令。
- Claude memory / file memory：适合 MemoryPack 按需读写，而不是把全部长期记忆加载进 prompt。
- LLMLingua / LongLLMLingua-style prompt compression：适合对已筛选片段做二次 token 压缩，但不能用于改写 exact fact。
- GraphRAG / RAPTOR-style hierarchy summary：适合行业格局、供应链、产品关系这类全局问题，但属于 R58/R59 的 retrieval / graph query 侧能力；R57 只要求这些 summary 被注入时有 refs、version 和 authority boundary。

#### inject

注入计划必须可回放：

```text
ContextInjectionPlan
- injection_id
- run_id
- node_id
- actor_id
- target_model
- selected_context_refs
- compression_artifact_ids
- compressed_context_hash
- prompt_slot_map
- excluded_context_refs
- budget
- created_at
```

任何重要输出都必须能回答：

```text
这个 node 当时看到了哪些上下文？
这些上下文经过了哪种压缩？
哪些上下文被丢弃了？
为什么丢弃？
有没有越权注入？
有没有过期 memory 注入？
压缩是否丢掉了数字、citation、authority 或 forbidden boundary？
```

#### write

节点输出不能直接写长期 memory。写入先进入候选：

```text
MemoryCandidate
- candidate_id
- source_event_id
- proposed_scope
- proposed_memory_type
- payload
- reason
- risk_flags
- required_approval
```

#### consolidate

定期或 run 结束后做 memory consolidation：

- 合并重复 memory；
- 提升可复用经验；
- 标记 stale；
- 生成 SkillPatch / GraphPatch / MemoryPatch proposal；
- 写入 eval / approval queue。

#### invalidate

必须能主动失效：

- 新披露覆盖旧披露；
- source adapter 修复后旧 public boundary 失效；
- human reviewer 纠正；
- tenant policy 更新；
- eval 发现 memory 导致错误输出；
- TTL 到期。

### 6.8 ContextEngine 与 WorkpaperEvent 的关系

ContextEngine 不应成为黑盒 prompt 拼接器。每次注入、写入、晋升、失效，都应写入可审计事件：

```text
WorkpaperEvent / RunAuditEvent
- context_resolved
- context_selected
- context_compressed
- context_injected
- memory_candidate_written
- memory_consolidated
- memory_promoted
- memory_invalidated
- context_policy_violation
```

这样前端和审计才能看到：

- 为什么某个 specialist 没看到某条证据；
- 为什么某条经验被注入；
- 为什么某条历史记忆被废弃；
- 哪条 memory 影响了 Research Lead 的计划；
- 哪条 memory 导致了 eval failure。

### 6.9 Context / Memory 风险和解决办法

| 风险 | 解决办法 |
| --- | --- |
| memory 把旧事实当新事实 | 所有 company/watchlist memory 必须带 as-of、TTL、staleness gate |
| 用户偏好覆盖证据边界 | memory authority 不得高于 source authority |
| tenant 私有经验泄露 | tenant_id、permission_policy、injection audit 必须硬门控 |
| skill/graph 自迭代污染生产 | patch 先 staging，必须 eval + human approval |
| context 太多导致 token 浪费 | ContextEngine select/compress 必须记录 dropped refs 和 budget |
| specialist 没看到关键 pack | required_graph_capability gate + missing required context eval |
| bad memory 长期存在 | eval-linked invalidation + supersession + memory review queue |

## 7. Registry 体系

### 7.1 Graph Capability Registry

记录所有图谱能力：

```text
graph_id
version
status: active / staging / deprecated / disabled
authority_modes
supported_questions
forbidden_claims
required_data_artifacts
query_surface
consumer_roles
eval_suite_id
last_validated_at
tenant_overrides
```

### 7.2 Skill Registry

记录所有 skill：

```text
skill_id
version
status
role
required_graph_capabilities
input_contract
output_contract
tool_permission_profile
model_route
context_budget
eval_suite_id
negative_case_suite_id
tenant_overlays
```

### 7.3 Memory Registry

记录可注入 / 可检索 memory：

```text
memory_pack_id
scope
owner
retention
privacy
injection_priority
staleness_policy
supersession_policy
linked_workpaper_events
linked_eval_feedback
```

## 8. 自迭代与审批流

禁止：

```text
模型发现一个新流程 -> 直接改 active skill
模型发现一个新关系 -> 直接写 active graph
模型从用户纠正中学到偏好 -> 直接污染所有 tenant
```

允许：

```text
Run / Eval / Human Review
 -> LearningEvent
 -> SkillPatch / GraphPatch / MemoryPatch proposal
 -> Staging Registry
 -> offline deterministic eval
 -> gold regression / negative eval
 -> human approval
 -> canary
 -> promote
```

Patch 类型：

- `SkillPatch`: prompt / contract / examples / forbidden claims / output schema。
- `GraphPatch`: node / edge / authority / source route / parser / query API。
- `MemoryPatch`: user preference / tenant preference / project lesson / stale memory removal。
- `PlaybookPatch`: 行业 schema、指标重点、source route、commercial gap boundary。

## 9. 专业性保障

专业性不能靠模型自由发挥，必须靠以下结构：

### 9.1 Domain Ontology

必须统一：

- issuer / security / exchange / filing / reporting period；
- statement / line item / metric / unit / period role；
- product / product family / SKU / spec / architecture / generation；
- customer / supplier / channel / deployment / contract / order；
- debt / ownership / holder / insider / corporate action；
- factor / universe / signal / label / backtest。

### 9.2 Industry Playbook

每个行业 playbook 至少包括：

- business model；
- key financial statement items；
- product / operating KPI；
- source hierarchy；
- peer universe；
- valuation framework；
- key debate questions；
- common mistakes；
- commercial tracker gap；
- required GraphPacks；
- required Skill overlays。

### 9.3 Claim Authority

必须区分：

```text
financial exact fact
company-disclosed operating exact
product technical fact
customer deployment signal
supply-chain signal
industry/macro context
market expectation signal
capital feedback signal
weak discovery lead
commercial tracker gap
```

### 9.4 Behavior Eval

未来 skill eval 不能只检查 prompt 是否注入，必须检查行为：

- Research Lead 是否选对 GraphPack；
- Specialist 是否使用 required GraphPack；
- 是否把 proxy 冒充 exact；
- 是否错过可修 retrievable gap；
- 是否按行业 playbook 组织分析；
- Memo 是否使用 MemoLogicPlan 而不是拼 ClaimCard；
- Graph edges 是否按 authority 正确进入 thesis / caveat / visualization。

## 10. 企业可拔插模式

### 10.1 Tenant Override

企业可以覆盖：

- playbook；
- peer group；
- valuation method；
- report template；
- internal source adapter；
- approved source list；
- forbidden claim policy；
- compliance phrase policy；
- human approval threshold。

但不能覆盖：

- source provenance required；
- exact fact value/unit/period/citation gate；
- parser/eval gate；
- audit ledger；
- forbidden secret handling；
- production approval flow。

### 10.2 插拔流程

```text
Upload / register new pack
 -> schema validation
 -> dry-run on fixture cases
 -> authority-boundary negative tests
 -> tenant reviewer approval
 -> staged activation
 -> canary task
 -> active routing
```

## 11. 与现有代码的映射

当前已有基础：

- `src/sec_agent/research_skills.py`: prompt skill registry 原型。
- `src/sec_agent/prompts/skills/`: markdown skill 原型。
- `src/sec_agent/product_intelligence_graph.py`: ProductIntelligenceGraph。
- `src/sec_agent/product_intelligence_runtime.py`: PIG runtime adapter。
- `src/sec_agent/product_spec_pack.py`: ProductSpecPack。
- `src/sec_agent/research_graph_store.py`: ResearchGraphStore。
- `src/sec_agent/dimension_evidence_portfolio.py`: DimensionEvidencePortfolio。
- `src/sec_agent/agent_runtime_consumption_contract.py`: role-specific EvidencePack contract。
- `src/sec_agent/context_engine.py`: ContextEngine v0.1。
- `src/sec_agent/mcp_contracts.py` / `mcp_tool_registry.py`: MCP-facing tool contract 原型。

当前缺口：

- 没有统一 `GraphCapabilityRegistry`。
- 没有结构化 `SkillPackRegistry`。
- 没有 `MemoryPackRegistry` 和 memory promotion / invalidation / staleness gate。
- skill eval 仍偏注入/边界测试，不足以证明专家行为。
- graph / skill / memory patch 还没有 staging / approval / canary 生命周期。

## 12. R57 后续 Demand 草案

| Demand ID | 目标 | 状态 |
| --- | --- | --- |
| `R57-D01-graph-capability-registry` | 建 GraphPack registry schema 和当前图谱 inventory | planned |
| `R57-D02-skillpack-registry` | 把现有 markdown skill 包成结构化 SkillPack contract | planned |
| `R57-D03-memorypack-registry` | 定义 NodeScratch / Run / Project / Company / Watchlist / Team / Org / GlobalPlaybook memory tiers 和 metadata contract | planned |
| `R57-D04-lead-graph-skill-selector` | Research Lead 基于 GraphPack + SkillPack registry 生成计划 | planned |
| `R57-D05-specialist-required-pack-gate` | Specialist 必须声明 required graph pack consumption | planned |
| `R57-D06-learning-patch-lifecycle` | SkillPatch / GraphPatch / MemoryPatch staging + approval flow | planned |
| `R57-D07-behavior-eval-suite` | 图谱使用、skill 行为、memory 注入的行为级 eval | planned |
| `R57-D08-tenant-overlay-contract` | 企业自定义 skill/playbook/template/source policy overlay | planned |
| `R57-D09-contextengine-lifecycle-contract` | 实现 resolve / select / compress / inject / write / consolidate / invalidate 合同和 replayable injection plan | planned |
| `R57-D10-memory-promotion-invalidation-gates` | 实现 TTL、staleness、supersession、tenant permission、promotion gate 和 eval-linked invalidation | planned |
| `R57-D11-context-compression-policy` | 实现 context class 分类、exact/ref-only/extractive/handoff/structured/memory/drop 压缩策略和 actor-specific context budget | planned |
| `R57-D12-context-compression-artifact` | 为每次压缩生成 `ContextCompressionArtifact`，并把 `compression_artifact_ids` 接入 `ContextInjectionPlan` | planned |
| `R57-D13-compression-quality-gates` | 实现 numeric/citation/authority/permission/staleness/forbidden-boundary preservation gate 和 compression hallucination verifier | planned |

## 13. Acceptance Gates

R57 framework 完成标准：

- 每个 active GraphPack 都能说明用途、authority、消费者、禁止结论和 eval。
- 每个 SkillPack 都能说明 required inputs、required graphs、output schema、allowed tools 和 forbidden claims。
- MemoryPack 明确不会成为事实证据，只影响规划、偏好和经验提醒。
- Memory 层级覆盖 NodeScratch、Run、Project、Company、Watchlist、Team、OrgPrivate、GlobalPlaybook，并且每条可持久化 memory 都有 provenance、authority、TTL、staleness、supersession、tenant/permission 和 promotion_status。
- ContextEngine 的 resolve / select / compress / inject / write / consolidate / invalidate 必须有可审计事件；每次注入必须生成可 replay 的 `ContextInjectionPlan`。
- ContextEngine 压缩必须先按 context class 分类；exact facts 不得被摘要替代，只能以 row / claim / evidence ref 方式注入。
- 每次压缩必须生成 `ContextCompressionArtifact`，记录 source refs、preserved refs、dropped refs、dropped reasons、压缩方法和 hash。
- 压缩质量 gate 必须证明 numeric、citation、authority、permission、staleness、forbidden boundary 未被压缩丢失。
- Research Lead planning 能基于 registry 选择 graph / skill，而不是硬编码 source family。
- Specialist output 能回溯到使用过的 GraphPack / SkillPack version。
- 任意 node 输出只能写 memory candidate，不能直接写 active long-term memory。
- 任意 skill / graph / memory 更新都先进入 staging，不得直接污染 active runtime。
- 至少有一组 negative eval 证明错误 graph edge、错误 memory、错误 skill 不能进入最终判断。

## 14. 当前结论

FinSight 现在已经有多个强图谱和 pack，但它们仍主要是数据/运行时对象；skill 也已经有 markdown prompt 原型，但还不是企业可插拔的专业能力资产。

R57 的目标不是“再写几个 prompt”，而是把图谱、skill、memory 都变成：

```text
versioned
testable
tenant-overridable
approval-gated
auditable
runtime-selectable
```

这一步完成后，企业才能按自己的行业经验替换 skill，按自己的数据源替换图谱，并通过 eval 和审批保证专业性，而不是把所有能力长期硬编码在一个固定 agent graph 里。
