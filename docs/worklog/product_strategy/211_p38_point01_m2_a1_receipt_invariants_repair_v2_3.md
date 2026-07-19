# P38 Point 01 M2-A1 receipt-invariants repair v2.3

日期：2026-07-14

状态：`receipt_invariants_repaired_package_frozen_pending_exact_admission`

## 审计整改

本轮只整改 M2-A1 v2.2 receipt authority 的三个实现缺口；未登记 external admission 或真实 receipt，未运行 P01/P02/P03、compiler 或 shadow。

- `CONSUMED_BEFORE_RUN` 现在原子写入 ledger-backed `M2A1ConsumptionGrant`。runtime/output materialization 必须验证 grant digest、receipt 的 consumed state、同一 ledger event、exact package/admission/scenario/run-root/preflight；仅 `REGISTERED` 或调用方构造的 grant 均在 mkdir 前 fail-closed。
- `M2A1ReceiptLedger.register()` 以调用方提供的 exact executable package digest 校验 receipt，且将 expected `scenario_id` 传入 authority validation；错误场景或错误 package 在 authority API 层停止，不能依赖 CLI 外层检查。
- executor 的未来真实路径固定为：preflight → existing-ledger no-create open → atomic consume → staged execution-tree reverify → grant/state verify → runtime/output mkdir → import canary/harness → execute。consume 后的 drift 或 grant failure 只写 `outcome_unknown`，receipt 保持 spent，且不 materialize runtime/output、不 import M2。

## 冻结与验证

- package ref：`point01-m2-a1-receipt-invariants-adversarial-audit-package-v2-3`
- package digest：`ff5476b9a8c4d9a82a11b163039e118922b09c945a0d53ff9df031b7c268b318`
- gate digest：`904d1030c7110281acc4963ec0a615da3db0b0ce9e4a68b0d6aaf80971549243`
- package 输入为 41 个 Git-index files；manifest/gate 的 staged-byte verification=`pass`。
- `pytest -q` receipt lifecycle、package static、boundary、assembly harness、harness boundary：`37 passed in 76.22s`。
- 语法编译：receipt authority、actual executor、registrar、freeze runner 均通过 `py_compile`。

所有测试仅使用 synthetic admissions/receipts 与 pytest temporary roots。external admission、真实 receipt registration/consumption、A0-M2 P01/P02/P03、compiler/shadow、model/network/tool/provider、fixed/production/business/legacy store open/write、PostgreSQL write、business Case/legacy authority mutation 均为 `0`；fixed approval DB 未打开。

## 结论与下一步

v2.2 package `19d70b9f…96973f0` / gate `d4e39a3c…1a84344` 已由 v2.3 supersede，不得用于 admission。v2.3 只是 execution-ready refreeze，仍需 total reviewer 对 exact package 独立复核后才可能讨论 package-external admission；当前禁止登记真实 receipt、执行 actual、进入 M3 或 M6.3R.3。
