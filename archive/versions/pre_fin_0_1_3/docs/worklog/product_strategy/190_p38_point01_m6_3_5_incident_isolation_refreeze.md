# 190 P38 Point 01 M6.3/M6.5 Incident Isolation Refreeze

日期：2026-07-13

## 结论

总审计窗口只批准 `approve_incident_remediation_test_runtime_isolation_only`。本轮完成 owned test/runtime/transport isolation 修复和 v4 package refreeze；没有登记新 receipt、没有设置或复用 SEC User-Agent、没有执行 SEC GET 或其他网络请求。

此前 v3 receipt 被 test-induced live branch 消费及其 HTTP 200、invocation、response hash 与 unpromoted/non-citable temporary artifacts 均保留为 append-only quarantine incident evidence。本轮不删除、不覆盖、不追认，也不将其用于 calibration、Evidence、Writer、Judgment 或任何 M6 下游路径。

## 根因与修复

- 最早错误是 contract test 直接调用 importable `RUNNER.build_result(execute_live=True)`，使测试依赖 production fixed approval store 中“没有 active receipt”的环境假设，并会创建真实 transport。
- `run_point01_m6_3_5_positive_sec_document_pilot.py` 现把 deterministic package freeze 与 explicit CLI live entrypoint 分离。importable `build_result()` 不解析 production fixed authority、不创建 HTTP client、不创建 local runtime store，也不接受 live flag。
- library-level execution 改为必须显式注入 authority service 与 non-network/explicit client；缺失依赖时在 receipt lookup、runtime store 或 send 前 fail-closed。
- `SingleCallSecDocumentClient` 默认 transport 改为 fail-closed；真实 `requests.Session()` 仅能由 explicit CLI `--execute-live` entrypoint 在 exact active receipt、process-local scope confirmation 和 admission 已通过后创建。
- receipt preflight 改为 library 函数显式接收 injected SQLite store；CLI 才能显式解析 fixed production path。
- 所有相关 contract/fixture tests 现以 `tmp_path` authority store、injected authority service 和 fake client 运作；新增 active canary receipt、missing authority/client、default transport 和 incident fixture 回归。

## v4 冻结证据

| 项目 | 值 |
| --- | --- |
| superseded incident package | v3 `7d2a5b40ad765a8de655c1d0fbd73e82130ed58e1be659cb5899aa5871054ca5` |
| 新 package ref | `point01-m6-3-5-nvda-10k-positive-retrieval-parser-package-v4-incident-isolation-refreeze` |
| package digest | `724bb947df735fc5392c038a978bdc6135a434baad66538b747b43279fe2cd0c` |
| manifest digest | `18f510b0a0adb20b9e56b6f4d55498728dea0928f9b0f0c3cb3537085fc7e6ea` |
| scope digest | `db2da6cf08a16d69636f61c680263440a6b7d7bd2d1f5f1a3c72d11b0362faf6` |
| status | `incident_remediated_refrozen_pending_total_reviewer` |

## 验证

- incident-isolation targeted contracts：`29 passed in 5.08s`。
- 全部 Point01 M6 contracts：`89 passed in 23.09s`。
- SQLite/RuntimeFacade：`28 passed in 4.95s`。
- M6.3/M6.5 design lint、actual-shape local parser gate、changed-surface `compileall`、`git diff --check` 均通过。
- default transport 和 fake transport tests 均明确证明 no-network；修复验证期间 `external_call_count=0`、network=0、model=0、tool=0。
- 以稳定 canonical 内容算法包裹一次完整 M6 suite 后，production fixed approval store 的 database SHA-256 与 content fingerprint 前后相同：`f98f4a1fd36a9c5a0ecf96fa98c0f66c21102d1cdce69a9316b121334d7a3291` / `3354d84b0e7693d019e3224a3d51af365ff35f0469fc82c97bc666af830ae5da`；rows=`2`、latest=`consumed:v2`。

## 仍然禁止与下一门

本轮不产生新的 human receipt，不能恢复或替换 v3 consumed receipt。M6.3/M6.5 live、M6.4、M6.6、M6.7、Evidence promotion、Writer、Domain Judgment、provider/model、full-chain、business Case mutation 和 legacy authority change 均保持 blocked。

下一步仅能由总审计窗口独立复核 v4 package 与 incident remediation evidence；在获得新的明确审批前，不得运行 receipt registration、preflight 或任何 live CLI send。
