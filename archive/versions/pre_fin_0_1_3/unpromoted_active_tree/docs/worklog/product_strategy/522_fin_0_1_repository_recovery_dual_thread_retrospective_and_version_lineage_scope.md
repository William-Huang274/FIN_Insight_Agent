# 522 — FIN 0.1 仓库恢复、双任务复盘与版本谱系 scope

日期：2026-07-31

## 已完成

执行只读、零删除、零模型的：

`FIN-0.1-REPOSITORY-RECOVERY-S0-TO-S4-AUDIT-AND-0.1.1-0.1.2-VERSION-LINEAGE-SCOPE-DECISION`

Codex task API 已分页读取至历史末尾：

- 当前任务 `019f91b7-662a-7f31-b71d-eb90d2ec32c2`：199 turns、121 compactions、2,055 file-change events；
- 相邻任务 `019f54fe-4b90-74c0-b5e7-6325c47b77ce`：135 turns、59 compactions、1,246 file-change events。

复盘确认：当前任务的反复返工来自 Provider surface 过宽、跨层合同不同源、fake/proof 盲点、exact-live 兼任集成测试和阶段 stop rule 未由机器预算强制；相邻任务在几乎没有模型质量依赖时仍出现多轮 repair，进一步证明 active set/behavior closure 太晚和治理对象家族膨胀是共同根因。

## 仓库快照

- branch=`codex/layered-data-source-expansion`；
- HEAD=`54d2e072b30d51cd7aaa3b55288d186782853a97`；
- status=`1118` rows；
- staged/unstaged/untracked=`799/28/317`；
- S0–S4 release JSON/tests/worklogs=`376/255/261`；
- T05 release JSON/tests/worklogs=`74/53/39`；
- T06 release JSON/tests/worklogs=`92/68/66`。

当前不具备安全删除或取消暂存条件。

## 决策

- S4 honest-block 真值和 T05/T06/T07 不重开保持；
- 第一轮 S0–S5 在 decision-only closeout 后冻结为 `FIN 0.1.1 Internal Engineering Baseline`，不是 release-qualified；
- common contract compiler、Provider surface reduction、proof hermeticity、DELL/MU transfer completion 和 post-transfer NVDA 进入 `FIN 0.1.2`；
- `FIN 0.2` 保持原定义 `Earnings Review Alpha`；
- S0–S5 宏观节奏不变，内部固定 G0–G6；一个失败 Gate 不得通过 R-number、replacement family 或新 H-stage 绕开；
- DeepSeek 只负责 request-local alias/enum 和 bounded judgment atoms，material number/date/identity/ID/lineage/cardinality 由本地确定性 owner；
- 每个阶段默认一个 StageCapsule、一个 assessment、一个 closeout；每个真实调用一个 RunCapsule；formal exact-live 每个产品 target 上限 1。

机器 scope SHA-256：

`055fe4f2f94214007efd0effc707d8ae177920a73f639d0d3cbd76ef067990b5`

## 验证

- 当前 scope + 历史 T10 scope 合同：`16 passed`；
- strict parse：`408` release JSON、`24` Project OS JSONL / `1502` records；
- duplicate/parse errors=`0`；
- source bindings=`11/11`；
- target diff check 与 scoped secret scan=`pass`。

## 没有发生

没有删除、移动、取消暂存、reset、checkout、commit、push、tag 或 release；没有凭据读取、模型、Provider、网络、source、external tool、admission、Run、business Artifact、exact-live、T10 closeout 或 S5 entry。

## 当前下一步

`FIN-0.1-REPOSITORY-EVIDENCE-FREEZE-AND-SAFE-CLASSIFICATION-EXECUTION`

该动作只生成 content-addressed inventory、路径分类和 commit/rollback slice 建议；任何删除、取消暂存、提交或 tag 仍需另行批准。
