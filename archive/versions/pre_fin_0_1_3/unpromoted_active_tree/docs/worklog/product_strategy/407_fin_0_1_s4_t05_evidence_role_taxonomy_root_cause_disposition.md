# FIN 0.1 S4-T05 Evidence Role Taxonomy 根因处置

日期：2026-07-26

## 权限与边界

用户以“可以，继续下一步”授权：

`S4-T05-DELL-EVIDENCE-ROLE-TAXONOMY-TO-RUNTIME-PLAN-ALIGNMENT-ZERO-CALL-ROOT-CAUSE-DISPOSITION-DECISION`

本轮只允许审计、选择合同、写入决策与治理记录。Runtime 实现、replacement admission、第二次 DELL exact-live、paired assessment、MU/NVDA、Human、S5、release 与 production 均未授权。

## 最早根因

当前 scalar `evidence_role` 同时承担：

1. 跨 Case 三 Cell 的 semantic axis；
2. Canonical EvidenceSlot 的 source-specific identity；
3. 历史 S3 fixture tool/route key。

因此 actual Runtime 用 `demand_signal / revenue_capture / thesis_counterevidence` 查询 DELL accepted slots 时得到 0 个 exact match，并在进入 S4 adapter 前失败。

## 选择

冻结：

`fin01.s4.case_evidence_role_group_mapping:v1`

- 跨 Case 稳定轴改为 `program_cell_id`；
- mapping 从 `S4CaseRuntimeBinding.program_cell_contracts.required_evidence_roles` 派生，不按 ticker 手写；
- Canonical slot 仍以同 Cell 的 exact source role 解析；
- DELL 和 MU 均保留 3 groups、`[4,5,5]`、14 roles；
- 所有 required roles 必须同 Cell、同 owner、exact-once 覆盖；
- actual Runtime 与 exact preflight 必须消费同一 dispatcher 和 mapping/alignment digest；
- legacy S3/NVDA singleton generic-role path 保持历史兼容。

明确拒绝：

- 重命名或复制 Canonical slots 为 generic roles；
- 每 Cell 只挑一个代表 role；
- DELL ticker 特判；
- synthetic generic slots；
- S4 回退到 S3 fixture candidates；
- missing role silent drop；
- 跳过全部 pre-adapter alignment。

## 产物与验证

- Decision：`configs/releases/fin_ia_0_1_s4_t05_evidence_role_taxonomy_runtime_plan_alignment_zero_call_root_cause_disposition_v1_0.json`
- Decision SHA256：`738c00d4a4f2aab411d838a44888ce97761898aab018a459fc5e1880d81b2d1c`
- Contract test：`tests/contract/test_fin_0_1_s4_t05_evidence_role_taxonomy_runtime_plan_alignment_root_cause_disposition.py`
- Decision 与 S2/S3/S4/cross-slice 邻接回归：`76 passed`
- Project OS disposition scope preflight：`pass`
- 下一 implementation scope Project OS preflight：`pass`，open blocker=`0`
- model / Provider / network / source / tool / admission / Run / Artifact / canonical write：全为 `0`

## 下一步

`S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-PREFLIGHT-ZERO-CALL-IMPLEMENTATION`

实现必须先证明：

- DELL、MU all-role exact coverage；
- legacy S3 compatibility；
- actual Runtime 与 exact preflight parity；
- missing/extra/duplicate/wrong-Cell/wrong-owner/digest mismatch 全部 fail-closed；
- DELL full fake-provider path 达到 6 nodes / 12 calls / 9 logical Artifacts；
- target Runtime 不变、真实调用为 0。

实现通过仍不等于 DELL R2，也不自动授权 replacement admission。
