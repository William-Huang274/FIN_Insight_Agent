# S1 VS5 COST valid-temporal R2 评价失败与停止线

日期：2026-08-18

状态：`R2_metric_fail / no_R3 / hidden_splits_blocked / reference_adjudication_and_architecture_disposition_required / S1_qualified=false`

## 1. 执行身份

- Candidate attempt：`FIN-0.1.3-S1-VS5-VALID-TEMPORAL-CANDIDATE-R2`
- Evaluation attempt：`FIN-0.1.3-S1-VS5-VALID-TEMPORAL-EVALUATION-R2`
- candidate public freeze：`7862c393`
- evaluator design：`11599a6b`
- evaluator authority：`8f6b9baa`
- evaluator network／generation model／learned vector／CPU vector fallback：全部 0
- deterministic in-memory replay：通过
- private evaluation raw：64,521 bytes，SHA-256 `43817342fb09a6ec266db67a23497a4a9aaba23aad672b497fffbde54c57ad52`

## 2. 结果

| 指标 | R1 | R2 | 门槛 | 结论 |
|---|---:|---:|---:|---|
| 五命题至少一条材料 | 0.80 | 1.00 | 1.00 | 通过 |
| 20 条已审对象全部覆盖 | 0.60（12/20） | 0.75（15/20） | 0.90 | 失败 |
| material facet coverage | 0.642857 | 1.00 | 0.85 | 通过 |
| required role coverage | 0.642857 | 1.00 | 1.00 | 通过 |

阶段性 object recall 为：candidate-union top20 `0.50`、BGE top20 `0.15`、Qwen top20 `0.40`、role-guarded top20 `0.40`、最终 review top20 `0.75`。这说明 v2 的命题保持与 facet-balanced review 确实把更多有用材料送入最终审阅面，但 learned ranking 和 temporal candidate-set 仍不稳定。

## 3. 五个命题的业务表现

1. **会员价值获取：3/3。** 会员费、续费和反方材料都进入前 20。
2. **营运资金：4/4。** 经营现金流、库存／应付桥接材料完整进入前 20。
3. **同店需求：3/4。** 已能看到直接需求、数值桥和替代解释，但“汽油价格与销量可能扭曲表面同店销售”的对象排在第 21；报告仍可能低估汽油口径影响。
4. **毛利压力：3/4。** 商品／工资／损耗／汽油正反方向已覆盖，但 FY2025/2024/2023 毛利金额表格排在第 21；机制叙事有了，精确同口径背景仍不够稳。
5. **跨期变化：2/5。** FY2024／FY2025 经营现金流 claim 进入前 20；同表 2025/2024/2023 现金流 metric row 排在第 21。另两条会员经营 claim 完全没进 reranker pool。

## 4. 这五条 miss 不能都算成同一种检索失败

### 4.1 两条会员 claim 暴露的是参考—请求不一致

`COST_TEMPORAL_CHANGE` 的正式 EvidenceRequest 只点名 revenue、gross margin 和 operating cash flow；两条漏失对象却是会员费／续费率。Runtime 没有被授权把 membership 当成该请求的第四个 metric，因此它们没进入 pool 不能直接记作“本来应该搜到但检索器没搜到”。

这属于 qualification asset 的 provisional reference consistency 问题。不能因为 R2 失败就删除标签，也不能为了标签把 membership 偷塞进 query。必须由 qualified human 判断：

- 是 EvidenceRequest 少写了 membership，需在未来新案例中提前冻结；还是
- 这两条对象本就不属于该问题，应从未来 reference 中移除。

无论哪一种，都不能改写已完成的 R1／R2 分数。

### 4.2 三条第 21 名暴露的是“对象排序”与“研究材料组选择”仍混在一起

汽油替代解释、毛利表格、跨期现金流表格都已进入候选或 reranker pool，却恰好落在有限 review window 外。当前系统按单个对象竞争前 20；它会保留多条相近的经营 claim，却不保证“直接事实＋反方／替代解释＋同口径表格”这个研究材料组一起进入审阅面。

下一步不能把 `review_k=20` 随手改成 21，也不能继续为 COST 调权重。正确的架构处置是把候选审阅从单对象多样性提升为 request-bound evidence-set coverage：先确保每个 material sub-question 的 direct／counter／bridge／temporal-pair 组有位置，再在组内排序；exact object recall 保留为诊断，但不能用任意等价对象缺失否定已经完整的业务 facet。

## 5. 停止线与下一步

预注册允许的两次 valid-temporal candidate execution 已全部消耗。当前明确：

- 不签发 COST R3；
- 不打开 JPM／CAT frozen test 或 NVO／SHEL／腾讯 holdout；
- 不把 15/20、facet=1.0 或 role=1.0 写成 S1 通过；
- 不修改 R1／R2 reference、阈值或历史结果追认成功。

下一步只做零调用处置：qualified-human reference consistency review；冻结 request-bound evidence-set／temporal-pair 评测合同；在开发／回归案例上证明组级选择不会隐藏错公司、错期、错单位或风险冒充事实；然后预注册新的 unseen temporal valid case。只有新 valid 通过后，才重新决定是否打开现有 hidden splits。
