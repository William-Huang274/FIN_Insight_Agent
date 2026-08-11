# FIN 0.1.3 S0 reference-role taxonomy owner 与 Exit Contract v2 处置

日期：2026-08-01

状态：`pass / planning normalization complete / implementation pending / zero external call`

## 背景

FIN 0.1.3 S0-T03 的唯一 host engineering proof 已在 repository closure 阶段终态失败。首错不是 DeepSeek、Provider、金融数据或金融判断，而是合法 `semantic followup_ref` 被旧 `ref/*_ref` 路径启发式误判。只读 collect-all 又暴露 47 种 reference field，说明需要重做角色合同，而不是继续逐字段补丁。

Owner 同时要求重新界定当前版本及 S0–S5 的任务归属，避免把后续模型质量、跨案例产品验收或下一版本功能继续塞回当前 S0。

## 本次决策

1. FIN 0.1.1 与 0.1.2 保持历史 internal honest block；FIN 0.1.3 是唯一当前主线。
2. 不自动创建 FIN 0.1.4，不改变 FIN 0.2 Earnings Review Alpha 的原定义。
3. 旧 v1 StagePlan、T03 closeout、`1/1` proof 预算和失败结论保持不可变；不重跑、不重算、不创建旧 T04。
4. 在同一 FIN 0.1.3 S0 下建立 `fin_0_1_3.S0.exit_contract:v2`。
5. v2 由一个版本化 registry/schema 统一编译六类 reference role：`repository_resource`、`package_relative_audit`、`external_content`、`restricted_runtime_audit`、`model_run_report`、`semantic_followup`。
6. 同一 source 同时生成 field rules、tracked-or-typed closure、collect-all validator、mutation 和 typed failure；未知 role fail closed，禁止建立 47 个字段例外。
7. v2 固定最多 `1 implementation / 1 host proof / 1 formal two-disposable proof`，无自动 retry、replacement 或版本跃迁。

## S0–S5 归属

- S0：hermetic Runtime、typed resources/reference/environment、active suite、capture/terminal、双 disposable parity；
- S1：DELL/MU/NVDA 零模型三案 `6/12/12/9` 与数值/日期/身份/lineage mutation；
- S2：DeepSeek V4 Flash stable / Pro preview 小样本模型边界与主线选择；
- S3：当前 Runtime 上 NVDA 三 Cell、九件套、独立 L1、paired 与 owner acceptance；
- S4：DELL/MU R2、post-transfer NVDA、R3 与 Workbench 真实用户价值；
- S5：RG1–RG5、commit/rollback 与 release 或 honest-block 决策。

## 落物

- 产品路线：`docs/product/FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260801.zh-CN.md`；
- 机器决策：`configs/releases/fin_ia_0_1_3_s0_t03_terminal_honest_block_reference_role_taxonomy_owner_and_exit_contract_v2_disposition_v1_0.json`，SHA-256=`2c040ff2...fcba`；
- 当前投影：`configs/runtime/fin_ia_0_1_3_current_program_projection_v1_4.json`；
- 更新技术 StagePlan、版本谱系、两份 backlog 与 Project OS；
- 历史 T03 测试改为只校验冻结 event snapshot，当前 mutable 状态由 v1.4 投影及本次决策测试持有。

## 验证

- JSON/JSONL duplicate-key 与解析合同由 focused tests 覆盖；
- `python -m py_compile`：3 个相关 contract test 文件通过；
- focused governance contracts：`24 passed`；
- 未执行 active full suite、full-fake、host proof 或 disposable proof，避免把规划验证误报为工程证明；
- model/Provider/network/admission/business Run/Artifact=`0/0/0/0/0/0`。

## 当前真值与下一项

本次没有用户可见能力增量。RC-P36-090–094 继续 open/full-chain blocker；FIN 0.1.3 S0 仍 blocked，S1/S2 未进入，DELL/MU R2、current NVDA R2、NVDA R3 与 release qualification 均为 false。

唯一下一项：

`FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-REGISTRY-AND-COLLECT-ALL-COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION`
