# FIN 0.1 第六层：Release Scope / Case Proof / Evaluation 执行草稿

日期：2026-07-19
状态：`docs_only_discussion_draft`
适用范围：FIN 0.1 下一阶段 Agent 产品主线

> 2026-07-22 S3-T09 增量：transport-v3 exact-once live Run 在第二 Specialist 的 `s3_owner_grade_epistemic_status_statement_conflict` 终态失败。5 次 Provider 请求均正常 stop，但本地认知状态合同拒绝至少一张 `cannot_infer` Claim Card；三态 failed、0 Artifact、无 orphan、无 retry/fallback/rerun。由于没有六节点/九 Artifact，RG3/RG4/T09 继续 blocked；本次 subtype 不是 prior context-ref membership failure，故下一项是需单独授权的零调用结果/根因决策，不自动重跑、比较或 owner acceptance。

> 2026-07-22 S3-T09 增量：transport v3 字段级闭合 context authority 与 safe subtype telemetry 已完成零调用 fixture proof。完整生产 model view 下，Claim Card 只允许当前 Cell Candidate＋Graph exact subset 或 `[]`；五类越权/类型负例 earliest-stop，canonical 不保存 raw ref/digest/index。该结果改善合同与可审计性，但没有 live Artifact 或研究质量增量；RG3/RG4/T09 继续 blocked。下一项仅为需单独授权的 fresh v3 Agent proof decision，不能签发/执行；若同类 live failure 复现，必须转 provider-route disposition。

> 2026-07-22 S3-T09 增量：零调用审计把 transport-v2 authority failure 定位为“直接模型越权＋项目 field-local closed-set conveyance/fixture/telemetry gap”，不是 DeepSeek-only 结论。选定 transport v3 修复，但尚未实现或 live-proven；六逻辑节点/九 Artifact、paired comparison 和 owner acceptance 仍缺，RG3/RG4/T09 继续 blocked。未来明确闭合集合下同类失败若复现，必须转 provider-route disposition，不能继续 prompt 微调。

> 2026-07-22 S3-T09 增量：segmented transport v2 的 fresh exact admission 已唯一消费。第一 Cell 完整通过，第二 Cell claim-card 在 context-authority membership gate fail-closed；三态 failed、0 Artifact、5 calls、0 retry/fallback/rerun、无 orphan。六逻辑节点/九 Artifact、paired comparison 与 owner acceptance 仍未证明，因此 RG3/RG4 与 T09 继续 blocked；下一项仅为需单独授权的零调用 context-authority failure 根因决策，不能自动修复、重跑或接受。

## 1. 本层目标

本层把 D02-D12 的 Agent、Evidence、Judgment、Writer 和 Runtime 决策收束为可发布产品语义。范围可以窄，但入选的用户任务必须从 Workbench Case 到 exact Human Review 完整贯通；工程完整性、研究质量和产品价值不得合并成一个可相互抵消的总分。

## 2. `L6-D13`：Release Scope And Case Proof

`L6-D13-ReleaseScopeAndCaseProof` 暂按用户确认冻结为：

```text
narrow_complete_vertical_release_with_three_case_transfer_proof
```

### 2.1 FIN 0.1 完整产品链

FIN 0.1 的 release claim 是以下 exact 纵向链，而不是 Point 数量、页面数量、合同数量或仓库中存在的历史 Agent 类：

```text
Workbench Case
  -> Lead plan and bounded DecisionSurface overlay
  -> Agent / Skill / Tool / Graph runtime consumption
  -> Agentic Search / Candidate / Evidence promotion
  -> Numeric / financial judgment / counterevidence
  -> targeted repair / Lead synthesis
  -> Writer no-source / layered verification
  -> Workpaper / Report / Trace
  -> exact Human Review
```

FIN 0.1 只承诺三个 active Agent cells：

1. 需求真实性与持续性；
2. 价值与利润捕获；
3. 瓶颈、反证与 What-Would-Change。

现有 10-cell deterministic P36 预览可继续作为兼容、方法和 UI 参考，但不能替代三个 active Agent cells 的 exact 运行证明，也不作为本版 Agent release depth。

### 2.2 三个 Case

| Case | 研究位置 | 必须证明 |
| --- | --- | --- |
| `NVDA` | accelerator / anchor | 需求转化、收入利润捕获、供应瓶颈、反证和跨 Cell synthesis |
| `DELL` | server OEM / transfer | 订单到收入、低毛利、营运资本与现金转化，不能复用 accelerator 结论模板 |
| `MU` | HBM / transfer | 供给、定价、客户集中和半导体周期，必须保留周期性反证 |

TSMC、ASML 等可以作为 Graph/Evidence counterpart；本版不把它们扩成第四、第五个完整 Case。SaaS/Bank 只保留结构泄漏回归，不计为产品研究质量 Case。

### 2.3 Case 成熟度

- 三个 Case 均需达到 `R2_calibrated_research_output`；
- NVDA anchor 至少一个 exact artifact 需达到 `R3_reviewer_accepted`；
- R2/R3 证据必须来自 `bounded_agent_internal` 或冻结的 `release_candidate`；
- deterministic fallback、fixture、shadow 或 supervisor 手工补源不得冒充 Agent Case proof；
- 若没有符合角色要求的 senior reviewer，只能记录 owner/self review 和 R2，不得自称 R3。

### 2.4 FeatureScope 重基线原则

现有 F01-F15 不删除，但必须按本版窄深度重新解释：

- `release_critical`：F01-F13 与 F15，仅限三-cell、三-Case、internal-alpha 深度；
- `demo_support_not_release_blocking`：F14 same-Case explanation，仅回答 exact artifact 的 why/gap/WWC，不自动发起新研究；
- `deferred`：10-20 active Agent cells、任意用户编排、广泛模型/plugin marketplace、全行业 Case、长期监控、企业多租户、生产运维。

界面不得暴露尚未实现的 release-critical 控件；被延后的能力应隐藏或明确标为 unavailable，不以空壳页面满足 FeatureScope。

### 2.5 FIN 0.2 边界

FIN 0.2 继续定义为 Earnings Review Alpha：在复用同一 Runtime、Evidence、Numeric、Writer、Review 和 UI 主线的基础上，增加财务、分部、指引和变化解释。FIN 0.1 与 FIN 0.2 可以连续开发或一起对外展示，但必须分别冻结 candidate、分别通过 Gate、分别打 tag，不得互相借用完成状态。

## 3. `L6-D14`：Evaluation, Human Review And Release Gate

`L6-D14-EvaluationHumanReviewAndReleaseGate` 暂按用户确认冻结为：

```text
hard_integrity_floor_plus_case_level_research_quality_and_human_value
```

### 3.1 五层评测

1. **Hard integrity**：权限、exact Case/Run/version、引用、numeric、unit/period、no-source、无静默 fallback；
2. **Agent behavior**：Lead 动态决策，Agent/Skill/Tool/Graph 实际 selected/invoked/completed/failed，repair/stop 合理性；
3. **Research quality**：回答直接性、证据权威性、数字桥接、机制深度、反证、边界、What-Would-Change、跨 Cell synthesis；
4. **Delivery quality**：Workpaper 可复核性、Report 主次与可读性、citation drilldown、视觉完整性；
5. **Product value**：Human 任务时间、修改量、review burden、信任、是否愿意继续使用，以及受限成本/延迟。

### 3.2 不可平均的硬失败

虚假引用或错误 Evidence promotion、material numeric error、Case/Run/artifact/review 错配、静默 deterministic substitution、Writer 越权取源/补事实、权限/秘密/数据边界突破，任一发生即阻断当前 candidate，不能用其他高分抵消。

### 3.3 Human Review

- `owner_product_review`：产品使用者评价任务是否可理解、可操作、有用；
- `qualified_senior_review`：具备相应投研经验的 reviewer 对 exact Case/Run/Report 做专业验收；
- review 必须绑定 artifact digest、profile、input/as-of、duration、confidence、finding、required repair 和最终 decision；
- 机器 verifier pass、owner self-review 和 shadow review 均不自动等于 R3。

### 3.4 Baseline

每个 release Case 至少与明确标记的 `deterministic_fallback` 做盲法或半盲法比较，证明 Agent 在研究判断、反证、解释或交付价值上产生实质增量，同时不降低完整性。外部 WorkBuddy/公开报告可作为人工参考质量尺，但没有授权、可重现输入和合法保存边界时，不进入机器 Gate。

### 3.5 FIN 0.1 Release Gates

| Gate | FIN 0.1 关闭条件 |
| --- | --- |
| `RG1_vertical_path` | 三个 Case 的 Workbench-to-Agent-to-artifact exact 纵向链，以及既有 package entry-to-leaf identity debt 关闭 |
| `RG2_evidence_numeric_integrity` | 三个 candidate 无硬完整性失败，material evidence/numeric/claim lineage 完整 |
| `RG3_research_outcome` | 三个 Case 达到 R2，NVDA 至少一个 exact R3 |
| `RG4_review_product_value` | owner task baseline 与 qualified senior review 形成可审计价值证据，Agent 相对 fallback 有实质增益 |
| `RG5_release_rollback` | candidate/profile/digest 冻结，失败真实性、known gaps 和 rollback 通过 |

只有 release owner 对同一 exact candidate 重跑 RG1-RG5 后，才能做 FIN 0.1 release/block decision。通过仍不等于 production admission。

### 3.6 成本与评测停止规则

前三个 bounded Case 用于测量实际 calls、tokens、cost、latency、accepted evidence yield 和 Human review time；在质量 Gate 通过前不以武断低预算掩盖输出不足。完成校准后再冻结 candidate 上限。不得新增与 release claim、已复现失败或用户价值无关的指标、gate family 或大规模测试矩阵。

## 4. 本层不授权事项

本文件不授权模型、provider、network、paid data、真实业务 Case mutation、qualified senior attestation、release candidate run、RG1 operational run、production cutover 或发布。当前 release 仍为 blocked，production readiness 仍为 not admitted。

2026-07-22 当前主线：S3-T09 transport-v3 fresh proof 的 exact identity/input/budget/nonreuse/first-error stop/provider-route disposition 合同已零调用冻结并原样签发，admission 仍 unconsumed/execution_not_started，完整 live owner-grade Artifact 为 0。下一项仅为需单独授权且先满足 retry-zero/exact-state preflight 的 exact-once live execution；这不改变 RG2-RG5、T09/T10、release 或 production 的 blocked 状态。
