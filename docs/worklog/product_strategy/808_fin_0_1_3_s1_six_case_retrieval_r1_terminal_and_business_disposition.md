# 808 — FIN 0.1.3 六案检索 R1 终态与业务处置

日期：2026-08-10

阶段：S1／五步计划第 2 步

状态：exact-once terminal success；ObjectBM25 主路、BGE shadow、fusion 不作全局默认

唯一 attempt `20260810_s1_six_case_candidate_bundle_exact_object_bm25_bge_m3_fusion_r1` 已消费并成功结束。结果 digest=`dfc2e69a...914a`；实际执行 `1` 次 BGE-M3 load、一次 `72` query encode、`72` 条 ObjectBM25 query 和按六案分组的 `6` 次 Milvus search，network／Provider／LLM／document fetch／rerank／Evidence promotion 均为 `0`，没有 retry。

前三案 18 条 Owner qrels 中有 2 条目标先天不在 93-object population。对其余 16 条，ObjectBM25 和 fusion 都达到 Recall@10=`1.0`，BGE=`0.875`；MRR 分别为 `0.7948 / 0.8038 / 0.7902`。这不是 fusion 的全局产品胜利：按案例拆开后，fusion 只在 MU 局部提高，DELL 和 NVDA 都低于纯 sparse；54 条 Slot 标签诊断中，ObjectBM25 的 MRR=`1.0`，fusion=`0.9878`，BGE=`0.8557`。

业务上，Microsoft 的 AI 投入能被三条路线正确找出，但只可作行业需求 read-through；Dell 的 Micron supply 目标被 sparse 排第一，却从 BGE 前十消失；Dell 的精确风险段被综合业绩稿压到 sparse 10／dense 7／fusion 8；Micron 的 dense 结果多次找对公司却回答错财务问题。留出案例更暴露“标签命中不等于研究证据”：ANET 的 Land 被标为 capacity，ORCL 的债券利率被标为 valuation，ASML 只有业绩、销量、毛利率和现金表格而缺五个 required Slot。

处置为：ObjectBM25 保留 Candidate 主路；BGE-M3 只作 shadow／候选扩展；fusion 的机械 `gain=true` 不作为全局准入，本轮不调权、不启用 reranker。第 3 步先逐项审 DELL 的事实、机制、反证、WWC 和真实 gaps，再在核心实现不变的前提下迁移其余五案。只有审计后仍缺的内容才进入 external supplement；DeepSeek 继续等待冻结 Evidence Pack。

R1 证明物理检索可以完成、结果可解释，不证明 93 个对象内容充分，也不证明 Evidence、研究综合、报告或 release。成功结果不重跑，机械 flag 不改写；业务处置以独立 successor 记录。
