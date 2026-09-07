# 016 S1 三案 Evidence Acquisition 尸检

日期：2026-08-17

状态：`read_only_audit_complete / owner_repair_decision_pending`

## Owner 授权范围

完成三件事：

1. 只读审计现有 DELL／MU／NVDA artifacts；
2. 逐命题还原“问了什么—找到什么—哪里丢失—是否补证—模型用了什么”；
3. 形成跨案例业务故障图。

没有授权代码、索引、模型、网络、Evidence 晋升或新 live。

## 已完成

- 按当前 authority 和 lineage 收敛 Pack、anchor、query／ranking、外源回放、dynamic truth spine、DELL R7 与独立内容验收；历史 attempt 仅作为因果证据，不重复计数。
- 对三案按需求、经营、价值／利润、现金、供给、反方、估值逐命题判断 Pack Readiness。
- 确认 DELL 20 条 reviewed Evidence 最终只有 8 条进入 R7 模型 Evidence cards，且全部为 DELL issuer direct；Pack 中的 ecosystem evidence 没有进入本次 cell model view。
- 确认 DELL 8 个请求产生 128 个候选、111 个 unreviewed、8 个唯一 accepted reviewed Evidence、12 个 typed gap、0 dynamic promotion；working-capital／issuer-counter／upstream-counter 三个请求为 0 accepted。
- 确认 MU／NVDA 只有一个工程形状请求且均 0 accepted，没有等价自然 Planner、补证循环、五单元模型消费或报告；当前不能称为泛化证明。
- 保留 S1／S2／S3 分账：Pack 不充分和晋升失败属于 S1；产品利润／PIT／AI cash bridge 属于 S2；DELL 已可见 revenue／orders／backlog 被否认属于 S3。

## 主要结论

1. 当前不是单一检索召回问题。source coverage、对象精度、头部排序、Evidence admission、CoverageState、第二轮补证、S2 bridge 和 S3 consumption 分别存在断点。
2. 当前最早的结构断点是 S1 closed-world reviewed join 与命题覆盖账缺失。已有候选不能在动态回合被审计晋升，Pack 有材料也可能因 slot/facet binding 变成 EvidenceResponse 0 条。
3. DELL 当前是部分命题 ready，不是完整报告 ready；MU／NVDA 的动态 readiness 尚未验证。
4. 现阶段没有证据支持先全面重建向量库或微调 Embedding／reranker。它们仍是候选层问题，但不能替代 EvidenceDecision 和补证闭环。

## 权威输出

- `docs/architecture/retrieval/FIN_0_1_3_S1_DELL_MU_NVDA_EVIDENCE_ACQUISITION_AUTOPSY_20260817.zh-CN.md`

## 未执行

- 0 code／model／Provider／network／retrieval／index／source promotion／live；
- 未更改历史 qrels、Pack、R7 或失败 attempt；
- 未签发任何后续修复 authority。

## 下一门

Owner 先审阅尸检结果，再决定是否按“CoverageState 与动态晋升 → 一次反驳补证闭环 → MU／NVDA 等价动态纵切 → S2 bridge → S3 consumption”进入有界实现。
