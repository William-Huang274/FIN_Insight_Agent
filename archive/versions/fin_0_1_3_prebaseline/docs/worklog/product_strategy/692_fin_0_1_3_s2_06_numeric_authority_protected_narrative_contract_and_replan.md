# FIN 0.1.3 S2-06 数值权威、受保护叙事合同与阶段重排

日期：2026-08-07

状态：`S2-06A_documentation_and_scope_alignment_complete_runtime_not_changed`

## 1. 用户问题

用户要求确认“模型仍然看见并使用数字完成研究、本地只守住事实写入而不代写研报”是否此前在文档和日志中写清楚；若没有，补入项目文档并重新梳理后续规划。

## 2. 审计结论

不是完全没有写，而是写得不够统一、不可执行：

- 文档 32 和早期 exact-value ledger 已要求 exact 数字、单位、期间、公司和引用不得被模型自由改写；
- worklog 430、442、443、497–499 已提出 judgment atom、numeric alias、本地 projection/renderer 和 compiled contract；
- TECH_04/05/09 已分别拥有数值、判断和 artifact；PRD 已写 Writer no-source 与 Evidence Gate；
- 但没有一处 canonical 文档同时区分模型的事实可见、分析、引用、自由写作和最终渲染五种权限；
- 没有明确写出模型仍必须看见 exact value 并负责经济机制、反方、thesis 和自然叙事；
- 没有把 protected narrative、逐 correction closure、最小 patch 和 anti-template paired quality 写成统一验收；
- 当前 S2-06 corrected-node Runtime 也没有消费这些分散规则，DELL R2 的 U3/U4 已证明 correction semantics 丢失和整节点重写会重开 L1。

因此该问题分类为 `method_to_runtime_gap`：历史理念部分存在，current canonical contract 和 runtime consumption 不完整。不能说“此前完全没考虑”，也不能说“已经写清楚、只是模型不遵循”。

## 3. 本轮补充

1. PRD 新增 7.9：模型研究判断权与金融事实写入权分离。
2. 新增跨域合同 38：五权边界、三类输出面、`NumericFactView`、`ProtectedNarrativeDraft`、`CorrectionObjective`、`CorrectionClosureReceipt`、analyst threshold 分轨和 anti-template 验收。
3. TECH_00 stable object graph 与 owner matrix 登记新对象；不创建 TECH_12，继续由 TECH_04/05/06/08/09/10 分工。
4. TECH_00A 增加 Hybrid Research Authoring / Protected Narrative 覆盖行，状态诚实记为 `unified contract not consumed`。
5. FIN 0.1.3 计划新增 7A.5，把当前工作拆成 `S2-06A` 文档、`B` 实现、`C` proof、`D` canary、`E` formal proof decision，再按依赖回到 S1/S3/S4/S5。

## 4. 核心产品决定

正式原则：模型可以看见、理解、比较、选择和引用受治理的精确事实；material fact 的最终数字、单位、期间、实体身份、引用和 lineage 由确定性 Harness 写入并验证。Harness 是 truth compiler，不是 report author。

这不是“超级拼装”：本地不得生成 thesis、经济机制、counter-thesis 或完整报告段落。模型继续拥有研究判断和自然语言；只有 material fact span 使用 typed ref，最终由本地替换和校验。

## 5. 规划与停止边界

- 当前完成的只是 `S2-06A` 文档/范围收敛；代码、模型调用、candidate、score、product acceptance 均为 0。
- RC-P36-148 保持 active；只有 `S2-06B/C` 实现并独立证明后才可记 engineering repaired。
- 下一项为一个共享零调用包，不逐字段 live patch，不直接启动 DELL R3/MU/NVDA。
- 合同发生变化后只做一个最小自然 canary；是否再次做 DELL supervised proof需要新的项目级 authority decision。
- S3-08/09 和 S5 必须继续把八维研究内容质量、paired gain、qualified-human acceptance 与 anti-template 作为硬门，不能用 `L1=0` 或完整链跑通代替。

## 6. 当前下一项

`FIN-0.1.3-013-S2-06B-CORRECTION-OBJECTIVE-PROTECTED-NARRATIVE-NUMERIC-FACT-VIEW-AND-CLOSURE-RECEIPT-ONE-SHARED-ZERO-CALL-IMPLEMENTATION`

本 worklog 不授权 Runtime 修改或模型执行；后续若执行，必须在新 attempt 中保存历史 DELL R2 immutable failure。
