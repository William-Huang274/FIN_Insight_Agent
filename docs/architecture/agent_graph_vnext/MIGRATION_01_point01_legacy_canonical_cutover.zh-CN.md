# MIGRATION_01：Point 01 Legacy-to-Canonical Cutover

日期：2026-07-12

状态：`frozen_for_point01_m0_m4_v1_0 / no_migration_executed`

上游：SCHEMA_01、DB_01、API_01、TECH_00/01/06/10、Point 01。

机器可读 mapping：`configs/engineering_handoff/point01_legacy_mapping_matrix_v0_2.json`。

## 1. Authority policy

| Phase | Legacy TaskRun | Canonical execution | DecisionSurface planning | Writer/downstream |
| --- | --- | --- | --- | --- |
| M0 | authoritative | schema only | none | legacy only |
| M1 | authoritative | canonical shadow kernel | none | legacy only |
| M2-M3 | authoritative | canonical shadow lane | shadow, read-only | legacy only；canonical forbidden |
| M4 after gate | authoritative | canonical for planning lane | canonical authority for approved scope | downstream still via compatibility projection |
| M5+ | separately decided | incremental canonical authority | canonical | migrated per later slice |

Point 01 does not cut over global TaskRun authority。M4 only cuts DecisionSurface planning for case-scoped approved lane。

## 2. Mapping scope

Included：legacy task/run identity、node execution、attempt/retry、events/tool/workpaper trace metadata、artifact refs、research objective、required items/dimensions、P34 evidence slots and planning ambiguity gaps。

Excluded：live EvidenceRequest execution、candidate/promotion、numeric trace migration、specialist judgment、full Workpaper/LeadReview、Context/Memory、Writer/Review/Release、Watchlist。These enter later migration contracts。

## 3. Migration modes

- `identity_binding`：不复制 legacy TaskRun business truth，只建立 canonical Case/binding；
- `shadow_projection`：从 legacy payload 编译 canonical planning object，不改变 legacy output；
- `semantic_split`：一个 legacy dimension/node 拆成多个 canonical cells/work units；
- `merge_adapter`：多个 legacy event/trace formats 归一到 one envelope；
- `new_control_record`：shadow comparison/cutover decision 无 legacy equivalent；
- `read_only_compatibility_projection`：cutover 后向 legacy consumer 投影，不恢复 legacy writer。

## 4. M0 readiness

Freeze：source files/functions/tables/payload fields、normalized identity、sample rows、missing fields、information loss、adapter owner、expected target、parity metric、rollback path。Unknown dynamic consumer blocks retirement but not shadow generation；must enter consumer inventory。

Baseline artifacts：

- v0.1 historical registry/mapping retained；
- Point01 v0.2 registry/mapping authoritative for first slice；
- P36 + SaaS/Healthcare/Banks positive calibration；
- relationship/parser/commercial negative controls；
- legacy planning output snapshot and hashes。

## 5. Shadow write policy

Canonical shadow writes use separate namespace/store and feature flag `decision_surface_shadow_v0_1`。No legacy table mutation、no Writer consumption、no Evidence execution、no formal Workbench approval。Failure is visible; system does not silently write an alternative canonical success row or alter legacy output。

Each shadow record binds legacy input version/hash、adapter/compiler/policy/schema versions、actor/permission and correlation IDs。

## 6. Comparison / calibration

`ShadowComparisonRecord` evaluates：

- identity mapping and missing/extra/split/merge；
- 10-20 judgment-oriented cells；
- required evidence slots、source policy、forbidden substitutions；
- sector/report/case pack origin；
- gap/stop/owner completeness；
- deterministic repeatability and model variance；
- legacy information preserved/lost；
- no forbidden downstream consumption。

Comparison result is TECH_10 quality truth, not planning authority。Human review records accept/reject/repair but cannot directly flip cutover flag。

## 7. M4 cutover gate

All required：

1. SCHEMA/DB/API repository conformance pass on SQLite；
2. PostgreSQL parity/concurrency/replay benchmark pass；
3. positive/negative calibration threshold pass with no hard identity/source-policy violation；
4. case-scoped consumer inventory complete；
5. canonical-to-legacy required-item projection parity accepted；
6. shadow objects never consumed by Writer/Evidence runtime before gate；
7. rollback drill pass；
8. TECH_10 `LaneCutoverDecision=passed` with exact schema/code/config/baseline refs；
9. authorized migration/cutover approval receipt for authority change；该 receipt 属于 TECH_10/06 runtime configuration release control，不是 TECH_09 research artifact `DecisionAttestation`；
10. Project OS capability/maturity ledger updated。

## 8. Cutover

RuntimeFacade executes approved decision with optimistic expected authority version。One transaction writes LaneCutoverDecision execution receipt、authority projection and PLANNING_AUTHORITY_CHANGED event。Feature scope is case-scoped initially；sector/user/global scope requires new decision and evidence。

After cutover：canonical DecisionSurface planning is sole writer for approved scope；legacy required-item output becomes read-only projection/compatibility adapter。Dual authoritative write forbidden。

## 9. Rollback

Triggers：hard contract violation、data corruption、unexplained parity regression、stale-write escape、permission leak、unrecoverable latency/SLO breach、consumer incompatibility or approval revocation。

Rollback：new LaneCutoverDecision version -> restore legacy planning authority for scope -> stop canonical authority writes -> retain canonical events/artifacts -> rebuild/read projections -> incident/failure attribution。No destructive down migration or history deletion。

Rollback window：minimum two stable release cycles or 60 days, whichever longer, subject to Point 01 retention policy。After window, rollback requires new migration plan; historical replay remains。

## 10. Legacy retirement

Retirement requires active legacy writer/consumer count zero、historical replay pass、compatibility period complete、rollback window closed、review approval and repository reference graph update。Archive before delete；destructive cleanup separate approval。

## 11. Freeze gates

- machine-readable mapping parses and references SCHEMA_01 IDs；
- every included mapping has authority、information-loss and cutover gate；
- excluded downstream domains remain excluded；
- no code/data migration executed during freeze；
- Point 01 and TECH_00A link this contract as implementation prerequisite。
