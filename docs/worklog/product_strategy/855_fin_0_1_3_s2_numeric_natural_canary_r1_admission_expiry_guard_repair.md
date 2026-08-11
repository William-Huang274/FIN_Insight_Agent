# 855 — FIN 0.1.3 S2 numeric natural canary R1 admission 到期门禁修复

日期：2026-08-11

状态：R1 admission 已拒绝且永不执行；working-tree expiry guard 通过；待 clean/synced 后签 v1.1；未调用 DeepSeek

## 签发后发现了什么

live admission R1 成功绑定了提交、输入、请求、来源 SHA 和凭据存在性，并保持未消费、零调用。但签发后的独立审查发现 validator 只检查 `expires_at > issued_at`，没有在 runner 执行前把当前观察时间放进有效窗口。因此一份名义上 24 小时的 admission 在过期后仍可能被接受。

这属于 S2 live control plane 缺陷，不是 DeepSeek、不属于网络或研究内容质量。R1 的 issuance、admission 和 authority digest 全部保留；它明确被处置为 `rejected_unconsumed_never_execution_eligible`，不得改标、复用或执行。本轮 provider/model/network/source=`0/0/0/0`，凭据值未写入任何结果。

## 原地修复

validator 现在要求 authority 与 admission 的签发／到期时间完全一致，并在执行路径强制 `issued_at <= observed_at < expires_at`。not-yet-valid、恰好到期和到期后一秒均在 Provider callback 前 fail closed。issuer 和 runner 改为只读写 replacement `v1_1`，防止 R1 被未来流程误用。

相关及相邻回归为 `56 passed`，包含三项时间 mutation；Python compile 通过。当前仍只是 working-tree 工程结果。下一步提交推送后，才允许从新的 clean/synced HEAD 签发一份未消费 v1.1 admission；签发本身仍不授权 DeepSeek 调用。
