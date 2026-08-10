# 846 — FIN 0.1.3 S2 selected-Evidence 数字候选共编处置

日期：2026-08-10

状态：零调用 root-cause／合同处置完成；Runtime 尚未实现；DELL 不自动重跑

## 这次真正决定了什么

changed-input DELL 报告中的 `16.1／97.8%／5000` 都能回到 cited Evidence，因此问题不是“模型编造了三个数字”。当前 `NumericFactView` 仍由旧手工事实表重绑定，再临时追加 TSMC 和行情事实；而模型输入会看到 selected SourceMaterial 的完整正文。Evidence Pack 一扩充，就可能出现“模型看得到、事实也是真的、但交付合同没登记”的数字。

本轮没有给 DELL 再补三个白名单，也没有把全文数字一律放行。只读审计发现，正则全放行会把资产负债表几十个无关单元格、日期尾标、Rule 4090、256GB、3D 等一起当成金融事实；同时还无法正确表达“2027 年上半年”“2027 年以后”“中个位数”等时间或定性区间。

最终选择 provider-neutral 的方案：从最终 selected Evidence 共编 `MaterialNumericCandidateInventory`，由 source-aware extractor 发现候选，再按实体、指标、期间、单位、币种、Evidence Slot／Facet、关系方向和输出边界做确定性裁决。精确值、官方舍入表面、单位换算和公式输出必须归入同一 stable fact 的 presentation program；原始 capture 继续完整私有留存，但不自动获得输出权威。

## 为什么不是 DELL 专用修复

六案数据形态不同：

- DELL／MU／NVDA 主要包含叙事正文、法说、财报表格、供应商和竞争对手 read-through；
- ORCL／ASML／ANET 的 held-out Pack 主要是已经带 table path 的 structured metrics，甚至没有 SourceMaterial 正文；
- ASML 同时需要保留 EUR 金额和 lithography system 台数，ANET 需要区分三个月与六个月，ORCL 的全公司收入不能自动变成 AI 收入。

因此合同同时覆盖 monetary／percentage／count／range／temporal boundary／qualitative band，并要求 structured metric 在 `source_materials=[]` 时仍能工作。核心合同不加入 DeepSeek 特有分支；未来模型更强时，只调整它能看到和能请求的候选范围，不修改金融事实骨架。

## 模型与 Harness 的分工

- Harness 负责候选坐标、事实身份、期间、币种、单位、舍入、公式、ref、lineage 和最终渲染；它不代写 thesis、机制和反方。
- 模型负责在授权事实面内做研究判断、机制综合、反证与写作。
- Specialist／Lead 可以看到 bounded Evidence 和就地标注的 non-output 数字；Writer 只看到可写 `NUM/FORM` 与遮蔽后的上下文；Verifier 负责语义支持。本地 numeric guard 永远保留最终独立否决权。
- 如果 Harness 漏编且模型又无 ref 输出，两类 finding 可以同时成立，不能把责任全推给任何一边。

## 后续边界

下一项只允许零调用实现：schema、source-aware adapter、deterministic adjudicator、stable fact／presentation program、节点视图和 local guard，然后跑 DELL／MU／NVDA 与 ORCL／ASML／ANET fake、capture replay 和 mutation，最后做两个 clean worker 的独立证明。

本轮不重开 S1 parser；S1 只保留残余来源和估值缺口。WWC、机制桥和内容密度仍归 S3。没有 DeepSeek、Provider、网络、source、retry、admission 或 business promotion，也没有 Owner acceptance／release。

机器可读处置：`configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_cocompilation_zero_call_disposition_v1_0.json`。

current next：`FIN-0.1.3-S2-SELECTED-EVIDENCE-NUMERIC-CANDIDATE-COCOMPILATION-MINIMUM-ZERO-CALL-IMPLEMENTATION`。
