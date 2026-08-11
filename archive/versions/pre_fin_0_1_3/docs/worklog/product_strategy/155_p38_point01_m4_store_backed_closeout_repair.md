# 155 P38 Point 01 M4 Store-Backed Closeout Repair

日期：2026-07-12

状态：`implementation_repair_passed / synthetic_preflight_passed / pilot_not_authorized / M4_closeout_pending`

## 问题与决定

审计确认此前 synthetic preflight 只检查 source SQLite store，而 M4.8 closeout 仅对齐 approval/evidence JSON；两份一致的手填 JSON 仍可能误通过。另有 authority event 固定写入 `0 -> 1`、approval registry identity 没有被持久化重验的问题。

本轮只修复 M4.8 工程门禁。未对 synthetic 或业务 persistent Case 调用 `request_cutover`、`execute_cutover` 或 `rollback_cutover`；不运行 Evidence、Writer、provider 或 full-chain。

## 已完成

- `SQLiteCanonicalStore.content_fingerprint()` 对所有版本化对象、event 和 kill switch 生成路径无关的内容摘要；store identity 仍保留路径绑定的 approval 语义。
- synthetic preflight 现在从 snapshot 恢复到独立路径、重开数据库，比较 integrity、`legacy` authority、exact contract/artifact/comparison bindings 与 source/restore fingerprint；旧的误导性 `backup_recovery_status` 已拆为 `source_store_integrity_check` 和 `backup_restore_drill`。
- `CutoverApprovalReceipt` / `LaneCutoverDecision` 新增 `approval_registry_ref`；resolver 必须同时返回相同 `approval_id` 与 registry identity。
- request、execute、authority-change、rollback event 记录实际 decision / CaseControl version 变化与 `state_subject`，不再固定 `0 -> 1`。
- M4.8 closeout 新增 `--persistent-store-path` 与 `--backup-snapshot-path`。它从 source store 回查 scope、exact entities/digests、decision v1/v2/v3、approval/registry identity、事件顺序/版本、最终 legacy authority，并由 gate 本身恢复 backup 后比较 fingerprint。
- approval/evidence 模板采用分离状态：实现修复与 synthetic preflight 已通过，但 pilot authorization 未授予、execution 未开始、M4 closeout 待定。

## 验证

- M4 targeted fast-contract suite：`16 passed`。
- 共享 M1 fixed-hash closeout：`pass / 125 passed`；M1_complete 不变。
- synthetic read-only preflight：`pass`，restore drill 的 source/restore content fingerprint 相同；authority 始终 `legacy -> legacy`，`mutation_performed=false`。
- M4 closeout：预期 `fail_closed / M4_closeout_pending`；当前未满足项仅为 human pilot approval、pilot execution 与 store-backed pilot verification 尚未可执行。
- 新负例覆盖：手填 receipt 无 source store、错误 store、错误 backup hash、错误 entity digest、缺事件、事件乱序、错误 event version、approval registry identity mismatch。

## 后续与安全边界

下一步不是自动执行 mutation。必须先由 human 单独授权一个隔离、非生产、无下游消费者的 synthetic persistent Case pilot，并提供 exact scope、approval/registry、backup、rollback window、kill switch 与影响范围。业务 Case mutation 仍为 `rejected_pending_repair`；M4 不得标记 complete。
