# Institutional Research Positioning PRD / TECH Refactor Impact Audit Draft

日期：2026-07-12

状态：`historical_audit / canonical_update_executed_20260712 / non_canonical`

审计对象：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`
- `docs/architecture/agent_graph_vnext/TECH_00-11`
- `docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md`
- `INSTITUTIONAL_RESEARCH_CONTROL_MEMORY_POSITIONING_REFACTOR_DRAFT_20260712.zh-CN.md`

边界：本文保存拟更新审计及其决策依据，不 supersede canonical PRD、TECH、Point 01、runtime schema 或代码。2026-07-12 用户已确认按 PRD -> TECH_00/00A -> 上游 TECH -> 下游 TECH 的顺序执行；正式结果以已更新 canonical 文档为准。

## 1. 审计结论

现有规划不是“功能不够”，而是功能已经大量存在于 PRD 和 TECH_01-11 中，但尚未围绕同一个纵向研究生命周期形成统一产品主线和对象主账本。当前最主要风险是：

1. `ResearchTask / TaskRun / DecisionSurface / Workpaper / Artifact / Watchlist` 已分别定义，但缺少稳定的 `InstitutionalResearchCase` 聚合身份串联 initiation、follow-up、review、release、monitoring、refresh 和 supersession。
2. TECH_03 与 TECH_07 都描述 memory lifecycle；TECH_06 与 TECH_09 都描述 approval/artifact version；TECH_01 与 TECH_06 都接近 case/run 当前态。边界虽可解释，但尚未固定为“业务真相 owner、物理持久化 owner、消费者”。
3. PRD 仍以功能页面和一次性任务为主要组织方式，新定位只在 14.6 局部出现，未贯穿 ICP、用户故事、模块、验收、指标和非目标。
4. Human-AI Accountability 已有 actor_id、PermissionSnapshot、ReviewAction、Approval、hash 和 trace 基础，但没有统一 `ActorSnapshot -> AccountabilityEvent -> DecisionAttestation -> ArtifactProvenanceManifest` 合同。
5. TECH_00A 已覆盖大多数模块，却没有把配置治理、机构记忆、纵向 refresh、责任链和 provider-neutral capability 作为独立闭环行。

建议不新增万能 `TECH_12`。应先修订 TECH_00/00A 的对象宪法和 owner，再让各 TECH 文件只拥有本模块业务语义；TECH_06 负责执行持久化，TECH_03 负责记忆地址与 PIT，TECH_09 负责审核/发布语义，TECH_10 负责质量证明。

## 2. 拟冻结的文档关系

所有产品能力应经过同一条可追踪关系，禁止只写 PRD 功能或只写 TECH 对象：

```text
PRD capability / user story
 -> TECH_00 canonical object and owner
 -> owner TECH contract
 -> runtime store / API / event / adapter
 -> product surface
 -> TECH_10 eval and release gate
```

文档职责拟固定为：

| 文档 | 负责 | 不负责 |
| --- | --- | --- |
| PRD | 用户、价值、产品行为、surface、bounded claims、验收和指标 | SQL、事件字段和实现类 |
| TECH_00 | stable object graph、唯一业务 owner、跨模块接口、supersession 宪法 | 模块内部算法 |
| TECH_00A | PRD 到 TECH/runtime/surface/eval 的覆盖矩阵 | 代替详细技术合同 |
| TECH_01-11 | 各 owner 的对象语义、输入输出、状态、失败和 fixture | 创建第二套跨模块主账本 |
| Point 01 | 首个 migration slice、旧新 adapter、cutover/gate | 提前实现全部长期目标 |
| Worklog/定位草稿 | 决策历史、市场判断、待确认提案 | 生产 source of truth |

## 3. Stable Aggregate 与对象主线

建议 `InstitutionalResearchCase` 只做聚合身份和版本引用，不做万能大表：

```text
InstitutionalResearchCase
 -> CaseControlState
 -> TaskRun / WorkUnit / Attempt
 -> DecisionSurfaceVersion / CellVersion
 -> EvidenceRecord / PromotionDecision / GapRecord
 -> NumericProgramRun / ModelInputSnapshot / AssumptionSet
 -> JudgmentVersion / WhatWouldChangeProgram
 -> WorkpaperPackVersion / LeadReviewDecision
 -> ArtifactVersion / DecisionAttestation / ReleaseRecord
 -> MonitoringSubscription / ThesisDelta
 -> InstitutionalMemoryRef / SupersessionGraph
```

新增责任链对象候选：

| 对象 | 用途 | 拟业务 owner |
| --- | --- | --- |
| `ActorSnapshot` | 保存动作发生时的人、Agent、服务身份、组织角色和授权快照 | TECH_06 |
| `AccountabilityEvent` | 把动作、因果、对象、before/after version 与 ActorSnapshot 绑定 | TECH_06 |
| `DecisionAttestation` | 对 review/override/approval/waiver 的 exact target 作出业务确认 | TECH_09 |
| `ArtifactProvenanceManifest` | 绑定 artifact hash、AI involvement、claim/evidence/numeric/review/release refs | TECH_09 |
| `HumanAIAccountabilityGraph` | 从事件和 attestation 投影 Cell/Claim/Artifact 责任链 | TECH_09 projection，TECH_03 index |

## 4. Owner 冲突消解

### 4.1 ResearchCase、TaskRun 与 Workpaper

- TECH_01 拥有 `InstitutionalResearchCase`、CaseControlState、DecisionSurface、Gap、Workpaper 和 LeadReview 的研究业务语义。
- TECH_06 拥有 TaskRun/WorkUnit/Attempt/EventEnvelope、执行 current-state projection、版本并发、checkpoint 和物理持久化语义。
- TECH_09 消费 frozen research versions，拥有 reviewer-visible action、artifact、approval 和 release 的业务语义。
- SQL 中可以由 TECH_06 统一持久化，但不能因此把研究业务状态定义权移给 runtime。

### 4.2 Evidence 与 Numeric

- TECH_02 拥有 EvidenceRequest、搜索编排、候选分类、Evidence Gate promotion/rejection/typed gap 的业务语义。
- TECH_03 只返回 CandidateBundle，并保存 source/structure/index/repair history/accepted-memory refs。
- TECH_04 拥有 NumericFact、MetricDefinition、NumericProgramTrace、row/unit/period audit 和 numeric subgate。
- TECH_05 只能基于 CellEvidencePack/Numeric refs 形成判断，不能自己晋升证据。

TECH_00 当前“TECH_02/03/04/05 共同拥有 evidence objects”的表达应拆成 producer/owner/consumer，避免 joint ownership。

### 4.3 Institutional Memory 与 Context

- TECH_03 拥有 memory address、namespace、PIT snapshot、freshness、TTL、supersession、revocation、contradiction、repair cache 和 downstream dependency index。
- Evidence/Judgment/Review 的原始业务真相仍分别属于 TECH_02/04/05/09；TECH_03 保存 versioned refs 和可检索投影，不复制裁决权。
- TECH_07 拥有 ContextRequirement、SelectionDecision、InjectionPlan、compaction 和 usage observation；只决定本次调用读取什么。
- TECH_07 的 `MemoryCandidate promotion/lifecycle` 应改为调用 TECH_03 Memory Registry，并保留 context-side admission rules，不再成为第二个长期 memory source of truth。

### 4.4 Approval、Artifact 与 Accountability

- TECH_09 定义 review/approval/release/stale/withdraw/supersede 的业务含义，以及 exact artifact/claim hash 的 DecisionAttestation。
- TECH_06 保存 immutable events、approval bindings、ReleaseTransaction 和 permission/identity snapshots，执行 optimistic transaction 和 invalidation。
- TECH_03 建立历史 review/actor/supersession 索引，供 follow-up/PIT reconstruction 使用。
- TECH_10 检查 attribution completeness、approval escape、hash mismatch、stale leakage 和 employee-surveillance policy violation。

## 5. PRD 拟更新意见

PRD 核心功能已充足，不建议继续增加 persona 或数据源清单。建议做结构性重写而非继续在末尾追加：

1. **产品定位**：把 14.6 的“机构研究控制与记忆系统”提升到第 1 节；保留 `AI junior analyst layer` 作为执行层描述，不再作为完整产品定义。
2. **ICP 与用户故事**：增加 Analyst、Research Lead、+1/+2、Compliance、Data/Admin、External Client 的纵向协作故事；以 initiation、earnings update、follow-up、thesis revision、release 和 monitoring 为主线。
3. **产品平面**：把 6.x 页面模块归入 Research Control、Evidence & Modeling、Institutional Memory、Review & Delivery、Monitoring & Learning 五个平面，页面仍保留但不再是架构主线。
4. **Institutional Memory**：新增独立产品能力，明确 AcceptedFact/Judgment、ReviewerDecision、RejectedEvidence、CaseControl、Monitoring/Supersession History 的差异及权限。
5. **配置治理**：Admin 增加 Agent/Skill/Sector/Report-Type/source/graph/workflow/model provider 的 draft-publish-test-rollout-rollback 生命周期；hard invariants 不可由普通配置关闭。
6. **Human-AI Accountability**：Human Review/Admin 增加 Cell 责任链、AI involvement、review/approval history、OA/SSO/SCIM binding、audit package、retention/legal hold 和反员工监控边界。
7. **更强模型和搜索**：作为 table stakes 与持续 Capability Frontier，要求 provider-neutral、authority/license/cost/failure policy、fallback 和 shadow eval；不把通用搜索规模写成 FIN 自建目标。
8. **验收与指标**：以 L1 Artifact complete、L2 Research valid、L3 Reviewer accepted、L4 Longitudinally maintainable 分级，增加 time-to-approved-output、review burden、quarterly selective refresh、correction reuse、stale leakage 和 attribution completeness。
9. **非目标与 bounded claims**：继续明确公开源不等于实时全市场、 sampled discourse 不等于总体舆情、Research-to-Quant 不等于自动交易、AI attribution 不等于自动法律归责。
10. **清理陈旧章节**：第 12 节“后续需拆技术文档”和第 13 节开放问题应对照已存在 TECH_01-11 更新状态，避免 PRD 继续声称尚未拆分。

## 6. TECH_00 / TECH_00A 拟更新意见

### 6.1 TECH_00

- 在 Stable Object Graph 顶部加入 `InstitutionalResearchCase`，但明确其是 aggregate identity/ref graph，不是物理大表。
- 增加 `ActorSnapshot / AccountabilityEvent / DecisionAttestation / ArtifactProvenanceManifest`。
- owner matrix 增加三列：`business truth owner`、`physical persistence owner`、`read/index/projection consumer`。
- 把 evidence joint ownership 拆成 TECH_02 promotion、TECH_03 candidate/address、TECH_04 numeric、TECH_05 judgment。
- 明确 TECH_03/07 memory、TECH_06/09 approval、TECH_01/06 case/run 的边界。
- 增加配置对象：`AgentDefinitionVersion / SkillVersion / GraphOntologyVersion / WorkflowPolicyVersion / ProviderPolicyVersion`。
- stable object 必须声明 identity、version、as_of/available_at、supersession、permission、retention、producer/consumer 和 TECH_10 eval owner。

### 6.2 TECH_00A

新增或拆分以下覆盖行：

- Institutional ResearchCase Lifecycle；
- Institutional Memory / PIT Reconstruction；
- Agent/Skill/Graph/Workflow Configuration Governance；
- Human-AI Accountability / OA Identity；
- Longitudinal Follow-up / Quarterly Selective Refresh；
- Cross-artifact Claim/Number Update and Reapproval；
- Provider-neutral Model/Search/Data Capability Frontier；
- External Platform Capability / Replacement Pressure Eval。

每行补充 TECH_10 metric/gate，不能只到 runtime/product surface。

## 7. TECH_01-11 逐文档拟更新

| 文档 | 保留的主职责 | 拟补充/重构 | 关键输入输出关系 |
| --- | --- | --- | --- |
| TECH_01 | Agentic Research Loop、DecisionSurface、Gap/Repair、Workpaper、LeadReview | ResearchCase lifecycle、CaseControlState、follow-up/refresh/reopen、CaseControlSummary、research semantic event | 收 UserTask/Memory refs；出 versioned Cell/Workpaper/WriterAdmission |
| TECH_02 | Agentic Search、Tool Planner、Evidence Gate、SourceHunter | EvidenceRecord identity、rejection reason、definition conflict、MemoryWriteCandidate、provider-neutral route | 读 Cell/EvidenceSlot；收 CandidateBundle/NumericGate；出 PromotionDecision/Gap |
| TECH_03 | Source/Document/Element/Candidate/Graph/Memory address layer | 统一 Memory Registry、PIT reconstruction、dependency index、accepted/rejected/reviewer refs、privacy/retention index | 读各业务 owner 的 immutable refs；向 TECH_02/07/11 返回 Candidate/Memory bundles |
| TECH_04 | Parser、NumericFact、MetricDefinition、NumericProgramTrace | ModelInputSnapshot、AssumptionSet、ScenarioRun、program version、selective recompute 和 artifact numeric lineage | 读 source/table candidates；出 numeric decision/trace 给 TECH_02/05/09 |
| TECH_05 | DomainOperator、Judgment、Counterevidence、WWC | JudgmentVersion/delta/supersession、reviewer-adjusted judgment、monitoring-trigger impact | 读 CellEvidencePack；出 JudgmentPack/WWC/CellDependency delta |
| TECH_06 | Durable runtime、Event、permission、budget、HITL persistence | ResearchCase execution binding、ActorSnapshot、AccountabilityEvent、identity/OA hooks、retention/redaction event | 执行其他 TECH 的业务状态命令；保存不可变事实，不重新定义业务语义 |
| TECH_07 | ContextEngine、Skill disclosure、compaction、usage observation | 取消长期 memory truth 重叠；消费 MemoryRef；增加配置版本/role policy 的 injection | 收 ContextRequirement + version refs；出 replayable InjectionPlan |
| TECH_08 | Subagents-as-tools、handoff、parallel impact、AgentDefinition | Agent/Skill selection contract、institution-configured role bounds、causal message actor/authority | 只交换 versioned delta/proposal；不直接写 shared truth |
| TECH_09 | Provenance、Workbench、Writer、ArtifactConsistency、review/release | DecisionAttestation、ArtifactProvenanceManifest、AI involvement disclosure、OA workflow、human edit attribution | 读 frozen research truth；出 reviewed/released artifact and accountability projection |
| TECH_10 | Eval、failure attribution、release quality、AIE | L1-L4 success、longitudinal maintenance、provider swap、accountability completeness、correction reuse | 对所有主对象和 product surface 建立 eval/gate |
| TECH_11 | Watchlist、MonitoringRule、Alert/ThesisDelta | affected Cell/Claim/Artifact routing、selective refresh request、stale propagation | 收 observations；出 targeted reopen/refresh/invalidation，不写 accepted truth |

## 8. Point 01 拟更新意见

Point 01 当前最小 Control Kernel + DecisionSurface Planning Shadow 路线仍合理，不应因新定位膨胀为全系统重写。建议只增加最薄的未来兼容接口：

1. 增加 `InstitutionalResearchCaseId / CaseVersion`，作为 legacy TaskRun binding 与 DecisionSurface artifact 的稳定父身份。
2. `EventEnvelope` 预留 ActorSnapshotRef、case_id、object_ref 和 policy/config versions；第一阶段不实现完整 OA。
3. `ArtifactVersion` 明确属于 Case，并可被后续 Workpaper/Review/Memory/Artifact graph 引用。
4. compiler 输出 `CaseControlSummary` 与 `MemoryCandidate` 只能作为 draft/ref，禁止自动 promotion。
5. 增加最小 compatibility tests：同一 case follow-up 可定位旧 Cell；review correction 可记录 invalidation；quarterly update 可生成 affected-cell set；artifact ref 可标记 stale。
6. 第一阶段不实现完整 Evidence、Numeric、Judgment、Workbench、OA、Monitoring，只冻结接口和 fixture，以防 M2 后重做 identity。

原计划第 3.3 节“第一阶段明确不实现的对象”需要保留；新增内容应标为 identity/ref compatibility，而不是功能 cutover。

## 9. 跨文档接口清单

正式更新前至少冻结以下接口，防止功能关系断连：

| 接口 | Producer | Consumer | 必须携带 |
| --- | --- | --- | --- |
| `ResearchCaseCreated/VersionAdvanced` | TECH_01 via TECH_06 | 03/07/09/10/11 | case/version/scope/as_of/actor/policy refs |
| `EvidenceRequest` | TECH_01/05 | TECH_02 | case/cell/slot/entity/period/source policy/forbidden substitution |
| `CandidateBundle` | TECH_03 | TECH_02 | source/structure/freshness/lineage/expansion/permission |
| `PromotionDecision` | TECH_02 + TECH_04 numeric hard gate | TECH_01/05/03/09 | accepted/context/rejected/gap、reason、exact refs |
| `MemoryWriteCandidate` | TECH_02/04/05/09/11 | TECH_03 | source business owner、status、as_of、TTL、permission、supersession |
| `ContextRequirement` | TECH_01/06/08 | TECH_07 | role、task/cell、version heads、budget、permission |
| `JudgmentVersion/Delta` | TECH_05 | TECH_01/03/09/11 | evidence/numeric refs、confidence、WWC、supersession |
| `ReviewRequest/DecisionAttestation` | TECH_01/09 | TECH_06/03/10 | exact target versions/hash、actor、authority、conditions |
| `ArtifactInvalidationRequest` | TECH_02/03/04/05/11 | TECH_09 via TECH_06 | changed refs、impact scope、materiality status、required action |
| `RefreshRequest/ThesisDelta` | TECH_11 | TECH_01/05/09 | observation、affected cells、old/new heads、monitor rule |

## 10. 文档更新顺序

为避免先改局部、后补关系，建议按以下顺序执行 canonical 更新：

1. **D0 Decision freeze**：确认 aggregate 名称、owner 冲突消解、Accountability 对象、Point 01 最小范围。
2. **D1 TECH_00 + TECH_00A**：先固定对象宪法、覆盖矩阵和跨文档链接。
3. **D2 PRD**：按已冻结对象关系重构定位、生命周期、surface、验收和 bounded claims，不复制技术字段。
4. **D3 TECH_01 + TECH_06**：同步定义 ResearchCase 业务状态与 durable execution/actor event，防止产生两套 case state。
5. **D4 Point 01**：只吸收 D1/D3 已冻结的 identity/ref compatibility，然后更新 migration gate。
6. **D5 TECH_02 + TECH_03 + TECH_04 + TECH_05**：固定 candidate/evidence/numeric/judgment/memory 的 producer-owner-consumer。
7. **D6 TECH_07 + TECH_08**：Context/Agent/Skill 只消费已冻结对象和权限，不再创造平行 memory。
8. **D7 TECH_09**：接入 exact frozen versions、Accountability、artifact/release/stale contract。
9. **D8 TECH_11**：接入 targeted refresh 和 stale propagation。
10. **D9 TECH_10**：汇总每个 owner 的 fixture、L1-L4 success 和 release gate，并反查 TECH_00A 无 orphan。

每一步完成后更新 TECH_00A；不得等所有文档改完再一次性补 coverage matrix。

## 11. 文档重构方式

- 不建议继续在每份 TECH 末尾无限追加日期 section。先增加一份 dated refactor contract，确认后把重复内容合并回 owner section，并更新 revision note。
- 不删除旧语义；使用 `superseded_by`、迁移说明和 legacy mapping，保留 P36/WorkBuddy/旧 R-series 的证据边界。
- 对象命名只在 TECH_00 定义一次；其他 TECH 使用链接和本地扩展，禁止复制不同字段版本。
- PRD 使用用户语言；TECH 使用合同语言；Point 01 使用实施/gate 语言；worklog 保存为什么改变。
- 每个新增对象都要有一个业务 owner，允许另有物理持久化 owner，但不能有两个 writer。
- 每个新增产品功能都要有 runtime state、product surface 和 TECH_10 eval；缺任一项标为 `contract_gap`，不能宣称 planned closed。

## 12. 审计发现分级

### Critical

1. 缺少贯穿纵向生命周期的 `InstitutionalResearchCase` aggregate identity。
2. Evidence 对象 joint ownership、TECH_03/07 memory lifecycle 重叠可能形成第二套 source of truth。

### High

1. Human-AI Accountability 没有 canonical object chain 和产品 surface。
2. TECH_06/09 approval/release 的业务与持久化 owner 尚未在 TECH_00 明确区分。
3. Follow-up、quarterly refresh、reviewer correction 和 cross-artifact reapproval 尚未成为 PRD 主验收链。
4. Agent/Skill/Graph 自由度已有原则，但缺机构配置发布、测试和回滚的统一产品合同。

### Medium

1. TECH_00A 未映射 eval owner，且缺少新定位的独立 coverage rows。
2. PRD 第 12/13 节部分内容已被 TECH_01-11 实现为合同但未回写状态。
3. provider-neutral 模型/搜索能力分散在 TECH_02/06/08/10，缺统一 capability policy ref。
4. 责任链需要明确隐私、retention、legal hold 和 usage analytics 隔离，避免审计变成员工绩效监控。

## 13. 建议保持不变的核心边界

- Writer no-source；发现 blocker 必须返回 Lead/owner repair。
- Reranker 只排序 candidate，不能决定 evidence promotion。
- Evidence Gate 使用 deterministic hard rules + bounded semantic suggestion；Lead 不能 override hard fail。
- Chunk 是 retrieval unit，不是 evidence unit；表格和数值必须有 lineage/NumericProgramTrace。
- Supervisor supplement 不能伪装成 runtime evidence。
- Agent 使用独立上下文并通过结构化 delta/proposal 通信。
- RunEvent 和 ArtifactVersion immutable；approval 绑定 exact version/hash。
- What-Would-Change 是独立 counterfactual/monitoring program，不静默改主结论。
- TECH_11 保持独立 owner，但只触发 targeted research，不绕过 Evidence/LeadReview/Release。

## 14. 文档重构完成标准

完成 canonical 更新后应满足：

1. 每个 PRD capability 都能映射到一个 TECH business owner、runtime state、surface 和 eval。
2. 每个 canonical object 只有一个业务真相 writer，并明确物理持久化 owner和消费者。
3. 同一 ResearchCase 能解释当前 head、历史版本、当时 as-of、actor、evidence/numeric/judgment、review、artifact 和 monitoring delta。
4. 任一 accepted/rejected evidence、numeric correction、review override 或 source revision 都能找到受影响的 Cell、Claim、Artifact 和 approval。
5. Point 01 不实现超出首 slice 的功能，但其 ID、event 和 artifact contract 不阻塞后续 Memory/Review/Accountability。
6. TECH_00A 不存在 orphan PRD row、orphan TECH object 或无 eval owner 的 release-sensitive capability。
7. 文档中的 `documented / runtime_partial / product_partial / proven` 状态与代码和 fixture 证据一致，不因文档更新自动提级。

## 15. 待用户确认后才能执行的修改

1. 是否正式采用 `InstitutionalResearchCase` 名称及其 aggregate 边界。
2. 是否接受 TECH_03/07、TECH_06/09、TECH_01/06 的 owner 拆分。
3. Point 01 是否只增加 identity/ref compatibility，而不扩成完整纵向闭环。
4. Human-AI Accountability 的近期范围：仅内部审计对象，还是同步进入 OA/SSO/SCIM 产品规划。
5. PRD 是否按五个产品平面重排现有 6.x 模块，还是先保留目录并增加跨模块生命周期章节。
6. canonical 更新采用“先追加 dated contract、后合并”，还是一次性重排章节并保留 supersession 附录。
