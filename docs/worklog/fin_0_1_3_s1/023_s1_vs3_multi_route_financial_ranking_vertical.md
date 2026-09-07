# FIN 0.1.3 S1 VS3 多路线检索与金融排序纵切

日期：2026-08-18  
状态：`VS3_vertical_slice_integrated / VS4_authorized / S1_qualification_false`

## 1. 本轮真正解决了什么

VS3 不是再选一个“最强向量模型”，而是把同一份金融对象库贯穿为一条可审计产品路径：

`EvidenceRequest → RetrievalNeed → 多路线有限候选池 → CUDA Embedding/Reranker → 金融 intent/Evidence Role → CandidateDecision → Coverage/Pack readiness → Workbench`

所有路线消费同一 33,085 对象快照。BM25、BGE-M3 dense／learned-sparse／multi-vector、Qwen Embedding、BGE/Qwen Reranker 和 typed route 只提供候选或分数；identity、period、source、relationship、金融角色和权限边界仍由 provider-neutral 合同裁决。

## 2. CUDA 执行边界

- `src/retrieval/embedding_runtime.py` 与 `src/retrieval/cross_encoder.py` 均显式要求 `cuda`；无 CUDA 时 fail closed，禁止静默回退 CPU。
- 实际运行由 `nvidia-smi` 确认 Python 进程占用 GPU。CPU 只负责 tokenizer、I/O、JSON、确定性排序和账本物化。
- `tests/test_cross_encoder_cuda.py` 覆盖 CUDA 不可用拒绝与 CUDA 可用加载行为。

## 3. 不可变失败与根因

1. **candidate v1.6：14/15。** DELL reported-results 正例已在 typed-intent route 排第 3，却被多路线 RRF 的 128 条总池挤出。根因是有限池调度，不是 Embedding 没找到。
2. **candidate v1.7：业务召回修复、稳定门失败。** 通用 per-need route floor 使 15/15 入池，但稳定性探针错误地比较 stratified forward 与旧 unstratified reverse，得到 0.722222。该失败属于 evaluator 口径，不是排序不稳定。
3. **candidate v1.8：最终 successor。** 同一 stratified compiler 做正反顺序比较，15/15 入池、14/15 union top10、MRR 0.859477、head stability 1.0。v1.6/v1.7 结果保留，不原地改写。

route floor 只按 RetrievalNeed 类型保护少量头部候选，不包含公司、对象 ID、gold URL 或答案标签；因此不是 DELL 特判。

## 4. 金融精排和 Evidence Role 结果

- 最终 financial shortlist：15/15 known positive 进入前十，MRR 0.933333，0 confirmed hard negative，216 条 review projection；完整 1,912 CandidateDecision universe 未丢弃。
- 复合 Evidence Role／financial-intent replay：
  - 全关系：positive compatible 50/62 = 0.806452；hard negative suppressed/abstained 68/68 = 1.0。
  - 当前候选池：48/56 与 46/46。
- 正例未达到 100% 不被掩盖：剩余对象多为过度残缺、proxy-only 或角色不直接；它们可以留在候选／复核面，但不能靠语义相似自动晋升。

## 5. VS1／VS2 同运行时回归

- VS1 两个历史 reviewed successor 均在候选池：旧 10-Q 对象位于当前金融短名单第 6；旧 transcript 对象位于第 15。前方是更新、更直接的 Dell 10-K／10-Q／官方 transcript。当前处置是保留旧 lineage 并把新对象列为 review，而不是调权重把旧答案强拉到第一。
- VS2 四个复杂文档目标全部进入最终审阅面：1 个直接进入金融 shortlist，3 个通过受限 parent/context expansion 接入。表格行仍无 NumericFact 权威。

## 6. CandidateDecision 与 gap 边界

最终 product gate 共物化 1,912 个对象级决定：

- accepted：10
- rejected：66
- unjudged：9
- needs-review：1,827

所有候选都有状态；hard-negative false accept=0，source-only false accept=0。`needs-review` 不等于 Evidence、拒绝或 public-information gap。三个预登记 gap 仍缺官方／外源补证资格证明，只允许在 VS4 继续收敛。

## 7. 当前产品消费者

- Runtime Registry 从 R16 升为 R17，新增 `application.result.current_s1_vs3_retrieval_vertical`。
- Operations 新增只读 API `/api/operations/s1/retrieval-quality` 和“检索与金融排序纵切”面板。
- 页面显示候选覆盖、金融前十、hard-negative、VS1／VS2 回归和 `Candidate != Evidence / NumericFact 未授权 / S1 未通过`，不显示 gold target 或答案 URL。

## 8. 验证

- 聚焦 Python 回归：55 passed。
- TypeScript typecheck：pass。
- Vite production build：pass。
- Playwright：desktop/mobile 两个 Operations 用例通过；无横向溢出，面板与权限边界可见。
- 第一次 Playwright 使用 4173 端口因本机 `EACCES` 未启动，改用 4317 后通过；未修改业务逻辑。

## 9. 权限与下一步

VS3 只获得 `vertical_slice_integrated`，不授予：

- 单个 Embedding／Reranker 产品 winner；
- 自动 Evidence／NumericFact promotion；
- fine-tuning；
- hidden qualification；
- `S1_qualified_stable` 或完整产品链资格。

下一项进入 VS4：用 DELL 营运资金、发行人反方和上游反方，从当前 Coverage／CandidateDecision 账本发起有界第二轮补证；必须先区分本地对象／解析／召回／排序故障、未执行路线、预算不足和真正免费公开信息边界，再允许形成 typed stop 或 gap。

