# FIN 0.1 S2-T03 v4 Parse-Subtype Telemetry Repair

日期：2026-07-20
状态：`fixture_proven / zero_call / T03_still_failed`

## 授权与目标

用户批准在已消费 v4 terminal failure 后做一次零调用、无正文的解析子类型遥测修复。授权不包含模型、provider、网络、新 admission、parser 放宽、重试、T04 或任何下游推进。

## 实现

- 通用 durable failure code 保持 `bounded_agent_strict_tool_arguments_invalid_json`，不破坏既有 canonical failure contract。
- 未来失败新增固定白名单 subtype：`json_decode_error`、`duplicate_key`、`non_object`。
- Telemetry 只写固定 parser contract，以及 raw arguments、digest、length 均未持久化的布尔事实。
- 独立复核发现任意 `Mapping` 型 telemetry 参数可能为未来正文泄漏留下入口，已收紧为仅接受 subtype 的专用参数，由异常对象集中生成闭合字段。
- Native JSON parser 没有放宽：fenced JSON、重复键和非 object 仍在 Artifact commit 前 fail-closed。

## 验证

- Parser 单元夹具分别覆盖 JSON decode、fenced JSON、duplicate key 与 non-object。
- 完整 transport failure matrix 验证三种 subtype、其他失败不出现该 telemetry，并用唯一敏感片段证明 arguments 原文不会进入 serialized failure observation。
- Focused T03：`39 passed in 2.39s`。
- T01+T03 contract：`44 passed in 2.10s`；相关 Runtime/S1/S2/Workbench：`76 passed in 56.76s`；补充 Agent/Skill/LangGraph：`68 passed in 40.07s`，三组无失败。
- 本轮 model/provider/network/external-tool calls=`0/0/0/0`，新 admission=`0`。

## 独立复核结论与边界

修复通过：分类是向前生效的 secret-safe observability 增量，不改变 parser、semantic validator、Artifact commit 或 consumed-identity guards。已消费 v4 Run 没有保存 raw arguments，因此具体 subtype 仍不可重建，不能用新夹具事实改写历史 Run。

S2-T03 继续 terminal failed，S2-T04/S3/release/production 继续 blocked。下一项仅为 `S2-T03-POST-TELEMETRY-PROVIDER-STRATEGY-DECISION`；任何 provider strategy change、新 exact admission 或真实执行都需要单独授权。
