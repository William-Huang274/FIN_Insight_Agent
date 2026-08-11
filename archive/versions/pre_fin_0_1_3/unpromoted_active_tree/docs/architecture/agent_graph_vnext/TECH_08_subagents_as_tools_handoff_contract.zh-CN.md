# TECH_08：Subagents-as-Tools / Handoff Contract

日期：2026-07-09

状态：技术合同草案。本文定义 FIN 中 subagent 作为工具调用的边界，避免把多 agent 做成自由 roleplay。

## 1. 要解决的问题

PRD 要求 Lead 可调用独立上下文 subagent，但跨 agent 通信必须通过结构化 artifact。Subagent 不是共享聊天群，也不能把 private scratchpad 当 evidence。

## 2. Agent 类型

| 类型 | 职责 | 输出 |
| --- | --- | --- |
| `ExploreAgent` | 探索 source / route / artifact candidate | `EvidenceRequest` / `SourceHunterRequest` / typed gap |
| `PlanAgent` | 辅助 Lead 拆决策面或 repair route | `DecisionSurfacePatchProposal` |
| `EvidenceAgent` | 执行 EvidenceRequest 或 parser/numeric request | `EvidenceResponse` / `PromotionDecision` |
| `DomainOperator` | 做领域 cell 判断与 bounded counterfactual / falsification pass | `DomainCellJudgmentPack` / `WhatWouldChangeProgram` |
| `WriterPresentationAgent` | 表达、结构、表格、图表、dashboard | draft artifact / `writer_blocker` |
| `VerifierAgent` | 审 source boundary、numeric、claim、cell、artifact | `VerificationResult` / `RepairTicket` |

## 3. Handoff 输入

`SubagentTask` 至少包含：

- `task_id`
- `caller`
- `agent_type`
- `decision_surface_id`
- `cell_ids`
- `assignment`
- `allowed_artifact_refs`
- `allowed_tools`
- `forbidden_tools`
- `budget`
- `stop_condition`
- `return_schema`

## 4. Handoff 输出

Subagent 只能返回结构化 artifact：

- `EvidenceResponse`
- `DomainCellJudgmentPack`
- `WhatWouldChangeProgram`
- `DecisionSurfacePatchProposal`
- `RepairTicket`
- `WriterDraft`
- `WriterBlocker`
- `VerificationResult`

不能返回：

- 私有 CoT；
- 未审 raw rows；
- 未经 Evidence Gate 的事实 claim；
- 跨 agent 聊天 transcript 作为共享事实。

## 5. Independent Context Policy

- subagent 可以有自己的 working context；
- Lead 只接收 artifact refs 和 summaries；
- raw rows / PDF / large graph object 留在 artifact store；
- handoff 必须记录在 Harness state；
- 对外共享只走 ledger 和 artifact。

## 6. 与其他 TECH 的边界

- `TECH_01` 决定什么时候调用 subagent；
- `TECH_02` 约束 EvidenceAgent 的工具使用；
- `TECH_06` 持久化 NodeAttempt / handoff；
- `TECH_07` 管理 isolated context；
- `TECH_10` 评估 subagent trajectory。

## 7. 第一批 fixture

1. Lead -> EvidenceAgent handoff fixture。
2. Lead -> DomainOperator handoff fixture。
3. WriterBlocker -> Lead repair fixture。
4. Private scratchpad 不进入 EvidenceLedger fixture。
5. Subagent ambiguity -> Lead clarification fixture。

## 8. 验收标准

- 每个 subagent 调用有 input/output schema。
- Lead 可 replay handoff decisions。
- subagent 输出不含 raw private scratchpad。
- Specialist 不能绕过 Evidence Layer 取数。
- Writer 不能补源，只能返回 blocker。

## 9. 2026-07-10 Domain Operator Handoff Extension

`DomainOperatorTask` 扩展 `SubagentTask`，增加 cell_question、business_decision_role、primary/contributor/challenger ownership、time_horizon、required_judgment_moves、CellEvidencePack ref、forbidden substitutions、repair policy 和 downstream claim boundary。

Domain operator 只能读取允许的 `CellEvidencePack` 和 role-specific SectorOperatorPack。它发现 decisive variable 或证据不足时返回 `RepairTicket` / `WhatWouldChangeProgram`，不能私自调用未授权 DB/RAG/web。Ambiguity 回 Lead clarification；evidence gap 回 Evidence Layer；numeric gap 回 TECH_04；业务解释冲突回 Cell Adjudicator。

## 10. Structured Coordination and Causal Message Contract

Subagent/agent-as-tool 遇到 ambiguity、dependency、evidence/numeric gap、judgment conflict、permission blocker、version advance 或 writer blocker 时，不能只返回一句自由文本问题，也不能共享完整聊天 transcript、private scratchpad 或原始 CoT。跨 agent 通信必须使用 `CoordinationMessageEnvelope`：它提供完成下一步所需的因果上下文，但把大 observation、raw document、row、trace 和模型输出留在 artifact store，通过 immutable refs drill down。

`CoordinationMessageEnvelope` 至少包含：

- identity/routing：message/event type、sender/recipient owner、run/work-unit/attempt、causation/correlation、priority、blocking state；
- research scope：decision surface、cell、evidence slot、entity/period/unit/segment/as-of；
- input binding：base pack、ContextInjectionPlan、PermissionSnapshot、artifact/evidence/judgment versions；
- expected contract：原任务、需要回答的判断问题、acceptable evidence、forbidden substitutions、return schema 和 stop condition；
- observation summary：发生了什么、failure/gap/conflict type、关键 observation refs 和不确定性；
- attempt summary：已尝试 route/tool/action、结果状态、已拒绝候选/替代口径及理由、remaining budget；
- downstream impact：受影响 claim/cell/artifact、是否 blocking、当前判断能保留到什么强度；
- requested action：目标 owner、repair/clarification/adjudication/approval/refresh 动作、期望输出和 deadline；
- audit refs：trace、ledger、artifact 和 prior related message refs。

这里的 `observation_summary`、`attempt_summary` 和 `action_rationale` 是可审计的结构化推理摘要，不是 token-level CoT。消息必须足以让接收方理解“为什么请求、已排除什么、影响什么、需要返回什么”，但不能把 sender 的全部 working context复制给 recipient。

消息类型至少稳定为：

| Message type | 默认 owner | 作用 |
| --- | --- | --- |
| `ClarificationRequest` | Lead | 用户意图、cell、口径或 assignment 不明确 |
| `DependencyRequest` | Harness router -> artifact/cell owner | 等待另一个 cell、pack 或 artifact；不允许 peer free chat |
| `EvidenceRepairTicket` | Evidence Layer | source/retrieval/parser/metadata/promotion gap |
| `NumericRepairTicket` | TECH_04 numeric owner | unit/scale/row selector/formula/reproduction gap |
| `JudgmentConflictNotice` | Cell Adjudicator；跨 cell 时 Lead | 多个 operator 对同一 evidence 或机制解释冲突 |
| `PermissionEscalationRequest` | TECH_06/Human | CapabilityGrant、license 或 approval 不足 |
| `VersionAdvanceNotice` | TECH_06 Version Impact Coordinator | 输入 head 前进，要求 continue/validate/rebase/cancel 判定 |
| `WriterBlocker` | Lead | Writer 发现 story、claim、citation 或 artifact contract 不闭环；Writer 仍不得补源 |
| `BoundedGapNotice` | Lead/Cell Adjudicator | 已满足 stop condition，应披露 gap 而不是无限 repair |

Agent 不能绕过 Harness 直接改变另一个 agent 的状态或注入其上下文。Harness 持久化 message、路由到 contract owner，并由 TECH_07 为 recipient 单独编译 `ContextInjectionPlan`。直接 agent-to-agent 调用也必须物化为上述 message/event/artifact，不以共享会话作为事实或执行账本。

## 11. Parallel Snapshot, Version Advance and Selective Invalidation Contract

并行 fan-out 必须绑定 immutable input snapshot。Subagent/agent-as-tool 只能提交 `PatchProposal`、`CandidateArtifact` 或 result delta，不能原地更新共享 pack。Evidence Gate、Cell Adjudicator、Lead 或其他明确 artifact owner 接受 proposal 后，才可生成 immutable new head；旧版本和基于旧版本运行的 attempts 继续保留在审计链中。

每个并行 `WorkUnit` 启动时生成 `InputDependencyManifest`，至少记录：

- base pack/artifact/cell/evidence/judgment versions 和 ContextInjectionPlan；
- exact `read_set`、`write_set`、required/optional dependency refs 和 dependency digest；
- cell dependency edges、assumptions、entity/period/unit/segment/as-of 和 permission refs；
- `MaterialityContract`：consumer 依赖哪些 direction、magnitude band、timing、confidence threshold、mechanism、evidence identity/status、counterevidence、What-Would-Change trigger 和 claim scope；哪些变化只是 citation/source-diversity 增量；
- `version_policy`、safe checkpoints、tool/model cancellation capability 和 estimated remaining cost；
- stale-output policy、required revalidation owner 和 fan-in acceptance contract。

每次 accepted head 前进必须生成 `PackChangeSet`，至少记录 from/to version、changed refs/cells/slots、add/correct/supersede/revoke/status-change 类型、identity/authority/claim-scope/judgment/confidence delta、affected dependency edges、declared materiality、invalidation candidates 和 producer/adjudicator refs。只发一个“v2 已生成”事件不够，scheduler 必须知道具体改变了什么。

### 11.1 Runtime State Awareness and Event Delivery

Agent 不负责在自己的 prompt 中维护全局状态，也不能假设“没有收到消息就代表 pack 没变”。TECH_06 以 append-only events 和 current-state projection 维护 authoritative `WorkUnitExecutionView`。它必须把三类正交状态分开：

| State plane | 建议状态 | 回答的问题 |
| --- | --- | --- |
| `execution_state` | queued / running / atomic_call_inflight / checkpointing / paused / recompiling / resumable / completed / cancel_requested / cancelled | worker 当前在做什么 |
| `input_currency_state` | current / head_advanced_unassessed / compatible / additive_pending_validation / material_rebase_required / hard_invalid | 当前输入相对 artifact head 是否仍可用 |
| `output_usability_state` | not_produced / current_proposal / pending_validation / compatible / stale_quarantined / accepted / rejected | 当前或即将返回的输出能否 fan-in / promotion |

Artifact owner 提交 new head 时必须产生 `ARTIFACT_HEAD_ADVANCED` event 和 `PackChangeSet`。VersionImpactCoordinator 按 `InputDependencyManifest` 为相关 WorkUnit 建立 subscription/projection，将 input currency 先标为 `head_advanced_unassessed`，再进行影响判定。无关 WorkUnit 不注入新材料；相关 WorkUnit 在判定完成前可以完成已经开始且不可安全中止的 atomic tool/model call，但不得开启下一次依赖旧状态的 model/tool decision，也不得提交 final result。

Worker 必须在 start、每个 safe checkpoint、开始下一次 model/tool action 前、resume 前和 result/fan-in commit 前调用 `validate_execution_view(expected_versions, last_seen_sequence_no)`。即使 event delivery 延迟，commit-time optimistic version check 仍必须拦截 stale output。外部调用不可中止时，返回结果只能进入 quarantine observation，等待新版本判断，不能自动进入 current pack。

Agent 只接收最小 `VersionControlDirective`，包括 base/current heads、input currency、changed-dimension summary、允许动作、effective checkpoint、old-output usability、required re-analysis questions 和 refs。它不直接接收整个新 pack，也不自行修改状态。Lead/Workbench 可读取 case-level state projection；普通 subagent 只读取自身 WorkUnit 和被授权 dependency 的状态。

典型状态迁移示例：

```text
T0  B 基于 Pack v1 运行
    running / current / not_produced

T1  A 的 proposal 被 owner 接受，产生 Pack v2 和 ARTIFACT_HEAD_ADVANCED
    B -> running / head_advanced_unassessed / not_produced

T2  B 已开始的 atomic call 可以结束，但不能开启下一次旧版 decision

T3  coordinator 运行 dependency + materiality 检查
    no overlap -> running / compatible / current_proposal
    semantic assessment needed -> checkpointing / head_advanced_unassessed / pending_validation
    material trigger hit -> paused / material_rebase_required / stale_quarantined

T4  ContextEngine 编译 v2 ContextInjectionPlan
    paused / recompiling / stale_quarantined

T5  新 WorkUnit version 从 checkpoint 恢复
    running / current / not_produced
```

### 11.2 Version Impact Authority

版本影响不是由正在运行的 agent 自行决定，也不是全部交给单一规则或单一 LLM。TECH_06 拥有 `VersionImpactCoordinator`，它消费 manifest、change set、dependency graph、artifact-owner decision 和当前 runtime policy，输出 durable `WorkUnitVersionDecision`；它是执行状态迁移的唯一入口，不做业务判断。

判定分三层：

1. `Deterministic impact filter`：检查 exact version/read-set intersection、entity/period/unit/segment/as-of、permission/revocation、accepted/context/rejected identity、forbidden substitution、schema compatibility 和 dependency edges。无依赖交集可判 `continue`；permission revoke、核心 identity correction、required dependency revoke 等硬失效可直接判 `cancel_and_supersede`。硬失败不能由 agent override。
2. `Semantic materiality assessment`：新增信息与 read-set 有交集，但是否改变机制、claim strength、confidence 或 judgment status 不可由结构字段确定时，调用受限的 `VersionImpactAssessor`。Cell 内材料性由 Cell Adjudicator 承担；跨 cell/story 影响由 Lead 承担；numeric/source identity 仍分别以 TECH_04/Evidence Gate 的决定为准。它只输出 `VersionImpactSuggestion`、受影响问题、需要重看的 refs 和置信度，不能直接 pause/cancel/accept output。
3. `Policy execution`：VersionImpactCoordinator 将 hard result、semantic suggestion、version policy、checkpoint/cost/cancellation state 编译为 `WorkUnitVersionDecision`，由 TECH_06 执行 continue、continue-then-validate、rebase-at-checkpoint 或 cancel/supersede。高影响且语义建议低置信或冲突时进入 Lead/Human review；默认 fail-safe 是在最近 safe checkpoint 暂停，不是静默继续。

`WorkUnitVersionDecision` 至少包含 decision、basis (`rule_only / semantic_assessment / human_review`)、base/current versions、affected dependencies、materiality、effective checkpoint、old-output usability、new WorkUnit/attempt refs、required revalidation、reason codes 和 causation event。

语义 assessor 不能只返回“相关/不相关”。`VersionImpactSuggestion.change_dimensions` 至少使用：`redundant_or_citation_only`、`evidence_strength_changed`、`confidence_threshold_crossed`、`mechanism_changed`、`direction_or_magnitude_changed`、`counterevidence_changed`、`what_would_change_triggered`、`identity_or_scope_changed` 或 `unknown`。Coordinator 将这些 dimensions 与 consumer 在 `MaterialityContract` 中声明的 sensitivity 对照：只有命中 consumer trigger 才需要 rebase；只增加同质 citation/source diversity 且不改变 evidence identity/status 时通常进入 validate；`unknown` 且可能影响 required dependency 时先 pause。

这使“没有推翻原输入”不再是充分条件。例如 confidence 从 low 变 medium：如果 consumer 声明 `minimum_confidence=medium`，它会跨过可使用阈值并触发 rebase；如果 consumer 只依赖方向且旧材料已经满足 authority/status，可能只需 continue-then-validate。新材料是否触发 What-Would-Change、改变机制或新增有效 counterevidence，也分别按显式 trigger 判断，而不是只看结论方向是否翻转。

核心判定关系是：

```text
PackChangeSet.change_dimensions
  intersect WorkUnit.MaterialityContract.consumer_sensitivity
  -> impacted triggers
  -> required re-analysis scope
  -> WorkUnitVersionDecision
```

其中规则先处理 exact intersection 和 hard boundary；无法结构化确认的 change dimensions 才由 VersionImpactAssessor 建议。Cost/remaining runtime 只能影响 checkpoint 时机，不能把命中的 hard/material trigger 降级成可直接提交。

### 11.3 Four Version Outcomes

| Outcome | 判定条件 | 执行动作 | 旧输出身份 |
| --- | --- | --- | --- |
| `continue` | 无 read/dependency overlap，或仅非语义 metadata/head bookkeeping 变化 | 原 snapshot 继续；fan-in 做版本兼容检查 | 可在 dependency digest 未变时兼容当前 head |
| `continue_then_validate` | 相关 additive evidence，但未改变 evidence identity、claim boundary、judgment status 或 required assumption | 允许跑完；fan-in 由 owner 做 delta compatibility validation | 先是 proposal，验证后才可进入 current head |
| `rebase_at_checkpoint` | 可能改变机制、confidence、claim strength、cell status 或 downstream dependency | 最近 safe checkpoint pause；创建新 WorkUnit version/context plan 后 resume | 旧 attempt 保留，可作 prior observation，不能直接晋升 |
| `cancel_and_supersede` | entity/period/unit/segment/as-of 错误、required evidence revoke、permission/license 撤销、核心 cell/scope 改变或关键 accepted fact 被推翻 | cooperative cancel；外部调用不可中止时隔离其结果；新 version 重跑 | `stale_rejected` / `superseded`，只留审计 |

禁止全局固定采用“任何新版本都重跑”或“所有 agent 一律跑完”。不同 WorkUnit 可声明：`pinned_snapshot`（例如 blind challenger）、`continue_then_validate`、`refresh_at_checkpoint`、`interrupt_on_material_change` 或 `latest_head_required`（Writer、Verifier、Adjudicator）。Writer 启动前必须冻结可写作的 DecisionSurfacePack head；material head advance 后旧 draft 进入 stale，Writer 仍不能自行补源。

### 11.4 Context Recompilation After Rebase

语义 assessor 只说明哪些 dependency、判断问题和 assumptions 被改变，不直接拼 prompt。`ContextRebaseRequirement` 由 VersionImpactCoordinator 基于旧 ContextRequirement、旧 ContextInjectionPlan、PackChangeSet、retained/invalidated refs、role policy、budget 和 requested re-analysis scope 生成，并交给 TECH_07 ContextEngine。

ContextEngine 必须：

- 保留仍有效且 digest 未变的 governance/task/context blocks；
- 排除 stale/superseded/revoked refs，替换被纠正的 evidence/cell/artifact versions；
- 注入 change summary、new evidence/counterevidence、unresolved conflicts、previous attempt summary 和 required re-analysis questions；
- 注入 `RuntimeStateBlock`：base/current heads、version decision、materiality triggers hit、retained/invalidated refs 和 output usability；
- 重新执行 permission/scope/freshness/budget/compaction selection，并生成新的 ContextSnapshot、SelectionDecisions 和 immutable ContextInjectionPlan；
- 不在原 attempt 中热替换 prompt，也不让 agent 自行选择性忽略新 head。

这样，agent 可以提出 `ContextExpansionRequest` 或指出“这个变化可能影响 margin mechanism”，但实际重编译内容由 ContextEngine 根据 versioned contract 决定。若 semantic materiality 无法可靠判断，系统先在 checkpoint 冻结旧 attempt，并把争议和两版 refs 一并交给 Cell Adjudicator/Lead，而不是让运行中 agent 自我认证“无需重跑”。

## 12. Additional Fixtures and Acceptance

6. Gap-only message negative fixture：缺少因果上下文、attempt refs 或 requested action 时拒绝路由。
7. Causal coordination replay fixture：recipient 可仅靠 envelope 和 refs 重建 repair/clarification 所需上下文。
8. Parallel no-overlap fixture：无 dependency overlap 的新 head 不触发误停。
9. Additive-evidence fixture：相关但不改变 identity/judgment boundary 的材料进入 continue-then-validate。
10. Semantic-materiality fixture：规则无法判断时路由 Cell Adjudicator/Lead，并记录 suggestion 与最终 policy decision。
11. Hard-invalidation fixture：unit/period/permission/revocation 变化触发 cancel/supersede，旧输出不进入 current head。
12. Rebase context fixture：新 plan 保留有效 blocks、替换 stale refs、注入 delta/conflict，且不原地修改旧 attempt。
13. Writer latest-head fixture：material pack advance 使旧 writer draft stale，但不能触发 writer 自补源。
14. State-awareness fixture：head advance 后 execution/input-currency/output-usability 三个状态面独立迁移，agent 不把未收到 prompt 消息当作 current。
15. Checkpoint validation fixture：event delivery 延迟时 commit-time version check 仍隔离 stale output。
16. Materiality-trigger fixture：相同 confidence/evidence-strength delta 对不同 consumer contract 分别产生 validate 或 rebase。
17. Atomic-call-inflight fixture：不可中止调用完成后进入 quarantine，不开启下一次旧版 decision。

附加验收标准：每次并行 version advance 都必须能回答谁提交了 change、谁判定 evidence/cell head、哪些 WorkUnit 被检查、规则和语义 assessor 各给出什么、为何 continue/rebase/cancel、重编译注入了哪些 delta，以及旧输出最终是否可用。

## 13. 2026-07-11 Presentation / Verification Handoff Extension

`PresentationTask` 扩展 SubagentTask，增加 frozen DecisionSurface/SurfaceClaim heads、WriterBrief、DeliverablePlan、NarrativeSurfaceContract、target audience/language/artifacts、disclosure policy、allowed citation/artifact refs、writer no-source capability profile、required panels、partial-draft policy 和 TECH_09 return contract。

`WriterResultEnvelope` 只能返回 CanonicalPresentationModel candidate、SurfaceClaim wording versions、Narrative/Table/Visualization specs、projection bindings、WriterDraft refs、typed WriterBlockers、input/output digests 和 usage observation。`completed` 只表示 Writer WorkUnit 返回合格 envelope，不表示 render/verification/review/release 通过。

`VerificationTask` 绑定 exact research/presentation/artifact versions、verification layers、required constraints、allowed drilldown refs 和 blocking policy；`VerificationResultEnvelope` 返回 deterministic/semantic/visual results、affected nodes、repair owner、old/new usability 和 release-blocking status。Writer/Verifier 均不得通过 handoff 获取补源权限。

## 14. 2026-07-11 Evaluator Agent-as-Tool Extension

只有需要模型语义判断、领域 rubric 或受控诊断的 evaluator 才作为 `EvaluatorAgent` 调用；schema/numeric/version/permission/static evaluator 保持 deterministic tool/test，不人格化。

`EvaluatorTask` 至少绑定 eval run/subject/evaluator/oracle/rubric refs、evaluation dimensions、candidate/blinding policy、allowed artifact/drilldown refs、budget、abstain/human-escalation policy 和 return schema。`EvaluatorResultEnvelope` 返回 per-dimension suggestion、confidence、support refs、abstain/conflict、usage 和 judge trace；它不能直接修改 EvalMetricResult、Gold、EvalGatePolicy、research artifact 或 release state。

EvaluatorAgent 与被评 agent 使用独立 ContextInjectionPlan，不共享 private scratchpad，也不能通过 handoff 暴露 hidden holdout。TECH_10/R60 evaluator runner 校验 envelope 后生成正式 EvaluatorRun/EvalMetricResult；模型返回本身只是 candidate judgment。

## 15. 2026-07-11 AgentDefinition / PromptBundle Ownership

`AgentDefinitionVersion` 至少声明 agent type、business role、allowed task/mode、input/output schema、read/write sets、allowed tools/subagents、required skills、context requirements、permission profile、budget/stop behavior、repair/escalation routes 和 forbidden actions。`PromptBundleVersion` 由 system/task/rubric/output/negative constraints 和 referenced skill versions 组成，不以散落字符串作为生产 source of truth。

AgentDefinition 不绑定单一 provider 型号；它声明 capability requirements，TECH_06 的 ModelSelectionDecision 选择满足要求且有权限的模型。任何 role、schema、tool authority、prompt/skill 或 fallback 改动都产生新 version，并进入 TECH_10 candidate-vs-baseline eval。现有 `agent_registry.py` 和 prompts/skills 是迁移输入，不代表该统一合同已经 runtime active。

## 16. 2026-07-12 Configurable Agent / Skill / Coordination Governance

根据新版 PRD 与 TECH_00，Agent/Skill/Graph/Workflow 需要机构可配置，但自由度与其对共享真值和正式交付的影响反向相关。TECH_08 拥有 Agent/Skill/handoff 的语义定义，TECH_06 拥有 registry/permission/rollout 执行，TECH_10 拥有 eval/release gate。

### 16.1 Versioned definitions

- `AgentDefinitionVersion`：objective、business role、input/output、read/write set、tools/subagents、skills、context requirement、budget/stop、repair/escalation、reviewer 和 forbidden actions；
- `SkillDefinitionVersion`：purpose、precondition、input/output、allowed source/evidence role、permission/cost、sector/report applicability、tests 和 compatibility；
- `CoordinationPolicyVersion`：primary/contributor/challenger/evidence/repair ownership、handoff routes、parallelism、clarification 和 materiality escalation；
- `GraphViewPolicyRef`：只控制 Agent 可见/可提议的 ontology/view/hypothesis；verified graph truth 仍由 TECH_03 ontology/source governance。

### 16.2 Freedom tiers

| Tier | 可配置动作 | Gate |
| --- | --- | --- |
| exploration | query、tool fallback、Skill selection、provisional cell/gap | permission/budget/trace |
| institution workflow | role、pack、handoff、review chain、provider allowlist | version + sandbox eval + approval |
| shared truth proposal | EvidenceDelta、JudgmentDelta、ArtifactPatchProposal | 对应 business owner adjudication |
| hard invariant / release | evidence/numeric/permission/secret/exact-hash rules | 普通配置禁止修改；受审 waiver only |

### 16.3 Handoff accountability

所有 `SubagentTask / ResultEnvelope / CoordinationMessage` 增加 case/version、ActorSnapshotRef、Agent/Prompt/Skill/ContextPlan versions、selected/injected/invoked capability、permission/budget 和 causation refs。通信必须带前因、目标、已尝试路线、观察、gap 类型、影响对象和期望响应，不能只返回一句“缺数据”。

Subagent 只能提交 delta/proposal；TECH_02/04/05/09 等 owner 才能推进 shared head。Agent 自主选择新 Skill/provider 时生成新 selection decision；若改变 context/tool capability，TECH_07/06 必须重新编译或新建 attempt。

### 16.4 Rollout and portability

定义从 draft/sandbox_eval/approved/staged_rollout/active 到 superseded/rollback。AgentDefinition 不绑定 DeepSeek/GPT/Gemini 型号，只声明 capability requirement；模型升级不得改变 output schema、permission 或 owner boundary。每次 provider/model/skill/config swap 进入 TECH_10 paired non-regression。

本节状态为 `documented / contract_draft`；不表示机构 Configuration Studio 或动态 Agent registry 已实现。
