# P38 Point 01 M2.4 Pack Selection Engine

日期：2026-07-12

状态：`m2_4_full_implemented / calibrated_multi_sector_report_type_rubric / shadow_only`

## 完成

- `PackSelectionEngine` 从 explicit 或 query-derived sector/report-type/case intent 选择 versioned PackResolution。
- 每次结果保留 selection reasons、rejections 或 conflicts，并固定 decision digest；ambiguous query、未知/缺失 intent 和 registry resolution failure 均 fail-close。
- engine 仅调用 in-memory M2.3 registry；没有模型、网络、evidence retrieval 或 legacy write。

## 校准

`run_point01_m2_4_pack_selection_fixture.py` 校准 AI/Semis、SaaS、Healthcare、Banks × initiation/event_update/valuation_price_in，共 12 个 selected 正例；另验证 ambiguity conflict 和 missing-sector rejection。focused selection tests `4 passed`。

## 边界

选择完成不等于用户问题已编译为 DecisionSurface。M2.5-M2.7 后续 inputs 已完成；M2.2 full serializer 现为 implementation-admitted，但仍未实现，必须先满足完整 artifact envelope/lineage/readback contract。
