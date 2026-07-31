# FIN 0.1 S4-T05 TaskClaimLinkPolicy 最小零调用实现

日期：2026-07-27

## 结论

`fin01.s3.task_claim_link_policy:v1` 已接入共享三 Cell runtime，并在不运行真实模型、Provider、网络、source 或外部工具的前提下完成 fixture proof。RC-P36-059 从“处置完成、实现待做”推进为“runtime 已注入、节点已消费、fixture 已证明、fresh-agent proof 待独立授权”。

这不是 DELL R2，也没有签发或消费 admission、创建新 Run 或业务 Artifact。

## 实现边界

- `TaskClaimLinkPolicy` 只作用于 `actionable_what_would_change_tasks`。
- alias 表只由当前 Cell 已通过校验的 Claim 构造，并按原始 `claim_id` 排序后生成 `Q001/Q002/...`。
- Provider 看到 Claim statement、epistemic status 和本地 scope summary，只返回精确 `claim_alias`；raw Claim ID 和跨 Cell/canonical identity 不进入选择面。
- runtime 在既有 task validator 前做 exact membership expansion，恢复原始 `claim_id`。
- raw Claim ID、unknown/blank/non-string、大小写或空白变体都以唯一新增 subtype `task_claim_alias_unknown` fail-closed；不 trim、casefold、猜测、模糊匹配、relink、drop 或 rewrite。
- 现有 provider-generated `task_id` nonblank/Cell 内 unique 行为保持不变。
- admission 以独立 `task_claim_link_policy_ref` 绑定；未设置该字段的历史 admission digest 与行为保持不变。

## Fixture 证据

- deterministic alias、正向 exact expansion 和对抗性 selection fixtures 通过；
- WWC request schema 使用 `claim_alias`，prior Claim projection 不暴露 raw Claim ID；
- content-free typed telemetry 不持久化 alias、Claim ID、Cell ID、item index 或 private reasoning；
- 六逻辑节点、十二次本地 fake-provider callback、九类逻辑 Artifact 完整通过；
- canonical output 与下游 fake Artifacts 的 `Q` alias residue 为 0；
- ClaimFactLinkPolicy、CellScopedResearchIdentityPolicy、S4 role-group mapping/actual dispatch 和 legacy raw task validator 回归保持通过。

## 历史绑定处理

历史 admission、proof、Run 和 role-mapping 实现结果均未改写。旧合同曾把共享 executor 与其测试文件的当时 SHA 当成永久 current SHA；新实现结果只显式允许这两个文件因本轮前向演进产生漂移，其余历史 exact bindings 仍必须逐字节一致。该处置不重解释任何历史业务证据。

## 后续携带项

以下事项仍不属于当前 T05 实现：

- deterministic locally assembled task identity：`S4-T10-to-S5-carry-forward`；
- complete typed WWC failure taxonomy：`S4-T10-to-S5-carry-forward`；
- cross-stage unified Claim/Task identity redesign：S5-or-later。

## 当前门禁

实现结果：

`configs/releases/fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_zero_call_implementation_v1_0.json`

SHA256：`ba6e3af28c2a7deaab355e105710a1e50839957b9152272db77a26ea5d0e52f9`

下一项仅为：

`S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-FRESH-AGENT-PROOF-DECISION`

该下一项仍是零调用 proof decision，并需独立授权；不包含 admission issuance/consumption、第三次 DELL exact-live、paired assessment、S4-T06 或更后阶段。
