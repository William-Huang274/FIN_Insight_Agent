# S1 VS5 COST valid-temporal 候选评估

日期：2026-08-18
状态：`candidate_ranking_failed / test_and_holdout_not_authorized / S1_qualified=false`

## 这次评估做了什么

先在标签不可见状态下冻结 COST 5 个研究问题的 CUDA 候选结果，再由独立 evaluator 读取 valid-temporal reference。评估阶段只做确定性账本计算：0 网络、0 模型、0 learned vector、0 CPU vector fallback、0 Evidence／NumericFact 晋升。JPM／CAT frozen test 和 NVO／SHEL／Tencent heterogeneous holdout reference 均未读取。

候选生成仍是 RTX 4060 Laptop `cuda:0 + FP16`。本次失败不属于 GPU、模型连通性或 CPU 回退；它第一次把当前查询、召回、reranker、Evidence Role 与最终金融 shortlist 放在一套未观察 COST 业务问题上验收。

## 总体结果

| 指标 | 实际 | 门槛 | 结果 |
|---|---:|---:|---|
| 5 个命题至少一条已审材料进入前 20 | 0.80 | 1.00 | 失败 |
| 20 条已审关键对象进入前 20 | 0.60（12/20） | 0.90 | 失败 |
| 必需证据 facet 覆盖 | 0.642857 | 0.85 | 失败 |
| 必需 Evidence Role 覆盖 | 0.642857 | 1.00 | 失败 |

同一批 20 条 material positive 在各阶段前 20 的召回为：初始 union 0.50、BGE reranker 0.15、Qwen reranker 0.35、Role-guarded 0.30、最终金融 shortlist 0.60。最终规则比两个通用 reranker 都好，但仍不够；这不能被解释成“换一个更强 Embedding 就能解决”。

## 五个业务问题实际发生了什么

### 1. 会员费与续费：3/3，完整

会员费／续费直接披露、数值桥和会员忠诚度反方均进入前 20。当前链可以把会员费增长、续费质量和反方风险同时送到复核面。这里仍只是 Candidate，不是最终 Evidence 或利润归因。

### 2. 营运资金：4/4，完整

经营现金流、库存和应付账款相关对象均进入前 20。当前结构化表格／claim 与 cash-conversion lane 在这个问题上工作正常；精确数字仍须 S2 NumericFact 裁决。

### 3. 同店需求：0/4，最严重失败

系统前五名主要是收入确认说明、税务风险、股价预期风险和泛化会员风险；真正需要的四条官方经营材料全部掉到第 33–45 名：

- FY2025 同店销售、购物频次、客单价和新店贡献：第 45；
- 汽油价格与销量对同店销售表面的替代解释：第 33；
- FY2024 购物频次和客单价的机制定义：第 44；
- 同店销售口径定义：第 37。

业务影响不是“少了几条网页”，而是报告无法区分核心购物需求、客单价、新店贡献与汽油／汇率口径影响，容易把表面同店增速直接写成需求改善。

最早问题不在来源或对象：四条材料均已存在于对象库，也都进入 96 个 reranker pool。问题位于 proposition-specific query／rerank／最终融合。`conversion_and_durability` 仍带有通用的 shipments、customer readiness、cancellation 等词，和 Costco 的同店销售问题不一致；最终 lane fusion 又没有为该命题的直接经营披露和口径解释保留位置。

### 4. 毛利率压力：3/4，漏反方

毛利率经营桥、汽油业务组合和表格结果进入前 20，但“库存过量、缺货、交付延迟与损耗会降低经营表现”的官方反方只排第 58。结果可写出毛利率表面与汽油组合，却无法完整权衡损耗／库存反方，容易形成单向归因。

该对象已进入 reranker pool，因此最早责任层是金融 shortlist／fusion，而不是来源、parser、chunk 或公开信息 gap。

### 5. FY2024–FY2025 跨期比较：2/5

前排主要是 FY2025 毛利率、FY2024 会员费单年结果和现金流片段，没有形成同指标、同公司、两期配对：

- FY2024 会员经营基线没有进入 96 候选池；
- FY2025 同公司会员结果也没有进入 96 候选池；
- FY2025 经营现金流只排第 30；
- 只有 FY2024 现金流和一条表格桥进入前 20。

根因是“FY2024 FY2025 comparison”目前只是 query token；系统没有一个结构化的 temporal-pair lane 去要求同指标对象按两期成组出现。它因此更像分别搜几段经营文字，而不是构建可比较的时间序列证据组。

## 根因判断

1. **不是资料不存在。** 8 条漏召回材料全部已经在官方 10-K 对象库中；本轮不声明任何公开信息 gap。
2. **不是 parser／chunk 全面失败。** 20 条 reference 对象全部可以在对象库中解析和定位。
3. **不是 CUDA 或模型连通性。** 候选生成已完整在 CUDA FP16 上执行；评估不计算向量。
4. **也不能只怪 BGE/Qwen。** 两个通用 reranker 的确较弱，但最终规则已经从它们的 0.15／0.35 恢复到 0.60；剩余主要问题是 QueryFacetPlan 仍把公司特定问题塞进泛化旧 slot，以及 final shortlist 缺少命题级 materiality／period-pair 约束。
5. **当前 COST 参考仍待 Owner 或 qualified-human 确认。** 分数是 provisional，但 0/4 同店需求与 2/5 跨期比较的失败幅度足以阻止隐藏集执行。

## 不能做的事

- 不能启动 JPM／CAT frozen test 或 heterogeneous holdout；
- 不能调一个分数阈值后把同一结果追认为通过；
- 不能把 8 条已存在但未召回的材料写成免费公开信息不足；
- 不能用会员和营运资金两项成功平均补偿同店需求 0/4；
- 不能因为向量必须走 CUDA，就把错误归结为 GPU 或继续盲目扩大向量预算。

## 建议的下一决策

当前 qualification lane 已失败，最安全的结构性路线是：

1. 先由 Owner／qualified-human 复核 COST 20 条 reference 是否构成合理 material positive；
2. 将本次 COST 结果永久保留为失败证据，并把 COST 从“未观察 temporal”转成已观察开发回归案例；
3. 在 DELL／MU／NVDA、COST 和 synthetic mutation 上做 provider-neutral 修复：命题级 facet 编译、无关通用 query seed 抑制、必需 facet／role 的 bounded shortlist floor、结构化同指标跨期 pair；
4. 不根据本轮分数调 BGE／Qwen 权重或阈值；先证明上述结构在多个已观察行业上成立；
5. 另行预注册一个新的、未观察 temporal case。只有新 temporal 通过后，才决定是否打开一次性 frozen test。

这会增加一个新的 temporal 案例，但不会创建新产品版本或重做 VS1–VS4；它是当前 VS5 失败后的同阶段资格修复。因为这会改变资格样本归属，需作为 Owner 决策点，不能由实现者静默改写。

## 可审计结果

- public result：`configs/retrieval/fin_ia_0_1_3_s1_vs5_valid_temporal_evaluation_result_v1_0.json`
- private raw：`data/workbench_private/fin_0_1_3_s1_vs5_qualification_evaluations/valid-temporal-eval-r1/raw.json`
- raw SHA-256：`a71a568262b53271bedada8025416b0c23db0b4ce8f337f9d89750b978c56b9e`
- raw result digest：`b042b5ce325e34829c147a229dd17cfc7bf67fcacf48819610a66305903968ad`
- public SHA-256：`f3b04e96ce4aaccae4f0c00debe2e3238e2cc3ba8743189607bff8e04f7e9966`

治理复证：评估器进入权限基线前全仓 `621 passed`、compileall、active baseline 通过，secret scan `7,109 / 0`；结果物化后 evaluator＋Project OS 定向 `35 passed`、active baseline 通过，secret scan `7,112 / 0`。评估结果没有改动 current Runtime Registry、Evidence Pack、Workbench 或任何历史 attempt。

## 2026-08-18 后续治理更正

上文“另行预注册一个新的、未观察 temporal case”不再是执行 COST successor 前的强制条件。机器预注册合同已在观察结果前冻结 `valid_temporal_max_executions=2`，Owner 随后授权在当前 S1／VS5 内完成结构修复并执行剩余一次 valid run。

正确边界为：R1 失败永久不可变；不得调门槛、写入对象 ID／答案 URL或打开 hidden split；第二次 COST 只用于验证跨案例通用结构修复，不能单独证明泛化或 S1 资格。若 R2 再失败，则不得进入 COST R3，届时才转为架构处置或新 temporal case 决策。具体 successor 设计与回放证据见 `033_s1_vs5_materiality_temporal_successor.md`。
