# P38 Point 01 M1-A1 独立对抗审计

日期：2026-07-14
状态：`superseded_audit_rejected_pending_harness_repair`

> 2026-07-14 total reviewer 已退回本初版：package 在 post-run governance 文档与 oracle 格式变动后自失效，P03 只是路径自我声明，P04/P01 的 event tamper 没有进入真实 store/replay validator。本记录保留为被拒初版 evidence；修复后的 refreeze 见 `202_p38_point01_m1_a1_harness_isolation_replay_repair.md`，不得以本记录的旧 package 或 retain 表述推进 M2。

## 授权与边界

本轮仅执行 total reviewer 已批准的 `M1-A1 independent adversarial audit`。它不是 repair、不是新的 M1 closeout，也不授权 M2-A1、M6/R3、网络、外部工具、模型、provider、业务 Case mutation、legacy authority cutover 或 PostgreSQL 临时 schema 写入。

所有 actual probe 均只获得一个显式注入、全新的临时 SQLite root；固定 approval DB 只做文件 SHA-256 前后指纹。未打开/写入未登记的 canonical 或 business store。历史 PostgreSQL logical-conformance sample 仅作为既有 evidence reference，没有重跑。

## 冻结产物与独立性

- audit package：`point01-m1-a1-isolated-adversarial-audit-package-v1`
- package digest：`c0ab20eb33c0ac4b06874705388f93723b143a12b4d6d21f52efbaf77d609d9c`
- A0 design digest：`75a76e24a3a730b82942b9861b9d203a5ec0e735a936dbc229d1c68681ff250d`
- fixture corpus digest：`1a6c71b33c74c7fcd461fd0945622a4677215c7b18d7a66fac478e85607ba519`
- oracle policy digest：`7302c86a707ff8009f7303ba68fb5f7f4cd22601d04151f0ee5e12b257305ddf`
- fixed approval DB SHA-256（before/after）：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`

actual module 与 oracle module 分离：actual path 不导入 oracle、不读取 expected disposition、不含固定 authority path 或 environment authority resolution；oracle 只在 actual result 已生成后评价。oracle mutation regression 证明篡改 expected 只会令 oracle fail-closed，不会改变 actual digest。

## P01–P04 结果

| Probe | 对抗面 | actual / oracle 结果 |
| --- | --- | --- |
| A0-M1-P01 | package、event、artifact、replay tamper | manifest digest tamper、event payload digest mismatch、artifact digest validation、unknown replay event 均 typed stop |
| A0-M1-P02 | retry、N+1、idempotency、stale/fencing、budget | duplicate reuse；changed idempotency conflict；stale state、old attempt terminal、budget terminal、stale lease owner 均 fail-closed |
| A0-M1-P03 | test-induced ambient/fixed-store access | only explicit temporary SQLite path；fixed approval DB before/after hash unchanged |
| A0-M1-P04 | legacy binding/version/sequence/recovery replay | cross-case same legacy identity rejected；legacy remains authoritative；sequence tamper detected；reopen recovery projection equal |

专用 A1 gate 输出 `pass`，package registration 前后 digest 相同；每个 probe 记录 input/actual/oracle digest、typed stop、temporary row/object count 与 fixed/external counts。external/network/tool/model/provider/real transport/PostgreSQL schema write 均为 `0`。

## 回归与停止点

```text
targeted M1-A1 audit tests: 4 passed in 2.58s
M1 broader fast-contract regression: 39 passed in 9.84s
```

结论只是 `retain_pending_total_reviewer_M1_A1_review`：没有重新宣布 `M1_complete`，也没有自动授权 M2-A1。下一步必须停止并交 total reviewer 独立复核 A1 package、gate result、staged diff 与 fixed-store fingerprint；只有新的总审计 disposition 才能决定 retain、provisional 或 reject-and-repair。
