# 128 P38 WorkBuddy 12-case Semantic Trajectory Reaudit And Pack Candidates

日期：2026-07-11

## 范围

对 WB-S01-S08、WB-T01-T04 的最终 HTML 和结构化 trajectory 进行逐案复审。读取 tool input/output、sequence、errors、token metadata 和最终报告；不读取或复制 raw reasoning/generation spans。

## 结果

- 12/12 完成语义与轨迹裁决。
- Direct WorkBuddy pack promotion：0。
- Pack candidates：20。
- `retain_with_independent_evidence`：4。
- `redesign_then_pack`：16。
- Global reject patterns：12。

维度均值：sector mechanism 4.50、decision-cell semantics 4.58、artifact usability 4.08；evidence binding 2.00、numeric integrity 1.42、valuation/scenario 1.67、tool grounding 1.50、repair/reflection 1.17、context efficiency 1.00、repeatability 1.58。

## 关键问题

1. 12/12 数值表格单元格没有 claim-local citation。
2. 12/12 没有 subagent/handoff 或 claim-to-observation lineage。
3. WebSearch-heavy trajectory 没有 source-open verification；结构化财务工具结果也没有进入最终 claim lineage。
4. 出现市场市值约 10 倍、产品收入 annualization、acquisition value/ARR 等系统性 numeric/category 错误。
5. S04/T01 对同一 Target 同店销售事实冲突，证明没有共享 accepted-fact consistency gate。
6. Artifact syntax validation 没有覆盖语义、数字、引用、图表数据或故事线一致性。

## Pack 裁决

拟实现 20 个候选分为：5 个 universal、5 个 report-type、9 个 sector/sector-delta、1 个 presentation。只保留研究责任、业务机制和结构合同；所有 WorkBuddy facts、values、rankings、probabilities、valuation outputs、source strategies 和 trajectories 都禁止继承。

## 产物

- `configs/engineering_handoff/workbuddy_semantic_trajectory_review_v0_1.json`
- `src/sec_agent/workbuddy_semantic_trajectory_reaudit.py`
- `scripts/engineering/build_workbuddy_semantic_trajectory_reaudit.py`
- `tests/test_workbuddy_semantic_trajectory_reaudit.py`
- `data/manifests/workbuddy_semantic_trajectory_reaudit_v0_1.json`
- `docs/architecture/repository/WORKBUDDY_12CASE_SEMANTIC_TRAJECTORY_REAUDIT_20260711.zh-CN.md`

## 边界

本轮不实现 packs、DecisionSurface compiler、Evidence/Numeric Gate 或 runtime cutover；不运行 FIN paid model、Writer 或 full-chain。
