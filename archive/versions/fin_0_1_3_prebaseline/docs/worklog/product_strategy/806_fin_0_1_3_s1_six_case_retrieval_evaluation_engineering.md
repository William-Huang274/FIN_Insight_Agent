# 806 — FIN 0.1.3 六案检索评测工程证明与真实 R1 入口

日期：2026-08-10

阶段：S1／五步计划第 2 步

状态：零模型 full-shape engineering pass／clean exact-once authority 待签发

## 这一步实际解决什么

第 1 步已经证明 93 个候选对象真实进入 ObjectBM25 与 BGE-M3/Milvus，但没有证明搜索是否把正确资料排到前面。本工作包把 DELL、MU、NVDA、ORCL、ASML、ANET 放进同一套评测，固定比较关键词、语义和 1:1 RRF fusion，并要求每个失败给出业务原因，而不是只报 Recall/MRR。

评测共有 72 个查询：前三案 18 条 Owner-reviewed qrels，另有六案各 9 个 canonical research Slots。查询从已冻结 Query Facet、通用研究合同、案例 profile 与行业 Pack 编译；候选全部生成后才加载目标标签，查询中禁止 target ID、标准答案 URL 和 slot filter。真实 R1 允许 1 次本地 BGE load、一次 72-query encode、按公司分组 6 次 Milvus search、72 次 ObjectBM25，禁止网络、Provider、LLM、fetch、reranker、Evidence promotion 与 retry。

## 零模型先暴露的业务事实

即使排序器完美，当前 93-object population 也只有 36/48 个 required Slots 有候选：

- DELL、MU、NVDA：各 8/8；
- ORCL：5/8，缺 demand、regulatory、counterevidence；
- ASML：3/8，只有 operating、pricing/mix、cash，缺 demand、capacity、relationship、regulatory、counterevidence；
- ANET：4/8，只有 operating、pricing、capacity、cash，缺 demand、relationship、regulatory、counterevidence。

Owner qrels 为 16/18；缺少 NVDA regulatory 精确目标，以及 NVDA case 下的 MU supply target。它们属于上游对象池空洞，dense/fusion 不能“搜回来”，后续必须保留 typed gap。

## 业务错误解释面

物理索引为了最小化搜索 schema，没有单独保存 disclosure owner 与经济关系方向。如果只看 `8K_EARNINGS::` 或 `SUPP::` 前缀，会把“谁在谈谁”判错。因此评测按 vector ID 回接同一 digest-bound Candidate spec，附上 disclosure owner、relationship direction、source record、source type 与 publication date；这个 join 不改 rank，也不晋升 Evidence。

错误至少区分：目标上游不存在、同 case 但错研究问题、错披露方／错关系方向、错报告期间、以及相邻或过泛内容排在精确目标之前。最终报告必须给出真实 top candidate 的标题/预览/来源，让 Owner 看得懂为什么算错。

## 工程与环境验证

focused contract 当前 8 passed；覆盖 72-query 无泄漏编译、93-object identity、case filter、六组 dense search、cross-case rejection、RRF 稳定、业务错误分类与失败 terminal envelope。零模型 implementation proof 还验证 duplicate/cross-case/order mutations。

WSL admission 检查发现原 policy 误指向不存在的模型缓存，已改回第 1 步实际验证的 `/mnt/d/hf_models/BAAI__bge-m3`；隔离环境缺 Pydantic，已按仓库依赖锁定补入 2.13.4。BGE 五文件摘要、R2 directory artifact、ObjectBM25 files 与检索依赖均只读资格通过。以上都发生在真实 R1 前，未加载模型、未搜索向量。

## 边界与下一步

当前只可在 clean/synced 提交后签发一次 R1 authority，再执行一次本地 exact evaluation。真实结果出来前，dense/fusion 不准入；slot label 只诊断 upstream tag，不等于 Evidence 有用。R1 成功后进入第 3 步 Evidence Pack：先逐项审 DELL 的事实、机制、反证和 what-would-change，再不改核心迁移其余案例。只有实际 residual gaps 才进入第 4 步外源补源；DeepSeek 仍在第 5 步。
