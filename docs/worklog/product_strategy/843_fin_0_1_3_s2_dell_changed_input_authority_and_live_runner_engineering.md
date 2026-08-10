# FIN 0.1.3 S2 DELL changed-input authority／live runner engineering

- 日期：2026-08-10
- 状态：zero-call engineering pass；authority not issued
- run scope：`FIN_0_1_3_S2_DELL_FIXED_PACK_MODEL_COMPARISON`

新增 authority 与 live runner 只复用已经 clean-proven 的 provider-neutral 13-node Runtime，不复制或修改节点逻辑。Authority 必须绑定 clean proof、新 input／Pack digest、当前 implementation、Project OS pass、DeepSeek Pro profile 和 exact-once admission；预算固定为 `1 case／13 fresh model nodes／13 provider calls／0 source／0 tool／0 retry／0 fallback／0 old node／0 promotion`。

Live runner 在 ledger reserve 前要求 clean/synced repository、implementation ancestor、authority 未消费、凭据仅 presence、Project OS 无 blocker、private attempt root 不存在。执行时完整保存每个模型可见 request、provider response、finish reason、usage 与 terminal；公开 result 只保留 digest／receipt／finding 摘要。旧报告只绑定为比较基线，不进入新请求；新运行内 direct baseline 与 Agent chain 同输入，但旧报告与新报告不是 same-input model A/B。

focused tests=`6 passed`，compile 与 diff check 通过；model/provider/source/network=`0/0/0/0`。下一步先提交并推送 runner，再签发一次 authority，提交 authority 后才能执行 live。任何 terminal failure 或新 L1 均按现有 stop rule 保留 capture 并停止，不自动生成第二份 admission。
