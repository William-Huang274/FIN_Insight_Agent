# 726｜FIN 0.1.3 S1-08 P3A clean proof A1：restricted input 装配失败

日期：2026-08-08

阶段：`013-S1-08-P3A`

状态：A1 immutable failed；P3A 未完成，P3B／R4 未进入。

## 发生了什么

v4 工程实现已在当前 checkout 完成 `92 passed / 0 failed / 0 skipped`，随后从 clean/synced commit `6488af2a...6f59` 启动 clean Git archive／fresh Python process 复证。

首个 worker 的结果是：

- `90 passed`；
- `1 failed`；
- `1 skipped`；
- network／model／Provider／retry／admission／live=`0/0/0/0/0/0`。

失败节点为历史 R1 restricted capture manifest 审计；错误码=`s1_08_restricted_capture_object_missing`。A1 runner 只注入了 R3 capture store，却同时声明执行包含 R1、R2 capture replay 的完整 S1-08 历史套件。R1 对象缺失导致失败，R2 对象缺失导致一个测试 skip。

## 如何归因

这是 clean-proof runner 的输入装配缺陷，不是 v4 Runtime 断言失败，也不是 16-call 固定预算不变量失败。更不是 DeepSeek、Provider 或网络问题：本次外部调用全部为 0，P3A 新增测试没有失败。

同时不能因为失败“只是 runner”就宣布通过。clean-source 独立复证的目的正是发现当前工作树之外的隐式输入依赖；A1 已作为不可变失败证据保留。

## 当前边界与建议

- 不自动补跑，不修改 v4 Runtime，不进入 P3B，不执行 R4；
- 工作树 `92/92` 仍只算 engineering evidence；
- 下一次若继续，应保留同一 P3A scope，只修 proof runner 的 declared-input manifest：把既有受治理的 R1 request objects 与 R2 content captures 按 digest 注入 clean archive；
- 修复后使用新 attempt ID `A2`，不得覆盖 A1；
- A2 仍须双 clean archive、双 fresh process、0 skip、0 external calls、R1/R2/R3 输入前后 byte-stable。

这不会扩大产品范围，也不会改变 16-call ceiling 或 no-R4。

Project OS 在该失败投影后复核通过：既有 P3A scope=`pass / open blockers 0 / contract errors 0`，而 `additional_S1_08_live_attempts`=`blocked / RC-P36-157`。因此 A2 的 runner-only 修正仍可在原 P3A scope 内进行，但任何 live 路径继续 fail closed。
