# FIN 0.1 S4-T06：MU R5 fresh exact admission issuance

日期：2026-07-30<br>
状态：admission 已签发、未消费；exact-live authority 待独立决策

## 目标与边界

根据 486 authority，仅将 fresh proof 中 digest=`3457fded...bd6e8` 的 frozen payload 原样物化为 R5 admission。当前步骤不读取凭据，不消费 admission，不启动 supervisor，不调用 DeepSeek，不生成 WorkUnit、Attempt、Run、Artifact，不做 paired assessment、owner acceptance 或 T07。

## 签发结果

- admission：`configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_and_material_numeric_classifier_fresh_exact_admission_r5.json`
- admission SHA256：`1f49070ddce794ebf097abed4cd07cec2675d85822a0d7a8547236460c5fbff7`
- admission digest：`3457fded0bd72b4df5d1fd6a1529bf7bfb8055681c388808b5d3e01a5dbbd6e8`
- issuance：`configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_and_material_numeric_classifier_fresh_exact_admission_r5_issuance_v1_0.json`
- issuance SHA256：`c91136b3478fe04a1e2a3ca7e863ac8cbb9d3f99446a0c6b0db884fa3a59fe05`
- issuer：`scripts/releases/issue_fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_and_material_numeric_classifier_fresh_exact_admission_r5.py`

绑定保持：

- `deepseek / deepseek-v4-pro / https://api.deepseek.com/beta`
- capture v2、material-numeric classifier v2、current-case identity v2
- Specialist-v7、Research Lead-v7、Writer-v3、output-v4
- `12/12/12 calls / 16800 output tokens / USD 0.10 / retry 0`

## 重验

- scoped Project OS：pass，open blocker=`0`
- 双 disposable fresh proof：重新运行且与 frozen proof 相等
- authority/proof/implementation/4 runtime bindings：match
- R4 admission/failure：immutable
- schema/profile、payload round-trip、runner-load：pass
- fresh WorkUnit/Attempt/Run rows：`0/0/0`
- Provider callback、credential check、model/network/source/tool calls：`0`
- issuance focused（账本同步前）：`4 passed / 1 deselected`
- issuance focused（账本同步后）：`5 passed`
- S4-T06 当前完整回归：`236 passed / 1771 deselected`
- 下一 authority scope Project OS：pass，open blocker=`0`
- broad full-chain Project OS：按预期被 RC-P36-067/068/080/081 四项阻断
- release JSON：`360 valid`
- Project OS JSONL：`24 files / 1362 rows valid`
- 历史用户 key 片段仓库命中：`0`

proof 运行中出现的 `provider_interaction_audit_capture_contract_invalid` 是主动负向 fixture 的预期 fail-closed 日志，发生在 disposable runtime；签发器终态成功，目标 runtime 未被写入。

## 下一步

`S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

下一项仍为零调用 authority。只有 authority 与 runner preflight 独立通过后，未来步骤才可能 exact-once 消费 admission。首个新 L1 停止，不自动进入 R6。
