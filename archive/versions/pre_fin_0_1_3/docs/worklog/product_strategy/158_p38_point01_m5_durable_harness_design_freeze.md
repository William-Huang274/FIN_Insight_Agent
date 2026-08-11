# 158 P38 Point 01 M5 Durable Harness Design Freeze

日期：2026-07-12

状态：`design_lint_pass / human_ops_security_design_approved_only`

## 已冻结的责任边界

M5.0 将 M5.1-M5.9 分为独立 owner：scheduler/lease、recovery lifecycle、checkpoint/artifact、capability security、budget/SLO、durable HITL、parallel context、observability/ops 和 aggregate closeout。每个 child 有 inputs、outputs、dependency、non-goals 与可验证 acceptance；M5.9 必须依赖 M5.1-M5.8 全部完成。

`scripts/engineering/run_point01_m5_design_lint.py` 通过，静态检查 owner 唯一、依赖可解析且无环、M5.9 覆盖所有子项、capability/tenant/budget/approval/snapshot/trace 边界，以及显式拒绝 provider/Evidence/Writer/full-chain 和业务 Case mutation。测试额外确认：不完整 M5.9 依赖、缺失 M5.4 tenant cross-read denial 都 fail-closed。

## 审阅状态与下一步

当前线程 user 已签发 `approve_m5_durable_harness_design_freeze_only`，记录为 `approved_m5_design_freeze_only`。该决定只允许 M5.1 的受控实现，不能直接授权 worker/queue service、外部工具、provider、Evidence/Writer、full-chain、业务 Case mutation 或 global cutover；M5.1 的实际实现/验证见 worklog 159。

本条仍不代表 M5.2-M5.9 runtime 已实现。M5.1 已在 temporary store 以无后台 worker 的控制面方式落地；legacy TaskRun 仍为 execution/history authority。
