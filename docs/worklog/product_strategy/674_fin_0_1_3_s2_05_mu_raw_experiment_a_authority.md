# 674 — FIN 0.1.3 S2-05 MU raw Experiment A authority

日期：2026-08-07

状态：`closed / authority committed and consumed once / superseded by worklog 675 result`

> 后续：本 authority 已在 commit `ddbaf2cd...c208` 上签发并 exact-once 消费；结果见 `675_fin_0_1_3_s2_05_mu_raw_exact_live_and_s2_06_boundary.md`。下文保留签发前事实，不改写为运行结果。

## 目标

在 DELL raw 已完整但质量失败后，继续测量 MU 的自然 raw 表现，同时避免把 DELL 的失败分析、纠错文本或 hidden Gold 泄漏给 MU。该动作是同一 Experiment A 的第二个独立案例，不是 DELL correction，也不是 S2-06 三案收口。

## 审计结论

- MU model-visible input 为 `11 Evidence / 3 derived numeric / 4 explicit gaps`，case digest=`c11bbfab...6393`；
- runtime、production entrypoint、policy 和 blind input 与 DELL layered raw 的模型可见合同相同；
- Evaluator v1.1 的修改发生在模型返回后的评分层，没有改变 prompt；
- Project OS `separate_MU_raw_admission_authority_decision` scope 与 production preflight 均通过；
- `DEEPSEEK_API_KEY` 只检查 presence=true，未读取或保存值；
- 当前仓库 clean/synced at `a56f24a1...d00eb`。

## 权限边界

只允许一份 MU admission、一次 exact-once execution、DeepSeek Pro、最多 12 calls、0 retry、0 fallback。raw capture-first，完整链后用 evaluator v1.1 评分；S2-05 永远不做 business promotion。DELL/NVDA admission、supervisor correction、corrected candidate 和 automatic next-case 均未授权。

MU 的 Provider request 只能来自冻结 model-visible blind input。DELL raw output、26-row correction ledger、S2-06 materialized runtime 和 evaluator-only hidden targets均不可见。完成 MU 后必须先保存 terminal/captures、形成独立 MU supervision boundary，再停在 NVDA authority 之前。

## 本轮完成与验证

- 新增 MU authority JSON、专用 Git-ignored issuer 和四项合同测试；
- issuer 在签发前校验 decision digest、S2-06 campaign guard、Git clean/synced、所有 frozen bindings、MU case digest 和凭据 presence；
- focused authority/entrypoint/S2-06=`12 passed`，S2-05/S2-06 broader=`74 passed`；compileall、JSON 和 diff check 通过；
- 模型、Provider、网络、admission、execution=`0/0/0/0/0`。

下一步是提交推送本 authority slice；随后签发一份 MU admission，重新跑 scoped execution preflight，只有仍为 green 才 exact-once 消费。
