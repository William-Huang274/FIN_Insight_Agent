# FIN 0.1.2 S2-T04：盲配对 assessment 权限与独立性协议

日期：2026-08-03

## 结论

T04 的六份公平输入已经齐备，但当前任务不能诚实承担“盲评”：它已经看到 Flash/Pro 映射，也已经记录过两者的方向性差异。若继续由同一上下文打分，评分表即使完整，也不能证明模型身份没有影响判断。

本轮因此只完成零调用权限与范围决策，不评分、不选模型、不关闭 S2。新增项目内问题 `RC-P36-104`，所有者是评估治理，不是 DeepSeek 或 Provider。

## 已冻结的执行方式

下一项一次性获得以下权限，无需再插入一个同类 authority decision：

1. 从六份 hard-integrity pass capture 生成三 family、两候选的去身份化 packet；原始失效的 WWC pair 永不进入评分。
2. 用随机且跨三 family 一致的两个 opaque label；映射单独存入受限、内容寻址对象，公开 packet 只带 commitment digest。
3. packet 排除模型/候选/调用身份、receipt、路径、可交叉查询的 digest、延迟、tokens、成本、生命周期与此前方向性观察。
4. 评分者必须是未接触映射和本任务历史的新 Codex task 或人工评审；当前任务无资格评分。
5. 每个 family、candidate 在证据相关性、认知纪律、决策有用性、简洁信息密度四项各打 0–2 分，并给出 packet 行或 alias 依据。
6. 完整评分记录先校验、冻结并取 digest，之后才允许解盲。解盲后才应用 StagePlan 的稳定版优先规则，并查看成本、延迟和 preview 生命周期。

## 模型与本地 surface 边界

为避免看到分数后临时改口径，本轮额外冻结 per-family 保留阈值：总分至少 4/8，且证据相关性、认知纪律、决策有用性各至少 1 分。未达标的 family 不因全局候选胜出而强行交给模型，而是转为本地确定性 ownership 或 honest block。若最终候选三个 family 全部未达标，则 S3 不选择 Provider 模型 surface。

这一阈值只落实 T04 原计划中的“模型/本地 surface disposition”，不改写 T03 hard-integrity，也不改变“两模型都 hard-pass 时，Flash 只有在总分落后 Pro 超过 2 分才失去优先权”的既有规则。

## 当前边界

- 本轮外部、模型、Provider、网络和业务 Artifact 调用均为 0。
- quality score=0，model selection=0。
- T04 仅 authority/scope pass，assessment 尚未开始。
- S2 尚未关闭，S3 尚未进入，release 未获资格。
- 如果没有独立评分者，只能停在已生成 packet 的状态，不能由当前任务补写假评分。

下一项：

`FIN-0.1.2-S2-T04-IDENTITY-SEALED-BLIND-ASSESSMENT-PACKET-AND-INDEPENDENT-EVALUATOR-HANDOFF-MINIMUM-ZERO-CALL-IMPLEMENTATION`
