# FIN 0.1 下一阶段产品主线执行草稿

日期：2026-07-19
状态：`discussion_draft / not_execution_authority / not_release_admission`
适用 Release：`REL-PROD-001 / FIN 0.1 Internal Alpha`
主题：`Product Mainline / Fin01ResearchRuntime integration boundary`

## 1. 文档目的

本草稿把 FIN 0.1 下一阶段的五项产品主线完成条件转成可执行、可核验的工程计划，避免后续再次出现以下偏差：

- 页面、fixture 或独立 runner 已完成，但当前产品入口没有消费真实能力；
- Workbench、Agent、Skill、Tool、Graph、Writer 和 Human Review 各自存在，却不属于同一个 Run；
- deterministic fallback 在 UI 中看起来像真实 Agent 研究结果；
- Point owner 局部通过，但 release vertical 没有端到端消费者；
- 为修复局部审计问题继续增加 gate/package family，而没有修复产品主链。

本草稿不替代 PRD、TECH 或现有 ReleaseContract。讨论确认后，才可把结论回写到现有 execution backlog、FeatureScope、ReleaseContract 和 Point 02-07 vertical overlay。

## 2. 权威输入与当前边界

本草稿以以下文档和机器合同为输入：

- `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`；
- `docs/product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`；
- `docs/architecture/agent_graph_vnext/TECH_00_agentic_research_technical_index.zh-CN.md`；
- `docs/architecture/agent_graph_vnext/TECH_00A_prd_tech_runtime_product_surface_coverage_matrix.zh-CN.md`；
- `docs/architecture/repository/RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md`；
- `docs/architecture/repository/RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md`；
- `configs/releases/fin_ia_0_1_release_contract_v1_2.json`；
- `configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_1.json`；
- `configs/releases/fin_ia_0_1_code_mainline_manifest_v1_0.json`；
- `docs/product/FIN_0_1_STAGE_REVIEW_20260719.zh-CN.md`；
- `docs/architecture/repository/FIN_0_1_CODE_MAINLINE_ARCHIVE_AND_DISCONNECTION_AUDIT_20260719.zh-CN.md`。

当前权限边界保持不变：

```yaml
release_admission: blocked
production_readiness: not_admitted
legacy_global_authority: retained
paid_model_authority: not_granted_by_this_draft
network_authority: not_granted_by_this_draft
commercial_data_spend: forbidden_without_separate_approval
real_business_case_mutation: forbidden
production_cutover: forbidden
```

## 3. 当前实现基线

当前 FIN 0.1 已有一条可检查的内部确定性产品纵向：

```text
Workbench
  -> Case
  -> 10-cell DecisionSurface
  -> 31 local candidates
  -> 3 exact facts / 2 derived margins
  -> deterministic judgment / repair / Workpaper
  -> fixture LeadReview
  -> deterministic no-source Writer
  -> Report / Trace / Human Baseline surface
```

当前不能宣称的能力：

- Workbench 尚未通过统一 `Fin01ResearchRuntime` 消费历史 Multi-Agent；
- Skill Registry、Agentic Tool Planner、Graph Research 和 ReAct 未进入当前产品主路径；
- standalone DeepSeek runner 尚未写回 canonical Case；
- actual model/provider/network call 为 0；
- exact Human Senior Review session 为 0；
- RG1、RG3、RG4 和 P07.5 尚未通过。

## 4. 下一阶段产品主线

下一阶段只允许形成一条产品执行主线：

```text
Workbench Case
  -> typed API/application service
  -> Fin01ResearchRuntime
  -> ExecutionProfile
       - orchestration_mode
       - model_profile
       - skill_profile
       - tool_profile
       - data_graph_profile
       - authority_budget_profile
  -> ResearchRun
  -> versioned ArtifactManifest
  -> structured EventTrace
  -> Workpaper / Report / Human Review projections
```

`Fin01ResearchRuntime` 是稳定产品边界，不是把旧引擎原样包住的兼容外壳。其内部允许逐步重构或替换 historical Multi-Agent、Skill、Tool、Graph、Writer 和 provider 实现，但 Workbench 不得再直接依赖任何独立 runner 或第二套 planning/synthesis 主线。

## 5. 五项产品主线完成 Gate

这五项是现有 `RG1/RG3/RG4/P07.5` 的产品主线 acceptance criteria，不新增独立 release gate family。

### PM-G1：Workbench 发起 canonical internal Case

产品要求：

- analyst 可以从 Workbench 创建、打开、恢复一个 internal Research Case；
- Case 使用 canonical ID、version、actor 和 tenancy boundary；
- 本阶段的“真实 Case”指真实进入当前 canonical application/runtime 的内部 anchor Case，不等于真实客户业务 Case；
- 创建和运行不能绕到独立脚本、临时 SQLite 或未登记 artifact 目录。

当前状态：`partial`。

当前已有 Workbench Case create/list/open/restore，但研究执行仍有 deterministic local service 和 standalone runner 旁路。

通过证据：

- 浏览器 create -> API -> Case store -> reopen vertical；
- exact Case identity 在 Run、Artifact、Trace 中保持不变；
- restart/reopen 后状态一致；
- unauthorized actor、stale version 和 unsupported mode fail closed。

### PM-G2：Case 只通过唯一 Fin01ResearchRuntime 运行

产品要求：

- Workbench/application service 只能调用一个 ResearchRuntime protocol；
- deterministic fallback、historical Multi-Agent 和 bounded provider execution 都实现同一 protocol；
- 不允许第二套 Case runner、Writer runner 或独立产品 artifact 主线；
- runtime mode 切换不能改变 canonical Case/Run/Artifact identity 规则。

当前状态：`not_implemented`。

通过证据：

- repository import/route audit 证明产品入口只有一个 runtime owner；
- deterministic compatibility run 通过统一入口且结果不退化；
- historical engine shadow run 通过同一入口；
- standalone DeepSeek runner 被吸收为 provider/runtime profile，或明确退出产品主线。

### PM-G3：Agent、Skill、Tool、Graph 使用情况可追踪

产品要求：

- 每次运行冻结 exact ExecutionProfile；
- EventTrace 记录已选择的 agent/capability、skill、tool、data route、graph operation、model stage、预算和 stop reason；
- 记录结构化 decision/action summary，不保存或展示模型私有 chain-of-thought；
- failed route、fallback、repair ownership 和未满足 gap 必须 typed；
- UI 和 JSON export 使用同一 trace source。

当前状态：`partial / current_product_not_agent_integrated`。

当前 deterministic Activity/Trace 已存在，但不能证明历史 Agent、Skill、Tool、Graph 被当前产品消费。

通过证据：

- 三个 P36 高价值 cells 的 fixture/shadow trace；
- 每个 cell 能追到 capability/skill/tool/data/graph profile；
- bounded retry、fallback、repair 和 stop 均有事件；
- trace 与最终 Judgment/Artifact 引用闭合。

### PM-G4：Workpaper、Report、Trace、Human Review 属于同一 exact Run

产品要求：

- Workpaper、LeadReview、WriterAdmission、Report、Trace、ReviewAction 共享 exact Case/Run identity；
- 每个 artifact 有 version、content digest、parent refs 和 supersession 状态；
- Human Review 必须绑定 exact artifact version/digest；
- return/repair 后产生新版本，不覆盖旧版本；
- canonical review 不得继续只存在于独立 Human Baseline SQLite。

当前状态：`partial`。

当前 fixture Workpaper/Deliverable/Trace 已有 exact identity，Human Baseline 支持 digest attestation，但尚未进入同一个 canonical Run，且 exact human session 为 0。

通过证据：

- Case -> Run -> Workpaper -> Report -> ReviewAction 双向 lineage；
- restart 后 exact version/digest 可恢复；
- stale review 被拒绝；
- return/repair/supersede 不删除历史 artifact；
-一次真实 analyst submit 和一次 exact Senior Review 记录。

### PM-G5：UI 不混淆 fallback 与真实 Agent 结果

产品要求：

- Case、Workpaper 和 Report 页明确显示运行模式；
- 至少区分 `deterministic_fallback`、`agent_fixture_shadow`、`bounded_model_run`；
- 显示 model/provider call count、skill/tool/graph usage summary 和 unresolved gaps；
- 没有模型 Lead synthesis 时，不得把 deterministic first-judgment projection 命名为完整核心结论；
- fixture/shadow/internal result 不得展示为 released/production result。

当前状态：`not_closed`。

当前页面已经可用，但 deterministic report 仍可能在视觉上被理解为完整 Agent 研究成果。

通过证据：

- 三种 mode 的 browser acceptance screenshots；
- fallback 模式明确的产品文案与受限操作；
- model/skill/tool/graph summary 来自 exact Run，不是前端推断；
- mode、digest、call counts 和 artifact refs 在 UI/API 一致。

## 6. 执行顺序

### PM-EP0：Runtime boundary 与历史组件裁决

- 冻结 `Fin01ResearchRuntime` protocol、ExecutionProfile、ResearchRun、ArtifactManifest、EventTrace；
- 对 historical Multi-Agent、Agent Registry、Skill Registry、Tool Controller、Graph、Writer、DeepSeek runner 做 `retain/refactor/absorb/retire` 裁决；
- 建立 characterization tests；
- 不运行网络、provider 或 paid model。

完成后解锁：`PM-EP1`。

### PM-EP1：Workbench -> Runtime -> deterministic compatibility

- Workbench/application service 改为只调用统一 Runtime；
- deterministic chain 作为明确 fallback profile 迁入；
- 保持现有 Case/10-cell/local preview 可用；
- 关闭直接调用 local research service 的产品旁路。

完成后关闭：`PM-G1`，部分关闭 `PM-G2/PM-G5`。

### PM-EP2：Agent Core 与结构化 trace

- 在统一 Runtime 内接入经过重构的 Research Lead、Capability/Skill Registry 和调度状态；
- 先完成一个 cell，再扩为三个高价值 cells；
- 接入 Tool/Graph profile 和 structured EventTrace；
- 详细 Agent Core 设计由下一层讨论冻结。

完成后关闭：`PM-G2/PM-G3` 的 fixture/shadow 范围。

### PM-EP3：Artifact lineage 与 canonical Human Review

- 统一 Workpaper/LeadReview/Writer/Report/Trace identity；
- 将 Human Baseline 的可复用交互和 attestation 能力接入 canonical ReviewAction；
- 保留旧记录只读迁移/导出边界；
- 完成 analyst submit 与 Senior Review 产品路径。

完成后关闭：`PM-G4`。

### PM-EP4：Truth-in-presentation 与候选版本

- UI 显示 exact runtime mode 和 capability usage；
- deterministic fallback 不再伪装成完整 Agent synthesis；
- 三-cell Agentic Research 与其余 bounded fallback 在同一 10-cell Case 中明确标识；
- 执行 browser acceptance、RG1/RG3/RG4 所需证据和 P07.5 候选判断。

完成后关闭：`PM-G5`，并进入现有 Release gate，而不是自动发布。

## 7. 四周产品列车中的位置

```text
Week 1: PM-EP0 + PM-EP1
Week 2-3: PM-EP2 Agent Core refactor and product integration
Week 4: PM-EP3 + PM-EP4 + bounded real run/human review/release decision
```

时间固定，安全和证据底线固定，范围可降级：

- 三-cell Agent 主链、exact identity 或 evidence safety 失败：不得发布 Internal Alpha；
- paid model 未授权或 exact Human Review 未完成：可保留 `Local Preview`，不得写 `Internal Alpha released`；
- 第四个以上 Agentic cell、更多 provider、商业数据、复杂 graph traversal：进入下一版本；
- production PKI/SLO/多租户企业 hardening：不阻断本次 Internal Alpha，进入 release/production backlog。

## 8. 测试与验收最小集合

每个 EP 只增加当前产品主链所需测试：

1. protocol/schema contract；
2. Workbench typed client -> API -> application -> Runtime integration；
3. exact Case/Run/Artifact/Trace identity；
4. deterministic compatibility；
5. Agent fixture/shadow three-cell vertical；
6. mode truth-in-presentation browser acceptance；
7. stale/unauthorized/wrong-profile fail-closed；
8. restart/reopen/review supersession；
9. separately authorized bounded model run；
10. exact human Senior Review。

不为未进入当前 release 的 provider、数据源、Agent 角色或极端输入扩张测试矩阵。

## 9. 草稿完成条件

本草稿只有在以下讨论完成后才能升级为 accepted execution overlay：

- 第二层：Agent Core、编排和 Skill 改造范围；
- 第三层：Agentic Search、RAG、SQL 和 Graph 主链；
- 第四层：Numeric、Judgment、Repair 和 Workpaper；
- 第五层：Writer、Workbench 和 Human Review；
- 第六层：RG1/RG3/RG4/P07.5 与发布标签。

在上述讨论完成前，不修改现有 release authority，不自动开始实现。

第二层详细草稿：`FIN_0_1_LAYER_2_AGENT_CORE_EXECUTION_DRAFT_20260719.zh-CN.md`。该草稿已记录 Agent Core、编排、Skill 的资产裁决、统一 Runtime 对象、三-cell 迁移顺序和完成 Gate，状态仍为 `discussion_draft`。
