# 766 — FIN 0.1.3 S1 内源 candidate ceiling 与 corpus refresh 入口

日期：2026-08-09

## 结果先行

内源 Query Facet 已经不只是“能编译”，而是第一次在真实本地资产上完成有界候选观察。修正后的 Attempt R2 得到 `SQL 0 / ObjectBM25 360 / BM25 360 / Graph 196`，并对 18 个 Milvus request 做资源资格检查。18 个 agent-curated、待 Owner 复核的 strict current target 只有 9 个进入候选池，required recall 为 1.0，因此 candidate ceiling 失败，BGE／fusion／rerank 不准入。

## 本轮纠正

最初观察把 reporting fiscal year 和 filing/publication calendar year 混成一个字段，导致 NVDA `Q1 FY2027` 在 2026 年文档索引中被误判为不存在。v1.1 将 SQL 的 `reporting_fiscal_years` 与文档/向量索引的 `index_filing_calendar_years` 分开。第一次 v1.1 观察又暴露 Milvus collection 已 release 后直接查询的生命周期错误；R2 显式 load 后完成 schema/ticker qualification。三个结果都保留为 immutable Attempt，不以新结果覆盖旧失败。

## 真实缺口

- Gold SQL 对 18 个 current target 为 `0/18`，说明 current exact fact mart 尚未覆盖本轮口径；
- TSM 在 BM25/ObjectBM25 corpus 中缺失，造成 6 个 lexical/object typed gap；
- MU current Q3、DELL current regulatory、NVDA current regulatory 等目标文件不在当前候选池；
- Graph 能提供关系候选，但没有足够 period authority，不能替代当前文件或精确事实；
- Milvus 66 万向量、schema、1024 维和五个 ticker coverage 均可识别，但配置指向的旧 BGE snapshot 不存在。本机 BGE-M3 可见，仍需 successor config 与候选 gate 后准入；本地 reranker 尚不存在。

因此当前主因是 corpus/index freshness 与 evidence-owner coverage，不是查询编译、DeepSeek、BGE 或 reranker 已被证明失败。排序只能重排已有候选，不能生成缺失材料。

## 当前边界

当前唯一产品工作项改为 `S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH`。先盘点本地 immutable raw/capture，按 target 识别 source、parser、transform、index 哪层缺失；如需重建，使用 successor asset，不原地修改旧索引。随后用同一 18-target qrels 重跑 candidate ceiling；只有 `18/18` 且 Owner review 完成，才进入 BGE-M3／fusion／reranker。Evidence、Claim、Workpaper、report 和 release 均未授权。external 4/12 coverage 仍是独立 release blocker。
