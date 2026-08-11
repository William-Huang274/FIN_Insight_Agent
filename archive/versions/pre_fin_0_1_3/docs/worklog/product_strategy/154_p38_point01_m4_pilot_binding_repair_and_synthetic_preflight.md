# 154 P38 Point 01 M4 Pilot Binding Repair and Synthetic Preflight

日期：2026-07-12

状态：`rejected_pending_repair / deterministic blocker repair and synthetic read-only preflight pass`

## 决策

当前线程 human reviewer 明确拒绝对任何真实 persistent Case 的 authority mutation，也不提供业务 Case scope。原因是 M4 先前没有在 execute transaction 内重新校验 approval 与 store 中 exact entity 的绑定，canonical read 未锁定获批 contract version，且没有可审计的 persistent pilot admission/preflight。

## 已修复

- `LaneCutoverRequest` / `CutoverApprovalReceipt` 现在同时绑定 store identity、contract/artifact/comparison 的 exact ref 与 digest；`LaneCutoverDecision` 持久化相同的获批 binding。
- `execute_cutover` 与 `request_cutover` 都在 transaction 内重新读取 immutable entities；contract、artifact、comparison、store identity 或 digest 任何不一致均 fail-closed。
- `execute_cutover` 重新检查 expiry；human receipt 必须通过 authoritative revocation resolver 重新读取，缺少 resolver 或已撤销均 fail-closed。
- canonical authority read 只读取 `LaneCutoverDecision.approved_contract_version_id`；后续最新 contract 不会越过获批版本。
- M4.8 gate 要求 human approval 与 execution receipt 在 store/scope/exact refs/backup/rollback/kill-switch/impact scope 上逐项一致。

## Synthetic persistent preflight

- 已创建 ignored 的 `data/staging/point01_m4_synthetic_pilot_v2/`：只含 synthetic、non-production Case 与 object store，未触及现有业务 Case。
- `python scripts/engineering/run_point01_m4_synthetic_pilot_preflight.py` 已两次通过；输出 `data/manifests/point01_m4_synthetic_pilot_preflight_result_v1_0.json`。
- 结果：exact contract/artifact/comparison bindings 与 store identity 已列出；backup snapshot SHA-256 已记录；consumer count 为 0；authority 为 `legacy -> legacy`；`mutation_performed=false`。

## 验证与边界

- M4 blocker regression：approval expiry、human revocation、exact artifact digest mismatch、approved contract read lock、downstream consumer rejection 均有 fast-contract tests。
- 未运行 `request_cutover`、`execute_cutover`、`rollback_cutover` 于 synthetic 或真实 Case；没有 Evidence/Writer/provider/full-chain。
- M4 不是 complete。再次申请真实 pilot 时须提交并获得批准：store identity、tenant/project/case/lane、exact contract/artifact/comparison refs、backup snapshot hash、rollback window、kill switch、impact scope 和 revocation registry；然后才可创建对齐 execution receipt。
