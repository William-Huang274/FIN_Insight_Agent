# FIN 0.1.2 S2-T03 paired canary 有条件权限与执行前缺口

日期：2026-08-03
状态：`conditional authority issued / execution not started / zero model calls`

## 结论

T03 的 MU 六调用 paired canary 已获得有条件权限：Fact、Claim、WWC 分别以完全相同的模型可见请求对比 `deepseek-v4-flash` stable 与 `deepseek-v4-pro` preview。只有后续最小 runner 与原子 capture 零调用 preflight 通过，权限才可进入一次真实执行。

本轮没有读取 credential，也没有调用模型、Provider 或执行网络。没有业务 Run/Artifact 写入。

当前 gate 验证为 `87 passed / 0 failed`，覆盖 S0 current contract、S1 production consumer/三案例行为、S2 StagePlan、T02 compiler 与本权限单。另行运行包含历史 S1 closeout 字节冻结测试的扩大集合得到 `86 passed / 1 historical finding`；finding 是 S1 当时的 compiler 字节与 S2-T02 计划内升级后的字节不同，因此只作为历史快照断言，不计入 current S2 gate，也不改写 S1 closeout。

## 为什么没有直接执行

T02 交付了请求 compiler、本地 validator/assembler、fake matrix 和内存 capture 对象，但没有为这六个调用交付独立真实 transport runner，也没有证明 capture 在本地校验前原子写入受限对象存储。若现在直接写一个临时 HTTP 脚本，可能再次出现失败输出只能从 telemetry 猜测、无法追溯的问题。

因此登记 `RC-P36-101`。它是 S2-T03 的项目内执行准备缺口，不是 DeepSeek 不遵循指令、Provider 故障或 sub2api 路由错误。

## 路由澄清

当前比较使用官方 DeepSeek `chat/completions` JSON-object 路线。此前用户提供的 sub2api 是 `gpt-5.5 /responses` strict-schema 备用路线，已单独停放并有显眼 handoff；两者不能混用，也不需要在本轮重新打开 sub2api。

## 实验边界

- 主要调用：`2 models × 3 families = 6`；
- 每调用 transport attempt：1；retry/fallback/provider hopping/prompt-only retry：0；
- 主实验输出预算：每调用 1400、合计 8400 tokens；总成本上限 USD 0.06；
- 语义失败：留存并继续其他独立 family；
- auth/transport/security/capture 失败：停止剩余调用；
- 业务 Run/Artifact：0；full-chain、九件套、owner acceptance、release：均不在本实验声明范围。

## 下一项

`FIN-0.1.2-S2-T03-PAIRED-CANARY-BOUND-RUNNER-ATOMIC-CAPTURE-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

只实现一个 runner/capture/preflight 包，不改模型可见合同、不扩大 family、不调用模型。preflight 通过后，才执行已签权的六调用 canary。
