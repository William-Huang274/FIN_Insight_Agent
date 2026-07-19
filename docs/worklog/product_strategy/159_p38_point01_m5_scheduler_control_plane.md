# 159 P38 Point 01 M5 Scheduler Control Plane

日期：2026-07-12

状态：`M5.0 design-only approval recorded / M5.1 deterministic temporary-store control plane pass`

## 授权与边界

当前线程 user 签发 `approve_m5_durable_harness_design_freeze_only`。该 receipt 已写入 `configs/engineering_handoff/point01_m5_human_ops_security_review_v1_0.json`，只允许 M5.1 的受控代码实现；它不授权启动 worker/queue service、provider、external tool、Evidence/Writer、full-chain、业务 Case mutation 或 legacy TaskRun authority change。

## 已实现

`DurableSchedulerService` 与 `RuntimeFacade` 共同实现：

- WorkUnit queue name / priority / enqueue time；
- temporary SQLite transaction 内 priority claim；
- scheduler-managed Attempt 的 worker identity、lease expiry、heartbeat 与 fencing token；
- expired lease reclaim：同一 Attempt 追加新版本、切换 owner/token，旧 token 不能再 mutation；
- queued 与 active WorkUnit cancellation 的 append-only propagation；
- read-only queue view，能显示 queued、leased、lease_expired、cancelled、terminal；
- scheduler events 进入 replay projection，未知 event 仍 fail-closed。

## 验证

- `tests/contract/test_point01_m5_durable_scheduler.py`、fixture runner、RuntimeFacade/store/M5.0 lint 的 focused suite：`38 passed`。
- `scripts/engineering/run_point01_m5_1_scheduler_fixtures.py`：`pass`；priority claim 命中 high-priority WorkUnit，heartbeat 后 reclaim token=`2`，cancel projection 与 replay 均通过。
- WorkUnit/Attempt schema 变更后已重新导出 checked-in JSON Schema bundle；M1 fixed-hash shared regression 为 `137 passed`，仍为 `M1_complete`。
- model/external call=0，worker_started=false。

## 下一步与回滚

M5.2 才拥有 retry/resume/replay/fork/dead-letter lifecycle；本轮不把 lease reclaim 夸大为完整 recovery policy。若需停止该 slice，保持 feature/runtime admission 不变即可：没有 background process、provider 调用、业务 Case mutation 或 legacy authority 写入需要撤销。
