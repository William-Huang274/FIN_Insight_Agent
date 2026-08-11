# TECH_09：Trace / Provenance / Workbench / ArtifactConsistencyGraph

日期：2026-07-09

状态：技术合同草案。本文定义 claim/cell 到 tool observation、parser/numeric lineage、canonical presentation、artifact consistency、Workbench review、DecisionAttestation 和 release 的 last-mile control contract；不表示 runtime/product 已实现。

## 1. 要解决的问题

P36 Node11 说明当前 verifier / Workbench 能守 claim/ref/source/gap/artifact 边界，但缺 `decision_surface_cell` review surface。用户要的是五链条决策矩阵，不是只看全文 citation。

## 2. Provenance Graph

每个 writer claim 必须追到：

```text
claim
 -> decision_surface_cell
 -> accepted_evidence
 -> promotion_decision
 -> parser/numeric lineage
 -> tool_invocation
 -> observation
 -> source/artifact
 -> verifier result
```

## 3. 核心对象

- `TraceSpan`
- `ClaimProvenanceGraph`
- `CellProvenanceRecord`
- `CitationClickthroughRef`
- `ArtifactConsistencyGraph`
- `WorkbenchReviewTarget`
- `ReviewAction`

## 4. Workbench decision-cell review

新增 review target：`decision_surface_cell`。

Cell review 必须展示：

- `cell_id`
- `chain_segment_id`
- `cell_question`
- `conclusion`
- `source_grade`
- `numeric_sanity_status`
- `official_or_estimate_flag`
- `accepted_evidence_refs`
- `rejected_candidate_refs`
- `typed_gap_refs`
- `repair_route`
- `what_would_change`
- `review_status`

Review action：

- `accept`
- `reject`
- `needs_source`
- `needs_parser`
- `needs_repair`
- `estimate_only`
- `commercial_gap`
- `supersede`

所有 action 必须 append-only。

## 5. ArtifactConsistencyGraph

覆盖：

- memo；
- PPT；
- Excel；
- dashboard；
- fact table；
- chart；
- citation / footnote。

检查：

- 数字一致；
- 单位一致；
- 期间一致；
- 口径一致；
- source boundary 一致；
- chart axis / label 不误导；
- supplement-only 不被写成 runtime accepted。

## 6. 与其他 TECH 的边界

- `TECH_01` 定义 cell / pack；
- `TECH_02-04` 生成 evidence / numeric / observation lineage；
- `TECH_06` 记录 TraceSpan / Artifact；
- `TECH_07` 保证 provenance context 不丢；
- `TECH_10` 评估 provenance 和 artifact consistency。

## 7. 第一批 fixture

1. Claim -> cell -> evidence -> observation lineage fixture。
2. Citation clickthrough fixture。
3. DecisionSurfacePack Workbench projection fixture。
4. Memo / dashboard / Excel numeric consistency fixture。
5. Supplement boundary consistency fixture。

## 8. 验收标准

- Workbench 可按 cell review，不只按 claim review。
- 每个 writer claim 可点击回 source / observation / numeric trace。
- ArtifactConsistencyGraph 能阻止跨 artifact 数字/口径冲突。
- Verifier 能拒绝 generic memo-only output。
- ReviewAction append-only 且可 replay。

## 9. 2026-07-10 FactorCard / Quant Validation Review

Workbench 新增 `factor_validation` review target，但它必须与 `decision_surface_cell`、原始 thesis 和证据链联动，不能成为独立的黑箱分数页面。

完整 lineage：

```text
decision_surface_cell
 -> quant_validation_projection
 -> FactorCard / ValidationResult
 -> PITDatasetSnapshot / LeakageGuardResult
 -> FeatureSpec / LabelSpec / UniverseSpec
 -> NumericProgramTrace
 -> promoted fact / market context
 -> source / available-time / revision
```

Review surface 至少展示：

- factor lifecycle status：`diagnostic_score` / `candidate` / `in_sample_supported` / `out_of_sample_supported` / `paper_monitored` / `retired`；
- data range、universe、coverage、missingness、publish/available/tradable-after policy；
- IC / RankIC、quantile monotonicity、decay、turnover、event-window 或 backtest result；
- OOS / walk-forward、multiple-testing、risk neutralization、cost/liquidity/capacity 状态；
- standard-factor exposure、regime stability、failure scenarios；
- 该 FactorCard 对当前 cell 是 support、counterevidence 还是 diagnostic only；
- `no_investment_advice`、禁止替代的 commercial fields 和 human approval events。

任何 artifact 如果把 `diagnostic_score` 写成 `validated factor`、把样本内结果写成样本外结论、把 lagged ownership 写成实时资金流，或隐藏失败/retired FactorCard，ArtifactConsistencyGraph 必须阻断。

## 10. 2026-07-10 Social Statement / Discourse / Conflict Review

Workbench 新增 `public_statement`、`social_discourse_sample`、`user_feedback_theme` 和 `claim_conflict` review targets。

公开发言 review 至少展示：

- account/channel immutable id、handle、owner、speaker role；
- verification type、official-domain crosslink、identity confidence；
- canonical post/video/live URL、post ID、发布时间、抓取时间；
- 原文、翻译、media/transcript timestamp、reply/quote/repost parent；
- edited/deleted/archived status 和 snapshot hash；
- `statement_authenticity`、`underlying_fact_status`、supports / cannot-support；
- conflict evidence、resolution 和 reviewer wording。

舆情 review 至少展示：

- platform/query/time window/sample size；
- sampling mode：top-engagement、chronological、random/API sample 或 user-provided；
- language/geo/account coverage、dedupe、bot/spam filter；
- engagement weighted 与 unweighted 结果；
- unavailable/deleted/private content、rate limit、ranking bias 和 missingness；
- 正面、负面、中性/混合主题及代表样本与反例。

Workbench 必须使用“observed platform discourse / 已观察样本中的反馈主题”等措辞，不能把单平台、高赞评论或不可审计样本呈现为“真实公众舆情”。用户可以自行判断这些信号的可信度，但系统必须如实展示样本和偏差。

ArtifactConsistencyGraph 必须阻断：

- 把“某人声称”改写成“事实已经发生”；
- 把政策意图改写成正式生效政策；
- 把产品发布直播改写成已验证性能、普遍可用或财务贡献；
- 把高赞评论或单平台样本改写成 representative public sentiment；
- 隐藏与该发言冲突的 accepted fact 或 `ClaimConflictRecord`。

## 11. 2026-07-10 Domain Judgment / What-Would-Change Review

Workbench 新增 `domain_cell_judgment`、`cell_dependency_edge`、`what_would_change_program` 和 `counterfactual_test` review targets。

Domain judgment review 展示 primary/contributor/challenger proposals、judgment status、business mechanism、confidence vector、evidence/counterevidence/gap refs、adjudication summary、downstream claim strength 和 wording boundary。

What-Would-Change panel 必须独立于主结论，展示：current judgment version、decisive variables、causal rationale、strengthen/weaken/overturn branches、evidence sought、tool/route attempt summary、observations、directional assessment、unresolved gaps、monitoring triggers 和 re-adjudication status。

ArtifactConsistencyGraph 必须阻断：

- 把 counterfactual scenario 或 monitoring trigger 写成当前事实；
- 把未完成的 directional inference 并入主结论；
- 隐藏 failed/rejected evidence attempts；
- 新证据未生成 cell version / adjudication event 就覆盖旧结论；
- 将审计 reasoning summary 扩写成不存在的 raw CoT 或模型确定性声明。

## 12. 2026-07-10 TECH_09 Last-Mile Control Plane 补强

TECH_09 不是单纯 trace viewer，也不是另一个事实生成 agent。它是 FIN 从冻结研究状态到用户可见交付物之间的 truth-preserving projection、verification、review 和 release control plane：保证 Writer/Composer 可以做高质量表达，但不能改变 evidence identity、numeric identity、adjudicated judgment、gap、counterevidence、What-Would-Change 或 source boundary。

### 12.1 TECH_09 与 R55 / 其他 TECH 的边界

TECH_09 拥有：

- frozen research state 到 canonical presentation model 的合同；
- `SurfaceClaim`、section/table/chart/citation binding 和 cross-artifact provenance；
- Writer/Presentation Agent 的 input/output、no-source 和 blocker/revision contract；
- ArtifactConsistencyGraph constraints、verification bundle、Workbench review target、release decision 和 invalidation；
- artifact 是否 review-ready、client-safe、publishable 或 stale 的业务控制状态。

现有 R55 `Deliverable Studio / Dashboard Projection` 继续拥有：renderer registry、DOCX/PPTX/XLSX/PDF/HTML/chart/graph tools、`RenderJob`、format-specific generation、layout implementation 和 artifact packaging。TECH_06 拥有 durable execution、generic immutable artifact persistence 和 approval/release transaction；TECH_09 拥有 review/approval/release 的业务语义与 exact-target attestation。TECH_07 编译 writer/verifier context；TECH_08 调用 Writer/Verifier subagent；R59 落 Workbench API/frontend；TECH_10 负责 eval。TECH_09 不复制这些实现，也不把 renderer 失败误写成研究失败。

### 12.2 Canonical Presentation Object Graph

正式主链路固定为：

```text
FrozenDecisionSurfaceSnapshot
 -> DeliverableIntent / DeliverablePlan
 -> WriterBrief
 -> NarrativeSurfaceContract
 -> CanonicalPresentationModel
 -> SurfaceClaim / SurfaceTable / VisualizationSpec / CitationBinding
 -> ArtifactProjectionBinding
 -> RenderJob / ArtifactVersion
 -> VerificationBundle / ArtifactConsistencyGraph
 -> WorkbenchReviewAction
 -> ReleaseDecision
 -> PublishedDeliverable / SupersededArtifact
```

稳定对象：

- `FrozenDecisionSurfaceSnapshot`：writer admission 时冻结的 DecisionSurfacePack、cell/judgment/evidence/numeric/gap/What-Would-Change heads 与 permission refs。
- `DeliverableIntent`：用户目的、audience、decision use、language、format、length、deadline、internal/client-safe 和 approval policy。
- `NarrativeSurfaceContract`：required/forbidden sections、storyline、tone、claim density、citation/disclosure、table/chart、appendix 和 What-Would-Change placement。
- `CanonicalPresentationModel`：与格式无关的章节、claim、table、chart、callout、gap、citation 和 appendix 模型；不是最终 prose，也不创造事实。
- `ArtifactProjectionBinding`：canonical object 到 memo paragraph、slide、sheet/cell、dashboard card、chart series/label 和 footnote 的映射。
- `VerificationBundle`：deterministic、semantic、visual 和 policy verification results 及 blockers。
- `ReleaseDecision`：绑定 exact artifact/input/review/permission versions 的 internal/client/publish 决定。

研究真相层、presentation model 层、rendered artifact 层和 review/release 层必须分开。Rendered artifact 或用户对 artifact 的编辑不能反向自动成为 accepted evidence、cell judgment 或 DecisionSurfacePack truth。

### 12.3 Writer / Presentation Agent Input, Output and Bounded Loop

`PresentationTask` 输入至少包括：FrozenDecisionSurfaceSnapshot、WriterBrief、DeliverablePlan、NarrativeSurfaceContract、approved/review-ready refs、typed gaps、What-Would-Change refs、audience/disclosure policy、template/style refs、budget 和 stop condition。禁止注入 raw retrieval dump、未经 gate 的 rows、private scratchpad、unapproved supplement 或不属于 writer role 的工具权限。

Writer 可以执行表达层 bounded loop：理解受众与母语表达、规划故事线、选择 section/table/chart/card、去重、压缩、生成多格式 presentation model、检查 claim coverage 和可读性、根据 verifier/reviewer 的 presentation-only feedback 局部修订。Writer 不得调用 DB/RAG/web/source adapter/parser/numeric research tool，不得从 raw rows 产生新结论，不得把 gap/scenario/context 改写为 fact。

Writer 状态机：

```text
ADMITTED
 -> INPUT_FROZEN
 -> NARRATIVE_PLANNED
 -> CANONICAL_MODEL_BUILT
 -> CLAIMS_BOUND
 -> DRAFTED
 -> RENDERED
 -> VERIFIED
 -> REVIEW_READY
 -> REVISION_REQUESTED / APPROVED / BLOCKED
 -> PUBLISHED / SUPERSEDED / RETIRED
```

Writer 输出 `CanonicalPresentationModel`、`WriterDraftPack`、`SurfaceClaim[]`、table/chart specs、ArtifactProjectionBindings 或 typed `WriterBlocker`。自由文本 draft 不能绕过 claim binding 和 verification 直接发布。

### 12.4 SurfaceClaim / ClaimSurfaceMap

新增一等对象：

- `SurfaceClaim`：一个 material fact、derived metric、adjudicated judgment、context signal、scenario、gap、counterevidence 或 What-Would-Change statement 的 presentation identity。
- `ClaimSurfaceMap`：同一 SurfaceClaim 在不同 section/artifact/language/audience 中的投影集合。

`SurfaceClaim` 至少记录 claim_id/type/role、source cell/judgment version、evidence/numeric/gap/counterevidence refs、claim strength、writer-allowed wording、forbidden wording、citation policy、audience visibility、language/translation version、current status 和 supersession。不是每个连接词都需 citation，但每个 material number、fact、judgment、chart takeaway 和 scenario boundary 必须绑定 SurfaceClaim。

同一 claim 在 memo、PPT 和 dashboard 中可以使用不同长度和措辞，但 claim strength、direction、period、unit、scope、identity 和 uncertainty 不能漂移。文本相同不是一致性的充分条件；共享 canonical claim/version 才是。

### 12.5 WriterBlocker and Revision Routing

`WriterBlocker` 必须分类并携带 section/claim/artifact refs、base versions、observed issue、downstream impact、requested owner/action 和可保留 draft scope：

| Blocker | 默认路由 |
| --- | --- |
| `storyline_or_scope_ambiguity` | Lead |
| `missing_or_weak_evidence` | Lead -> Evidence/repair owner；Writer 不补源 |
| `numeric_or_unit_conflict` | TECH_04 / verifier |
| `cell_judgment_conflict` | Cell Adjudicator / Lead |
| `citation_or_provenance_missing` | provenance/evidence owner |
| `audience_or_disclosure_conflict` | Lead/Human/Compliance |
| `render_or_layout_failure` | R55 renderer owner |
| `format_or_language_quality` | Writer presentation-only revision |

稳定的 `writer_blocker_type` 还必须细分：

- `missing_required_cell`：NarrativeSurfaceContract 要求的 material cell 缺失，回 Lead / cell owner；
- `missing_surface_claim`：上游有可用判断但未形成受控展示命题，回 Lead / TECH_09 claim compiler；
- `missing_citation_binding`：material claim 没有可解析 citation，回 provenance/evidence owner；
- `missing_numeric_binding`：正文、表格或图表使用数字但缺 NumericProgramTrace/canonical fact binding，先回 TECH_04；若根因是 source/evidence 缺失再转 TECH_02；
- `pack_version_conflict`：Writer 输入、claim、numeric、citation 或 What-Would-Change versions 不兼容，回 TECH_06/08 version coordinator；
- `claim_boundary_ambiguity`：allowed strength/qualifier/cannot-support 不足以生成稳定 wording，回 Cell Adjudicator / Lead；
- `audience_disclosure_conflict`：目标受众无权看到 claim/source/citation，回 Human/Compliance；
- `what_would_change_missing`：仅在 DecisionSurfaceContract/NarrativeSurfaceContract 要求时阻断，回 domain owner / Lead；
- `artifact_projection_conflict`：同一 canonical object 无法按目标格式投影，先由 TECH_09 分类为 content-density、semantic、data-binding 或 renderer/layout 根因后路由 Writer/R55/Lead。

每个 blocker 记录 `draft_can_continue`、`blocked_projection_scope`、`retained_sections`、`required_return_schema` 和 `repair_completion_condition`，避免一个局部 blocker 无条件废弃全部 draft。

上游 research truth 变化必须走 TECH_08 latest-head/rebase；只影响语言、版式或信息密度的 revision 可以复用同一 frozen research head 并生成新 presentation/artifact version。Blocker 不能通过 Writer 添加免责声明或模糊措辞假装关闭。

### 12.6 Bidirectional Provenance and Invalidation

完整 provenance 扩展为：

```text
source/snapshot
 -> observation/tool invocation
 -> parser/table/numeric lineage
 -> promotion decision / accepted evidence
 -> DomainCellJudgment / AdjudicatedDecisionCell
 -> SurfaceClaim
 -> section/table cell/chart series/dashboard card
 -> ArtifactVersion
 -> VerificationResult / ReviewAction / ReleaseDecision
```

必须同时支持 backward clickthrough 和 forward impact analysis。source amendment/restatement、parser/numeric correction、promotion revoke、cell supersession、permission/license change 或 reviewer override 发生时，系统沿 graph 找到受影响 SurfaceClaims、artifacts、dashboards 和 published deliverables，产生 stale/review/release invalidation events；不能静默重写已发布文件。

Forward impact 不得只输出全局 `stale=true`。新增 `ArtifactStalenessAssessment`：

- `artifact_current`：所有 material bindings 与 active compatible heads 一致；
- `artifact_partially_stale`：局部 SurfaceClaim/section/table/chart binding 失效，但不改变核心结论或 release eligibility；只重开受影响 projection 和 verifier；
- `artifact_materially_stale`：核心判断、关键数字、风险披露、What-Would-Change、client-safe boundary 或 release gate 依赖失效；暂停继续发布/分发并要求 re-review；
- `artifact_superseded`：已有正式新 artifact version 替代旧版；旧版保留审计但不作为 current；
- `artifact_withdrawal_required`：已发布 artifact 存在事实、权限、许可或合规硬问题，需要显式 withdrawal decision，不能只等待新版本。

Assessment 必须记录 changed upstream refs、affected SurfaceClaims/projections、materiality basis、current release state、allowed continued use、required owner/action 和 revalidation scope。未被当前 artifact 引用的 non-material cell head advance 不得自动使整份 artifact stale。

Citation clickthrough 至少能定位 source snapshot、page/section/table/row/cell/timestamp、parser version、numeric trace、promotion status 和 claim/cell boundary。URL-only 或无法回放 snapshot 的 citation 必须显示 replay debt，不能获得与 frozen source 同等的可审性。

### 12.7 ArtifactConsistencyGraph Schema and Constraints

ArtifactConsistencyGraph 的 nodes 至少包括 canonical fact/metric/judgment/gap/SurfaceClaim、table/cell、chart/series/axis/label、section/slide/sheet/card、citation/footnote、artifact version 和 release decision。Edges 至少包括 `derived_from`、`projects`、`cites`、`same_identity_as`、`transforms`、`rendered_as`、`conflicts_with`、`supersedes` 和 `approved_for`。

约束分为：

- identity：entity/ticker/segment/product/metric/period/as-of 一致；
- numeric：value/unit/scale/currency/sign/rounding/formula/bridge 一致；
- semantic：wording strength、direction、uncertainty、scenario/context/gap 身份不越权；
- evidence：citation、authority、promotion、supplement、cannot-support 边界一致；
- version：所有 artifact projection 使用兼容 frozen heads，mixed-version 必须显式阻断或披露；
- visual：axis baseline/range、single/dual-axis mapping、label/unit、series/date alignment、time-window parity、sorting/order、color semantics、legend、truncation 和 footnote 不误导；
- disclosure：tenant/private/internal/client-safe/license/retention policy 一致；
- completeness：material counterevidence、typed gap、What-Would-Change 和 required appendix 未被格式压缩丢失。

Constraint result 固定为 pass、warning、block、not_applicable 和 unresolved_review；每个 failure 要有 affected nodes/edges、rule/policy version、recommended owner、repair route 和 old/new artifact usability。

### 12.8 Four-Layer Verification

Verifier 分四层：

1. `DeterministicVerifier`：ID/version、数字、单位、期间、公式、citation refs、chart/table bindings、file hash、permission/disclosure hard rules。
2. `SemanticVerifier`：claim wording 越权、机制漂移、重要反证/gap 遗漏、scenario/fact 混淆、翻译或摘要改变含义。
3. `VisualVerifier`：DOCX/PDF/PPTX/XLSX/HTML 的 overflow、截断、乱码、分页、图表轴/图例/脚注、移动/桌面 dashboard 可读性。
4. `HumanReviewer`：业务敏感性、客户口径、house view、最终 internal/client-safe/publish approval。

LLM verifier 只能提出 semantic classification/revision suggestion，不能 override deterministic hard fail。Visual pass 不代表内容正确；内容 pass 也不代表 artifact client-ready。Verifier 不得自行补源或重写 research truth。

### 12.9 Multi-Format Projection, Not Independent Generation

Memo、Word、PPT、Excel、PDF、dashboard 不得由多个 Writer 分别从原始 pack 独立生成。它们都从同一 CanonicalPresentationModel 和 SurfaceClaim set 投影：

- memo/Word 展开完整论证和引用；
- PPT 按 slide storyline、takeaway 和 speaker-note/appendix 分层；
- Excel 保存 exact tables、formula/numeric trace、source/as-of 和 review cells；
- dashboard 只显示 current state、thesis change、coverage/gap、trigger 和 drilldown；
- PDF/brief 按 audience policy 压缩，但不能丢 material boundary。

格式之间追求 semantic parity，不追求文字完全相同。每个 projection 保存 canonical refs、format transform、rounding/aggregation policy、omitted-content reason 和 renderer/template version。Dashboard 只能投影 durable events/SQL/artifact heads，不自行推断幽灵状态。

### 12.10 Artifact Revision / Approval / Release Lifecycle

Artifact production state 与 approval/release state 必须正交保存，不能用一条 overloaded lifecycle 同时表示“文件生成到哪一步”和“能否对外使用”。

Artifact production state：

```text
planned
 -> drafting
 -> canonicalized
 -> rendered
 -> verifying
 -> blocked / revision_requested / review_ready
 -> production_retired
```

Approval/release state：

```text
unapproved
 -> approved_internal
 -> approved_senior_review
 -> approved_client_safe
 -> released
 -> published
 -> stale_review_required
 -> superseded / withdrawn
```

- `released`：Release Gate 已对 exact artifact package 作出允许交付/分发的 durable decision，但不证明外部渠道已经收到；
- `published`：发送、上传、共享或外部展示已由 delivery event 确认；
- `stale_review_required`：依赖发生 material change，现有 approval/release 不再可继续沿用；
- `superseded`：存在批准的新版本替代旧版；
- `withdrawn`：因事实错误、权限、许可、隐私或合规原因显式撤回；已发布历史和 withdrawal reason 保留审计。

Artifact staleness、production state 和 approval/release state 是三个独立维度。例如 artifact 可以是 `rendered + artifact_partially_stale + approved_internal`，也可以是 `review_ready + artifact_current + unapproved`。

Artifact、presentation model、SurfaceClaim 和 review decision 均 immutable/versioned；修改生成新 version 和 supersedes edge。Approval 绑定 exact research/presentation/artifact/permission versions；material upstream change 自动使 approval stale。客户正式交付默认需要 human approval；内部草稿是否可自动 review-ready 由 tenant policy 决定。

ReleaseDecision 至少记录 release audience/channel、artifact refs/hash、input heads、verification bundle、open warnings/gaps、approver、permission snapshot、valid-from/as-of、supersession 和 revocation policy。发布失败不能删除已生成历史 artifact。

Release Gate 最低硬条件：

- 所有 material SurfaceClaim 有 active/compatible upstream binding；
- deterministic hard checks 通过，使用中的 numeric/citation/version bindings 可解析且兼容；
- client-safe/disclosure policy 通过；
- 当前 head 没有命中该 artifact MaterialityContract 的未处理 invalidation；
- NarrativeSurfaceContract 要求的 material gaps、risk 和 What-Would-Change panels 已保留；
- required HumanApproval 仍绑定当前 exact versions；
- `reviewed_artifact_hash == release_candidate_hash == delivered_artifact_hash`。

默认要求审核、release 和实际发送使用相同 binary hash。若文件容器时间戳等非内容 metadata 导致 binary hash 改变，必须由 versioned metadata-only policy 证明 canonical content digest、render inputs、renderer/template 和 visible output 未变；否则重新验证/审批。任何渲染后内容变化都产生新 ArtifactVersion，不能沿用旧 approval。

### 12.11 Workbench Five Review Surfaces

Workbench 至少提供：

1. `DecisionSurfaceMatrix`：chain/cell question、conclusion、status、confidence、evidence/counterevidence、gap、What-Would-Change、owner 和 version。
2. `ClaimProvenanceDrawer`：从正文、表格或图表点击到 SurfaceClaim、cell、evidence、numeric trace、parser、observation 和 source。
3. `ArtifactConsistencyPanel`：按 claim/metric/version 对比 memo/PPT/Excel/dashboard，展示 pass/warning/block 和 diff。
4. `RepairAndReviewQueue`：needs_source/parser/numeric/judgment/wording/layout/disclosure 分类、owner、priority、blocking state、attempt 和 resume refs。
5. `VersionReleaseTimeline`：head advance、writer/verifier/reviewer action、approval、publish、stale、supersede 和 forward impact。

Document grid、numeric trace drawer、source snapshot viewer、factor/social/conflict/What-Would-Change panels作为上述 surface 的 drilldown。UI 状态必须来自 durable projection；前端不得把缺失字段推断为 pass，也不能只显示当前版而隐藏历史 review/action。

### 12.12 Human Edit Classification and Truth Boundary

人工编辑先分类：

- presentation-language-only：修复病句、语序、标题或非实质压缩，不改变 canonical meaning；生成新 wording/artifact version 并走基础/visual verification。
- translation-or-semantic-paraphrase：跨语言翻译、摘要、同义重写或标题化表达；即使预期不改变 claim，也必须经过 SemanticVerifier 检查 strength、negation、uncertainty、scope 和 required qualifiers。
- claim-wording-material：实际改变强度、方向、范围、uncertainty、qualifier 或 disclosure；生成 SurfaceClaim patch，必须经过 semantic/deterministic verification，必要时回 Cell Adjudicator。
- research-truth：改变数字、evidence status、business mechanism、cell conclusion、confidence、gap 或 What-Would-Change；不能直接改 artifact，必须生成 DecisionCellPatch/RepairTicket 并回 Lead/Cell Adjudicator。
- source correction：新增/替换来源、parser/number 修正；回 Evidence/TECH_04 gate，不因 reviewer 输入自动 accepted。

所有 edit/comment/action append-only，记录 target/version、before/after diff、reason、actor、permission、classification 和 downstream invalidation。Workbench 可以提供编辑体验，但不能把“可编辑”实现成原地覆盖 source-of-truth。

### 12.13 Audience / Disclosure / What-Would-Change Integrity

Internal 与 client-safe 不是简单删字段。每个 SurfaceClaim/citation/artifact binding 必须有 audience、tenant、confidentiality、source visibility、license、quote policy 和 disclosure status。若关键 claim 只由不可外发 evidence 支撑，客户版必须删除、降级、改为不可验证边界或进入 human review，不能只隐藏 citation 后保留强结论。

What-Would-Change 在 Workpaper、memo、Word、PPT、dashboard 中保持独立 canonical section/panel，绑定 current judgment version、decisive variables、strengthen/weaken/overturn tests、attempts/observations、directional assessment、gaps、monitoring triggers 和 re-adjudication status。未 adjudicated scenario/trigger 不得进入主结论；格式压缩也不能把它变成免责声明或普通风险列表。

TECH_09 新增 `WhatWouldChangePanel` presentation object。它至少记录 panel/program/current-judgment version、trigger/change-condition、required evidence/metric、operator/comparator/threshold、current value 与 as-of、monitoring status、last checked、next check/refresh policy、source/numeric refs、responsible owner、gap、re-adjudication status 和 audience visibility。Memo 可展开机制，PPT 可压缩为关键 trigger，dashboard 显示 status/last checked，Excel 显示 threshold/current value/source；所有 projection 必须引用同一 program/trigger versions。

Translation、摘要和 client-safe rewrite 都必须保留 exact/proxy/scenario/gap、negation、conflict、confidence、period/unit 和 cannot-support。原始私有 CoT、internal scratchpad 和 unapproved reviewer discussion 不得进入交付物。

### 12.14 TECH_08 / TECH_06 / TECH_07 Runtime Interfaces

- TECH_08 handoff：`PresentationTask -> WriterResultEnvelope`，`VerificationTask -> VerificationResultEnvelope`。Task/Result 必须绑定 frozen research/presentation heads、target projections、audience/disclosure、allowed artifacts/tools、budget/stop condition 和 typed blockers；Writer completed 不等于 artifact approved/released。
- TECH_06 durable execution：持久化 `WriterWorkUnit`、`RenderWorkUnit`、`VerificationWorkUnit`、`HumanReviewWorkUnit` 和 `ReleaseTransaction`，以及 candidate/frozen/rendered/reviewed/released/published/stale/withdrawn events。TECH_09 定义业务状态语义，TECH_06 拥有事件、版本、事务、retry/resume/cancel 和 approval persistence。
- TECH_07 context：分别编译 `PresentationContextRequirement`、`VerificationContextRequirement` 和 `HumanReviewContextRequirement`。Writer 不读取 raw retrieval/private scratch；Verifier 读取 draft、SurfaceClaim、source/numeric boundary、artifact versions 和 forbidden claims；Human Reviewer 读取 client-safe summary 与授权 drilldown。

### 12.15 Evals, Fixtures and Current Boundary

新增 fixtures：

1. Frozen DecisionSurface -> CanonicalPresentationModel -> multi-format bindings parity。
2. SurfaceClaim claim-strength/period/unit/translation preservation。
3. Writer no-source / raw-row / unapproved-supplement negative fixture。
4. WriterBlocker typed routing 和 presentation-only partial revision。
5. Source correction -> forward invalidation -> artifact stale/review-required。
6. Memo/PPT/Excel/dashboard numeric/semantic/version/visual consistency。
7. Deterministic hard fail 不被 semantic verifier override。
8. Human edit presentation/claim/research/source classification 与正确 repair route。
9. Internal -> client-safe non-disclosable evidence downgrade/removal。
10. What-Would-Change cross-format separate-section integrity。
11. Approval exact-version binding、upstream material change 和 reapproval。
12. Workbench decision matrix/clickthrough/consistency/queue/timeline replay parity。
13. Partial/material stale assessment 与 dependency-scoped local revision。
14. Reviewed/released/delivered hash equality 和 metadata-only exception policy。
15. Released/published/stale/superseded/withdrawn state transition 与 withdrawal audit。
16. WhatWouldChangePanel threshold/current-value/last-checked/owner 跨格式 parity。

验收不只看“能导出文件”。必须评 client-ready、senior-review-ready、claim directness、citation clickthrough、numeric reproducibility、cross-artifact semantic parity、layout/readability、unsupported-claim rate、review edit distance、repair routing accuracy、approval/release integrity 和 workflow time saved。

当前项目已有 memo/workpaper/Workbench projection、claim/ref/source/gap verifier、artifact refs、部分 renderer 和 R55 framework，但尚未统一实现 CanonicalPresentationModel、SurfaceClaim/ClaimSurfaceMap、双向 invalidation、constraint graph、四层 verifier、五类 Workbench surface 或 exact-version release control。本节状态仅为 `documented / contract_draft`，不能据此宣称 client-ready、多格式一致性或正式发布链已完成。

## 13. 2026-07-11 Workpaper Projection / Audience-Scoped Presentation

Workbench 必须把 `WorkpaperPack` 作为任务协作当前态展示：section、DecisionSurface cells、evidence/gap、conflict、review comments、approval、deliverable plan 和 versions。`DecisionSurfacePack` 是可审判断投影；`FrozenDecisionSurfaceSnapshot` 是 writer admission 时的 exact research input；二者都不能替代完整 Workpaper event/review history。

跨格式一致性共享的是 `CanonicalClaimRegistry`、numeric/citation bindings 和 `PresentationBasis`，不要求 internal、client-safe、不同语言和不同模板使用完全相同的一份 prose/presentation tree。链路调整为：

```text
FrozenDecisionSurfaceSnapshot
 -> CanonicalClaimRegistry / PresentationBasis
 -> AudienceScopedCanonicalPresentationModel
 -> Memo / PPT / Word / Excel / PDF / Dashboard projections
```

Audience-scoped model 可以删除不具披露权限的内容、改变解释深度和组织方式，但不能改变 canonical claim identity、事实强度、数字、period/unit、conflict/gap 或 What-Would-Change 身份。不同 audience/language artifacts 仍通过 shared claim/binding graph 做一致性和 disclosure 检查。

## 14. 2026-07-12 Decision Attestation / Human-AI Accountability

根据 PRD 与 TECH_00，TECH_09 是 ReviewDecision、DecisionAttestation、SurfaceClaim、ArtifactProvenanceManifest 和 ReleaseRecord 的业务真相 writer；TECH_06 保存执行事件、ActorSnapshot、hash 和 transaction，TECH_03 建历史索引，TECH_10 评完整性。

### 14.1 DecisionAttestation

`DecisionAttestation` 绑定 exact target，不是宽泛“批准过”：

- case/cell/claim/evidence/numeric/workpaper/presentation/artifact refs 和 exact versions/hash；
- decision type：comment、request_repair、accept/reject、soft-judgment override、conditional approval、internal/client-safe approval、waiver、supersede、withdraw；
- ActorSnapshot、authority/delegation、workflow/OA ref；
- reason、conditions、scope、audience/channel、valid-from/expiry；
- permission/config snapshot、open warnings/gaps；
- supersedes/revokes/invalidated-by 和 signature/timestamp refs。

Evidence/Numeric hard fail 不能通过普通 attestation 变 accepted。受审 waiver 必须保留 hard-fail history、scope、expiry、accountable owner 和 release disclosure policy。

### 14.2 ArtifactProvenanceManifest

Manifest 至少绑定 ResearchCase、CanonicalPresentationModel、SurfaceClaim/number/citation versions、AI involvement mode、Agent/Model/Prompt/Skill refs、human edits、review/approval attestations、renderer/template、artifact/content digest、release/delivery event 和 supersession。

三层标记：

1. visible disclosure：AI-generated draft、AI-assisted、human-reviewed、compliance-approved、released，按 tenant/audience policy 展示；
2. embedded metadata：case/artifact version、manifest URI/hash、review/approval/release refs；
3. cryptographic attestation：对 exact artifact hash 与 manifest 做机构签名/时间戳，可借鉴 C2PA，但必须扩展 Cell/Claim/Evidence/Numeric/Approval 语义。

文本 watermark 或“AI 生成”标签不能替代 provenance manifest、exact hash 和责任链。

### 14.3 HumanAIAccountabilityGraph / Workbench

从 TECH_06 AccountabilityEvent 和 TECH_09 Attestation/Manifest 投影：

```text
Actor -> Prompt/Agent/Tool Action
 -> Cell/Claim/Evidence/Numeric Change
 -> Review/Override/Approval
 -> Artifact/Release/Delivery
```

Workbench 按 Cell/Claim 展示 created/requested/collected/calculated/proposed/modified/reviewed/approved/released by，AI proposal 与 human edit diff，before/after versions，受影响 artifacts 和 current accountable owner。普通语言润色与改变 claim strength/number/citation/assumption 的 material edit 必须分类不同。

### 14.4 OA workflow / release

OA callback 只能形成 candidate decision。TECH_06 校验 ActorSnapshot、delegation、workflow node、target exact version/hash 和 idempotency后，TECH_09 才创建 DecisionAttestation。Approval target 或 upstream material head 变化时 attestation stale；重新发送邮件或通知不能延续旧批准。

### 14.5 Privacy and responsibility boundary

Research provenance、Compliance audit、Runtime observability、Usage analytics 分别授权。Raw prompt/private reviewer discussion 只有在 policy 允许时进入 drilldown；客户 artifact 不得泄露 internal scratchpad。系统提供 accountability evidence，不自动裁定法律责任或用 usage 指标评价员工绩效。

### 14.6 Review assignment / collaboration semantics

TECH_09 拥有 `ReviewAssignmentVersion`、`CommentThreadVersion`、`MentionEvent` 和 `ReviewSLA` 的业务语义：target exact refs、review type、required role、assignee/delegation、due/escalation、blocking policy、allowed decisions、comment visibility、resolution/supersession 和 audience。Research/cell execution assignment 仍归 TECH_01。

TECH_06 负责 timer、notification、delivery receipt、retry 和 durable events；邮件/Teams/Slack/OA 只传递任务或候选 action，不成为 review/approval truth。Comment 不自动修改 Cell/Claim/Artifact；material comment 必须转成 repair、patch proposal 或 DecisionAttestation。

新增 fixtures：exact-version OA approval、delegation expiry、human edit classification、visible/metadata/signed manifest parity、upstream correction触发 attestation stale、withdrawal audit、raw prompt retention separation。

本节状态为 `documented / contract_draft`；不表示 OA、签名或责任图 runtime 已实现。

## 15. FIN 0.1.3 Current-Candidate Workbench Dogfood Boundary（2026-08-08）

FIN 0.1.2 的 Workbench/Report/Trace 页面证明了投影、exact-version review 和 lineage 形状，但截图中大量“证据方向支持／详见本地绑定事实”的通用判断原子也证明：页面可打开、Artifact 数量正确和 citation chip 存在，不能代表研究底稿或交付报告有实质内容。

FIN 0.1.3 S4 只接受 S3 最终 current candidate，不再用历史 fixture、minimum anchor 或手工拼装摘要作为产品验收输入。一次 dogfood 必须能在同一 Case 中完成：

1. 从 Research Objective、动态 DecisionSurface 和 source/search activity 进入 Evidence/Numeric；
2. 在 Workpaper 中看到公司专属 thesis、关键事实与推导、机制链、反方、gap、WWC 和对应 Evidence/Numeric lineage；
3. 对 material number、claim strength、citation 或 assumption 发起 repair，并观察受影响 Cell/Artifact 的 stale/rebuild 范围；
4. LeadReview、WriterAdmission、Report、Human Review 和 Trace 使用同一 exact Case/Artifact version；
5. qualified reviewer 独立记录内容分、审阅负担、需要重写比例和 acceptance/return 原因。

S4 可以修页面信息结构、交互、review burden、repair UX 和 audience projection；不得在 renderer 中补写模型没有形成的 thesis，或用本地超级拼装掩盖 S1/S3 缺口。当前页面薄内容归 S3 research outcome，页面如何让 reviewer 高效验证该内容才归 TECH_09/S4。
