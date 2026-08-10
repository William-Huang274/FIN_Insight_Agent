# 807 — FIN 0.1.3 六案检索 R1 authority

日期：2026-08-10

阶段：S1／五步计划第 2 步

状态：issued unconsumed

clean/synced implementation commit=`9f1ad280b5a45f765676093afca05c907db11012`，authority digest=`473594ac72e50f2ea36efa02482d907f84cc0f58e85bb142eb9fe402823b3ddd`，唯一 attempt=`20260810_s1_six_case_candidate_bundle_exact_object_bm25_bge_m3_fusion_r1`。

签发时从 Ubuntu-22.04 隔离环境重新核对：R2 directory artifact=`aebe67d0...3f35`、93 条 ObjectBM25 文件、BGE-M3 五个模型文件、Torch/ST/Transformers/pymilvus/milvus-lite/rank-bm25 与 Pydantic 2.13.4；Project OS scoped preflight 为 pass。资格检查没有加载 embedding model、没有搜索向量。

唯一允许的运行形状为：72 个 ObjectBM25 query、1 次 BGE model load、1 次 encode／72 query vectors、按 DELL/MU/NVDA/ORCL/ASML/ANET 分组的 6 次 Milvus search；0 network/provider/LLM/document fetch/rerank/Evidence，0 retry。fusion 固定 1:1 RRF，不准看结果调参。

下一步必须先提交并推送本 authority，再在同一已绑定实现上消费一次。authority 本身不代表检索质量、Evidence Pack 或研报能力通过。
