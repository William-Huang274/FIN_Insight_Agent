# FIN 0.1 仓库证据冻结与安全分类

日期：2026-07-31<br>
决策：`FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION`

## 1. 结论

本轮完成的是仓库证据冻结和安全分类，不是仓库清理。

当前 Git/index/worktree 状态已经逐路径内容寻址，并被归入 8 个有明确 owner 的候选提交切片。没有路径被删除、移动、取消暂存、reset、checkout、提交、push、tag 或 release；也没有触发模型、Provider、网络、source、external tool 或 exact-live。

仓库仍然不适合直接清理或直接提交：

- inventory scope 中 `1,127` 条状态记录含 `799` 条 index 变更、`29` 条 unstaged worktree 变更和 `326` 条未跟踪；写出 inventory 自身后实际 `git status` 为 `1,128` 条，其中新增的第 `1` 条就是被刻意排除以避免自引用的 inventory；
- `29` 条路径同时存在必须分别保留的 index/worktree 版本；
- `326` 条未跟踪路径不能从当前 Git 历史恢复；
- 没有任何路径被证明为可安全删除，`safe_delete_candidates_proven=0`；
- 当前 S4 honest-block、T10 未 closeout、S5 未进入、FIN 0.1 未 release-qualified 的产品真值均未改变。

机器清单：

`configs/releases/fin_ia_0_1_repository_evidence_freeze_and_safe_classification_inventory_v1_0.json`

## 2. 快照边界

| 项目 | 冻结值 |
|---|---:|
| branch | `codex/layered-data-source-expansion` |
| HEAD | `54d2e072b30d51cd7aaa3b55288d186782853a97` |
| inventory-scoped status rows（排除 output 自身） | `1,127` |
| inventory-scoped staged / unstaged / untracked | `799 / 29 / 326` |
| post-write actual status rows / untracked | `1,128 / 327` |
| index/worktree split paths | `29` |
| ephemeral candidates | `0` |
| proven safe-delete candidates | `0` |
| potential plaintext secret paths | `0` |
| intentional non-secret credential-shaped fixtures | `2` |

清单不保存文件正文、diff 正文或凭据值。每个状态路径只保存路径分类、recoverability、HEAD/index/worktree 的 Git object ID、SHA-256 和大小；cached/unstaged binary diff 只保存整体 bytes 与 SHA-256。

## 3. 凭据形态扫描

初次正则扫描命中两个测试路径，但受限上下文复核确认它们都是故意构造的非密钥 fixture：

1. strict-schema canary runner 使用声明为非真实的 OpenAI-style key，验证环境变量读取和“不落盘”；
2. audit-evidence v2 测试故意构造 Authorization-shaped 内容，验证 unsafe capture 被拒绝和脱敏。

最终清单将它们分类为 `intentional_non_secret_credential_test_fixture`，保留路径和命中类型，不保存值，也不把它们误报为需要轮换的真实凭据。任何不在 exact allowlist 中的新命中仍会被标为 critical 并阻止提交。

## 4. 路径归属

| 顺序 | 候选提交切片 | 路径数 | 目的 |
|---:|---|---:|---|
| 0 | `slice_00_foundation_and_product_shell` | 33 | Point01/Point02 与 FIN 0.1 program-wide 合同 |
| 1 | `slice_01_shared_runtime_and_workbench` | 30 | 跨阶段共享 Runtime、Workbench 与根级回归 |
| 2 | `slice_02_FIN_0_1_one_cell_baseline` | 103 | S0–S2 foundation、fixture 与 one-cell baseline |
| 3 | `slice_03_FIN_0_1_NVDA_anchor` | 427 | S3 NVDA anchor、T09 收敛与相应证据 |
| 4 | `slice_04_FIN_0_1_three_case_transfer` | 516 | S4 DELL/MU/NVDA transfer 与 honest-block 证据 |
| 5 | `slice_05_execution_evidence` | 2 | 跨阶段 model-run index 与执行证据 |
| 6 | `slice_06_repository_recovery_governance` | 8 | 双任务复盘、版本谱系、仓库清单与测试 |
| 7 | `slice_07_Project_OS_finalization` | 8 | current context、capability/root-cause ledger 与 handoff |
| 8 | `slice_08_owner_review_required` | 0 | 仅作漏接保护；当前无未归属路径 |

顺序是依赖顺序，不是本轮已执行的 Git 操作。共享 Runtime 先于消费它的阶段证明，执行证据在对应阶段之后，仓库复盘和 Project OS 最后落地。

## 5. 未跟踪路径

inventory scope 内的 `326` 条未跟踪路径分成两类：

- `225` 条为 implementation、machine contract、test 或 runner 等高优先级候选，必须保留并进入相应切片；
- `101` 条为文档、worklog、report 或 ledger 等 owner-review 候选，默认仍保留，只有逐路径证明重复、无引用、可重建且有恢复副本后，才可能进入未来删除决策。

写出后的第 `327` 条未跟踪路径就是 inventory 文件本身；execution guard 单独记录它的路径和状态码，未把它重复计入自己的 entries。

“owner review required”不表示可疑或应删除，只表示文件内容对产品叙事、证据完整性或历史审计有语义影响，不能只靠扩展名自动处置。

## 6. index/worktree 分叉

`29` 条 split path 的 index 与 worktree 不能互相覆盖：

- `18` 条 `AM`：index 中是新增快照，worktree 又有后续修改；
- `9` 条 `MM`：HEAD、index、worktree 三个版本均可能不同；
- `2` 条 ` M`：HEAD/index 可恢复，但 unstaged worktree 版本尚未进入 index。

清单已经分别记录可用版本的 SHA-256，但 hash 不能替代内容备份。任何 `git restore --staged`、reset、checkout、重新暂存或分片提交之前，必须先完成 owner 授权的离仓内容寻址备份，并验证能恢复 index 和 worktree 两套字节。

## 7. 建议提交与回滚协议

后续若 owner 批准，不应直接对当前 index 提交。安全执行顺序应为：

1. 以本清单为 source，冻结 exact path manifest 和 parent HEAD；
2. 在仓库外建立受限、内容寻址的 index/worktree/untracked 恢复包，并完成读取回验；
3. 对 29 个 split path 逐一证明 index/worktree 两份字节均在恢复包中；
4. 依序重建一个候选切片，每片只包含 manifest 中的路径；
5. 每片执行自己的 parse、contract 和相关回归；失败时只回到恢复包，不使用 destructive reset；
6. 每片提交信息明确“工程证据”与“产品 maturity”不同，不把 S4 或 FIN 0.1 宣称为通过；
7. 最后更新 Project OS，并重新生成 clean-tree/remaining-dirty 证明；
8. 删除仍是另一项独立、exact-target、可恢复性先行的授权，不能和提交切片隐式绑定。

当前 inventory 证明的是“每条变化都有可追溯归属和保留建议”，不是“所有变化已经经过 owner 审核”，更不是“仓库已经 clean”。

## 8. 验证

- inventory、repository-recovery scope 与历史 T10 scope 合同：`24 passed`；
- `409` 个 release JSON 与 `24` 个 Project OS JSONL / `1,504` records 严格解析通过，duplicate key=`0`；
- repository/Git-hygiene Project OS preflight=`pass`，open blocker=`0`；
- inventory generator compile 与生成前后 no-unexpected-mutation guard=`pass`。

## 9. 下一项

`FIN-0.1-REPOSITORY-CLASSIFICATION-OWNER-REVIEW-AND-COHERENT-COMMIT-SLICE-AUTHORITY-DECISION`

该项只决定接受、修改或拒绝上述分类和恢复协议。未获得新的明确授权前，不建立恢复包、不取消暂存、不重新暂存、不提交，也不执行任何删除。

## 10. 后续授权执行记录

本节记录 inventory 冻结之后另行获得 owner 授权的执行结果，不回写或改写前述历史快照。

### 10.1 离仓恢复包

- package：`D:\FIN_Insight_Agent_recovery\packages\fin_0_1_repo_recovery_20260731T163800+0800_head_54d2e072`
- source HEAD：`54d2e072b30d51cd7aaa3b55288d186782853a97`
- manifest entries：`1,128`
- unique content-addressed objects：`1,255`
- source versions verified：`1,929`
- manifest SHA-256：`ca8edba1599f782f9c661ff81a4b056c65564be0d3ab22798101ca632a5ad12a`
- package-tree SHA-256 before verification record：`7f1723c40d1333e9dde3b1aefdf2d766a85726b0fea1f35cedbca5a76b8c35e4`

恢复包逐项保存并回验 HEAD/index/worktree/untracked 字节。它用于恢复本轮 Git/index 操作，不等同于异盘灾备。

### 10.2 索引重建

owner 授权后，先把 index 恢复到 parent HEAD；操作后：

- HEAD 未变化；
- cached diff 为空；
- `1,128` 个状态路径集合未变化；
- `1,128` 份 worktree 文件 SHA-256 与恢复包逐项一致。

之后只使用仓库外 NUL 分隔 exact path manifest 逐片暂存，没有使用 `git add .`、reset、checkout、clean、删除、移动或历史改写。

### 10.3 已完成提交

| 顺序 | commit | 路径数 | 内容 |
|---:|---|---:|---|
| 0 | `8f904ae6cd4505c0d92295cb36b9a7d2ec0601db` | 33 | foundation 与 product shell |
| 1 | `65f2e46ebb1d7a9985ba1d93fba51b27b017e5c5` | 30 | shared Runtime 与 Workbench |
| 2 | `1eaab9b39bb701acf2af8fd971293940f97dc1ab` | 103 | S0–S2 one-cell baseline |
| 3 | `9cc7b8b36442d3b7cc989e04e9309c97f66d3c04` | 427 | NVDA S3 anchor 与 acceptance evidence |
| 4 | `d456c38573294944a6a4a86b6e50d5b5bdaeb184` | 516 | three-case transfer 与 honest-block evidence |
| 5 | `0c26410963ba8e06a3f6ed67668754e544e7b8fd` | 2 | execution evidence index |

每个 commit 的路径集合都与对应 exact manifest 相等，提交后 index 为空。没有 push、tag、release 或 S5 entry。

### 10.4 验证与非膨胀边界

- slice 00：`10 passed`；
- slice 01：`12 passed`，Workbench TypeScript/Vite production build 通过；
- slice 02：`133 passed`；
- S3 全历史套件：`582 passed / 64 failed`；当前 acceptance core：`30 passed / 1 mutable-pointer assertion deselected`；
- S4 全历史套件：`676 passed / 126 failed / 1 skipped`；当前 T07–T10 authority core：`33 passed / 2 mutable-pointer assertions deselected`。

S3/S4 全历史套件的非绿项没有在仓库恢复阶段逐条改写。它们集中于 immutable 历史证明绑定 mutable `current_next`、已消费 admission、累计 store、living-document digest 或后续 shared Runtime code binding；S4 还保留了 T07 已知的 template/profile/proof-isolation 回归。后者是 FIN 0.1 honest-block 的组成部分，不能为取得绿色测试数字而被隐藏。

因此本轮提交证明的是：

1. dirty repository 已被可恢复、可审计地拆分；
2. 当前 S3 anchor 合同仍成立；
3. S4/FIN 0.1 仍未达到 release qualification；
4. 历史测试时间耦合与当前产品阻断已被分开记录。
