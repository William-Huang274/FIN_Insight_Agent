# P38 Point 01 M1.3/M1.4 Retry, Concurrency and Closeout Gate

日期：2026-07-12

状态：`m1_0_m1_4_full_implemented_calibrated / m1_5_reviewer_approved / m1_complete / legacy_authoritative`

## 目标

按 Point 01 第 26.2 节补齐 M1.1 store conformance、M1.2 recovery、M1.3 retry/multi-attempt 与 M1.4 concurrency/transaction conformance，并以 M1.5 machine gate 审计整个 M1 的真实状态；不把局部 contract pass 误记为 M1 complete。

## 实现

- `WorkUnit` 新增 bounded retry policy、retryable/poison failure taxonomy 与 immutable input-head；`Attempt` 记录 input head、lease owner 和 UTC lease expiry。
- `retryable_failed` 是显式非终态：只有 `retry:bounded` policy 中允许的 transient failure，且尚有 max-attempt/retry-budget，才能启动同一 WorkUnit 的 Attempt N+1；permanent/poison/exhausted failure 均为 terminal failed。
- `start_attempt` 强制严格的下一个 attempt number、bounded lease 与 CAS；旧 Attempt 继续 append-only。
- commit/complete/fail 均检查 WorkUnit/Attempt CAS、lease owner/expiry 与 input-head；artifact object 可以先写入但没有通过 SQL transaction 时不会发布 artifact metadata，作为可回收 orphan。
- SQLite lock/busy 被投射为 typed `transaction_conflict`；Case view 单列 retry-pending WorkUnit。
- `recover_case_execution` 在 SQLite 重开后校验 `PRAGMA integrity_check`、event/outbox 双向完整性、artifact digest、无外部调用 replay 与 legacy authority；recovery 后可继续 retry Attempt。
- SQLite adapter 为 case-bound records 增加 Case scope trigger，并校验 Attempt->WorkUnit、Artifact->Attempt、Cell->Contract、Slot/Gap->Cell 的 parent/version/scope 关系。
- 新增 `point01_m1_closeout_gate_manifest_v1_0.json` 和 runner，固定代码/配置/计划文档 SHA-256，并输出 closeout result。

## 验证

```text
python -m pytest -q -m fast_contract tests/contract/test_point01_runtime_facade.py tests/contract/test_point01_sqlite_store.py tests/contract/test_point01_canonical_models.py
27 passed

python scripts/engineering/run_point01_m1_closeout_gate.py
machine checks: initial closeout 55 passed; M2.0-M2.4 replay was 71 passed after 16 added contract tests; M2.5-M2.7 replay was 82 passed after 11 more; latest fixed-hash replay is 95 passed after M2.2/M2.8/M2.9/M2.10 added 13 more contract tests to the same directory; compileall + ephemeral PostgreSQL conformance sample pass
M1.5 result: pass / M1_complete (after recorded human reviewer approval)
```

M1.2 覆盖 legacy bridge restart/recovery、integrity/outbox/replay/authority and resumed retry；M1.3 覆盖 transient/permanent/poison、Attempt N+1 immutable history、retry budget/max attempts；M1.4 覆盖 concurrent winner/loser、SQLite lock timeout、stale input head、lease expiry、orphan object and bounded eight-WorkUnit load。M4 新增 14 个 fast-contract tests 后，M1 fixed-hash replay 已再次更新为 `123 passed`；这只扩展回归覆盖，不改变 M1 acceptance scope。

## M1.5 结论与后续

审计结果：`data/manifests/point01_m1_closeout_gate_result_v1_0.json`。M1.3/M1.4 已是 `full_implemented / calibrated_local_fixture`；M1.1 PostgreSQL logical conformance、M1 rollback/recovery drill 和人工 reviewer approval 均已记录，重跑 fixed-hash M1.5 后 `gate_status=pass`、`milestone_status=M1_complete`。初始 closeout suite 为 55 passed；M2.0-M2.4 后为 71 passed；M2.5-M2.7 后为 82 passed；当前结果为 95 passed，因为 runner 的同一 contract directory 还包含 M2.2/M2.8/M2.9/M2.10 新增的 13 个 tests，并不改变 M1 acceptance 条件。

- M1.1 PostgreSQL logical conformance sample 已在 disposable `postgres:16-alpine` container 中通过；
- M1 rollback/recovery drill 已执行并记录；
- 当前窗口的人类 reviewer 已明确批准，approval record 已写入 reviewer type、timestamp 和 audit note；Codex 未自行审批。

下一工程动作仅可进入 M2.0 compiler/pack/quality 子项设计冻结。未运行 paid model、model compiler、full-chain、Evidence、Writer、cutover 或 migration；legacy TaskRun 仍 authoritative，DecisionSurface 仍 shadow-only。
