# API_01：Point 01 Runtime Command and Event Contract

日期：2026-07-12

状态：`frozen_for_point01_m0_m2_v1_0 / no_runtime_implementation`

上游：SCHEMA_01、DB_01、TECH_01、TECH_06、Point 01。

## 1. Boundary

API_01 defines in-process/service-neutral commands and result envelopes. It does not require HTTP, MCP or distributed queue in M0-M2. CLI、Python service and future HTTP adapters must call the same RuntimeFacade/application service.

## 2. Command envelope

Every state-mutating command carries：

```json
{
  "command_id": "...",
  "command_type": "CREATE_RESEARCH_CASE",
  "schema_version": "1.0",
  "tenant_id": "...",
  "project_id": "...",
  "case_id": "...",
  "actor_snapshot_ref": "...",
  "permission_snapshot_ref": "...",
  "policy_config_refs": [],
  "idempotency_key": "...",
  "expected_state_version": 0,
  "causation_event_id": null,
  "correlation_id": "...",
  "requested_at": "UTC timestamp",
  "payload": {}
}
```

Payload must be schema-validated before transaction。Secret/credential/private CoT forbidden。

## 3. Frozen commands

### RuntimeFacade

- `create_research_case`：create canonical Case identity/summary and optional legacy binding；
- `bind_legacy_task_run`：idempotently bind existing Case to legacy TaskRun；
- `create_work_unit`：create logical DecisionSurface compile/comparison work；
- `start_attempt`；
- `complete_attempt`；
- `fail_attempt`；
- `cancel_work_unit`；
- `get_case_execution_view`；
- `get_work_unit_execution_view`；
- `list_events`；
- `get_artifact_version`；
- `replay_projection`：rebuild without external model/tool/web calls。

### DecisionSurfacePlanningService

- `compile_decision_surface`：requires active compile WorkUnit/Attempt and frozen compiler policy；
- `validate_decision_surface_bundle`；
- `record_compile_time_gap` as part of bundle commit；
- `get_decision_surface`；
- `compare_with_legacy_plan`；
- `submit_shadow_calibration_review`；
- `request_planning_lane_cutover`；
- `execute_planning_lane_cutover` only after valid TECH_10 decision；
- `rollback_planning_lane_cutover`。

M0-M2 forbids Evidence execution、SourceHunter、Numeric、Judgment、Writer、Release、OA and Monitoring commands。

## 4. Result envelope

```json
{
  "command_id": "...",
  "status": "succeeded|rejected|conflict|failed",
  "state_version_before": 1,
  "state_version_after": 2,
  "event_ids": [],
  "artifact_refs": [],
  "projection_refs": [],
  "reused_idempotent_result": false,
  "warnings": [],
  "error": null
}
```

`succeeded` means command transaction succeeded, not research quality/reviewer acceptance/cutover approval。

## 5. Error taxonomy

- `validation_error`；
- `permission_denied`；
- `identity_conflict`；
- `idempotency_conflict`：same key, different normalized payload；
- `stale_state_version`；
- `illegal_state_transition`；
- `missing_dependency`；
- `artifact_write_failed`；
- `transaction_conflict`；
- `legacy_binding_conflict`；
- `shadow_authority_violation`；
- `cutover_gate_not_satisfied`；
- `backend_unavailable`。

Errors are typed and audit-recorded where security policy permits; do not silently fallback to legacy write on canonical command failure。

## 6. Event namespace

Frozen M0-M2 events：

```text
RESEARCH_CASE_CREATED
CASE_CONTROL_SUMMARY_ADVANCED
LEGACY_TASK_RUN_BOUND
WORK_UNIT_CREATED
WORK_UNIT_STARTED
WORK_UNIT_COMPLETED
WORK_UNIT_FAILED
WORK_UNIT_CANCELLED
ATTEMPT_STARTED
ATTEMPT_COMPLETED
ATTEMPT_FAILED
ARTIFACT_VERSION_CREATED
DECISION_SURFACE_COMPILED
DECISION_SURFACE_VALIDATION_FAILED
SHADOW_COMPARISON_RECORDED
SHADOW_CALIBRATION_REVIEW_SUBMITTED
PLANNING_CUTOVER_REQUESTED
PLANNING_CUTOVER_DECIDED
PLANNING_AUTHORITY_CHANGED
PLANNING_ROLLBACK_EXECUTED
STALE_WRITE_REJECTED
```

All events use TECH_06 EventEnvelope and DB_01 transaction/outbox policy。Business events name completed facts, not commands。

## 7. Idempotency / concurrency

- command id unique for audit；idempotency key scoped by tenant + command type + logical target；
- exact duplicate returns prior ResultEnvelope；same key/different digest rejects；
- expected state version required for mutation；create uses explicit expected absence/version 0；
- compiler/model retry creates new Attempt but not new WorkUnit version if logical inputs unchanged；
- input or policy change creates new WorkUnit/Artifact/Contract version；
- worker cannot commit if lease/input heads/state version stale。

## 8. Replay

Projection replay reads events/artifacts only。Default replay does not re-call model、web、API、tool or external write。Compiler rerun is explicit new attempt/repair, not replay。Unknown event schema blocks projection with typed error; no best-effort silent skip for state-mutating events。

## 9. Read models

Read API separates：

- execution state；
- input currency；
- output usability；
- planning authority (`legacy / shadow / canonical_for_lane`)；
- artifact current/superseded；
- comparison/review/cutover state。

Frontend/reviewer report cannot infer pass from missing fields。

## 10. Freeze gates

1. Every command maps to DB transaction and one or more EventEnvelope types。
2. Every event maps to SCHEMA_01 object refs。
3. Illegal shadow writes and unmet cutover gate fail closed。
4. Duplicate/stale/rollback scenarios have deterministic fixtures。
5. No paid model/full-chain invocation is required to validate this contract。
