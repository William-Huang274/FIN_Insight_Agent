# Evaluation records / 评测记录

2026-09-11 · Open-label local qualification, not a blind benchmark.

- `retrieval-queries.json`: 28 exact questions, development/validation split and labeled source anchors.
- `retrieval-results.json`: per-query top-five candidates and measured metrics for BM25, dense retrieval and hybrid reranking. Four unanswerable queries are not included in positive-query accuracy denominators.
- `retrieval-source-manifest.json`: 739 source-node locators, original-content hashes, capture identity and corpus digest. Source text is excluded. The HPE material was user-supplied; Microsoft and RFC entries retain their public source URLs. Re-extracting changed documents does not guarantee the same chunk IDs.

These records allow checking the published Hit@5 and anchor Recall@5 arithmetic without an API key. MRR@20 is retained from the original measured receipt; only top-five candidates are distributed here, so this bundle does not independently reconstruct MRR@20. To rerun ranking, supply the original scoped `nodes.json` (or create a new corpus with newly labeled anchors) to `scripts/qualification/retrieval_acceptance.py`. Do not reuse these source IDs against unrelated chunks.

这些文件公开题目、标注、逐题前五候选及原文定位信息，可不调用 API 核对 Hit@5 与锚点 Recall@5。它们不包含完整来源正文、私有模型响应或账户信息，也不代表可仅凭源码完全重建相同语料。验证结果在工程修复时已可见，因此不能称为盲测。

```powershell
python -m scripts.qualification.verify_public_retrieval
```
