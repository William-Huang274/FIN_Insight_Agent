# 192 P38 Point 01 M6.3/M6.5 v4 Single Fixed NVDA 10-K Live Pilot

日期：2026-07-13

## 决策与范围

总审计窗口以 `approve_m6_3_5_v4_single_fixed_nvda_10k_live_get_only` 批准一次且仅一次的 SEC Archives GET。审批绑定 v4 package `724bb947df735fc5392c038a978bdc6135a434baad66538b747b43279fe2cd0c`、manifest `18f510b0a0adb20b9e56b6f4d55498728dea0928f9b0f0c3cb3537085fc7e6ea`、scope `db2da6cf08a16d69636f61c680263440a6b7d7bd2d1f5f1a3c72d11b0362faf6`，目标固定为 NVIDIA 2025 10-K 的 approved SEC Archives path。

在 send 前的只读检查中，current UTC、receipt active/unconsumed、expiry、reviewer william/003、store identity、exact package/scope、capability/budget one-call policy 均通过。process-local SEC User-Agent 只在此 live CLI process 中设置；没有输出或持久化其明文。

## 结果

| 项目 | 结果 |
| --- | --- |
| HTTP / external / tool | `200` / `1` / `1` |
| retry / fallback / model | `0` / `0` / `0` |
| fixed receipt | `approval_point01_m6_3_5_nvda_10k_incident_isolation_refreeze_global_one_shot:v2`，`consumed` |
| invocation | `sec_document_invocation_8951234b49a7b1c6281cae52:v5`，`succeeded / positive_chain_persisted` |
| source SHA-256 / bytes | `dae19486be264fd26eb00a7f920dc641041a261c81bc8c03b678eea947de4856` / `2067520` |
| coordinate | `table[21]/row[3]/period_group[3:9]/value_column[4]` |
| fact | Revenue `130497`，`USD_millions`，`2025-01-26` |
| temporary store writes | `9` |

candidate、parser、normalized fact 与 numeric trace 各一条，均分别为 `unpromoted_candidate`、`parsed_unpromoted`、`unpromoted_numeric_fact`、`unpromoted_numeric_trace`。raw HTML 与 User-Agent 明文未持久化；[live audit result](/D:/FIN_Insight_Agent/data/manifests/point01_m6_3_5_v4_single_fixed_nvda_10k_live_pilot_result_v1_0.json) 只保留 source metadata/hash、receipt、lineage 与 unpromoted artifacts。

## Incident 隔离

v3 incident 的 HTTP 200/quarantine artifacts 没有被本次 runtime 输入、修补或晋升。v4 本次独立请求得到相同 source hash，表示命中同一固定公开文件，而非复用 incident response。

## 停止点

当前状态：

```text
v4_single_live_pilot_completed_audit_pending_no_downstream_authority
```

本结果只证明单文档、一次性、receipt-bound retrieval/parser 的可审计终态，不能称为 M6.3/M6.5 full/calibrated 或 M6 complete。不得自动进入 M6.4/M6.6/M6.7、Evidence promotion、Writer/Judgment、模型/full-chain、业务 Case mutation 或 legacy authority change。下一步必须先由总审计窗口审阅 live artifact。
