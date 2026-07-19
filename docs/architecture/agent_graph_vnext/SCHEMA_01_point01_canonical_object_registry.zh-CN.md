# SCHEMA_01：Point 01 Canonical Object Registry

日期：2026-07-12

状态：`frozen_for_point01_m0_m2_v1_0 / no_runtime_cutover`

上游：PRD、TECH_00 Owner Constitution、TECH_01 ResearchCase、TECH_06 Durable Runtime、Point 01。

机器可读合同：`configs/engineering_handoff/point01_canonical_object_registry_v0_2.json`。

## 1. 冻结范围

本合同只冻结 Point 01 M0-M2 所需 canonical identity、version 和 reference，不定义 Evidence/Numeric/Judgment/Memory/Review/Release/Monitoring 完整业务对象。

```text
InstitutionalResearchCase
 -> CaseControlSummaryVersion
 -> LegacyTaskRunBinding
 -> WorkUnit -> Attempt -> EventEnvelope
 -> ActorSnapshot
 -> ArtifactVersionEnvelope
 -> DecisionSurfaceContractVersion
 -> DecisionSurfaceCellVersion
 -> EvidenceSlotVersion
 -> CompileTimeGapVersion
 -> ShadowComparisonRecord
 -> LaneCutoverDecision
```

## 2. 通用字段

所有 canonical versioned objects 必须具有：

- stable logical ID；
- immutable version ID / monotonic version number；
- `schema_version`；
- `tenant_id / project_id / case_id`，不适用时显式 null policy；
- `created_at / recorded_at` UTC timestamp；
- `actor_snapshot_ref`；
- `causation_event_id / correlation_id`；
- `permission_snapshot_ref / policy_config_refs`；
- `content_digest`；
- `supersedes_version_id / current_status`；
- retention/data classification。

禁止以 ticker、文件名、模型生成标题或自增 row id 作为跨系统稳定身份。

## 3. 对象冻结表

| Object | Business writer | 第一阶段 authority | 关键 identity/version |
| --- | --- | --- | --- |
| InstitutionalResearchCase | TECH_01 | canonical identity；非完整 lifecycle authority | case_id / case_version |
| CaseControlSummaryVersion | TECH_01 | canonical shadow | case_id + summary_version |
| LegacyTaskRunBinding | TECH_06 | canonical binding；legacy TaskRun 仍 authoritative | binding_id / binding_version |
| WorkUnit | TECH_06 | canonical shadow-lane execution | work_unit_id / work_unit_version |
| Attempt | TECH_06 | canonical execution | attempt_id / attempt_no |
| ActorSnapshot | TECH_06 | canonical execution identity snapshot | actor_snapshot_id / snapshot_version |
| EventEnvelope | TECH_06 | canonical append-only event | event_id / sequence_no |
| ArtifactVersionEnvelope | TECH_06 envelope；payload owner by artifact_type | canonical immutable envelope | artifact_id / artifact_version |
| DecisionSurfaceContractVersion | TECH_01 | shadow until M4 planning cutover | contract_id / contract_version |
| DecisionSurfaceCellVersion | TECH_01 | shadow until M4 | cell_id / cell_version |
| EvidenceSlotVersion | TECH_01 slot requirement；TECH_02 future consumer | shadow planning object | slot_id / slot_version |
| CompileTimeGapVersion | TECH_01 | shadow planning gap | gap_id / gap_version |
| ShadowComparisonRecord | TECH_10 quality semantics；TECH_06 persistence | comparison-only | comparison_id / comparison_version |
| LaneCutoverDecision | TECH_10 gate decision；TECH_06 execution | inactive until M4 | cutover_id / decision_version |
| LegacyCanonicalIdentityMap | TECH_06 migration control | canonical migration metadata | mapping_id / mapping_version |

## 4. First-slice schemas

### 4.1 InstitutionalResearchCase

Required：case_id、case_version、tenant/project、case_type、created_from_task_ref、CaseControlSummaryRef、current planning heads、accountable owner ref、status、retention/policy refs。

第一阶段 status 仅允许 `shadow_created / shadow_active / planning_cutover_candidate / planning_authoritative / rolled_back / archived`。不得使用 released、monitoring 或 R4 状态冒充完整 Case lifecycle。

### 4.2 LegacyTaskRunBinding

Required：binding_id、case_id、legacy system/store/task/run IDs、legacy authority status、normalized identity digest、created/verified time、adapter version、conflict status。

同一 tenant + legacy system + legacy task/run identity 只能有一个 active binding。M1-M3 中 `legacy_authority_status=authoritative`。

### 4.3 WorkUnit / Attempt

WorkUnit 是逻辑工作；Attempt 是一次物理执行。WorkUnit required：type、target refs、input version set、expected state version、state、budget/permission refs、idempotency key。Attempt required：attempt_no、worker/model/tool refs、started/ended、terminal reason、input/output refs。

Retry 不创建新 WorkUnit version；repair/input change 必须创建新 WorkUnit version。

### 4.4 EventEnvelope

采用 TECH_06 envelope：event/type/run/work-unit/attempt、sequence、occurred/recorded、ActorSnapshotRef、causation/correlation、before/after state version、payload ref/digest、schema version。单 TaskRun 内 sequence 单调递增；event append-only。

### 4.5 ArtifactVersionEnvelope

Required：logical artifact ID/version、artifact_type、payload business owner、producer attempt、input refs、schema/content hash、object-store ref、created time、status、supersedes、retention/license。

第一阶段 artifact_type 只允许 DecisionSurfaceContract bundle、shadow comparison payload 和 reviewer report。Writer/deliverable artifact 不在范围内。

### 4.6 DecisionSurface planning objects

- Contract：case/query/scope/as-of/universe/language、universal/sector/report pack refs、compiler policy、required cells、status。
- Cell：decision question、archetype/sector/report/case origin、owner role、materiality、dependencies、status、stop rule。
- EvidenceSlot：cell binding、evidence role、entity/period/metric/source policy、forbidden substitutions、acceptance role、required/optional。
- CompileTimeGap：cell/slot、gap type、reason/materiality、owner suggestion、next action；不得表示 Evidence Gate runtime gap。

## 5. 不变量

1. 单一 business writer；persistence adapter 不推进业务 head。
2. Version immutable；current head 是 projection。
3. CaseVersion、TaskRun state version、WorkUnit version、ArtifactVersion 不得混用。
4. Shadow objects 不得被 Writer、Evidence runtime 或正式 Workbench 当 accepted truth。
5. Actor/permission/policy refs 在 state mutation 时必填。
6. Large payload 只进 ObjectStore；SQL 保存 ref/hash/index。
7. 所有 timestamps 为 timezone-aware UTC；业务 as-of 单独保存。
8. Schema evolution forward-only；旧版本可读、不可原地回写。

## 6. v0.1 supersession

`canonical_object_registry_v0_1.json` 保留为全链工程交接历史输入，不再作为 Point 01 first-slice owner source of truth。其 joint owner 字段由本 v0.2 的 `business_writer / persistence_owner / consumers` 替代。v0.2 只覆盖 M0-M2，不宣称替代 v0.1 中所有后续对象。

## 7. Freeze gate

- machine-readable JSON 可解析；
- 每个对象只有一个 business writer；
- 所有 first-slice tables/API/events 可映射到对象 ID；
- 不含 EvidenceRequest、PromotionDecision、NumericProgram、Judgment、DecisionAttestation 或 Monitoring 的 runtime implementation；
- TECH_00/01/06 与 Point 01 引用一致。
