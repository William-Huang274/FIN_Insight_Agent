# FIN 0.1 S2-T03 v4 Live Validation 决策

日期：2026-07-20
状态：`decision_complete / strict_tool_adapter_first / no_live_admission`

## 问题

v4 closed envelope 与 canonical execution identity 已完成 deterministic proof。下一项需要在“直接签发一次普通 `json_object` v4 admission”和“先采用 provider 强结构化输出”之间作出选择。

## 官方能力核验

- DeepSeek JSON Output 文档：`https://api-docs.deepseek.com/guides/json_mode/`。`response_format={"type":"json_object"}` 只保证合法 JSON，仍依赖 prompt/example，并明确存在偶发空 content；没有 nested key schema guarantee。
- DeepSeek Tool Calls strict mode：`https://api-docs.deepseek.com/guides/tool_calls/`。`https://api.deepseek.com/beta` + function `strict=true` 会由服务端验证受支持的 JSON Schema；所有 object 属性必须 required 且 `additionalProperties=false`。
- DeepSeek Chat Completion API：`https://api-docs.deepseek.com/api/create-chat-completion/`。named `tool_choice` 可强制指定函数，工具调用以 `finish_reason=tool_calls` 返回。

本地 `llm_gateway.chat_completion` 已能透传 `tools`、`tool_choice` 和 arbitrary base URL，也能返回 `tool_calls`；但当前 bounded executor 固定发送 `response_format=json_object`、读取 `message.content`、只接受 `finish_reason=stop`，因此 strict tool output 尚未接入。

## 决策

不签发普通 `json_object` v4 admission。先实现 `S2-T03-V4-STRICT-TOOL-ADAPTER`：

- beta base URL；
- 唯一 output-carrier function `submit_specialist_lead_result`；
- `strict=true`，所有 object required + `additionalProperties=false`；
- named `tool_choice` 强制该 function；
- 恰好一个 tool call、exact function name、`finish_reason=tool_calls`；
- 只解析 arguments 作为 v4 output，不执行任何外部工具；
- provider schema 只负责结构约束，本地 candidate ID、evidence boundary 与 semantic validator 继续 fail-closed。

理由：v2/v3 已各消费一次真实 provider call 且均因第一阶段输出形状失败。在官方已有 server-validated schema path 的情况下，再用 prompt-only `json_object` 运行会重复已知风险，而不是检验新的信息。

独立复核额外检查了 cardinality request contract。当前 DeepSeek 官方 Chat Completion 文档没有列出 `parallel_tool_calls`，因此不得因为本地 gateway 能透传该字段就假设 provider 支持；方案固定为 forced named tool，并在本地对 0 个、多个和错误名称调用全部 typed fail-closed。

## 边界

- 本轮 model/provider/network/external tool=0；
- 新 exact v4 admission=0；
- strict adapter implementation=0，deterministic proof=0；
- T03、T04、S3、RG1/RG3/RG4、release、production 均未通过或解锁。

只有 strict adapter 的确定性负例、secret-safe failure、canonical truth 与回归全部通过后，才进入另一项独立的 v4 admission 决策；不得把本决策解释为已经授权实际执行。
