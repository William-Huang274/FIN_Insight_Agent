# 673 — FIN 0.1.3 S2-06 DELL supervision boundary 与 campaign disposition

日期：2026-08-07

状态：`zero-call engineering pass / DELL raw complete-quality-fail / MU authority may be considered separately`

## 为什么不能继续把 29 条 finding 当 29 个问题

DELL replacement 的 typed schema 和十节点链已经成功，当前问题集中在研究实质与 evaluator 精度。path-aware evaluator v1.1 对 immutable raw capture 重算后为 `26 findings = 2 L1 + 1 L2 + 23 L3`：

- 2 个 L1 是同一真实问题在 Specialist 与 Writer 的传播：把“中个位数”无权精确化成 `4–6%`；
- 1 个 L2 是 Verifier false-green；
- 4 个 L3 是 Specialist 没有显式 counterevidence；
- 19 个 L3 是未校准 scenario/WWC threshold。

原来的 `10-K→10`、跨 section OCF/P-E 拼接和 conditional threshold→L1 三类误报已关闭。真实 L1 没有被放宽。

## Supervisor 能做什么

本地 deterministic runtime 只可把 `4–6%` 删除/降级回 Evidence 允许的方向性口径、把无依据阈值标为 unvalidated scenario，并在模型 Verifier 漏报时阻止晋升。它不能代写 counterevidence、strongest counter-thesis、阈值依据、thesis 或估值结论。

若要让模型补研究内容，必须新建 `supervisor_augmented` correction，给它可见 finding 和本案 Evidence 引用，使用新 candidate identity；不得暴露 hidden Gold，也不得覆盖 raw。该能力本轮未调用、未证明。

## 为什么现在不先扶正 DELL

Experiment A 的目的首先是测量三案自然 raw 表现。若看过 DELL 结果后修改模型可见合同或把纠错经验注入 MU/NVDA，会污染公平比较。因此：

1. DELL 永久记为 `raw_complete_quality_fail`；
2. 当前不执行 DELL supervisor 模型纠错；
3. MU raw admission 可以进入单独 authority decision，但不会自动签发；
4. MU/NVDA 必须沿用同一冻结的 model-visible contract，不能读取 DELL correction 或 hidden targets；
5. 三案 raw 完成后，再在 S2-06 分案形成 corrected candidate 与能力归因。

实际零调用 correction ledger 已写入忽略目录 `.codex_runtime/fin013_s2_06/DELL/`，共 26 rows，SHA-256=`a8640de2...66c47`。focused=`17 passed`、S2-05/S2-06 broader=`70 passed`、compileall 和 immutable raw capture hash 复核通过。本轮模型、Provider、网络、MCP、业务晋升均为 0。
