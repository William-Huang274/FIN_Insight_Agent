# FIN 0.1 S3-T09 transport-v4 认知状态机零调用修复

日期：2026-07-22

## 授权与边界

用户以“授权”只批准 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V4-FIELD-LOCAL-EPISTEMIC-STATUS-STATE-MACHINE-AND-SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION`。本轮没有签发或消费 admission，没有调用真实模型、Provider、网络、来源或工具，没有新建真实 WorkUnit/Attempt/Run/Artifact，也没有重跑、paired comparison、Human Review、T10、S4、release 或 production 行为。

## 实现结果

新增独立 transport `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v4`。历史 v1/v2/v3、canonical `fin01.s3.bounded_agent_three_cell_output:v3` 和现有 strict local owner-grade validator 保持不变。

Claim Card 请求现在在字段旁携带 machine-readable 四状态矩阵：`fact_supported` 与 `bounded_inference` 必须有 support；`hypothesis` 必须有非空 qualification；`cannot_infer` 必须同时满足 `support_fact_ids=[]` 与至少一个非空 `cannot_support`。请求要求逐 Claim 做响应前 cross-field self-check，并禁止静默改 status、删除 support、捏造 boundary 或 coerce 字段来通过合同。

新增 `segmented_specialist_epistemic_status` closed telemetry，仅允许三个 cannot-infer 冲突子型：仍带 support、缺 cannot-support boundary、两者同时存在。terminal failure event 只保存 segment、field、subtype 和 failing count，不保存 raw Claim、fact IDs、boundary、item index、任意 key 或 private reasoning；逐字 Provider final assistant text 仍只通过 `fin01.s3.provider_output_capture.assistant_final_text_only:v1` restricted object capture 持久化和复盘。canonical allowlist 对夹带 raw Claim fail-closed。

## 确定性验证

fake Provider 使用完整生产 model view。合同测试覆盖四个合法状态、六逻辑节点/九 Artifact family/十二调用正例，以及三个 cannot-infer 冲突分支；负例均在第一 Cell 的 `owner_grade_claim_cards` 段、累计两次假 Provider 调用后 earliest-stop，Lead、Writer、Verifier 和 Artifact commit 均未执行。历史 transport-v3 请求仍不出现 v4 状态矩阵。

专项 v4 合同、canonical persistence/rejection、历史 v3 相邻回归、S3-T09 grouped regression、Python compile、JSON/JSONL、Project OS preflight、diff 与 secret scan 的最终数量记录在同名 release result contract；本文件不把 fake fixture pass 冒充真实 Provider conformant 或研究产品通过。

## 产品判断与下一项

项目内最早可控的状态机漏传已修复并 fixture-proven，但研究质量增量仍为 0：没有新的 Evidence、Numeric、Judgment、Report 或 Alpha，也没有完整 live owner-grade Artifact。因此 RC-P36-039 只推进到 `transport_v4_zero_call_fixture_proven_fresh_agent_proof_decision_pending_separate_authority`；RC-P36-037、T09、T10、S4、release 和 production 继续 blocked。

当前唯一下一项为 `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V4-FRESH-AGENT-PROOF-DECISION`，尚未授权。它只能零调用冻结 fresh identity、exact input、预算、nonreuse、first-failure stop 与 restricted output-capture binding；不能签发或执行。若未来 v4 再发生 Claim Card contract failure，停止 prompt-only v5，转 Provider-route disposition 或 defer T09。
