# 182 P38 Point 01 M6.2 Global One-Shot / Send-Boundary Remediation

日期：2026-07-13

## 审计整改范围

本项只修复 M6.2-M6.5 receipt-bound local terminal chain 的四项审计缺口：全局 one-shot approval、durable send boundary、SEC User-Agent 合规校验，以及 Point 文档的 external-network authority 口径。没有设置 `SEC_USER_AGENT`，没有向 SEC 或任何外部服务发请求。

## 交付

- fixed canonical global approval store：`M6GlobalOneShotApprovalReceipt` 独立于任意 local pilot store；必须由 total reviewer `william（工号003）` 提供 exact package/manifest/scope digest、unique nonce、UTC expiry 与 scope。执行器只消费 active receipt，消费在 HTTP send 前的 approval-store transaction 内 append-only 变为 `consumed`；更换或复制 local `--store-root` 不会获得新调用权。
- digest package 与 human receipt template：package manifest 覆盖 runtime、policy、runner、receipt recorder 和 contract tests；preflight 只计算 scope/package，不创建 store 或调用网络。total reviewer `william（003）` 已将 checked-in receipt 填为 `approved`，并由独立 recorder 登记到 fixed authority store；live runner 永不自行登记 receipt。
- send boundary：ToolInvocation receipt 的 lifecycle 固定为 `prepared -> send_authorized -> send_started -> succeeded/outcome_unknown`。HTTP 前已记录 `send_started`；HTTP 返回后的进程退出、budget consume 写失败或 terminal receipt 写失败，只能在 restart reconciliation 中保守终止为 `outcome_unknown`，并且不会再次调用 client。
- User-Agent：最低长度、应用标识、邮箱形式联系人与 placeholder 拒绝均为 hard validation；canonical receipt 只有 SHA-256 fingerprint，不保存原始联系方式。
- 文档口径：generic external execution 继续禁止。唯一例外是 exact NVDA `data.sec.gov` metadata pilot，且前提是 active、unexpired、digest-bound global one-shot human receipt 与合规 User-Agent；当前前提都未被满足。

## 定向验证

```text
python -m pytest tests/contract/test_point01_m6_2_real_bounded_sec_metadata_execution.py tests/contract/test_point01_m6_2_global_one_shot_approval.py -q
# 14 passed

python -m pytest (Get-ChildItem tests/contract -Filter 'test_point01_m6_*.py' | ForEach-Object { $_.FullName }) -q
# 60 passed

python -m pytest tests/contract/test_point01_sqlite_store.py tests/contract/test_point01_runtime_facade.py -q
# 28 passed

python scripts/engineering/run_point01_m6_0_design_lint.py --output $env:TEMP\point01_m6_design_lint_remediation.json
# pass

python scripts/engineering/run_point01_m1_closeout_gate.py --output $env:TEMP\point01_m1_closeout_remediation.json
# pass (includes PostgreSQL conformance)

python scripts/engineering/run_point01_m6_2_global_one_shot_preflight.py --output $env:TEMP\point01_m6_global_one_shot_preflight_remediation.json
# pending_human_receipt / external_call_count=0 / store_write_count=0
```

覆盖 global receipt 跨 local-store one-shot、错误 package、placeholder/missing-contact User-Agent、mocked send 后 child-process `os._exit`、budget consume failure、terminal receipt write failure、restart reconciliation 与 no-resend。

## 当前状态与下一步

状态为 `conditional_authority_remediation_complete_global_one_shot_receipt_registered_no_live_send`。approval preflight 的 exact values 为：package digest `3f3d004dd6893b99da993b5b1a73d7230a2d9e16d7fcbc066c0bd80b508d6942`、manifest digest `454b6693fbce8a33a399a8dc797aee2360d560db6abb9092ba162c31862d2cb3`、scope digest `a944b3016d8244dd1b0d61a2b98b084e5f8967c33382d12b4b7c85fba7a46218`。total reviewer `william（003）` 的 receipt 已登记为 active，expiry 为 `2026-07-13T08:00:00Z`（北京时间 16:00）。此记录仍不是 live 执行许可：`SEC_USER_AGENT` 未设置，实际 external call 为 0。

在完成 SQLite/RuntimeFacade、M1 gate 与 exact package digest 后，下一步只能提交 preflight 的 package/manifest/scope digest 给 total reviewer；reviewer 需填入 nonce/expiry 后独立登记 receipt。只有该动作完成，才可重新申请唯一一次 live NVDA SEC metadata pilot。M6.3-M6.5 仍只可消费 future exact successful receipt 的 typed exhaustion；M6.7、Evidence promotion、Writer/Judgment、full-chain、业务 Case mutation 与 legacy authority change 均未获准。
