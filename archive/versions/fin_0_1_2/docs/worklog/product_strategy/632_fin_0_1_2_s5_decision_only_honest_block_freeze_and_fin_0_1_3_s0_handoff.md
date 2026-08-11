# 632 FIN 0.1.2 S5 decision-only honest-block 冻结与 FIN 0.1.3 S0 交接

日期：2026-08-06
状态：`FIN_0_1_2_closed_honestly_blocked / release_not_qualified / FIN_0_1_3_S0_entry_ready`

## 目标

执行 T08 后冻结的下一项：不机械运行已知会失败的 RG1–RG5，不改写 0.1.2 历史 exact evidence，准确冻结 0.1.2 已实现能力、已知发布阻断和 FIN 0.1.3 的首个责任层。

## 关键判断

0.1.1 的旧 S5 结论不能直接复用。0.1.2 已新增三案例 current source-grounded exact run、27 个业务 Artifact、三案 bounded R2、Workbench current projection、typed return/replay 和一次本地 bounded NVDA R3 动作；这些进展必须保留。

但以下问题仍使 FIN 0.1.2 无法形成 release candidate：

- DELL `23.931B` 季度值被标为 FY2025 全年，属于 confirmed L1；
- 三案来源/Graph 覆盖和研究内容质量未达到 FIN 0.1.3 新硬门禁；
- current create→run→actual repair→rebuild→review 与 burden 未闭环；
- RG1–RG5 没有正式候选可验，不能用内部 recoverability 代替 release qualification。

## 新发现：0.1.3 namespace 冲突

仓库保留早先已被合并/放弃的 `FIN 0.1.3` 命名资产：18 个 release config、16 个 runtime config、13 个 contract test，共 47 个；0.1.2 active-suite manifest 仍有 7 个 `0_1_3` 引用。新正式 0.1.3 若直接沿用这些名称，可能把旧 proof 当成新版本证据。

该问题归 `013-S0-01`，本 S5 只记录和交接，不删除、重写或静默晋升旧证据。S0 必须按 exact digest 分类为 historical/reusable，并签发新的 canonical delta inheritance 与 active-suite successor。

## 实现

- 新增机器可读 S5 closeout/handoff：`configs/releases/fin_ia_0_1_2_s5_decision_only_honest_block_candidate_freeze_and_fin_0_1_3_handoff_v1_0.json`。
- 新增 content-addressed、非膨胀、namespace 和 zero-call 合同测试。
- FIN 0.1.2 终态为 `closed_honestly_blocked_decision_only`，`release_qualified=false`。
- FIN 0.1.3 只进入 `013-S0-01`；FIN 0.2 定义不变。

## 验证与边界

新 closeout 合同测试 `5 passed`。与 0.1.1 历史 S5 freeze 一起跑的相邻集为 `12 passed / 1 failed`；唯一失败是旧 S5 decision 将一个后来继续维护的 version-lineage 文档 SHA 当作永久锚点，当前 HEAD 已与旧 digest 不同。该失败不由本轮文件引起，属于既有 RC-P36-128 mutable-source-SHA test debt；本轮不改写旧 decision 或更新其 SHA，交 `013-S0-02` 分离 historical receipt 与 living source。

本包只运行本地确定性合同测试，不运行模型、Provider、source、业务网络、full-chain、正式 RG、tag 或 release。没有读取 reviewer credential 或 credential digest，也没有修改 private store。

## 下一步

执行 `FIN-0.1.3-S0-01-DELTA-INHERITANCE-NAMESPACE-AND-SECRET-SAFE-CURRENT-TRUTH-BASELINE`，先解决新旧 0.1.3 命名/证据边界和 current truth 一致性，再进入 shared runtime 与金融语义 truth-oracle。
