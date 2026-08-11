# P38 Point 01 M1-A1 exact-admitted 单次隔离审计重跑

日期：2026-07-14
状态：`completed_pending_independent_review`

## 授权与执行边界

total reviewer `william/003/total_reviewer` 以 package-external admission `point01-m1-a1-total-reviewer-package-admission:v1` 精确批准 package `point01-m1-a1-isolated-adversarial-audit-package-v2-identity-bound`，package digest 为 `c5169899e84a8eb0d99e49b3dbaa3dca0b963d9423364816605df8a49775bcf7`。本次只允许一次 M1-A1 isolated temporary SQLite audit；禁止 PostgreSQL schema write、fixed/business/legacy mutation、网络、工具、模型、provider、M2-A1、M6/R3 与任何 milestone closeout。

admission 本身不进入 package inputs。执行封套先从 Git index 重建并校验冻结 package，再在 append-only receipt ledger 写入 `single_use_consumed_before_actual_audit`；无论运行结果如何，该 receipt 不得重用或重试。

## 结果

- admission digest：`f05e33dcff4d053d38ea7daf37b62514b430500de497f27d5892eeaaa9f18628`。
- package staged/index preflight before/after 均为 `pass`；index-rebuilt package digest 保持 `c5169899e84a8eb0d99e49b3dbaa3dca0b963d9423364816605df8a49775bcf7`。执行 inputs working bytes 均等于 staged bytes；3 个 historical-evidence working/tree differences 未进入 execution path，仍只按 index bytes 复验。
- execution receipt `point01-m1-a1-exact-admitted-execution:m1_a1_exact_admitted_rerun_29fceae7a4914314bf2c80e6683e5acc` 已消费，terminal=`completed`，receipt digest=`c362e590fb7966b3afc1fb66e21043771ae29a5fcf21226f67c3e546ab215771`。
- P01–P04 actual/oracle 全部 `pass`；gate result digest=`009e0ea96f20c43346ba373c2a68acc1d016f3c11a60131739efd31f6f37b4df`，gate=`pass`。
- scoped M1 regression：`35 passed in 6.77s`。P01/P04 cloned-store tamper 由真实 append-only trigger 拒绝；P02 覆盖 retry/idempotency/stale/fencing；P03 fixed-path、ambient-path、transport constructor negative 各一次 typed stop。
- fixed approval DB SHA-256 before/after 均为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`；external/network/tool/model/provider/real transport/PostgreSQL schema write 均为 `0`。
- 所有 SQLite 写入都在运行时创建的 temporary roots：P01/P02/P03/P04 temporary object+row counts 分别为 `27/46/4/6`；canary 记录的 469 次 store open 与 6536 条 SQLite write statements 均在 allowlisted temporary roots，fixed/ambient open 和 transport constructor 均被拒绝。

## 审计材料与停止点

- package-external admission：`data/manifests/point01_m1_a1_exact_external_package_admission_v1_0.json`。
- append-only receipt ledger/projection：`data/manifests/point01_m1_a1_exact_admitted_execution_receipts_v1_0.jsonl` 与 `data/manifests/point01_m1_a1_exact_admitted_execution_receipt_projection_v1_0.json`。
- actual gate/closeout：`data/manifests/point01_m1_a1_exact_admitted_audit_gate_result_v1_1.json` 与 `data/manifests/point01_m1_a1_exact_admitted_audit_execution_closeout_v1_0.json`。

这只完成受审批的一次 audit rerun，**不重新声明 M1 retained 或 M1 complete**。receipt 已消费；现在必须停下并交 independent total reviewer 复核，M2-A1、M6/R3 及其他下游继续 blocked。
