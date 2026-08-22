# DELL residual external ladder R3 计划与零调用门

日期：2026-08-23
阶段：FIN 0.1.3 / S1
状态：clean-bound live 已执行；CandidateDecision 前置的 capture replay 修复待完成

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

## R3 clean-bound live 结果

- attempt：`dell-external-residual-r3`，绑定 clean／synced commit `483f60d490649723262c3a24a124cea1c10316bb`；
- 28 条 predecessor locator 按 digest 重放，22 条 Tencent WSA Standard locator 查询真实执行；50/50 query success，355 个 locator，0 retry，0 模型；
- 60 条公平 shortlist 覆盖 17 个域、4 个来源层；原文 capture 49 条，但只编译为 15 个 source object、15 条 candidate proposal；
- proposal 分布：客户需求 5、PVM 5、销量 2、价值池 2、价格 1、供应链 0、反方 0；多数为 predecessor capture 的可重复材料，本轮 fresh query 只新增两条 TrendForce 行业销量上下文；
- 当前结果 digest `9aeb7a80e32b51ff4e51d13daf4ad85226a125477adb5704d2be8e601e8fb9ce`，public result 为 `configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_result_v1_2.json`，private terminal SHA-256 为 `09c07053f5d925885df442da67b4755c25d8561cfec6dd834fe2ab0333cc70fc`。

## 真实业务故障归属

1. **资料抓到了但正文未进入对象库。** NVIDIA Investor FY2027 Q1、FY2026 Q2／Q3 三页原文各有约 25k–28k 可见文本，包含 Blackwell 销售、售罄、H20 shipment boundary 和 Dell 平台关系等内容，却因页面正文主要位于 `div` 而不是当前 parser 只读的 `p/li/tr` 标签，被误拒为 `public_context_article_body_too_thin`。
2. **正文发布日期与页尾推荐文章日期混淆。** NVIDIA Newsroom 三篇明确点名 Dell 的官方材料分别可见 2023-08-22、2022-08-30、2020-06-22，但通用 date marker 同时抓入 2026 年页尾推荐文章日期，触发 `conflicting_original_publication_dates`。这使“供应商点名 Dell／产品交付或可用性”关系材料无法进入候选。
3. **部分可信上下文同样被日期层挡住。** CRN 的 Dell 供应连续性材料已经 capture，但 publication date 未恢复；TrendForce Blackwell 页面已形成 source object，却被旧候选筛选规则挡在 proposal 外。
4. **仍然没有被工具找到的真实残余。** Dell IR 的三条销量路线 read timeout，IDC 三条路线为 403；CDW／Insight／SAM.gov 没有形成 Dell AI 服务器可观察成交价或可复算报价。价格、Dell 台数／份额仍未 ready，不能用 parser 修复伪关闭。

因此最早责任层是 `capture → publication-date adjudication → source-object parse → candidate screening`，不是 Provider、DeepSeek 或公开信息边界。R3 原始结果保持不可变；下一步只允许使用已保存 capture 做零网络 replay，修复通用正文／日期裁决并重新编译 Candidate，再进入人工 CandidateDecision／Evidence Gate。
