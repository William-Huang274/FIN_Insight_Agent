# 163 P38 Point 01 M5 Budget / Stop Control

日期：2026-07-12

状态：`M5.5 deterministic temporary-store budget fixture pass`

## 范围

本轮在当前线程 user 继续 M5 的授权下实施 M5.5。预算 unit 是 deterministic control-plane token-unit、tool-call 和 time-second reservation，不代表 paid model token 或真实 provider/tool consumption。

## 已实现

- `BudgetPolicy` / `BudgetReservationRequest`：case、WorkUnit、Attempt 三层 quota；
- `BudgetControlService.reserve()`：protected checkpoint write 之前先 reserve，按三层 token/tool/time 限制 fail-closed；
- refund：按 reservation identity 追溯，不能超过剩余额度；
- fallback：没有独立预算池，走相同剩余 limit，因此不能 overrun；
- typed stop：超限产出 `budget_exhausted`，`apply_terminal_stop()` 复用 `fail_attempt`，把 Attempt/WorkUnit 置 terminal，M5.2 retry 无法继续；
- deterministic ledger/SLO view：计数 reservation、consume、refund、stop，provider/tool execution 均为 0。

## 验证

- contract tests 覆盖 reserve-before-checkpoint、refund trace、fallback 的 token/tool/time overrun、typed terminal stop 与 retry 拒绝；
- M5.1-M5.5 focused suite：`39 passed`；
- `scripts/engineering/run_point01_m5_5_budget_stop_fixtures.py`：`pass`，checkpoint 仅在 reserve 后创建、fallback blocked、refund=1、terminal stop 后 retry blocked；
- M5.1-M5.5 fixture 与 `scripts/engineering/run_point01_m5_design_lint.py` 均为 `pass`；
- 新预算合同模型已进入 schema exporter；M1 fixed-hash closeout 已重跑为 `163 passed`，compileall、PostgreSQL logical conformance、rollback/recovery drill 与人工 reviewer approval 均通过。

## 边界

不运行 paid model/provider/external tool，不启动 worker/service，不把 token-unit 误称为真实 token/cost；ledger/SLO 不是 M5.8 durable metric/alert pipeline。下一项 M5.6 为 durable HITL/approval invalidation，M5 仍不能 closeout。
