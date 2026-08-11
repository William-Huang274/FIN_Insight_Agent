# FIN 0.1 S3-T09 原始回答持久化与 epistemic-status 根因决策

日期：2026-07-22

## 授权与边界

用户要求先把原始回答持久化，使后续失败可以持续复盘，再执行当前下一项。本轮因此先实现 future-run Provider 输出审计合同，再完成 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-EPISTEMIC-STATUS-STATEMENT-CONFLICT-RESULT-AND-ROOT-CAUSE-DECISION`。没有调用模型、Provider、网络，没有签发/消费 admission，没有新 live WorkUnit/Attempt/Run/Artifact，也没有重跑、比较、Human Review 或进入 T10/S4/release/production。

## 原始回答持久化结果

每次 Provider 调用现在在本地 parse/semantic validation 前捕获最终 `assistant content` 字符串。成功和失败路径都会把它交给 Runtime；Facade 将正文写入 content-addressed canonical object store，terminal Run event 只存 policy、stage、call id、provider/model、digest、对象引用与访问/保留类别。读取必须经内部 `read_research_run_provider_output_captures`，并重新校验 object digest、Run lineage、sequence、call id 和无 private reasoning/raw-envelope 标志。

该合同明确不保存 HTTP response envelope、header、credential、request prompt 或 reasoning content。历史 transport-v3 Run 在该能力存在前已结束，正文不能恢复或伪造回填；只能保证未来 Run 可逐字复盘。旧 admission digest 通过“字段未显式出现时不进入历史 digest”保持兼容；未来 admission 必须显式绑定 `fin01.s3.provider_output_capture.assistant_final_text_only:v1`。

确定性测试证明：失败事件不含正文，引用可逐字读回；夹带 raw Provider envelope 会 fail-closed；成功的 12-call fixture 按 1..12 序列完整携带正文；semantic failure 的已完成调用同样保留。

## 零调用根因结论

历史安全证据只能证明 Value/Profit claim-card 命中 `s3_owner_grade_epistemic_status_statement_conflict`。本地条件只有三种可能：`cannot_infer` 仍带 `support_fact_ids`、`cannot_support=[]`、或两者同时发生。由于旧 Run 没有正文，不能指出具体 Claim、字段值或分支。

代码审计发现最早项目可控缺口：validator 明确要求 `cannot_infer => support_fact_ids=[] AND cannot_support 非空`，但 transport-v3 Provider 可见 schema 只把 `support_fact_ids` 描述成“exact validated fact_id”，只说明 `cannot_support` 对 cannot_infer 必需，没有给出“support 必须为空”的跨字段条件，也没有闭合的 per-status state matrix 或响应前 cross-field self-check。模型直接输出不合规是直接原因，但项目让模型猜一个未显式传达的状态机，因此不能把根因归为 DeepSeek-only。

## 选定后续与停止线

下一实现应新增 immutable transport v4，历史 v1/v2/v3 与 local output-v3 validator 均不变。请求在 Claim Card 字段旁给出 machine-readable epistemic-status matrix；`cannot_infer` 必须 `support_fact_ids=[]` 且至少一个非空 `cannot_support`；禁止静默改 status、删 support 或补 boundary。closed telemetry 只区分三个 cannot-infer 冲突子型和数量，事件仍不含正文；完整正文只经 restricted object capture 复盘。

未来 transport-v4 fixture 通过后，仍需独立 proof decision、issuance 和 exact-once execution 授权。若 v4 再出现 claim-card 合同失败，停止 prompt-only v5，转 DeepSeek provider-route disposition 或 defer T09。即使 transport 通过，也仍需九 Artifact、paired comparison 和 owner acceptance 才能通过 T09。

验证结果：capture/decision/transport 专项 `17 passed`；除超慢 live-runner 文件外的完整 S3-T09 `195 passed`；与本次直接相关的 live-runner terminal-failure/nonreuse 用例 `1 passed in 105.14s`；历史 admission/digest 相邻合同 `21 passed`。完整 live-runner 文件因四次 full canonical prepare 超过单命令预算，没有冒充全文件通过。JSON/JSONL 解析、Python compile 与 `git diff --check` 均通过。

当前下一项为 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V4-FIELD-LOCAL-EPISTEMIC-STATUS-STATE-MACHINE-AND-SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION`，尚未授权。
