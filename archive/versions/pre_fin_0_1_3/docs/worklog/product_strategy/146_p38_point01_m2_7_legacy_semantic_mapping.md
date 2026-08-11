# P38 Point 01 M2.7 Legacy Semantic Migration Mapping

日期：2026-07-12

状态：`m2_7_full_implemented / calibrated_four_case_information_loss_review / shadow_only`

## 完成

- 在原 pure legacy objective adapter 旁新增 `adapt_legacy_objective_semantically()`，输出不可变 `LegacyMigrationPlan`。
- 每个 legacy required item 都保留 identity，并且只能 semantic `merge`、`split` 或 `downgrade`；每项强制 information-loss tags/review。
- direct equivalence、mapping coverage 缺失、错误的 merge/split/downgrade target/reason 均 fail-close；legacy fact/query 不会被伪装成一对一 DecisionCell。

## 校准与验证

- `run_point01_m2_7_legacy_semantic_mapping_fixture.py` 覆盖 AI/Semis、SaaS、Healthcare、Banks 四个 mapping plan，并验证 direct-equivalence 与 missing-mapping 负例。
- `tests/contract/test_point01_m2_legacy_semantic_mapping.py` 与原 `test_point01_legacy_objective_adapter.py`：`4 passed`；runner、adapter 与 tests `compileall` 通过。
- model/external call 为 0，legacy TaskRun/required items 仍是 authoritative history/input。

## 边界与回滚

- M2.7 只生成 semantic mapping audit，绝不写 legacy state、触发 cutover、调用模型或运行 M3 comparison。
- 回滚为移除新增 semantic mapping types/fixture/tests；原 `adapt_legacy_research_objective()` 不受影响。
