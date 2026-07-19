# TECH_05：Domain Evidence Operator 与 Decision Surface Projection

日期：2026-07-09

状态：技术合同草案。本文把 Fundamental / Product / Graph / Market / Risk 等能力从人格化专家输出改成 decision-cell-oriented domain evidence operator。

## 1. 要解决的问题

P36 Node05-08 显示各领域能力分散存在，但没有投影成五链条 x 决策格：

- Fundamental rows 没自然变成利润质量 / business-line economics；
- ProductIntelligenceGraph 有大量资产，但 selector 不按五链条平衡；
- relationship graph 多是关系召回，缺 value-capture / risk transmission；
- market / ownership / capital feedback 没进入 price-in / crowding cells；
- risk prompt 强，但输入不是 risk-specific cell pack。

## 2. 设计原则

- 减少“人格化专家”，增加 domain evidence operator。
- Specialist 仍可做业务判断，但输入必须是 `DomainOperatorTask + CellEvidencePack`，不是 bounded row dump。
- 每个 operator 输出 `DomainCellJudgmentPack`，并必须带 `decision_surface_cell_id`。
- Graph / product / market 信号可以支持 bounded thesis driver，但不能冒充 exact revenue / order / share / real-time flow。

## 3. 核心 projection

| Projection | 输入 | 输出 |
| --- | --- | --- |
| `FundamentalDecisionCellPack` | exact rows、peer panel、working capital、derived metrics | revenue / margin / cash / balance sheet / operating leverage cells |
| `ProductIndustryDecisionSurfaceProjection` | ProductIntelligenceGraph、product specs、deployment、industry metrics | accelerator / server OEM / foundry-packaging / HBM / semicap cells |
| `GraphToDecisionCellProjection` | ProductRelationshipGraph、relationship_graph_lookup、research graph | customer/supplier/value-capture/risk-transmission edges |
| `MarketCapitalDecisionSurfaceProjection` | market snapshot、valuation、ownership、capital feedback | price-in / crowding / liquidity / valuation risk cells |
| `RiskCounterevidenceDecisionSurfaceProjection` | product gaps、market/capital rows、relationship conflicts、regulatory/source gaps | RiskMatrixPack / counter-thesis cells |
| `MethodToDomainOperatorProjection` | MethodMemory、WorkpaperExemplarMemory、research ruler、answer exemplars | operator rubric、required judgment moves、what-would-change template |
| `ResearchGraphToThesisMechanismProjection` | ResearchGraphPointer、ProductIntelligenceGraph、ProductRelationshipGraph、capital feedback graph | thesis mechanism path、evidence support refs、cannot-infer boundaries |

## 4. Domain Operator 输入 / 输出合同

`SpecialistCellPack` 作为输入和输出的旧式命名在本合同中被拆分；兼容层可以暂时读取旧字段，但新 runtime contract 使用以下对象：

- `DomainOperatorTask`：说明要判断什么、为什么重要、由谁负责、允许使用哪些 artifacts、禁止哪些 claim、预算和 stop condition。
- `CellEvidencePack`：只承载 accepted evidence、context-only signals、numeric traces、conflicts、gaps、authority / period / unit / freshness 和 cannot-support。
- `DomainCellJudgmentPack`：operator 的结构化业务判断输出，不包含未经 gate 的新事实。

`DomainCellJudgmentPack` 必备字段：

- `domain_judgment_pack_id`
- `role`
- `decision_surface_id`
- `cell_id`
- `chain_segment_id`
- `accepted_evidence_refs`
- `context_refs`
- `numeric_trace_refs`
- `risk_refs`
- `cannot_infer`
- `judgment_status`
- `cell_answer`
- `business_mechanism`
- `economic_materiality`
- `time_horizon`
- `alternative_explanations`
- `counterevidence_refs`
- `confidence_vector`
- `downstream_claim_strength`
- `writer_allowed_wording_boundary`
- `what_would_change_program_ref`
- `repair_requests`
- `forbidden_claims`

## 5. AI infrastructure 五链条 baseline

第一版必须覆盖：

- Accelerator / GPU demand and value capture；
- Server OEM revenue vs margin quality；
- Foundry / advanced packaging bottleneck；
- HBM / memory economics；
- Semicap lagged capex read-through；
- Market price-in / ownership / valuation risk；
- Risk / counterevidence matrix。

## 6. 与其他 TECH 的边界

- `TECH_01` 定义 cells 和 business role；
- `TECH_02-04` 提供 accepted evidence / numeric traces；
- `TECH_08` 定义 domain operator 作为 subagent/tool 的调用方式；
- `TECH_09` 让 Workbench 按 cell review domain output；
- `TECH_10` 评估 specialist 是否按 cell 产生判断，而不是泛化 memolet。

## 7. 第一批 fixture

1. Product / Industry selector chain-balanced fixture。
2. GraphToDecisionCellProjection fixture。
3. MarketCapitalDecisionSurfaceProjection fixture。
4. RiskMatrixPack fixture。
5. Fundamental peer / business-line economics fixture。
6. DomainCellJudgmentPack -> DecisionSurfacePack preservation fixture。
7. MethodMemory / WorkpaperExemplarMemory -> operator rubric fixture。
8. ResearchGraphPointer -> thesis mechanism projection fixture。

## 8. 验收标准

- 每个 domain output 都有 `decision_surface_cell_id`。
- 五链条 coverage 不能被单一 source family 挤占。
- `context_or_proxy`、`estimate_only`、`cannot_infer` 必须显式保留。
- Market/ownership/capital feedback 不得晋升为基本面 exact fact。
- Product/graph signal 不得晋升为 revenue / ASP / shipment / backlog exact claim。

## 9. 2026-07-10 研报方法 / 底稿 skill / 研究知识图谱边界

P33/P36 已经证明项目里存在研报方法、gold workpaper、prompt skills 和研究图谱资产，但它们不能停留在“背景知识”或“人格化专家提示词”。TECH_05 的职责是把这些资产编译成 domain evidence operator 的 cell-level 输出。

相关上游对象：

- `MethodMemory`：由 TECH_03 保存，来自 `financial_research_method_registry.jsonl`，例如 thesis path、product-to-financial bridge、three-statement peer panel、secondary-market capital feedback、customer-supplier readthrough。
- `WorkpaperExemplarMemory`：由 TECH_03 保存，来自 P33 humanmade gold case、research judgment ruler、answer exemplars、rubric / negative cases。
- `ResearchGraphPointer`：由 TECH_03 保存，指向 ResearchGraphStore、ProductIntelligenceGraph、ProductRelationshipGraph、capital feedback graph 的 graph nodes / edges / support rows。
- `SkillMemoryRef`：由 TECH_03 / TECH_07 保存，指向 Research Lead、Memo Writer、Fundamental、Product、Industry、Market、Risk 等 skill 版本。

TECH_05 的转换规则：

- 方法和底稿样例只能生成 operator rubric、required judgment moves、cell checklist、what-would-change 模板，不能生成事实。
- 研究图谱只能生成 mechanism path、candidate relationship、value-capture hypothesis、risk-transmission hypothesis，不能绕过 source authority / Evidence Gate。
- prompt skill 只能约束输出结构和判断深度，不能替代 accepted evidence。
- 每个 operator 输出仍必须绑定 `decision_surface_cell_id`，并引用 `accepted_evidence_refs`、`context_refs`、`numeric_trace_refs` 或明确 gap。

## 10. Domain Operator 应输出什么

每个 domain operator 不应只写 memolet，而应输出可聚合、可审计的 `DomainCellJudgmentPack`。

第一版要求：

- `FundamentalDecisionCellPack`：把 exact rows、peer panel、working capital、derived metrics 转成 revenue quality、margin bridge、cash conversion、balance-sheet risk、business-line economics 等 cells。
- `ProductIndustryDecisionSurfaceProjection`：把 product specs、architecture、deployment、customer adoption、industry operating metrics 和 WorkpaperExemplar rubric 转成 accelerator / server OEM / foundry-packaging / HBM / semicap cells。
- `GraphToDecisionCellProjection`：把 relationship graph 和 research graph 转成 customer/supplier/value-capture/risk-transmission paths，并保留 relationship confidence、direction、source boundary 和 cannot-infer。
- `MarketCapitalDecisionSurfaceProjection`：把 market snapshot、valuation、ownership、capital feedback 转成 price-in、crowding、liquidity、valuation premium、event-window reaction 和 capital access cells。
- `RiskCounterevidenceDecisionSurfaceProjection`：把 product gaps、market/capital rows、relationship conflicts、regulatory / policy / geo-risk / external signals 转成 risk matrix、counter-thesis、trigger、what-would-change。

特别注意外源新闻 / 政策 / 公开发言：

- TECH_03 的 `ExternalSignalCandidate` 进入 TECH_05 后，只能支持 catalyst、risk、policy exposure、counter-thesis、market narrative 或 source discovery。
- 如果外源信号来自官方公司/监管/政府渠道，可按 source authority 进入 company-authored context 或 official policy context。
- 如果只是媒体报道或转述，只能作为 `context_only` 或 `lead_only_needs_verification`，不能写成公司 exact fact、verified customer fact、revenue/order/share fact。
- 地缘政治和政策事件应优先走 official government / regulator source；新闻可帮助形成事件簇和叙事，但不能替代官方政策文本。

## 11. Method-to-Operator Fixture 要求

新增 fixture 应证明：

1. `thesis_path_first_research` 不只是写在 registry 里，而是让 Research Lead / domain operator 输出 thesis mechanism 和 required cells。
2. `product_to_financial_bridge` 能让 Product/Industry operator 在无 SKU revenue 时仍输出 bounded product judgment，同时明确不能推导 sales / margin / share。
3. `three_statement_peer_panel` 能让 Fundamental operator 输出 peer / business-line / working-capital cells，而不是孤立比率摘要。
4. `secondary_market_capital_feedback` 能让 Market/Capital operator 输出 price-in / crowding / funding-window cells，而不是只给价格表。
5. `customer_supplier_readthrough` 能让 Graph operator 输出 read-through path 和 cannot-infer，而不是把关系图谱写成收入事实。
6. P33 / P36 humanmade gold exemplars 能约束 answer depth 和 cell coverage，但不能把 exemplar 文本当成新 case 事实。

## 12. 2026-07-10 Quant Validation 到 Decision Surface 的投影

Research-to-Quant 结果不是新的事实源，也不能替代 commercial consensus、real-time flow、dealer gamma、borrow cost 或业务线未披露数据。TECH_05 只接收经过 R53/S9 PIT / leakage / validation gate 的 `FactorCard` 或 `QuantValidationResult`，并把它们投影为某个 decision cell 的量化支持、反证或诊断材料。

新增 projection：

| Projection | 输入 | 输出 |
| --- | --- | --- |
| `QuantValidationDecisionSurfaceProjection` | FactorCard、ValidationResult、RiskAttribution、FeatureSpec refs、PITDatasetSnapshot refs | `quant_support`、`quant_counterevidence`、`diagnostic_only`、coverage、regime、failure scenario、model-risk refs |

每条投影至少保留：

- `decision_surface_cell_id`
- `factor_card_id`
- `validation_status`
- `support_class`
- `economic_logic`
- `feature_refs`
- `source_refs`
- `pit_dataset_ref`
- `sample_coverage`
- `out_of_sample_status`
- `risk_exposures`
- `regime_tags`
- `failure_scenarios`
- `cannot_support`

允许进入 decision cell 的状态：

- `diagnostic_score`：可以作为定量背景，不得称为显著因子或 alpha。
- `research_factor_candidate`：有 PIT FeatureSpec / LabelSpec，但尚未获得样本外支持。
- `in_sample_supported`：只能说明样本内结果。
- `out_of_sample_supported`：可以作为 bounded quant corroboration / counterevidence。
- `paper_monitored_factor`：仍是内部研究监控，不等于投资建议。
- `retired_or_failed`：必须保留为反例和经验记忆。

第一批差异化 factor families 可包括 `FundamentalAccelerationFactor`、`ExpectationDivergenceFactor`、`GuidanceRevisionEventFactor`、`ProductDeploymentVelocityFactor`、`SupplyChainReadthroughFactor`、`CapitalPositioningFactor`、`MacroExposureRegimeFactor` 和 `DisclosureChangeFactor`。它们必须由 TECH_04 的 source-backed features、R53 的 PIT validation 和 TECH_09 的 provenance/review 共同约束；domain operator 不得自由生成分数或把 proxy 改名为缺失的商业字段。

## 13. 2026-07-10 Derivatives Market Signal Projection

新增 `DerivativesMarketSignalProjection`，把 TECH_03/04 的 bounded derivatives observations/metrics 投影到相关 decision cells，而不是生成独立交易观点。

输入：

- `FuturesCurveSnapshotPIT`
- `COTPositionPIT`
- `OptionMetricResult`
- `PublicSwapRegimePIT`
- `IssuerDerivativeCapitalContext`
- derivative metric/gap/lineage refs

输出：

- `macro_or_cost_regime`
- `expectation_or_event_uncertainty`
- `positioning_or_crowding_proxy`
- `tail_risk_signal`
- `funding_or_dilution_context`
- `equity_credit_divergence`
- `commercial_or_source_gap`

每条 cell projection 必须说明：instrument/underlying、observation/available time、source authority、metric identity、economic interpretation、supports、cannot_support、what-would-change 和 model/source risk。

默认由 Market/Capital、Industry 和 Risk operator 解释；不新增常驻“衍生品人格专家”。只有用户问题本身是复杂 options/volatility/cross-asset/hedging 研究时，才通过 TECH_08 激活 `DerivativesQuantOperator` subagent-as-tool。

衍生品信号不能证明基本面，只能支持 price-in、expectation、risk、cost transmission、funding 和 counterevidence。例：财报前 IV 高于 realized volatility 可说明事件不确定性较高，不能说明财报一定超预期。

## 14. 2026-07-10 External / Social Signal Decision Surface Projection

新增 `ExternalSocialSignalDecisionSurfaceProjection`。它消费 TECH_02 gate 后的 attributed statements、policy events、news/event clusters、social discourse samples、user-feedback themes 和 conflict records，只把它们投影为与当前 cell 有关的 bounded signal。

输出类型：

- `official_or_company_statement`
- `policy_intent_or_negotiation_signal`
- `product_announcement_or_roadmap_signal`
- `event_catalyst_or_market_narrative`
- `observed_platform_discourse`
- `user_feedback_theme`
- `counterevidence_or_claim_conflict`
- `identity_or_fact_verification_gap`

每条 projection 必须保留：speaker/account identity、speaker role、platform、canonical source、published/retrieved time、statement claim type、underlying fact status、sample methodology where applicable、conflict refs、supports、cannot-support 和 user-facing uncertainty wording。

解释规则：

- 政府官员在第一方账号发表的内容可作为政策意图、谈判立场或事件催化剂；政策是否已生效仍由正式命令、法规或监管文本确认。
- CEO 或公司官方账号发布产品信息可作为第一方 announcement；产品是否已交付、性能是否达到宣称、销量和财务贡献仍需产品文档、实测、客户/监管或财务证据。
- 产品负责人、工程负责人在回复区说明 bug、功能或 roadmap，可作为产品状态 / user-feedback repair lead；除非有公司正式材料或可观测 runtime 验证，否则不是公司承诺或稳定功能事实。
- 高赞评论可以说明“在已观察样本中存在这一主题并获得较高互动”，不能说明用户总体评价或市场共识。Domain operator 必须同时寻找反例、负面/正面双侧主题和 sampling bias。
- 当人物发言与 accepted fact 冲突时，不对人物做整体可信度人格判断。operator 应判断该句是事实、意图、预测、观点、修辞还是会影响市场的事件，并输出 `ClaimConflictRecord` 对应的 bounded conclusion。

Risk / Counterevidence operator 是 conflict projection 的默认 owner；Product/Industry、Market/Capital 或 Policy operator 按 cell 共同解释。Lead 决定冲突是否需要继续 repair 或在最终故事线中显式披露，但不能推翻 TECH_02 hard gate。

## 15. 2026-07-10 Domain Judgment Architecture 补强

### 15.1 Projection / Judgment / Adjudication 三层

TECH_05 内部固定拆成：

1. `DomainEvidenceProjection`：确定性选择、去重、分组、排序和 cell binding；不输出业务结论。
2. `DomainJudgmentOperator`：基于 `CellEvidencePack` 解释业务机制、替代解释、反证、缺口和 what-would-change；不改变 evidence identity。
3. `CellAdjudicator`：合并 primary / contributor / challenger proposals，执行 hard-boundary precheck 和语义裁决，形成 `AdjudicatedDecisionCell`。

### 15.2 Cell ownership

每个 cell 必须区分：

- `primary_operator`：对直接答案负责。
- `contributing_operators`：提供跨领域补充。
- `challenger_operator`：检查反证、替代解释、过度推断和 falsifier，默认 Risk / Counterevidence。
- `evidence_owner`：负责结构化取证，不一定是 primary operator。
- `repair_owner`：按 gap 类型路由给 Evidence、SourceHunter、Parser、Numeric、Graph 或 domain operator。

Risk 可以挑战但没有单独 veto 权；Evidence Gate 决定证据身份但不决定业务结论；Lead 控制跨 cell story 和 repair 优先级；Human Reviewer 通过 append-only action accept / reject / supersede。

### 15.3 Bounded agentic loop / durable resume

Domain operator 状态机：

```text
TASK_RECEIVED
 -> CELL_UNDERSTOOD
 -> EVIDENCE_INSPECTED
 -> CANDIDATE_JUDGMENT
 -> ALTERNATIVE_TESTED
 -> COUNTEREVIDENCE_CHECKED
 -> SUFFICIENCY_ASSESSED
 -> REPAIR_REQUESTED / BOUNDED_FINALIZED
```

证据充分时允许一次调用完成；证据不足时输出 `RepairTicket` 并 pause。新 `CellEvidencePack` 到达后从 checkpoint 恢复，不重跑全部 case。TECH_05 定义业务状态，TECH_06 负责 attempt persistence / checkpoint / replay。

### 15.4 Judgment status / confidence vector

固定 judgment statuses：`supported`、`bounded_supported`、`mixed`、`contradicted`、`insufficient_evidence`、`commercial_gap`、`not_applicable`。

`confidence_vector` 不使用模型随手生成的单一概率，至少拆为：`evidence_coverage`、`source_authority`、`numeric_sanity`、`inference_distance`、`cross_source_consistency`、`freshness`、`conflict_severity`、`proxy_dependence`。

### 15.5 CellDependencyEdge

新增 `CellDependencyEdge`：`from_cell_id`、`to_cell_id`、`edge_type`、`mechanism`、`direction_or_sign`、`expected_lag`、`conditions`、`evidence_refs`、`confidence_vector`。

允许的 edge types 包括 `supports`、`contradicts`、`prerequisite`、`value_capture_transmission`、`risk_transmission`、`price_in_divergence`、`monitoring_trigger`。上游 cell 被 reject / supersede / stale 时，依赖图必须生成下游 reopen candidates；graph edge 本身仍不是事实证据。

### 15.6 SectorOperatorPack / progressive disclosure

`SectorOperatorPack` 包含 sector cell templates、ownership defaults、required evidence slots、metric dictionary、source policies、accepted proxies、forbidden substitutions、domain methods、risk checklist、repair playbooks、default dependency edges 和 positive/negative exemplars；不包含当前 case 事实。

TECH_07 按 cell 渐进式加载相关 section，不把全部行业手册注入 operator。Case-specific 规则只有经过多 case calibration 才能晋升 sector pack 或 universal archetype。

### 15.7 Activation / duplication / budget

Operator activation reasons 固定为：`primary_owner_required`、`cross_domain_dependency`、`independent_challenge_required`、`repair_reassessment_required`、`user_explicitly_requested`、`optional_low_marginal_value`。最后一类默认不激活。

预算按 cell 分配 initial attempt、repair resume、challenger、context refs、tokens、elapsed time 和 stop condition。Contributor 不重复 primary 的完整分析；Risk 只消费 proposal 和关键 refs 做 challenge。AIE 记录 operator cost 是否转成新 judgment、conflict、repair ticket 或 adjudication change。

### 15.8 Cell Adjudicator boundary

确定性 precheck 负责拒绝 rejected evidence、越权 claim、numeric hard fail、gap 丢失和未回答 cell question。语义 adjudication 负责比较解释、判断分歧类型、选择 mechanism、确定 judgment status 和措辞边界。TECH_05 输出 `AdjudicatedDecisionCell`；TECH_01 Lead 负责跨 cell thesis 和 writer handoff；TECH_09 负责 reviewer override 与 provenance。

## 16. 2026-07-10 WhatWouldChangeProgram / Counterfactual Falsification Pass

`what_would_change` 升级为每个 material cell 的主动研究程序，而不是结尾免责声明。它是 Risk / Counterevidence 的升级能力，但不只寻找 downside：它同时寻找会加强、削弱或推翻判断的变量，由 primary operator 与 challenger 共同定义。

核心对象：

- `DecisionChangeCondition`：决定性变量、方向、阈值/区间、时间窗和预期影响。
- `CounterfactualTest`：要验证的正反假设、必要 evidence slots、forbidden substitutions、attempt budget 和 stop condition。
- `WhatWouldChangeProgram`：当前 cell/judgment version、causal rationale、tests、attempts、observations、directional assessment、gaps、re-adjudication 和 monitoring triggers。
- `MonitoringTrigger`：指标、阈值、数据源、频率、freshness、owner 和触发后的 reopen / review action。

运行过程：

```text
identify decisive variables
 -> explain causal relevance
 -> define strengthen / weaken / overturn branches
 -> compile EvidenceRequest / NumericProgramTrace
 -> execute bounded attempts
 -> classify exact / derived / directional proxy / scenario / gap
 -> re-adjudicate if material evidence changes
 -> publish separate What Would Change section
```

例如 `server_oem.margin_capture` 发现 segment margin expansion 与 cash conversion 是决定性变量后，可以依次检查：reported segment revenue / operating income、management margin commentary、product mix / BOM pass-through、inventory / receivables / operating cash flow、historical/peer patterns 和 customer/supplier read-through。结果必须保持身份：reported exact、deterministic derived、bounded directional inference、assumption-based scenario 或 unavailable/commercial gap。

如果只能找到收入增长而找不到 AI server-specific margin，operator 应展示查过的 source/metric、为何 proxy 不足、当前 directional assessment 为 mixed/unknown、哪些新披露会改变判断，而不是编造 segment margin。展示的是结构化审计推理摘要和 evidence trajectory，不是 raw CoT。

`What Would Change` 在 Workpaper、memo 和 dashboard 中始终作为独立 section / panel。其研究发现只有经新 cell version 和 Cell Adjudicator 后才能改变主结论；未完成 adjudication 的情景、预测和监控变量不能并入主结论。

## 17. 2026-07-11 Deterministic Valuation / Forecast / Scenario Engine

估值和 price-in 不能只由 Market Operator 用自然语言给出。新增 `ForecastAssumptionSet`、`PeerSetVersion`、`ScenarioDefinition`、`ForecastModelRun`、`ValuationModelRun`、`SensitivityTable` 和 `ValuationInterpretation`。

输入必须区分 reported fact、management guidance、licensed consensus、public proxy、user assumption 和 model assumption；每项带 source/as-of/period/currency/scope/override lineage。TECH_04 负责输入资格、公式和 NumericProgramTrace；确定性 engine 负责 DCF、multiple、bridge、scenario/sensitivity 等可复算程序；TECH_05 只解释业务机制、price-in 和 cell impact。没有合法 consensus 或商业数据时必须使用公开披露/用户假设的 bounded scenario，不能生成伪 consensus。

LLM 可以提出 scenario、peer inclusion/exclusion 和解释建议，但不能直接写入 accepted assumption 或覆盖 deterministic output。所有模型运行必须可复算，并允许 reviewer 修改 assumption 后生成新 version，而不是编辑旧结果。

## 18. 2026-07-12 Judgment Version / Delta / Longitudinal Contract

根据 TECH_00/01-04，TECH_05 是 DomainCellJudgment、WhatWouldChangeProgram、CellDependencyEdge 和 judgment supersession 的业务真相 writer。它消费 TECH_02 accepted/context/gap EvidenceRecord 和 TECH_04 NumericProgram refs，不得自行检索晋升或修改 numeric output。

### 18.1 JudgmentVersion

`JudgmentVersion` 至少包含 case/cell/version、question、direction/status、mechanism graph、evidence/counterevidence/numeric/gap refs、confidence vector、claim strength、assumptions、WWC refs、downstream implications、actor/adjudicator/event refs、as-of、supersedes 和 wording boundary。

Judgment status 固定区分 `supported / mixed / unsupported / unknown / bounded_scenario / human_override`。`human_override` 必须保留原 machine proposal、override reason、evidence/numeric hard boundaries 和 approval requirement，不能伪装成模型独立结论。

### 18.2 JudgmentDelta / supersession

新 evidence、numeric recompute、review correction、scope change 或 monitoring trigger 先生成 `JudgmentDeltaProposal`：

- changed inputs / old-new refs；
- direction/confidence/mechanism/claim-strength delta；
- affected dependent cells 和 SurfaceClaims；
- strengthen/weaken/overturn/unchanged classification；
- required re-adjudication/LeadReview/human review；
- old judgment continued-use policy。

只有 Cell Adjudicator 接受后才能创建新 JudgmentVersion 和 supersedes edge。新增材料“相关但未推翻”仍可能改变 confidence、机制、WWC 或下游利润捕获，因此需要 bounded semantic impact agent；deterministic dependency filter 先筛选范围，Agent 只提出 materiality suggestion，最终由 adjudicator/Lead 按权限裁决。

### 18.3 Reviewer correction memory

Reviewer 对机制、口径、判断强度或 counterevidence 的修改形成 structured `ReviewerJudgmentCorrection`，并提交 TECH_03 MemoryWriteCandidate。默认只对当前 entity/cell/report type 生效；跨 Case/sector 复用必须经过 rule/skill proposal、TECH_10 eval 和版本发布。

### 18.4 Monitoring / refresh

WWC trigger 命中后 TECH_11 只提交 observation/impact request。TECH_05 评估 affected judgment，TECH_01 决定 reopen/refresh scope，TECH_09 处理 artifact stale/reapproval。Monitoring worker 不得直接推进 Judgment head。

### 18.5 Fixtures

1. 新证据不改变方向但提高 confidence，产生新 JudgmentVersion 而非静默追加 citation。
2. 上游需求增强但利润捕获减弱，跨 cell dependency 保留相反方向。
3. Numeric recompute 改变 threshold 后 WWC 从 inactive 转 active，并触发 re-adjudication。
4. Reviewer override 可 PIT replay，后续 Case 只在适用 scope 内复用。

本节状态为 `documented / contract_draft`；不表示现有 specialist output 已迁移为 JudgmentVersion。
