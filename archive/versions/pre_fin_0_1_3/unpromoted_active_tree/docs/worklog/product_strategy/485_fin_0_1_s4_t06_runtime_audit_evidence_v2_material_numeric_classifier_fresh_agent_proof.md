# FIN 0.1 S4-T06：审计证据 v2 与 material-numeric classifier fresh-agent proof

日期：2026-07-30<br>
状态：双 disposable-runtime fresh proof 通过；R5 admission 未授权、未签发

## 目标

在不调用模型、不写目标 canonical runtime、不签发 admission 的前提下，独立重验 484 的实现是否与当前代码、MU exact input、三案例路径和失败原子性保持一致。

## 证明方法

proof generator 独立执行两次，每次都：

- 校验 implementation 的 4 个运行时代码 exact bindings；历史兼容测试由显式 supersession allowlist 管理；
- 在新的 disposable runtime clone 中对同一 MU execution identity 连续 prepare 两次；
- 校验 WorkUnit、Attempt、ResearchRun 均为 fresh，且 input digest 保持 `7887b5bb...a12e1`；
- 重跑 DELL/MU/NVDA v2 full-fake 正向路径和 material-numeric 负向路径；
- 重跑 R4 两个报告期路径、v1 历史语义、capture-v2 原子回放/不晋升和凭据拒绝；
- 编译但不写入 prospective R5 admission payload。

## 结果

- 两次独立 proof 输出完全一致；
- 每案正向 fixture：`6 nodes / 12 callbacks / 12 captures / 9 Artifacts`；
- 每案负向 fixture：第 1 个 callback/capture 后终止，0 Artifact；
- R4 两路径均为 `reporting_period_label / terminal=false`；
- 目标 SQLite digest、object-tree digest 和逻辑快照完全不变；
- prospective R5 admission digest：`3457fded...bd6e8`；
- prospective admission 文件不存在，issued/consumed/execution 均为 false；
- proof contract tests：`4 passed`；
- S4-T06 完整合同回归：`227 passed`；
- model/provider/network/source/tool/admission/target writes/paired/owner/T07：全部 0。

## 边界

本轮证明 fresh-agent state isolation、当前代码/input 一致性和确定性路径，不证明 DeepSeek R5 行为、最终 9 Artifact L1、paired quality 或 owner acceptance。MU R4 仍是 immutable failed / 0 Artifact；automatic R6=false。

## 下一步

`S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-CLASSIFIER-FRESH-EXACT-ADMISSION-R5-AUTHORITY-DECISION`

下一步仍是零调用权限决策。未经后续明确授权，不写 admission、不执行 R5。
