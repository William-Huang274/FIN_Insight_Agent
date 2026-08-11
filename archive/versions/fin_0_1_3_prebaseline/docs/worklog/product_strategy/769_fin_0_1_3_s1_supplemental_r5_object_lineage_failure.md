# 769 — FIN 0.1.3 S1 supplemental R5 Object lineage 失败处置

日期：2026-08-09

## 实测结果

三份已经 capture-first 保存的官方文档被机械切分为 292 个候选片段，分别建立 292 条 BM25 与 292 条 ObjectBM25。R5 在零网络、零模型、零 embedding、零 rerank、零 Evidence promotion 下完成历史资产与 supplemental 资产联邦，候选数为 `SQL 0 / ObjectBM25 369 / BM25 297 / Graph 196 / Milvus 0 qualification-only`。

## 为什么 R5 不能进入 qrels

ObjectBM25 共用的 compact record 仅保留检索文本和过滤字段，丢掉 source URL、publication date 与 accession。对 supplemental MU 片段，后续 lineage resolver 因找不到精确 accession，回退到 ticker/year/form 的唯一历史文档，从而错误绑定为上一季度。相同片段在 BM25 中仍保留正确 2026-06-24 URL 和 accession，证明源采集与分段没有错，错误属于 Object 索引压缩和 fallback 边界。

R5 和 v1 manifest 作为失败证据保留，不删除、不覆写，也不用于宣称 17/18。该问题不是 DeepSeek、BGE 或 reranker 问题。

## 有界修复

Object compact record v1.1 保留 source URL、publication date、accession 及 candidate-only 元数据；当 record 内三项 lineage 完整时优先采用 embedded lineage，不再用旧 manifest 猜测。用新的 `v2` 私有目录和 v1.1 manifest 重建同一批 292 条记录，再签发新的 R6 零调用观察。只有 R6 血缘和候选门禁通过后，才允许生成 qrels successor；BGE/fusion/rerank 继续 blocked。
