# FIN 0.1 S4-T05 WWC Task→Claim 闭合身份：有界根因处置

日期：2026-07-27

## 用户约束

用户要求继续时特别强调：

> 不要把单任务序列的问题做无限扩展；属于下一序列的任务传递到下一阶段再做。

本轮因此只做 RC-P36-059 的零调用根因处置，不实现代码、不签 admission、不发起第三次 DELL exact-live，也不进入 paired assessment、MU、NVDA、Human、S5、release 或 production。

## 处置结论

DELL replacement exact-live 的第三 Cell 已验证 Claim 只有 `C1/C2`，WWC 回答却绑定 `C1/C2/C3`。当前 validator 对 `C3` 的 L1 identity/lineage fail-closed 是正确行为；禁止改写 `C3`、删除第三项 task、模糊匹配或放松 validator。

选择最小共享 `TaskClaimLinkPolicy`：

- WWC Provider 只看到由当前 Cell 已验证 Claim 确定性生成的 request-local `Q001/Q002` 闭合集合；
- Provider 返回 `claim_alias`，runtime 只做 exact membership expansion，恢复原始 `claim_id` 后再执行现有 task shape、authority 和 identity 校验；
- canonical Specialist output 和下游 Artifacts 不保留 `Q` alias；
- unknown alias 使用最小 content-free subtype `task_claim_alias_unknown` fail-closed；
- 现有 provider-generated `task_id` 的 Cell 内 nonblank/unique 校验保持不变。

这是解除当前 T05 blocker 所需的最小合同，不是完整身份系统重构。

## 明确不在当前序列扩展

以下项目不阻断当前 T05，登记为后续携带项：

- runtime 本地生成 deterministic task identity：传递至 `S4-T10-to-S5-carry-forward`，仅在后续出现稳定 task identity 的真实需求或 live 不稳定证据时重入；
- 拆解全部 `s3_owner_grade_WWC_task_incomplete` failure subtype：传递至 `S4-T10-to-S5-carry-forward`，仅在最小 unknown-alias subtype 后仍存在实质诊断问题时重入；
- Claim/Task 跨阶段统一身份重构：传递至 `S5-or-later-architecture-sequence`，必须有具体多 Case 或持久化任务需求才能重入。

## 本轮产物与验证边界

- 决策合同：`configs/releases/fin_ia_0_1_s4_t05_dell_wwc_task_to_claim_closed_identity_zero_call_root_cause_disposition_v1_0.json`
- 合同测试：`tests/contract/test_fin_0_1_s4_t05_dell_wwc_task_to_claim_closed_identity_root_cause_disposition.py`
- 模型 / Provider / 网络 / source / external tool 调用：`0 / 0 / 0 / 0 / 0`
- admission 签发 / 消费：`0 / 0`
- 新 WorkUnit / Attempt / Run / Artifact / canonical write：`0`

本轮决策通过不代表 DELL R2；RC-P36-059 仅进入 `root_cause_disposed_minimum_shared_policy_selected_implementation_pending`。

## 下一步

`S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-MINIMUM-ZERO-CALL-IMPLEMENTATION`

下一步仍只允许实现上述最小闭合身份面和 deterministic fixtures。fresh proof、admission 与第三次 exact-live 继续需要后续独立授权。
