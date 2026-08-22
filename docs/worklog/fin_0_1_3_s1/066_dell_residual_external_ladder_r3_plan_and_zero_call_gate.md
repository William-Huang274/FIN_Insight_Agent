# DELL residual external ladder R3 计划与零调用门

日期：2026-08-23
阶段：FIN 0.1.3 / S1
状态：零网络计划编译通过；clean-bound live 待执行

## 为什么需要 R3

formal integrated readiness 已把剩余问题限定为四类可观察信息：Dell AI 服务器价格、Dell 台数／份额代理、GPU 供给释放时点、Dell—供应商双边关系。R2 虽然增加了 14 条 Evidence，但多数是产品配置、行业量或供应链背景，没有直接观察上述四个轴。

## 计划范围

- 新查询 22 条：价格／采购 6，销量／份额 6，GPU 释放 5，双边供应关系 5。
- 来源阶梯包括 Dell／NVIDIA 官方披露、IDC／Omdia／TrendForce／Canalys／Gartner、SAM.gov／UK 招标、CDW／Insight 渠道，以及 Reuters／CRN／EE Times 上下文。
- R1 的 28 个 provider 结果只按 digest 重放，不付费重查；R2 的 43-Evidence Pack 保持不可变，不被 R3 隐式重编。
- 最多 22 次 provider locator 调用、60 个 capture-first 原始页，每查询最多 3 页、每域最多 8 页，0 retry，0 模型。这些上限根据四个残余轴的来源阶梯和 R2 中的根页／付费摘要／域预算挤占失败设定，不是为省费用压缩研究。

## 零调用结果

- successor spec：`configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_residual_successor_spec_v1_1.json`；
- spec digest：`b941e5c843bdc9daf4ab79634b44957cec0387fb9e6023a3c645de37b043ebe0`；
- compiled plan digest：`4f9b44ece344fba7de047dd5bcae47f6d9c7f8309e57ffa11a725dd32eb16ad1`；
- 编译后 50 个 query unit：28 replay＋22 provider，40 个受审来源域；
- 定向测试 `17 passed`，0 网络／0 Provider／0 模型／0 promotion。

## 权限与停止条件

Search Provider 只提供 locator。任何页面必须先保存原始响应，再验证公司、日期、披露方、关系方向和主张用途。R3 不允许 Candidate 自动成为 Evidence，不允许宣称公开信息 gap，不允许晋升 current Pack 或运行动态 Agent。付费墙、robots、解析失败或搜索未命中必须分开记录，不得合并为“信息不存在”。
