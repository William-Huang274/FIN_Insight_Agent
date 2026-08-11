# 156 P38 Point 01 M4 Synthetic Persistent Mutation Pilot

日期：2026-07-12

状态：`pilot_execution_passed / human_acceptance_pending / M4_closeout_pending`

## 授权与范围

当前线程 user 明确批准一次 synthetic persistent mutation pilot。执行只使用新建、ignored 的 `data/staging/point01_m4_synthetic_pilot_v3/` SQLite store；Case 为 synthetic/non-production、下游 consumer 为 0。批准记录为 `configs/engineering_handoff/point01_m4_synthetic_pilot_approval_v1_0.json`，其 scope/approval id/registry/store/exact refs/backup hash 均固定。

未触及业务 Case、legacy TaskRun authority、Evidence、Writer、provider、full-chain、sector/tenant/global cutover。

## 已执行序列与证据

1. Read-only preflight 为 legacy authority，记录 v1 contract/artifact/comparison exact bindings 与 baseline content fingerprint。
2. 在 mutation 前创建 SQLite baseline backup。
3. 执行 `request_cutover`、`execute_cutover`：authority 进入 `canonical_for_lane`，decision 为 v1/v2。
4. 插入同一 contract 的 v2；canonical read 仍锁定获批 v1，证明不会漂移到最新版。
5. 执行 `rollback_cutover`：authority 恢复 legacy，decision 为 v3；source store 保留四条 append-only pilot events。
6. 将 pre-mutation backup 恢复到新 SQLite 路径：恢复库 integrity pass、legacy authority/exact refs 与 baseline fingerprint 匹配，pilot event count 为 0。此恢复库不应包含 source post-rollback 的 append-only history。
7. `store_backed_pilot_verification()` 通过；它回查 source 的 decision/events/versions/final authority，并用 baseline mode 校验 restore target。

## 结果

- Pilot result：`pass`。
- M4 focused fast-contract suite：`17 passed`；共享 M1 fixed-hash closeout：`pass / 126 passed`。
- `legacy -> canonical_for_lane -> legacy`。
- Event versions：`0->1`、`1->2`、`1->2`、`2->3`。
- v2 contract 已存在，但 canonical approved-version read 始终返回 v1。
- business Case mutation=false；model/external call=0。

## 人工审阅与下一步

`point01_m4_synthetic_pilot_human_acceptance_v1_0.json` 保持 `pending_human_acceptance`。该审阅与本次“执行批准”分离：只有在 user 接受 approval、execution evidence、baseline restore 和边界后，才可考虑把这次 non-production synthetic pilot 作为 M4 closeout 证据；当前不宣称 M4 complete。
