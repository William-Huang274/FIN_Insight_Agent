# Repository Architecture Audit

本目录维护代码仓库的结构审计、引用图和清理规则。

- `REPOSITORY_ARCHITECTURE_MAP.zh-CN.md`：自动生成的仓库摘要、功能图、复杂度热点、数据资产类型和待审对象。
- `REPOSITORY_DEEP_AUDIT_20260711.zh-CN.md`：截至 2026-07-11 的代码、测试、数据资产和 PRD/TECH 对齐审计。
- `ENGINEERING_HANDOFF_BASELINE_20260711.zh-CN.md`：Canonical Object Registry、Legacy Mapping Matrix 和 Test Profile Split 的可执行交接基线。
- `NEXT_PHASE_IMPLEMENTATION_DISCUSSION_DRAFT_20260711.zh-CN.md`：下一阶段新需求和新功能实施顺序的可修订讨论草稿，尚非正式 backlog。
- `POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md`：第一点 Control/DecisionSurface migration 的完整 M0-M7 技术路线草稿。
- `TECH_POST_REFACTOR_SPLIT_AND_UPDATE_AUDIT_20260712.zh-CN.md`：新版 PRD/TECH 上游到下游更新后的拆分、owner、覆盖和实施就绪审计；结论为顶层拆分通过、实施级子规格仍需补齐。
- `POINT01_TECH_PRD_SPLIT_ALIGNMENT_AUDIT_20260712.zh-CN.md`：Point 01 四份前置合同冻结后的 PRD/TECH/Point 对齐、15-object registry、10-mapping 和 store/API/cutover 边界审计。
- `RELEASE_OPERATING_MODEL_20260717.zh-CN.md`：PRD、TECH、Point 与版本列车之间的统一发布运行模型。
- `POINT_EXECUTION_PLAN_TEMPLATE.zh-CN.md`：后续 Point 的 release binding、四阶段证据、gate budget、repair stop 和 closeout 模板。
- `RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md`：下一内部产品版本 FIN 0.1 的四周执行计划；以完整研究工作台闭环为产品范围，P36 AI infrastructure 作为 Anchor calibration。
- `RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md`：FIN 0.1 可直接开发的产品与工程详设；覆盖页面/交互、read model、API、state/event、permission、前后端代码边界、Point 02-07 的 38 个 execution points、四阶段验收、测试和 rollback。
- `FIN_0_1_PRD_TECH_POINT_IMPLEMENTATION_BASELINE_20260719.zh-CN.md`：截至 2026-07-19 的 PRD/TECH/Point 实证基线；区分 current release path、formal Point owner closeout、真实模型/人审/operational qualification 和 release readiness。
- `../../product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`：`P001-F01`-`F15` 的 PRD、TECH owner、产品 surface、Point 和 release acceptance 映射。
- 完整机器可读图：`data/manifests/repository_architecture_inventory_v0_1.json`。

维护命令：

```powershell
python scripts/engineering/build_repository_architecture_inventory.py
python scripts/engineering/check_repository_architecture_guard.py
python scripts/engineering/build_engineering_handoff_baseline.py
pytest -q tests/test_repository_architecture_inventory.py
pytest -q tests/test_engineering_handoff.py
```

静态图用于发现依赖、孤儿候选和复杂度变化，不替代 runtime trace。归档或删除前仍需确认动态加载、调度器、文档命令和外部调用方。
