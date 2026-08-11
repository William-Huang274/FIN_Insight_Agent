# P38 Point 01 M2.3 Pack Registry and Resolution

日期：2026-07-12

状态：`m2_3_full_implemented / calibrated_four_sector_registry_corpus / shadow_only`

## 完成

- `PlanningPackRegistry` 管理 immutable `PlanningPackVersion`、exact reads、freshness reports、supersession ledger、lifecycle events 和 deterministic snapshot replay。
- 支持 Universal、Sector、Report-Type、Case Delta 四类 versioned pack；只允许 `reviewed_runtime_candidate` 或 `provisional_case_delta`，拒绝 `document_only` promotion。
- exact read 对 stale、not-yet-effective、superseded version fail-close；resolution 返回 pack refs 与 resolved source-authority policy refs。

## 校准

`run_point01_m2_3_pack_registry_fixture.py` 覆盖 AI/Semis、SaaS、Healthcare、Banks 四个 sector 的 resolution，并验证 Case Delta、supersession 后 v1 拒绝/v2 选择、stale exact 拒绝、document-only 拒绝、snapshot event-history replay。focused registry tests `4 passed`。

## 边界

这是 in-memory shadow planning registry，snapshot 可重放但不是生产持久/tenant registry；不会写 legacy TaskRun、不会调用模型、检索或 Evidence/Writer。M2.5-M2.7 已完成后，M2.2 full serializer 获得 implementation admission，仍待完整 artifact/readback 实现。
