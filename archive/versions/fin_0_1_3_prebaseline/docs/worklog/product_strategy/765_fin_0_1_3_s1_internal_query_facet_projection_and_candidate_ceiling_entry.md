# 765 — FIN 0.1.3 S1 内源 Query Facet 投影与候选池入口

日期：2026-08-09

## 本轮完成

外源 current provider round 已诚实收口后，按用户批准的连续计划进入内源检索。统一 Query Facet 的 36 个中英 plan 被合并为 18 个双语研究束，并确定性投影为 90 个 route-specific request：SQL、ObjectBM25、BM25、Milvus、relationship Graph 各 18 个。

核心纠正不是增加关键词数量，而是把研究对象和证据披露方分开。DELL 的 customer slot 可以由 MSFT 披露，supply slot 可以由 MU／NVDA／TSMC 披露；内容路由使用 evidence-owner ticker，TSMC 映射为本地 `TSM`，同时保留 subject、relationship direction、period、as-of、negative entities 和 forbidden expansion。SQL 不接收自由文本，ObjectBM25／BM25／Milvus 分别接收 exact／lexical／semantic query，Graph 只接收 typed relationship。

专项合同测试 `11 passed`。物化 proof 为 `18 bundle / 90 request / 60 cross-entity request / 15 TSMC→TSM projection request`；network／provider／model／document／retrieval／embedding／rerank／Evidence 均为 0。因此当前只能记为 `zero_call_engineering_pass`，不能记为召回、RAG、研究质量或 release 通过。

## 新发现与边界

本地真实资产并非同质：BM25 文档索引和 ObjectBM25 FTS 有 DELL／MU／NVDA／MSFT，但当前看不到 `TSM`；Gold SQL 有 `TSM`，但 current-quarter exact authority 可能稀疏；Graph 需要按真实 direction 检验；Milvus 数据库和 66 万余向量存在，但配置中的模型 locator 与本机实际 BGE-M3 路径需要资格化；本地没有 BGE reranker-v2-m3。

这意味着下一轮不能直接做统一融合分数。先分别测 exact、lexical、graph 的 candidate ceiling，并把 dense route 的资源状态变成 typed qualification；target 不在 pool 时归因 query／route／index／corpus，而不是让 BGE／reranker“救”。历史 qrels 多为 agent-authored diagnostic，本轮新增 qrels 在 Owner 复核前必须标记 `agent_curated_pending_owner_review`。

## 当前下一步

当前唯一产品工作项是 `S1_INTERNAL_CANDIDATE_CEILING_AND_QRELS_GATE`：对 DELL／MU／NVDA 的 18 个 bundle 执行只读本地候选生成，保存 route contribution、期间／实体／关系 hard negative 和 typed gap；同时完成 Milvus／BGE resource qualification。candidate ceiling 通过后才进入 BGE、fusion 与 rerank；最后再证明 Evidence／Claim／Workpaper／report utilization。外源覆盖不足仍是独立 release blocker，没有因内源工作开始而关闭。
