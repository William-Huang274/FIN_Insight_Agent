# FIN 0.1.2 pre-S2 T03 replacement hermetic proof 与 honest-block closeout

日期：2026-08-01

任务：`PRE-S2-RB-T03`

结果：`terminal failed / unique package consumed / pre-S2 honest block / S2 entry=false`

## 1. 本轮权限与停止线

用户以“继续”授权执行已冻结的唯一 T03 双 disposable replacement proof。父处置只允许一个 implementation bundle 和一个 replacement proof package；T02 已消费 implementation，本轮消费唯一 proof package。失败后必须诚实收口，禁止修后重跑、第二包、历史 S1 T03/T04 重跑、S1 reopen 或 S2 entry。

本轮没有读取凭据、调用模型或 Provider，也没有业务网络、source/tool、admission、business Run、business Artifact 或 paid reproof。

## 2. 唯一证明包

- Git baseline：`97f20c4a301f5591526fef2f42501ccf4d0b0221`
- branch：`codex/layered-data-source-expansion`
- output：`D:/FIN_Insight_Agent_recovery/packages/fin_0_1_2_pre_s2_t03_replacement_hermetic_proof_20260731T161211Z_head_97f20c4a`
- execution：exactly once，exit code `1`，约 `103.8s`
- verification SHA-256：`dd5b9594ef374e3397912aa196ea5e00dfc8e6b74964c81d7c2d1133601a757e`
- package manifest SHA-256：`13217026a2006b12e1a8d57eef21afcc91dcb01ccc2f2b3d96bee212003eb8cd`
- disposable A terminal SHA-256：`0c44be8194f696d67ba8cb22419a0f64557ebaf7d4958bab4ee9960a2489f4b3`
- disposable B terminal SHA-256：`65b6d5742144d0fa12708b267be0492c066885048dbbdca3e1b964fb3173d516`

两套 disposable 均为 `56 passed / 1 failed / 0 collection errors`，唯一 gating node 相同；repository unchanged，per-test 和 process stdout/stderr/detail 全部内容寻址留存。

## 3. T02 三个 owner 的实际结果

T03 没有复现 T02 要处理的三个原始问题：

1. tracked MU fixture 精确入包一次，SHA-256=`84e2f2ad...679909`；active three-case proof 不再读取 host-local MU object；
2. `SKILL_FILES` 的 16 项 Runtime resource 连同 inventory/registry 共 18 个路径全部入包，missing=`0`、digest mismatch=`0`；
3. 两套 semantic projection digest 相同，normalization valid，unknown absolute path=`0`；raw digests 保持不同，说明 raw evidence 未被改写。

三案例 full-fake、候选和 request-local alias mutation、final Artifact mutation、下游 capture 与 terminal-result retention 也都通过。因此原 RC-P36-085 的 tracked fixture、Runtime resource 和 semantic parity owner 可以关闭；这不等于 T03 pass。

## 4. 首个阻断：disposable 自反 Git inventory

唯一失败节点为：

`tests/contract/test_fin_0_1_2_pre_s2_hermetic_fixture_resource_rebaseline_minimum_zero_call_implementation.py::test_T03_manifest_is_runnable_and_binds_all_T02_dependency_contracts`

该测试本来验证 host 侧 manifest/package discovery，却被同时选进 disposable current gate。它在隔离仓内再次调用 `discover_repository_paths`，后者执行 `git ls-files`；disposable 按 hermetic 设计只有仓库字节、不含 `.git`，因此以 `hermetic_git_inventory_failed` 终止。A/B 的 failure node 和语义 projection 完全一致。

这属于项目内 test topology / stage contract 问题，登记：

`RC-P36-090-fin-0-1-2-pre-s2-t03-disposable-self-introspection-git-inventory-dependency`

它不是 MU fixture 缺失、Runtime resource 缺失、semantic parity、未知绝对路径、金融 Runtime L1、DeepSeek 或 Provider 问题。

## 5. 独立边界发现：ignored Runtime state 被带入 package

package manifest 的进一步审计发现 164 个 `.codex_runtime/` 文件、合计 `6,427,052 bytes` 被内容寻址打包；源路径全部 Git ignored、Git tracked count=`0`。直接原因是 JSON reference closure 对新发现的相对路径只检查“文件存在”，没有继续要求其属于 tracked 或 manifest explicit allowlist。mutable backlog/ledger 中指向历史运行证据的 ref 因此把 ignored Runtime state 带入包。

active three-case proof 没有读取这些文件，它们也不是上面的首个 pytest 失败。但这违反 package data-minimization 与审计证据隔离，登记：

`RC-P36-091-fin-0-1-2-hermetic-package-recursive-json-ref-admits-ignored-runtime-state`

Provider credential environment 在 pytest 前已移除，但这不能独立证明所有递归带入的历史内容都没有 credential-shaped 数据。因此该离仓包只作为 restricted/quarantined 审计材料：不得分享、不得晋升、不得视为业务 Artifact。本轮未获授权，也没有删除该包。

## 6. 终态与产品真值

- implementation/proof package budget：`1/1`，全部消费；
- T02：`engineering pass / owner fixes positive`；
- T03：`terminal failed`；
- pre-S2：`closed honest block`；
- S1：保持历史 honest block，不重开；
- S2 entry：`false`；
- DELL R2、MU R2、post-transfer NVDA exact product、NVDA R3、FIN 0.1 release qualified：全部仍为 `false`；
- 第二个 T03 package、patch-then-rerun、模型/Provider/business execution：全部为 `0`。

机器记录：

`configs/releases/fin_ia_0_1_2_pre_s2_t03_replacement_hermetic_proof_and_honest_block_closeout_v1_0.json`

## 7. 收口验证

- 新 closeout contract：`4 passed`；
- touched JSON/JSONL strict parse：通过，无 duplicate key；
- Python compile 与 `git diff --check`：通过；
- 当前 10 个 FIN0.1.2 contract 文件：`95 passed / 6 failed`。六项失败都来自旧 S0/S1/T01/T02 测试仍把 T02 的 historical `next_action` 或 ledger-last-row 当作 mutable current projection；没有新增应用 Runtime、三案 full-fake、resource 或 semantic-parity failure。按本轮 stop rule 保留为 RC-P36-090 的 test-topology 证据，不在 closeout 中批量改绿；
- broad full-chain Project OS preflight：按 RC-P36-090/091 正确 `blocked`，open blockers=`2`；
- 精确 current-next decision scope preflight：`pass`，说明只允许下一项 scope decision 和 repository hygiene，不允许 paid/full-chain 绕过。

## 8. 下一项

当前只允许一个新的 decision-only scope：

`FIN-0.1.2-PRE-S2-TERMINAL-HONEST-BLOCK-AND-S0-TEST-PACKAGING-CONTRACT-REOPEN-OR-DEFER-SCOPE-DECISION`

它需要决定：把 RC-P36-090/091 作为 FIN 0.1.2 S0 test/packaging contract 的新有界 reopen stage，还是明确递延到后续 patch line。无论选择哪条，都不能把当前失败包改写为 pass，也不能把未来新 stage 的证明叫作第二次 T03。
