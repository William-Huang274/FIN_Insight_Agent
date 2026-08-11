# FIN 0.1 S4-T05：WWC Numeric authority surface 最小处置

日期：2026-07-27

## 本轮权限

用户以“继续”授权 RC-P36-060 的零调用根因处置。没有授权 runtime patch、admission、模型或 Provider 调用、第四次 DELL execution、paired assessment、S4-T06 或后续阶段。

## 结论

RC-P36-060 是两个 authority membership owner 漂移：

- Fact 字段从 `cell_input.authority_refs.numeric_refs` 读取闭合 Numeric refs；
- WWC 字段却从 `numeric_input.selected_financial_rows/derived_metrics` 重建另一套 Numeric membership；
- R3 exact input 的前者含 6 个 ref，后者为空，导致合法任务被 generic `s3_owner_grade_WWC_task_incomplete` 拒绝。

模型按照 exact input 使用了 6 个合法 Numeric refs，因此直接 owner 是项目 runtime，不是模型或 Provider。

## 选定的最小合同

选择 `fin01.s3.what_would_change_authority_policy:v1`：

- `what_would_change.authority_refs` 的唯一 membership owner 是 `cell_input.authority_refs`；
- 保留 WWC 既有四类语义：Evidence、Numeric、Candidate、Graph；
- Provider request 显式获得当前 Cell 的字段级 closed surface；
- 本地 validator 消费同一 policy 或其 canonical projection；
- 输出必须是 non-empty exact subset；
- 禁止 trim、casefold、fuzzy matching、remap、drop、relink、跨 Cell 和 ticker 特判；
- `numeric_input` 仍可提供 scope 与 cannot-support 元数据，但不再决定 ref membership；
- 不允许把旧重建集合与 canonical list 求并集，因为这会继续保留两个 owner。

Authority/lineage 仍是 L1 hard integrity。只增加当前 blocker 所需的 content-free failure：`s3_owner_grade_WWC_task_authority_invalid` 及两个闭合 subtype；不宣称完成完整 WWC failure taxonomy。

## 明确不做

- 不修改或重放历史 R3 capture/Run；
- 不针对 DELL 六个 ref 写 special case；
- 不把 unknown authority 降为质量 finding；
- 不改变 TaskClaimLinkPolicy；
- 不改为“任务只能引用 Fact ID”；
- 不重入 deterministic task identity、完整 WWC taxonomy 或跨阶段统一身份重构。

后三项继续按原计划后传，避免 T05 单任务序列无限扩展。

## 验收边界

未来 implementation 至少验证四类 exact subset、混合集合、R3 六个 Numeric refs，以及 blank/non-string/outside/cross-Cell/legacy-only/fuzzy 负例。只有实现与 fake/contract regression 通过后，才可另行决定 fresh proof、admission 和 exact-live。

本轮 model / Provider / execution network / source / tool / Run / Artifact / paired / Human 均为 0。DELL R2 仍未证明。

## 下一步

`S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-MINIMUM-ZERO-CALL-IMPLEMENTATION`

该实现仍需独立授权。
