# 125 P38 Historical Case And Sector Report Calibration Audit

日期：2026-07-11

## 问题

在 Point 01 runtime migration 实施前，先审计历史 case 的真实表现深度和跨行业投研报告结构，再决定首批 calibration case，避免只用 P36/AI infrastructure 过拟合。

## 完成内容

- 新增可复算历史 case audit，读取 13 个 case catalogs/fixtures、P33/P34 readiness、最新 P33 no-paid multicase audit，以及 P20/P30/P33/P36 运行记录。
- 将成熟度拆成 `catalog_only`、`fixture_defined`、`exemplar_artifact_backed`、`live_artifact_backed`、`fresh_specialist_fixture_proven`、`node_level_proven`、`full_chain_proven`、`human_accepted`。
- 单列旧 SEC benchmark generation：cross-industry10 0.88、combined40 0.884，确认其可作为旧 retrieval/exact-value/bounded synthesis 基线，但不可晋升为当前 agentic runtime proof。
- 审计 5 份 CFA/CFA Society 行业报告、1 份 CFA 通用报告指引和 WorkBuddy 9 个 AI-infrastructure 本地样本，提取 sector mechanisms、metrics、evidence families 和 report-type surfaces。
- 冻结 4 个 positive shadow calibration cases 和 3 个 negative controls。

## 结果

- Source memberships：122；去重 cases：137。
- Artifact-backed packs：15，其中 exemplar-backed 14、case-specific AI/Semis 1。
- No-paid fresh-specialist fixture：1。
- 真实 node-level fresh specialist / explicit accepted full-chain / human-accepted 跨行业可比 cases：0。
- 当前 agentic runtime generalization：`not_proven`。
- Sector/report archetype sources：7，覆盖 7 个 group。

## 产物

- `src/sec_agent/calibration_case_audit.py`
- `scripts/engineering/build_calibration_case_and_report_archetype_audit.py`
- `configs/engineering_handoff/historical_case_audit_sources_v0_1.json`
- `configs/engineering_handoff/sector_report_archetype_sources_v0_1.json`
- `data/manifests/historical_case_performance_audit_v0_1.json`
- `data/manifests/sector_report_archetype_audit_v0_1.json`
- `data/manifests/calibration_case_selection_v0_1.json`
- `docs/architecture/repository/HISTORICAL_CASE_PERFORMANCE_AUDIT_20260711.zh-CN.md`
- `docs/architecture/repository/SECTOR_REPORT_ARCHETYPE_AUDIT_20260711.zh-CN.md`
- `docs/architecture/repository/CALIBRATION_CASE_SELECTION_20260711.zh-CN.md`
- `tests/test_calibration_case_audit.py`

## 验证

```text
python -m pytest -q tests/test_calibration_case_audit.py
3 passed

python scripts/engineering/build_calibration_case_and_report_archetype_audit.py
historical=pass, archetype=pass, selection=pass

python scripts/engineering/build_repository_architecture_inventory.py
node_count=1713, edge_count=7425, python_parse_error_count=0

python scripts/engineering/check_repository_architecture_guard.py
status=pass, error_count=0, warning_count=27
```

Architecture guard 的 27 个 warning 均为既有大文件复杂度警告；本轮新增审计模块未进入 warning list。

## 边界

- 未运行 paid model、full-chain、live retrieval、crawler、parser 或新模型推理。
- WorkBuddy samples 只用于产品形态校准，不作为其中事实的 authority source。
- CFA Research Challenge 报告是结构/方法样本，不作为当前公司事实或投资建议。
- Shadow calibration case 尚未成为 runtime pass；只有 deterministic + reviewer gates 通过后才允许 DecisionSurface Compiler 单节点 paid comparison。
