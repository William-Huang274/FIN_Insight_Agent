# FIN 0.1 S2-T03 GPT-5.6 Sol native live validation HTTP 429

日期：2026-07-20
状态：`terminal_failed / admission_consumed / T03_still_failed`

## 执行

用户明确授权消费此前签发的 v5 exact admission 一次。执行前，正式 T03 + Project OS contracts=`73 passed`，最终零调用 preflight 再次确认 digest、fresh identity、同一 Case/input、3 candidates、OpenAI native JSON Schema transport、reasoning=`medium`、retry=0 和 USD 0.25 cap 未漂移。

随后仅执行一次 Specialist provider call；没有 retry、fallback、第二次运行、T04 或下游扩张。

## Canonical 结果

- 1 WorkUnit / 1 Attempt / 1 failed ResearchRun / 0 Artifact。
- WorkUnit：`wu_p02_5_d2f329725f5b8af48813f91e`。
- Attempt：`attempt_fin01_cf3852087cc52386d3108d04`。
- Run：`research_run_fin01_17bf9f5ab4bcb68150e6e895`。
- Terminal reason：`bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:provider_failure`。
- OpenAI `/v1/responses` 返回 HTTP 429；1 model/provider/network call，1 transport attempt，latency=2341 ms，tokens=0，estimated cost=USD 0.0。
- source network=0、external tool=0、Writer=0、Verifier=0、fallback/retry/rerun=0。

Canonical WorkUnit、Attempt、ResearchRun 全部 terminal failed，无 orphan。Raw response、credential value 与 private chain of thought 未持久化。

## 判断

本次失败发生在 provider admission 阶段，未收到 structured output，因此不是 JSON Schema 输出、模型 JSON 内容或本地 parser failure。安全 gateway event 只保留 HTTP 429，没有具体 OpenAI error code/message，无法从 durable evidence 区分余额/配额/支出上限与普通 rate limit；不得臆测。

代码审计还确认一个独立的项目内 precision gap：Responses gateway 为避免回显输入而只保留 HTTP status，没有像 typed telemetry 那样安全提取 provider error `type/code`，因此 durable root-cause classification 被压扁为 429。该缺口只授权记录，未授权本轮修复。

Admission ID 与 WorkUnit key 已加入 consumed guards，禁止直接复用。T03 继续 failed，T04/S3/release/production blocked。下一项冻结为 `S2-T03-OPENAI-HTTP-429-BILLING-RATE-LIMIT-AND-SAFE-SUBTYPE-TELEMETRY-DECISION`；应先核对平台 billing/limits，并决定是否做零调用 allowlisted subtype telemetry，再考虑任何新 admission。当前不授权重跑。

Post-run gateway + S2-T01/T02/T03 + Project OS regression=`91 passed in 96.23s`。真实 v5 reuse preflight 在 provider 前返回 `t03_consumed_admission_reuse_forbidden`，gateway events 保持 `2→2`。
