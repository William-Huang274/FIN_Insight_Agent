# 759｜FIN 0.1.3 S1-08 外源 combined clean authority

日期：2026-08-09
状态：`one exact-live authorized / admission not issued`

## 决策

基于 clean/synced implementation commit `3e6ab5cf7e8742d320041fa76fba1eb6df737b0f`、11 个专项测试、273 个 S1-08 回归以及零真实调用证明，批准一次外源 combined exact-live。

## 唯一允许的执行

- admission：最多 1 份；
- exact-live：最多 1 次；
- official primary：DELL/MU/NVDA 合计最多 48 次网络调用；
- Firecrawl shadow：24 个计划，最多 24 次网络调用；
- 总网络上限：72；
- model、embedding、rerank、Evidence promotion：0；
- retry、fallback、自动 replacement：0；
- 单次 timeout 30 秒、全链 900 秒。

authority digest：`282f7c3810a0033efd0f22a5bfca6dd33f77d8bdc301ca0e5ca6d42cf2107de7`。

## 不可放宽的边界

- Firecrawl 结果仍只是 locator candidate；
- 原始响应必须先 capture 再 parse；
- Provider 日期不拥有财务日期权威；
- 不做 reranker rescue；
- 失败后保留三案与两 lane 已完成结果；
- 本次权限不授权内源检索、BGE/fusion/rerank 或下游研究链。

下一步只允许：提交并推送本 authority 与 Project OS 投影，签发一份 fresh admission，然后 exact-once 执行并评估外源 candidate quality。
