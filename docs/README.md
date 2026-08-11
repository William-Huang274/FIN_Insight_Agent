# FIN 0.1.3 文档地图

当前文档按“产品目标、当前技术事实、研究质量、历史证据”分层，避免用数百份过程日志冒充项目结构。

## 每次恢复先读

1. [当前上下文包](project_os/current_context_pack.zh-CN.md)
2. [高级助手协作规范](project_os/senior_assistant_collaboration_policy.zh-CN.md)
3. [FIN 0.1.3 当前计划](product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md)
4. [当前代码图](architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md)

## 产品

- [产品 PRD](product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md)：完整愿景和用户价值。
- [FIN 0.1.3 当前计划](product/FIN_0_1_3_CURRENT_BASELINE_AND_S0_TO_S5_CLOSEOUT_PLAN_20260812.zh-CN.md)：唯一当前范围、S 阶段归属和下一步。
- [PRD 功能吸收与版本分配矩阵](product/FIN_PRD_FULL_ABSORPTION_AND_RELEASE_ALLOCATION_MATRIX_20260719.zh-CN.md)：长期功能归属。

## 当前工程

- [当前代码图](architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md)
- [严格主线验收程序](architecture/repository/FIN_0_1_3_STRICT_MAINLINE_REBASELINE_ACCEPTANCE_AND_MIGRATION_PROGRAM_20260811.zh-CN.md)
- 机器活动图：`../configs/repository/fin_0_1_3_active_baseline_manifest_v1_0.json`
- 严格验收门：`../configs/repository/fin_0_1_3_strict_mainline_rebaseline_acceptance_v1_0.json`
- 历史重定向：`../archive/versions/FIN_0_1_3_REBASELINE_REDIRECT_INDEX.jsonl`

## 研究质量与案例证据

- [研究内容质量 Rubric](eval/FIN_0_1_3_RESEARCH_CONTENT_OUTPUT_QUALITY_RUBRIC_20260806.zh-CN.md)
- [三案例研究协议](eval/FIN_0_1_3_CODEX_VS_DEEPSEEK_THREE_CASE_RESEARCH_PROTOCOL_20260806.zh-CN.md)
- `research/fin_0_1_3_gold_candidates/`：DELL、MU、NVDA 参考研究。
- `research/fin_0_1_3_retrieval_autopsy/`：三案例真实检索尸检与跨案根因。

## Project OS

`project_os/` 的规范路径只保存当前短投影和长期方法注册表。完整旧上下文、能力台账和 root-cause 台账已保存在版本归档，避免每次任务恢复都重新加载数 MB 历史。

历史设计、attempt、运行报告和旧工作日志不在当前文档入口；请通过 archive 重定向索引查找。
