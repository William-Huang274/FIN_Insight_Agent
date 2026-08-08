# 753 — FIN 0.1.3 S1-08 统一 Query Facet 零调用实现

日期：2026-08-08

## 为什么做

外源 Provider 对照证明，弱查询会把检索缺口错误归因给 Provider；代码审计同时确认内源 exact／BM25／dense／graph 也没有共同的 route-specific query contract。BGE 和 reranker 只能排序已有候选，无法找回未进入候选池的目标。因此本轮不调用 DeepSeek、不跑 live，先实现外源与内源共同上游的 Query Facet。

## 实现结果

- 将 60 个 route-specific SearchIntent 按 `case × Evidence Slot × evidence owner × language` 合并为 36 个共享 Query Facet Plan，保留 60/60 intent lineage；
- 每个计划都生成 exact lookup、lexical、semantic、typed one-hop graph、negative／forbidden expansion 和 route-specific filters；
- external route 覆盖为 `36 official primary + 24 semantic shadow`；每个计划同时声明 internal exact-object、BM25、dense 与 relationship-graph 的未执行查询面；
- 关系型查询优先使用证据披露方自身词汇：Microsoft→Azure AI infrastructure／capex，Micron→HBM output／capacity，TSMC→CoWoS／advanced packaging；被研究公司产品只作次级连接词；
- 去除短词被长词包含造成的重复，如 `CoWoS capacity capacity`；
- 模型原子只允许 metric／product／mechanism／synonym。模型不得提供 identity、period、relationship、domain、route、URL 或 Gold；合法原子只能新增受控 lexical／semantic 查询，不能覆盖本地 filters；
- cross-scope、URL、future period、identity alias、duplicate、over-budget、plan tamper 和 input permutation mutation 均已覆盖；
- proof=`36 plans / 60 intents / 12 case-slots / 72 exact / 72 lexical / 36 semantic / 36 graph`，专项=`13 passed`，S1-08 全回归=`228 passed`；network/provider/model/document/Evidence/retrieval/embedding/rerank=`0`。

## 诚实边界

该实现证明查询合同和基础本地 deterministic variant，不证明这些查询能在真实 Provider 或本地索引中找到目标。`target-in-pool`、日期准确性、来源多样性、成本、延迟、内部 qrels、BGE／rerank 增益和下游 Claim／Workpaper 使用均未测。当前也没有调用 DeepSeek；模型辅助是否值得接入必须由下一项三路对照决定。

## 下一步

进入 `S1_08_QUERY_FACET_THREE_WAY_DELL_MU_NVDA_EVALUATION`：

1. 用户原句／旧 raw query；
2. 当前 deterministic local Query Facet；
3. DeepSeek query atoms＋同一个 local compiler。

先用相同冻结候选池／capture replay 比较 facet coverage、错误实体／期间／关系方向、重复率和稳定性；如需最小自然 canary，必须另行限制为 query atoms，不得让模型输出 URL、日期或最终物理查询。只有模型辅助产生可复现增益且不扩大污染，才进入后续 combined external live。外源关闭后仍按已登记顺序回到内源 exact／BM25／dense／graph、qrels/candidate ceiling，再决定 BGE／fusion／rerank。
