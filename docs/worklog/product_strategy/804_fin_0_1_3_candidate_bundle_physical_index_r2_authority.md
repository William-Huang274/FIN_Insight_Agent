# 804 — FIN 0.1.3 CandidateBundle physical-index R2 authority

日期：2026-08-10

阶段：S1

状态：issued／unconsumed

## 签发结果

clean/synced commit=`afc627f5aef90c9652bae3d21a5be5b7aaa0892b` 上重新核对 Ubuntu 包、BGE 五个模型文件、Milvus directory profile、93-spec manifest、fresh working/final roots、microcanary result 和 clean A2 proof。Project OS scoped preflight 通过。

authority=`a8889058d76a7fd0813ec722d4032356f83e750b0cb5a2696f142ec6ab6a08fd`，attempt=`20260810_s1_candidate_bundle_object_bm25_bge_m3_milvus_linux_r2`。

唯一允许：1 次本地 CPU BGE load，93 vectors／12 batches；同一 93 specs 写入 fresh ObjectBM25 和 fresh Milvus v2 collection；完成 flush／count／metadata／reopen、private receipt、directory artifact 校验与 whole-root publication。禁止 network／provider／LLM／search／rerank／Evidence，0 retry。

R1 failed root 与 microcanary root 均不可复用；本 authority 不是执行成功或检索质量结论。
