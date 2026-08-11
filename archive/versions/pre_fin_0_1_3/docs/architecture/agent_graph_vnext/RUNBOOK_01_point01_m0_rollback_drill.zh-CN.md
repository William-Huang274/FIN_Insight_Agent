# RUNBOOK_01：Point 01 M0 Rollback Drill

日期：2026-07-12

状态：`deterministic_fixture_pass_20260712 / legacy_authority_preserved / no_runtime_cutover`

## 1. 目标

证明 canonical shadow lane 可在不破坏 legacy authority、不删除审计历史、不让 shadow material 泄漏到下游的情况下停止写入并恢复 legacy-only read path。

## 2. 前置条件

- feature flag 初始为 `off`；
- fixture DB 与 object-store 使用临时隔离目录；
- legacy fixture 有可验证的 TaskRun authority snapshot；
- 不调用模型、web、Evidence、Writer 或 full-chain。

## 3. 演练步骤

1. 验证 `off` 时 canonical mutation 被拒绝。
2. 对单一 fixture scope 启用 `shadow`，创建 Case binding、WorkUnit、Attempt 和 DecisionSurface shadow bundle。
3. 记录 DB integrity、event sequence、artifact digest、legacy authority snapshot。
4. 触发 kill switch，验证新的 canonical mutation fail closed。
5. 验证 read authority 回到 legacy，shadow artifact 不进入 forbidden consumers。
6. 验证既有 canonical events、actor snapshot、identity map 和 artifact metadata仍可审计与 replay。
7. 再次运行 projection replay，确认无外部调用且结果 digest 一致。

## 4. 通过条件

- legacy authority before/after 相同；
- kill switch 后 canonical write count 不增加；
- audit rows 未删除或覆盖；
- replay digest 一致；
- shadow leakage count 为 0；
- 无 paid/full-chain/external source invocation。

任何条件失败均阻断 M0 closeout，并记录 typed root-cause issue。Rollback 不等于删除 canonical 数据，也不把 shadow output 晋升为 legacy truth。

## 5. 2026-07-12 执行记录

`tests/contract/test_point01_runtime_facade.py::test_replay_is_deterministic_and_kill_switch_preserves_history` 已执行完整 deterministic fixture：legacy binding -> WorkUnit/Attempt -> shadow DecisionSurface bundle -> replay -> kill switch -> legacy authority/audit history复核。结果与相邻回归合计 `31 passed`。机器结果见 `configs/engineering_handoff/point01_m0_rollback_drill_result_v1_0.json`。
