# P38 Point 01 M2.5 Cell Composition

日期：2026-07-12

状态：`m2_5_full_implemented / calibrated_four_sector_adversarial_corpus / shadow_only`

## 完成

- 新增 `CellCompositionEngine`，仅消费已选择的 pack refs 与 versioned archetypes，确定性输出 10–20 个 `ComposedDecisionCell`。
- composition 保留 merge/split/dedupe、origin-pack、dependency、fact-to-slot、What-Would-Change 与 counterevidence owner lineage。
- archetype 未被选择、merge/slot contract 冲突、依赖缺失、owner 或 WWC/counterevidence 不合规则 fail-close。

## 校准与验证

- `run_point01_m2_5_cell_composition_fixture.py` 覆盖 AI/Semis、SaaS、Healthcare、Banks 四个 10-cell 正例，及 merge conflict、dependency missing、unselected pack 三个负例。
- `tests/contract/test_point01_m2_cell_composition.py`：`4 passed`；其中包含把 composition seeds 交给 M2.1 full validator 的集成检查。
- runner、runtime 和 tests `compileall` 通过；model/external call 均为 0。

## 边界与回滚

- 这是 shadow planning composition，不读取/写入 legacy TaskRun，不检索证据、不调用模型、不进入 Evidence/Writer/full-chain/cutover。
- 回滚为移除该 engine、policy、fixture 与 contract tests；不会影响 legacy authority。
