# TECH_10：Quality Evaluation / Failure Attribution / Runtime Release / Governed Improvement

日期：2026-07-09
最近修改：2026-07-17

状态：技术合同草案。本文是 FIN agentic research 的最新质量合同 source of truth，统一 TECH_01-11 的评测语义；现有 R60 继续作为实现、可观测、incident、fallback 和 release-readiness 计划。本文不表示新合同已被 runtime 消费。

## 0. 正式定义与 Non-Goals

TECH_10 是 FIN 的 Quality and Learning Control Plane。它把冻结的研究任务、tool/model trajectory、evidence promotion、DecisionSurfaceCell/Pack、rendered artifact、human review 和线上反馈建模为版本化 `EvalSubject`，通过受治理的数据集、Gold contract、OracleRoutingPolicy、EvalMetricDefinition、EvalGatePolicy 和可复现 EvalRun 产生质量判断；再通过 FailureAttributionGraph、candidate-vs-baseline release gate 和 ImprovementProposal 控制 runtime/config 如何被验证和改进。

这里的 Learning 只指 failure/regression/gold、skill/rule/prompt/harness proposal 和 reviewer feedback 的受治理沉淀，不包括：

- 自动训练或更新模型权重；
- 在线自适应修改 prompt、skill、memory policy 或 tool policy；
- 自动放宽 permission/source/disclosure/release gate；
- 自动晋升 evidence、Gold 或 reviewer decision；
- 自动合并 runtime patch 或运行 paid/full-chain。

TECH_10 决定某一套 code/model/prompt/tool registry/runtime contract 是否有足够质量证据进入目标 release maturity；TECH_09 决定某一份具体 artifact 是否可 internal/client-safe/published。两种 release 不能混用。

## 1. Quality Ledger 与 Source-of-Truth

质量主链路：

```text
EvalProgram
 -> EvalDatasetVersion
 -> EvalCase
 -> EvalRunManifest / EvalRun
 -> EvalSubject
 -> EvaluatorRun
 -> EvalMetricResult / QualityCard
 -> FailureAttributionGraph
 -> RuntimeReleaseGateDecision
 -> RegressionCase / ImprovementProposal
```

稳定对象：

| 对象 | 作用 |
| --- | --- |
| `EvalProgram` | 定义评测目的、subject/mode/dataset/evaluator/gate/repetition 范围 |
| `EvalDatasetVersion` | 冻结 case membership、split、snapshot、gold/rubric 和治理状态 |
| `EvalCase` | 一个结构化研究/执行/交付合同，不等于标准文章 |
| `EvalRunManifest` | 冻结 candidate/baseline、dataset、judge、source、runtime 和 repetition 环境 |
| `EvalRun` | 一次不可变评测执行及状态 |
| `EvalSubject` | 被评对象的统一 versioned envelope |
| `EvaluatorDefinition` | evaluator 输入、oracle、metric、权限、版本和适用边界 |
| `EvaluatorRun` | 一次 deterministic/human/LLM evaluator 执行 |
| `EvalMetricDefinition` | 评测公式、单位、方向、适用对象和聚合语义；不与 TECH_04 财务 `MetricDefinition` 混用 |
| `EvalGatePolicy / EvalThresholdProfile` | maturity/task/slice 对应阈值、hard/warn、waiver 和 missing policy |
| `EvalMetricResult` | 某 EvalRun/Subject/Evaluator/Metric 的不可变结果 |
| `QualityCard` | 分层 hard gates、soft quality、slice、cost/latency 和不确定性 |
| `FailureAttributionGraph` | symptom、candidate cause、intervention、replay 和 root-cause assessment |
| `RuntimeReleaseGateDecision` | candidate runtime/config 的 passed/blocked/rollback 等决策 |
| `ImprovementProposal` | 引用 failure/fixture/sandbox 的受治理变更候选 |

TECH_06 RunEvent Ledger 是执行事实源；TECH_10 Quality Ledger 是评测结果、归因和 runtime release decision 的事实源；R60 落物理 store/dashboard/incident pipeline。Quality Ledger 只引用 run events/traces/artifacts，不复制或重写执行历史。

所有记录 append-only。`EvalMetricResult` 在同一 EvalRun 内不可普通覆盖：dataset/judge/rubric/candidate/baseline/evaluator 变化必须创建新 EvalRun。发现 evaluator bug 或输入损坏时，旧 result/run 标记 `invalidated`，新 EvalRun 通过 `replaces_invalidated_run_ref` 关联；不能用 `v2` 静默改写原结论。

## 2. EvalSubject Taxonomy

统一的是 envelope，不是 rubric。`EvalSubject` 至少包含 subject id/type、task/run/work-unit/attempt refs、subject artifact/version、input versions、runtime config、permission snapshot、as-of、producer 和 frozen digest。

第一版 subject types：

| Subject | 主要问题 |
| --- | --- |
| `tool_invocation` | permission、args/schema、failure classification、observation usability |
| `evidence_candidate` | route relevance、metadata、authority lead、duplicate/noise |
| `evidence_promotion` | entity/period/unit/source/claim scope、promotion hard boundary |
| `work_unit` | assignment、input version、state transition、result envelope |
| `trajectory` | invariants、tool choice、repair、loop、stop 和有效增量 |
| `decision_surface_cell` | evidence/counterevidence、judgment、gap、confidence、What-Would-Change |
| `decision_surface_pack` | mandatory cell coverage、thesis path、cross-cell conflict/version |
| `context_plan` | selection、permission、compaction、reconstruction、usage |
| `rendered_artifact` | SurfaceClaim、numeric/citation、semantic/visual/disclosure consistency |
| `artifact_release` | TECH_09 exact-version/hash/approval/client-safe integrity |
| `user_workflow` | task completion、follow-up、reviewability、time saved、edit distance |
| `operational_run` | reliability、latency、cost、recovery、incident、fallback |

Evaluator 必须声明 accepted subject types。禁止把 tool、cell、artifact 和 workflow 分数平均成无语义的单一 overall score。

## 3. Evaluation Mode 与 Proof Boundary

| Mode | 能证明 | 不能证明 |
| --- | --- | --- |
| `deterministic_fixture` | schema、公式、状态、权限、路由、hard rules | 开放式模型判断质量 |
| `frozen_observation_replay` | 相同 observation 下的 node/prompt/policy 变化 | live web/API/tool reliability |
| `snapshot_retrieval_eval` | 冻结 corpus/index 的 retrieval/rerank/metadata | 当前互联网可得性 |
| `live_tool_eval` | 当前 network/tool/parser/permission integration | 严格复现和长期稳定性 |
| `model_node_eval` | 单 node/agent 输出和 rubric | 完整协作和 durable runtime |
| `manual_dogfood` | 发现复杂真实 workflow/quality 问题 | runtime automation 和统计结论 |
| `shadow_online_eval` | 线上分布、候选版本和 drift signal | 无可靠 label 时的绝对正确性 |
| `runtime_release_gate_eval` | candidate 是否满足目标 runtime maturity | 单独覆盖所有未来线上风险 |

每个 EvalRun 必须声明 `replayability_level`：

- `exact_replayable`：pure deterministic input/output；
- `frozen_observation_replayable`：复用历史 model/tool/web observations；
- `snapshot_replayable`：依赖 frozen corpus/index/data snapshot；
- `best_effort_live_reproducible`：外部系统可能变化，只能复现 manifest 和 attempt；
- `non_replayable_manual`：人工 dogfood/interaction，保存 artifact/notes，不声称机器复现。

P36 manual run、supervisor supplement、frozen fixture 和 live runtime 必须分别标识，不能互相冒充 capability evidence。

## 4. EvalDataset / Case / Gold Governance

`EvalDatasetVersion` 冻结：case list/split/weight、sector/company/language/task/source/doc/gap/artifact slices、source/data/index snapshot、as-of/available-time、permission/tool environment、gold/rubric versions、owner、created/expiry 和 contamination state。

Dataset states：

```text
development
 -> active_regression / adversarial / hidden_holdout
 -> stale / contaminated / retired

online_candidate
 -> reviewed_regression_candidate / gold_candidate
 -> active_regression / gold / rejected
```

`hidden_holdout` 必须由 evaluator-only storage/permission 真实隔离，不得放入 runtime、coding/self-improvement agent 可读 context。被针对性开发、人工解封或泄漏后产生 `DatasetContaminationEvent`，转 regression/retired 并建立新 holdout；不能只改字段后继续声称 unseen。

金融研究 Gold 是结构化合同，不是唯一 memo。`EvalCase` 至少声明：

- task/user/as-of/scope、required DecisionSurfaceCells；
- frozen source/data snapshots 和 permission boundary；
- accepted evidence/claim boundaries 与 rejected substitutions；
- expected numeric values/traces where deterministic；
- acceptable judgment range、required counterevidence/gaps/What-Would-Change；
- forbidden claims/actions/transitions；
- expected repair/stop/handoff behavior；
- artifact/review/release requirements；
- oracle/rubric refs、reviewer record、expiry/supersession。

Gold prose 只能作 presentation exemplar；不得用文本相似度决定研究正确性。Case as-of 之后公开的数据不得进入历史评测。

## 5. OracleRoutingPolicy 与 Evaluator Governance

Oracle 不是串行 fallback，而是按 subject + metric dimension + severity 路由并可并行组合：

| Oracle | 适用 |
| --- | --- |
| deterministic/schema/state | permission、version、formula、citation、writer tool violation、transition |
| provenance/numeric | source/row/unit/period/formula/replay |
| reviewed domain rubric | mechanism、judgment boundary、counterevidence、cell quality |
| human pairwise/absolute | candidate-vs-baseline、client/senior-ready、ambiguous high-impact |
| audited LLM-as-judge | 规模化 semantic/presentation 初筛与建议 |
| abstain/human-required | 无可靠 oracle、冲突或低置信高影响 |

`OracleRoutingPolicy` 记录 dimension、eligible/required oracle、precedence、conflict policy、abstain policy、confidence threshold 和 human escalation。Deterministic hard fail 不可被 human/LLM 平均分覆盖；但 deterministic pass 不替代 domain/human quality oracle。

每个 LLM Judge 调用记录 judge model/snapshot、prompt/rubric/input-mapping versions、candidate ordering、identity masking、output schema、reasoning summary、confidence、latency/cost 和 permission。Judge 自身必须有 calibration dataset，评估：human agreement、false accept/reject、repeat stability、order/model/self-preference bias、sector/language/task slices 和 abstention calibration。

### 6.4 Same-Prompt Research Repeatability

P38 WorkBuddy 多行业审计发现，同一网络安全反证 prompt 的两个完成版本虽然都保留 hypothesis tree / counterevidence / falsifier 结构，但 source-domain Jaccard 仅约 4.4%，引用数量、表格数量和 quantitative framing 明显不同。因此 repeatability 不能只比较最终主题或语言相似度。

同 prompt / 同 model-policy / 同 data-cut 的重复运行至少比较：

- DecisionSurfaceCell coverage、cell status 和 owner；
- source family / authority / issuer diversity；
- accepted material claims 与 counterclaims；
- numeric values、units、periods、derived traces；
- gap classification、repair path 和 stop reason；
- artifact section/chart/table presence；
- conclusion direction、confidence 和 What-Would-Change；
- model/tool/context cost 与 useful claim yield。

外部 live source 会变化时，EvalRun 必须冻结 source snapshot 或将差异分解为 `source_drift / tool_nondeterminism / model_nondeterminism / renderer_nondeterminism`，禁止把所有差异都归因于模型随机性。

Blinding 是 best effort；style、citation 或 artifact metadata 可能泄漏 candidate identity时必须记录 `blinding_limitation`。Judge 不得晋升 evidence、修改 Gold、override hard fail 或单独批准 runtime/artifact release。Judge/rubric/gold 修改属于 `evaluation_contract_change`，不是 runtime improvement。

## 6. EvalMetricDefinitionRegistry / EvalGatePolicy / QualityCard

`EvalMetricDefinition` 只拥有：eval metric id/version、subject types、formula、unit、direction、applicability、aggregation、missing/zero-denominator policy、minimum sample support、confidence interval policy、required slices、anti-gaming note、known limitations 和 owner。它与 TECH_04 用于金融衍生指标计算的 `MetricDefinition` 是不同对象。

阈值不写入 eval metric definition。`EvalGatePolicy / EvalThresholdProfile` 按 target maturity、task family、risk/severity、subject/slice 声明 threshold、hard/warn、non-regression margin、repetition requirement、waiver、expiry 和 human approval。相同 eval metric 可被 L0/L2/L3/L4 使用不同阈值。

QualityCard 分层：

```text
G0 Governance / Safety
permission, privacy, source boundary, writer no-source, disclosure

G1 Contract / Version Integrity
schema, state, handoff, context, immutable versions

G2 Evidence / Numeric / Provenance Integrity
promotion, authority, metadata, numeric replay, citation lineage

G3 Research Quality
cell coverage, mechanism, judgment, counterevidence, gap, What-Would-Change

G4 Delivery Quality
SurfaceClaim, cross-artifact semantic/numeric/visual/client-safe integrity

G5 Workflow / Product Value
task completion, follow-up answerability, review time, edit distance, time saved

G6 Operational Quality
success, p50/p95/p99, queue/tool/model latency, cost, recovery, incident, fallback
```

G0-G2 hard failure 不能被平均；G3-G6 也不能压成一个 overall score 掩盖 worst slice。AIE/cost 指标必须说明质量产出分母，例如 accepted evidence、adjudicated cell、review-ready workpaper、approved deliverable 和 successful targeted repair。

## 7. EvalRunManifest 与可复现执行

`EvalRunManifest` 至少冻结：

- eval program/dataset/case selection 和 execution mode/replayability；
- candidate/baseline code commit、model/profile、prompt/skill/config、tool/permission/source-policy versions；
- source/data/index/artifact snapshot refs；
- evaluator/judge/rubric/oracle/gate/metric versions；
- repetition/seed/scheduling/cache/budget policy；
- runtime environment、provider observed model/version、started time；
- output/ledger/artifact refs 和 manifest digest。

Random seed 只在 provider/tool实际支持时有效；记录 seed 不代表确定性。Live Eval 必须记录 retrieved time、external response/version/hash、rate limit 和 failure，不能声称 exact replay。

长程 model/tool/replay/shadow eval 通过 TECH_06 durable WorkUnit 执行。Static/schema/unit/deterministic CI evaluator 可在 CI/Test Runner 运行，只要以 signed/hashed result envelope 回写 Quality Ledger；不强制包装为研究 WorkUnit。

## 8. Invariant-Based Trajectory Evaluation

Trajectory Eval 不比较完整 gold step sequence。每个 `TrajectoryContract` 声明：

- required checkpoints 和 mandatory invariants；
- allowed path variants、tool/source routes 和 fallback；
- forbidden actions/transitions/substitutions；
- input/version/context/permission requirements；
- repair/clarification/dependency owner；
- budget/loop/stop/bounded-gap conditions；
- expected output artifacts 和有效增量定义。

评测内容：是否覆盖 mandatory cells、选择合理工具、观察并分类失败、使用正确 input version、路由 repair、避免越权/重复/无价值循环、在 stop 条件关闭，并把成本转成 accepted evidence/judgment/reviewer value。

多条 trajectory 都可通过。`ActionContributionRecord` 可标记 `necessary / useful / redundant / harmful / unresolved`，但不能只因未走 exemplar path 判错。效率 eval 必须同时看 source authority、成功概率和质量增量，不能简单奖励更少 tool calls。

## 9. FailureAttributionGraph / Counterfactual Replay

```text
ObservedSymptom
 -> CandidateCause
 -> ContributingFactor
 -> CounterfactualIntervention
 -> ReplayOutcome
 -> RootCauseAssessment
 -> DownstreamImpact
```

Failure taxonomy 覆盖 source/data/index、retrieval/rerank/metadata/chunk、parser/table/row/unit、numeric、evidence promotion、context/memory、model judgment、handoff/concurrency/version、writer/provenance/render/release、permission/security、infra/cost/latency。

Counterfactual replay 必须声明 frozen observations、intervention boundary、replaced refs/versions、side-effect policy 和 expected downstream comparison；一次 intervention 不得静默替换多个未知环节。外部写操作禁止自动 replay，live web/API 默认复用旧 observation。

Root-cause states：`confirmed_root_cause`、`probable_root_cause`、`contributing_factor`、`correlated_only`、`unresolved`。LLM 只能生成 hypothesis/suggestion；confirmed 要求 deterministic reproduction、controlled replay 或 human root-cause approval。多个共同原因可以同时保留，不能默认把最后失败 node 当根因。

## 10. Statistical Repetition / Flakiness / Paired Comparison

Agent/model eval 至少报告 pass@1、N-run pass rate、mean/variance、worst case/slice、confidence interval、flaky failure rate、hard-failure occurrence/frequency。所有 attempts 保留，禁止 rerun-until-pass 后只保留最好结果。

`RepetitionPolicy` 按 mode/risk/cost 声明 N、paired candidate-baseline、seed/support、snapshot reuse、early stop 和 budget。Deterministic fixture 通常 N=1；stochastic model eval 使用重复；live tool eval 若外部状态变化，应使用同一 snapshot/frozen observation 或声明 non-paired limitation。

单次 privacy/permission/writer-source/numeric hard-fail 不能被高平均通过率抵消。Flaky hard fail 默认 release blocked 并进入 root-cause；不能通过提高 N 稀释。

## 11. Runtime Candidate-vs-Baseline Release Gate

Runtime release 同时满足：

```text
absolute contract thresholds
 AND candidate-vs-baseline non-regression
 AND no new zero-tolerance hard failure
 AND required operational/security readiness
```

Baseline 很差时，candidate 只要略好不能发布。Candidate/baseline 必须使用兼容 dataset/snapshot/oracle/judge/repetition policy 做 paired comparison；不兼容时状态为 `insufficient_evidence`。

`RuntimeReleaseGateDecision`：`passed`、`conditional_pass`、`blocked`、`insufficient_evidence`、`rollback_required`。Zero-tolerance hard fail 不允许 conditional pass。Waiver 只能覆盖明确非硬项，并记录 owner、reason、scope、risk、compensation、expiry 和 verification plan。

Point 01 `ShadowComparisonRecord` 是 planning shadow output 的 scoped EvalMetric/Quality artifact；`LaneCutoverDecision` 是 `RuntimeReleaseGateDecision` 的 `subject_type=decision_surface_planning_lane` specialization。TECH_10 写 quality/cutover business decision，TECH_06 只执行 authority transaction。该 migration/config approval 不等同于 TECH_09 对 research artifact 的 DecisionAttestation。

输出至少包含 hard gate status、absolute thresholds、baseline deltas、improvement claims、new failures、worst slice、flakiness、cost/latency、waivers、known gaps、rollback target 和 release maturity (`L0-L4`)。

TECH_10 runtime release 针对 code/model/prompt/tool/config；TECH_09 artifact release 针对 exact report/artifact/hash。Runtime gate pass 不自动批准客户 artifact，artifact approval 也不证明 runtime production-ready。

## 12. Online Eval / Drift / Incident Feedback

```text
online trace/reviewer feedback/incident
 -> privacy + permission + tenant filtering
 -> sampled quality candidate
 -> label/review
 -> online candidate dataset
 -> regression/gold/improvement proposal decision
```

线上 trace 默认只进入 candidate pool。监控 source/data/index、task/user distribution、model/provider、retrieval/parser、context、cost/latency、reviewer disagreement、release escape、fallback 和 incident drift。Audit-critical security/release events 100% 留本地账本；对外 observability export 只能发送 policy 允许的最小字段。

Online signal 不得自动晋级 Gold、修改 runtime prompt/skill/memory、放宽 gate 或生成已激活长期规则。Drift alert 进入 incident/failure queue，并保留 baseline/window/sample/tenant/privacy 和 missingness。

## 13. Human Evaluation Workbench

Workbench 支持 blinded pairwise、absolute rubric、claim/source/numeric/artifact drilldown、reviewer identity/role、review duration、confidence、comment、disagreement 和 adjudication。

Reviewer roles 使用不同 rubric：senior research（完整性/判断/反证）、compliance（permission/disclosure/client-safe）、presentation（语言/图表/密度）、operations（recovery/SLA/cost/incident）。需要 reviewer calibration set、inter-rater agreement、reviewer drift 和 adjudicator record。

Human edit/rating 是 label candidate，不自动成为 Gold、research fact 或 runtime policy。Pairwise 应随机 candidate order、尽量隐藏 model/baseline identity，并记录 blinding limitation。

## 14. Governed Self-Improvement

```text
FailureObservation
 -> RecurringIssueCluster
 -> RootCauseHypothesis
 -> ReproducibleFixture
 -> ImprovementProposal
 -> SandboxEval
 -> HumanReview
 -> StagedRollout
 -> OnlineMonitoring
 -> Accept / Rollback
```

Proposal targets：data/parser/ontology/rule/prompt/skill/tool-policy/context-policy/orchestration/renderer/eval。每个 proposal 记录 target contract、failures、root-cause confidence、patch refs、expected improvement、possible regressions、permission/security impact、fixture/sandbox results、rollout/rollback 和 owner。

系统可以自动创建 issue/fixture/skill/rule/prompt/test/harness patch proposal，但不能自动合并、扩大权限、晋升 evidence/Gold、修改 disclosure、覆盖 reviewer、运行 paid full-chain 或放宽 release gate。`evaluation_contract_change` 必须单独评审，不能通过改 judge/rubric/gold 把失败包装成 runtime improvement。

Recurring clustering/LLM diagnosis 前必须做 privacy/tenant filtering；proposal 不应复制受限原文或 secret。任何 accepted patch 至少新增/更新一个 regression case，并在 staged rollout 后持续监控目标与非目标 slices。

## 15. 与 TECH_01-11 / R60 的接口

| Owner | 向 TECH_10 提供 / TECH_10 要求 |
| --- | --- |
| TECH_01 | DecisionSurface/trajectory/stop/follow-up expected contract |
| TECH_02 | tool/evidence/rejection/promotion traces 与 hard gates |
| TECH_03 | source/index/retrieval/memory snapshot、freshness 和 conversion metrics |
| TECH_04 | parser/table/numeric traces 与 reproducibility oracle |
| TECH_05 | cell/judgment/counterevidence/What-Would-Change rubric objects |
| TECH_06 | durable run/events/checkpoint/replay；只为长程/model/tool eval 提供 WorkUnits |
| TECH_07 | blinded Judge/Human context、rubric injection、identity/privacy isolation |
| TECH_08 | evaluator/judge agent-as-tool task/result envelope；deterministic evaluator 不是 agent |
| TECH_09 | SurfaceClaim/artifact/verification/review/release/staleness/escape incidents |
| TECH_11 | monitoring rule/observation/alert/no-alert、RefreshRequest、ThesisDelta、source-failure 与 stale propagation |
| R60 | Eval store、runner、observability、incident/fallback、dashboard、release-readiness implementation |

TECH_10 定义 eval 业务语义，不拥有 research truth、execution event truth、artifact approval 或 R60 physical implementation。所有 paid/full-chain/release runs 继续受 Project OS preflight 和 capability ledger 约束。

## 16. R60 / Legacy E0-E12 Migration Crosswalk

现有 R60 的 EvalRun/store、gold/failure、token/cost、incident、release-readiness 和旧 `11_agent_eval_runtime_framework` E0-E12 是可复用基座，不直接等于新 contract 已生效。

必须建立 crosswalk：

| 字段 | 含义 |
| --- | --- |
| legacy_eval_id | 旧 case/runner/metric/gate ID |
| legacy_subject | 原评对象与输入 |
| new_eval_subject_type | 映射的新 subject |
| eval_mode / replayability | 原 run 能证明什么 |
| dataset/gold/oracle/metric/gate refs | 是否满足新治理合同 |
| runtime_consumed | 新 TECH_01-11 runtime 是否实际消费 |
| evidence_refs | trace/report/test/code |
| gap / owner / disposition | adapt / retain / retire / replace |

存在 eval script、fixture 或 S10 scope pass，只证明对应旧 slice；不能推断 DecisionSurface、agentic search、new ContextEngine、subagent version control、CanonicalPresentationModel 或新 release gate 已 runtime-proven。

## 17. Module Eval Requirement Matrix

以下现有 eval 继续有效，但必须注册为 EvalProgram/EvaluatorDefinition/Metric/Gate，不再作为散落顶层架构：

| Domain | Required evals |
| --- | --- |
| Agentic Search / Evidence | trajectory positive/negative、metadata-filter precision、RAG-to-evidence conversion、exact-authority violation、tool fallback/rejection/promotion |
| Numeric / Parser | table/row/unit/period/metric binding、numeric replay、derived metric fidelity、forbidden substitution |
| External / Social | SocialIdentityAttribution、StatementFactSeparation、ClaimConflict、DiscourseSampling、SentimentRepresentativeness、SocialProvenance |
| Domain / WWC | CellAnswerDirectness、BusinessMechanism、OperatorOwnership、JudgmentBoundary、CellDependency、RepairResume、WhatWouldChangeQuality、CounterfactualEvidenceTrajectory、SeparateSectionIntegrity |
| Context / Memory | ContextCompleteness、RelevanceAndEconomy、RoleIsolation、EvidenceIdentityPreservation、CompactionDrift、StaleMemoryLeak、GovernanceDecay、FollowUpContinuity、MemoryPromotion、InjectionExplainability、InputReconstruction、SnapshotRace |
| Subagent / Parallel | CoordinationEnvelopeCompleteness/Routing、ParallelVersionImpact、SemanticMaterialityCalibration、SelectiveInvalidation、ContextRebaseIntegrity、StaleParallelOutput、VersionStateAwareness、CheckpointVersionValidation、MaterialityContract、AtomicCallQuarantine |
| Presentation / Artifact | CanonicalPresentationParity、SurfaceClaimBoundary、WriterNoSourceTrajectory、BidirectionalProvenance、ArtifactConstraintGraph、VerifierLayerBoundary、MultiFormatSemanticParity、HumanEditRouting、ClientSafeDisclosure、ReleaseVersionIntegrity、WorkbenchProjectionReplay、ClientSeniorReady |

TECH_09 指标继续包括 material claim trace completeness、cross-artifact claim consistency、stale claim leakage、numeric projection fidelity、disclosure leakage、human edit routing、release gate escape 和 What-Would-Change projection consistency；它们必须通过 EvalMetricDefinition + EvalGatePolicy 注册并按 artifact/audience/language/severity/renderer slices 报告。

## 18. Minimum Fixtures / Acceptance / Current Boundary

第一批合同 fixtures：

1. EvalRunManifest canonical digest/reconstruction 与 incompatible-manifest rejection。
2. EvalSubject type-specific evaluator routing；rubric 不跨 subject 误用。
3. Evaluation mode proof-boundary 和 replayability classification。
4. Gold contract、time/as-of leakage、hidden-holdout isolation/contamination。
5. OracleRoutingPolicy 多 oracle/conflict/abstain 和 deterministic hard precedence。
6. Judge calibration、ordering/identity bias、false accept/reject 和 judge contract change。
7. EvalMetricDefinition 与 EvalGatePolicy 分离；L2/L3/L4 thresholds 不改公式。
8. Invariant trajectory 多条合法 path、forbidden transition、loop/stop/repair fixture。
9. FailureAttributionGraph controlled intervention、probable/confirmed/unresolved fixture。
10. Statistical repetition、paired comparison、flaky hard-fail 和 rerun-until-pass negative fixture。
11. Absolute threshold + baseline non-regression runtime release fixture。
12. Online trace privacy filter、candidate promotion、drift/incident fixture。
13. Human pairwise/calibration/disagreement/adjudication fixture。
14. ImprovementProposal -> sandbox -> review -> rollout -> rollback；gate/Gold auto-change negative fixture。
15. R60/E0-E12 crosswalk：legacy asset 不冒充 new runtime consumed。

验收标准：每个 quality claim 都能回答评什么 subject/version、在哪种 mode、使用哪个 dataset/snapshot/oracle/evaluator/metric/gate、结果是否可重放、为何归因、candidate 相对 baseline 和绝对门槛如何、谁批准 release/waiver、失败如何进入 regression/improvement proposal。

当前项目已有 SQL-backed eval store、R60 objects、50-case catalog、failure/gold lifecycle、token/cost/incident/release-readiness fixtures 和部分 node/full-chain eval；但尚未统一实现本文的 Quality Ledger、EvalRunManifest、EvalSubject、OracleRoutingPolicy、Metric/Gate separation、invariant trajectory evaluator、FailureAttributionGraph、statistical paired release gate、hidden holdout isolation、Human Eval Workbench 或 governed staged self-improvement。

因此状态仅为 `documented / contract_draft`。旧 eval/runtime evidence 需逐项 crosswalk；不得把本文或旧 S10 scope pass 写成新 TECH_01-11 agentic architecture 已完成、paid/full-chain 已通过或生产发布就绪。

## 19. 2026-07-11 Agent Information Economy Contract

新增 `InformationEconomyLedger`，统一 TECH_06 model/tool/cost facts、TECH_07 context selection/usage、TECH_08 activation/handoff/output usability 和 TECH_09 accepted workpaper/artifact value。PRD 的 `token_to_workpaper_yield`、`token_to_rendered_claim_yield`、`duplicate_context_rate`、`invalid_information_transfer_rate`、`specialist_useful_output_rate`、`first_pass_judgment_yield`、`repair_due_to_agent_failure_rate` 和 `answer_density_per_required_item` 必须注册为 EvalMetricDefinition，而不是 dashboard 临时公式。

高 token 不是自动失败，低 token 也不是自动成功。AIE 需要按 task mode、sector、cell count、source complexity、model/agent/prompt version 和 quality gate 分层，只有在研究质量、evidence/numeric、review 和 delivery hard gates 同时满足时比较单位价值。FailureAttributionGraph 必须区分 bad planning、over-fanout、duplicate context、selector pollution、unusable specialist output、avoidable repair 和 legitimate evidence complexity，禁止单纯削减上下文来优化成本指标。

## 20. 2026-07-12 External Platform Capability / Replacement Pressure Eval

TECH_10 新增 `ExternalPlatformCapabilitySnapshot`，用于持续评估通用 Agent 平台、金融垂直 Agent 和专业研究软件对 FIN 产品能力与 ICP 的替代压力。它不是竞品宣传材料摘要，也不能把外部平台输出当 Gold。

每个 snapshot 至少冻结：platform/version/date、model、UI-selected expert/skills、observable invoked tools/agents、prompt-equivalence limitation、task/sector/report type、artifact、structured trajectory、source-open、claim lineage、numeric/period quality、latency/token、user-segment fit 和 terms/data-access boundary。

评测必须分开：

1. `artifact_quality`：结构、可扫读性、图表、交付格式、语言与表面 client readiness；
2. `research_quality`：机制、证据、数字、期间、反证、估值和来源可核验性；
3. `runtime_capability`：实际 agent/subagent、tool use、repair、context、durability、permission 和 provenance；
4. `product_replacement_pressure`：哪些用户工作流已经可替代、接近替代或仍明显缺失；
5. `information_economy`：相同任务下的时间、模型调用、累计输入、工具调用与 accepted workpaper yield。

必须区分 `selected_capability`、`context_injected_capability`、`invoked_capability` 和 `accepted_output_capability`。UI badge、task list 或报告标题不能证明专家、Skill、subagent 或工具执行。外部平台没有公开内部轨迹时必须标记 `not_observable`，不得反向推断没有能力。

替代压力状态固定为 `current_pressure`、`near_term_pressure`、`watch`、`not_observed`，并按 ICP/workflow 切片。任何“尚未替代”结论都有 platform version/date TTL，不能永久固化。当前首批 fixture 为 `WB-S01B/WB-S02B`：通用平台已对公开网页研究初稿和 HTML/dashboard 形成高压，但尚未证明 claim-local provenance、可复算 numeric program、point-in-time accepted memory、私有/商业数据治理、durable institutional approval 和 cross-artifact consistency。

## 21. 2026-07-12 R1-R4 / Institutional Control Evaluation Contract

根据新版 PRD/TECH_00A，TECH_10 必须同时评价 capability maturity 和单个 ResearchCase 的 product outcome。两者正交：`runtime_partial` 不等于某 Case R2，单个 R3 artifact 也不等于产品 L4 production。

### 21.1 Research outcome levels

| Level | Required gates |
| --- | --- |
| `R1_artifact_complete` | schema/render/openability/visual integrity |
| `R2_research_valid` | required-cell closure、Evidence promotion、Numeric replay、Gap/LeadReview、no hard-fail escape |
| `R3_reviewer_accepted` | exact-version DecisionAttestation、reviewer role/authority、approval/hash/release integrity |
| `R4_longitudinally_maintainable` | follow-up continuity、PIT reconstruction、selective refresh、reviewer correction reuse、cross-artifact stale/reapproval |

EvalRun 必须声明 target level；不能用 R1 指标通过来证明 R2-R4。

### 21.2 New metric families

- `institutional_case_integrity`：Case head uniqueness、business owner writer、event replay、version/supersession；
- `institutional_memory_quality`：PIT reconstruction、freshness/permission、contradiction、reviewer correction reuse、negative memory precision；
- `longitudinal_maintenance`：affected-cell precision/recall、unnecessary rerun、refresh latency、thesis delta correctness；
- `artifact_accountability`：material claim attribution、ActorSnapshot coverage、DecisionAttestation target/hash、manifest parity、stale leakage；
- `configuration_governance`：unapproved config activation、hard-invariant override、rollback/reproducibility、tenant isolation；
- `provider_portability`：model/search/parser/data swap 的 R2/R3 non-regression、cost/latency 和 failure recovery；
- `human_workflow_value`：time-to-approved-output、review burden/edit distance、approval turnaround、repeat correction avoided。

### 21.3 Accountability and privacy eval

Fixtures 覆盖：material event attribution completeness、delegated approval scope、OA callback replay、exact artifact hash、retention/deletion tombstone、raw prompt access、audit/usage view isolation。员工 usage 指标不得进入 productivity score；任何测试若发现普通 manager 可读取无业务必要的 raw prompt，作为 permission/privacy hard fail。

### 21.4 Cross-module invariants

1. TECH_03/07 不得同时写 active memory head。
2. TECH_06 execution success 不得自动推进 TECH_01/02/04/05/09 business accepted。
3. TECH_11 trigger 不得直接修改 Judgment/Artifact current head。
4. model/provider/skill/config swap 不得改变 owner、permission、schema 或 hard-gate semantics。
5. reviewer correction必须传播到 affected Case/Memory/Artifact fixtures，不能只改 prose。
6. released artifact依赖 material upstream stale 时不得继续显示 current/approved。

### 21.5 Required longitudinal calibration cases

首批 corpus 除单次 P36/跨行业 cases 外，必须加入同一 Case 的四步序列：initial research -> reviewer correction -> user follow-up -> quarterly refresh/cross-artifact reapproval。每一步冻结 source/as-of/available-at、actor/config/model/provider 和 expected affected scope，用于评 R4，而不是把四次任务当独立报告。

本节状态为 `documented / contract_draft`；新增指标和 fixtures 尚未进入 R60 runtime，不得把文档更新写成 R1-R4 已通过。

## 22. Product Release Train / Gate Budget Contract（2026-07-17）

TECH_10 现在同时消费 `ProductReleaseIntent` 和 Point execution evidence，但不拥有产品需求或业务对象。新增稳定质量对象：

| 对象 | 质量职责 |
| --- | --- |
| `ReleaseContract` | 冻结 release channel、L/R 目标、Case set、TECH/Point refs、风险、预算和 rollback |
| `ReleaseSlice` | 标记一次纵向能力增量及 consuming release |
| `ReleaseGatePolicy` | 定义最多五个产品 release-blocking gates |
| `DeferredBacklogItem` | 记录不阻断当前版本的风险、owner、目标版本和触发条件 |
| `ReleaseEvidenceManifest` | 引用 exact candidate、EvalRun、Case、artifact、review、known gaps 和 rollback evidence |
| `ReleaseGateDecision` | 对目标 channel 做 passed/conditional/blocked/rollback 裁决 |

ReleaseContract 必须声明四个独立状态轴：`release_channel`、`target_product_maturity`、`target_case_outcomes`、`production_readiness`。单项 capability maturity 继续沿用 TECH_00 lifecycle，不能被 release-level status 覆盖。

每个产品版本最多设置：

1. `RG1_vertical_path`；
2. `RG2_evidence_numeric_integrity`；
3. `RG3_research_outcome`；
4. `RG4_review_product_value`；
5. `RG5_release_rollback`。

底层测试数量不受五项限制，但必须归入上述 gate evidence，不能每发现一个边界就创建新的产品 closeout gate。

当前版本 zero-tolerance hard fail 至少包括：权限/秘密/数据破坏、false evidence promotion、material numeric corruption、Writer source violation、supervisor supplement 冒充 runtime、material provenance 缺失、双 authoritative write、核心纵向链不可运行且无 rollback。其他问题必须分类为 `next_release_committed / enterprise_readiness / operational_regression_backlog / exploration / commercial_or_external_boundary`。

同一 blocker 最多两轮 bounded repair。第二轮后，TECH_10 必须输出 block/defer/stop 裁决；只有发现真实数据破坏、权限绕过或核心路径不可运行的新证据，才允许继续同一 release 的第三轮以上治理修订。不能用不断新增 gate 代替上游 root-cause repair，也不能因理论最优防御无限延迟目标通道发布。

测试 profile 固定分为：

- `fast`：每次提交；
- `component`：合并前/每周；
- `operational`：明确权限下的 runtime/recovery/tool/rollback；
- `release`：Anchor/regression Case、human review、artifact 和目标通道准入。

Internal Alpha 不要求重复完整 enterprise production qualification。企业 pilot/production 才要求真实多用户、SSO/retention、长期 worker、SLA、incident 和正式 security evidence。任何 release decision 都必须保留 `production_readiness`，不得把 Internal Alpha 的 L2/R2 结果描述为生产通过。

`REL-PROD-001` 当前机器可读合同为 `configs/releases/fin_ia_0_1_release_contract_v1_1.json`，其 feature scope 为 `configs/releases/fin_ia_0_1_feature_scope_matrix_v1_0.json`。v1.1 supersede v1.0，因为旧版把 P36 Anchor Case 的六个 cell families 与产品功能范围混在一起；旧合同只保留审计。RG1/RG4 必须同时验证 Task Center、Case workspace、Evidence/Numeric、Workpaper/Repair、Deliverable/Review 和 Activity/Trace 产品 surface，不能只凭 memo 或 Case R2 判定 Internal Alpha 达到 L2。完整规则见 `docs/architecture/repository/RELEASE_OPERATING_MODEL_20260717.zh-CN.md`。

## 23. FIN 0.1.3 Search / Model / Research 分层评测与失败归因（2026-08-08）

FIN 0.1.3 的真实工程结果证明，检索、模型合同和研究内容必须作为三个可独立失败的 EvalSubject，不能把“完整链终止”“JSON 合法”或“报告已渲染”合并成一个绿色分数。

### 23.1 Search gate ladder

`SearchQualityCard` 按以下门依次出具，后门不得在前门失败时计算通过：

| Gate | EvalSubject | 最低证据 | 失败 owner |
| --- | --- | --- | --- |
| SQ0 | Provider capability | declared/configured/operational/replay/live exact state | TECH_02/06 |
| SQ1 | Fair route execution | required slot first opportunity、attempt/capture、budget/no starvation | TECH_02/06 |
| SQ2 | Candidate ceiling | evaluator-only target-in-pool、required-slot recall、currentness | TECH_02/03 |
| SQ3 | Ranking/selection | NDCG/MRR、selected coverage、diversity/reconciliation | TECH_02/03；仅 SQ2 pass 后 |
| SQ4 | Promotion | false promotion=0、authority/date/entity/relationship/lineage | TECH_02/04 |
| SQ5 | Research utilization | accepted Evidence 到 Claim/Workpaper 的实质利用与边界 | TECH_01/05/10 |

`typed_gap` 只有在 SQ0–SQ2 的真实 attempt 或明确 external/commercial boundary 后才可记 honest closure。未运营 Provider、未尝试 route、slot starvation 或 parser rejection 必须分别归因；不能统一记成 source absence。

### 23.2 Model and content gates

- Model Capability Eval 按 contract family 记录 strict JSON、identity、numeric ref、evidence role、closure、threshold、tool use 和 narrative；一个 family 的通过不提升其他 family 自主权。
- Deterministic Harness guard 通过不等于模型 natural adherence 通过；模型自然失败也不能通过在核心 Runtime 中无限增加 Provider-specific 分支修复。
- Research Outcome Eval 必须单独评价公司/问题专属性、证据论证、Numeric 解释、因果机制、跨 Cell 综合、反方/gap、WWC 和 senior usefulness；`L1=0`、9 Artifacts 或完整调用次数不能替代八维质量和 qualified-human acceptance。
- FailureAttributionGraph 必须把 source/tool 缺口、contract/compiler 缺口、model adherence、research method/coverage、renderer/product UX 和 release governance 分开；counterfactual replay 只能证明被改变的层。

### 23.3 Current FIN 0.1.3 projection

当前 S1-08 v3 已在 clean archive/fresh process 以 `70 passed / 0 failed / 0 skipped` 独立证明确定性结构，最近 DELL live SQ1 terminal integrity 通过但 SQ2 target-in-pool=0，因此 SQ3 ranking 仍未准入。S2 deterministic correction control 已证明，但 DeepSeek natural evidence-role/closure 失败。S3 只有 minimum engineering anchor，八维产品内容验收未执行；S4/S5 未开始。故 release gate 仍为 blocked，本节不授权 live、model、ranking 或 release execution。

## 24. FIN 0.1.3 中段质量、证明预算与阶段 Join Gate（2026-08-08）

### 24.1 六轴状态，禁止单一绿色总分

后续评测分别维护：`execution governance`、`source/search`、`numeric truth`、`model autonomy`、`research outcome`、`product/release`。每条证据只能提升其直接评测轴：

- clean archive、exact-once、lineage mutation 只提升 execution governance；
- candidate ceiling、currentness、recall、promotion 只提升 source/search；
- exact fact、formula、period/unit/currency 只提升 numeric truth；
- natural canary、correction closure、profile adherence 只提升 model autonomy；
- thesis、机制、跨 Evidence 综合、反方、WWC 与 human rubric 只提升 research outcome；
- current Case dogfood、review burden、exact acceptance、rollback/RG 只提升 product/release。

不得把测试数、Artifact 数、typed gap 数、JSON 合法、页面渲染或 preflight pass 合成一个“全链通过”。

### 24.2 证明预算

1. 确定性合同改动先用 zero-call unit/mutation/full-fake；同一合同 family 最多一次结构修订。
2. clean proof 只在环境可移植性、source lineage、权限或外部副作用值得独立证明时执行；普通文档或无 Runtime 改动不重复跑全套。
3. natural canary 按合同 family 计，不按字段计；每个发生实质变化的 family 最多一次最小节点 canary。
4. live search 在同一根因结构修复后最多一次 successor；再次失败进入 Provider／产品范围决策。
5. formal end-to-end 只在 SearchQualityCard、NumericTruthCard 和 ModelCapabilityProfile 已就绪后执行；不得用 full-chain 发现本可由 mutation 暴露的确定性缺陷。

### 24.3 S3 Join Gate 与研究方法激活

S3 入口必须同时满足：S1 current Evidence Pack 可用、S2 已冻结当前 Provider 的 `ModelCapabilityProfile + AutonomyGrant`、material numeric truth 可重算。方法 registry 中的条目只有在 `runtime_injected`、`node_consumed`、`paid_artifact_proven` 后才能计入实现覆盖；`documented` 或 `contract_translated` 只表示设计资产。

S3 出口必须同时通过 L1/L2、八维绝对质量 `>=24/32`、Q1–Q7 无低于 2、Q1/Q2/Q3/Q8 各不低于 3、paired gain 和 qualified-human content acceptance。Search 不足、模型不遵循、内容薄弱分别保留自己的 failure code；任何一类都不能被另一类分数补偿。
