# 188 P38 Point 01 M6.3/M6.5 Exact Receipt Registration And Read-only Preflight

日期：2026-07-13

## 本轮授权与范围

总审计窗口批准 `approve_m6_3_5_exact_package_receipt_registration_and_preflight_only`。本轮只允许为已冻结 v3 package 登记 package-external one-shot receipt，并进行只读预检与 digest stability 回查；没有获准执行 SEC GET、网络请求或 live executor。

## 登记结果

- receipt：`approval_point01_m6_3_5_nvda_10k_revenue_parser_repaired_global_one_shot:v1`
- reviewer：william（003，total reviewer）
- fixed store identity：`a62079db4293d7430a2c912fdb5cbec0446cf2eb442a1e5c623d64ac545ddd01`
- UTC expiry：`2026-07-13T12:53:53Z`
- nonce：不记录明文；审计摘要为 prefix `86d0623f…`、SHA-256 `373f2994a26519a76b72ad980759340d10f00e917c4f13e0cb899b3629257b92`。

## 精确绑定与稳定性

```text
package_ref:      point01-m6-3-5-nvda-10k-positive-retrieval-parser-package-v3-immutable-authority-boundary
package_digest:   7d2a5b40ad765a8de655c1d0fbd73e82130ed58e1be659cb5899aa5871054ca5
manifest_digest:  8970c0aae48d9059ed11d8ec8efc54882a8cbc74e32ee4f29f5932c792b714f3
scope_digest:     ad5df001105162f36528c217457464df65ff5e4e1778c55134412a50296ee1b0
```

- 登记前只读预检：预期 `fail_closed / global_approval_receipt_not_registered`，external/network/tool/store write 均为 `0`，并确认 v3 三项 digest 完全匹配。
- 登记后只读预检：`pass`；receipt 为 `active`、`unconsumed`、`scope_exact`，preflight 内 before/after digest 都与上表完全一致。
- package freeze after receipt：三项 digest 重算一致；默认 freeze runner 没有读取 receipt，仍输出 package-freeze 状态，不能将其 `reason` 当作 receipt 真实性判断；receipt 真值由专用只读 preflight 产生。

## 验证

- `python -m pytest -q tests/contract/test_point01_m6_3_5_positive_sec_document_receipt_preflight.py`：`2 passed`。
- `python -m compileall -q scripts/engineering/run_point01_m6_3_5_positive_sec_document_receipt_preflight.py tests/contract/test_point01_m6_3_5_positive_sec_document_receipt_preflight.py`：通过。
- `python scripts/engineering/run_point01_m6_3_5_positive_sec_document_receipt_preflight.py`：`pass`。

## 安全边界与下一步

- 未设置、读取、输出或持久化 SEC User-Agent 明文。
- external/network/tool call=`0`；live send、parser、numeric、Evidence promotion、M6.4 repair、M6.6 promotion、M6.7、Writer/Judgment、model/provider、full-chain、业务 Case mutation、legacy authority change 均为 `0`。
- 当前状态：`receipt_registered_preflight_only_live_send_separately_pending`。
- 必须由总审计窗口另行批准 `approve_m6_3_5_single_fixed_nvda_10k_live_get_only`，才可在 send 前原子消费该 receipt；本轮到此停止。

## Supersession

本记录的“active/unconsumed”状态已由 [189 incident record](189_p38_point01_m6_3_5_unapproved_test_induced_live_get_incident.md) supersede：其后错误运行的 broader regression 消费了 receipt 并触发未授权 GET。不得以本记录作为当前可执行授权。
