# 046 S1 当前对象／索引绑定与三案例类型化回放

日期：2026-08-18

状态：`current_runtime_successor_bound / three_case_candidate_replay_complete / product_readiness_producer_next`

## 本轮为什么不是直接做 EvidenceDecision

上一轮已经证明旧输入同时包含表格上下文污染、材料 coverage 假阴性和已知对象召回不足。若直接把这些状态写成产品 PackReadiness，系统会把自己的对象／合同／召回问题正式登记为“资料不够”。本轮先把三个最早责任层修到同一 current Runtime，再执行三案回放。

## 当前 Runtime 已切换的内容

- 来源库仍为 1,841 条不可变记录；新对象快照为 34,117 个金融对象：24,379 条 claim、8,532 条 metric row、1,206 条 bounded parent context。
- 新对象快照使用 source-local table context；旧对象编译器和历史结果保持不可变。
- Qwen3-Embedding-0.6B 对 34,117 个对象重新物化 1,024 维 FP16 cache；设备为 `cuda:0`，0 CPU vector fallback。
- Hybrid Runtime v1.4 同时继承金融排序、owner balance 与 typed-balanced lexical recall；修复了版本特性未累积继承导致新 policy 无法加载的问题。
- Runtime registry 升至 R22；对象、FP16 cache、policy、S2 fact mart、reviewed Evidence Pack 和 anchor catalog 由同一 binding receipt 约束。

## 三案例自然 current replay

三案均走相同 Workbench／S1／S2 current 路径，0 网络、0 生成模型、0 qrel／gold／hidden 读取、0 Evidence 晋升、0 public-gap 声明。

| 案例 | 请求 | 候选 | material requirement | 完整 requirement | NumericFact | S2 resolved／gap／conflict | 边界 |
|---|---:|---:|---:|---:|---:|---:|---|
| DELL | 8 | 128 | 12 | 12 | 58 | 19／9／0 | 原自然 scope 仍为 `explicit_scope_required`，本次只算 candidate-provenance audit |
| MU | 8 | 128 | 12 | 6 | 27 | 12／10／1 | 4 个请求 candidate material set complete |
| NVDA | 8 | 128 | 12 | 9 | 31 | 10／10／0 | 5 个请求 candidate material set complete |

## 业务结果

1. DELL 的订单／积压、订单转收入、利润、现金、营运资金和反方材料已经能稳定进入候选面；当前问题不再是“什么都搜不到”。
2. MU 的战略客户协议、特定采购量、customer deposit 和 take-or-pay 从旧的第 275—780 名进入当前 top 16，证明 typed-balanced 查询修复有效。
3. NVDA 最新 Data Center 收入本来就能进入 reported-results 候选；它不能替代订单／积压证据，故 demand direct 仍不应被误判为完成。
4. MU／NVDA 的若干 incomplete 来自上游请求把多个不同命题揉进同一 requirement：例如把 HBM4 交付、客户承诺和一般订单同时要求 direct＋counter。它属于 query／material decomposition，不是简单调大 top-k。
5. Evidence Role 仍漏识别 MU 的 binding commitments、take-or-pay 和 customer deposits 作为直接需求／耐久性信号；这些候选被找到，但没有进入正式材料 reservation。
6. 表格跨区域标题污染已消除，但个别 metric row 的局部行层级仍需在 EvidenceDecision 前 fail closed，例如 Operating income 行可能继承 Gross margin 的 row context。后续必须由产品 producer 明确归责，不能靠文本相关度掩盖。

## 失败证据与修复

- `fin_ia_0_1_3_s1c_typed_runtime_policy_load_attempt_failure_v1_0.json`：新 policy 最初因版本特性非累积继承而失败；已用统一 feature flag 继承修复。
- DELL R1：objective ID 绑定旧值，失败保留。
- DELL R2：通用 runner 把 `explicit_scope_required` 当成非法 replay；已区分“可审计 candidate-provenance”与“材料就绪”，不再错误阻断审计，也不因此授予 readiness。
- DELL R3、MU R1、NVDA R1 为新的 immutable replay；历史失败未覆盖、未改写。

## 当前判断

RC-S1-036 的 coverage cardinality、RC-S1-037 的主要跨表污染和 RC-S1-038 的 MU 已知对象召回均已进入 current successor 并完成回放。RC-S1-034 现在可以恢复实施，但必须复用既有 `candidate_decision` 与 `integrated_pack_readiness` 合同，不能新造平行轮子。

下一步产品 producer 应同时输出：

- candidate 的 `accepted／rejected／unjudged／needs_review`；
- 只复用当前 reviewed Pack Evidence，绝不把候选文字直接晋升；
- 逐命题 CoverageState 与 S2 NumericFact 独立状态；
- 逐 gap 的 source／parse／object／query／rank／EvidenceDecision／route exhaustion 最早责任；
- 只有完整 GapEligibilityReceipt 才允许公开信息 gap；
- Workbench 可逐对象追溯，但仍不宣称 S1 qualification。

## 权威与调用

- network／provider／generation-model／reranker calls：0；
- learned vector execution：CUDA FP16 only；
- candidate text promotion／Evidence creation／NumericFact creation／public-gap claim：0；
- 本轮不涉及 paid node，因此没有新增 TokenBudgetBasis；后续任何模型或付费检索仍必须逐节点签发。

## 未完成

- current product EvidenceDecision／GapEligibility／PackReadiness producer；
- Workbench canonical object drilldown；
- S1 独立 qualification、自然扫描源、qualified-human COST 处置和新 blind assets；
- S2 MU period identity；
- S3 动态研究与完整报告；
- S4／S5。

## 复证

- 定向 contract／runtime／registry：`25 passed`；
- 全仓：`743 passed`；
- `compileall`、S1 program foundation、active baseline、JSON／JSONL 与 `git diff --check` 通过；
- active baseline：168 Python／8 frontend／22 Runtime resources／0 forbidden reference；
- repository secret scan：7,234 files／0 findings。
