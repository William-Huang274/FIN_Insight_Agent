# P38 Point 01 RC-P38-024 Phase A：transport isolation repair package

日期：2026-07-14

状态：`repair_package_frozen_pending_independent_review_phase_b_blocked`

## 范围

本轮仅落实 Phase A：根因分类、代码修复、deterministic regressions 和 Git-index repair package/gate 冻结。没有签发 admission/receipt，没有创建 authority/ledger/runtime namespace，没有重跑 baseline，也没有网络、模型、provider、tool、fixed/canonical/business store 或业务/legacy authority mutation。

## 根因分类

新鲜 `python -I` 子进程确认，历史 failure 由两项 owned defect 叠加：

- `canonical_runtime.__init__` eager public exports 经 `receipt_bound_candidate_bundle` 载入 `bounded_sec_metadata_execution`，从而 import `requests`；因此纯 local planning path 意外拥有 transport 模块。
- canary 把 `requests/urllib3` module presence 当作 transport constructor attempt，无法区别宿主 alias 与实际 capability use。

clean Python、canonical planning compile、legacy bridge/runtime facade、actual clean bootstrap 都已验证为 transport delta=`{}`。只有专门负控制显式 import `requests`：module presence 仍只是 context；`requests.Session` constructor、socket connect、`urllib.request.urlopen` 均在联网前 typed stop，request success=0。

## 修复

- `canonical_runtime` 改为 lazy `__getattr__` public exports，planning path 不再 transitively import M6 SEC transport client；
- M2 actual supervisor 保持 stdlib-only，并以 `python -I` clean child 执行；child 在 M2 harness/compiler import 前安装 canary；
- canary 分离 `transport_module_loaded/preloaded_alias` observation 与 constructor/connect/request/success counters，保留 concrete socket/HTTP/tool/provider/store intercept；
- actual runner 与 clean child 均不 import/read oracle 或 reviewer expectation；已消费旧 receipt 的 replay contract 保持 fail-closed。

## Evidence

- classification digest：`537801860ceb455c1ce035621776128c3d8647e2d3af00e66b02d27e8b1e0b71`
- repair package digest：`11f4cd9267e56e9c6c33eaeb32119194731d76dbe0040e34b441e6daf66bd7cd`
- repair gate digest：`52cd13eda74affc99352a14a3ffff322e96b992b252c40d9dd6335d9f9e181fe`
- focused M2-A1 regressions：`40 passed`（2 + 22 + 16 分组）；local planning regression：`6 passed`。
- fixed approval DB 仅以 pinned SHA-256 对照：`ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

## 状态与下一步

- `M2 milestone_scope_status = complete_deterministic_shadow`
- `M2 operational_qualification_status = fail_closed_pending_transport_isolation_repair_review`
- `M3–M5 = scoped_closeout_retained_adversarial_operational_requalification_pending`

必须停止等待 independent review。下一步若获批准也只能是 Phase B 的 fresh baseline authority decision；不得复用本次或历史 admission/receipt/nonce，不得自动重跑 baseline 或放行其余 15 个 scenario。
