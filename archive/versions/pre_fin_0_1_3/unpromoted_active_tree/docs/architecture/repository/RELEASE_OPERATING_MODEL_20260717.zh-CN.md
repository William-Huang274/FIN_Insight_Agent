# FinSight Release Operating Model

日期：2026-07-17
状态：`accepted_execution_governance / not_runtime_implementation`

## 1. 作用与边界

本文把 PRD、TECH_00/10 和 Point execution 连接成同一发布控制模型。它不新增 TECH owner，也不替代 TECH_01-11 的业务合同。它规定：一个版本如何立项、由哪些 Point 消费、哪些 gate 能阻断、哪些问题进入 backlog，以及如何在固定节奏内关闭版本。

```text
PRD user job / product slice
  -> ReleaseContract
  -> ReleaseSlice / PointExecutionPlan
  -> TECH owner contracts
  -> implementation + adapters
  -> test profiles / EvalRun
  -> ReleaseGateDecision
  -> ReleaseEvidenceManifest
  -> channel publish or rollback
```

## 2. 稳定发布对象

| 对象 | Owner | 作用 |
| --- | --- | --- |
| `ProductReleaseIntent` | PRD/Product | 用户、工作流、产品 claim 和目标通道 |
| `ReleaseContract` | TECH_10 quality semantics；TECH_06 persistence | 冻结版本范围、L/R 目标、风险、预算、依赖和 rollback |
| `ReleaseSlice` | consuming Point + TECH owners | 一个可验证纵向增量 |
| `ReleaseGatePolicy` | TECH_10 | 最多五个 release-blocking gate 和阈值 |
| `DeferredBacklogItem` | 对应 TECH owner | 不阻断当前版本但必须追踪的债务 |
| `ReleaseEvidenceManifest` | TECH_10 refs；TECH_06/09 提供执行和 artifact refs | 汇总测试、Case、review、hash、known gaps 和 rollback 证据 |
| `ReleaseGateDecision` | TECH_10 | `passed/conditional_pass/blocked/rollback_required` |
| `ArtifactReleaseDecision` | TECH_09 | 某个 exact artifact 是否 internal/client-safe/published |

Runtime release 和 artifact release 继续分离。某个 runtime candidate 通过不表示某份报告可发布；某份报告被 reviewer 接受也不表示整个 runtime 可扩大通道。

## 3. 四轴状态模型

每个 ReleaseContract 必须同时写入：

```yaml
release_channel: dev_snapshot | foundation_alpha | internal_alpha | calibration_beta | enterprise_pilot | production
target_product_maturity: L0 | L1 | L2 | L3 | L4
target_case_outcomes:
  anchor_case: R0 | R1 | R2 | R3 | R4
production_readiness: not_admitted | pilot_admitted | production_admitted
```

每项 capability 另按 TECH_00 maturity lifecycle 记录。禁止创建一个笼统 `complete=true` 覆盖四个状态轴。

## 4. ReleaseContract 必填字段

```yaml
release_id:
version:
release_channel:
target_user:
target_job:
prd_slices:
anchor_case:
regression_cases:
target_product_maturity:
target_case_outcomes:
primary_delivery_workstreams:
required_tech_owners:
consuming_points:
canonical_objects:
frontend_delivery_contract:
detailed_design_ref:
detailed_execution_backlog_ref:
material_claim_policy:
hard_blockers:
known_deferred_gaps:
rollback_target:
test_profiles:
time_budget:
cost_budget:
production_readiness:
legacy_authority_status:
```

Point execution point 没有 `consuming_release_id` 时，不得默认进入当前迭代；只能是 backlog、exploration 或 future foundation work。

若 ReleaseContract 声明 required product surfaces，`frontend_delivery_contract` 必须同时冻结现有/目标 stack、route/surface、用户动作、API 边界、UI 状态、E2E gate 和明确 deferred 的视觉/设备范围。仅有 backend/API/schema/fixture 不得通过面向用户工作流的 `RG1_vertical_path`。

当一个版本横跨三个以上产品 surfaces 或两个以上 TECH owner 时，概设之后必须有详细设计和机器可读 backlog。详细设计至少覆盖页面/交互、read model、command/API、state/event、permission、persistence、error/next action、代码边界、execution point、四阶段验收、测试与 rollback。缺少这些内容时只能标记 `concept_design`，不得进入 implementation admission。

## 5. 四周执行状态机

```text
proposed
 -> contract_frozen
 -> vertical_path_running
 -> quality_hardening
 -> dogfood_active
 -> release_candidate_frozen
 -> released | conditional_released | blocked | rolled_back
```

状态转换规则：

- `contract_frozen` 后新增第二用户工作流或新 canonical cutover，必须拆分 release；
- 第 3 周只修 hard blocker、已复现的高价值根因和 release regression；
- 第 4 周不接受新功能；
- 版本冻结后发生 code/config/prompt/data/policy 变化必须生成新 candidate digest；
- release evidence 只能引用 exact candidate、Case、artifact 和 evaluator versions。

## 6. Gate 数量与优先级

每个产品版本最多五个 release-blocking gates：

| Gate | 含义 |
| --- | --- |
| `RG1_vertical_path` | 指定用户工作从输入到目标 surface 可完成 |
| `RG2_evidence_numeric_integrity` | Evidence promotion、material number、source/supplement 边界通过 |
| `RG3_research_outcome` | Anchor Case 达到目标 R level |
| `RG4_review_product_value` | reviewer 可审、可追责，工作流价值达到目标通道 |
| `RG5_release_rollback` | exact candidate、known gaps、rollback、release note 完整 |

底层可以有更多 contract/test checks，但不得把每个检查提升成新的产品 closeout gate。

Zero-tolerance hard blockers：权限/秘密/数据破坏、false evidence promotion、material numeric corruption、Writer 越权补源、material provenance 丢失、双 authoritative write、核心链不可运行且无 rollback。

其他问题按 `current_release_blocker / next_release_committed / operational_backlog / exploration` 分类。

## 7. Repair 和 Stop Rule

同一 release blocker 最多允许两轮 bounded repair。第二轮后必须由 release owner 裁决：

1. 会破坏当前版本研究正确性或安全边界：重设计并继续阻断；
2. 有 typed stop、人工复核或 feature flag 可安全隔离：延后到下一版本；
3. 只影响 enterprise production：进入 Enterprise Readiness backlog；
4. 没有当前或下一版本 consumer：停止实施。

除非新证据证明存在数据破坏、真实权限绕过或核心纵向路径无法运行，不得在同一执行点继续创建第三轮以上的治理包。发现新问题时先判断是否属于同一根因；同根因合并处理，不新增 gate 名称。

## 8. 测试 Profile

| Profile | 触发 | 内容 | 能证明 |
| --- | --- | --- | --- |
| `fast` | 每次提交 | schema、pure function、lint、核心 typed stop | 开发回归 |
| `component` | 合并前/每周 | store/API/adapter/subgraph integration | 组件合同消费 |
| `operational` | 明确批准 | resume/replay/permission/live bounded tool/rollback | 指定运行环境资格 |
| `release` | 版本冻结 | Anchor/regression cases、human review、artifact、rollback | 目标通道准入 |

Internal Alpha 不重复执行完整 enterprise release profile。Enterprise Pilot 才要求真实多用户、SSO/retention、长期 worker、SLA、incident 和正式 security qualification。

## 9. 容量与变更预算

主列车采用 50/20/15/10/5 的产品/证据数值/基础控制/eval/清理基准。每个 ReleaseContract 还要冻结：

- 一个 primary workflow；
- 一个 Anchor Case + 两个 regression cases；
- 最多三个 primary delivery workstreams；每个 workstream 可以消费多个 TECH owner 合同，但不得创建平行 source of truth；
- 最多一个 authority cutover；
- 最多五个 blocking gates；
- 一个 rollback target；
- 明确 token、model、tool、network 和人工 reviewer budget。

预算超出时优先减少范围和 artifact，而不是降低 Evidence/Numeric hard gate。

## 10. Point 与 Release 的关系

Point 是工程执行容器，不是产品版本。一个 Point 可以：

- 被一个 ReleaseContract 消费；
- 为多个未来版本提供基础，但当前只关闭声明范围；
- 以 `foundation_alpha` 完成而不获得 production admission；
- 把未被当前版本消费的 execution points 转交后续 Point。

每个 Point 必须使用 `POINT_EXECUTION_PLAN_TEMPLATE.zh-CN.md`，并在最终 closeout 中报告：目标 release、目标 L/R、实际成熟度、deferred backlog、rollback 和下一 consumer。只有最终 Point closeout gate 可宣布该 Point 在声明 scope 内完成。

## 11. Git 与发布证据

每次 release candidate 必须有：

- exact Git commit 或明确 dirty/staged digest manifest；
- machine-readable ReleaseContract；
- test profile 结果；
- Anchor/regression Case refs；
- capability maturity delta；
- known-gap/deferred backlog；
- rollback target 和命令/步骤；
- release note，明确未运行 paid/full-chain/production 的部分。

历史 superseded package 保留审计引用，但不能继续作为 active routing input。每个对象只能有一个 current release head。

## 12. 当前应用

- Point 01 消费方：`REL-FND-001 / Foundation 0.1`；目标是平台 L1 Foundation Alpha。
- Point 01 收口后首个产品消费方：`REL-PROD-001 / FIN 0.1 Internal Alpha`。
- `REL-PROD-001` 的完整执行计划见 `RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md`。
- 生产准入、真实客户数据、商业数据购买和 broad full-chain 不因本文自动授权。
