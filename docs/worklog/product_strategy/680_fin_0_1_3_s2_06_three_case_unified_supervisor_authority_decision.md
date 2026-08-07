# 680 — FIN 0.1.3 S2-06 三案例统一 Supervisor 权限决策

日期：2026-08-07

状态：`decision complete / issuance blocked / one shared zero-call implementation package next`

## 问题与结论

用户批准继续三案例统一 Supervisor 实验。审计确认三份 raw 与 `27/24/32` 条 correction boundary 已齐，但当前仓库只有 correction ledger compiler，没有可签发的 SupervisorPlan 合同和 corrected-candidate runner。现在直接签发会让 live 再次承担发现项目合同缺口的职责，因此本轮只冻结 authority decision，不签 admission、不调用 Provider。

“统一”被定义为同一协议、同一验收、三个物理隔离案例执行；不是把 DELL、MU、NVDA 放进同一个 Prompt。每案 Supervisor 只能看到本案 immutable raw、本案 evaluator v1.4 visible findings 和本案 blind Evidence/Numeric/Gap aliases；hidden Gold、Codex Gold、另一案例 raw/correction/candidate 和新外部检索全部禁止。

## 选定实验

每案最多 1 次 typed SupervisorPlan 调用，随后只重跑受影响 originating nodes，并确定性重算所有下游依赖；最坏为原十节点全部重算，因此每案最多 `1+10=11` 次、三案最多 `33` 次，retry/fallback/provider hopping=`0/0/false`，USD hard ceiling=`0.18/case, 0.54/campaign`。capacity 必须在 admission 前证明，不能在 live 中调上限。

Supervisor 只产出 correction plan，不直接写新报告或新金融事实。本地 Runtime 不得代写研究；raw identity 永不复用，corrected Run/Attempt/captures 必须全新。共享 infra/auth/capture/contract 失败停整个 campaign；已排除共享根因后的 case-local semantic failure 保留终态，并允许另两个预签发隔离案例继续，避免 first-failure 再次遮住能力分布。

## 验收与归因

逐案必须满足：fresh corrected identity 与完整 lineage；evaluator v1.4 `L1=0/L2=0`；无跨案、未知数值或 citation-role 错误；空 counterevidence 全部由本案反证或显式无证据理由关闭；保留阈值必须具 evidence/time-window/source-route 校准或保持非事实 typed request；Verifier 必须覆盖此前 material finding classes。hidden score 只能在 candidate freeze 后运行。

三案全部逐案通过才标记 `supervised_recoverability=proven`；部分通过只能标记 `partial`，不能平均掩盖失败。raw autonomous 结果继续保持三案 quality fail。即使 Supervisor 成功，本项也不自动成为业务报告、产品验收或 release。

## 签发前四个项目 blocker

1. correction ID 仍为每案重复的 `CORR-001` 形状，缺少 case-qualified typed SupervisorPlan；
2. citation/pack coverage 三类 finding 仍落入 `typed_manual_disposition_required`，没有明确 originating-node return owner；
3. 没有只重跑受影响节点并重新计算下游的 exact-once corrected-candidate runner；
4. 没有把 fresh corrected identity、capture-first terminal 和 candidate-freeze 后 hidden scoring 串成一条受治理路径。

下一项只允许一个零调用共享实现包：`FIN-0.1.3-013-S2-06-THREE-CASE-UNIFIED-SUPERVISOR-COMPILED-CORRECTION-PLAN-AND-CORRECTED-CANDIDATE-RUNNER-ZERO-CALL-IMPLEMENTATION`。通过三案 full-fake、污染/Gold/数值/引用/依赖/容量 mutation 和 fresh proof 后，才另行决定 admission。

机器决策见 `configs/releases/fin_ia_0_1_3_s2_06_three_case_unified_supervisor_authority_decision_v1_0.json`。focused=`15 passed`，S2-05/S2-06 broad=`103 passed / 3,201 deselected`；本轮 model/provider/network/admission/corrected candidate/raw mutation=`0/0/0/0/0/0`。
