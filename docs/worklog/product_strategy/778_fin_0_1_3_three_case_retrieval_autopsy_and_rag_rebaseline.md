# 778 — FIN 0.1.3 三案例检索尸检与 RAG 重定基

日期：2026-08-09

归属：FIN 0.1.3 / S0-S1 诊断，向 S3-S5 传递

状态：`three_case_diagnostic_complete / zero_product_code_change / rag_rebaseline_decision_current`

## 1. 用户授权与执行边界

用户要求按冻结的 1–8 顺序自然跑完，不急于修复，只有“不修就不能继续诊断”时才允许最小修正。本轮唯一修正是私有诊断脚本把错误的 slot 字符串改为仓库真实枚举；未修改产品代码、索引、qrels、模型合同或生产状态。

## 2. 执行结果

- A 当前自动内源：18 bundle / 90 terminal；ObjectBM25 369、BM25 297、Graph 196、SQL 0、dense 0 qualification-only。
- B Codex 监督同工具：只改 36 个 sparse/object query。A→B Recall@1=`4/18→7/18`、Recall@5=`16/18→13/18`、Recall@10=`16/18→17/18`、MRR@10=`0.5111→0.5849`。
- 外源 immutable replay：digest=`387ee50c...7358`；runtime recovery pass，required-slot=`4/12`、hidden target-in-pool=`0/12`、source family=`1`，产品覆盖失败。
- C 独立参考研究：完成 DELL/MU/NVDA 的官方 IR、电话会、SEC 与供应链一手资料对照，未向 A/B 泄漏标准答案。
- 手工 Evidence Pack：`0/3` 案例能由当前自然结果直接组成四槽完整 pack。

## 3. 关键纠正

当前最重要的纠正不是选 BM25 还是 BGE，而是评价对象错位：18-row qrels 测量单个已知相关候选的排序，完整 Evidence Pack 需要多个候选共同覆盖事实、机制、反证、关系方向和来源多样性。`18/18 target-in-pool` 与 `16/18 Recall@10` 都不能证明研报资料充分。

现有问题主要属于 S0/S1：源发现、chunk/object 形状、typed query、route 分工、关系归因、外源补源和 pack completeness。S2 本轮没有模型调用；S3 以后负责动态追问和研究综合，不得反向替代缺失 Evidence。

## 4. 处置

暂停正式 410-vector build，保留所有既有 specs 和失败现场。先冻结 C 参考研究揭示的 facet inventory，再定 S0 financial source/chunk blueprint 与 S1 multi-candidate Evidence Pack evaluator。随后才重建 sparse/dense/graph/exact lanes，并用 residual gaps 回到外源补源。

## 5. 证据

- `data/workbench_private/retrieval_autopsy/20260809_three_case/B_codex_supervised_same_tools.json`
- `data/workbench_private/retrieval_autopsy/20260809_three_case/AB_sparse_qrels_comparison.json`
- `data/workbench_private/retrieval_autopsy/20260809_three_case/D_external_capture_replay_assessment.json`
- `docs/research/fin_0_1_3_retrieval_autopsy/20260809_DELL_retrieval_autopsy.zh-CN.md`
- `docs/research/fin_0_1_3_retrieval_autopsy/20260809_MU_retrieval_autopsy.zh-CN.md`
- `docs/research/fin_0_1_3_retrieval_autopsy/20260809_NVDA_retrieval_autopsy.zh-CN.md`
- `docs/research/fin_0_1_3_retrieval_autopsy/20260809_cross_case_retrieval_root_cause_map.zh-CN.md`

## 6. 当前下一步

下一项应是 `FIN_0_1_3_S0_S1_FINANCIAL_SOURCE_CHUNK_QUERY_AND_EVIDENCE_PACK_REBASELINE_DECISION`，先审设计，不直接改代码。它必须保留外源作为本地 residual gap 补源，并把 S2 模型 query atoms、S3 动态 research 和 S4/S5 产品验收分别留在所属阶段。
