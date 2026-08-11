# Repository Architecture Audit

本目录维护代码仓库的结构审计、引用图和清理规则。

- FIN_0_1_3_REPOSITORY_BASELINE_AUDIT_20260811.zh-CN.md：当前全仓基线；覆盖 6,112 个 tracked 文件、本机 ignored/private 数据、真实产品入口静态依赖图、FIN 0.1.3 candidate 与 Workbench cutover 边界、版本冲突和“反复修”根因。该文档是当前人工判读入口，Owner 审阅前不授权删除、迁移或恢复 S3。
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
- `FIN_0_1_2_S0_COMMON_RUNTIME_AND_TEST_CONTRACT_REBASELINE_20260731.zh-CN.md`：FIN 0.1.2 S0 共同 Runtime 权限边界、单一来源 consumer envelope、五类 proof semantics，以及已通过的 hermetic dependency package、完整 per-test capture、双 disposable parity 和 active-suite closeout。
- `FIN_0_1_2_S1_REALISTIC_THREE_CASE_DETERMINISTIC_VERTICAL_STAGE_PLAN_20260731.zh-CN.md`：FIN 0.1.2 S1 的 bounded production-consumer 迁移、DELL/MU/NVDA realistic fixture、mutation/collect-all/full-fake 证明矩阵，以及固定 T01–T04 与 G0–G6 边界。
- `../../product/FIN_0_1_INTERNAL_ALPHA_FEATURE_SCOPE_MATRIX_20260717.zh-CN.md`：`P001-F01`-`F15` 的 PRD、TECH owner、产品 surface、Point 和 release acceptance 映射。
- 完整机器可读图：`data/manifests/repository_architecture_inventory_v0_1.json`。

当前紧凑机器基线为 configs/repository/fin_0_1_3_repository_baseline_v1_0.json。旧完整机器引用图 data/manifests/repository_architecture_inventory_v0_1.json 仍可用于查文本引用，但它的 active/reachability 分类不能直接作为清理依据。

当前 rebaseline、代码生命周期和 Workbench cutover 权威见 `FIN_0_1_3_CLEAN_BASELINE_CODE_LIFECYCLE_AND_WORKBENCH_CUTOVER_20260811.zh-CN.md`，机器摘要见 `configs/repository/fin_0_1_3_code_lifecycle_cutover_v1_0.json`。该方案禁止按修改时间或静态未可达直接归档，要求先证明 successor、产品消费者切换和 redirect manifest。

维护命令：

```powershell
python scripts/engineering/build_repository_architecture_inventory.py
python scripts/engineering/check_repository_architecture_guard.py
python scripts/engineering/build_engineering_handoff_baseline.py
pytest -q tests/test_repository_architecture_inventory.py
pytest -q tests/test_engineering_handoff.py
```

静态图用于发现依赖、孤儿候选和复杂度变化，不替代 runtime trace。归档或删除前仍需确认动态加载、调度器、文档命令和外部调用方。
