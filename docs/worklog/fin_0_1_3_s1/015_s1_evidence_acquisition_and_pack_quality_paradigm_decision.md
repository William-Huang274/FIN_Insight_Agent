# 015 S1 证据获取与 Evidence Pack 质量范式决策

日期：2026-08-17

状态：`decision_recorded / no_code / no_model / no_network`

## 问题

在讨论把 DELL 固定五单元泛化为 ResearchBlueprint、Generic Cell Runtime 和多形态 DeliveryPlan 时，Owner 指出：当前 S1 的内外源检索、排序、补源和动态再检索质量仍很一般。如果先增加研究结构复杂度，会把资料不充分的地基埋得更深，也会继续把 S1、模型和 Harness 的失败混在一起。

## 证据与判断

- 当前 S1 已有对象、候选、排序 shadow、Source Intake、官方 PDF 和 reviewed Pack，但没有统一的 proposition-level EvidenceCoverageState 与 Pack Readiness。
- 模型能提出 EvidenceRequest，但当前产品还不能稳定执行“评估第一轮材料—寻找反方／替代解释—发起更针对性请求—按信息增量停止”的闭环。
- DELL 当前缺产品利润桥、ASP／PVM、供应分配／时点和估值；MU／NVDA 也存在不同资料缺口，因此报告信息密度弱不能只归咎于 DeepSeek。
- R7 对已经可见的 AI revenue、orders 和 backlog 作出 false absence，仍是独立 S3 缺陷；S1 补源不能替它洗白。

## 决策

1. 把 S1 定义为 `证据获取—反驳—补证—充分性验收` 产品链，而不只是 retrieval/ranking 工程层。
2. 把 ResearchBlueprint／DeliveryPlan 保留为已接受产品方向，但代码实现后移到 S1 task-relative Pack Readiness 通过之后。
3. 下一项先做现有三案 artifacts 的只读 Evidence Acquisition 尸检和跨案 failure atlas；不修改代码、索引、标签，不调用模型、网络或 Provider。
4. 根据尸检结果只修 S1 最早责任层，避免把 source、parser、query、ranking、Evidence Gate、S2 和 S3 问题打成一个总包。

## 已更新

- PRD 16.38：通用研究内核、动态 ResearchBlueprint 和多形态交付。
- PRD 16.39：S1 Evidence Acquisition／Pack Readiness 产品门。
- `docs/architecture/retrieval/FIN_0_1_3_S1_EVIDENCE_ACQUISITION_AND_PACK_QUALITY_PARADIGM_20260817.zh-CN.md`：阶段责任、数据流、质量门、状态与评测矩阵。
- 当前 S0–S5 计划和 Project OS：记录新的先后顺序与 S1/S3 分账。

## 未执行

- 未修改 Runtime 或测试代码；
- 未运行模型、Provider、网络、检索、索引、补源或评测；
- 未重写历史 qrels、Evidence Pack、R7 报告或失败 attempt；
- 未授权 S1 实现或 S3 新 live。

## 下一步

只读生成 DELL／MU／NVDA 的命题级证据链尸检，至少回答：模型提出了什么问题、S1 实际找到了什么、哪些材料被排序或 Gate 丢失、哪些是真实公开资料缺口、是否主动寻找了反方、第二轮查询是否缩小 gap，以及现有 Pack 对当前研究问题为何 ready／partial／blocked。
