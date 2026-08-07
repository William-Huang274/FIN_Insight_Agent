# TECH_00：Agentic Research 技术文档总索引

日期：2026-07-09
最近修改：2026-08-07

状态：技术文档拆分索引。本文只整理 PRD、P36/P37 记录和当前代码资产之间的工程边界，不表示 runtime 修复完成，不表示已运行 paid LLM、true full-chain、MCP server、source ingestion 或 parser promotion。

## 1. 背景

本轮扫过以下 source-of-truth：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/worklog/product_strategy/117_p36_codex_as_paid_model_manual_full_chain_dogfood.md`
- `docs/worklog/product_strategy/118_p37_git_hygiene_codebase_audit_prd_alignment.md`
- `docs/architecture/agent_graph_vnext/37_agentic_research_harness_codebase_audit_and_technical_doc_split.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/external_pattern_registry.jsonl`
- `docs/project_os/financial_research_method_registry.jsonl`

结论：2026-07-12 PRD 已将产品主定位升级为 Institutional Research Control and Memory System。技术主干不能再以 Report、Chat、单次 TaskRun 或某个 Agent 为 aggregate root；必须以 `InstitutionalResearchCase` 串联 DecisionSurface、Evidence/Numeric/Judgment、Workpaper、Review、Artifact、Memory、Monitoring 与 Supersession，同时保留各模块单一业务真相 owner。

因此本轮修订为：

```text
TECH_01 负责 ResearchCase 研究语义 + agentic research loop + decision surface 主干。
TECH_02 负责 agentic search + evidence promotion/rejection 业务语义。
TECH_03-11 负责地址/记忆、数值、判断、运行时、上下文、subagent、provenance/workbench、eval 和 monitoring。
```

## 2. Stable Object Graph

T0 的定位是 architecture constitution：规定 vNext 研究系统中哪些对象是稳定一等对象、哪些 TECH 文档拥有这些对象、旧文档与新文档冲突时以哪里为准。T0 不是 runtime 实现，也不是 PRD 的重复摘要。

稳定对象图如下：

```text
InstitutionalResearchCase
  -> CaseControlState / CaseVersion
  -> UserTask / TaskModeDecision / LegacyTaskRunBinding
  -> AgenticResearchLoop
  -> DecisionSurfaceContract
  -> DecisionSurfaceCell
  -> EvidenceRequest / DomainOperatorTask / SubagentTask
  -> ToolInvocation / Observation
  -> EvidenceCandidate / RejectedCandidate / PromotionDecision / EvidenceRecordVersion
  -> NumericFact / MetricDefinitionVersion / ModelInputSnapshot / NumericProgramRun
  -> NumericFactView / ProtectedNarrativeDraft
  -> CellEvidencePack
  -> DomainCellJudgmentPack / JudgmentVersion / JudgmentDelta / WhatWouldChangeProgram
  -> AdjudicatedDecisionCell / CellDependencyEdge
  -> GapRecord / RepairTicket / RepairAttempt
  -> CorrectionObjective / CorrectionClosureReceipt
  -> WorkpaperEventLedger / WorkpaperPack
  -> DecisionSurfaceAssembly / LeadReviewDecision
  -> DecisionSurfacePack
  -> WriterAdmissionDecision / FrozenDecisionSurfaceSnapshot
  -> WriterBrief / AudienceScopedPresentationModel
  -> ArtifactVersion / ArtifactProvenanceManifest
  -> WorkbenchReviewAction / DecisionAttestation / ReleaseRecord
  -> Trace / EvalSubject / EvalRun / FailureAttribution
  -> RuntimeReleaseGateDecision / ShadowComparisonRecord / LaneCutoverDecision
  -> ImprovementProposal / RepairTicket

Longitudinal memory and accountability:
  InstitutionalMemoryRef / MemoryWriteCandidate / MemoryInvalidationEvent
  ActorSnapshot / AccountabilityEvent / HumanAIAccountabilityGraph
  FollowUpRequest / RefreshRequest / ThesisDelta / SupersessionGraph

Cross-cutting registries:
  AgentDefinitionVersion / PromptBundleVersion / SkillVersion
  GraphOntologyVersion / WorkflowPolicyVersion / ProviderPolicyVersion
  ModelCapability / ModelSelectionDecision

Human collaboration:
  CaseRoleAssignment / ResearchAssignment / ReviewAssignment
  CommentThread / Mention / ReviewSLA / DelegationGrant / DeliveryReceipt

Long-running monitoring:
  Watchlist / CoverageSubscription / MonitoringRule / TriggerObservation
  -> ThesisDeltaAssessment / AlertDecision / WatchlistDigest / NotificationDelivery
```

## 2.1 Owner Constitution（2026-07-12）

每个 stable object 只能有一个 `business truth writer`。可以另有 `physical persistence owner` 和多个 read/index/projection consumer，但物理落库不转移业务定义权，消费者不得创建第二个 current head。

| 对象域 | Business truth writer | Physical persistence / execution | Read / index / projection consumers |
| --- | --- | --- | --- |
| ResearchCase / CaseControl / DecisionSurface / Gap / Workpaper / LeadReview | TECH_01 | TECH_06 Event/State Store | TECH_03、05、07、09、10、11 |
| EvidenceRequest / PromotionDecision / Rejection / typed gap | TECH_02 | TECH_06 invocation/event；TECH_03 candidate/index store | TECH_01、03、04、05、09、10 |
| SourceDocument / CandidateBundle / Memory address / PIT reconstruction | TECH_03 | TECH_03 source/index/memory store；TECH_06 ingestion events | TECH_02、07、09、10、11 |
| NumericFact / MetricDefinition / NumericProgramRun / AssumptionSet | TECH_04 | TECH_04 numeric store；TECH_06 run/artifact event | TECH_02、05、09、10、11 |
| DomainCellJudgment / WWC / CellDependency / Judgment supersession | TECH_05 | TECH_06 artifact/event store | TECH_01、03、07、09、10、11 |
| TaskRun / WorkUnit / Attempt / EventEnvelope / Permission / Budget / ActorSnapshot / AccountabilityEvent | TECH_06 | TECH_06 | 所有 TECH 只读消费 |
| ContextRequirement / SelectionDecision / InjectionPlan / Compaction | TECH_07 | TECH_06 event + TECH_07 context artifact store | TECH_06、08、10 |
| AgentDefinition / PromptBundle / handoff / coordination delta | TECH_08 | TECH_06 registry/event store | TECH_01、06、07、10 |
| OntologyVersion / Graph verified identity / memory taxonomy | TECH_03 | TECH_03 index store + TECH_06 rollout events | TECH_02、04、05、07、08、10 |
| WorkflowPolicyVersion / Agent-Skill configuration semantics | TECH_08 | TECH_06 registry/permission/rollout | TECH_01、07、09、10 |
| Source/SearchProviderCapabilityVersion / SourceProviderPolicyVersion | TECH_02 | TECH_06 registry/event store | TECH_03、06、08、10 |
| ModelRuntimeProviderPolicyVersion / ModelSelectionDecision | TECH_06 | TECH_06 registry/event store | TECH_07、08、10 |
| CaseRoleAssignment / ResearchAssignment | TECH_01 | TECH_06 event/SLA/notification | TECH_07、08、09、10 |
| ReviewAssignment / CommentThread / Mention / ReviewSLA | TECH_09 | TECH_06 event/SLA/notification | TECH_01、10、11 |
| SurfaceClaim / WorkbenchReview / DecisionAttestation / ArtifactProvenanceManifest / Release | TECH_09 | TECH_06 artifact/event/release transaction | TECH_01、03、07、10、11 |
| Eval / FailureAttribution / RuntimeReleaseGate / ImprovementProposal | TECH_10 | R60 Eval Store + TECH_06 execution events | TECH_00A、各 owner TECH |
| Watchlist / MonitoringRule / TriggerObservation / Alert / ThesisDelta | TECH_11 | TECH_06 schedule/cursor/event store | TECH_01、03、05、09、10 |

特殊边界：

- `InstitutionalResearchCase` 是 aggregate identity/ref graph，不是万能大表；Evidence、Numeric、Judgment、Review 仍由各自 owner 写业务真相。
- TECH_03 拥有 memory address、freshness、TTL、PIT 和 invalidation index；AcceptedFact/Judgment/ReviewerDecision 的原始业务状态仍由 TECH_02/04/05/09 提供 immutable refs。
- TECH_07 只决定一次模型调用注入什么，不拥有长期 memory truth；`MemoryWriteCandidate` 必须提交 TECH_03 registry。
- TECH_09 定义 approval/release 业务语义；TECH_06 执行 exact-version transaction、保存 event/hash 和 invalidation。
- TECH_02 拥有 evidence promotion；TECH_04 对 numeric claim 提供不可被 LLM override 的 numeric hard gate；TECH_05 不得自行晋升 evidence。
- WriterBrief 的研究边界来自 TECH_01，context compilation 来自 TECH_07，presentation/artifact 业务语义来自 TECH_09；Writer 永久 no-source。
- `ActorSnapshot` / `AccountabilityEvent` 由 TECH_06 写执行事实；`DecisionAttestation` / `ArtifactProvenanceManifest` 由 TECH_09 写审核发布语义；TECH_03 只建历史索引，TECH_10 评完整性。
- Point 01 `LegacyTaskRunBinding`、`LegacyCanonicalIdentityMap` 是 TECH_06 migration control objects；`ShadowComparisonRecord` 和 `LaneCutoverDecision` 是 TECH_10 quality/release semantics 的 first-slice specialization。它们不新增产品业务域。

所有后续 TECH 修改都应扩展这张对象图，而不是创造平行的任务面、证据面或 writer 面。

## 3. 修订后的 TECH 划分

| 编号 | 文档 | 负责问题 | 不负责 |
| --- | --- | --- | --- |
| `TECH_01` | `TECH_01_agentic_research_loop_decision_surface_contract.zh-CN.md` | InstitutionalResearchCase 研究语义、CaseControl、`plan-act-observe-classify-repair-stop` 总控、DecisionSurface、Gap/Repair、Workpaper、LeadReview | TaskRun 执行持久化、具体检索/parser、artifact release |
| `TECH_02` | `TECH_02_agentic_search_evidence_toolgateway_sourcehunter.zh-CN.md` | agentic search、EvidenceRequest、Tool Registry/Planner、SourceHunter、Evidence Gate、promotion/rejection/typed gap | source/index 存储、numeric 算法、领域判断、writer |
| `TECH_03` | `TECH_03_document_metadata_rag_knowledge_layer.zh-CN.md` | DocumentMetadataIndex、source/structure/candidate、RAG/KB、repair cache、memory address/PIT/freshness/supersession index | evidence promotion、业务判断、context selection、模型直接回答 |
| `TECH_04` | `TECH_04_numeric_program_trace_parser_promotion.zh-CN.md` | Structured Numeric Fact Compiler、Parser / Numeric Agent、exact row selection、DerivedMetricRegistry、NumericProgramTrace、unit/period/row sanity | 文档发现、因子显著性验证、业务叙事、domain cell 结论 |
| `TECH_05` | `TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md` | Fundamental/Product/Graph/Market/Risk 的 domain evidence operator 和 decision-cell projection | 工具执行治理、writer 表达、全局 durable state |
| `TECH_06` | `TECH_06_durable_harness_runtime_permission_state.zh-CN.md` | durable TaskRun/WorkUnit/Event、Case execution binding、permission/HITL、ActorSnapshot/AccountabilityEvent、budget/replay | ResearchCase 业务判断、Evidence promotion、context 内容选择、approval 业务语义 |
| `TECH_07` | `TECH_07_context_engine_skills_compaction_governance.zh-CN.md` | ContextRequirement/Selection/Injection、skills 渐进式披露、compaction/governance decay | 长期 memory truth、工具执行、evidence promotion、Workbench UI |
| `TECH_08` | `TECH_08_subagents_as_tools_handoff_contract.zh-CN.md` | subagents-as-tools、Agent/Prompt/Skill contracts、handoff/delta、独立上下文、配置化角色边界 | 自由 roleplay、共享真相写入、模型/权限执行决策 |
| `TECH_09` | `TECH_09_trace_provenance_workbench_artifact_consistency.zh-CN.md` | Provenance、Workbench review、SurfaceClaim、ArtifactConsistency、DecisionAttestation、ArtifactProvenanceManifest、release/stale | research truth 生成、trajectory 自动修复、工具 fallback |
| `TECH_10` | `TECH_10_trajectory_eval_self_improvement.zh-CN.md` | Quality Ledger、R1-R4、trajectory/failure attribution、provider-swap、longitudinal/accountability eval、runtime candidate-vs-baseline release 和 governed improvement | research truth、单份 artifact approval、R60 physical implementation、自动合并/训练/放宽 gate |
| `TECH_11` | `TECH_11_watchlist_monitoring_alert_runtime.zh-CN.md` | Watchlist 长期状态、coverage subscription、incremental observation、thesis delta、alert/no-alert、dedupe/suppression、digest 和 notification 语义 | 单次 deep research、Evidence Gate、renderer、通用生产监控 |

完整的 PRD -> TECH -> R-series -> runtime -> product surface 映射见 `TECH_00A_prd_tech_runtime_product_surface_coverage_matrix.zh-CN.md`。该矩阵区分 `legacy_planned`、`runtime_partial`、`product_partial` 和 `owner_gap`，防止把旧设计或 fixture 写成新合同已运行。

## 4. TECH Owner Coverage Matrix

| PRD / 记录要求 | Owner TECH | 说明 |
| --- | --- | --- |
| Stable Object Graph / TECH owner coverage | `TECH_00` | 规定 vNext 稳定对象、对象归属和跨 TECH 边界 |
| InstitutionalResearchCase lifecycle | `TECH_01`, `TECH_06`, `TECH_03`, `TECH_09`, `TECH_11` | TECH_01 拥有研究生命周期；TECH_06 持久化执行；TECH_03 索引历史；TECH_09 审批发布；TECH_11 触发 refresh |
| Institutional Memory / PIT reconstruction | `TECH_03` + `TECH_02/04/05/09` | TECH_03 拥有地址/freshness/supersession；业务 owner 提供 immutable fact/judgment/review refs |
| Human-AI Accountability / OA identity | `TECH_06`, `TECH_09`, `TECH_03`, `TECH_10` | Actor/事件、DecisionAttestation/manifest、历史索引和完整性评测共用同一责任链 |
| Agent/Skill/Graph/Workflow configuration governance | `TECH_03`, `TECH_06`, `TECH_08`, `TECH_10` | TECH_03 拥有 ontology/verified graph identity；TECH_08 拥有 Agent/Skill/Workflow 语义；TECH_06 执行 registry/permission/rollout；TECH_10 评测；hard invariants 不可关闭 |
| Team assignment / review collaboration | `TECH_01`, `TECH_09`, `TECH_06`, `TECH_10` | TECH_01 研究 assignment；TECH_09 review/comment/SLA 语义；TECH_06 持久化通知；TECH_10 评 workflow value |
| Provider-neutral capability frontier | `TECH_02`, `TECH_06`, `TECH_08`, `TECH_10` | 模型/搜索/数据/parser provider 通过 capability policy、permission、fallback 和 shadow eval 接入 |
| Longitudinal follow-up / selective refresh / cross-artifact reapproval | `TECH_01`, `TECH_03`, `TECH_05`, `TECH_09`, `TECH_11`, `TECH_10` | 同一 Case 的 affected-cell refresh、judgment delta、artifact stale、reapproval 和 R4 eval |
| Capability maturity lifecycle | `TECH_00`, `TECH_10` | TECH_00 定义阶段；TECH_10 用 eval / trace 证明成熟度迁移 |
| Supersession / source-of-truth | `TECH_00` + worklog | PRD、TECH、Project OS、旧节点文档冲突时的优先级和回写规则 |
| Agentic Research Operating System | `TECH_01`, `TECH_06`, `TECH_07`, `TECH_08`, `TECH_10` | TECH_01 定义研究 loop；TECH_06-10 落运行时、上下文、subagent 和 eval |
| bounded ReAct / 不暴露原始 CoT | `TECH_01`, `TECH_02`, `TECH_06`, `TECH_10` | 记录 `reasoning_summary` / `action_rationale` / `observation_summary`，不持久化私有 CoT |
| Agentic Search | `TECH_02`, `TECH_03`, `TECH_04` | EvidenceRequest-driven search；RAG/KB 只是 candidate；parser/numeric 决定 exact row 是否可晋升 |
| Agentic Research | `TECH_01`, `TECH_05`, `TECH_08`, `TECH_09` | DecisionSurfaceContract-driven research；domain operator 输出 cell pack；Workbench 按 cell review |
| Writer no-source / Presentation Agent | `TECH_01`, `TECH_07`, `TECH_08`, `TECH_09` + 现有 R55 | Writer 只消费冻结的 DecisionSurfacePack / WriterBrief / DeliverablePlan；TECH_09 拥有 canonical presentation、SurfaceClaim、verification/review/release contract，R55 拥有 renderer / RenderJob / format-specific generation |
| SourceHunter / supervisor supplement boundary | `TECH_02`, `TECH_03`, `TECH_09` | P36 supplement ledger 是 input queue，不是 runtime success evidence |
| DocumentMetadataIndex | `TECH_03` | metadata 进入 retrieval filter，不只是 reranker feature |
| Data foundation source map | `TECH_03`, `TECH_02`, `TECH_04` | TECH_03 组织 source / snapshot / index / graph / memory；TECH_02 调用 SourceHunter / ToolGateway；TECH_04 负责 parser / numeric promotion |
| Public capital-market source expansion / PIT panel | `TECH_03`, `TECH_04`, 现有 R53/S9 | TECH_03 组织历史行情、security master、corporate actions、ownership、short、credit、derivatives context、macro vintage 和 non-US official source；TECH_04 生成可复算 features；R53/S9 只在 PIT/leakage gate 后做因子验证 |
| Futures / options / other derivatives | `TECH_03`, `TECH_04`, `TECH_05`, 现有 R53/S9 | TECH_03 保存 DerivativeInstrumentMaster / ObservationPIT；TECH_04 计算 curve/IV/OI/COT 等 bounded metrics；TECH_05 按 sector/cell 投影 expectation/risk/regime；R53/S9 验证 factor，不默认全任务注入 |
| External news / public statements / policy events / social discourse | `TECH_03`, `TECH_02`, `TECH_05`, `TECH_09`, `TECH_10` | TECH_03 建模 ExternalSignalCandidate / SocialSourceSnapshot；TECH_02 取源、账号归因和 gate；TECH_05 只投影 bounded catalyst / risk / policy / narrative / user-feedback signal；TECH_09 审冲突与 provenance；TECH_10 评估舆情采样和失真 |
| DerivedMetricRegistry / NumericProgramTrace | `TECH_04`, `TECH_09` | TECH_04 注册公式、输入资格、as-of/period/scope/lag policy 并生成 trace；TECH_09 在 artifact / Workbench / verifier 中消费 |
| 模型研究判断 / material fact 写入 / 受保护叙事 | `TECH_04`, `TECH_05`, `TECH_06`, `TECH_08`, `TECH_09`, `TECH_10` | TECH_04 拥有 NumericFactView 与 material span；TECH_05 拥有研究判断；TECH_06 持久化 correction attempt；TECH_08 单源编译 agent 合同；TECH_09 渲染和 artifact verification；TECH_10 评 closure、paired quality 与 anti-template。跨域合同见文档 38，不创建新 TECH owner。 |
| Domain specialists 减少人格化、增加 operator | `TECH_05`, `TECH_08` | TECH_05 定义 domain evidence operator；TECH_08 定义 subagent-as-tool 调用 |
| Structured agent coordination / parallel version invalidation | `TECH_08`, `TECH_06`, `TECH_07`, `TECH_10` | TECH_08 定义 causal coordination envelope、input dependency manifest、pack change set 和选择性失效语义；TECH_06 执行版本决策；TECH_07 重编译 context；TECH_10 评估误停、漏停和 rebase drift |
| Active What-Would-Change / counterfactual falsification | `TECH_01`, `TECH_05`, `TECH_06`, `TECH_09`, `TECH_10` | TECH_05 定义决定性变量、反事实测试和领域判断；TECH_01 控制 re-adjudication；TECH_06 持久化 attempts；TECH_09 独立展示；TECH_10 评估证伪质量 |
| Research methods / workpaper exemplars / research graph | `TECH_03`, `TECH_05`, `TECH_07`, `TECH_09` | TECH_03 保存 memory / pointer；TECH_05 编译为 operator rubric 和 cell projection；TECH_07 注入 skill；TECH_09 审 artifact / review |
| MCP / ToolGateway / sandbox / permission | `TECH_02`, `TECH_06` | TECH_02 定义工具能力和 evidence tool loop；TECH_06 定义 runtime permission gate |
| Durable execution / HITL / replay | `TECH_06` | RuntimeFacade、RunEvent/EventEnvelope、TaskRun/WorkUnit/Attempt、checkpoint、immutable ArtifactVersion、PermissionSnapshot、dead-letter、partial rerun / replay / fork |
| Context rot / governance decay / self-compaction | `TECH_07`, `TECH_03`, `TECH_10` | TECH_07 定义 ContextRequirement/Candidate/Snapshot/SelectionDecision/Block/InjectionPlan/ExpansionRequest/RoleContextPolicy 和 context-side admission/compaction；TECH_03 拥有长期 memory lifecycle/invalidation/forget index；TECH_10 评估 reconstruction、drift、stale leak、role contamination、governance decay 和 context economy |
| Trace / Provenance / claim clickthrough | `TECH_09`, `TECH_10` | TECH_09 定义 lineage；TECH_10 评估 lineage 完整度 |
| ArtifactConsistencyGraph | `TECH_09` | 对 canonical claims、numbers、citations、versions、wording boundaries、chart/table bindings 和 disclosure policy 做跨 memo / PPT / Excel / dashboard 一致性约束 |
| Workbench decision-cell / deliverable review | `TECH_09`, `TECH_01`, 现有 R55/R59 | TECH_01 定义 cell；TECH_09 定义 decision matrix、claim/provenance、artifact consistency、repair/review queue 和 release timeline；R59 落前后端 UI/API |
| Quality eval / failure attribution / runtime release / self-improvement | `TECH_10` + 现有 R60 | TECH_10 统一 EvalSubject、mode、Gold/Oracle、Metric/Gate、trajectory、causal attribution、candidate-baseline release 和 ImprovementProposal；R60 落 runner/store/dashboard/incident；不自动合并或放宽 gate |
| Research-to-Quant | 现有 R53/S9 + `TECH_04`, `TECH_05`, `TECH_09` | 不重复拆 TECH；TECH_04 提供 source-backed derived features，R53/S9 构建 PIT dataset / validation / FactorCard，TECH_05 投影为 bounded quant support/counterevidence，TECH_09 审计 lineage 和 review |
| Deliverable Studio / dashboard | 现有 R55/S7 + `TECH_09` | 不重复拆 TECH；ArtifactConsistencyGraph 和 Workbench review 补齐一致性 |
| Task modes / mode routing | `TECH_01`, `TECH_06`, `TECH_10` | TECH_01 定义 TaskModeDecision 和升级/降级；TECH_06 执行 mode budget/runtime；TECH_10 评模式误路由和单位价值 |
| Workpaper / shared research state | `TECH_01`, `TECH_06`, `TECH_09` + 现有 R52/R59 | R52 旧合同迁移为 vNext WorkpaperEvent/Pack；DecisionSurfacePack 是 Workpaper 判断组件，不是完整协作状态 |
| Pack-level LeadReview / writer admission | `TECH_01`, `TECH_05`, `TECH_09` | 跨 cell 冲突、coverage、thesis path 和 narrative completeness 通过后才冻结 writer input |
| Unified Gap lifecycle | `TECH_01`, `TECH_02`, `TECH_03`, `TECH_06`, `TECH_09` | GapRecord 是缺口身份；RepairTicket/Attempt 是行动；支持 dedupe、reopen、supersession 和 bounded disclosure |
| Data Room intake lifecycle | `TECH_03`, `TECH_04`, `TECH_06`, `TECH_09` + R58/R59 | upload/ACL/quarantine/parse/review/reprocess/delete 进入统一 source/provenance/runtime contract |
| Deterministic valuation / scenario modeling | `TECH_04`, `TECH_05`, `TECH_09` | TECH_04 校验输入与计算 trace；TECH_05 定义业务/估值语义；TECH_09 投影 assumption/scenario/sensitivity |
| Agent / prompt / model registry | `TECH_06`, `TECH_08`, `TECH_10` | Agent/Prompt 定义、模型能力/选择、权限/成本/fallback 和 eval baseline 都必须版本化 |
| Agent Information Economy | `TECH_06`, `TECH_07`, `TECH_08`, `TECH_10` | usage/selection/handoff/yield 汇入统一 metric registry 和 failure attribution |
| Watchlist / monitoring / alert | `TECH_11` + `TECH_01-10` | 独立持续运行态；复用 evidence、WWC、durable、Workbench 和 eval，不冒充实时全覆盖 |

## 5. Capability Maturity Lifecycle

所有能力必须显式标注成熟度，避免把“已讨论”误写成“已实现”：

| Stage | 含义 | 可接受证据 |
| --- | --- | --- |
| `documented` | 只在 PRD / worklog / TECH 中有设计描述 | dated doc section |
| `contract_draft` | 已有对象、字段、边界或状态机草案 | TECH contract |
| `fixture_proven` | 已有小样例或离线 fixture 验证 | fixture input/output, snapshot |
| `runtime_injected` | 已注入 runtime prompt / config / schema | code diff, config diff |
| `node_level_consumed` | 单节点或子图实际消费该 contract | trace, unit/integration run |
| `paid_artifact_proven` | paid-model 或 manual dogfood 产物证明可用 | dogfood artifact, reviewer notes |
| `dogfood_accepted` | 经 Workbench / Lead / human review 通过，并沉淀为默认路径 | accepted ledger entry |

TECH 文档默认只代表 `contract_draft`。除非文档中列出运行证据，否则不能推断为 runtime 已具备。

## 6. Supersession / Source-of-Truth 规则

当前 source-of-truth 分层：

- PRD 负责产品形态与目标体验，最新日期的 PRD section 优先于旧讨论。
- `TECH_00` 负责技术文档拆分、对象归属和 owner coverage matrix。
- `TECH_01` 到 `TECH_11` 负责各自模块 contract，模块内冲突以最新日期的对应 TECH 为准。
- `docs/worklog/product_strategy/117...`、`118...`、`119...` 负责过程记录和决策轨迹，不作为最终 contract 的唯一来源。
- `docs/project_os/current_context_pack.zh-CN.md`、capability ledger、root-cause ledger 负责当前状态、阻塞项与历史债务，不覆盖已更新 TECH contract。
- 旧 R52/R53/R55/R58/R59/R60、S7-S10 和 P36 节点文档保留为设计、实现资产和问题来源，必须经 `TECH_00A` crosswalk 后才能被 vNext owner 继承；不能直接视为 vNext runtime contract。

变更规则：

- 聊天中达成的新架构结论必须回写到对应 TECH 和 worklog。
- 如果某项设计改变对象归属或跨 TECH 边界，必须同步更新 `TECH_00`。
- 如果某项设计只改变局部字段、状态或工具策略，更新对应 TECH，并在 worklog 记录原因。
- 不允许只在 runtime prompt 中改变 contract 而不更新 TECH。

## 7. 新增 TECH 判定与不重复拆分原则

不新增独立的 `Agentic Search / Agentic Research` TECH，因为这会把核心 loop 从主干文档里抽走，导致 `TECH_01` 又退回普通 schema 文档。修订后：

- `Agentic Research` 是 `TECH_01` 的主线；
- `Agentic Search` 是 `TECH_02` 的主线；
- `ReAct` 的 runtime 持久化、上下文隔离、subagent handoff、trajectory eval 分别落在 `TECH_06/07/08/10`；
- `RAG / KB` 的角色变化落在 `TECH_03`。
- 新增 TECH 的标准是“出现无法归属到现有 stable object graph 的新运行时对象”，而不是“某个理念很重要”。

2026-07-11 审计确认 Watchlist / Monitoring 满足该标准：它拥有跨任务长期状态、subscription、cursor、incremental observation、alert/no-alert、dedupe/suppression、digest 和 notification，不是单次 research loop 或 dashboard projection。因此新增 `TECH_11_watchlist_monitoring_alert_runtime.zh-CN.md`；这不改变 TECH_01/02 对 Agentic Research / Search 的所有权。

## 8. 当前边界

- 这些 TECH 文档及 TECH_00A 覆盖矩阵是 architecture / contract draft；
- 没有实现 runtime 代码；
- 没有运行 paid LLM、true full-chain、MCP server、source ingestion、parser promotion 或 Workbench replay；
- 不得把这些文档视为 P36 blockers 已关闭。

## 9. 2026-07-12 Post-Refactor Split Audit

更新后的顶层拆分结论为 `architecture_split_pass / implementation_spec_split_required`：TECH_01-11 已覆盖 ResearchCase、Evidence、Knowledge/Memory、Numeric、Judgment、Durable Runtime、Context、Subagents/Configuration、Artifact/Review、Eval 和 Monitoring，没有出现必须新增 TECH_12 的独立业务状态域。

但 TECH owner 文档是 architecture constitution/contract，不应直接承担全部实现细节。进入具体 migration slice 前，需按 owner 下拆 child implementation specs，至少覆盖：

- canonical machine-readable schema / ID / version / supersession；
- command/API/event envelope、producer/consumer 和 idempotency；
- SQL/ObjectStore/index/queue physical ownership 与 transaction boundary；
- permission/retention/license/tenant policy；
- legacy adapter/migration/cutover/rollback；
- deterministic fixture、integration eval 和 R1-R4 gate。

建议使用 `TECH_XXA/XXB` 或 `RFC/API/DB/EVAL` 子文档，不新增平行 business owner。Point 01 首批已冻结 `SCHEMA_01_point01_canonical_object_registry`、`DB_01_point01_canonical_store_transaction_boundary`、`API_01_point01_runtime_command_event_contract` 和 `MIGRATION_01_point01_legacy_canonical_cutover`。完整审计见 `docs/architecture/repository/TECH_POST_REFACTOR_SPLIT_AND_UPDATE_AUDIT_20260712.zh-CN.md`。

## 10. Release Operating Model 与 TECH 消费关系（2026-07-17）

TECH owner、capability maturity、产品 release channel 和 ResearchCase outcome 是正交坐标：

| 坐标 | 回答的问题 | Source of truth |
| --- | --- | --- |
| TECH owner | 谁定义业务对象和 invariant | TECH_00 / TECH_01-11 |
| Capability maturity | 单项能力实现到哪一层 | TECH_00 / TECH_10 / capability ledger |
| Release channel / L0-L4 | 当前版本可以给谁使用 | PRD / ReleaseContract / TECH_10 |
| Case outcome / R1-R4 | 某个研究 Case 的结果到哪一层 | TECH_10 / Workbench review |
| Production readiness | 是否取得真实企业部署准入 | Release/Deployment gate |

不得再用一个 `complete` 字段覆盖以上状态。`foundation_alpha` 可以在 L1 关闭而保持 `production_readiness=not_admitted`；一个 R3 artifact 也不能把全产品提升到 L4。

产品版本不按 TECH 编号顺序实施。每个 ReleaseContract 以用户纵向工作为主线，引用所需 TECH owners；每个 Point 必须声明 `consuming_release_id`。没有当前/下一版本 consumer 的 platform work 默认进入 backlog，不得抢占当前产品列车。

发布对象归属：

- PRD/Product 定义 `ProductReleaseIntent`、目标用户、工作流和产品 claim；
- TECH_10 定义 `ReleaseContract`、`ReleaseGatePolicy`、`ReleaseEvidenceManifest` 和 runtime/config `ReleaseGateDecision` 的质量语义；
- TECH_06 持久化 release execution、approval snapshot、event 和 rollback execution facts；
- TECH_09 决定 exact research artifact 的 internal/client-safe/published 语义；
- 各业务 TECH owner 对 release slice 中的对象和 hard invariant 继续负责，不把 ownership 转移给 release 文档。

正式工程规则见 `docs/architecture/repository/RELEASE_OPERATING_MODEL_20260717.zh-CN.md`。Point 文档采用 `POINT_EXECUTION_PLAN_TEMPLATE.zh-CN.md`，并把 `skeleton / fixture / full / calibrated` 与最终 milestone closeout 分开。

`REL-PROD-001 / FIN 0.1` 不能以 P36 六个产业链主题代替产品范围。当前 release 通过 `P001-F01`-`F15` 消费 TECH owners：TECH_01/06/08 形成 Case、计划和 durable control；TECH_02-05/07/08 形成 search、evidence、numeric、judgment、workpaper 和 repair；TECH_09/10 形成 deliverable、human review、provenance 和 release eval。六条 AI infrastructure 链只作为动态 10-20 cells 的 mandatory families。正式映射见 `docs/product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md` 和 `TECH_00A` 第 5 节。
