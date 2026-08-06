# 671 — FIN 0.1.3 S2-05 DELL layered replacement exact-live authority

日期：2026-08-07

状态：`authority compiled / commit-push and scoped preflight required / not issued`

## 决策

用户在看见“下一步应使用新 successor runner 单独签发一次 DELL replacement exact-live”后明确回复“继续”。该授权只覆盖一份 DELL admission 和一次 exact-once DeepSeek Pro 执行；不覆盖 MU、NVDA、第二次 replacement、supervisor correction 或业务晋升。

## 入口审计发现与修复

结构修复虽已实现 `execute_case_layered`，但生产入口仍调用旧 `execute_case`。若直接签发，会继续使用 first-failure 路径。现已把 production entrypoint 绑定到 layered successor，并新增零调用测试证明 preflight 暴露 `capture_first_full_chain_then_layered_evaluation`，执行完成状态只认 `terminal_completed_layered_raw_evaluation`。

入口/authority 聚焦回归=`42 passed`，宽 S2 回归=`120 passed`；本项 Provider/网络/admission=`0/0/0`。

## 运行边界

- 最多 12 calls，通常六 Specialist 时为 10 calls；
- retry/fallback/second replacement=`0/0/0`；
- transport、parse、capacity、不可用或污染 Lead 立即停止；
- Lead 后 schema/numeric/financial-semantic finding 完整收集到 Verifier；
- raw chain 完整即可进入 hidden scoring，但 S2-05 business promotion 永远为 false；
- 原 R1 与 collect-all 保持 immutable。

下一步：提交并推送入口绑定与 authority；运行 scoped Project OS preflight；credential 仅检查 presence；签发一次 admission 并 exact-once 消费。
