# FIN 0.1 S3-T09 profile-v3 final exact-live 硬失败

时间：2026-07-24（Asia/Shanghai）

用户授权按冻结顺序执行，并明确只有一次 final exact-live。Project OS scoped preflight、fresh identity、exact input、credential presence、retry=0、12-call/16800-token/USD 0.10 上限和零 source/tool/business write 均通过；admission digest `e3db9ce6…add12` 随后 exact-once 消费。

Run 在第 5 次调用的 Value/Profit Specialist Claim Card 硬失败。两个 Claim 的六个 `support_fact_ids` 全部是上游 Fact 的底层 Numeric refs，零个是要求的本地 Fact ID；validator 以 `s3_owner_grade_claim_support_fact_unknown` 正确 fail-closed。该回答为 valid JSON、finish reason=stop，没有新增无支持事实或精度，但 Claim → Fact identity layer 错误。Prompt 已写明 exact validated fact_id，故 DeepSeek semantic mapping failure 成立；同时 model view 暴露多层 ref 而无字段级闭合 Fact alias allowlist，存在项目稳健性缺口。

三态 `failed/failed/failed`、orphan=false、Artifact=0；calls=`5/5/5`，tokens=`20072/1801/21873`，cost=USD `0.0096356`，retry/fallback/rerun=`0/0/0`。五份回答和 receipts 均先受限持久化并 5/5 回读。

按停止合同不做第二次执行、patch、paired comparison、T10 或 cross-slice acceptance manifest。profile-v3 未在 live 链路到达，因此 RC-P36-047 只保持 zero-call fixture repaired；新增 RC-P36-048 记录 Claim-Fact identity-layer hard failure。

下一项是 `S3-T09-FINAL-HARD-FAILURE-DISPOSITION-DECISION`，需要 owner 决定 blocked closeout/carry-forward，或重新授予 generalized `ClaimFactLinkPolicy` 与新 proof 预算。
