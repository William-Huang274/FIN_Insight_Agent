# 668 — FIN 0.1.3 S2-05 DELL R1 quarantined collect-all readiness

日期：2026-08-07

状态：`zero-call engineering pass / one diagnostic admission authorized not issued`

## 目标

用户要求继续把 DELL 链路跑到末端，集中暴露问题后再合并修复。本项不把失败的 formal R1 改写为成功，也不重跑 Lead；只建立一条不可晋升的下游诊断路径。

## 实现边界

- 复用 immutable R1 Lead capture，原 Lead 仍保持 `experiment_a_unbound_numeric_surface`；
- 最多新增 9 次调用：6 Specialist、1 Synthesis、1 Writer、1 Verifier；
- 每个 raw 输出先 capture，再运行正式 validator；失败写 finding 后继续；
- 只有 raw 无法解析/使用时才注入 typed local placeholder，并单独记录；
- 所有输出位于 `quarantined_non_promotable`，不具 formal raw candidate、hidden scoring、business promotion、paired 或 Owner 资格；
- retry/fallback/第二次 diagnostic/MU/NVDA 均为 0。

## 零调用证据

- diagnostic focused=`2 passed`；
- formal runtime＋diagnostic=`29 passed`；
- mutation 同时在 Specialist、Synthesis、Writer 注入输入外数字，诊断仍保留逐阶段 findings 并到达 Verifier；
- compile、diff check、secret scan 通过；
- 本项模型/Provider/网络调用=`0/0/0`，diagnostic admission 尚未签发。

下一项：提交并推送干净代码链，运行 scoped Project OS diagnostic override preflight，签发一份独立 admission，然后执行一次 9-call downstream collect-all。
