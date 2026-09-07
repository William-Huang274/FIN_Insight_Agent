# 073 Case Truth split zero-call R2：证明脚本混淆本地合同与传输投影

时间：2026-08-17

## 结果

R2 绑定 clean/synced commit `d8a3820a4075d5f581b1057dc87a1f349dfd149a`，在模型、Provider、网络、embedding、候选晋升和报告发布均为 0 的情况下终止。失败发生在零调用 runner 检查 DeepSeek strict wire tool 时：代码错误地从 wire projection 读取 `minItems`，触发 `KeyError: minItems`。

## 业务与工程含义

这不是 Case Truth 金融合同失败，也不是 DeepSeek 不遵循合同。canonical local tool 仍要求每个 cell 恰好提交 3 个 surface，本地 Validator 仍执行穷尽覆盖、重复、未知 alias、跨 Case 和错误 absence 校验。DeepSeek strict adapter 为兼容 Provider 会移除部分服务端不支持的 JSON Schema 关键词，projection receipt 同时明确 `finance_contract_weakened=false`，因为这些约束仍由本地权威执行。

根因是证明脚本把两种责任混在同一个断言里：

- canonical tool 用于检查完整金融与数量合同；
- wire projection 用于检查 Provider 可传输形状和投影 receipt；
- local Validator 才是跨字段和穷尽性最终权威。

## 处置

R2 authority 与 terminal failure result 保持不可变，不改写为成功。runner 已改为分别检查 canonical exact count 和 wire compatibility，且仍要求投影没有放宽金融合同。完成整库回归、clean commit/push 后，只能签发 fresh R3 零调用 proof；R2 不授权自然 semantic canary、R7 修复或报告验收。
