# S1 三案例候选回放与最早责任层重定

时间：2026-08-18

## 这轮真正做了什么

在 DELL 已完成回放之后，MU 与 NVDA 使用同一条当前产品入口、同一份对象库和 BM25＋Qwen CUDA/FP16 候选链各跑了一次。两案都没有调用生成模型、没有联网，也没有读取 qrel、gold 或 hidden label。完整候选只保存在受限 capture 中，公开结果只保留阶段数量、容量和根因摘要。

三案合计 24 条 EvidenceRequest 全部能进入当前检索链，但只有 5 条形成当前合同认定的完整材料组。24 条请求全部打满 BM25 64、Qwen 64 和 union 96；因此不能把 19 条不完整请求解释为“公开资料没有”。

## 业务上看到了什么

### DELL

现有材料能够支持 AI 服务器需求、积压订单、ISG 业绩、利润、现金和营运资金风险的基本研究。但精确订单数、客户数，以及 AI 服务器对增量利润、现金转换和应收／存货的独立贡献仍无直接桥接证据。

### MU

当前候选能够看到 HBM 出货、产能、先进封装、供给安排及公司自己承认的不确定性。更关键的是，对象库里已经存在“take-or-pay、绑定采购量、多年期战略客户协议”的官方表述，但它没有进入订单／转化问题的 96 条候选池。这不是 Micron 没披露，而是系统没有把“客户承诺和采购结构”正确翻译到“take-or-pay／strategic customer agreement”。

S2 还发现一个独立问题：两个不同起止日期的离散季度都被标成 FY2025 Q3。系统拒绝任选一个数字是正确行为，但期间身份需要由 S2 修复。

### NVDA

当前材料能看到 Blackwell 出货、需求、长期产能承诺、数据中心和能源约束，以及很丰富的出口管制反方材料。但最新 Data Center 收入对象已经在对象库里，仍未进入 reported-results 的 96 条候选池；这是时点／召回问题。

更严重的是，部分债务到期和利息收入行被冠以 `Gross Profit and Gross Margin` 表题。它们因此可能在进入 reranker 之前就伪装成毛利材料。这是对象编译污染，不能靠换 Embedding 或扩大 top-K 解决。

## 为什么不能直接进入 Pack Readiness

本轮还证明当前材料覆盖合同存在数学和业务语义不一致：

- 一个 group 可能要求同时覆盖四个指标和多个产品，却只预留两条候选容量；
- 指标和产品默认按全 AND 处理，即使其中实际是可替代主题；
- S2 已经独立提供权威 NumericFact，S1 仍要求叙事候选重复完成全部数值轴；
- 一个候选覆盖了关键反方，但没有在同一句里覆盖另一个产品词时，整个 group 会被标为失败。

因此当前大量 `material incomplete` 是混合状态：真实缺材料、召回丢失、对象污染和合同假阴性同时存在。现在注册产品级 EvidenceDecision／GapEligibility／PackReadiness 只会把这些误判固化成正式输出。

## 调整后的顺序

1. 先修表格行与局部表题、表头、lineage 的绑定；无法证明局部上下文的行降级或 fail closed。
2. 再把 material requirement 改成明确的 atomic／any-of／all-of 语义，并让 S2 数值权威与 S1 叙事材料分离；编译时验证合同在预留容量内可满足。
3. 在不硬编码对象 ID 的前提下，让 MU take-or-pay 与 NVDA 最新 Data Center 结果进入对应候选池。
4. 仅因对象编译变化而重建受影响对象及 CUDA/FP16 索引，以新 attempt 重跑三案。
5. 新三案结果可信后，才注册产品 EvidenceDecision、GapEligibilityReceipt 和 PackReadiness producer。

## 当前边界

本轮不是 S1 通过。它关闭的是三案例统一 candidate-ceiling 回放的执行问题，并找到了三个更早的 S1 责任层和一个 S2 期间责任层。0 模型／0 付费调用，因此本轮不产生 TokenBudgetBasis；未来任何模型或付费节点仍须按项目政策单独签发依据。
