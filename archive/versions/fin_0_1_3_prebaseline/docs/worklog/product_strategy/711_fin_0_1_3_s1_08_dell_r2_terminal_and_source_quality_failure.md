# 711 — FIN 0.1.3 S1-08 DELL R2 terminal 与 source-quality failure

日期：2026-08-08
阶段：`013-S1-08`
状态：`exact-live complete / reliability pass / product source quality failed / no R3`

## 1. 唯一 R2 结果

clean/synced `b0e8cf0d...c790` 上，唯一 R2 admission 在 shared ledger reserve 后执行并终态：

- status/code=`complete / dell_current_search_r2_complete_with_typed_gaps`；
- network/model/provider/retry=`16/0/0/0`；
- query attempts/checkpoints=`11/11`；
- accepted/selected/typed gaps=`2/2/3`；
- shared admission receipt=`terminal`；
- terminal digest=`af9a02fe...c33a`。

两条 candidate 实际指向同一份 2026-07-06 DELL 8-K，只是分别晋升到 issuer-results 与 regulatory-reconciliation 角色，因此 unique source 只有 1。

## 2. 产品质量验收

- 五个 role 都有 candidate 或 typed gap：`5/5`，说明终态物化完整；
- navigation noise fetch=`0`，说明噪声门有效；
- qualified-document yield=`2/16=0.125`，低于冻结门 `0.5`；
- customer、supply-chain、market 三个角色都是 gap；
- evaluator-only Gold match：matched source=`0`，DELL 四组 target-in-pool recall=`0.0`，selected coverage=`0.0`；
- ranking admitted=`false`。

所以“链路跑完”是真的，“检索质量通过”不是真的。S1-08 不能关闭。

## 3. 为什么失败

主要问题仍是 source coverage，而不是模型：structured IR locator 和 external site search 都 unavailable；普通 IR discovery 对大量 locator 无法证明 publication date 或 Evidence Slot fit，16 次调用耗尽前没有拿到 customer/supply evidence。receipt 中 `evidence_slot_fit_unproven=339`、stale=`88`、published-date-unproven=`36`、route-unavailable=`6`、ceiling-reached=`4`。

本轮没有调用 DeepSeek，也没有进入 ranking，因此不能归因模型或 reranker；也不能把 typed gap 解读成“公开资料不存在”。

## 4. 停止与下一步

按 Q-H stop rule，不自动进入 R3，不启动 MU/NVDA、BGE/Milvus、ranking 或 S3。下一项只做 post-R2 disposition：决定在 S1-08 内补哪一类真正 operational provider/locator coverage，以及是否调整 evidence acquisition budget；不得继续逐网址打补丁。
