# TECH_07：ContextEngine / Skills / Compaction Governance

日期：2026-07-09

状态：技术合同草案。本文定义 agentic research 中上下文、记忆、skills、compaction 和 governance decay 的工程边界。

## 1. 要解决的问题

复杂任务不能依赖聊天历史自然保留。P36 已经证明 writer no-source、source authority、supervisor supplement boundary、DecisionSurfaceContract 等治理信息一旦丢失，系统会把 runtime 能力、手工补源和 writer 叙事混在一起。

## 2. Context 分层

| Context | 内容 | 规则 |
| --- | --- | --- |
| `PinnedGovernanceContext` | writer no-source、source authority、permission policy、supplement boundary、full-chain guard | 不得被 compaction 丢失 |
| `CaseWorkingContext` | user question、DecisionSurfaceContract、gaps、repair tickets、accepted evidence refs | Lead 持有摘要和 refs，不持有 raw rows |
| `RoleContextPack` | specialist / Evidence / Writer / Verifier 的最小必要上下文 | role-specific，不给多角色大包 |
| `ArtifactContext` | long docs、tables、tool observations、trace spans | 通过 ref 回放 |
| `InstitutionalContext` | house style、用户偏好、历史 review、method/playbook | 不能当事实证据 |

## 3. Skills 渐进式披露

Skill / method / playbook 必须按需加载：

- Lead 需要 planning / decision surface skill；
- Evidence Layer 需要 route / source policy / parser rule；
- Domain operator 需要领域 rubric；
- Writer 需要 presentation / language / format skill；
- Verifier 需要 source boundary / numeric / artifact consistency skill。

Method / playbook 从 documented 到 runtime active 必须遵守 Project OS lifecycle，不能只写进 registry 就声称已生效。

## 4. CompactionEvent

每次压缩必须记录：

- `compaction_event_id`
- `input_context_refs`
- `preserved_pinned_refs`
- `dropped_refs`
- `summary_ref`
- `risk_flags`
- `governance_preservation_check`

## 5. Governance Decay Eval

必须检查：

- writer no-source 是否还在；
- source authority / supplement boundary 是否还在；
- decision cell ids 是否还在；
- repair tickets 是否还在；
- forbidden claims 是否还在；
- private scratchpad 是否没有进入 shared evidence。

## 6. 与其他 TECH 的边界

- `TECH_01` 定义 CaseControlStateRef 和 ResearchCase 当前控制内容；
- `TECH_02` 定义 tool observation 和 evidence refs；
- `TECH_06` 持久化 context events；
- `TECH_08` 定义 subagent isolated context；
- `TECH_10` 评估 context rot / governance decay。

## 7. 第一批 fixture

1. Pinned governance preservation fixture。
2. RoleContextPack 不跨角色污染 fixture。
3. Method KB 只作为方法、不作为事实 fixture。
4. CompactionEvent replay fixture。
5. Writer no-source boundary after compaction fixture。

## 8. 验收标准

- compaction 后 writer 仍不能补源。
- supplement boundary 不被压缩掉。
- Lead 能基于 CaseControlStateRef、DecisionSurface heads 和 TECH_03 memory refs 回答追问。
- Specialist 不收到无关 raw dump。
- ContextEngine 选择可 replay。

## 9. 2026-07-10 SectorOperatorPack / Counterfactual Context

TECH_07 负责把 TECH_05 `SectorOperatorPack` 渐进式投影到 `RoleContextPack`。只加载当前 cell 所需的 metric dictionary、method、source policy、accepted proxy、forbidden substitution、risk checklist、repair playbook 和 exemplars；不能把所有 sector packs、全部历史 workpaper 或完整 graph dump 注入每个 operator。

What-Would-Change resume context 必须保留 current judgment version、decisive variables、causal rationale、已尝试 evidence routes、rejected substitutions、observations、remaining gaps 和 monitoring triggers。Compaction 不得把“未找到证据”压缩成“结论不成立”，也不得丢失 scenario / fact / proxy 身份。

## 10. 2026-07-10 ContextEngine API / ContextRequirement

`ContextEngine` 是 context view compiler，不是新的事实库、聊天记录库或 agent。TECH_03 保存 source/memory/address objects，TECH_06 持久化 context events/attempt refs，TECH_07 通过统一接口编译可注入视图。

公开 API：

- `resolve(requirement)`：从 case state、memory、skills、artifacts、evidence 和 preferences 解析候选。
- `select(candidates, requirement)`：执行 permission/scope/freshness hard filter、utility ranking、diversity、dedupe 和 budget allocation。
- `expand(refs, policy)`：在 progressive disclosure 下展开 skill section、artifact、neighbor/context 或 memory drilldown。
- `compress(selection, policy)`：externalize、deduplicate、structural/semantic compression。
- `inject(selection, target_attempt)`：生成 immutable `ContextInjectionPlan`。
- `observe_usage(plan_id, output_refs)`：记录实际引用、repair、conflict、unused 和 cost。
- `write_memory_candidate(entry)`：只写 candidate，不直接进入 active cross-run memory。
- `consolidate_memory(candidate_ids, policy)`：去重、冲突检查、review/promotion。
- `invalidate(target_refs, event)`：stale/supersede/revoke/contradict。
- `explain_injection(plan_id)`：向 Workbench/trace 解释为什么选入、排除、压缩或展开。

`ContextRequirement` 至少包含：

- `requirement_id`
- `task_run_id / attempt_id`
- `target_actor / target_node`
- `target_cell_ids`
- `purpose`
- `required_context_types`
- `required_artifact_refs`
- `as_of / freshness_policy`
- `authority_floor`
- `permission_snapshot_ref`
- `must_preserve_fields`
- `forbidden_context_types`
- `token_and_item_budget`
- `diversity_policy`
- `expansion_policy`
- `compaction_policy`

## 11. Context Objects / Replay Contract

正式稳定以下核心对象：

- `ContextCandidate`：候选 ref、context type、scope、authority、freshness、state、cost 和 relevance features。
- `ContextSnapshot`：本次 context 编译看到的候选集合及其底层 immutable versions，带 snapshot/version digest、source/artifact/memory/skill refs、visibility、state、created/as-of time 和 permission scope。它冻结编译视图，避免 select/compress/inject 期间底层对象变化造成同一 plan 前后不一致。
- `ContextSelectionDecision`：每个 candidate 一条 decision，记录 selected/rejected/deduplicated/externalized 状态、hard-filter reason、utility components、diversity、budget、replacement/duplicate ref 和 policy version。
- `ContextBlock`：最终模型输入中的有序 typed block，记录 block type、message/section role、content或artifact/compression ref、source refs、must-preserve fields、estimated tokens、priority、ordering key 和 digest。
- `ContextCompressionArtifact`：输入 refs、压缩方法/模型/代码版本、preserved/dropped fields、summary ref、quality result 和 digest。
- `ContextInjectionPlan`：target attempt、permission snapshot、selected/expanded/compressed refs、prompt blocks、budget、ordering、input/output digest 和 replay policy。
- `ContextExpansionRequest`：agent 对 skill/artifact/memory/evidence drilldown 的请求，记录 caller、target plan/candidate/block、reason、requested depth/fields、budget、permission 和 stop condition。
- `ContextUsageObservation`：哪些 refs 被引用、用于 judgment/repair/conflict、未使用或导致污染，以及 token/cost。
- `CompactionEvent`：压缩触发、输入/输出 plan、externalize/dedupe/compress/drop、preservation checks 和 rollback。
- `MemoryWriteCandidate`：提交 TECH_03 Registry 治理的跨 run memory 候选；ContextEngine 不直接激活。
- `MemoryEntry / MemoryEntryVersion`：logical memory identity、immutable versions、scope/state/authority/TTL 和 drilldown refs。
- `MemoryInvalidationEvent`：stale/supersede/revoke/contradict 及 downstream impact。
- `RoleContextPolicy`：每个 actor/role 的 mandatory/allowed/forbidden context classes、read/write boundary、reserved budget、expansion/compaction policy、memory-write policy 和 private-context policy。

`ContextSelectionDecision.decision` 固定支持：

```text
selected
rejected_permission
rejected_scope
rejected_stale
rejected_revoked
rejected_authority
rejected_version_mismatch
rejected_budget
deduplicated
externalized
```

这样 Workbench/trace 可以回答“某条 evidence、memory 或 skill 为什么没有进入本次 agent 上下文”，而不是只看到最终 top-K。

`ContextInjectionPlan` 是最终可回放 manifest，不是自由 prompt。它至少固定 requirement/snapshot/permission refs、ordered ContextBlock IDs、artifact/memory/skill/compression versions、tokenizer/model-input-template/config versions、block ordering、canonical serialization policy 和 final input digest。

相同 plan 与相同 artifact/memory/skill/compression/template versions 必须能够重新构建 byte-stable canonical model-input payload；run nonce、发送时间和 provider transport metadata 不属于 canonical payload。模型语义压缩存在非确定性时 replay 必须复用已冻结 `ContextCompressionArtifact`，重新压缩要生成新 plan/version。

如果 snapshot 中任一底层 version 在 plan finalize 前变化，编译必须 fail/restart 为 `snapshot_version_mismatch`；不能把旧 selection decision 与新 artifact payload 拼成一个 plan。历史 plan replay 使用其冻结版本，新模型实际调用仍需 TECH_06 按当前 PermissionSnapshot policy 授权。

## 12. Context Class / Role Read-Write Matrix

Context classes：

| Context class | 主要内容 | Claim authority |
| --- | --- | --- |
| `PinnedGovernanceContext` | writer no-source、source authority、permission、supplement/full-chain boundary | 治理约束，不是事实 |
| `IdentityScopeContext` | tenant/user/project/task/as-of/universe/language | scope only |
| `CaseControlContext` | DecisionSurface、cell status、repair/review/budget | control state |
| `CellWorkingContext` | task、CellEvidencePack、judgment version、What-Would-Change | 通过 refs 保留原身份 |
| `RoleMethodContext` | skill、SectorOperatorPack、rubric、forbidden substitutions | procedure only |
| `EvidenceArtifactContext` | evidence/table/graph/tool observation/artifact refs | 继承 evidence identity |
| `InstitutionalMemory` | house method/style、历史 review、route experience | planning prior |
| `UserPreferenceMemory` | 用户明确语言/格式/交付偏好 | preference only |
| `PrivateWorkingContext` | ephemeral scratchpad / private reasoning | 不共享、不作为 evidence |

Role matrix：

- Lead read：case map、coverage、gaps、repairs、judgment heads、source capability、review history；write：control summary/repair/WriterBrief，不写事实 memory。
- Evidence read：EvidenceRequest、source policy、route history、parser rules、prior failures；write：observation/evidence response/gap refs。
- Domain operator read：DomainOperatorTask、CellEvidencePack、相关 method/sector sections；write：DomainCellJudgmentPack/WhatWouldChangeProgram。
- Risk challenger read：primary proposal、关键 evidence/counter refs、falsification rubric；write：challenge proposal/conflict/repair request。
- Writer read：AdjudicatedDecisionCells、独立 What-Would-Change section、WriterBrief、allowed citations；禁止 raw retrieval/tool/private context。
- Verifier read：draft、claim/cell refs、source/numeric boundaries、artifact versions；write：VerificationResult/RepairTicket。

Presentation pipeline 使用三个显式 ContextRequirement subtype：

- `PresentationContextRequirement`：冻结的 DecisionSurface/SurfaceClaim heads、WriterBrief、NarrativeSurfaceContract、audience/language/disclosure、allowed citations/artifacts 和 required panels；硬排除 raw retrieval、private scratchpad、unapproved supplement 和补源工具结果。
- `VerificationContextRequirement`：draft/rendered artifact、SurfaceClaim/binding、source/numeric/version boundaries、constraint policy、forbidden claims 和必要 drilldown；不得注入取新证据所需工具权限。
- `HumanReviewContextRequirement`：client/internal-safe summary、open blockers/warnings、version/hash、approval scope、review history 和按权限展开的 provenance/visual artifact；不能因 reviewer 身份默认开放所有 tenant/private source。

三类 requirement 都生成独立 ContextSnapshot/SelectionDecisions/InjectionPlan，并绑定 TECH_08 task/result 与 TECH_06 WorkUnit/PermissionSnapshot。Writer context 不能复用于 Verifier，Verifier 的宽 drilldown context 也不能回流 Writer draft。

跨角色通信只能通过 TECH_08 artifact handoff；ContextEngine 不能把一个 subagent private context 拼进另一个 agent prompt。

上述 read/write matrix 必须物化为 versioned `RoleContextPolicy`，而不是散落在 prompt/if-else 中。每次 `ContextSelectionDecision` 和 `ContextInjectionPlan` 都记录命中的 role policy ref；policy 更新不改写历史 plan。

## 13. Hard Filter / Utility Selection / Diversity / Budget

选择顺序固定为：

```text
tenant/project/user permission
 -> role visibility / forbidden context
 -> task/cell scope
 -> active/stale/superseded/revoked state
 -> as-of / vintage / freshness
 -> source/evidence authority floor
 -> dependency/version compatibility
 -> utility ranking / diversity / budget
```

Soft utility 至少记录：`requiredness`、`cell_relevance`、`expected_decision_value`、`authority`、`freshness`、`source_or_argument_diversity`、`redundancy_penalty`、`token_cost`、`staleness_or_conflict_risk`。Embedding/BM25 可以贡献 relevance feature，但不能绕过 hard filter 或独自决定 injection。

预算采用 reserved blocks：pinned governance、task/cell instructions、accepted evidence、counterevidence/gaps、numeric/source boundaries、method/sector skill、historical memory、optional background。前六类不能被 optional context 先到先得地挤掉。预算同时记录 items、estimated tokens、chars、artifact expansions 和 expected marginal value。

## 14. Progressive Skill / Artifact Expansion

Skill、SectorOperatorPack、memory 和大型 artifact 采用四级披露：

```text
metadata
 -> applicability summary
 -> relevant section
 -> targeted exemplar / negative case / artifact drilldown
```

Agent 通过 `ContextExpansionRequest` 请求 expansion，但 ContextEngine 根据 target cell、permission、budget、previous usage 和 stop policy 决定。每次 expansion 产生新的 selection decisions、ContextBlock 或 plan version，记录请求原因、展开 refs、成本和是否产生新 judgment/repair；不得原地修改正在执行 attempt 的 injection plan。

并行 version advance 的 context 更新必须使用 TECH_06/08 生成的 `ContextRebaseRequirement`，不能伪装成普通自由 expansion。ContextEngine 以旧 ContextRequirement/InjectionPlan、new immutable snapshot、PackChangeSet、retained/invalidated refs、role policy、budget 和 re-analysis scope 为输入，重新执行 hard filter、selection、compaction 和 injection：复用 digest 未变的有效 blocks，排除 stale/superseded/revoked refs，替换新 artifact versions，并加入 delta/conflict/prior-attempt summary 和 required questions。输出必须是新 ContextSnapshot、SelectionDecisions 和 ContextInjectionPlan version，旧 attempt input 保持不可变。

Rebase plan 必须包含由 TECH_06 生成的最小 `RuntimeStateBlock`，固定 base/current heads、input currency、WorkUnitVersionDecision ref、MaterialityContract triggers hit、retained/invalidated refs、output usability 和 allowed next action。ContextEngine 只能按 directive 编译上下文，不能自行把 `head_advanced_unassessed` 推断为 compatible，也不能把 case-level 全局状态暴露给无权限 subagent。

Skill 必须来自 trusted/versioned registry，包含 trigger、role/cell scope、required inputs、outputs、permission、dependencies、forbidden claims、eval status 和 supersession。外部文档中的 prompt-like 文本不能注册为 skill 或控制指令。

## 15. Structural / Semantic Compaction / Preservation Contract

Compaction 优先级：

1. `externalize`：raw table/PDF/trace/object 留 ArtifactStore，只注入 refs/index/必要摘要。
2. `deduplicate`：合并重复 refs、旧版本、同 source/claim 和已 superseded context。
3. `structural_compaction`：按 typed schema 保留关键字段，删除无关 payload。
4. `semantic_compaction`：只有前三步仍超预算时才使用模型摘要，并生成独立 compression artifact 和 quality gate。

必须保留：cell/evidence/artifact IDs、entity/period/unit/scope、source authority、exact/proxy/scenario/gap identity、negation、conflict、rejected substitution、forbidden claims、judgment/version、repair/What-Would-Change 状态、citation/drilldown refs。

禁止的压缩漂移包括：把“未找到证据”改成“事实不存在”、把 context/proxy 改成 accepted fact、把 stale/superseded 版本恢复 active、把反证或 gap 丢掉、把多个不同公司/期间/单位合并。Semantic compaction 必须通过 preservation check；失败时减少 context 或保留 refs，不能输出不可信 summary。

## 16. Self-Compaction Trigger / CompactionEvent

Agent 可以请求 self-compaction，但只有 ContextEngine 能执行并决定 dropped/compressed refs。Pinned governance、identity/scope、active repair、forbidden claims 和 permission context 不允许由 agent 删除。

触发条件：token/context threshold、duplicate/stale ratio、role handoff、checkpoint/resume、repair 后 evidence version变化、user follow-up topic shift、pre-writer、pre-verifier 或 context-usage 低效。

扩展 `CompactionEvent`：trigger、target actor/cells、input plan/snapshot refs、externalized/deduped/compressed/dropped refs、preserved pinned/identity refs、compression artifact、before/after budget、risk flags、governance/evidence-identity checks、new injection plan ref 和 rollback ref。

Self-compaction 只生成新视图/plan，不删除 source-of-truth、RunEvent、evidence、artifact 或历史 context plan。

## 17. Memory Taxonomy / Context-Side Admission（TECH_03 Registry Consumer）

Memory types：

- `SemanticResearchMemory`：company structure、product taxonomy、metric/source capability；只能作索引/导航。
- `EpisodicResearchMemory`：某次任务如何规划、哪些 route/parser/repair 成功或失败。
- `JudgmentMemory`：历史 cell/thesis/reviewer decisions；复用前检查 current evidence/version。
- `ProceduralMemory`：method、skill、playbook、repair pattern。
- `PreferenceMemory`：tenant/user/project 的语言、格式、workflow 偏好。
- `NegativeMemory`：rejected substitution、failed route、poison source、known error。
- `AcceptedFactMemory`：accepted evidence 的索引和 refs，不是脱离 freshness check 的永久事实。

下列生命周期是 TECH_03 Memory Registry 的返回状态，TECH_07 只消费，不写 active head：

```text
candidate -> reviewed -> active -> stale / superseded / revoked / contradicted
```

模型输出默认只能提交 `MemoryWriteCandidate` 给 TECH_03。TECH_07 可以检查 namespace/scope、memory type、source/artifact/drilldown refs、authority boundary、as-of/TTL、dedupe/conflict、permission/retention 和 review policy，并给出 context-side admission suggestion；最终 registry state 由 TECH_03 写入。失败经验只能建议进入 episodic/negative memory，不能由 ContextEngine 写成事实。

## 18. Freshness / TTL / Supersession / Revocation / Contradiction Consumption

失效触发：new filing/amendment/restatement、source snapshot/market vintage、parser/ontology/source-policy 版本、new accepted evidence conflict、reviewer supersede、cell/judgment version、permission/license/retention 变化、user correction/forget、TTL 到期。

- `stale`：可能过期，需要 refresh/review。
- `superseded`：由明确新版本替代。
- `revoked`：权限、许可、隐私或治理上禁止继续使用。
- `contradicted`：被当前 accepted evidence 明确冲突，保留为历史/反证。

TECH_03 `MemoryInvalidationEvent` 必须记录 trigger、affected memory/context plans、dependency refs、previous/new state、replacement refs、downstream reopen candidates 和 reviewer/permission refs。TECH_07 消费该 event，标记受影响 ContextInjectionPlan/attempt 并请求 recompile；不能自行改写 memory state。已注入但随后失效的 context 必须能追到受影响 attempt/artifact，不能静默删除历史。

## 19. ContextUsageObservation / AIE Feedback

每个 model/subagent attempt 后记录：injected refs/tokens、referenced/used refs、judgment/repair/conflict/citation contributions、unused refs、detected contamination/staleness、expansion requests、output artifact refs 和 cost。

AIE 使用这些 observation 优化 future selection、dedupe、budget 和 skill disclosure，但有两条边界：一次未被引用不能自动删除 governance/counterevidence；模型自报“有用”不能覆盖 provenance 或人工 eval。Selection policy 变更必须版本化，并通过 frozen context eval cases。

## 20. Permission / Privacy / Tenant / Retention / Forget

每个 ContextRequirement / InjectionPlan 绑定 TECH_06 `PermissionSnapshot`。ContextEngine 不跨 tenant/project/user scope，不把 private data、credential、raw scratchpad 或 restricted artifact 注入无权 actor。

Preference、institutional memory、private data 和 execution audit 使用不同 retention policy。用户 forget/revoke 请求产生 durable event：允许删除的 payload 按 policy 删除或加密销毁，相关 memory/context versions 标记 revoked；需要保留的合规审计只留最小 tombstone/hash/reason，不继续提供内容。Forget 不得被解释为修改历史研究事实，但所有后续 injection 必须排除 revoked payload。

Context plan 和 compression artifact 只保存 secret alias/category，不保存 API key/token。外部 source 内容中的 prompt injection 被标记为 untrusted content，不能进入 PinnedGovernanceContext、skill registry 或 tool permission。

## 21. Follow-Up / Repair Resume / What-Would-Change Continuity

用户追问不依赖完整聊天历史，而从 TaskRun events、CaseControlContext、DecisionSurfacePack、active cell/judgment heads、Evidence/Repair ledgers 和 prior ContextInjectionPlans 重建新 ContextRequirement。用户纠正、scope/as-of 变化或新问题必须生成新 context/cell version，并显式 supersede 旧假设。

Repair resume 保留 target cell、previous evidence-pack/judgment version、attempted routes、rejected substitutions、new evidence delta、unresolved conflicts 和 stop/budget state；只重新注入受影响 work unit。

What-Would-Change continuity 保留 decisive variables、causal rationale、strengthen/weaken/overturn branches、attempt/observation refs、directional assessment、remaining gaps、monitoring triggers 和 re-adjudication status。Compaction 不能把 scenario 变成 fact，或把 attempt-backed unknown 变成 negative conclusion。

## 22. ContextManager / ContextEngine / InjectionPlan Unified Entry

`ContextEngine` 是唯一 public runtime interface。现有 `SecAgentContextManager` 继续负责 session/user-message resolution 和 controller-context adapter，但不拥有独立的 selection/compression/memory truth；它必须把结果编译为 `ContextRequirement` 并调用 ContextEngine。

现有 `build_agent_data_view()` / RoleContextPack、R57 SQL-final ContextInjectionPlan、P33 ContextEngine fixture 和 writer/specialist prompt compaction 都应逐步通过统一 ContextEngine facade 注册 input/output digests、permission snapshot、selection decisions 和 usage observation，避免多个模块各自截断和压缩。

## 23. Fixtures / Evals / Current Boundary

第一批 fixtures：

1. ContextRequirement -> Snapshot/SelectionDecision/InjectionPlan replay。
2. role read/write matrix 与 private-context isolation。
3. hard filter 优先于 relevance；stale/revoked/cross-tenant candidate fail-closed。
4. reserved budget 保留 governance/task/evidence/counterevidence，optional background 不挤占。
5. progressive skill/artifact expansion 的 trigger、permission、cost 和 usage trace。
6. structural/semantic compaction preservation，覆盖 negation、gap、proxy、unit/period、conflict 和 forbidden claims。
7. self-compaction CompactionEvent / rollback / no source-of-truth mutation。
8. memory candidate -> review -> active -> stale/superseded/revoked/contradicted lifecycle。
9. filing/parser/source-policy/reviewer/user-forget 驱动 invalidation 和 downstream reopen。
10. ContextUsageObservation -> AIE policy proposal，但不得自动删除 governance/counterevidence。
11. follow-up reconstruction、repair delta resume、What-Would-Change continuity。
12. ContextManager/agent data view/ContextEngine unified facade parity。
13. ContextSnapshot compile-race fixture：底层 artifact/memory/skill version 变化时 fail/recompile，不混合版本。
14. Per-candidate ContextSelectionDecision reason fixture，覆盖 selected/rejected/deduplicated/externalized 全枚举。
15. ContextBlock ordering/digest 与 ContextInjectionPlan byte-stable canonical input reconstruction。
16. ContextExpansionRequest 生成新 plan version，旧 attempt plan immutable。
17. RoleContextPolicy version binding 与历史 plan explainability。

当前实现已有 `ContextEngine.resolve/select/compress/inject/write_memory` 骨架、role-scoped data view、context digest、P33 writer raw-dump blocking 和 R57/P13/P14 registry/lifecycle fixtures。但 selection 仍主要是 visibility/order/item/char cap，`token_budget` 不是完整 allocation；compression preservation fields 有限；memory write 只有基础 refs gate；TTL/freshness/supersession/forget/usage feedback 尚未统一；并非所有 live nodes 动态消费 SQL-final ContextInjectionPlan。

因此本节状态为 `documented / contract_draft`。现有 fixture 只证明 runtime-alignment / bounded role context，不证明生产级跨 run memory、self-compaction、governance-decay resistance 或多租户 privacy lifecycle 已完成。

## 24. 2026-07-11 Judge / Human Eval Context Extension

TECH_07 新增 `JudgeContextRequirement` 和 `HumanEvalContextRequirement`。它们绑定 EvalRunManifest、EvalSubject、OracleRoutingPolicy、rubric/evaluator versions、required source/artifact refs、candidate ordering/blinding policy、tenant/privacy、token budget 和 forbidden identity leakage。

Judge context 只能包含完成指定 metric 所需的 frozen subject 和 refs，不能看到 hidden holdout Gold、candidate/baseline/model identity 或不属于该 evaluator 的其他分数；无法完全隐藏时记录 blinding limitation。Human eval context 按 reviewer role 展示 research/compliance/presentation/operations rubric 和授权 drilldown，不因 reviewer 身份默认开放所有 private source。

Judge/Human context 与普通 Writer/Verifier/Domain context 分开生成 ContextSnapshot/SelectionDecisions/InjectionPlan。Evaluator output 只能进入 TECH_10 result envelope，不能写事实 memory、修改 Gold、晋升 evidence 或回流被评 agent 当前 attempt。

## 25. 2026-07-12 Memory Ownership Correction / ResearchCase Context

根据 TECH_00/03，本文第 17-18 节的 Memory Taxonomy、promotion 和 lifecycle 现解释为 `context-side memory admission`，不再构成长久 Institutional Memory source of truth。TECH_03 Memory Registry 拥有 entry/address/freshness/TTL/supersession/revocation/contradiction；TECH_07 只决定某次调用是否选择、如何压缩和注入 exact memory refs。

### 25.1 Updated ContextRequirement

ResearchCase 相关 ContextRequirement 必须携带 case/case-version、task/work-unit、target cell/claim、required business heads、as-of、role/purpose、freshness/permission、budget、config policy 和 expected output schema。它从 TECH_03 获取 MemoryCandidateBundle，从 TECH_01/02/04/05/09/11 获取 exact owner refs，不能从聊天摘要推断 current head。

ContextSelectionDecision 对每个 memory candidate 记录 `selected / rejected_permission / rejected_scope / rejected_stale / rejected_business_status / rejected_budget / deduplicated / externalized`。历史 accepted ref 若被 owner supersede/revoke，即使 embedding relevance 高也必须拒绝或显式注入为 historical/contradicted context。

### 25.2 Memory write path

现有 `ContextEngine.write_memory` 改为提交 `MemoryWriteCandidate` 到 TECH_03 registry；返回 candidate/ref/status，不得直接创建 active AcceptedFact/Judgment/Reviewer memory。ContextUsageObservation 可以提出 retention/dedupe/skill 改进建议，但无权撤销 business truth。

### 25.3 Case continuity

- follow-up：注入 CaseControlSummary、target cell heads、relevant evidence/numeric/judgment/review refs 和 prior answer boundary；
- refresh：注入 old/new source delta、affected-cell set、retained compatible heads 和 stale refs；
- reviewer correction：注入 correction exact scope、old/new refs 和 forbidden repeat；
- writer/reviewer：只注入 frozen/admitted exact versions，不因 memory 新鲜度排序改变 research truth。

### 25.4 Skill/config disclosure

SkillVersion、RoleContextPolicy 和 Institution configuration 都必须经过 TECH_06 active rollout state。ContextEngine 只注入 active/compatible versions，并记录为何未选择其他 Skill。Tenant Skill/Method 只能提供程序与 rubric，不能作为事实证据。

新增 fixtures：Memory Registry status 与 context selection 一致；stale/revoked owner ref fail-closed；同一 ContextInjectionPlan 可按 exact artifact/config versions 重建；follow-up 不依赖完整聊天；provider/model swap 不改变 business refs。

本节状态为 `documented / contract_draft`；现有 `write_memory` 骨架需 adapter/migration，不能继续作为并行长期 memory writer。
