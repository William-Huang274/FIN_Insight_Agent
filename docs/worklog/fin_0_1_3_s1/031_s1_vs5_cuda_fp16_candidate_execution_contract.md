# S1 VS5 CUDA FP16 候选执行合同

日期：2026-08-18
状态：`candidate_execution_engineering_ready / valid_temporal_not_executed / S1_qualified=false`

## 为什么没有直接启动向量任务

在资格排序开始前，执行审计发现两项会让结果失真的合同问题：

1. 原 overlay 按“每命题最多 96 个候选”记录每个 reranker 最多 2,880 对，但继承的 VS3 策略要求每候选与该命题全部 RetrievalNeed 做笛卡尔积。30 个命题、每题 20 至 30 个 need 时，真实上限可能约为每模型 86,400 对，和已记录的 `TokenBudgetBasis` 不一致。
2. BGE／Qwen 编码器与 Cross-Encoder 虽然已经在 CUDA 上运行，但旧的 dense、learned-sparse 与 BGE multi-vector 相似度函数仍会在 NumPy／SciPy／FlagEmbedding helper 中回到 CPU。它不符合 Owner 要求的“向量计算直接走 CUDA”。

这两项均在任何 qualification ranking、hidden scoring 或标签读取前被发现，因此允许先修正执行合同；没有根据结果调阈值或路线。

## 实现处置

- 新建统一 qualification candidate runner。它只读 split-safe runtime input，不读取 evaluator reference；先物化 private raw Candidate output，后续评价由独立 evaluator 完成。
- 候选仍来自 typed exact／metric、BM25、BGE dense／learned sparse／multi-vector、Qwen dense 和 route-floor RRF；没有删除命题、facet、路线或候选。
- Reranker 只评分“实际召回该候选”的 RetrievalNeed，每候选最多 3 个；BGE 与 Qwen 使用同一有限 pair manifest，但分别选择自己的最佳 need。它避免单一预选 need 偏置，也避免无关 need 笛卡尔积。
- 完整资格集每个 reranker 最多 `30 × 96 × 3 = 8,640` 对；valid temporal 最多 `5 × 96 × 3 = 1,440` 对。该上限有任务目的、输入规模、交付、schema、质量风险、历史证据、profile 和停止语义，不以省钱或省时替代研究要求。
- BGE／Qwen 对象和查询编码强制 `cuda:0 + FP16`；Qwen loader 新增强制 `.half()`。
- dense 相似度、learned-sparse 点积与 multi-vector late interaction 全部显式在 CUDA FP16 上计算。PyTorch CUDA 不支持 FP16 sparse addmm，因此 learned-sparse 使用 CUDA FP16 gather＋`scatter_add_`，不退回 SciPy／CPU float32。
- BGE／Qwen Cross-Encoder 继续 `cuda + FP16`。GPU、模型 digest、对象 digest、shape、非有限分数或输出已存在时均 fail closed。
- CPU 只保留 BM25、SQL、tokenization、hard filter、账本、JSON 和确定性排序编排；这些不是 learned vector 计算。
- Git 执行门允许设计基线之后仅多出一笔 authority-only commit；若该提交同时改动 runner、策略、输入、对象或其他文件即拒绝。这样 authority 可以先进入干净提交，又不会产生提交哈希自引用。

## 边界

- Candidate 不是 Evidence；metric row 不是 NumericFact；Evidence Role 仍是独立输入，不可由 reranker 分数覆盖。
- runner 还没有执行 valid temporal，因此没有任何检索成绩、资格分数或新 Evidence。
- natural scanned official source 硬门已经失败，后续排序结果只能继续暴露责任层，不能通过平均值把 S1 合成为通过。
- test frozen／heterogeneous holdout 仍无执行权限；必须先完成 temporal、人工确认 evaluator reference，再分别签发 exact-once authority。

## 验证

- CUDA dense／learned-sparse／multi-vector 实际 GPU smoke；FlagEmbedding 的 CPU `colbert_score` helper 被测试禁止调用。
- BGE／Qwen Embedding 与 BGE／Qwen reranker 均有 CUDA fail-closed 测试。
- 有界 relevant-need pair、双 reranker 独立 best-need、无全量笛卡尔积测试通过。
- candidate execution policy 的所有输入与源码 digest 逐一验证，evaluator reference 不在 runtime binding 中。
- 当前定向集合：`22 passed`；更完整回归与 clean commit／push 仍在 valid temporal authority 前执行。

## 下一步

1. 完整回归、Git／secret／JSON 治理并 clean commit／push。
2. 基于该 clean commit 单独签发一次 valid temporal exact-once authority。
3. 只运行 5 个 temporal 命题的 label-blind CUDA candidate generation。
4. 先冻结 raw output，再由独立 evaluator 读取 reference 并做业务级错误解释；不得只汇报指标。
5. temporal 和 reference 人工确认通过后，才决定 test frozen；holdout 仍须再下一道独立权限。
