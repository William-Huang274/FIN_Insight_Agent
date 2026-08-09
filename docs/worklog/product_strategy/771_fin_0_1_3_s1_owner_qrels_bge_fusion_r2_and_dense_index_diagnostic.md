# 771 — FIN 0.1.3 S1 Owner qrels、BGE/fusion R2 与 dense index 诊断

日期：2026-08-09

## 结论先行

Owner 已接受 18/18 research qrels，内源 ranking 获得了真实评测入口。有效的 R2 表明当前最好方案仍是 sparse RRF：其 Recall@10=`16/18`、MRR@10=`0.51111111`；BGE dense 只有 `3/18`、MRR=`0.16666667`；fusion 为 `14/18`、MRR=`0.28201058`，低于 sparse，故不准入。

这不是“BGE 一定不适合金融检索”的结论。只读诊断确认 10 个唯一目标中只有 5 个进入现有 Milvus；18 行里 8 行属于 current supplemental 文档尚未入向量索引。其余已在索引中的目标又有 1 行只到 rank 16、6 行未进 top 24，所以同时存在索引新鲜度和语义检索质量两个问题。

## 本轮完成

1. Owner 对 qrels v1.3 的 18 行逐项接受，0 行改写；研究候选仍是 candidate-only，不被晋升为 Evidence。
2. 修正 Milvus 查询的财年口径：reporting fiscal year 不再被 filing calendar year 替代。
3. 建立 sparse／dense／fusion 同池合同，冻结 query、filter、预算、权重和 qrels load-after-generation 边界。
4. R1 真实执行后发现 namespaced evidence ID 被首个 `::` 截断；R1 保持不可变，但禁止用于模型质量或采用判断。
5. 只修复 final-known-vector-kind suffix 规则后执行唯一 R2；identity collision regression=`0`。
6. 使用 10 次只读 Milvus metadata query 将 dense 缺口拆成 index freshness 与 semantic retrieval 两类；没有重新 embedding、vector search、rerank 或 Evidence promotion。

## 为什么不能现在调 fusion 或加 reranker

当目标文档没有进入 dense index 时，任何 fusion 权重和 reranker 都无法把它从不存在的候选中救回来。现在直接调参还会把只有 18 行的 Owner qrels 变成训练集，形成评测泄漏。正确顺序是先补齐 current capture-backed dense assets，使 10/10 唯一目标都物理可见；再按完全相同矩阵做一次有界对照。若仍下降，保留 sparse，并把 query formulation 或 reranker 作为独立实验。

## 下一执行边界

1. 建立新的 immutable supplemental dense collection，只处理已 capture 的 DELL/MU/TSM/MU 10-Q current 文档；不覆盖历史 662,908-vector collection。
2. 保留 evidence ID、vector-kind、ticker、期间、form、URL/capture lineage，并以 federation 而非跨库 raw-score 拼接消费。
3. 先做 metadata gate：10/10 unique selected targets in index。未达门槛不执行新 ranking。
4. 门槛通过后只做一次同矩阵 sparse／dense／fusion successor；不调 Gold 权重。
5. reranker 本机缺失，不静默下载，也不作为当前 dense refresh 的必要门槛。
6. current-quarter SQL `0/6`、external `4/12`、Evidence→Claim→Workpaper→report 利用均保持独立待办。

## 反思

这轮最重要的工程纠偏不是“再换一个 embedding 模型”，而是把 candidate presence、index freshness、semantic ranking 和 downstream usefulness 分账。过去把这些问题压成一个 retrieval 分数，很容易让我们在缺语料时调模型、在缺候选时调 reranker。后续每一层都必须先证明输入存在，再评价排序能力，最后才评价金融研究内容是否真正利用了证据。
