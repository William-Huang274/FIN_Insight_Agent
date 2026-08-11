# 523 — FIN 0.1 仓库证据冻结与安全分类

日期：2026-07-31

## 已完成

执行：

`FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION`

生成内容寻址的 Git/index/worktree inventory，并将 output 之前的 `1,127` 条状态记录归入 8 个有 owner 的候选提交切片；保留第 9 个空的 owner-review 漏接保护切片。inventory 为避免自引用排除自身，写出后的实际 `git status` 为 `1,128` 条。

## 主要结果

- inventory-scoped staged/unstaged/untracked=`799/29/326`；post-write actual untracked=`327`，新增项仅为 inventory 自身；
- index/worktree split paths=`29`，index 与 worktree digest 均单独保留；
- untracked high-priority/owner-review=`225/101`；
- safe delete candidates=`0`，ephemeral candidates=`0`；
- potential plaintext secret paths=`0`；
- 两个 credential-shaped 命中均为 deliberate non-secret test fixture，清单只保存路径、类型和判定理由，不保存值；
- 所有路径均有 stage slice、artifact role、commit slice、risk、disposition、recoverability 与可用 HEAD/index/worktree digest；
- output 自身排除后，生成前后 repository status signature 一致。

## 候选提交顺序

`foundation/product shell → shared runtime/workbench → S0–S2 → S3 → S4 → execution evidence → repository recovery governance → Project OS finalization`

该顺序只是 owner-review proposal。本轮没有建立恢复包、取消暂存、重新暂存或提交。

## 验证

- inventory + repository-recovery scope + T10 historical scope：`24 passed`；
- strict parse：`409` release JSON、`24` Project OS JSONL / `1,504` records，duplicate key=`0`；
- Project OS `repository_and_git_hygiene` preflight=`pass`，open blocker=`0`；
- generator compile、inventory digest 和 no-unexpected-mutation guard=`pass`。

## 没有发生

没有删除、移动、clean、unstage、reset、checkout、commit、push、tag、release；没有凭据值读取或持久化；没有模型、Provider、网络、source、external tool、admission、Run、Artifact、exact-live、T10 closeout 或 S5 entry。

## 当前下一步

`FIN-0.1-REPOSITORY-CLASSIFICATION-OWNER-REVIEW-AND-COHERENT-COMMIT-SLICE-AUTHORITY-DECISION`

下一项只决定是否接受或调整分类与恢复协议。任何离仓恢复包、Git index 改写、提交或删除仍需新的明确授权。

## 后续 owner 授权执行

owner 随后批准分类、离仓恢复包、Git index 重建和 8 个 coherent commit slices；授权仍明确排除删除、历史改写、push、tag 和 release。

### 恢复前提

- recovery package：`D:\FIN_Insight_Agent_recovery\packages\fin_0_1_repo_recovery_20260731T163800+0800_head_54d2e072`
- manifest entries / unique objects / verified source versions：`1,128 / 1,255 / 1,929`
- manifest SHA-256：`ca8edba1599f782f9c661ff81a4b056c65564be0d3ab22798101ca632a5ad12a`
- source HEAD：`54d2e072b30d51cd7aaa3b55288d186782853a97`

恢复包完整验证后才执行 index 变化。index 恢复到 HEAD 后，HEAD 未变、cached diff 为空、`1,128` 个 worktree SHA-256 全部仍与恢复包一致。

### 已提交切片

1. `8f904ae6cd4505c0d92295cb36b9a7d2ec0601db` — 33 paths — foundation/product shell
2. `65f2e46ebb1d7a9985ba1d93fba51b27b017e5c5` — 30 paths — shared Runtime/Workbench
3. `1eaab9b39bb701acf2af8fd971293940f97dc1ab` — 103 paths — S0–S2
4. `9cc7b8b36442d3b7cc989e04e9309c97f66d3c04` — 427 paths — S3/NVDA
5. `d456c38573294944a6a4a86b6e50d5b5bdaeb184` — 516 paths — S4/three-case honest block
6. `0c26410963ba8e06a3f6ed67668754e544e7b8fd` — 2 paths — execution evidence

每个提交都通过 exact-path equality 和 cached diff 检查；没有使用 broad staging。

### 测试审计

- foundation：`10 passed`
- shared Runtime：`12 passed`
- S0–S2：`133 passed`
- S3 historical suite：`582 passed / 64 failed`；current acceptance core：`30 passed`
- S4 historical suite：`676 passed / 126 failed / 1 skipped`；current T07–T10 core：`33 passed`

S3/S4 的 historical-suite failures 主要是旧证明绑定当前 pointer、已消费 admission、累计 store、旧 code/digest binding；S4 另包含必须诚实保留的 T07 template/profile/proof-isolation 回归。仓库恢复不负责把这些历史事实逐项改成 green，也不因此把 S4 或 FIN 0.1 宣称为通过。

### 恢复阶段允许的最小修正

- 修正 4 个早期治理测试中把历史时点误写成永久当前状态的断言；
- 将 28 个 Markdown/Python 纯格式 finding 收敛为 clean cached diff；
- 没有修改 S3/S4 产品 verdict、exact-live 结果、owner acceptance 或 release gate。

后续只剩 repository-governance slice、Project OS finalization 和最终提交链/remaining-status 审计。
