# DB_01：Point 01 Canonical Store and Transaction Boundary

日期：2026-07-12

状态：`frozen_for_point01_m0_m2_v1_0 / sqlite_first_postgresql_compatible / no_migration_run`

上游：SCHEMA_01、TECH_06、Point 01 18.1。

## 1. 决策

```text
first runtime/fixture backend = SQLite WAL
logical schema/repository contract = PostgreSQL-compatible
production target option = PostgreSQL
PostgreSQL parity gate = required before M4 planning cutover
```

Domain/service 只依赖 `CanonicalStore` repository ports，不接收 `sqlite3.Connection`。Backend-specific SQL、PRAGMA、JSON/boolean/timestamp/upsert/locking 差异隔离在 adapter。

## 2. Logical tables

| Table | Object | Write owner | Payload policy |
| --- | --- | --- | --- |
| canonical_research_cases | InstitutionalResearchCase current identity/projection | TECH_06 executes TECH_01 command | indexed metadata |
| canonical_case_control_versions | CaseControlSummaryVersion | TECH_06 | JSON payload allowed under schema |
| canonical_task_run_bindings | LegacyTaskRunBinding | TECH_06 | metadata only |
| canonical_work_units | WorkUnit versions/current execution projection | TECH_06 | metadata + input ref set |
| canonical_attempts | Attempt | TECH_06 | metadata; large result externalized |
| canonical_actor_snapshots | ActorSnapshot | TECH_06 | no credentials/raw tokens |
| canonical_events | EventEnvelope | TECH_06 append only | payload ref/digest only for large payload |
| canonical_artifact_versions | ArtifactVersionEnvelope | TECH_06 | object-store ref/hash |
| canonical_decision_surface_contract_versions | DecisionSurfaceContractVersion | TECH_06 executes TECH_01 write | typed JSON + indexed identity |
| canonical_decision_surface_cell_versions | DecisionSurfaceCellVersion | TECH_06 executes TECH_01 write | typed JSON + indexed case/contract |
| canonical_evidence_slot_versions | EvidenceSlotVersion | TECH_06 executes TECH_01 write | typed JSON + indexed cell/source role |
| canonical_compile_gap_versions | CompileTimeGapVersion | TECH_06 executes TECH_01 write | typed JSON + indexed gap type/status |
| canonical_shadow_comparisons | ShadowComparisonRecord | TECH_06 executes TECH_10 write | summary SQL + detailed artifact ref |
| canonical_lane_cutover_decisions | LaneCutoverDecision | TECH_06 executes TECH_10 write | append-only decision versions |
| canonical_legacy_identity_map | LegacyCanonicalIdentityMap | TECH_06 | migration metadata |
| canonical_outbox | transactional event delivery | TECH_06 | event ref/status/attempt |
| canonical_schema_migrations | backend migration history | migration runner | version/hash/applied time |

## 3. Required relational constraints

- tenant/project/case composite scope enforced on all case-bound tables；
- case-control/contract/cell/slot/gap versions reference case_id and exact parent version；
- WorkUnit references case_id、logical target and exact input version set digest；
- Attempt references one WorkUnit version；
- Event references TaskRun/WorkUnit/Attempt when applicable and one ActorSnapshot；
- Artifact references producer Attempt and input refs digest；
- same logical ID + version number unique；
- one active legacy binding per normalized legacy identity；
- append-only tables reject update/delete through repository policy and conformance tests；
- current-head projection uses optimistic compare-and-swap, never `INSERT OR REPLACE`。

## 4. Transaction boundaries

### 4.1 Create/bind Case

One transaction：identity map check -> ResearchCase identity -> CaseControl v1 -> LegacyTaskRunBinding -> RESEARCH_CASE_CREATED event -> outbox。Duplicate idempotency key returns existing result。

### 4.2 Create WorkUnit

One transaction：validate case/binding/input refs -> insert WorkUnit version -> append WORK_UNIT_CREATED -> reserve budget metadata -> outbox。

### 4.3 Start/finish Attempt

Start：lease/expected WorkUnit state -> Attempt -> WORK_UNIT_STARTED/ATTEMPT_STARTED。Finish：Attempt terminal state + output ArtifactVersionEnvelope + WorkUnit state compare-and-swap + terminal events + outbox。Large payload write must complete before SQL commit and be content-addressed; orphan cleanup is asynchronous and never treated as committed artifact。

### 4.4 Compile DecisionSurface

One logical commit boundary：ArtifactVersionEnvelope、Contract/Cell/Slot/CompileGap versions、WorkUnit/Attempt terminal state、events and outbox。If object payload is large, object-store put occurs first; SQL transaction atomically publishes refs. Partial publication is forbidden。

### 4.5 Shadow comparison / cutover

Comparison record and artifact ref written atomically。LaneCutoverDecision append-only; authority projection change and cutover event occur in one transaction with expected previous authority version。Rollback creates a new decision/version; no destructive reverse migration。

## 5. ObjectStore

First backend is filesystem-compatible content-addressed store behind `CanonicalObjectStore` port。Key uses SHA-256 digest; SQL stores URI/key、digest、size、media/schema type、encryption/classification and retention。Do not store absolute developer-machine paths as portable artifact identity。

Payload classes：DecisionSurface bundle、comparison details、reviewer Markdown/JSON report、large compiler/model output。Raw private CoT and credentials are forbidden。

## 6. SQLite adapter rules

- WAL、foreign_keys、busy_timeout configured by adapter startup；
- explicit transactions；no implicit autocommit for state mutation；
- UTC ISO timestamp serialization with parser validation；
- boolean encoded by adapter with check constraint；
- JSON validated in application layer and optionally JSON1；
- no domain-level PRAGMA、rowid identity、dynamic typing dependence or `INSERT OR REPLACE`；
- writer concurrency initially serialized/limited; lock timeout becomes typed retryable error。

## 7. PostgreSQL parity

Same repository conformance suite must pass：schema semantics、unique/FK/check constraints、optimistic concurrency、idempotency、transaction rollback、event sequence、outbox、replay and query projections。M4 requires container/service benchmark after resource check; no production claim from SQLite-only pass。

## 8. Retention / backup / recovery

- events、identity maps、cutover decisions and artifact metadata retained for audit policy；
- shadow payload retention default 90 days unless promoted/legal hold；
- raw prompt/model payload policy separate from event metadata；
- backup includes SQLite DB + object manifest + migration history；
- recovery validates DB integrity、artifact digest availability and event projection parity；
- deletion uses policy/tombstone; no direct removal of audit-required rows。

## 9. Freeze gates

1. Logical table names map 1:1 to SCHEMA_01 objects/control records。
2. SQLite/PostgreSQL repository interface has no backend-specific domain method。
3. Transaction tests cover success、duplicate、stale-write、object-store failure and rollback。
4. No table grants shadow objects writer eligibility。
5. No migration/DDL has been executed by this document freeze。
