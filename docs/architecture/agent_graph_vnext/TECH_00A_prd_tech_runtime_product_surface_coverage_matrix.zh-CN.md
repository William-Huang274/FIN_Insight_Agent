# TECH_00A：PRD -> TECH -> Runtime -> Product Surface 覆盖矩阵

日期：2026-07-12

状态：架构覆盖审计。本文记录产品能力、稳定对象、TECH owner、既有 R-series 设计、代表性 runtime 资产、产品 surface 和当前成熟度之间的对应关系。`legacy_planned`、`fixture_proven` 或 `partial` 不等于 vNext runtime 已消费新合同。

> **2026-07-19 current implementation overlay**：第 2 节主矩阵和第 5 节 Release Consumption 保留 2026-07-17 架构/准入快照。FIN 0.1 现已形成 internal current-train vertical，但没有 release：Point 01 narrow contract/runtime proof complete；Point 02-06 current release path substantial internal implementation；Point 07 blocked decision；真实 DeepSeek、exact Human Senior Review、RG1/RG3/RG4 仍未完成。逐 TECH 与逐 Point 的当前实证见 `../repository/FIN_0_1_PRD_TECH_POINT_IMPLEMENTATION_BASELINE_20260719.zh-CN.md`。

## 1. 状态口径

| 状态 | 含义 |
| --- | --- |
| `covered_contract` | 已有明确 vNext TECH owner 和合同 |
| `legacy_planned` | 旧 R-series 有设计，但尚未完成 vNext 继承或 supersession |
| `runtime_partial` | 有代表性代码、fixture 或旧 runtime slice，但未完成新合同消费 |
| `product_partial` | 有 API/UI/projection 局部能力，但没有完整产品闭环 |
| `owner_gap` | PRD 有要求，但 stable object graph 没有明确 owner |
| `new_contract_required` | 需要新增稳定对象、状态机或独立 TECH |

## 2. 全量覆盖矩阵

| PRD 能力 / surface | 核心产品对象 | vNext TECH owner | 既有 R-series / 方案 | 代表性 runtime / fixture 资产 | 产品 surface | 当前判断 | 主要缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard / Home | ProjectSpace、TaskSummary、ReviewQueue、WatchlistProjection | TECH_09；API/UI 由 R59 | R55、R59 | `r53_r60_deliverable_studio_dashboard.py`、Workbench frontend | dashboard、任务和审批入口 | `product_partial` | 真实多租户数据、长期状态、watchlist backend 未闭环 |
| Institutional ResearchCase Lifecycle | InstitutionalResearchCase、CaseControlState、CaseVersion、FollowUpRequest、RefreshRequest、SupersessionGraph | TECH_01 business truth；TECH_06 execution persistence；TECH_03/09/11 consume | R52/R57/R59 局部 | legacy task/workpaper/memory/watchlist assets | case timeline、follow-up、refresh、history | `covered_contract / not_runtime` | aggregate identity、纵向 current heads、selective refresh 和 archive 尚未 runtime 化 |
| Research Task Center | ResearchTask、TaskModeDecision、TaskRun、WorkUnit | TECH_01 research semantics；TECH_06 execution；TECH_08 handoff | R52、R59 | `multi_agent_runtime.py`、`langgraph_orchestrator.py` | task create/progress/resume | `covered_contract / runtime_partial` | TaskModeRouter 合同已补；需绑定 ResearchCase，mode escalation 和 mode-specific gate 尚未 runtime 化 |
| Agentic Research | DecisionSurfaceContract、Cell、Pack、RepairTicket | TECH_01、05-08 | P33-P36、R52 | Research Lead、specialist、aggregate、writer fixtures | deep research task | `covered_contract / runtime_partial` | vNext DecisionSurface 仍未完整 runtime 消费；P36 blockers 未关闭 |
| Agentic Search / Evidence | EvidenceRequest、Candidate、PromotionDecision、EvidenceResponse | TECH_02-04 | R58 | retrieval、evidence operator、fact selection、MCP tool registry | Evidence Workbench drilldown | `covered_contract / runtime_partial` | accepted-evidence conversion、reranker precision、table/numeric promotion 仍需审计 |
| Input / Data Room | DataRoom、UploadSession、IngestionJob、DocumentACL、ExtractionReview | TECH_03、04、06、09 | R58、R59 | uploaded-artifact parser contract、P14 ingestion fixture | upload、outline、table/cell、extraction log | `covered_contract / legacy_planned / product_partial` | intake/security/quarantine/reprocess/delete 合同已补；R58/R59 adapter 与 E2E 未完成 |
| Evidence Workbench | EvidencePack、GapRecord、PromotionDecision、NumericTrace | TECH_02-04、09 | R58、R59 | Workbench backend、claim/evidence ledger、P33 review fixture | candidate/accepted/rejected/gap review | `runtime_partial / product_partial` | Gap identity 分散；新 cell-level evidence surface 未完全实现 |
| Workpaper Builder | WorkpaperEvent、WorkpaperPack、Section、ReviewComment、Approval | TECH_01、05、06、09 | R52、R55、R59 | legacy workpaper projection、P33 Workbench fixture | editable/reviewable workpaper | `covered_contract / legacy_planned` | Workpaper 与 DecisionSurfacePack 关系已冻结；R52 migration/schema/runtime/UI 尚未完成 |
| Cross-cell LeadReview | DecisionSurfaceAssembly、CrossCellConflict、LeadReviewDecision、WriterAdmission | TECH_01、05、09 | R52 LeadReviewBarrier | aggregate/judgment planner、MemoLogicPlan | pre-writer review | `covered_contract / not_runtime` | pack-level story/coverage/conflict/admission 合同已补，尚无 vNext runtime consumer |
| Unified Gap lifecycle | GapRecord、RepairTicket、RepairAttempt、GapResolution | TECH_01、02、03、06、09 | R52 GapLedger | `claim_evidence_ledger.py`、typed gaps | gap board、repair queue | `covered_contract / runtime_partial` | Gap/repair 身份已分离；dedupe/reopen/supersession 仍未统一实现 |
| Graph Workspace | GraphSnapshot、GraphCandidate、CellDependencyEdge、ReviewAction | TECH_03、05、09 | R57、R59 | `relationship_graph.py`、ProductIntelligence runtime | graph explore/filter/drilldown | `runtime_partial / product_partial` | 关系召回强于价值捕获；交互编辑/temporal diff 仍不完整 |
| Numeric / Fact Table | NumericFact、NumericProgramTrace、MetricDefinition | TECH_04、09 | R58 | exact-value ledger、derived metric layer | fact table、formula drilldown | `covered_contract / runtime_partial` | table-aware extraction、unit/scale、row selector 尚未达到全 source gate 水平 |
| Hybrid Research Authoring / Protected Narrative | NumericFactView、ProtectedNarrativeDraft、CorrectionObjective、CorrectionClosureReceipt | TECH_04/05/06/08/09/10；跨域合同 38 | 历史 alias/atom/renderer 与 FIN 0.1.3 S2-06 R2 failure | unified corrected-node contract、numeric renderer、closure validator | Workpaper、memo、report、review diff | `runtime_injected / deterministic_proven / natural_model_fail` | S2-06B/C 已消费并独立证明；D natural canary 证明 DeepSeek evidence-role/closure 不可靠，paid artifact、anti-template paired quality 与 human acceptance 仍缺 |
| Valuation / Scenario | ForecastAssumptionSet、ValuationModelRun、ScenarioModelRun、SensitivityTable | TECH_04、05、09 | R53 不是公司估值引擎 | 零散 valuation-enriched pack / derived metrics | valuation/price-in workpaper | `covered_contract / not_runtime` | owner/identity 已补；确定性模型、peer/scenario lineage 尚未实现 |
| Market / Derivatives | SecurityMasterPIT、DerivativeObservationPIT、DerivedSignal | TECH_03-05 | R53、S8/S9 | capital feedback、secondary market context | capital feedback / risk surface | `covered_contract / runtime_partial` | 免费源深度和频率有限；复杂期权/CDS 只能 bounded/commercial |
| Research-to-Quant | FactorHypothesis、Feature/Label/Universe、Backtest、FactorCard | TECH_04、05、09、10；R53 主 owner | R53/S9 | `r53_r60_research_to_quant_lab.py`、P33 handoff fixture | Quant Lab | `fixture_proven / product_partial` | 只能 assisted/internal；不能自动升级为交易建议 |
| Deliverable Studio | FrozenDecisionSurface、PresentationModel、SurfaceClaim、ArtifactVersion | TECH_09 | R55、R59 | renderer/dashboard projection、artifact review fixture | memo/PPT/Word/Excel/PDF/dashboard | `covered_contract / product_partial` | canonical model、跨格式 parity、exact release hash 未统一 runtime 化 |
| Human Review / Approval | ReviewAction、DecisionAttestation、Waiver、ReleaseTransaction | TECH_09 business truth；TECH_06 persistence；TECH_10 eval | R52、R59/R60 | reviewer acceptance fixtures | comments、approve/reject/supersede | `runtime_partial / product_partial` | exact target/hash attestation、assignment/SLA/delegation/notification 与真实多人流程未闭环 |
| Human-AI Accountability / OA Identity | ActorSnapshot、AccountabilityEvent、HumanAIAccountabilityGraph、ArtifactProvenanceManifest | TECH_06 event/identity；TECH_09 attestation/manifest；TECH_03 index；TECH_10 eval | R59/R60 局部 audit | permission/review/run event fixtures | responsibility graph、audit package、OA approval link | `covered_contract / not_runtime` | OIDC/SAML/SCIM、delegated authority、OA callback、retention/legal hold、visible disclosure 未实现 |
| Watchlist / Monitoring | Watchlist、CoverageSubscription、MonitoringRule、AlertDecision、Digest | TECH_11；依赖 TECH_01/03/05/06/09/10 | R55 仅 projection、R57 memory、R60 eval monitor | 零散 MonitoringTrigger、dashboard projection | alerts、digest、review queue | `covered_contract / not_runtime` | TECH_11 已补；长期状态、增量观测、去重、抑制、触发解释和通知尚未实现 |
| External / Social signals | ExternalSignal、SocialStatement、DiscourseSample、ConflictRecord | TECH_02、03、05、09、10 | 无独立 R-series | 新闻/GDELT 探针和合同 | statement/conflict/discourse cards | `covered_contract / not_runtime` | 平台 adapter、采样框架、删除/编辑追踪、代表性评测未实现 |
| Institutional Memory / PIT Reconstruction | MemoryWriteCandidate、InstitutionalMemoryRef、MemoryInvalidationEvent、PITReconstruction | TECH_03 address/lifecycle；TECH_02/04/05/09 business refs | R57、P33/P36 | context/method/memory fixtures | case history、prior judgment、review correction、repair history | `covered_contract / runtime_partial` | TECH_03 registry、业务 owner refs、PIT replay、permission-aware reuse 尚未统一 |
| Context / Skills / Compaction | ContextInjectionPlan、ContextSelectionDecision、SkillVersion | TECH_07；运行依赖 TECH_06/08；memory refs 来自 TECH_03 | R57 | `context_engine.py`、method runtime fixtures | follow-up/resume context、skill disclosure | `runtime_partial` | 并非所有 live nodes 消费 SQL-final plan；需移除长期 memory truth 重叠 |
| Agent / Skill / Graph / Workflow Configuration | AgentDefinitionVersion、PromptBundleVersion、SkillVersion、GraphOntologyVersion、WorkflowPolicyVersion | TECH_03 ontology/verified graph；TECH_08 Agent/Skill/Workflow semantics；TECH_06 registry/permission/rollout；TECH_10 eval | R56/R57/R59 局部 | agent/skill/method/ontology registries | admin configuration studio | `covered_contract / runtime_partial` | draft/sandbox/approve/staged rollout/rollback 和 hard-invariant lock 尚未实现 |
| Provider-neutral Capability Frontier | ProviderPolicyVersion、ModelCapabilityProfile、Search/Data/ParserCapability、SelectionDecision、AutonomyGrant、ConstraintRetirementDecision | TECH_02、06、08、10；PRD 7.10、跨域合同 38 | provider adapters / R56 局部 | `llm_gateway.py`、Tool Registry、source probes、S2-06 canary | admin provider policy、shadow comparison、autonomy tier | `covered_contract / runtime_partial / adaptive policy documented` | 稳定金融内核与 provider workaround 已定义分离，但 capability profile compiler、family eval、autonomy routing、shadow retirement 与 rollback 尚未 Runtime 化 |
| Agent Information Economy | InformationEconomyLedger、UsageObservation、YieldMetric | TECH_06-08、10 | P30 AIE | `agent_information_economy.py`、Workbench projection | cost/yield/admin/eval | `covered_contract / runtime_partial` | PRD 指标 owner 已补；统一 metric registry、因果归因和 release gate 尚未实现 |
| Admin / Governance | Tenant、Role、Policy、Entitlement、AuditExport | TECH_06、07、09、10；R59 实现 | R59、R60 | RBAC/sandbox/ops fixtures | admin/ops/eval/cost | `runtime_partial / product_partial` | SSO/OIDC/SCIM、KMS/DLP、data residency、license entitlement 仍未拆细 |
| Collaboration / Notifications | CaseRoleAssignment、ResearchAssignment、ReviewAssignment、CommentThread、Mention、ReviewSLA、DeliveryReceipt | TECH_01 research assignment；TECH_09 review/collaboration semantics；TECH_06 durable SLA/notification；R59 product API | R52、R59 | append-only workpaper/review events | team assignment、review、alerts、integrations | `covered_contract / legacy_planned` | assignment schema、邮件/Slack/Teams/webhook、升级和外部分享仍需 implementation contract |
| Longitudinal Refresh / Cross-artifact Reapproval | RefreshRequest、AffectedCellSet、ThesisDelta、ArtifactStalenessAssessment、ReapprovalRequest | TECH_01/03/05/09/11；TECH_10 eval | R55/R57/R59 局部 | WWC/monitoring/artifact fixtures | quarterly update、stale panel、reapproval queue | `covered_contract / not_runtime` | affected-cell selection、selective recompute、stale propagation 和 R4 fixture 未闭环 |
| Sector / Method packs | CellArchetype、SectorOperatorPack、MethodSkillVersion | TECH_01、03、05、07、10 | P32/P33 | method registry、skill files、AI/Semis fixtures | template / sector setup | `fixture_proven / runtime_partial` | 缺 pack release、compatibility、calibration、deprecation 和非 AI/Semis 深度证明 |
| Evaluation / Improvement | EvalSubject、QualityCard、FailureAttribution、ReleaseGate | TECH_10 | R60 | eval store/scripts、gold/fixture assets | eval dashboard / incident / release | `covered_contract / runtime_partial` | 新 Quality Ledger 和 paired release contract 尚未统一实现 |

## 2.1 Product Outcome / Eval Coverage（2026-07-12）

现有主矩阵描述 capability ownership 和成熟度。所有 release-sensitive 行还必须由 TECH_10 绑定以下结果级别，避免“有 owner”被误写成“产品可用”：

| Product outcome | 必须覆盖的矩阵行 | 最低 eval / gate |
| --- | --- | --- |
| `R1_artifact_complete` | Deliverable Studio、Dashboard、Data Room | schema/render/visual/openability |
| `R2_research_valid` | Agentic Research/Search、Evidence、Numeric、Judgment、LeadReview | required-cell closure、claim lineage、numeric replay、hard-fail escape |
| `R3_reviewer_accepted` | Workpaper、Human Review、Accountability、Release | exact-version attestation、review burden、approval escape、audit completeness |
| `R4_longitudinally_maintainable` | ResearchCase、Memory、Monitoring、Cross-artifact Refresh | follow-up continuity、PIT reconstruction、selective refresh、correction reuse、stale leakage |

每个 capability row 在进入实现前必须登记 `tech10_eval_subject / metric / gate / fixture`。缺失 eval owner 的 row 状态不得高于 `covered_contract`。

## 3. 覆盖结论

核心研究链已经有明确 TECH owner。2026-07-12 进一步为 InstitutionalResearchCase、Institutional Memory、Human-AI Accountability、configuration governance、provider-neutral capability frontier 和 longitudinal refresh/reapproval 固定单一 business writer 与执行/索引消费者；这些修订只把 `owner_gap` 推进到 `covered_contract`，并未自动推进到 runtime/product maturity 或 R1-R4 outcome。

R52/R58/R59/R60 不是废弃资料。它们分别保留 Workpaper/协作、数据与检索实现、B 端 API/UI、eval/ops 的工程设计，但必须通过本矩阵映射到 vNext stable objects。未映射的 legacy object 不得直接成为新 runtime 的第二套 source of truth。

## 4. 实施级拆分要求

每一行从 `contract_draft` 进入实现前，都必须补齐：machine-readable schema、API/event、SQL/ObjectStore/index ownership、producer/consumer、permission、retry/idempotency、UI projection、fixture/eval、migration/supersession 和 maturity evidence。只出现类名、prompt 字段或 UI mock 不构成闭环。

Point 01 M0-M2 已于 2026-07-12 冻结第一组 implementation prerequisites：SCHEMA_01、DB_01、API_01、MIGRATION_01 及 registry/mapping v0.2。该状态只表示 `implementation_contract_frozen`，不把任何主矩阵行提升为 `runtime_partial` 或 R1-R4 pass。

## 5. REL-PROD-001 Release Consumption（2026-07-17）

`FIN 0.1 Internal Alpha` 消费本矩阵的方式如下。P36 六个产业链 family 是 Anchor calibration coverage，不是产品 feature scope。

| Release feature | 主矩阵行 | TECH owners | Point consumer | 当前 release 状态 |
| --- | --- | --- | --- | --- |
| `P001-F01-F04` Product entry/control | Dashboard、ResearchCase、Task Center、Agentic Research、Context/Skills | TECH_01、06、07、08、09、10 | Point 02 | required / not implemented |
| `P001-F05-F07` Evidence/numeric | Agentic Search、Evidence Workbench、Numeric/Fact、Graph/Market bounded inputs | TECH_02、03、04、06、09 | Point 03-04 | required / runtime assets partial |
| `P001-F08-F10` Workpaper/repair/Lead | Workpaper、Cross-cell LeadReview、Unified Gap、Sector/Method packs | TECH_01、02、05、06、07、08、09 | Point 05 | required / not vNext closed |
| `P001-F11-F14` Deliver/review/trace/follow-up | Deliverable、Human Review、Accountability、Memory/Context bounded reuse | TECH_01、03、06、07、09、10 | Point 06 | required / product partial |
| `P001-F15` Quality/release | Evaluation/Improvement、AIE、release outcome | TECH_06、09、10 | Point 07 | required / contract only |

FIN 0.1 明确 deferred：Data Room、Watchlist/R4、Research-to-Quant、全行业 pack、完整 valuation/scenario、全格式一致性、企业身份/多租户和商业/实时衍生数据。Deferred 行的接口继续保留，但不能抢占当前四周产品列车。

完整 feature/surface/acceptance 见 `docs/product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`；机器合同见 `configs/releases/fin_ia_0_1_release_contract_v1_1.json`。

## 6. FIN 0.1 当前实现覆盖（2026-07-19）

| Release feature | 当前实现覆盖 | 当前边界 |
| --- | --- | --- |
| `P001-F01-F04` Product entry/control | Case/Task Center/10-cell DecisionSurface/fixture WorkUnit/Activity 已进入浏览器 current train | operational resume/retry 与 formal Point 02 owner closeout未完成 |
| `P001-F05-F07` Evidence/numeric | 31 local candidates、Evidence Workbench、3 exact facts、2 derived margins 和一次 bounded repair | live SourceHunter/provider、formal promotion/parser calibration 未完成 |
| `P001-F08-F10` Workpaper/repair/Lead | 10 deterministic judgments/Workpaper、counterevidence/WWC、fixture LeadReview/WriterAdmission | DeepSeek Domain/Lead 和 exact Human LeadReview 未运行 |
| `P001-F11-F14` Deliver/review/trace/follow-up | deterministic no-source Writer、HTML/Markdown、Report/Review/Trace surfaces 已实现 | report 不是最终 Lead synthesis；human review=0；Agent same-Case follow-up 未闭环 |
| `P001-F15` Quality/release | shadow Senior R2、RG2 internal fixture、RG5 rollback 和 P07.5 blocked decision 已记录 | RG1/RG3/RG4 blocked，FIN 0.1 未 release |

当前 machine release source 为 `configs/releases/fin_ia_0_1_release_contract_v1_2.json`，不再以本节末尾保留的 v1.1 历史引用判断 authority。

## 7. FIN 0.1.3 current implementation overlay（2026-08-08）

本节 supersede 第 6 节的“当前实现”描述，但不改写旧时点证据。它只更新 FIN 0.1.3 当前成熟度，不改变 `REL-PROD-001` feature scope。

| Release feature | FIN 0.1.3 当前实证 | 当前判断 | 下一硬门 |
| --- | --- | --- | --- |
| `P001-F01-F04` Product entry/control | S0 inheritance/exact-once/truth oracle 已关闭；S3 有 12–13 Cell engineering plan；RC-P36-156 仍暴露共享 blocker-state/run-scope fail-open | `runtime/control partial` | typed blocker state＋RunScopeRegistry；current Case vertical 与动态 Lead |
| `P001-F05-F07` Evidence/numeric | S1-01–05 truth/numeric/graph/governed pack、S1-06 MCP、S1-07 official-source runtime 各自通过；S1-08 DELL live 只有 1 unique source、target-in-pool=0，v3 仅 zero-call engineering pass | `numeric/official-source scoped pass; Agentic Search failed` | v3 clean proof、DELL live decision、provider/scope disposition、三案 candidate ceiling，之后才准入 ranking |
| `P001-F08-F10` Workpaper/repair/Lead | S2 capability experiments与 correction guard 已完成但 DeepSeek natural closure 失败；S3-01–05 minimum anchor 有结构，无产品级 thesis/counterevidence/内容验收 | `engineering anchor / product not passed` | DS-A1/A2/A3、S3-06/07 dynamic research、S3-08/09 八维内容验收 |
| `P001-F11-F14` Deliver/review/trace/follow-up | 继承 0.1.2 的只读 Workbench/Report/Trace surface；尚未消费 FIN 0.1.3 current evidence/research candidate | `historical product projection only` | S4-06 current Case dogfood、exact review、review burden 与 bounded follow-up |
| `P001-F15` Quality/release | 失败 attempt、capture、paired rubric 与 rollback 合同存在；0.1.3 RG1–RG5 未执行 | `release blocked` | S1/S3/S4 通过后执行 S5；RC-P36-156 shared governance 必须关闭 |

### 7.1 Current issue ownership

- provider/locator/candidate ceiling、publication date、relationship direction、slot fairness：TECH_02/03，S1-08；
- typed blocker state/run-scope registry：TECH_06/10，共享 S0/S5；
- model family capability/autonomy：TECH_08/10，S2；
- dynamic DecisionSurface、targeted repair、content quality：TECH_01/05/10，S3；
- Workbench usefulness/review burden：TECH_09，S4；
- release/rollback/portability：TECH_06/09/10，S5。

因此，`runtime_partial` 不能再被压缩为一个总状态。FIN 0.1.3 必须分别报告 source/search、numeric truth、model adherence、research outcome、product usability 和 release readiness；其中任一通过都不能替代其他轴。
