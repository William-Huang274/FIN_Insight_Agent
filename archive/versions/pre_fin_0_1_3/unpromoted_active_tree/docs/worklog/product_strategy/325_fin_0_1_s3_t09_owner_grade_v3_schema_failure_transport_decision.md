# FIN 0.1 S3-T09：owner-grade v3 首 Specialist schema failure 根因与 transport 决策

日期：2026-07-22

## 结论

用户以“授权”只允许 `S3-T09-OWNER-GRADE-V3-FIRST-SPECIALIST-SCHEMA-FAILURE-ROOT-CAUSE-AND-TRANSPORT-DECISION`。本轮没有模型、Provider execution、execution network、admission、Run、Artifact、comparison 或 Human Review。

最早项目内根因已经确认：DeepSeek Specialist 请求中的 `required_output_schema` 有 14 个顶层键，其中 7 个其实是 cardinality/字符/字节限制；请求同时声明 `additional_properties_allowed=false`，但本地 `_validate_specialist_output` 只接受另外 7 个真实输出键。也就是说，Provider-facing prompt contract 与 canonical validator 自相矛盾。真实失败只能证明 exact keys 或 Cell binding 不通过，不能把历史 raw output 或具体 missing/extra/cell-id subtype事后补写。

## Provider 合同与路线判断

复核 DeepSeek 当前官方 JSON Output、Tool Calls 和 Chat Completion 文档：`json_object` 保证合法 JSON，并要求 prompt 明确 JSON 和示例，但没有承诺符合应用 JSON Schema；Beta strict Function 声称 schema conformance，但本项目已经消费两次 strict 路线且没有 closed Artifact，Project OS 已冻结不得做第三次同路线尝试。

同仓库 S2 已有更强的实际证据：`deepseek_segmented_json_object:v1` 把 Specialist 与 Lead 变成较浅的独立输出，本地校验后确定性装配 canonical v4；真实 Run 以 4 次调用、retry=0 形成 9 Artifact。因此本轮不选择“修 prompt 后再试一次单体 v3”，不回 strict tool，也不把 OpenAI 作为当前主路线；选择 DeepSeek 分段 Specialist＋本地装配。

## 冻结的后续实现合同

下一实现保持 canonical `fin01.s3.bounded_agent_three_cell_output:v3` 和六个逻辑节点不变，只把每个 Specialist 分成三个 Provider segment：

1. facts / explanation / remaining gaps / terminal；
2. owner-grade Claim Cards；
3. actionable WWC tasks。

每段先按 exact Cell、authority、ID/ref 和闭合 keys 校验，本地再装配原七键 Specialist v3 对象，并复用现有完整 owner-grade validator；Lead/Writer/Verifier 合同暂不改。Provider-visible schema 只能包含真实输出字段，cardinality/length/byte 进入独立 `output_constraints`。安全 telemetry 只允许 missing / unexpected / cell-id 三个枚举子型和数量，不保存 raw output 或任意 Provider key 名。

实现阶段的上限冻结为 12 semantic/provider/network calls、16,200 output tokens、USD 0.10、每次 transport attempt=1、retry/fallback/repair/rerun=0。它只是实现/fixture ceiling，不是 admission，也没有授权任何 paid proof。

## 下一步与边界

当前唯一下一项为 `S3-T09-OWNER-GRADE-V3-DEEPSEEK-SEGMENTED-SPECIALIST-TRANSPORT-ZERO-CALL-IMPLEMENTATION`，需另行授权。实现必须有正例六逻辑节点/九 Artifact fixture，以及 unknown key、Cell mismatch、unauthorized ref、duplicate ID、later-segment-not-called 等 earliest-owner 负例；不得修改历史 v3 Run、静默 fallback、签发 admission、执行模型、比较 baseline 或进入 T10。
