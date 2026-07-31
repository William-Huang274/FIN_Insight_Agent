# FIN 0.1 S2-T03 原生 JSON Schema response adapter

时间：2026-07-20

## 授权与边界

用户授权按已选方案实现原生 strict JSON Schema assistant response，并给出未绑定的模型偏好：GPT-5.6 优先、GPT-5.5 备选。本轮只实现 provider-neutral response adapter、OpenAI Responses 首个 wire binding、确定性 fixtures 和独立复核。没有读取、写入或持久化凭据材料，没有检查账户模型可用性，没有绑定 exact model、签发 admission 或发起 provider/model/执行网络调用，也没有进入 T04、S3、release 或 production。

## 实现结果

1. 新增 `fin01.bounded_agent.native_json_schema_response:v1`，Specialist 请求通过 Responses API `text.format.type=json_schema`、`strict=true` 承载现有闭合 v4 schema；不发送 `tools` 或 `tool_choice`，不执行外部工具。
2. 复用现有 candidate enum、native JSON object、duplicate-key、candidate/evidence 和 semantic validators；不接受 fenced JSON、本地 repair、未知 candidate 或 schema 外字段。
3. `completed` 只接受恰好一个 message 和一个 `output_text`；`incomplete`（含 token cap/content filter）、refusal、缺失或多个 message/content、未知 content type、空输出、decode、duplicate、非 object 全部为固定 typed failure。
4. Gateway event 只记录调用 metadata/status/usage，不记录 response output；执行器的成功 Artifact 和失败 observation 均不携带 raw provider response、raw output、refusal 文本或私有 reasoning。
5. 旧 DeepSeek strict-tool 适配器、既有 admission schema/digest 和 canonical terminal truth 保持不变；新 adapter 只能显式注入 executor，当前默认应用装配未切换，因而不会越过 admission 决策自动启用。

## 独立复核与修复

初稿把 OpenAI admission binding 放进了号称 provider-neutral 的 parser。独立复核后已拆分：`NativeJsonSchemaResponseAdapter` 只负责通用 schema request/normalized response parsing，OpenAI base URL、credential env 与 `model_ref` 一致性留在 executor 的首个 wire-binding 边界。随后补充 provider refusal 和 unknown candidate 两类 executor 级失败夹具，均证明只形成一次 Specialist receipt、Writer/Verifier 不运行、既有 `BoundedAgentExecutionError` closeout 生效且原文不进入 failure observation。

## 验证

- gateway + T03 focused：`62 passed in 3.97s`；
- S2-T01～T03 联合合同：`70 passed in 110.51s`；
- model/provider API/执行网络/external tool：`0/0/0/0`；
- 新 admission / actual execution：`0/0`。

实现依据与 wire contract 对齐 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)；exact model 仍须在后续 admission 前按官方当前模型合同与账户权限单独预检。

## 结论

Adapter 已达到 zero-call、executor-boundary、fixture-proven，并通过一次独立复核；这只关闭项目内 transport implementation gap，不代表 live provider compliance、closed v4 Agent Artifact、研究质量增量或 T03 通过。S2-T03 仍 failed，T04/S3/release/production 继续 blocked。下一项为 `S2-T03-NATIVE-JSON-SCHEMA-EXACT-LIVE-ADMISSION-DECISION`：只有用户另行决定后，才可检查账户模型可用性、选择一个 exact model、轮换并通过 credential gate、冻结预算/Case/input/fresh identity 并签发 admission；实际执行仍需再一次明确指令。
