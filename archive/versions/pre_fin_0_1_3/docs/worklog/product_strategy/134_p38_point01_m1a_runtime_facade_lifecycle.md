# P38 Point 01 M1.1 / M1.2 RuntimeFacade Lifecycle Fixture

日期：2026-07-12

状态：`m1_1_m1_2_fixture_proven / m1_3_m1_4_local_closeout_recorded_in_137 / milestone_m1_not_complete / legacy_authoritative`

## 目标

补齐 DecisionSurface compiler 运行前必需的 canonical execution lifecycle、只读恢复和 replay contracts；不实现 compiler、model adapter、comparison/review/cutover 或下游研究域。

2026-07-12 rebaseline：本 worklog 原先的 “M1A lifecycle completion” 只表示最小 lifecycle/read/replay fixture 关闭，现正式归档为 Point 01 M1.1/M1.2 `fixture_proven`。M1.3 retry/multi-attempt 尚未实现：`retryable=true` 的失败仍将 WorkUnit 置为 terminal failed，不能启动 Attempt N+1。M1 milestone 保持 open，只有 M1.5 closeout gate 可宣布完成。

2026-07-12 后续状态：上一段是本 worklog原始历史状态；M1.3/M1.4 已由 worklog 137 实现并完成 local deterministic calibration。M1.1/M1.2 本身仍只有 fixture proof，M1.5 machine gate 为 fail-closed，故本 worklog不能被解读为 M1 milestone complete。

## 实现

- `bind_legacy_task_run`：existing Case 的幂等 binding；normalized identity 只能有一个 active binding，cross-Case 冲突返回 typed `legacy_binding_conflict`。
- `complete_attempt`、`fail_attempt`、`cancel_work_unit`：终态写入 append-only Attempt/WorkUnit versions、event/outbox/history；failure 保留 type/retryability/terminal reason。
- `get_case_execution_view`、`get_work_unit_execution_view`：分别呈现 execution state、input currency、output usability、artifact status 与 attempt history；planning authority 仍为 `legacy`。
- `get_artifact_version`：读取 immutable envelope；可选 object payload digest 验证，绝不返回本机绝对路径。
- `replay_projection`：以 compact event payload 重建 Case/WorkUnit/Attempt/artifact projection；unknown state-mutating event fail closed；不调用模型、web、tool、API 或外部写操作。

为支撑 immutable version reads，SQLite store/protocol 增加 exact version 与 latest-list read methods；schema bundle 已随 Attempt failure fields 和 Event payload contract 同步更新。

## 验证

```text
python -m compileall -q src/sec_agent/canonical_runtime tests/contract
pass

python -m pytest -q -m fast_contract tests/contract tests/test_runtime_bridge_contracts.py tests/test_r53_r60_runtime_task_spine.py
35 passed

git diff --check
pass (only existing line-ending warning)
```

覆盖 standalone binding idempotency/conflict、complete/fail/cancel legal/illegal transition、terminal immutability、append-only history/event/outbox、artifact digest mismatch、legacy authority views、event replay parity/no external calls、unknown replay event fail-closed、kill-switch read/replay、runtime bridge 与 legacy spine regression。

## 边界与下一步

Legacy TaskRun 继续 authoritative；canonical DecisionSurface 仅 shadow，flag 默认 off。未运行 paid LLM、full-chain、model compiler、Evidence/Numeric/Judgment/Writer、Workbench UI、comparison/reviewer/cutover、PostgreSQL parity 或 migration。

下一步仅可进入 M1B：`DecisionSurfacePlanningService.validate_decision_surface_bundle`、`get_decision_surface`、CompilerInputContract、PackSelectionDecision、CompilerObservation/CompileTimeGap 与 deterministic compiler fixture。任何 model/node shadow run 仍需 deterministic gate 后的显式批准。
