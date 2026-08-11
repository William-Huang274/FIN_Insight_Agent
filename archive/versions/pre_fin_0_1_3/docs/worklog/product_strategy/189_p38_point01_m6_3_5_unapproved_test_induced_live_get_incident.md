# 189 P38 Point 01 M6.3/M6.5 Unapproved Test-induced Live GET Incident

日期：2026-07-13

## 结论

本轮只获准 receipt 登记与只读 preflight。登记和 preflight 均按批准完成后，执行窗口错误运行了 broader M6 test manifest；其中一个既有负例在 production fixed approval store 上调用 `RUNNER.build_result(execute_live=True)`。因为 exact receipt 已 active，该负例不再 fail-close，而是进入真实 executor。

这导致一条 receipt 被原子消费，并发生 **1 次未经本轮批准的 exact SEC Archives GET**。因此本次 event 不能标为批准的 live pilot，也不能用于推进 M6.3/M6.5 或任意下游。

## 已核实事实

- 被消费 receipt：`approval_point01_m6_3_5_nvda_10k_revenue_parser_repaired_global_one_shot:v2`，状态 `consumed`；不得重放、续期或复制。
- exact invocation：`sec_document_invocation_8951234b49a7b1c6281cae52`。
- 网络：exact `www.sec.gov` fixed Archives path；HTTP `200`；external call=`1`、fallback=`0`、retry=`0`。
- 数据：response SHA-256 为 `dae19486be264fd26eb00a7f920dc641041a261c81bc8c03b678eea947de4856`；raw document 未持久化。
- temporary SQLite 产生 candidate/parser/fact/trace，但均为 `unpromoted`、`non-citable`；它们仅作为 quarantine audit evidence，不能被 Evidence、Writer、Judgment 或 M6.6 消费。
- 事后执行只读 preflight：`fail_closed / global_approval_not_active:consumed`，外部/network/tool call 均为 `0`。

## 最早根因

`tests/contract/test_point01_m6_3_5_positive_sec_document_execution.py` 中的 `test_no_active_exact_receipt_denies_execute_live_before_local_store_or_send` 假设 production fixed store 没有 active receipt；它把测试 User-Agent 与 live flag 直接交给 global runner，而未注入临时 approval store 或 fake client。该负例在 receipt registration 后变成外部 side effect。

## 当前门禁

```text
incident_open_unapproved_test_induced_live_get_receipt_consumed
```

禁止补发、替换 receipt、重放、promotion、M6.4 repair、M6.6、M6.7、Writer/Judgment、模型/full-chain、业务 Case mutation 或 legacy authority change。

在总审计窗口给出进一步指令前，只允许 incident 的只读审计。后续工程整改必须先把 regression live branch 注入 isolated temporary authority store 与 non-network client，并增加“active production receipt cannot be consumed by tests”的回归；整改会改变 package，必须重新 freeze 并再走审批。
