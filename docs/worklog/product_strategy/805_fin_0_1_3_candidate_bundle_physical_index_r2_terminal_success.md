# 805 — FIN 0.1.3 CandidateBundle physical-index R2 terminal success

日期：2026-08-10

阶段：S1

状态：terminal succeeded／五步计划第 1 步完成／第 2 步检索质量评估 current

## 运行结果

唯一 attempt `20260810_s1_candidate_bundle_object_bm25_bge_m3_milvus_linux_r2` 已消费，终态为 `terminal_succeeded_physical_sparse_dense_build`，无 retry。result digest=`6b239d7b2642efd51edc5f89587b28ab544a0e4a27d3a94a264a4c32975c1ce7`，authority=`a8889058d76a7fd0813ec722d4032356f83e750b0cb5a2696f142ec6ab6a08fd`。

同一六案 93-spec CandidateBundle 同时形成：

- ObjectBM25：93 条 records，`candidate_only_not_evidence`，record digest=`1e24445c...c0d1`；
- BGE-M3：本地 CPU 模型加载 1 次、12 batches、93 vectors；
- Milvus：database／collection create=`1/1`，insert=`12 batches／93 vectors`，flush／count／metadata／reopen=`2/2/1/1`；
- 目录型 store：6 files／7 directories／1,011,008 bytes，collection `current_seq=93`，1024 维、COSINE、FLAT；artifact digest=`aebe67d0c143e23c1bf3dd2887443caf338d44226af37699bfd3defd03d63f35`；
- whole-root 从 fresh working root 发布至 `/home/william/.cache/fin_insight/candidate_bundle_indexes/fin_0_1_3_s1/v2`，发布前后 artifact digest 一致。

network／provider／LLM／document fetch／vector search／rerank／Evidence promotion 均为 0。运行墙钟约 103 秒，其中 embedding 约 48.8 秒。

## 业务含义

此前 dense `3/18` 的一部分首因是旧 Milvus 根本缺少目标对象；现在六案 93 个经过冻结的 Candidate 对象已经真实进入同一 sparse/dense population，后续可以公平比较关键词、语义和 fusion。这个结果只回答“资料对象有没有被可靠建成可搜索索引”，不回答“搜索是否把正确公司、期间、关系、章节和内容排进前十”。

因此 `physical_sparse_index=true`、`physical_dense_index=true`、`shared_population_integrity=true`；`retrieval_quality`、Evidence Pack、外源补源、DeepSeek research 与 release 仍为 false。

## 下一步

按 Owner 批准的五步线进入第 2 步：对 DELL／MU／NVDA／ORCL／ASML／ANET 使用同一 typed Query Facet matrix，分别运行 exact、ObjectBM25、BGE-M3 与 fusion；必须先报告 candidate ceiling，再解释每个 miss 实际是错公司、错期间、错关系、错章节、内容过泛还是目标对象本身缺失，不能只给 Recall/MRR 数字。若 dense／fusion 不改善已声明的业务用例，就限制或不准入，不调权重制造通过。
