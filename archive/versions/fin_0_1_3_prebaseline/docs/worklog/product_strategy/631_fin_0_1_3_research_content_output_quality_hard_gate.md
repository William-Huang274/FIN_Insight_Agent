# 631 FIN 0.1.3 研究内容输出质量硬门禁

日期：2026-08-06
状态：`accepted_requirement / documented / runtime_translation_pending`

## 用户要求

用户明确要求 FIN 0.1.3 务必把研究内容输出质量加入考核标准，避免再次出现工程链、Artifact 和页面通过，但研究底稿/报告没有实质内容的情况。

## 决策

研究内容质量由此前可能后传的 L3 finding 升级为 FIN 0.1.3 release-blocking gate。它与 L1 financial truth、L2 evidence authority 和 L4 product delivery 分开：任一层失败都不能被其他层分数补偿。

新增八维 Rubric：

1. 公司与问题专属性；
2. 证据到结论的论证；
3. 财务与 Numeric 解释；
4. 因果机制与行业逻辑；
5. 跨 Cell 综合与冲突裁决；
6. 反方、风险与 gap 纪律；
7. WWC 与行动价值；
8. 写作与 senior 决策可用性。

每案总分必须 `>=24/32`，Q1–Q7 无低于 2，Q1/Q2/Q3/Q8 各 `>=3`；三正式案例逐案通过，不使用平均分。Agent 还需相对 same-input deterministic baseline 在至少三个内容维度产生 reviewer-confirmed material gain。qualified reviewer 的 content acceptance 与身份/workflow acceptance 分开记录。

## 更新

- 新增 `docs/eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md`。
- 更新 FIN 0.1.3 delta plan、扩展测试计划、FIN 0.1 F08/F15 release acceptance、Project OS 和 ledgers。

## 当前边界

本轮只冻结产品/评测要求，没有实现 runtime schema、Verifier、score packet、Workbench surface，没有运行模型、source、case 或 full-chain。当前能力状态只能是 `documented_accepted / contract_translation_pending`。
