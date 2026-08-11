# 517｜FIN 0.1 S4-T07 current-worktree 回归与 honest block

## 任务

依据 S1–S4-T06 阶段边界重基线进入 T07：先冻结一个零调用三案 current-worktree
回归 package；只有全部通过，才允许另做 NVDA post-transfer exact-live authority
decision。本项不自动读取凭据、调用模型、签发 admission 或执行 live。

## Scope decision

冻结 7 个既有合同测试文件、97 个测试节点，覆盖：

- DELL/MU/NVDA current compiled full-fake 各 `6/12/12/9`；
- Fact candidate pool、Claim、WWC 和本地稳定选择；
- cross-case/structural leakage；
- numeric、delivery identity、temporal、manifest/trace lineage mutation；
- Research Lead、Writer、Verifier failure capture；
- capture-v2 terminal-result materialization。

机器合同：
`configs/releases/fin_ia_0_1_s4_t07_entry_current_worktree_three_case_regression_and_nvda_post_transfer_exact_revalidation_scope_decision_v1_0.json`

scope 合同测试：`4 passed`。

## 执行结果

唯一 package 已消费：

- collected=`97`
- passed=`93`
- failed=`4`
- pytest exit=`1`
- wall clock=`58.92s`
- credential/model/provider/network/source/external tool=`0`
- admission/WorkUnit/Attempt/Run/business Artifact/exact-live=`0`

当前 compiled Runtime 的三案 full-fake、Fact/Claim/WWC、候选边界、本地
numeric/identity/temporal/lineage ownership、capture 与 terminal-result 路径均在
同一 package 中通过。

四个失败归为两类：

1. 两个旧 S4-T03 fixture admission 只设置 company 和 research profile，没有
   携带后来成为 mandatory 的 numeric-authority 与 delivery-identity policy refs；
2. 两个历史实现记录测试把 immutable implementation evidence 耦合到 mutable
   program `current_next` allowlist，无法接受后来的 T06/T07 状态。

这没有建立新的金融业务 L1、模型/Provider 故障或 active current-runtime
回归。但冻结 stop rule 不允许为凑绿灯修改旧 fixture 后重跑，因此没有 second
package。

结果合同：
`configs/releases/fin_ia_0_1_s4_t07_current_worktree_three_case_zero_call_regression_failure_result_v1_0.json`

## 阶段处置

- T07：`terminal_honestly_blocked`
- NVDA post-transfer exact-live：未授权、未执行
- NVDA latest nine-Artifact product / R3 candidate：未生成
- S3 NVDA R2 owner acceptance：历史证据保留，不复用为 R3
- RC-P36-086：转 S5 的 manifest-based test inventory 和 hermetic release baseline
- Runtime、fixture 和历史测试：本项不修、不重跑

下一项：

`S4-T08-READ-ONLY-THREE-CASE-CALIBRATION-AND-WORKBENCH-PRODUCT-VALUE-SCOPE-DECISION`

T08 只使用 immutable evidence，不晋升 failed/quarantined output，也不把
DELL/MU R2 或 NVDA post-transfer exact product的缺失改写为通过。
