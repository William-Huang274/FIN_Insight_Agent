# 768 — FIN 0.1.3 S1 内源官方源 live 终态与 supplemental refresh

日期：2026-08-09

## Live 结果

唯一 commit-bound admission 已在 `ec7eefe437e2078074a43ecf975c79a759eaf92f` 上 exact-once 消费。三项计划源全部成功：DELL FY2026 10-K 主文档、MU Q3 FY2026 8-K 的同 accession Exhibit 99.1、TSM Q2 2026 6-K 的同 accession exhibit。共八次网络请求，零 retry、零模型、零 broad provider、零 embedding、零 rerank、零 Evidence promotion。共享 admission ledger 已 terminal success；原始请求、响应和解析正文全部 capture-first 留在 Git 外。

## 新发现与纠正

“三项 source target 成功”不等于“18 个 qrels 已齐”。MU results/HBM bundle 可以使用 8-K exhibit，但 MU regulatory/reconciliation bundle 的合同只允许 10-Q/10-K/6-K/20-F，不能把 8-K 改名塞进去。保存的 MU submissions response 已发现 Q3 FY2026 10-Q（filing 2026-06-25），正文并未在已消费 admission 内抓取。MU prepared remarks 也仍是独立 uncovered source。因此本轮三文档做成索引后的诚实上限预计是 17/18。

这不是 DeepSeek、BGE 或 reranker 问题，而是第一版 source plan 把“业绩新闻稿”和“监管财务底稿”合并得过粗。成功 live 保持 immutable，不重放、不扩大原 admission。

## 当前工作

从三份已捕获正文机械生成重叠 document segments，建立小型 supplemental BM25 与 ObjectBM25；document segment 必须标记为 `candidate_not_adjudicated_claim`，不得改写原文或直接成为 Evidence。通过 federated read-only retriever 与旧 BM25、新 full ObjectFTS 合并，不复制或覆盖历史大索引，也不比较跨索引的原始 BM25 score。随后重跑同一 18-row gate。

若实测为 17/18，才针对已经由 retained submissions capture 发现的 MU 10-Q 设计一次单文档、零 retry 的 successor acquisition；在此之前不准入 BGE/fusion/rerank。外源 broad-search blocker 继续独立保持 open。
