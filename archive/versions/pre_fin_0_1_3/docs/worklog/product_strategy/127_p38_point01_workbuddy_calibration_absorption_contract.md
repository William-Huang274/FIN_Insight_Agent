# 127 P38 Point 01 WorkBuddy Calibration Improvement Contract

日期：2026-07-11

## 问题

WorkBuddy 的 12 个跨行业、跨议题 case 原本用于校准 Point 01 方向。需要明确这些结果应进入 Point 01、PRD 和 TECH 的哪一层，避免在尚未完成 pattern adjudication 时直接把外部报告结构固化成 FIN packs。

## 裁决

1. 12-case 首要归属是 Point 01 `M2 compiler design input + M3 shadow calibration corpus`。
2. WorkBuddy 使用 DeepSeek V4，不按强模型或成熟 reference 处理；外部样本先补语义/轨迹复审，再生成 `DefectAndPatternCandidateMatrix`。
3. 候选再分类为 universal、sector、report-type、case-only、evidence-slot 或 reject。
4. 每条候选默认进入 improve/redesign/reject review；只有独立 rubric corroboration 且 reviewer-confirmed 的改进后候选才能进入 versioned pack registry 和 deterministic compiler fixtures。
5. FIN shadow compiler 的输出质量才是 M3 gate 对象；WorkBuddy 报告质量不能替代 M3，也不能触发 M4 cutover。

## 文档与审计修正

- Point 01：增加 12-case 改进基线合同、四层 planning composition、M2/M3 gate 和 prompt-leakage 防护。
- TECH_01：从三层改为 `Universal Responsibility + Sector + Report-Type + Case Delta`，增加 `report_type_pack_refs` 和 candidate lifecycle。
- PRD：只形成跨行业/跨议题适配能力假设与产品边界，不采纳具体事实、标题顺序、工具选择或原始 reasoning。
- TECH_02/03/04/09：吸收 source authority、claim lineage、numeric binding 暴露的问题。
- TECH_06/08：吸收 bounded tool loop、artifact complete/trajectory degraded 的 runtime 要求。
- TECH_07/10：吸收 context cost、AIE 和 same-prompt repeatability。
- TECH_09：吸收 HTML、表格、图表和 Decision Surface 的可审阅产品 surface。

## 边界

- 本轮修正 audit code、generated manifest/report 和 architecture docs，但不改变 FIN runtime。
- 尚未生成正式 `DefectAndPatternCandidateMatrix` 或 pack registry。
- 未实现 Point 01 runtime、canonical schema/store、compiler 或 shadow lane。
- 未运行 FIN paid model、full-chain、Writer、live retrieval/parser 或 cutover。

## 后续完成

2026-07-11 已完成完整 12-case semantic/structured-trajectory re-audit。该复审关闭“尚未复审”的边界，但不构成 pack promotion：直接晋升为 0；20 个候选需要独立证据或重设计后再进入 FIN fixtures。
