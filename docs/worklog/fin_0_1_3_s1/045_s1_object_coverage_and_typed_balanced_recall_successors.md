# S1 对象、覆盖语义与类型化均衡召回 successor

日期：2026-08-18  
状态：`engineering_pass / current_runtime_not_switched / CUDA_rebuild_and_three_case_replay_pending / S1_qualified=false`

## 业务复核纠正

三案首次回放把 MU 与 NVDA 都描述为“已知高价值对象未进入 candidate union”。进一步读取私有候选与实际 BM25 排名后，必须拆开：

- MU 的 take-or-pay、绑定采购量和多年期战略客户协议确实被旧大词袋挤到第 275—780 名，未进入 top 64；这是 QueryFacetPlan／第一阶段召回问题。
- NVDA 最新 `Data Center revenue was $75.2 billion` 在 reported-results 的旧 BM25 已排第 16，实际进入 bounded union。它被标成 requirement incomplete，是旧 coverage 合同要求一段叙事同时满足多项数字指标和产品轴造成的假阴性，不是召回失败。

因此 RC-S1-038 必须缩为“MU 等已知披露的类型化查询表面缺失”；NVDA 归入 RC-S1-036 coverage semantics。旧回放和 v1.0 评估保留为历史证据，不改写；本记录提供 successor 更正。

## 三项通用结构修复

### 1. 表格对象不再继承整段旧标题

冻结的 `object_view_compiler.py` 已逐字恢复，避免破坏现有资格资产摘要。新 `object_view_compiler_v2.py` 先复用 v1 的 claim／table 解析，再在去重前用当前表格前的局部原文重建 table title、local context、model text 和 metric-row identity。真实形状回归证明 NVIDIA 债务到期行不再携带 `Gross Profit and Gross Margin`。

### 2. 材料覆盖不再让 S1 叙事重复承担 S2 数字职责

EvidenceSetCoverage v1.2 增加明确的 metric／product `all_of`、`any_of` 与 `retrieval_context_only`：

- 非时间型叙事 requirement 的 metric 默认只提供检索上下文，精确数值继续由 S2 NumericFact 负责；
- product 轴默认逐项 `all_of`，不能用一个泛化词假装多个产品议题已覆盖；
- 预留容量按真实 required axes 计算；部分覆盖显式列出 missing axes；不可满足的合同在运行前失败，而不是跑完后误报资料缺失。

### 3. 一个研究请求拥有多个有界召回入口

`query_plan_v3.py` 保留 v1 的公司身份、期间、来源、关系和 facet 硬边界，只把请求拆成：原始请求、规范化 metric aliases、每个 product concept 的财报披露表面。`balanced_lexical_recall.py` 在同一 hard-filtered corpus 内分别执行 BM25，候选融合后才截断；没有对象 ID、答案 URL、ticker 分支、qrel／gold 或 Evidence 权威。

provider-neutral ontology v1.3 增加 `strategic customer agreements`、`take-or-pay agreements`、`binding commitments for specific volumes`、`customer deposits` 等通用披露语言。用当前 MU 官方对象做零向量诊断，三条原本第 275—780 名的材料在新 64 候选中分别为第 4、8、11 名。

## 版本与回放边界

- 历史 v1 QueryFacetPlan、v1 object compiler、COST R1／R2、DELL／MU／NVDA R1 结果全部保持不可变。
- 新行为通过 v2／v3 successor 暴露；旧 Hybrid policy 默认仍执行单一 broad BM25，只有新 typed-balanced policy 才启用多查询召回。
- 本轮 0 网络、0 生成模型、0 learned-vector 计算、0 qrel／gold／hidden／holdout 读取；Candidate 仍不是 Evidence，ontology match 仍无 NumericFact 权威。

## 验证与下一步

定向对象、coverage、Hybrid、Project OS 回归通过；全仓 `739 passed`，compileall 通过。下一步只做一次统一 successor 构建：

1. 用 object compiler v2 从当前 1,841 条来源生成新对象快照；
2. 只在 CUDA／FP16 上为该快照重建 Qwen dense cache，禁止 CPU fallback；
3. 生成并内容寻址绑定 typed-balanced Hybrid policy、ontology 和 runtime receipt；
4. 用相同 DELL／MU／NVDA 请求执行 successor replay，核对真实业务材料、污染、coverage 与 lineage；
5. 通过后才实现产品级 EvidenceDecision、GapEligibilityReceipt 与 PackReadiness producer。

这仍不是 S1 通过、完整动态 S3、人工内容验收、发布或 release。
