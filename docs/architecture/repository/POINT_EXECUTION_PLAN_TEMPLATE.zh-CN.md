# Point Execution Plan Template

状态：`canonical_template_v1 / 2026-07-17`

所有新 Point 或现有 Point 的下一 major revision 应使用本模板。删除不适用段落时必须写明原因，不能静默省略。

## 0. Identity

```yaml
point_id:
title:
status: draft | approved | in_progress | blocked | scope_complete | superseded
consuming_release_id:
release_channel:
target_product_maturity:
target_case_outcome_contribution:
primary_tech_owners:
upstream_points:
downstream_consumers:
production_readiness: not_admitted
legacy_authority_status:
```

## 1. User / Release Contribution

- 本 Point 对目标用户工作流提供什么可观察增量；
- 如果不做，本版本哪个纵向步骤无法完成；
- 哪些产出只属于平台基础，不能作为产品能力宣传；
- 明确不在本 Point 范围内的 PRD/TECH 能力。

## 2. Architecture Target

- 目标对象、owner、producer、consumer；
- store/API/event/artifact/permission boundary；
- source of truth、current head、supersession；
- legacy adapter、cutover、rollback 和 archive 条件；
- 完整目标形态与本次最小纵向实现的差异。

## 3. Execution Points

每个 `Mx.y` 必须分四个证据阶段：

| Stage | 含义 | 禁止冒充 |
| --- | --- | --- |
| `skeleton` | 类型、接口、空路径、fail-closed 边界 | runtime capability |
| `fixture` | deterministic fixture 和负例 | 真实工具/模型/业务 Case |
| `full` | 声明范围内真实依赖图执行 | calibrated quality / release |
| `calibrated` | Anchor/regression/human review 达标 | production readiness |

只有最终 milestone closeout gate 可以宣布 `Mx complete`；中间阶段必须写成 `Mx.y_<stage>_pass`。

每个 execution point 使用：

```yaml
execution_point_id:
consuming_release_gate:
input_contract:
output_contract:
owner:
dependencies:
permission_and_budget:
skeleton_acceptance:
fixture_acceptance:
full_acceptance:
calibrated_acceptance:
typed_stops:
rollback:
deferred_items:
```

## 4. Test Profiles

- `fast`：每次提交；
- `component`：合并前；
- `operational`：需独立批准；
- `release`：只由 consuming release 执行。

明确列出各 profile 的入口、fixture/Case、外部调用权限、写入范围、预期计数和输出 manifest。

## 5. Release Blocking Gates

本 Point 最多贡献五个产品 release-blocking gates。其他检查只能作为 gate 内部 evidence 或 component regression。

每个 blocker 必须有：严重度、用户/研究影响、最早 owned root cause、修复 owner、最多两轮 repair、stop/defer 条件和目标 release。

## 6. Deferred Backlog

按以下类型记录：

- `next_release_committed`；
- `enterprise_readiness`；
- `operational_regression_backlog`；
- `exploration`；
- `commercial_or_external_boundary`。

每项必须注明不阻断当前版本的理由和未来触发条件。

## 7. Closeout Gate

最终 closeout 必须输出：

```yaml
point_scope_status:
consuming_release_id:
target_vs_actual_maturity:
runtime_proof:
case_outcome_contribution:
production_readiness:
legacy_authority_status:
hard_blockers_open:
deferred_backlog_refs:
rollback_verified:
release_evidence_refs:
next_consumer:
```

若当前 Point 只达到 Foundation Alpha，应明确写 `production_readiness=not_admitted`。不得用 scoped/fixture/synthetic pass 宣称 production complete。
