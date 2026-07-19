# P38 Point 01 M1B DecisionSurface Planning Service

日期：2026-07-12

状态：`reclassified_to_m2_1_m2_2_fixture_proven / m2_execution_matrix_open / milestone_m2_not_complete`

M1B 新增 deterministic-only `DecisionSurfacePlanningService`：CompilerInputContract、PackSelectionDecision、cell/slot seeds、fixture bundle generator、bundle invariant validation 与 committed shadow DecisionSurface read model。fixture 不调用模型、web、tool 或外部写；validation/read 不改变 authority。

覆盖：deterministic repeatability、case/parent/dependency/slot/gap fail-closed validation，以及 committed shadow bundle readback。边界：这不是 model compiler、M2 shadow node、M3 comparison/reviewer、M4 cutover、Evidence/Numeric/Judgment/Writer/Workbench 或 full-chain。

2026-07-12 rebaseline：现有成果归档为 M2.1 shape schema/validator fixture 与 M2.2 deterministic assembler/readback fixture。它接收人工预填的 cells/slots，不会从 query 选择 packs 或设计 10-20 个判断 cells；`case_delta_pack_refs`、完整 quality policy、multi-sector calibration 和 model-backed compiler 尚未闭环。完整剩余路线见 Point 01 第 26.3 节 M2.3-M2.10。
