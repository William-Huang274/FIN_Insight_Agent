# 544 — FIN 0.1.3 S0 v2 failure 项目级处置与 Exit Contract v3

日期：2026-08-01

结论：`pass / keep FIN 0.1.3 / select bounded S0 Exit Contract v3 / implementation pending`

## 1. 本项处理的问题

v2 唯一 host proof 已在 proof manifest policy 与共享 compiler 的第一道边界失败并消费；没有进入 import、collect、pytest 或三案 Runtime。当前必须决定：是直接补丁重跑、豁免 proof、创建新产品版本、向后续阶段转交，还是在项目级建立新的有界合同。

本项只做 decision，不修改 manifest、runner 或 Runtime；只新增本决策合同测试，并把两项旧测试从“持续拥有 mutable current”更正为历史快照断言。不执行 eligibility、host/formal proof，也不调用模型、Provider、网络或业务链。

## 2. 方案比较

- 拒绝“改 `fail_closed_collect_all` 为 `fail_closed` 后重跑 v2”：这会违反 consumed-run stop rule，并重写 immutable v2 evidence 的含义。
- 拒绝“93 项本地矩阵足以豁免 host/formal proof”：它不能证明 exact manifest 可执行包装与双-disposable semantic parity，RC-P36-090–094 仍无法关闭。
- 暂不创建 FIN 0.1.4：本次没有触达或否定金融 Runtime/产品行为，仅因 proof 控制面错误升级产品内部版本会制造版本漂移。
- 拒绝向 S1/S5/FIN0.2 转交：该问题拥有 S0 hermetic evidence boundary，后移会造成 acceptance inflation。
- 选择保留 FIN 0.1.3，在同一 S0 建立最后一次有界 Exit Contract v3。

## 3. v3 的边界

v3 不重新实现六角色 reference registry、29 项 Runtime resource、八类 typed environment root 或 DELL/MU/NVDA 确定性链。它只修两个最早 owner：

1. repository-reference proof policy 必须只有一个版本化来源，manifest compiler、validator 与 shared compiler 同源；
2. fixed-budget host proof 必须在消费前，用 exact manifest 穿过正式执行的同一 `compile_repository_inventory` 与 inventory validation 边界。

语义上把 `unknown_reference_behavior=fail_closed` 与 `unknown_reference_reporting=collect_all_typed_envelope` 分开，不再把报告方式伪装成行为 enum。

non-consuming eligibility 必须绑定 clean/synced committed HEAD、execution/active manifest、全部 source digests、tracked snapshot 和 compiled inventory digest，并保存 content-addressed attestation。正式 host execution 立即重算并匹配 attestation 后，才允许写入 consumed marker并进入 import sweep。

## 4. 预算和停止线

v2 `[implementation, host, formal] maximum/observed=[1,1,1]/[1,1,0]` 保持不可变。v3 `[implementation, eligibility, host, formal] maximum/observed=[1,1,1,1]/[0,0,0,0]`。

implementation 不等于 eligibility 或 proof；eligibility 通过后仍需单独 host authority，host 通过后仍需单独 formal authority。任一 v3 eligibility/host/formal 新结构失败都冻结 FIN 0.1.3 internal honest block；同版本禁止 Exit Contract v4，不允许自动 retry、replacement 或 FIN 0.1.4。

## 5. 产品真值

本项没有用户可见金融研究能力增量。RC-P36-090–095 全部继续 open；S0 blocked，S1/S2 未进入，DELL/MU R2、current NVDA R2、NVDA R3 与 FIN0.1 release 均为 false。FIN0.2 Earnings Review Alpha 定义不变。

机器决策：`configs/releases/fin_ia_0_1_3_s0_v2_host_proof_first_credible_failure_project_level_disposition_and_exit_contract_v3_decision_v1_0.json`

决策 SHA256：`273e0383c133fa6530205357beb722453830f9e6aff03564f8e5765a962fdc30`

当前投影：`configs/runtime/fin_ia_0_1_3_current_program_projection_v1_8.json`

当前下一项：`FIN-0.1.3-S0-EXIT-CONTRACT-V3-PROOF-POLICY-SINGLE-SOURCE-AND-PRE-CONSUMPTION-BOUNDARY-MINIMUM-ZERO-CALL-IMPLEMENTATION`

## 6. 零调用验证

- JSON：两份 backlog、v3 decision 与 projection v1.8 均可解析；
- JSONL：capability/root-cause/external-pattern 三本台账逐行可解析；
- decision/projection 与相关历史合同矩阵：`49 passed / 2 deselected`；两项 deselected 是 v2 implementation 文件内仍主动调用旧 current projection 的历史测试，该文件被 immutable implementation artifact 以 SHA256 绑定，不能在本 decision 中改写；它们已明确归属下一项 v3 proof-control-plane implementation，而不是伪装为本轮通过；
- 下一项 Project OS full-chain preflight：`pass / 0 missing files / 0 missing capabilities / 0 applicable open blockers`；
- 外部调用：credential/model/Provider/network/source/admission/business Run/Artifact 全为 `0`。
