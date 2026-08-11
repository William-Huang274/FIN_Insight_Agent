# FIN 0.1 S3-T09 Owner-grade Writer-v2 live validation R1

执行日期：2026-07-23（Asia/Shanghai）

结论：未通过研究产品验收，但 capture/terminal 修复获得真实证明。Exact admission 只消费一次；执行在第 5 个 Provider 调用、Value/Profit Specialist claim-card 校验处 fail-closed，未到达 Memo Writer-v2。失败 Run 正确终态化，五份安全原始回答在 terminal failure 前受限持久化并可按 Run 回读，没有再次形成 orphan。

## 精确执行事实

- Admission：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-research-lead-v3-writer-v2-exact-admission-r1`
- Admission digest：`1dc1b3290bf19bf73e0ad90cb8d5be3e1e60bf71bf151129c913894e93256885`
- WorkUnit：`wu_p02_5_821cee42568e9454078c5104`
- Attempt：`attempt_fin01_d2279356bce93fb0d4035953`
- ResearchRun：`research_run_fin01_76a7eace510a50091c351502`
- Provider / model：DeepSeek / `deepseek-v4-pro`
- 调用：5 model / 5 provider / 5 network
- token：19,055 input + 2,372 output = 21,427 total
- 成本：USD `0.00968997`
- retry / fallback / rerun：`0 / 0 / 0`
- Artifact：0

## Canonical 与持久化事实

- WorkUnit / Attempt / ResearchRun：`failed / failed / failed`
- 事件：WorkUnit/Attempt start、lease、Run start、provider output captured、Run/Attempt/WorkUnit failed
- orphan：false
- 五份安全 final-assistant outputs 先写入 restricted object store，再由 `RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED` 与 Run 绑定
- 五份 capture 均完成 restricted readback；tracked release result 只保存 digest/ref，不保存回答正文
- 原始 HTTP envelope、credential 与 private reasoning 未持久化

## 首个可信失败

失败 stage：
`domain_specialist:value_and_profit_capture:owner_grade_claim_cards`

失败 code：
`s3_bounded_segmented_specialist_contract_invalid:value_and_profit_capture:owner_grade_claim_cards:s3_owner_grade_claim_scope_exceeds_fact_authority`

受限原文复盘显示，Claim `c2` 有直接 Numeric/Fact 支持，但 Claim 输出 period=`FY2025`，其支持 authority 的精确 period=`FY2025-FY`。公司实体、company-total business scope 与 attribution 其余一致。当前合同要求模型不得改写 deterministic authority token，因此 validator 的 fail-closed 是正确的；不能为了让本次回答通过而静默归一化。

## 产品判断与边界

本轮真实证明了两个修复效果：失败回答不再因 terminal telemetry 问题丢失，Run 也不再残留为 running orphan。它没有证明 Writer-v2 的真实效果，因为执行在上游 Specialist 已停止；也没有形成研究 Artifact，不能进入 paired comparison 或 owner acceptance。

下一项只能是另行授权的零调用根因决策：
`S3-T09-OWNER-GRADE-SPECIALIST-CANONICAL-SCOPE-TOKEN-ZERO-CALL-ROOT-CAUSE-DECISION`。
在该决策前不得再次调用、rerun、normalize、patch、签发 replacement admission 或进入 T10/S4/release/production。
