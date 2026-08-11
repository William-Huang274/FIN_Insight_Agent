# P38 Point 01 M2-A1 execution-ready package repair v2

日期：2026-07-14

状态：`execution_ready_package_frozen_pending_exact_admission`

## 审计整改与 v1 处置

旧 v1 executable package `1a51d745f14751a19add0d0f72d5296879fdab95d0ee84f837b481ddd9cf2061` 已标记为 `executable_harness_skeleton_frozen_rejected_pending_full_actual_implementation`；不得登记 admission、receipt 或运行。

本轮只完成 v2 静态实施/refreeze，**没有执行** `A0-M2-P01/P02/P03`，没有注册 admission/receipt，也没有打开 fixed approval DB。

## v2 合同

- `execute_admitted_scenario()` 在 import M2 compiler/pack/serializer/shadow 前，验证 package-external admission 并在独立 SQLite ledger 原子消费 one-shot receipt。
- future path 实际连接 adapter、registry、selection、planning、shadow、serializer 与 orchestration；canonical/object root 仅允许显式 temporary root。无完整输入合同会 terminal typed stop，不伪造 envelope。
- constructor-level canary patch SQLite/object store、文件读写、oracle/provider import、socket/HTTP 与 subprocess；记录 attempt/success/read/write/constructor/request，fixed/ambient/oracle/provider/network/tool 在访问前 typed stop。
- v2 matrix 固定 16 场景；runner 仅接收 `scenario_id/input_ref/mutation`，不接收 reviewer expected stop/cell oracle。
- immutable actual、独立 oracle 与 reviewer gate 分别校验 lineage/owner/slot/semantic/replay、negative exact stop/P03 counters 及 receipt consumption/terminal/coverage。

## 冻结与验证

- package ref：`point01-m2-a1-execution-ready-adversarial-audit-package-v2`
- package digest：`453088e5015a612a3859d6b925f25133f6a05df7e52b85936958796b4bd69314`
- gate digest：`7b28f0655a0d5b44d965827acdcdb9162062d0f82de7da6a6655304024136d42`
- 定向 boundary/static tests：`10 passed`。

## 停止线

compiler/shadow actual、model/network/tool/provider、external transport、fixed/production/business/legacy store open/write、PostgreSQL write、业务 Case mutation 和 legacy authority mutation 均为 `0`。fixed approval DB 仅 bind 已知 SHA-256，未打开。

下一步仅能由 total reviewer 审核 v2 exact package；即使获 admission，仍需新 receipt 和单独 execution approval。不得自动执行 P01-P03 或进入 M3/M6/R3。
