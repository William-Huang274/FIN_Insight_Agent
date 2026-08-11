# P38 Point 01 M2-A1 execution-admission preflight repair v2.1

日期：2026-07-14

状态：`execution_preflight_repaired_package_frozen_pending_exact_admission`

## 审计整改

total reviewer 拒绝将 v2 `453088e5015a612a3859d6b925f25133f6a05df7e52b85936958796b4bd69314` 直接用于 exact admission：旧入口可信 package JSON 字段、允许替换 corpus/matrix 与任意 temporary/ledger/output 路径，且 P03 通过直接调用 canary rejection 自报成功。

v2.1 在任何 `mkdir`、SQLite connect、receipt register/consume 或 M2 runtime import 前执行 package-external `ExecutionAdmissionPreflight`：

- canonical package payload digest、37 个 Git-index input SHA-256、CRLF-tolerant working/index equivalence；
- exact admission、固定 approval-store fingerprint、package-bound corpus/matrix/policy canonical digest；
- 只由 package/admission/receipt ID 推导 staging run root；CLI 不再接收 corpus、case、matrix、package、temporary root、ledger 或 output 路径；
- ledger/output/runtime 仅能位于派生 root，阻止 symlink/reparse escape；ledger 在 mkdir/connect 前验证 authority root；
- actual negative path 改为真实 accessor/constructor：oracle file read/hash、`sqlite3.connect`、`os.getenv` ambient resolver、provider import、`socket.socket.connect`；canary 同时拦截 socket/HTTP connect 和预加载 transport/provider module alias。

## v2.1 冻结证据

- package ref：`point01-m2-a1-execution-preflight-adversarial-audit-package-v2-1`
- package digest：`7773472a998c2559a95f68110dc7cd708bba96b985efcb01a942371a79818f50`
- gate digest：`19e57d5512f71879792267c2eb8d6ab0afd32f9c890c7bfc3dd94c8866d1e75d`
- package inputs：37，全部从 Git index 固定；gate package verification=`pass`。
- 定向 static/boundary regression：`15 passed`。覆盖 package payload/working drift、missing admission、derived paths、no caller path arguments、real accessor canary、preloaded alias 与 reparse branch。
- 扩展 no-I/O M2-A1 harness regression 与上述定向集联合：`18 passed`；未执行 compiler/shadow 或 A0-M2-P01/P02/P03。

## 不变边界

本轮没有 external admission、receipt registration/consume、P01/P02/P03 actual、compiler/shadow、model/network/tool/provider、fixed/production/business/legacy store read/write、PostgreSQL write、业务 Case 或 legacy authority mutation；所有 execution/write count 为 0。fixed approval DB 沿用已冻结 fingerprint，未在本轮打开。

v2.1 仍只可供 total reviewer 审核 exact package；不得自行登记 admission 或 receipt，更不得运行 actual、M3/M6/R3。
