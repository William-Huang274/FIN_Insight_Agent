# 542 — FIN 0.1.3 S0 reference-role / current Runtime host zero-call proof 权限决策

日期：2026-08-01

结论：`pass / authorize one future v2 host zero-call engineering proof / not executed`

## 1. 本项做了什么

本项只完成证明权限与执行前边界冻结，没有执行 host proof。旧 T03 的终态失败、`1/1` run 消耗和旧 T04 未创建事实保持不可变；FIN 0.1.3 exit-contract v2 的 observed budget 在本项后仍为 `1 implementation / 0 host / 0 formal`。

独立 Project OS preflight 对本决策 scope 得到 `pass / 0 missing files / 0 missing capabilities / 0 open blockers applicable to the authorized decision scope`。仓库在 `codex/layered-data-source-expansion` 上为 clean/synced，HEAD 与 upstream 均为 `dc978ac94fe6084252e9b14cab58bfed03233ad9`。实现、closure、typed environment、旧 T03 truth 与 DELL/MU/NVDA full-fake 关联的六个测试文件独立复跑为 `83 passed in 27.53s`。

写入新 current projection/backlog 后，同一合并矩阵为 `87 passed / 2 failed`。两项失败都来自冻结的 implementation snapshot manifest v1.2 仍通过 projection v1.5 校验 mutable backlog 的旧拓扑，因此在 current-next 前进后报 `current_projection_next_action_drift`；没有 Runtime、reference-role、三案例或金融 L1 失败。本项不回写冻结 implementation record、v1.2 manifest 或旧 T03，也不把这两项改成绿色。未来单次 proof 必须用新的 execution manifest 选择新的 current authority contract；不得把 v1.2/v1.5 当作当时仍未签权的当前投影。

## 2. 授权范围

未来只允许执行一次：

`FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-AND-CURRENT-RUNTIME-HOST-ZERO-CALL-ENGINEERING-PROOF`

执行项可以创建一份新的 digest-bound execution manifest 和纯编排 runner，以绑定执行时的 committed HEAD、当前投影、Runtime、registry、manifest 与测试文件。FIN 0.1.3 S0 v1.2 active manifest 保留为实现快照，不在本权限项中改写。

证明必须从 clean/synced committed HEAD 启动；移除 provider credential environment，封锁 network socket；把 raw stdout、stderr、detail、per-test capture 与 terminal result 以内容寻址方式保存到仓库外受限证据根；验证仓库 before/after readback 相同。失败包只能用于 restricted audit，不能分享或晋升业务内容。

## 3. 必须覆盖的证明面

- 六类 reference role、registry/rule digest、完整 tracked closure、0 allowlist、0 unknown；
- 含 `/` 的 semantic follow-up、collect-all typed failure、duplicate/cross-version/rule-order/unknown path/traversal/symlink 等 mutation；
- application import sweep、active-suite collect-only 与 current selected pytest；
- 29 项 RuntimeResourceRegistry、八类 typed environment roots；
- DELL/MU/NVDA 各 `6 nodes / 12 interactions / 12 captures / 9 Artifacts` 的 full-fake；
- numeric、identity、temporal、lineage mutation；
- Lead、Writer、Verifier 下游失败时 capture-v2 与 terminal-result 留存；
- package 内 `.git / .codex_runtime / ignored / untracked` 均为 0，repository unchanged。

执行时的完整闭包 path、observation、role counts 与 digest 必须由新 manifest 重新编译并记录，不能把实现记录中的 `1,233 / 4,996` 当作永远不变的硬编码预期。

## 4. 停止线与非授权项

proof 中不得修共享 Runtime、资源合同、reference-role registry/compiler、typed environment 或测试合同；不得调用 credential、模型、Provider、网络、source/external tool，不得签发 admission、运行金融业务链或生成业务 Artifact。任何失败均终态停止，不允许同项 patch 后 retry、replacement、第二次 host proof、T05/R/H 或自动 FIN 0.1.4。

host proof 成功只建立宿主零调用工程证据，不自动关闭 RC-P36-090–094，也不自动授权 formal two-disposable proof。成功后的下一步必须另做 formal-proof authority decision；失败则回到项目级 scope/contract/version disposition。

## 5. 当前产品真值

本项没有用户可见金融研究能力增量。RC-P36-090–094 继续 open/full-chain blocker；FIN 0.1.3 S0、S1、S2 与 release 继续 blocked，FIN 0.1.4 未创建，FIN 0.2 Earnings Review Alpha 定义不变。模型、Provider、网络、source、admission、business Run、business Artifact 均为 0。

机器决策：`configs/releases/fin_ia_0_1_3_s0_reference_role_taxonomy_and_current_runtime_host_zero_call_engineering_proof_authority_decision_v1_0.json`

决策 SHA-256：`e1ab2dbfea350f309a19981fb9b625bfbff3892f6b1510e6bb3d6841d69486e8`

当前投影：`configs/runtime/fin_ia_0_1_3_current_program_projection_v1_6.json`

当前下一项：`FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-AND-CURRENT-RUNTIME-HOST-ZERO-CALL-ENGINEERING-PROOF`
