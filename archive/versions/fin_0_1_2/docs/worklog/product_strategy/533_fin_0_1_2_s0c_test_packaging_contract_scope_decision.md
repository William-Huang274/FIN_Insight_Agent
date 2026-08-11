# FIN 0.1.2 S0C test/packaging contract scope decision

日期：2026-08-01

任务：`FIN-0.1.2-PRE-S2-TERMINAL-HONEST-BLOCK-AND-S0-TEST-PACKAGING-CONTRACT-REOPEN-OR-DEFER-SCOPE-DECISION`

结果：`S0C-T01 pass / bounded corrective stage selected / S0C-T02 ready / S2 blocked`

## 1. 为什么选择现在修而不是递延

pre-S2 唯一 T03 已终态失败且不能重跑，但两套 disposable 在首个 gate 前各有 56 个测试通过，tracked MU fixture、16 项 Runtime resource、三案 full-fake/mutation/capture 与 semantic parity 均有正面证据。剩余两项 blocker 是有限的仓库 owner：

- RC-P36-090：host-only package discovery 测试在无 `.git` 的 disposable 内自反执行；
- RC-P36-091：recursive JSON ref 只检查文件存在，未继续约束 tracked/explicit allowlist，带入 164 个 ignored `.codex_runtime` 文件、6,427,052 bytes。

它们不是 DeepSeek、Provider、金融方法或新的业务 Runtime L1，也不是 FIN 0.2 generalized compiler。若递延，FIN 0.1.2 会在 S2 前永久阻断；因此最合理的最早 owner 是 FIN 0.1.2 S0 的测试与打包合同。

## 2. 选择的阶段边界

新阶段为：

`FIN-0.1.2-S0C-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-PACKAGE-CLOSURE-R1`

`S0C` 表示 S0-owned corrective stage，不表示历史 S0 reopen。历史 S0 pass、S1 honest block 与 `PRE-S2-RB-T03 terminal failed / package consumed` 全部保持不可变。未来证明使用新的 stage、manifest 与 package identity，绝不称为第二次旧 T03。

固定任务与预算：

1. `S0C-T01`：本 decision-only 项，已通过；
2. `S0C-T02`：最多一个零调用实现包；
3. `S0C-T03`：仅在 T02 全绿后，最多一个双 disposable corrective proof package，并在同一任务内 pass 或 honest-block closeout。

不得自动派生 T04、R-number、第二 implementation bundle、第二 proof package或 patch-then-rerun。

## 3. T02 必须一次覆盖的结构问题

- host 负责 Git inventory construction 与 package pre-materialization；disposable 只消费冻结 inventory，零 `.git` 依赖；
- seed 与所有递归引用都必须是 Git tracked 或显式 typed policy allowlist；ignored、untracked、unknown、symlink escape 和 existing-file-only admission 在 object storage 前 fail closed；
- `.codex_runtime` 引用作为明确负向 fixture；
- immutable event 测试只验证当时事件，active slice、current next 与 ledger latest 由单一 current-projection owner 验证，不能再让六个历史 snapshot 竞争当前真值；
- raw stdout/stderr、terminal result、assistant output 与 capture refs 原样内容寻址；telemetry 只作带 ref/digest/location 的索引；
- failed/quarantined package 不得晋升业务 Artifact。旧 package 继续 restricted quarantine，本轮未授权删除、分享或声称 credential 内容缺失。

实现后需先用 host zero-call、mutation 与 DELL/MU/NVDA `6/12/12/9` 矩阵一次暴露问题；不得逐字段 live。

## 4. T03 与停止线

T03 必须在两个 fresh root/process 中证明：disposable 不含 `.git` 且 Git subprocess count=0；ignored/untracked Runtime path packaged count=0；raw evidence 完整；semantic parity 成立；repository unchanged；current gates 全绿。

通过后也只允许单独编制 FIN 0.1.2 S2 StagePlan scope decision，不自动进入 S2。失败则 S0C terminal honest block，不继续维修。

## 5. 本轮实际变化与真值

本轮只创建 decision contract、同步架构/backlog/Project OS 与合同测试；没有修改 runner、旧测试或业务 Runtime，没有执行 proof package。模型、Provider、网络、source、admission、Run、business Artifact 与 paid reproof 均为 0。

机器权威：

`configs/releases/fin_ia_0_1_2_s0c_hermetic_test_topology_and_allowlisted_package_closure_scope_decision_v1_0.json`

当前下一项：

`FIN-0.1.2-S0C-T02-HERMETIC-TEST-TOPOLOGY-AND-ALLOWLISTED-PACKAGE-CLOSURE-MINIMUM-ZERO-CALL-IMPLEMENTATION`

S2 entry、DELL R2、MU R2、post-transfer NVDA exact product、NVDA R3 与 FIN 0.1 release qualification 均仍为 false。
