# P38 Point 01 M1-A1 审计器隔离与 replay probe 修复

日期：2026-07-14
状态：`audit_harness_repaired_refrozen_pending_total_reviewer`

## 总审计退回与修复范围

本轮只修 M1-A1 audit harness，不修改 `models.py`、`store.py`、`facade.py` 的 M1 runtime 语义。初版 A1 被拒的三个原因是：package 将 post-run 可变治理文档纳入 immutable inputs、P03 没有真实 access canary、P01/P04 只在内存中计算 tamper 而没有把篡改交给 runtime/store。

## 已修复的审计合同

- package 改为 Git-index bytes freeze：所有 input SHA 都从最终 staged bytes 计算与复核。execution inputs 必须 working tree 与 index 相同；历史 M1 evidence 也按 index bytes 验证，但不要求覆盖用户 working tree 中不参与本次执行的行尾/治理差异。
- 主计划、context、worklog、ledger 从 immutable package input 移出，因其必然在 gate 后记录审计结论；它们不再引入 self-invalidation。
- 对未登记的 M1 fixed canonical/business store 写入 explicit absence manifest；`M1AuditAccessCanary` 会拒绝任意 non-allowlist store path，不能以“not registered”跳过检测。
- canary 在同一进程拦截 `SQLiteCanonicalStore`、`FileCanonicalObjectStore`、直接 `sqlite3.connect`、HTTP/HTTPS constructor、`urlopen` 与 socket transport。scoped broader M1 tests 使用 `--basetemp` 落在 canary allowlist 内。
- P03 实际尝试 fixed approval DB、ambient/unallowlisted SQLite path 与 HTTPS constructor，三者均在打开/构造前 typed fail-closed。
- P01 在 cloned temporary SQLite 上实际更新 `canonical_events.payload_digest`；P04 实际更新 `sequence_no`。两者均由真实 SQLite append-only trigger 返回 `IntegrityError:append_only_table`。若未来 mutation 被接受，probe 会立即在 clone 上调用真实 replay/recovery；若二者未 fail-closed，gate 记录 runtime bypass 并停止，不在本轮修 M1。

## 新冻结与验证

- package digest：`91cc1f89d98d6b8a1b94339986f58537e5f0dbb2e0dc56ab4b4acdcebe4358e0`
- oracle policy digest：`e3c19d1f188d7d15fc5453515089102b1f712393265ed5d0f04ea58065e2c6b0`
- fixture corpus digest：`1a6c71b33c74c7fcd461fd0945622a4677215c7b18d7a66fac478e85607ba519`
- `package_current_verify_before=pass`、`package_current_verify_after=pass`，input source 为 `git_index`。
- targeted harness tests：`5 passed in 2.82s`。
- canary scoped M1 regression：`35 passed in 6.07s`。
- canary evidence：fixed-store open attempt `1`、ambient/unallowlisted open attempt `1`、transport constructor attempt `1`，均为预期 negative typed stop；其余 `469` store opens 均在临时 allowlist 内。
- fixed approval DB before/after SHA-256：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。
- network/tool/model/provider/real transport/PostgreSQL schema write 都是 `0`。

## 停止点

gate 为 `pass`，但 disposition 仅为 `audit_harness_repaired_refrozen_pending_total_reviewer`。这不是 M1 retained、更不是 M1 complete：必须由 total reviewer 独立复核新 package、staged-byte verification、canary negative 和 cloned-store evidence 后，才能对 M1-A1 给出 retain/provisional/reject disposition。M2-A1、M6/R3 与所有下游 authority 继续 blocked。
