# FIN 0.1 S3-T09 profile-v3 final exact-live validation

时间：2026-07-24 01:05（Asia/Shanghai）

## 结论

唯一获授权的 final exact-live 已 exact-once 消费并可信终止，但没有通过 S3-T09。失败发生在第 5 次调用的 Value/Profit Specialist Claim Card，而不是刚修复的 Research Lead narrative quality 分级；因此 profile-v3 在真实链路中尚未到达。

三态为 `failed / failed / failed`，orphan=false，Artifact=0。真实 model/provider/network calls=`5/5/5`，tokens=`20072/1801/21873`，estimated cost=USD `0.0096356`，retry/fallback/rerun=`0/0/0`。五份 assistant final text 与 receipts 均先受限持久化并 5/5 回读；source network、external tool、live Case head write 均为 0。

## 硬失败复盘

Value/Profit facts segment 正常产生两个本地 Fact。随后两个 Claim 的 `support_fact_ids` 共六个值，全部复制了这两个 Fact 底层的 Numeric support refs；零个值等于应使用的本地 `fact_id`。本地 validator 因此正确报：

`s3_owner_grade_claim_support_fact_unknown`

这不是 JSON 失败、精度编造或 Research Lead 320/512 问题。它是 Claim → Fact 链接选择了错误身份层：模型把“Fact 的来源引用”当成了“Claim 支持的 Fact ID”。

Provider-visible schema 已写明 `exact validated fact_id`，所以 DeepSeek 的语义映射错误成立；但工程侧仍有稳健性缺口：claim-card view 同时暴露 local Fact ID 与底层 Evidence/Numeric ref，却没有字段级闭合 Fact alias allowlist。若未来另行授权，泛化方向应是共享 `ClaimFactLinkPolicy`：Provider 只从 request-local `F001/F002` 中选择，本地扩展回 canonical Fact ID；底层 source refs 保留在 Fact lineage，但不进入 Claim link 的选择表面。不得用模糊匹配或静默改写本次回答。

## 阶段处置

按“任何新硬完整性失败即停止”的冻结规则，本轮不做第二次调用、不补 patch、不做 paired comparison、不进入 T10，也不生成仅在 T09 acceptance 后到期的跨 Slice manifest。

当前 S3-T09 仍 blocked。下一项只能是 `S3-T09-FINAL-HARD-FAILURE-DISPOSITION-DECISION`：由 owner 决定是以 blocked 状态收口 S3 并把 generalized Claim-Fact linking 修复带入后续，还是重新授予一次新的修复与 proof 预算。Codex 不代签 owner acceptance。
