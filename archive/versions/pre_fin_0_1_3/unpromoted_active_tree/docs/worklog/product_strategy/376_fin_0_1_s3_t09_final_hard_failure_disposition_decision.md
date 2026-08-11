# FIN 0.1 S3-T09 最终硬失败处置决策

时间：2026-07-24（Asia/Shanghai）

## 结果

用户授权执行 `S3-T09-FINAL-HARD-FAILURE-DISPOSITION-DECISION`。本轮选择通用 `ClaimFactLinkPolicy` 修复路线，不选择带着错误 Claim→Fact 血缘进入 S4，也不选择为本次 NVDA/DeepSeek 输出增加特判。

本轮只完成零调用决策和 source-of-truth 同步；没有实现 runtime、Prompt、schema 或 validator，没有签发或消费 admission，没有调用模型、Provider、执行网络、来源或外部工具，没有创建新的 WorkUnit、Attempt、ResearchRun、Artifact、paired comparison 或 Human Review。

## 根因与处置

最终 exact-live 的两个 Claim 共六个 `support_fact_ids` 全部复制了底层 Numeric source refs，零个等于上一步两个 validated local Fact IDs。该问题是硬证据血缘完整性失败，不是普通文风、Alpha 或 Research Lead profile-v3 质量缺口，不能在仍宣称 S3 NVDA R2 的情况下后置。

直接模型语义映射失败成立；项目内同时存在 conveyance robustness gap：Claim Card 选择面同时暴露 local Fact identity 与底层 source-ref namespace，且没有字段级 closed Fact alias allowlist。

## 冻结的通用合同

选择 `fin01.s3.claim_fact_link_policy:v1`：

- runtime 从已经 validated 的当前 Cell Facts 确定性生成 request-local `F001/F002/...`；
- Claim Provider 只输出 `support_fact_aliases`；
- Claim link 选择面不暴露底层 Evidence/Numeric/Candidate/Graph/routing/object refs；
- runtime 只按 exact alias membership 展开回原始 local `support_fact_ids`，再进入现有 Epistemic、Scope 和 owner-grade validator；
- aliases 不成为 canonical identity，不进入 Writer、Verifier 或 Artifact lineage；
- 禁止 fuzzy match、normalize、trim、prefix guess、静默改写和历史回答重写；
- 行为由 typed policy/capability registry 驱动，不新增 `if transport == v8` 特判。

未来零调用实现必须覆盖非 NVDA、异期间、mixed Evidence/Numeric、跨 Cell 各自 `F001`、unknown/duplicate/wrong-layer/raw-ref 和完整六节点/十二假调用/九 Artifact；历史 profile-v3 final answer 必须仍重放为原硬失败。

## 后续证明预算

本决策不授权实现或真实运行。只有零调用实现与确定性回归通过后，才能另行决定 fresh identity/input/admission；若未来另行授权，最多一次 fresh exact-live，retry/fallback/rerun 均为 0。再次出现新的硬完整性失败时，S3 blocked closeout，不继续 transport/prompt 版本循环。

## 状态

- RC-P36-048：`generalized_claim_fact_link_policy_selected_zero_call_implementation_pending`
- RC-P36-047：fixture repaired，profile-v3 live 未到达
- RC-P36-046：complete live scoped lineage 未证明
- RC-P36-037：完整 live Artifact 产品仍缺失
- S3-T09：blocked
- T10/S4/carry-forward manifest：未进入/未到期

下一项：`S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-CLOSED-ALIAS-ZERO-CALL-IMPLEMENTATION`，仍需独立授权。
