# FIN 0.1 S2-T03 v4 Strict Tool Adapter

日期：2026-07-20
状态：`deterministic_fixture_proven / no_live_admission / T03_still_blocked`

## 授权与目标

本轮只执行 `S2-T03-V4-STRICT-TOOL-ADAPTER`：把已冻结的 DeepSeek `/beta` strict named-function 方案接入现有 bounded executor，并用 deterministic fixture 证明成功、失败和 secret-safe truth。没有签发 v4 admission，也没有获得 model/provider/network、T04、S3、release 或 production 权限。

## 实现结果

- Specialist 精确要求 `deepseek / deepseek-v4-pro / deepseek:deepseek-v4-pro / https://api.deepseek.com/beta`，不匹配时在 provider 前 typed fail-closed。
- 使用唯一 output-carrier function `submit_specialist_lead_result`；`strict=true`，每个 object 的全部 properties 均 required 且 `additionalProperties=false`，candidate IDs 绑定为本次 input enum。
- 使用 forced named `tool_choice`，不发送官方合同未列出的 `parallel_tool_calls`；本地要求 `finish_reason=tool_calls`、空 message content、恰好一个 exact-name function call。
- 只解析 function arguments，不执行任何外部工具；manifest/trace 明确记录 transport ref、strict schema requested 和 external tool executed=false。
- strict arguments 直接进入 v4 closed envelope与既有 candidate/evidence/semantic validator，不经过历史无损 normalizer。Writer/Verifier 仍使用 `json_object`。
- request cost projection 纳入 tools、tool choice 与 response format 的序列化体积；usage、cost、retry=0、failure truth 和 secret boundary 保持原合同。

## 独立复核与修复

第一版复用了可清理 fenced JSON 的通用 parser，这会把 provider-native strict arguments 的格式偏差静默接受；标准 JSON decoder 对重复 object key 也会后值覆盖。已改为专用 native-JSON parser：围栏 JSON、duplicate keys、非 object、空 arguments、0/多 call、错误 finish/name/schema 全部 typed fail-closed，并且失败记录不持久化 raw arguments、secret 或私有推理。

## 验证

- 聚焦 strict adapter 合同：`32 passed in 1.67s`。
- LLM gateway + Runtime + S1 + S2 + Workbench 相关回归：`91 passed in 84.85s`。
- model calls=0；provider calls=0；network calls=0；external tool executions=0。
- 新 exact v4 admission=0；live validation=0；Artifact/真实业务 Case 写入=0。

## 产品与研究结论

产品能力增量仅为：v4 Specialist+Lead 输出现在有一个 fixture-proven、结构闭合、不会执行工具且 fail-closed 的 provider adapter。研究质量增量为 0，因为没有真实模型输出或研究 Artifact。该结果不等于 DeepSeek live compliance、不等于 T03 pass，也不解锁 T04。

下一项固定为 `S2-T03-V4-LIVE-ADMISSION-DECISION-AFTER-STRICT-ADAPTER`：必须由用户另行决定是否签发一份全新的 exact v4 admission，并显式冻结 model/provider/network/cost authority；不得复用 v1/v2/v3 identity 或自动执行。
