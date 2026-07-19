# P38 Point 01 M2.1 Full Compiler Input / Cell / Slot / Gap Validation

日期：2026-07-12

状态：`m2_1_full_implemented / calibrated_local_schema_corpus / m2_open`

## 完成

- `CompilerInputValidationPolicy` 冻结 10–20 material cell、owner、materiality、source policy、acceptance role 和 forbidden-substitution policy。
- `validate_compiler_input_full()` 对 query/universe/as-of、cell count、duplicate/unknown/self/cycle dependency、owner/materiality、stop rule、required slot、source/forbidden/acceptance policy fail-close。
- `validate_decision_surface_bundle_full()` 在既有 parent/case/version validation 上追加 assembled Cell/Slot/Gap 的 full policy、bundle cycle 与 gap owner/reason/action checks。
- 原 `compile_deterministic_fixture()` 和 basic `validate_decision_surface_bundle()` 保留为 M1B/M2 fixture compatibility；一-cell bundle 在 basic mode 可 pass，在 full mode 必因 10-cell policy fail-close。

## Corpus 与验证

- policy：`configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json`。
- fixture runner：`scripts/engineering/run_point01_m2_1_compiler_validation_fixture.py`；输出 `data/manifests/point01_m2_1_compiler_validation_fixture_result_v1_0.json`，正例 10-cell DAG pass；cell count、cycle、duplicate/unknown dependency、owner/source/forbidden 和 invalid gap 负例均被捕获。
- `pytest -q -m fast_contract tests/contract/test_point01_m2_design_freeze.py tests/contract/test_point01_m2_compiler_full_validation.py tests/contract/test_point01_decision_surface_planning.py`：`10 passed`。
- full validator、fixture runner 和 tests 均 `compileall` pass；没有模型、Web、paid/full-chain 或 authority write。

## 边界与下一步

这只关闭 M2.1 的 schema/shape contract，不选择 pack、不生成用户问题的完整 DecisionSurface、不检索证据、不变更 legacy authority。后续 M2.3-M2.7 已补齐 registry/selection/composition/evidence-policy/legacy semantic mapping；按已冻结 dependency graph，M2.2 full assembler/serializer/readback 已获 implementation admission，但仍待实现完整 artifact envelope、atomic commit/readback 与 replay corpus。
