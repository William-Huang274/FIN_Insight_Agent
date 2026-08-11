# FIN 0.1 S2-T03 R2 后 provider transport pivot 决策

时间：2026-07-20

## 授权与边界

用户以“继续”授权当前冻结项 `S2-T03-POST-R2-PROVIDER-TRANSPORT-PIVOT-DECISION`。本轮只做证据复核和机器决策合同：没有实现 adapter，没有配置或读取凭据，没有绑定模型，没有签发 admission，没有发起模型/provider API/执行网络调用，也没有进入 T04、S3、release 或 production。为核对时效性能力，只读取了 OpenAI 与 DeepSeek 官方文档；这不属于 FIN 执行链的 provider 调用。

## 独立复核结果

1. 普通 `json_object` 路线在 v2/v3 已分别出现第一阶段 shape failure；DeepSeek 官方合同只承诺合法 JSON，不能证明 FIN v4 精确 schema。
2. DeepSeek beta strict named-function 在 r1/r2 都到达 `tool_calls`，但两次均未形成 closed v4 output 或 Agent Artifact；R2 的项目内 terminalization 缺口虽然已经修复，历史 subtype 仍不可重建，也不能据此合理化第三次同路线试跑。
3. 本阶段实际需要的是“结构化回答”，不是“请求应用执行函数”。OpenAI 官方 Structured Outputs 把二者分开：回答可通过 Responses API 的 `text.format` 使用 strict JSON Schema，并为 refusal、incomplete、缺失 output 等提供可分型的响应状态。
4. 因此选择 provider-neutral 内部 transport `fin01.bounded_agent.native_json_schema_response:v1`，首个 provider/API 候选为 OpenAI Responses Structured Outputs；精确模型、base URL、credential env、价格与调用预算暂不冻结，必须在后续 exact admission 中单独绑定。

## 冻结的 adapter 边界

- 复用现有 `specialist_lead_output:v4` 闭合 schema，不发送 tool 或 tool choice，不执行外部工具；
- 保留 native JSON object、duplicate-key、candidate/evidence 与 semantic validators；
- refusal、incomplete、缺失或多个 message output、parse/schema/semantic failure 全部 typed fail-closed；
- 不持久化 raw provider response，也不在失败时持久化 raw output text；
- 禁止自动 fallback、retry、rerun 和从新 transport 回退到旧 strict function/json_object；
- 先做纯 deterministic adapter fixtures，之后才允许另行决定 provider/model/credential/budget admission，实际执行还需再一次明确指令。

## 拒绝的方案

- 第三次 DeepSeek beta strict named-function：违反既定 stop rule，且前两次没有闭合产物；
- 退回 DeepSeek `json_object`：合同更弱，无法解决已观察到的 shape drift；
- 本地放宽 parser 或“修复” provider JSON：会掩盖 transport 不符合并可能改写金融研究语义；
- 立即切 provider 并实跑：当前没有 adapter、凭据 gate、模型绑定、预算和 fresh admission 权限。

## 验证

- T03 决策与历史合同：`44 passed in 6.39s`；
- S2-T01～T03 联合合同：`57 passed in 95.50s`；
- Project OS preflight：`6 passed in 0.36s`；
- JSON/JSONL 全量解析与 `git diff --check`：通过。

## 结论

Transport pivot 决策通过，但这不是 T03 通过。S2-T03 仍 failed，T04/S3/release/production 继续 blocked。下一项冻结为 `S2-T03-NATIVE-JSON-SCHEMA-TRANSPORT-ADAPTER-IMPLEMENTATION-DECISION`；当前 implementation、credential、model selection、admission 和 execution 均未授权。
