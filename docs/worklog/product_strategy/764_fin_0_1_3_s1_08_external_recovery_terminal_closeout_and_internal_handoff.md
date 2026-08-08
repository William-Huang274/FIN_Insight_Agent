# 764 — FIN 0.1.3 S1-08 external recovery 终态、诚实收口与内源交接

日期：2026-08-09

## Recovery exact-live

唯一 recovery admission 在 clean/synced `4334d7c45b1ac97185b8d2e954b0bb3ac531b6a6` 上 exact-once 消费：

- terminal=`completed_with_typed_failures`；
- official 三案全部 completed，network/document=`34/7`；
- Firecrawl network=`1`，首个请求即 `429 reason=credits`，其余 23 个 query no-network terminalize；
- total network=`35`；model／embedding／rerank／Evidence／retry／fallback=`0`；
- elapsed=`211,301 ms`；terminal/public digest=`959c95ed...402f / e912e3fa...f4eb`；
- official/shadow capture integrity=`108/108 objects + 49/49 refs`。

受控 DNS 握手已 live 证明：R1 的 `official_source_private_network_forbidden` 没有复发。33 个 query receipt 均保留 effective bound query，attempt budget digest 与 receipt 一致。Firecrawl quota stop 也从 R1 的 19 次必败调用收敛为 1 次。

## 质量结论

工程恢复通过不等于检索质量通过：

- official 在 12 个外源必需槽位只选出 `4/12`：三案 regulatory 各 1，NVDA supply 额外 1；issuer results、customer 与多数 supply 仍缺；
- 4 个 selected candidate 均有本地 typed date、identity、relationship 和 capture lineage，但只有 regulatory filing 一个来源族、3 个 unique documents；
- evaluator-only 12 个 Gold target group 的 target-in-pool／selected coverage=`0/12 / 0/12`，因此 ranking 不准入；
- 历史 Firecrawl 完整同矩阵仍为 `5/6` target-in-pool，但 date accuracy=`0`、状态 diagnostic-only；
- 历史腾讯同矩阵为 `0/6`，同样 diagnostic-only。

所以当前没有 production-qualified broad provider，也没有 external product acceptance。该失败不是 DeepSeek 问题，reranker 无法从缺失候选中补出目标。

## 边界与下一步

当前供应商轮测和 recovery 循环到此诚实收口：不 R3、不等 quota 自动补跑、不逐网址 patch。外源生产覆盖不足继续作为 release blocker；拿到新国内 Provider 时必须复用同一 Query Facet/qrels/gate 复验。

根据用户已批准的连续顺序，现在进入 `S1_INTERNAL_RETRIEVAL_QUERY_FACET_INTEGRATION`：先让 exact SQL／object、BM25／ObjectBM25、dense／Milvus 与 relationship graph 各消费自己的 typed facet/filter。其后扩大 qrels 并证明 candidate ceiling；只有通过后才比较 BGE、fusion 和 reranker，最后再测 Evidence／Claim／Workpaper／report 利用。

独立 `--preflight` CLI 在本轮曾检查 zero-call scope 并被当前 Project OS 拒绝；该命令没有签发 admission、没有联网。`--issue`／`--execute` 内部使用 exact-live scope，直接 exact-scope preflight=`pass`。这是 CLI 语义可读性 finding，不构成 Runtime/live 缺陷，也不扩展本轮修复。
