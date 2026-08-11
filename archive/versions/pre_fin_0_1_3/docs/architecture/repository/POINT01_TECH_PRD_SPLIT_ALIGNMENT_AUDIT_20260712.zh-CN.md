# Point 01 / TECH / PRD Split Alignment Audit

日期：2026-07-12

状态：`alignment_audit_pass_after_repair / prerequisite_contracts_frozen / implementation_not_admitted`

审计对象：PRD、TECH_00/00A、TECH_01/06/10、Point 01、SCHEMA_01、DB_01、API_01、MIGRATION_01、Point01 registry/mapping v0.2。

## 1. 总体结论

| 审计维度 | 结果 |
| --- | --- |
| PRD -> TECH 产品能力与 owner | PASS |
| TECH -> Point first-slice 范围 | PASS |
| SCHEMA -> DB table coverage | PASS，15/15 |
| Mapping -> registry object refs | PASS，15 refs / 0 missing |
| 单一 business writer | PASS，15/15 |
| API command/event -> object/store boundary | PASS_AFTER_REPAIR |
| Migration authority/cutover/rollback | PASS |
| Runtime implementation | NOT STARTED / NOT ASSESSED |

Point 01 前置合同已经冻结，可以作为 M0 ADR、DDL/repository interface 和 contract-test 设计的上游；但尚未满足 `implementation_admitted`，因为 first-slice ADR、实际 JSON/Pydantic/DDL、test manifest、feature flag 和 Project OS admission 还未创建。

## 2. 文档拆分关系

```text
PRD
 -> TECH_00 / TECH_00A
 -> TECH_01 Research business semantics
 -> TECH_06 execution/persistence semantics
 -> TECH_10 comparison/cutover quality gate
 -> SCHEMA_01 object/identity/version freeze
 -> DB_01 store/transaction freeze
 -> API_01 command/event freeze
 -> MIGRATION_01 authority/cutover freeze
 -> Point 01 M0-M7 orchestration
```

职责判断：

- PRD 说明用户价值、产品 lifecycle 和 bounded claim；
- TECH 定义 stable business owner 和跨模块宪法；
- SCHEMA/DB/API/MIGRATION 把 TECH 编译成 first-slice implementation contract；
- Point 01 编排 milestone、gate 和 rollout，不重复定义对象字段或 DB/API 细节；
- 配置 JSON 提供 machine-readable frozen registry/mapping；
- worklog 记录为何改变，不是 source of truth。

该拆分不存在新的平行业务主账本。

## 3. PRD -> TECH -> Point coverage

| PRD requirement | TECH contract | Point 01 coverage | 判断 |
| --- | --- | --- | --- |
| InstitutionalResearchCase | TECH_01 business；TECH_06 persistence | Case identity + bounded summary only | aligned；full lifecycle excluded |
| Research Control / DecisionSurface | TECH_01 | Contract/Cell/Slot shadow compile | aligned |
| Durable execution | TECH_06 | WorkUnit/Attempt/Event/Artifact envelope | aligned |
| Human-AI actor trace | TECH_06 | ActorSnapshot minimal execution identity | aligned；OA/review excluded |
| Evidence control | TECH_02/04 | EvidenceSlot requirement only | aligned；execution/promotion excluded |
| Institutional Memory | TECH_03 | refs/placeholders only | aligned；registry runtime excluded |
| Review/Release | TECH_09 | no formal artifact review/release | aligned；shadow calibration only |
| Eval/cutover quality | TECH_10 | ShadowComparison + LaneCutoverDecision | aligned |
| Monitoring/R4 | TECH_11/10 | compatibility fixture only | aligned；runtime excluded |

Point 01 没有通过“先建字段”冒充完整 PRD capability。

## 4. Object alignment

| Point object | Parent TECH semantic | Writer | Alignment note |
| --- | --- | --- | --- |
| InstitutionalResearchCase | TECH_01 ResearchCase | TECH_01 | identity only |
| CaseControlSummaryVersion | TECH_01 CaseControlState | TECH_01 | bounded projection |
| LegacyTaskRunBinding | TECH_06 migration control | TECH_06 | legacy remains authoritative |
| WorkUnit / Attempt | TECH_06 runtime | TECH_06 | shadow lane only |
| ActorSnapshot / EventEnvelope | TECH_06 identity/event | TECH_06 | no OA/full accountability workflow |
| ArtifactVersionEnvelope | TECH_06 generic persistence | TECH_06 envelope | payload owner by artifact_type |
| DecisionSurfaceContract/Cell | TECH_01 | TECH_01 | shadow until M4 |
| EvidenceSlotVersion | TECH_01 requirement；TECH_02 future consumer | TECH_01 | no EvidenceRequest execution |
| CompileTimeGapVersion | TECH_01 Gap subtype | TECH_01 | planning gap only |
| ShadowComparisonRecord | TECH_10 Eval/Quality artifact | TECH_10 | comparison only |
| LaneCutoverDecision | TECH_10 RuntimeReleaseGate specialization | TECH_10 | TECH_06 executes transaction |
| LegacyCanonicalIdentityMap | TECH_06 migration metadata | TECH_06 | not product object |

## 5. Machine-readable audit

`point01_canonical_object_registry_v0_2.json`：

- object count 15；
- unique object IDs 15；
- unique object names 15；
- unique logical tables 15；
- missing/compound business writer 0；
- every object has persistence owner and authority boundary。

`point01_legacy_mapping_matrix_v0_2.json`：

- mapping count 10；
- canonical refs 15；
- missing registry refs 0；
- every mapping has mode、authority、information loss and cutover gate。

DB_01 文档覆盖 registry logical tables 15/15。

Freeze manifest：`configs/engineering_handoff/point01_prerequisite_contract_freeze_manifest_v1_0.json`，记录四份合同与两份 machine-readable artifacts 的 SHA-256；`implementation_admitted=false`。后续修改任一 frozen artifact 必须升级 manifest 并重跑本审计。

## 6. 审计发现并修复

1. **v0.1 joint owner 不再适用**：新 v0.2 使用 business_writer/persistence_owner；v0.1 保留历史全链 handoff。
2. **LegacyTaskRunBinding 未进入 TECH_00 graph**：已补为 TECH_06 migration control object。
3. **LaneCutoverDecision owner 模糊**：已定义为 TECH_10 RuntimeReleaseGate 的 planning-lane specialization，TECH_06 只执行。
4. **ArtifactVersion owner 可能冲突**：已拆成 TECH_06 `ArtifactVersionEnvelope` 与 `artifact_type` payload business owner。
5. **Shadow review 与正式 review 混名**：API 改为 `submit_shadow_calibration_review`；不触发 TECH_09 formal Review/DecisionAttestation。
6. **Migration human approval 与 artifact approval 混淆**：已明确是 TECH_10/06 configuration cutover approval receipt，不是 TECH_09 research artifact attestation。
7. **Point 旧 SQL/API/adapter 初步设计可能继续竞争**：已增加 supersession note，正式细节以 DB_01/API_01/MIGRATION_01 为准。

## 7. 仍未冻结/实现的内容

以下不是 alignment failure，而是 implementation admission 前的下一层交付：

1. First-slice ADR：目录、package、dependency injection、repository port、object-store adapter、feature flag。
2. Executable JSON Schema/Pydantic models 和 generated docs。
3. SQLite DDL/migration、repository interfaces、PostgreSQL conformance skeleton。
4. RuntimeFacade Python protocols/result/error/event enums。
5. Contract-test manifest、P36/cross-sector fixtures、negative controls 和 rollback drill script。
6. Project OS implementation admission row。

Evidence/Numeric/Judgment/Memory/Review/OA/Monitoring runtime 继续留在后续 slice，不应加入上述 M0 实现。

## 8. 实施 admission gate

Point 01 可以进入 implementation planning，但不能开始无合同编码。正式 `implementation_admitted` 需：

- ADR approved；
- schema/API/DB generated artifacts pass validation；
- test manifest and fixture inputs frozen；
- code module/legacy adapter file ownership confirmed；
- feature flag and rollback drill acceptance frozen；
- Project OS 更新状态。

本审计不修改 runtime maturity，不运行 migration、数据库建表、paid model 或 full-chain。

## 9. 最终判断

- **Point 文档是否与新版 PRD 对齐**：是。
- **Point 文档是否与 TECH owner 宪法对齐**：审计修复后是。
- **四份子合同是否拆分合理**：是，职责无重叠。
- **是否可以删除旧 v0.1**：不可以；保留为历史全链 handoff，但 Point scope 已被 v0.2 supersede。
- **是否可以开始编码**：下一步先完成 ADR + executable schema/DDL/API/test manifest admission package，然后才能进入 M1 implementation。
