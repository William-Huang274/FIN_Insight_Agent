# 126 P38 WorkBuddy Multi-sector HTML And Trajectory Calibration Audit

日期：2026-07-11

## 问题

用户按 WB-S01-S08、WB-T01-T04 完成 12 个 WorkBuddy 多行业/多任务测试。需要读取最终 HTML、memory、task、artifact-index、project logs 和 traces，判断 WorkBuddy 是否真正 agentic、各行业 DecisionSurface 如何变化，以及哪些模式应进入 FIN，哪些不能越过 Evidence Gate。

## 输入

- WorkBuddy reports：`C:/Users/hht13/WorkBuddy/2026-07-11-*`。
- WorkBuddy state：`C:/Users/hht13/.workbuddy/{sessions,traces,projects,tasks,artifact-index}`。
- 正式 cases：WB-S01-S08、WB-T01-T04。
- 重复对照：`2026-07-11-21-12-24` 网络安全反证版本。
- 中止目录：`2026-07-11-21-00-01`，无 HTML。

## 结果

- HTML：12/12；完整 trajectory：12/12；agentic loop observed：12/12。
- DeepSeek V4 Pro model calls：200；tool calls：399；WebSearch：98。
- 总 trajectory wall time 约 70.68 分钟，平均每 case 约 5.89 分钟。
- Cumulative input tokens 16,177,682，其中 cached 14,921,600（92.24%）；uncached 1,256,082；output 286,137。
- External links 222；government/issuer primary links 30，约 13.5%。
- 10/12 满足全部 required surfaces；WB-T01/WB-T03 缺明确 data-gap surface。
- Machine-readable claim-to-observation lineage：0/12。
- WB-S07 顶层 agent trace error，但 HTML/memory 已完成；WB-T02 memory Edit ENOENT 后自修复并完成。
- 同一 WB-T04 prompt 的两个完成版本 source-domain Jaccard 约 4.4%，结构稳定但来源与量化表达不稳定。

## Visual QA

使用本机 Edge + Playwright 在 1440x900 抽查 WB-S02、WB-S03、WB-T03、WB-T04：

- 横向溢出 0；console/page errors 0；
- WB-S02 13 个 canvas、WB-S03 5 个、WB-T04 1 个均实际渲染；
- WB-T03 为 17 张静态表格，无 canvas，布局正常；
- 首屏结论、Decision Surface 和表格层级清晰，适合快速扫描；
- 主要缺口是 claim 旁缺可点击 citation/lineage，而不是视觉完成度。

临时截图位于 `.tmp_workbuddy_visual_audit/`，不进入 Git。

## 官方源抽样核验

抽样核验并确认：May 2026 CPI 4.2%、Walmart Q1 FY27 7.3%/4.1%、Target Q1 2026 6.7%/5.6%、Lilly 2025 revenue USD 65.179B、Novo 2025 sales DKK 309.064B、PANW Q3 FY26 NGS ARR +60% 且含 acquired ARR USD 1.6B。该检查不是整份报告事实验收。

## 工程结论

1. WorkBuddy 观察到 multi-step tool-use activity，不是一次性 prompt；但 DeepSeek V4 不是强模型，该观察不证明 loop 质量成熟。
2. Sector 与 report type 可作为 DecisionSurface 正交输入的待验证假设，需由独立行业 rubric 和 FIN shadow compiler 验证。
3. gap-driven search、独立上下文、scenario/What-Would-Change 和 HTML/dashboard surface 只能进入改进候选，不能直接吸收。
4. FIN 不应照搬其 source promotion：外链 authority 不稳定、0/12 claim lineage、同 prompt source repeatability 弱。
5. TECH_10 增加 same-prompt research repeatability，比较 cells、sources、claims、numbers、gaps、artifact 和 cost/yield。

## Point 01 吸收裁决

12-case 的主要用途不是直接生成正式 packs，而是作为 Point 01 `M2 compiler design input + M3 shadow calibration corpus`：

1. 先补语义/轨迹复审，再形成 `DefectAndPatternCandidateMatrix`，区分 `prompt_required`、`independently_observed` 和 `reviewer_inferred`。
2. 再把候选裁决为 universal、sector、report-type、case-only、evidence-slot 或 reject。
3. 只有 reviewer-confirmed candidates 才能编译为 versioned fixture packs，并交给 FIN shadow compiler 做比较。
4. WorkBuddy 的 agentic loop 观察回流 TECH_06/08；source/lineage/numeric 缺口回流 TECH_02/03/04/09；context/cost 回流 TECH_07/10；artifact surface 回流 PRD/TECH_09；same-prompt variance 回流 TECH_10。
5. WorkBuddy 报告质量不替代 Point 01 M3 gate。M3 必须评价 FIN compiler 的 contract/cell/slot 输出，且 M4 cutover 仍需独立批准。

## 复审发现的审计盲区

上一轮是 artifact/trajectory inventory，不是完整研究质量审计。尚未系统覆盖：cell 语义质量和 material coverage、完整 claim-source entailment、numeric/unit/period/currency、source freshness/conflict、query/tool/observation usefulness、repair 因果和 stop rule、context duplication/yield、handoff/version consistency、chart data binding、行业判断和估值深度。正式 matrix 前必须补审；默认裁决是 improve/redesign/reject，只有独立证据充分时才 retain。

2026-07-11 follow-up：上述 semantic/structured-trajectory re-audit 已完成，产物见 `WORKBUDDY_12CASE_SEMANTIC_TRAJECTORY_REAUDIT_20260711.zh-CN.md` 和 `workbuddy_semantic_trajectory_reaudit_v0_1.json`。结果为 direct promotion 0、pack candidates 20、retain-with-independent-evidence 4、redesign-then-pack 16。

## 产物

- `configs/engineering_handoff/workbuddy_multisector_calibration_cases_v0_1.json`
- `src/sec_agent/workbuddy_calibration_audit.py`
- `scripts/engineering/build_workbuddy_multisector_calibration_audit.py`
- `tests/test_workbuddy_calibration_audit.py`
- `data/manifests/workbuddy_multisector_calibration_audit_v0_1.json`
- `docs/architecture/repository/WORKBUDDY_MULTISECTOR_CALIBRATION_AUDIT_20260711.zh-CN.md`

## 验证

```text
python -m pytest -q tests/test_workbuddy_calibration_audit.py tests/test_calibration_case_audit.py
5 passed

python scripts/engineering/build_workbuddy_multisector_calibration_audit.py
status=pass, case_count=12, trace_available_count=12, agentic_loop_observed_count=12

python scripts/engineering/build_calibration_case_and_report_archetype_audit.py
historical=pass, archetype=pass, selection=pass

python scripts/engineering/build_repository_architecture_inventory.py
node_count=1719, edge_count=7445, python_parse_error_count=0

python scripts/engineering/check_repository_architecture_guard.py
status=pass, error_count=0, warning_count=27
```

27 个 warning 均为既有大文件复杂度警告；本轮新增 audit module 未进入 warning list。

## 边界

- 未复制或展示 WorkBuddy raw reasoning/CoT，只保存 aggregate trajectory metrics。
- WorkBuddy HTML、memory 和 trace 仍是 external calibration input，不是 FIN accepted runtime evidence。
- 未运行 FIN paid model、full-chain、Writer、live retrieval/parser 或 runtime cutover。
