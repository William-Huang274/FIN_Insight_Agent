# 160 P38 Point 01 M5 Recovery Lifecycle Control Plane

日期：2026-07-12

状态：`M5.2 deterministic temporary-store recovery control plane pass`

## 授权与范围

当前线程 user 直接授权继续 M5.2。实施仅覆盖 M5.2：retry、resume、read-only replay plan、fork lineage 与 dead-letter。它建立在 M5.1 temporary SQLite scheduler control plane 之上，不能扩展为真实 worker/service、checkpoint lifecycle 或任何业务运行时准入。

## 已实现

- `RecoveryLifecycleService`：从 canonical store 重建带 digest 的 replay plan；retry/resume 只可从 `retryable_failed` WorkUnit 继续，并绑定最新失败父 Attempt、expected state version 与 plan digest；
- exact checkpoint enforcement：resume/fork 必须提供 `<artifact_id>:vN`，在 transaction 内校验 tenant/project/case、artifact identity 和 producer Attempt；本轮不读取、创建或 compaction checkpoint 内容；
- append-only recovery data：Attempt 记录 recovery mode、parent Attempt、resume checkpoint ref、replay-plan digest；WorkUnit 记录 fork source 与 dead-letter metadata；
- fork：创建新的 pending WorkUnit，并把 checkpoint ref 写入 immutable input set；source WorkUnit 不被改写；
- dead-letter：仅 terminal failed WorkUnit 可关闭为 `dead_lettered`，原因和 source Attempt 进入 event/replay/read view；
- replay 和 queue/read views 知晓 recovery/dead-letter event/state，未知状态事件仍 fail-closed。

## 验证

- M5.2 contract tests 覆盖 retry immutable history、poison fail-closed + dead-letter、exact checkpoint resume、fork lineage、budget/max-attempt termination：`4 passed`；
- M5.1/M5.2 focused suite（包含 scheduler 回归与 fixture runners）：`12 passed`；
- `scripts/engineering/run_point01_m5_2_recovery_lifecycle_fixtures.py`：`pass`，resume checkpoint 为 `checkpoint-1:v1`、budget 后 retry 被阻止、dead-letter 可读、model/external call 均为 0；
- canonical WorkUnit/Attempt JSON schema bundle 已重新导出；M1 fixed-hash gate 随后通过，shared fast-contract regression 为 `142 passed`，compileall 与 PostgreSQL logical conformance 也通过。

## 边界、回滚与下一步

此 slice 不拥有 M5.3 checkpoint persistence/compaction，也没有启动 background worker、provider 或 external tool；Evidence/Writer/full-chain、业务 Case mutation 和 legacy TaskRun authority change 均未触及。停止该 slice 时不需要外部回滚：没有运行中进程或外部副作用；feature/runtime admission 仍保持原样。下一步只能是 M5.3 checkpoint/artifact versioning 的独立设计/授权和实现，不能把 M5.2 当作 M5 complete。
