# FIN 0.1 S4-T05 R9 profile-aware lineage 实现

日期：2026-07-28

## 结果

RC-P36-066 的最小结构性修复已经实现并通过零调用证明：

- legacy S3、S4 base、S4 research-profile overlay 分别使用 exact 6/4/5 键 lineage；
- manifest 记录 validation contract、family 和 canonical lineage digest；
- trace digest、S4 case pack、method contract、runtime binding、source pack 与 profile overlay refs/digests 必须一致；
- lineage 仍为 L1 hard gate，不做自动归一化、fallback 或质量 finding；
- typed failure 只保存 allowlisted subtype、artifact type 与 family，不保存 Provider text、字段值、credential、stack 或 raw exception message。

## Full-fake 证明

真实 S4 profile-v3 input 经 executor、6 个 logical nodes、12 个 fake callbacks、adapter artifact binding 与 post-Verifier profile validation，形成 9 个 Artifacts。

注入 trace runtime-binding digest 故障后：

- usage receipts=12；
- restricted captures=12；
- completed node receipts=6；
- business Artifacts=0；
- subtype=`bounded_agent_profile_lineage_digest_mismatch`；
- secret/raw output/private reasoning/stack 均未进入 observation。

## 边界

本实现没有修改或重跑 R9，没有模型、Provider、网络、source/tool 或 canonical business write。DELL R2 尚未证明，paired assessment、owner acceptance 与 S4-T06 均未进入。下一步是独立 fresh proof，然后签发全新 R10 admission 并 exact-once 执行；首次可信终态即停。

机器记录：

`configs/releases/fin_ia_0_1_s4_t05_dell_r9_profile_aware_artifact_lineage_validation_and_typed_subtype_minimum_zero_call_implementation_v1_0.json`
