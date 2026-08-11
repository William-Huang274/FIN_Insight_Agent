# Institutional Research Control And Memory Positioning Refactor Draft

日期：2026-07-12

状态：`historical_discussion / absorbed_into_canonical_20260712 / non_canonical`

边界：本文保存 2026-07-12 关于“机构研究控制与记忆系统”的讨论轨迹，不修改或 supersede canonical source of truth。2026-07-12 经用户确认后，核心定位已按 upstream-first 顺序吸收到 PRD、TECH_00/00A、TECH_01-11 和 Point 01；后续以这些 canonical 文档为准，本文仅用于解释决策来源。

## 0. 阅读导航与讨论状态

本文按四组内容组织，避免把定位、产品、技术和治理讨论混成一条线：

| 主题组 | 对应章节 | 当前状态 | 后续去向 |
| --- | --- | --- | --- |
| 定位与产品主线 | 1-7 | `proposed_for_review` | PRD、TECH_00/00A、Point 01 |
| 可配置性与能力竞争 | 8-11 | `proposed_for_review` | PRD Admin/Governance、TECH_06-08、TECH_10 |
| 差异化与机构采用 | 12-15 | `proposed_for_review` | PRD positioning/metrics、TECH_10 eval |
| Human-AI Accountability | 16-17 | `proposed_for_review` | PRD Review/Admin、TECH_03/06/09/10 |

已形成稳定倾向、但尚未进入 canonical 文档的内容包括：

- `InstitutionalResearchCase` 应成为纵向研究生命周期的聚合身份，Report 只是受控投影；
- `DecisionSurface + Evidence/Numeric Control + PIT Memory + Durable Review + Cross-artifact Consistency` 是统一主线；
- Agent/Skill/Graph 可以配置，但 hard evidence/numeric/permission/release invariants 不可被普通配置关闭；
- 更强模型、搜索、行业 Pack 和交付能力必须持续建设，但通过 provider-neutral 接口接入控制与记忆主干；
- Human-AI Accountability 复用 Event/Review/Provenance/Memory/Eval，不另建平行日志栈。

仍需正式裁决的内容包括：对象最终命名、业务真相与物理持久化 owner、Point 01 第一阶段纳入范围、OA/身份系统的近期实现深度、visible AI disclosure policy，以及各机构配置项的默认权限级别。

配套影响审计见 `INSTITUTIONAL_RESEARCH_POSITIONING_PRD_TECH_REFACTOR_IMPACT_AUDIT_DRAFT_20260712.zh-CN.md`。该审计负责说明这些提案应如何映射到 PRD、TECH_00-11、Point 01、runtime 和产品 surface；本文继续保存讨论本身。

## 1. 暂定产品定位

FIN 不应只被定义为生成金融研究报告的多 Agent，而应被定义为面向金融机构和专业服务团队的机构研究控制、协作与记忆系统：Agent 负责执行研究，FIN 负责让研究过程可控制、可复核、可延续、可追责。

主链路暂定为：

```text
用户问题
 -> InstitutionalResearchCase
 -> DecisionSurface
 -> Evidence / Numeric / Judgment
 -> Workpaper
 -> Human Review
 -> ArtifactSet / Release
 -> Institutional Memory
 -> Follow-up / Monitoring / Refresh / Supersession
```

Report 不再是主状态，而是 ResearchCase/Workpaper 的一个受控投影；Agent 不拥有事实真值；RAG/DB/Graph/Web 是候选与记忆基础设施；Review、Release、Monitoring 和 Memory 是一等生命周期。

## 2. PRD 暂定重构方向

### 2.1 产品定义与 North Star

North Star 从“能否生成高质量报告”转向：time-to-reviewer-ready、material claim lineage、numeric reproducibility、follow-up continuity、quarterly selective refresh、reviewer correction reuse、cross-artifact consistency 和 release escape。

### 2.2 ICP

核心 ICP 暂定为存在多人协作、私有/商业数据、数值模型、复核责任、历史追问和正式交付要求的买方/卖方研究、咨询、企业战略及其他专业服务团队。只需要一次公开资料报告的用户不是主要差异化对象。

### 2.3 五个产品平面

1. Research Control Plane：Task Center、ResearchCase、DecisionSurface、LeadReview、Repair/Gap、Assignment/Handoff。
2. Evidence & Modeling Plane：Evidence Workbench、Data Room、RAG/DB/Web/Graph、Numeric/Valuation/Scenario、Claim lineage。
3. Institutional Memory：Accepted Fact/Judgment、Reviewer Decision、Case Control、Method/Playbook、Monitoring History。
4. Review & Delivery：Workpaper、Review Queue、ArtifactConsistency、Deliverable Studio、Approval/Release。
5. Monitoring & Learning：Watchlist、What-Would-Change、staleness、incremental refresh、Eval、governed improvement。

### 2.4 能力分层

- Table stakes：Agentic Search、Deep Research、金融 Skill、公司比较、HTML/图表/dashboard、WWC、多格式输出、基础 fallback。
- Core differentiation：Evidence Gate、NumericProgramTrace、point-in-time memory、Reviewer Memory、private/licensed data、durable workflow、cross-artifact consistency、approval/release、incremental refresh。
- Optional expansion：更多 persona、更多通用源、自动组合建议、复杂舆情、高频衍生品、自动交易。

### 2.5 ResearchCase 生命周期

```text
Initiate -> Research -> Review -> Release -> Monitor -> Refresh -> Supersede -> Archive
```

PRD 需要覆盖 follow-up、reviewer correction、new-quarter refresh、private/public conflict、artifact staleness 和 multi-format synchronized update 等纵向用户故事。

## 3. TECH 暂定重构方向

### 3.1 TECH_00

新增 `InstitutionalResearchCase` 聚合主图，但不形成万能大表：

```text
InstitutionalResearchCase
 |- TaskRun / CaseControlState
 |- DecisionSurfacePack
 |- EvidenceRecord / GapRecord
 |- NumericProgramTrace
 |- DomainCellJudgmentPack
 |- WorkpaperPack
 |- ReviewDecision
 |- ArtifactSet / ReleaseRecord
 |- MonitoringSubscription
 `- InstitutionalMemoryRefs
```

TECH_00 需要固定 owner、source of truth、version/supersession、read/write、retention、product surface 和 eval coverage。

### 3.2 TECH_01-11 Owner 调整

- TECH_01：ResearchCase 业务语义、DecisionSurface、coverage、case stop/reopen、follow-up answerability、thesis revision。
- TECH_02：Evidence identity、claim boundary、metric definition、conflict、promotion、supersession 和 rejection memory。
- TECH_03：source/structure/candidate 之外，明确拥有 accepted institutional memory 的版本化地址、freshness、TTL、supersession 和 PIT reconstruction；不拥有业务裁决。
- TECH_04：NumericProgram、ModelInputSnapshot、AssumptionSet、ScenarioSet、recompute 和 model/artifact lineage。
- TECH_05：Judgment revision、evidence delta、confidence change、WWC monitoring trigger 和 judgment supersession。
- TECH_06：TaskRun/WorkUnit/Event 执行事实、durable ResearchCase、selective resume、approval invalidation 和 stale propagation。
- TECH_07：只决定本次调用注入什么；长期 memory existence/source of truth 归 TECH_03 及其上游 owner。
- TECH_08：Agent 通过 EvidenceDelta、JudgmentDelta、Gap、RepairTicket、ReviewRequest、ArtifactPatchProposal 通信，不以自由聊天作为共享真值。
- TECH_09：Workpaper review、ArtifactSet、cross-artifact consistency、exact-version approval、release/stale/withdraw/supersede。
- TECH_10：增加 accepted evidence、numeric replay、follow-up、PIT reconstruction、reviewer reuse、selective refresh、artifact consistency 和 external platform replacement-pressure eval。
- TECH_11：Watchlist 作为 memory refresh engine，把新 Observation 路由到受影响的 cell/model/artifact 和 targeted repair。

不暂定新增万能 TECH_12；Institutional Memory 是跨模块主线，TECH_03 拥有存储/寻址生命周期，其他 owner 保留 evidence/judgment/review 的业务真值。

## 4. Point 01 暂定重构方向

Point 01 不再只以“DecisionSurface compiler 可运行”为最终目标，而是第一个可以持续存在、恢复、追问和增量更新的 `InstitutionalResearchCase` slice。

第一阶段最小对象候选：

```text
InstitutionalResearchCase
TaskRun binding
DecisionSurfaceContract / Version
WorkpaperPack / WorkpaperEvent
GapRecord
CaseControlSummary
ArtifactRef
MemoryCandidate
```

新增四类验收 fixture：

1. Follow-up continuity：恢复原 cell/evidence/judgment 回答追问。
2. Reviewer correction：被拒 row 不再静默进入后续 accepted pack，并生成 repair request。
3. Quarterly refresh：只失效并重跑受影响 cell，输出 thesis delta。
4. Cross-artifact staleness：同一 claim/number 在 memo/model/deck/dashboard 中同步失效和重新审批。

Point 01 cutover 除 compiler/schema 外，还需验证 version history、Case resume、reviewer correction reuse、MemoryCandidate no-auto-promotion 和 artifact stale propagation。

## 5. Runtime / Repository 暂定重构方向

1. Report 从主状态降为 `ResearchCase -> WorkpaperPack -> reviewed artifact projection`。
2. Candidate Store、Accepted Research Memory、Artifact/Review Store 至少逻辑隔离。
3. DecisionSurface、EvidencePack、JudgmentPack、Workpaper、Artifact、ReviewDecision 使用 immutable version + supersession。
4. 旧 parser/RAG/market/graph 通过 adapter 输出 canonical candidate/evidence schema。
5. 旧 required-item/dimension 保留限时 compatibility projection；Writer 改读 WorkpaperPack，lane 迁移完成后再 archive 旧直接路径。
6. 不做大爆炸重写；先统一 canonical aggregate、store interface、event 和 acceptance fixtures。

## 6. 暂定工程优先级变化

```text
1. InstitutionalResearchCase canonical aggregate
2. Versioned Workpaper/Event/Memory contracts
3. Evidence/Numeric identity
4. Follow-up and quarterly refresh
5. Reviewer correction
6. Artifact consistency/release
7. Sector/Agent/Skill/search/output expansion
```

这里的“排后”不是不重要，而是要求更强 Agent、搜索、行业 Pack 和交付能力接入稳定控制与记忆主干，避免再次成为独立临时状态。

## 7. 待讨论问题

1. Agent role、Skill、Graph、Sector Pack、workflow 和 source policy 应开放多少机构级/用户级配置自由度；哪些 hard invariants 不允许修改。
2. 更强模型和更强搜索的最低当前要求、持续升级路线、provider abstraction、shadow eval 和最终理想状态。
3. 与 FactSet RMS、AlphaSense、Rogo、Hebbia、Intapp DealCloud、Palantir AIP 等相邻产品的边界；FIN 是全新赛道还是既有研究管理/市场情报/AI workflow 的融合升级。

以上问题尚未裁决，不得仅凭本文进入 canonical PRD/TECH/Point 或 runtime backlog。

## 8. Agent / Skill / Graph 的暂定可配置自由度

核心原则：自由度与动作对共享真值、机构记忆和正式交付的影响反向相关。

| 动作 | 暂定自由度 |
| --- | --- |
| 搜索、探索、提出假设 | 高 |
| 选择 Agent、Skill、工具和分析维度 | 中高 |
| 写入共享 Workpaper | 中 |
| 晋升 Evidence/Fact/Judgment | 低 |
| 修改硬规则、权限和数值口径 | 很低 |
| 对外发布 | Human approval |

### 8.1 不可配置的系统宪法

Provenance、permission/audit、evidence identity、period/entity/unit binding、NumericProgramTrace、immutable version、writer no-source、secret redaction、exact-version release，以及 rejected evidence 不得静默晋升，不允许被普通机构配置关闭。例外只能通过带 reason/scope/owner/expiry 的受审 waiver，不能抹去 hard-fail history。

### 8.2 机构级配置

机构可配置 Agent role、Skill pack、Sector/Report-Type Pack、source authority、licensed provider、Graph ontology、review/approval chain、institution terminology、house style、retention、budget 和 model allowlist。所有配置采用 draft/published/superseded version、owner、permission、sandbox eval、release 和 rollback，而不是直接编辑生产 prompt。

### 8.3 Case 级控制

Research Lead、PM 或 Senior Analyst 可增删 DecisionSurfaceCell、激活/禁用 Specialist、指定来源、调整搜索预算、添加内部假设、指定 WWC 和交付格式、要求 repair/stop，并可 override soft judgment；不得把 rejected evidence 改为 accepted 或让 Writer 绕过证据链。

### 8.4 Agent 自主空间

Agent 在 CapabilityGrant、budget 和 stop policy 内可改写 query、切换 fallback、扩展邻居/section、发现 gap、请求 clarification、提出 provisional cell、选择 Skill 和生成 RepairTicket。`AgentRole` 不等于 Persona Prompt，而应是 objective、allowed context、capability grants、tools、output schema、budget、escalation 和 reviewer 的版本化合同。

Skill 应有 version、owner、precondition、input/output、permission、cost、tests、applicable sectors 和 release status。Graph 分为 VerifiedFactGraph、InstitutionOntologyGraph、Hypothesis/MechanismGraph 和 CaseViewGraph；用户可扩展 ontology/view/hypothesis，但不能把 hypothesis edge 伪装成 verified edge。

## 9. Control Spine 与 Capability Frontier 双轨优先级

“更强 Agent、更多搜索、更多行业 Pack、更漂亮报告排后”修正为双轨并行，而不是能力建设暂停：

```text
Control / Memory Spine        Capability Frontier
----------------------        -------------------
ResearchCase                  Stronger models
Evidence/Numeric identity     Stronger search
Workpaper/Review              Better tools and agents
Version/Memory                More sector skills
Artifact consistency          Better rendering
```

Control Spine 优先冻结接口和 source of truth；Capability Frontier 从第一阶段就保持可插拔升级。当前需实现 multi-provider ModelAdapter、SearchProviderRegistry、官方源/通用 Web/内部 KB/商业源统一 CandidateBundle、provider cost/authority/jurisdiction/license/failure policy、shadow comparison 和 fallback。无需自建全球网页索引或 foundation model。

理想状态是 Lead/Search Planner 按任务动态选择 DeepSeek/GPT/Gemini/其他模型与 Google/Tencent/official/internal/licensed routes；所有结果进入统一 Evidence/Numeric/Memory/Review 对象。模型升级可以减少 repair、提高 coverage 和 judgment quality，但不能拥有机构 source of truth，也不能带走 private data、accepted memory、review decisions、approval history 和 cross-artifact graph。

更强模型不会带来绝对防替代。可持续优势来自数据集成、历史研究资产、组织流程、治理、交付一致性和迁移成本；如果通用平台也完整实现这些能力，FIN 仍会面临直接竞争。

## 10. 市场类比与暂定赛道判断

FIN 不是完全无人覆盖的新赛道，而是几个已验证市场的融合：

| 参照产品 | 已验证能力 | 对 FIN 的含义 |
| --- | --- | --- |
| FactSet RMS / IRN | 内部研究、推荐历史、协作、可配置流程、合规记录、GenAI draft | 最接近机构研究控制与记忆的传统基座 |
| AlphaSense / Tegus | premium content、structured financials、Deep Research、multi-agent、custom agents、monitoring、slides | 强数据与 Agentic Research 对手 |
| Rogo | 投行/PE/资管 Agent、内外部数据、Excel/PPT/Word、firm templates、RBAC/audit/single tenant | 最直接的金融 Agent/workflow 竞品 |
| Hebbia Matrix | 大规模文档分析、可配置 Matrix/agent workflow | 文档工作台与用户自定义参照 |
| Intapp DealCloud | 行业数据模型、relationship graph、configurable workflow、RBAC/audit、专业服务 system of record | 机构对象、流程和关系记忆参照 |
| Palantir Foundry/AIP | ontology、data/logic/workflow、third-party model connectivity、agent/eval/governance | model-neutral control plane 技术参照 |

暂定类别：`AI-native Research Management System / Institutional Research Operating System`。

可描述为：FactSet RMS 的研究记忆与合规 + AlphaSense 的内容/Search + Rogo 的金融 Agent/Office workflow + Hebbia 的文档工作台 + Intapp 的行业对象/流程 + Palantir 的 ontology/governance/model-neutral runtime。

战略上不与 Google/Tencent 竞争通用索引，不与模型公司竞争 foundation model，不与 AlphaSense/Bloomberg/FactSet 正面重建全部 premium data；FIN 应接入这些能力，并拥有 InstitutionalResearchCase、DecisionSurface、Evidence/Numeric control、PIT Memory、Durable Review 和 ArtifactConsistency 的统一状态与工作流。

Rogo、AlphaSense 和传统平台正在快速覆盖上述交集，因此当前差异化只是一组待实现、待验证的组合假设，不是已建立护城河。

## 11. 新增待讨论：组合差异化与采用障碍

下一轮需验证：

1. 为什么 DecisionSurface、Evidence/Numeric、PIT Memory、Durable Review、Cross-artifact 尚未在一个产品中形成统一标准；
2. 金融机构/咨询公司对现有 AI research/workflow 产品仍观望的原因，区分产品缺陷、集成/治理成本、采购周期、组织变革和监管责任；
3. 哪些能力可直接借鉴，哪些必须重做，哪些只需率先达到稳定 task success rate；
4. FIN 应以哪些 wedge 进入市场，而不是同时重建所有平台；
5. 如何用 success rate、review burden、time-to-approved-output、numeric/citation hard fail 和 longitudinal reuse 证明可用，而不是依靠功能清单。

## 12. 为什么完整组合尚未形成统一标准

五个部分单独已有成熟或快速发展的产品，但公开产品中心对象不同：AlphaSense 更接近 source/document/search result，Rogo 更接近 finance task/work output，FactSet RMS 更接近 research note/recommendation，Intapp DealCloud 更接近 deal/relationship/engagement，Palantir 更接近 ontology object/action。

FIN 暂定以同一个 `DecisionSurfaceCell / Claim` 串起：

```text
DecisionSurfaceCell
 -> Evidence
 -> NumericProgram
 -> Judgment
 -> Review
 -> ArtifactClaim
 -> Monitoring
 -> Revision / Supersession
```

每层共享 cell_id、claim_id、version 和 as_of。当前公开资料尚未明确展示某一产品把同一 Claim 从搜索、计算、判断、审核、多交付物到下一季度刷新全部作为统一对象链；这是基于公开产品描述的推断，不代表厂商内部一定没有。

Citation 不等于 Evidence Control：还需验证 source entailment、entity/period/unit/definition、proxy、supersession、accepted/rejected reason 和 numeric replay。Structured financial data 也不等于 Numeric Control：还需 input snapshot、formula/program、assumption owner、intermediate values、reviewer override、multi-artifact binding 和 selective recomputation。

Research note/chat/task memory 也不等于完整 Institutional Memory；目标组合是 AcceptedFact、AcceptedJudgment、ReviewerDecision、RejectedEvidence、CaseControl 和 Monitoring/Supersession History。多格式导出不等于 Cross-artifact consistency；目标是 approved Claim version 绑定 memo/PPT/Excel/dashboard，新 evidence 触发所有相关 artifact stale、recompute 和 reapproval。

## 13. 机构采用障碍与竞品问题假设

市场采用不是零：AlphaSense、Rogo、FactSet、Intapp 已有真实机构客户。尚未全面普及的是让 Agent 独立承担高影响研究、模型、建议和正式交付责任。采用速度不能只归因于产品质量，还受 procurement、security/legal/model-risk review、data migration、training 和组织变革影响。

当前需要验证的七类障碍：

1. 平均准确率可用，但低频、难发现的 hard fail 仍不足以放心授权；机构关心 failure severity、pre-release capture、replay 和 responsibility。
2. 数据质量、权限、内部系统碎片和 interoperability 限制真实工作流接入。
3. 第三方模型/云依赖带来 concentration、outage、data residency、training use、model upgrade drift 和 exit risk。
4. 监管和监督责任不能外包给供应商；citation 不能替代 supervisory procedure、approval、retention、model inventory 和 incident handling。
5. 个人试用不等于组织 integration；Senior trust、Compliance policy、IT integration、ROI 和 user training 决定规模化。
6. 完全通用平台配置成本高，过度垂直平台又可能不适配；自由度与治理之间存在产品矛盾。
7. 机构采购、历史迁移和 workflow change 周期长，即使产品有效也不会立即全量替换。

对具体竞品的结论必须保持证据边界：不能因公开资料未展示某能力就断言内部不存在；应记录 `publicly_demonstrated / vendor_claimed / customer-validated / not_observable / independently_tested`。

## 14. 暂定差异化方式

差异化不要求每项原创，可以来自：

1. 把 FactSet-style research memory、AlphaSense-style content/search、Rogo-style finance agents、Intapp-style workflow 和 Palantir-style ontology/governance 围绕 InstitutionalResearchCase 统一；
2. 把已有但不稳定的 citation、financial data、review、memory、multi-format 和 customization 做成 claim-local、numeric-replayable、exact-version、PIT、stale-propagating 和 governed；
3. 更早达到稳定的 reviewer-accepted task success rate，而不是更早生成 Demo。

暂定七个差异化核心：

- DecisionSurfaceCell 作为 objective/evidence/numeric/owner/judgment/counterevidence/reviewer/WWC/artifact/monitoring 的统一工作单元；
- Evidence proves the claim，NumericProgram proves the number；
- Reviewer Correction Memory，使一次人工纠错影响后续 Case；
- Point-in-time Research Replay，解释当时依据、缺口、后续变化和批准版本；
- Cross-artifact Claim Graph，把 canonical claim/number 投影到 memo/PPT/Excel/dashboard；
- Provider-neutral model/search/data/parser integration；
- 高自由度但受 version/test/approval/rollout/rollback 治理的机构配置。

## 15. 市场切口与成功率

暂定最值得验证的切口是“可审核、可更新的上市公司覆盖生命周期”：

```text
Initiation / Deep Dive
 -> Earnings Update
 -> Follow-up
 -> Thesis Revision
 -> Memo + Model + Deck + Dashboard
 -> Monitoring
```

该切口同时验证 Search、Evidence、Numeric、Memory、Review、Cross-artifact 和 Monitoring，并具有重复发生、可测 ROI 和正式复核需求。

任务成功率分四级：

| 等级 | 定义 |
| --- | --- |
| L1 Artifact complete | 文件生成且可打开 |
| L2 Research valid | 核心 Cell、Evidence、Numeric 通过 |
| L3 Reviewer accepted | Senior/Compliance 批准 |
| L4 Longitudinally maintainable | 可追问、refresh、supersede、跨产物更新 |

市场竞争指标应聚焦 required Cell resolved/typed gap、material claim lineage、numeric replay、period/entity/unit hard fail、reviewer acceptance、review corrections、time-to-approved-output、quarterly refresh precision、stale leakage、cross-artifact mismatch、follow-up continuity 和 cost per accepted workpaper。

竞争不是谁先做出最多 Agent，而是谁先让机构敢把真实任务、内部数据、审核责任和持续历史放进系统，并稳定获得可批准、可维护结果。若 FIN 长期停留在架构规划而没有可运行闭环，当前窗口会快速关闭。

## 16. 新增待讨论：Human-AI Accountability / Attribution

需要讨论是否将用户 Prompt、Agent/tool action、Cell/Claim/Artifact 修改、Reviewer 意见、+1/+2/Compliance approval 和 release 全部纳入可审计 attribution chain；区分可见 AI-assisted 标记、artifact provenance、runtime observability、合规 audit ledger 和员工 usage analytics，明确 OA/SSO/SCIM/workflow integration、隐私、retention、legal hold 和责任边界。

## 17. Human-AI Accountability / Attribution 暂定设计

本节记录 2026-07-12 已对齐的十点讨论，仍是 non-canonical proposal。正式名称暂定为 `Human-AI Accountability and Attribution System`；“水印”只属于 Artifact 层，底层目标是证明谁以什么身份触发了什么 AI/Agent 行为、使用了哪些数据、修改了哪些 Cell/Claim/Artifact、由谁审核批准并发布。

### 17.1 Actor identity 与 authority snapshot

Actor 至少包括 HumanUser、HumanReviewer、HumanApprover、ComplianceOfficer、DelegatedApprover、Agent、Subagent、Tool、ServiceAccount 和 ExternalSystem。每个事件保存 actor_id/type、tenant/department/team、role snapshot、authority scope、delegation、SSO session、acting-on-behalf-of、agent/model/skill version 和 permission snapshot，避免组织角色变化后无法解释历史授权。

### 17.2 全链路动作记录

需要覆盖 PromptSubmitted、ResearchCaseCreated、DecisionSurfaceModified、AgentActivated、SkillSelected、SourcePolicyOverridden、ToolInvoked、SourceOpened、EvidenceCandidateCreated/Rejected、NumericProgramExecuted、GapRaised、RepairRequested、AgentOutputSubmitted、ArtifactEditProposed、CellJudgmentOverridden、EvidenceStatusChanged、NumericAssumptionChanged、Claim/CitationChanged、ReviewDecision、Approval 和 Release。

事件必须绑定 ResearchCase、TaskRun/WorkUnit/Attempt、Cell、Claim、Evidence、NumericProgram、Artifact、causation/correlation 和 before/after version/hash，而不是只保存一段聊天历史。

### 17.3 Cell 级责任图

DecisionSurfaceCell 可投影 created_by、evidence_requested/collected_by、numeric_program_run_by、judgment_proposed/modified_by、reviewed_by、approved_by、artifact_claim_refs 和 monitoring_owner。Workbench 应能展示 AI proposal、accepted/rejected evidence、human edits、review/approval 和受影响 memo/model/deck/dashboard。

### 17.4 不新建孤立日志系统

复用 TECH_06 immutable Event Envelope 作为执行事实，TECH_09 ReviewDecision/ReleaseRecord 作为审核发布语义，TECH_03 负责历史 Actor/Decision/supersession 索引，TECH_10 评估 attribution completeness/approval escape，Workbench 负责投影视图。新增对象候选为 ActorSnapshot、AccountabilityEvent、DecisionAttestation、ArtifactProvenanceManifest，并由事件投影 `HumanAIAccountabilityGraph`，避免 trace、audit、OA 和文档历史彼此断连。

### 17.5 三层 Artifact 标记

1. Visible disclosure：按机构/audience policy 展示 AI-generated draft、AI-assisted、human-reviewed、compliance-approved、released。
2. Embedded metadata：ResearchCase ID、artifact version、AI involvement mode、model/agent refs、reviewed/approved-by、release time 和 manifest URI/hash。
3. Cryptographic attestation：对 exact artifact hash 与 provenance manifest 做机构签名，证明审核后未被修改并支持 supersession verification。

可借鉴 C2PA Content Credentials 的 signed manifest、ingredient/edit history 和 human/organization identity，但金融研究还需扩展 Cell、Claim、Evidence、Numeric、Review 和 Approval 语义；不能把 C2PA 或文本 watermark 当作完整责任系统。

### 17.6 OA / enterprise integration

使用 OIDC/SAML 做登录，SCIM 同步用户/部门/角色，OA/HR API 提供 +1/+2 汇报关系与 delegated authority；OA workflow 与 ReviewRequest 双向绑定，审批结果回写 DecisionAttestation。Teams/Slack/企业微信/邮件只做通知或受控入口，正式批准必须绑定 exact artifact/claim hash、workflow id、审批节点和 ActorSnapshot。高风险产物可接电子签名、证书、时间戳、legal hold/archive。

### 17.7 Prompt/Response retention 与敏感数据

不默认全部明文永久保存。Audit metadata 和 prompt/response hash 可长期保存；encrypted payload ref、redacted prompt 和 raw payload 按 sensitivity/tenant/retention/legal-hold policy 分层；secret/credential 禁止进入日志。采集能力与采集政策分离，支持 purpose limitation、least privilege、DLP、eDiscovery、deletion approval 和 tenant override。

### 17.8 防止退化成员工监控

Research provenance、Compliance audit、Runtime observability 和 Usage analytics 四类视图逻辑隔离。Token、Prompt、Agent 调用、修改次数和 AI 使用比例不得直接作为员工绩效。个人级 usage 访问需要明确目的、权限、通知和二次审计；默认提供聚合采用/成本视图，避免隐性 surveillance、chilling effect 和不当 productivity scoring。

### 17.9 Accountability evidence 不自动裁定责任

系统证明谁触发、修改、访问、审核、批准和发布，以及当时数据、模型、规则、权限和版本；不自动裁定法律责任。责任仍取决于机构 policy、岗位、授权、监管、合同、司法辖区及故意/过失/系统缺陷。Agent 不是法律责任主体；高影响 Case 必须有 human accountable owner。目标是 accountability evidence，不是自动甩锅。

### 17.10 与五个核心差异化的连接

```text
DecisionSurface      -> 谁负责哪个 Cell
Evidence/Numeric     -> 谁取得、接受、拒绝、计算和修改
PIT Memory           -> 当时谁基于什么作出判断
Durable Review       -> 谁审核、批准、附加条件和撤回
Cross-artifact       -> 哪个批准传播到哪些正式产物
```

该能力可形成 Claim 责任链、Cell 审核历史、AI involvement、Reviewer Correction Memory、exact-version approval、OA integration 和 audit package。正式技术拆分前必须明确 TECH_06/09/03/10 owner、event/decision source of truth、privacy/retention 及产品 Admin/Workbench surface，不能另建平行审计栈。
