# P38 Point 01 M2-A1 receipt lifecycle repair v2.2

日期：2026-07-14

状态：`receipt_lifecycle_repaired_package_frozen_pending_exact_admission`

## 整改范围

v2.1 虽已在写入前验证 package、staged inputs、admission、fixed fingerprint 和路径，却没有可闭环的 receipt lifecycle：没有 registrar，executor 会创建空 ledger，并在消费前创建 runtime/output。本轮仅修复该控制面；没有运行 A0-M2-P01/P02/P03 或任何 compiler/shadow path。

- 新 registrar 只可创建 derived `authority` root 和 ledger，并登记 exact `REGISTERED` event；不 import M2，也不创建 runtime/output。
- executor 只能以 SQLite `mode=rw` 打开既有 ledger；原子消费 receipt 后，才可 materialize runtime/output 和 import future M2 runner。
- receipt exact bind package/admission/nonce SHA-256/expiry/reviewer/scope/authority boundary/staging namespace/scenario。
- missing ledger、replay、expiry、tamper、wrong package/scenario 均在 runtime/output/M2 import 前 fail-closed；consume 后无 terminal 的 crash 只能写 `outcome_unknown`，不能重放。

## 冻结与验证

- package ref：`point01-m2-a1-receipt-lifecycle-adversarial-audit-package-v2-2`
- package digest：`19d70b9fd0c89bd3e7945454a5d7bcc70ff4b2fb26b6d4118ef84543096973f0`
- gate digest：`d4e39a3cef3c14965b1419ea7b1354a543e524cb8939d85b9286d1feb1a84344`
- inputs：41 个 Git-index-staged 文件；package verification=`pass`。
- `pytest -q` no-I/O M2-A1 harness/boundary/static/lifecycle：`33 passed`。

所有测试使用 synthetic admission/receipt 与 pytest temp root；没有 external admission 或真实 receipt registration/consumption。P01/P02/P03、compiler/shadow、model/network/tool/provider、fixed/production/business/legacy store open/write、PostgreSQL write、business Case 和 legacy authority mutation均为 `0`；fixed approval DB 未打开。

## 下一步

只允许 total reviewer 独立审核该 v2.2 exact package 是否具备 external admission 的技术资格。不得自行登记真实 admission/receipt、不得执行 actual 或进入 M3/M6/R3。
