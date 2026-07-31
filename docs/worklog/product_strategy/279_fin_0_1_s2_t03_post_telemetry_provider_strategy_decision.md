# FIN 0.1 S2-T03 Post-Telemetry Provider Strategy Decision

日期：2026-07-20
状态：`decision_complete / zero_call / r2_admission_not_issued`

## 问题

v4 strict-tool live Run 已以 `bounded_agent_strict_tool_arguments_invalid_json` terminal failed，随后向前补齐了 secret-safe parse-subtype telemetry。当前需要决定：立即改变 provider 输出策略，还是保留 strict-tool 并建议一次全新 exact admission。

## 核验

- DeepSeek 当前官方 Tool Calls 合同仍声明：`/beta`、`strict=true`、合规 JSON Schema 是其 schema-constrained Function Calling 路径。
- 官方 JSON Output 合同只保证 `json_object` 为合法 JSON，仍依赖 prompt/example，并明确可能返回空 content；因此它不比 strict-tool 更适合 closed v4 envelope。
- 本地 request 精确发送 beta base URL、唯一 strict function 和 forced named tool，未发送未采用的 `parallel_tool_calls`。
- Provider outer response JSON 已成功解析，gateway 对 `tool_calls` 和 `function.arguments` 只做原样透传；未发现项目内转义、flatten、normalizer 或二次序列化根因。
- 普通 JSON 已有两次真实 shape failure；strict named-tool 只有一次 live failure，而且历史 arguments 未持久化，具体 subtype 无法恢复。新 subtype telemetry 已 fixture-proven，可使下一次结果具备判别力。

## 决策

保留 DeepSeek beta strict named-function transport，不退回 `json_object`，暂不切换 provider，不放宽 native JSON parser。建议的下一步仅是：在用户另行明确要求后，签发最多一次全新、带 subtype telemetry 的 r2 exact admission。

r2 必须保持同一 Case/version/input digest/candidates、v4 output contract 与 strict transport；使用 fresh admission ID、fresh WorkUnit key、fresh isolated root；最多 3 semantic/provider/network calls、每次 1 transport attempt、retry=0、USD 0.05；source network、external tool、live Case head write 和 raw arguments persistence 继续关闭。

## Stop Rules

- 本决策不签发 admission，也不授权实际执行。
- r2 若再次出现任一 parse subtype，必须 terminal fail 并停止；在任何第三次 strict 尝试前转向 provider-transport pivot/escalation。
- Specialist 若成功但后续节点失败，只修最早已证明的节点，不自动重放前序成功节点。
- 即使 Run 成功，也必须先审查 Artifact、证据边界和研究价值，不能自动通过 T03 或进入 T04。

## 结果与边界

机器决策：`configs/releases/fin_ia_0_1_s2_t03_post_telemetry_provider_strategy_decision_v1_0.json`。Contract 回归：T01+T03=`45 passed in 2.78s`。本轮 model/provider/network/external-tool/new-admission/actual-execution 均为 0。

下一项为 `S2-T03-V4-R2-EXACT-ADMISSION-ISSUANCE-DECISION`。S2-T03 仍 failed，S2-T04/S3/release/production 继续 blocked。
