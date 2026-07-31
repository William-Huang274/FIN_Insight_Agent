# FIN 0.1 第四层金融判断 / Context / Repair 执行草稿

日期：2026-07-19
状态：`discussion_draft / not_execution_authority / not_release_admission`
上位草稿：`FIN_0_1_LAYER_3_AGENTIC_SEARCH_EVIDENCE_EXECUTION_DRAFT_20260719.zh-CN.md`
主要 TECH owner：`TECH_05_domain_evidence_operator_decision_surface_projection.zh-CN.md`、`TECH_06_durable_harness_runtime_permission_state.zh-CN.md`、`TECH_07_context_engine_skills_compaction_governance.zh-CN.md`、`TECH_08_subagents_as_tools_handoff_contract.zh-CN.md`

## 1. 文档目的

> 2026-07-21 S3-T06 执行更新：同一 deterministic `Fin01ResearchRuntime` 已从 exact T02-T05 lineage 生成三份 fact/explanation/judgment 分层 `SpecialistJudgmentVersion`、一个含跨 Cell dependency/conflict/variant view 的 Lead synthesis、三类 earliest-owner `RepairTicket`、重复 failure fingerprint stop 和 stale/late output quarantine。Demand/Risk 没有把 Candidate/Graph 提权为事实，Value 只保留公司整体 Numeric 并拒绝产品/分部/增量/跨链归因。consumer 可完整重编译 pack；实际模型、网络、repair、canonical Judgment head write 均为 0。该结果证明 deterministic runtime/node-level 合同，不证明 Specialist/Lead 模型质量、T07 delivery、paid artifact 或 Human acceptance。

> 2026-07-19 S1-T04 执行更新：一个 NVDA“需求真实性与持续性” fixture-shadow Cell 已通过现有 LangGraph Specialist 与 Judgment aggregation 节点，产生共享同一 Run 的 `agent_fixture_judgment` 与 `agent_fixture_workpaper` immutable artifacts；Evidence、Numeric、Judgment、Workpaper 之间引用已在 commit 前绑定为 canonical `ArtifactVersionID`。判断保留持续性条件和 What-Would-Change，但全部为 deterministic fixture shape，不构成真实 Specialist 金融研究质量、跨三 Cell Lead synthesis 或 Human acceptance。

本草稿定义 FIN 0.1 如何把 claim-scoped Evidence、Numeric 和 Graph observation 转成有金融分析价值、边界清楚、可重评的专业 Judgment，并为 Context/Memory、repair、并发和版本失效提供产品级决策。本草稿不证明历史 Specialist 已进入当前 Runtime，不批准模型、网络、canonical Case mutation 或 release。

## 2. 当前事实基线

- TECH_05 已定义 `DomainCellJudgmentPack / JudgmentVersion`、confidence vector、cannot-infer、counterevidence、repair 和 Cell dependency 合同；
- 历史 Specialist/Lead/Workpaper 链具有部分运行资产，但与 FIN 0.1 Workbench 唯一 Runtime 断连；
- 当前 FIN 0.1 主链以 deterministic projection 生成 10-cell judgment/workpaper，不证明 Specialist Agent 实际消费 Evidence 并形成专业 Judgment；
- 当前 31 条本地结果仍是 Candidate，不是 D07 意义下的 accepted Evidence；
- 因此本层决策先冻结目标语义，再进入 one-cell runtime integration，不以旧 fixture 数量宣称完成。

## 3. `L4-D08`：Specialist Judgment Contract

`L4-D08-SpecialistJudgmentContract` 已冻结为 `structured_financial_judgment_with_bounded_narrative_and_lead_cross_cell_synthesis`。

Specialist 不交付无法审计的自由文本报告，也不退化为只填字段的 JSON 表单。主输出是带有结构化判断骨架和受约束专业叙事的 `SpecialistJudgmentVersion`；事实、解释和判断三层保持分离。

### 3.1 主输出

```text
SpecialistJudgmentVersion
  direct_answer
  claim_cards[]
  evidence_links[]
  numeric_facts[]
  mechanism_explanation
  counterevidence[]
  assumptions[]
  remaining_gaps[] / cannot_infer[]
  what_would_change[]
  confidence_vector / confidence_rationale
  recommended_next_action
```

- 事实层只能消费 D07 accepted Evidence 和 TECH_04 deterministic Numeric；
- 解释层允许 Specialist 描述业务机制，但必须绑定事实、假设、推理距离和替代解释；
- 判断层允许形成方向和强度，但必须显示反证、缺口、适用边界和 What-Would-Change；
- hypothesis 必须显式标注，不能通过叙事变成 accepted fact；
- `cannot_infer` 是正式输出，不是失败后被删掉的备注。

### 3.2 三-cell 专业语义

| Cell | 必须回答的判断链 |
| --- | --- |
| `demand_signal` | 需求信号 -> 公司特定性 -> 真实部署 -> 持续性驱动 -> 当前材料不能证明什么 |
| `revenue_capture` | 需求传导 -> 产品/分部归因 -> 收入 -> 毛利/营业利润/现金转化 -> 无法归因部分 |
| `thesis_counterevidence` | 最强反证 -> 影响机制 -> 是否已发生 -> 概率/影响边界 -> What-Would-Change |

三个 Cell 不能共享一个通用总结模板。SectorOperatorPack 可以提供方法、metric、proxy、forbidden substitution 和 risk checklist，但不包含当前 Case 事实。

### 3.3 Specialist / Lead 边界

Specialist 可以在 exact Cell/Branch 内形成专业 Judgment、申请 Evidence、提出 hypothesis、声明 cannot-infer，并提示跨 Cell 影响；不能改写其他 Cell、形成最终跨 Cell thesis、私自检索、修改 Evidence/Numeric head、决定 WriterAdmission 或把自由文本作为业务 head。

Lead 消费多个 exact SpecialistJudgmentVersion，负责跨 Cell 冲突、依赖和 synthesis，例如“需求真实但公司价值捕获不足”或“利润捕获成立但瓶颈不可持续”。Lead synthesis 不能只是三段 Specialist 文本拼接，也不能覆盖 D07/TECH_04 hard boundary。

### 3.4 Workpaper 与 Report 分工

Workpaper 展示形成 Judgment 的事实、机制、替代解释、反证、数字、gap 和 review trail；Report 展示经 Lead adjudication 后的决策叙事。二者共享 exact Claim/Judgment refs，但不是同一个 JSON 的不同排版，也不允许 Report 回到 raw Candidate 重新推理。

### 3.5 最小完成证明

至少证明：同一 Evidence 在不同 Cell 中按专业语义正确解释；Specialist 产生有内容的 Judgment 而非检索摘要；Numeric 冲突不能被文字覆盖；无法完成分部/利润归因时保留 cannot-infer；反证改变判断强度或状态；Lead 根据三个 Cell 形成新的跨 Cell synthesis；Workpaper 和 Report 保留同一 exact Claim/Judgment lineage。

## 4. `L4-D09`：Context And Memory Allocation

`L4-D09-ContextAndMemoryAllocation` 已冻结为 `role_scoped_reconstructable_context_with_registry_governed_memory`。

Context 是一次调用基于 exact business heads 编译的版本化视图；Memory 是跨 Run 的 candidate/prior。二者都不是 Evidence、Judgment 或 Case 的业务真相 writer。FIN 0.1 使用一个 ContextEngine public interface，为不同角色分别生成 `ContextRequirement -> ContextSnapshot -> ContextSelectionDecision[] -> ContextInjectionPlan -> exact input digest`。

### 4.1 Role Context

| Role | 默认可见 | 禁止默认注入 |
| --- | --- | --- |
| Lead | Case 目标、Cell/Branch 状态、Judgment heads、Gap/Repair、预算、能力目录、跨 Cell 依赖和 compact refs | 全部 raw rows、其他 Agent 私有草稿 |
| Specialist | exact Cell/Branch、accepted Evidence/Counterevidence、Numeric、相关 Skill/Sector pack、必要依赖 | 全 Case dump、无关 Cell、其他 Specialist private context |
| Evidence Operator | EvidenceRequest、entity/period/source policy、acceptance criteria | Lead 希望得到的结论、最终 Judgment、无关 thesis narrative |
| Writer | adjudicated Judgment/Claim、WWC、WriterBrief、allowed citation refs | raw Candidate、检索/补源工具、private reasoning |
| Verifier | draft、Claim/Evidence/Numeric/version boundary、forbidden claims 和授权 drilldown | 新检索权限、Evidence/Judgment 写权限 |
| Human Reviewer | client/internal-safe conclusion、关键依据、boundary、version/hash 和按权限 drilldown | 因 reviewer 身份默认开放全部 private/tenant source |

Evidence Operator 只接收要回答的问题和证据标准，避免把预期结论作为检索上下文造成确认偏误。Specialist 获得足够支持专业分析的 Cell-local material，而不是通过极端压缩牺牲研究深度。

### 4.2 Progressive Disclosure 与 Compaction

Context 先外置 raw artifact，再做 hard filter/去重/结构化压缩；只有仍超预算时才做带 preservation gate 的语义压缩。Case/entity/as-of、permission、accepted Evidence/Counterevidence、unit/period/scale、active Gap/Repair、cannot-infer、forbidden claims 和 Writer no-source boundary 不得因 compaction 丢失。

Agent 可以申请 `ContextExpansionRequest`，但只有 ContextEngine 能检查权限、预算、版本和必要性后生成新 plan。Workbench Inspect 展示“本次 Agent 看到了什么、为什么选择或排除”，不展示私有思维链。

### 4.3 Memory Boundary

- Semantic memory 只用于 entity/product/source 导航；
- Episodic/Negative memory 记录 route、parser、repair 的成功失败 prior；
- Judgment memory 是历史判断，必须检查 current Evidence 和 as-of；
- Procedural memory 进入 Skill/Playbook，不成为事实；
- Preference memory 只影响语言、格式和 workflow；
- AcceptedFact memory 只保存 exact Evidence ref/index，复用前重新检查 freshness、authority 和 owner status。

Agent/ContextEngine 只能提交 `MemoryWriteCandidate`；TECH_03 Memory Registry 拥有 active/stale/superseded/revoked/contradicted lifecycle。Reviewer correction 默认限定当前 entity/cell/report scope，跨 Case 泛化必须进入独立 rule/skill proposal 和 eval。

### 4.4 最小完成证明

至少证明：每个角色收到不同且可重建的 ContextPlan；Specialist 无无关 raw dump；Evidence Operator 不接收预期答案；Writer 无 source/tool 权限；stale/revoked memory 无法恢复成 current fact；compaction 保留反证、gap、negation、period/unit 和权限；follow-up 从 canonical heads 重建而不是依赖完整聊天；Inspect 可解释 selected/dropped refs。

## 5. `L4-D10`：Repair, Concurrency, Invalidation And Stop

`L4-D10-RepairConcurrencyInvalidationAndStop` 已冻结为 `owner_routed_targeted_repair_with_snapshot_isolated_parallelism_and_materiality_based_invalidation`。

Repair 修最早错误 owner；并发只扩大独立候选生产，不产生多个业务真相 writer；version advance 根据 dependency/materiality 选择性失效；停止由信息增量和 bounded policy 决定，不使用跨所有任务统一的“一次 repair”规则。

### 5.1 Repair Ownership

| Failure | Repair owner |
| --- | --- |
| route/retrieval/source missing | Evidence Tool Planner / Operator / SourceHunter |
| metadata/table/parser | Parser owner |
| entity/period/unit/formula | Numeric owner |
| promotion/boundary | Evidence Gate re-adjudication |
| mechanism/judgment | Domain Specialist / Cell Adjudicator |
| cross-cell conflict/scope proposal | Lead |
| wording/layout only | Writer/Renderer |
| unsupported Report claim | 返回最早 Judgment/Evidence owner，不由 Writer 伪装修复 |

`RepairTicket` 必须绑定 earliest faulty object、failure fingerprint、affected refs、new information/route hypothesis、expected output、owner、budget、resume checkpoint 和 stop condition。新 repair 必须改变输入、route、owner hypothesis 或可验证产物；相同失败指纹无新信息重复出现时停止。

### 5.2 Parallelism 与 Single Writer

允许相互独立的只读 EvidenceRequest、counter-search 和无 head 依赖冲突的 Specialist task 并行；同一个 Evidence promotion head、Cell Judgment head、Artifact/Review head 只允许一个 authoritative writer。FIN 0.1 初始 profile 最多三个并发只读 WorkUnit，具体数值是性能/成本配置，不是业务语义。

每个 WorkUnit 固定 Case/Cell/Evidence/Numeric/Judgment versions、ContextInjectionPlan、Agent/Skill/Profile、PermissionSnapshot 和 dependency digest。外部调用不可取消时，其迟到结果进入 quarantine，不自动进入 current head。

### 5.3 Version Impact 与选择性失效

accepted head 前进时生成 `PackChangeSet`。根据 read/dependency intersection、identity、period/unit、authority、claim strength、counterevidence、mechanism、confidence 和 consumer MaterialityContract，选择：

```text
continue
continue_then_validate
rebase_at_checkpoint
cancel_and_supersede
```

例如 Margin NumericFact 被纠正时，`revenue_capture Claim/Judgment -> Lead synthesis -> Report SurfaceClaim` 进入重评；无依赖交集的 demand Evidence 和 Graph path 不重跑。entity、scope、permission、required Evidence revoke 等硬变化可直接 cancel/supersede，模型不得 override。

### 5.4 Stop 与 Resume

Lead 在 Cell policy 满足、边际信息价值低、route exhausted、commercial/external gap、权限/预算耗尽、相同失败指纹重复、unresolved material conflict 需人工处理或 DecisionSurface 必须修订时停止。停止可以产生 bounded Judgment、typed/commercial gap 或 Human escalation，不要求每个 Cell 得到肯定答案。

Rebase/resume 从最近 safe checkpoint 创建新的 WorkUnit/ContextPlan version；旧 attempt 和输入保持不可变。不得用 broad full-chain rerun 替代 dependency-based repair。

### 5.5 最小完成证明

至少证明：独立 EvidenceRequest 可以并行；stale/late output 无法 commit；同质 citation 增量不触发全链重跑；Numeric correction 只失效依赖链；permission revoke 会 cancel/quarantine；unsupported claim 返回最早 owner；无新信息的重复 repair 停止；resume 使用新 ContextPlan 且旧 attempt 可审计；同一业务 head 不出现双 authoritative write。

## 6. 下一层接口

- `L5-D11-WriterVerifierRoleBoundary`：Writer/Verifier 哪些部分保留为 Agent、Writer no-source 如何形成有质量的 Report、Verifier 如何分层发现问题并路由修复；
- `L5-D12-ExecutionProfilesAndFailureTruth`：deterministic、agent shadow、bounded model 和 release candidate 如何共用同一 Runtime，并在失败、fallback、UI 和 artifact authority 上保持真实区分。
