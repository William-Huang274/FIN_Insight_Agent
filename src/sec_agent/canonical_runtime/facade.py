from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from .feature_flags import FeatureFlagError, FeatureFlagRegistry
from .models import (
    ActorSnapshot,
    ArtifactVersionEnvelope,
    Attempt,
    AttemptState,
    CaseControlSummaryVersion,
    CaseStatus,
    CommandEnvelope,
    CompileTimeGapVersion,
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EventEnvelope,
    EvidenceSlotVersion,
    InstitutionalResearchCase,
    LegacyTaskRunBinding,
    PlanningCheckpointVersion,
    ResultEnvelope,
    WorkUnit,
    WorkUnitState,
    canonical_digest,
    utc_now,
)
from .planning_service import (
    DecisionCellSeed,
    P02_4_COMPILER_POLICY_REF,
    P02_4_CONTRACT_DIGEST,
    P02_4_FIXED_CELL_SEEDS,
    P02_4_PACK_SELECTION_REF,
)
from .protocols import CanonicalObjectStore, CanonicalStore, CanonicalTransaction
from .store import IdempotencyConflict, KillSwitchEnabled, StaleStateVersion, TransactionConflict


FLAG_ID = "decision_surface_shadow_v0_1"
MAX_CHECKPOINT_SNAPSHOT_BYTES = 262_144
LEGAL_WORK_UNIT_TRANSITIONS = {
    WorkUnitState.PENDING.value: {WorkUnitState.RUNNING.value, WorkUnitState.CANCELLED.value},
    WorkUnitState.RUNNING.value: {
        WorkUnitState.RETRYABLE_FAILED.value,
        WorkUnitState.SUCCEEDED.value,
        WorkUnitState.FAILED.value,
        WorkUnitState.CANCELLED.value,
    },
    WorkUnitState.RETRYABLE_FAILED.value: {WorkUnitState.RUNNING.value, WorkUnitState.CANCELLED.value},
    WorkUnitState.SUCCEEDED.value: set(),
    WorkUnitState.FAILED.value: {WorkUnitState.DEAD_LETTERED.value},
    WorkUnitState.DEAD_LETTERED.value: set(),
    WorkUnitState.CANCELLED.value: set(),
}


class RuntimeFacadeError(RuntimeError):
    error_code = "runtime_facade_error"

    def __init__(self, message: str | None = None, *, details: Mapping[str, Any] | None = None):
        super().__init__(message or self.error_code)
        self.details = dict(details or {})


class IllegalStateTransition(RuntimeFacadeError):
    error_code = "illegal_state_transition"


class LegacyBindingConflict(RuntimeFacadeError):
    error_code = "legacy_binding_conflict"


class MissingDependency(RuntimeFacadeError):
    error_code = "missing_dependency"


class ArtifactValidationError(RuntimeFacadeError):
    error_code = "artifact_validation_error"


class UnknownEventSchema(RuntimeFacadeError):
    error_code = "unknown_event_schema"


class StaleInputHead(RuntimeFacadeError):
    error_code = "stale_input_head"


class LeaseValidationError(RuntimeFacadeError):
    error_code = "lease_validation_error"


class NoEligibleWorkUnit(RuntimeFacadeError):
    error_code = "scheduler_no_eligible_work_unit"


class PlanningVersionConflict(RuntimeFacadeError):
    error_code = "version_conflict"


class PlanningConflict(RuntimeFacadeError):
    error_code = "planning_conflict"


class PlanningNotFound(RuntimeFacadeError):
    error_code = "planning_not_found"


class PlanningAuthorityViolation(RuntimeFacadeError):
    error_code = "planning_authority_violation"


REPLAY_EVENT_TYPES = frozenset(
    {
        "RESEARCH_CASE_CREATED",
        "CASE_CONTROL_SUMMARY_ADVANCED",
        "LEGACY_TASK_RUN_BOUND",
        "WORK_UNIT_CREATED",
        "WORK_UNIT_STARTED",
        "WORK_UNIT_COMPLETED",
        "WORK_UNIT_FAILED",
        "WORK_UNIT_CANCELLED",
        "ATTEMPT_STARTED",
        "ATTEMPT_COMPLETED",
        "ATTEMPT_FAILED",
        "SCHEDULER_LEASE_ACQUIRED",
        "SCHEDULER_LEASE_HEARTBEAT_RECORDED",
        "SCHEDULER_LEASE_RECLAIMED",
        "RECOVERY_RETRY_SCHEDULED",
        "RECOVERY_RESUME_SCHEDULED",
        "RECOVERY_FORK_CREATED",
        "RECOVERY_DEAD_LETTERED",
        "ARTIFACT_VERSION_CREATED",
        "CHECKPOINT_VERSION_CREATED",
        "DECISION_SURFACE_COMPILED",
        "DECISION_SURFACE_VALIDATION_FAILED",
        "EVIDENCE_FIXTURE_COMPILED",
        "EVIDENCE_CANDIDATE_REJECTED",
        "EVIDENCE_REPAIR_REQUESTED",
        "EVIDENCE_REPAIR_COMPLETED",
        "NUMERIC_FIXTURE_COMPILED",
        "WORKPAPER_FIXTURE_COMPILED",
        "LEAD_REVIEW_COMPLETED",
        "DELIVERABLE_PREVIEW_COMPILED",
        "DELIVERABLE_REVIEW_RECORDED",
        "TRACE_MANIFEST_COMPILED",
        "SHADOW_COMPARISON_RECORDED",
        "SHADOW_CALIBRATION_REVIEW_SUBMITTED",
        "PLANNING_CUTOVER_REQUESTED",
        "PLANNING_CUTOVER_DECIDED",
        "PLANNING_AUTHORITY_CHANGED",
        "PLANNING_ROLLBACK_EXECUTED",
        "STALE_WRITE_REJECTED",
    }
)


class RuntimeFacade:
    """M0 application boundary. It is a shadow control kernel, not a research runtime."""

    def __init__(
        self,
        store: CanonicalStore,
        object_store: CanonicalObjectStore,
        flags: FeatureFlagRegistry,
        *,
        mode: str = "off",
        grants: set[str] | frozenset[str] = frozenset(),
        planning_fixture_profile: Mapping[str, Any] | None = None,
    ):
        self.store = store
        self.object_store = object_store
        self.flags = flags
        self.mode = mode
        self.grants = frozenset(grants)
        self._planning_fixture_profiles: dict[str, dict[str, Any]] = {
            P02_4_COMPILER_POLICY_REF: {
                "compiler_policy_ref": P02_4_COMPILER_POLICY_REF,
                "pack_selection_ref": P02_4_PACK_SELECTION_REF,
                "contract_digest": P02_4_CONTRACT_DIGEST,
                "contract_ref": "configs/releases/point02_p02_4_vertical_contract_increment_v1_0.json",
                "cell_seeds": P02_4_FIXED_CELL_SEEDS,
            }
        }
        if planning_fixture_profile:
            planning = planning_fixture_profile.get("planning_profile")
            if not isinstance(planning, Mapping):
                raise ValueError("planning_fixture_profile_missing")
            compiler_policy_ref = str(planning.get("compiler_policy_ref") or "")
            pack_selection_ref = str(planning.get("pack_selection_ref") or "")
            raw_cells = planning.get("cells")
            if not compiler_policy_ref or not pack_selection_ref or not isinstance(raw_cells, Sequence):
                raise ValueError("planning_fixture_profile_invalid")
            normalized_cells = []
            for row in raw_cells:
                if not isinstance(row, Mapping):
                    raise ValueError("planning_fixture_cell_invalid")
                normalized_cells.append(
                    DecisionCellSeed.model_validate(
                        {
                            "cell_key": row.get("cell_key"),
                            "decision_question": row.get("decision_question"),
                            "origin_type": "vt4_p36_calibrated_fixture",
                            "owner_role": row.get("owner_role"),
                            "materiality": row.get("materiality"),
                            "stop_rule": row.get("stop_rule"),
                            "what_would_change": row.get("what_would_change", ""),
                            "dependency_cell_keys": row.get("dependency_cell_keys", ()),
                            "evidence_slots": row.get("evidence_slots", ()),
                        }
                    )
                )
            self._planning_fixture_profiles[compiler_policy_ref] = {
                "compiler_policy_ref": compiler_policy_ref,
                "pack_selection_ref": pack_selection_ref,
                "contract_digest": canonical_digest(planning_fixture_profile),
                "contract_ref": "configs/releases/fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json",
                "cell_seeds": tuple(normalized_cells),
            }

    def planning_fixture_contract_digest(
        self, compiler_policy_ref: str, pack_selection_ref: str
    ) -> str:
        return str(
            self._planning_fixture_profile(compiler_policy_ref, pack_selection_ref)[
                "contract_digest"
            ]
        )

    def planning_fixture_contract_digest_for_case(self, case_id: str) -> str:
        case = self.store.get_latest("canonical_research_cases", case_id)
        if not case:
            raise PlanningNotFound("case_not_found", details={"case_id": case_id})
        contract = self.store.get_latest(
            "canonical_decision_surface_contract_versions", self._p02_contract_id(case)
        )
        if not contract:
            raise PlanningNotFound("decision_surface_not_found", details={"case_id": case_id})
        compiler_policy_ref = str(contract.get("compiler_policy_ref") or "")
        profile = self._planning_fixture_profiles.get(compiler_policy_ref)
        if profile is None:
            raise PlanningAuthorityViolation("compiler_policy_ref_not_admitted")
        return str(profile["contract_digest"])

    def _planning_fixture_profile(
        self, compiler_policy_ref: str, pack_selection_ref: str
    ) -> Mapping[str, Any]:
        profile = self._planning_fixture_profiles.get(compiler_policy_ref)
        if profile is None:
            raise PlanningAuthorityViolation("compiler_policy_ref_not_admitted")
        if profile["pack_selection_ref"] != pack_selection_ref:
            raise PlanningAuthorityViolation("pack_selection_ref_not_admitted")
        return profile

    def create_research_case(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = command.case_id or str(command.payload.get("case_id") or f"case_{uuid4().hex}")
        task_run_id = str(command.payload.get("legacy_run_id") or "") or None
        scope_key, payload_digest, reused = self._idempotency(command, case_id)
        if reused:
            return reused
        now = command.requested_at
        summary_id = str(command.payload.get("summary_version_id") or f"summary_{uuid4().hex}")
        case = InstitutionalResearchCase(
            **self._scope(command, case_id=case_id),
            case_version=1,
            case_type=str(command.payload.get("case_type") or "deep_research"),
            created_from_task_ref=str(command.payload.get("legacy_task_id") or "manual_shadow_case"),
            case_control_summary_ref=summary_id,
            accountable_owner_ref=str(command.payload["accountable_owner_ref"]),
            planning_head_refs=(summary_id,),
            current_status=CaseStatus.SHADOW_CREATED,
        )
        summary = CaseControlSummaryVersion(
            **self._scope(command, case_id=case_id),
            summary_version_id=summary_id,
            summary_version=1,
            query=str(command.payload["query"]),
            as_of=self._datetime(command.payload.get("as_of"), fallback=now),
            universe=tuple(command.payload.get("universe") or ()),
            language=str(command.payload.get("language") or "zh-CN"),
            planning_authority="legacy",
            current_status="shadow_active",
        )
        binding = self._binding(command, case_id) if command.payload.get("legacy_task_id") else None
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.insert("canonical_research_cases", case_id, 1, case.model_dump(mode="json"))
            tx.insert("canonical_case_control_versions", summary_id, 1, summary.model_dump(mode="json"))
            if binding:
                self._ensure_binding_identity_available(tx, binding, case_id)
                tx.insert("canonical_task_run_bindings", binding.binding_id, 1, binding.model_dump(mode="json"))
            events = [
                self._event(
                    tx,
                    command,
                    "RESEARCH_CASE_CREATED",
                    {"case_id": case_id, "case_status": CaseStatus.SHADOW_CREATED.value},
                    task_run_id,
                )
            ]
            tx.append_event(events[-1])
            if binding:
                events.append(
                    self._event(
                        tx,
                        command,
                        "LEGACY_TASK_RUN_BOUND",
                        {"binding_id": binding.binding_id, "case_id": case_id},
                        task_run_id,
                    )
                )
                tx.append_event(events[-1])
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=0,
                state_version_after=1,
                event_ids=tuple(event.event_id for event in events),
                projection_refs=(case_id, summary_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def create_work_unit(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or f"wu_{uuid4().hex}")
        inputs = tuple(command.payload.get("input_version_refs") or ())
        work_unit = WorkUnit(
            **self._scope(command, case_id=case_id),
            work_unit_id=work_unit_id,
            work_unit_version=1,
            state_version=0,
            work_unit_type=str(command.payload.get("work_unit_type") or "decision_surface_compile"),
            target_refs=tuple(command.payload.get("target_refs") or (case_id,)),
            input_version_refs=inputs,
            input_version_set_digest=canonical_digest(inputs),
            expected_state_version=0,
            state=WorkUnitState.PENDING,
            budget_ref=str(command.payload.get("budget_ref") or "budget:none"),
            idempotency_key=command.idempotency_key,
            max_attempts=int(command.payload.get("max_attempts") or 1),
            retry_budget=int(command.payload.get("retry_budget") or 0),
            retry_policy_ref=str(command.payload.get("retry_policy_ref") or "retry:none"),
            retryable_failure_types=tuple(str(value) for value in command.payload.get("retryable_failure_types", ())),
            poison_failure_types=tuple(str(value) for value in command.payload.get("poison_failure_types", ("poison",))),
            queue_name=str(command.payload.get("queue_name") or "point01.default"),
            queue_priority=int(command.payload.get("queue_priority") or 0),
            queued_at=command.requested_at,
            input_head_digest=canonical_digest(inputs),
            current_status=WorkUnitState.PENDING.value,
        )
        return self._single_object_command(
            command,
            table="canonical_work_units",
            logical_id=work_unit_id,
            version=1,
            model=work_unit,
            event_type="WORK_UNIT_CREATED",
            work_unit_id=work_unit_id,
        )

    def start_attempt(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        attempt_id = str(command.payload.get("attempt_id") or f"attempt_{uuid4().hex}")
        scope_key, payload_digest, reused = self._idempotency(command, attempt_id)
        if reused:
            return reused
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
            current = tx.get_latest("canonical_work_units", work_unit_id)
            if not current:
                raise MissingDependency("work_unit_not_found")
            retrying = current["state"] == WorkUnitState.RETRYABLE_FAILED.value
            if current["state"] != WorkUnitState.PENDING.value and not retrying:
                raise IllegalStateTransition("work_unit_must_be_pending_or_retryable_failed")
            prior_attempts = [row for row in tx.list_latest("canonical_attempts", case_id=case_id) if row["work_unit_id"] == work_unit_id]
            attempt_no = int(command.payload.get("attempt_no") or (max((int(row["attempt_no"]) for row in prior_attempts), default=0) + 1))
            expected_attempt_no = max((int(row["attempt_no"]) for row in prior_attempts), default=0) + 1
            if attempt_no != expected_attempt_no:
                raise IllegalStateTransition("attempt_no_must_be_next_immutable_sequence")
            if attempt_no > int(current.get("max_attempts", 1)) or (
                retrying and int(current.get("retry_count", 0)) >= int(current.get("retry_budget", 0))
            ):
                raise IllegalStateTransition("retry_budget_or_max_attempts_exhausted")
            lease_duration_seconds = int(command.payload.get("lease_duration_seconds") or 60)
            if not 1 <= lease_duration_seconds <= 3600:
                raise LeaseValidationError("lease_duration_seconds_out_of_range")
            updated = WorkUnit.model_validate(
                {**current, "state": WorkUnitState.RUNNING.value, "current_status": "running", "state_version": int(current.get("state_version", 0)) + 1, "retry_count": int(current.get("retry_count", 0)) + (1 if retrying else 0)}
            )
            attempt = Attempt(
                **self._scope(command, case_id=case_id),
                attempt_id=attempt_id,
                attempt_no=attempt_no,
                work_unit_id=work_unit_id,
                work_unit_version=updated.work_unit_version,
                state=AttemptState.RUNNING,
                worker_ref=str(command.payload.get("worker_ref") or "local_fixture_worker"),
                model_ref=command.payload.get("model_ref"),
                tool_refs=tuple(command.payload.get("tool_refs") or ()),
                started_at=command.requested_at,
                input_refs=updated.input_version_refs,
                input_head_digest=updated.input_head_digest,
                lease_owner_ref=str(command.payload.get("lease_owner_ref") or command.payload.get("worker_ref") or "local_fixture_worker"),
                lease_expires_at=command.requested_at + timedelta(seconds=lease_duration_seconds),
                current_status="running",
            )
            tx.insert("canonical_work_units", work_unit_id, updated.work_unit_version, updated.model_dump(mode="json"))
            tx.insert("canonical_attempts", attempt_id, attempt.attempt_no, attempt.model_dump(mode="json"))
            events = []
            events.append(self._event(tx, command, "WORK_UNIT_STARTED", {"work_unit_id": work_unit_id, "attempt_no": attempt_no}, work_unit_id=work_unit_id))
            tx.append_event(events[-1])
            events.append(self._event(tx, command, "ATTEMPT_STARTED", {"attempt_id": attempt_id, "attempt_no": attempt_no, "input_head_digest": updated.input_head_digest}, work_unit_id=work_unit_id, attempt_id=attempt_id))
            tx.append_event(events[-1])
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=0,
                state_version_after=1,
                event_ids=tuple(event.event_id for event in events),
                projection_refs=(work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def claim_next_scheduled_attempt(self, command: CommandEnvelope) -> ResultEnvelope:
        """Atomically lease one queued WorkUnit; this is a control-plane operation, not a worker loop."""
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        worker_ref = str(command.payload.get("worker_ref") or "")
        if not worker_ref:
            raise LeaseValidationError("worker_ref_required")
        queue_name = str(command.payload.get("queue_name") or "point01.default")
        lease_duration_seconds = self._lease_duration(command)
        requested_work_unit_id = command.payload.get("work_unit_id")
        scope_key = f"{command.tenant_id}:{command.command_type}:{case_id}:{worker_ref}:{command.idempotency_key}"
        payload_digest = canonical_digest(command.payload)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            self._require_case_row(tx, command, case_id)
            candidates = [
                row
                for row in tx.list_latest("canonical_work_units", case_id=case_id)
                if row.get("queue_name", "point01.default") == queue_name
                and row.get("state") in {WorkUnitState.PENDING.value, WorkUnitState.RETRYABLE_FAILED.value}
            ]
            if requested_work_unit_id:
                current = self._require_case_row(
                    tx, command, case_id, table="canonical_work_units", logical_id=str(requested_work_unit_id)
                )
                if current.get("queue_name", "point01.default") != queue_name:
                    raise NoEligibleWorkUnit("work_unit_queue_mismatch")
                if current.get("state") == WorkUnitState.RUNNING.value:
                    raise LeaseValidationError("scheduler_lease_already_active")
                if current.get("state") not in {WorkUnitState.PENDING.value, WorkUnitState.RETRYABLE_FAILED.value}:
                    raise NoEligibleWorkUnit("work_unit_not_schedulable")
            else:
                if not candidates:
                    raise NoEligibleWorkUnit("scheduler_queue_empty")
                current = sorted(
                    candidates,
                    key=lambda row: (
                        -int(row.get("queue_priority") or 0),
                        str(row.get("queued_at") or row.get("created_at") or ""),
                        str(row.get("work_unit_id") or ""),
                    ),
                )[0]
            work_unit_id = str(current["work_unit_id"])
            retrying = current["state"] == WorkUnitState.RETRYABLE_FAILED.value
            prior_attempts = [
                row for row in tx.list_latest("canonical_attempts", case_id=case_id) if row["work_unit_id"] == work_unit_id
            ]
            recovery_mode = str(command.payload.get("recovery_mode") or "") or None
            recovery_parent_attempt_id = str(command.payload.get("recovery_parent_attempt_id") or "") or None
            resume_checkpoint_ref = str(command.payload.get("resume_checkpoint_ref") or "") or None
            replay_plan_digest = str(command.payload.get("replay_plan_digest") or "") or None
            if recovery_mode:
                if recovery_mode not in {"retry", "resume"}:
                    raise IllegalStateTransition("unsupported_recovery_mode")
                if not retrying:
                    raise IllegalStateTransition("recovery_claim_requires_retryable_failed")
                tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
                if not recovery_parent_attempt_id:
                    raise MissingDependency("recovery_parent_attempt_id_required")
                if not replay_plan_digest:
                    raise MissingDependency("recovery_replay_plan_digest_required")
                parent_attempt = next((row for row in prior_attempts if row["attempt_id"] == recovery_parent_attempt_id), None)
                if not parent_attempt or parent_attempt.get("state") != AttemptState.FAILED.value:
                    raise MissingDependency("recovery_parent_attempt_invalid")
                if recovery_mode == "resume":
                    resume_checkpoint_ref = self._validate_recovery_checkpoint(
                        tx,
                        command,
                        case_id=case_id,
                        checkpoint_ref=resume_checkpoint_ref,
                        parent_attempt_id=recovery_parent_attempt_id,
                    )
                elif resume_checkpoint_ref:
                    raise IllegalStateTransition("retry_must_not_include_checkpoint_ref")
            attempt_no = max((int(row["attempt_no"]) for row in prior_attempts), default=0) + 1
            if attempt_no > int(current.get("max_attempts", 1)) or (
                retrying and int(current.get("retry_count", 0)) >= int(current.get("retry_budget", 0))
            ):
                raise IllegalStateTransition("retry_budget_or_max_attempts_exhausted")
            fencing_token = max((int(row.get("lease_fencing_token") or 0) for row in prior_attempts), default=0) + 1
            state_before = int(current.get("state_version", 0))
            updated = WorkUnit.model_validate(
                {
                    **current,
                    "state": WorkUnitState.RUNNING.value,
                    "current_status": "running",
                    "state_version": state_before + 1,
                    "retry_count": int(current.get("retry_count", 0)) + (1 if retrying else 0),
                    "latest_scheduler_fencing_token": fencing_token,
                }
            )
            attempt_id = str(command.payload.get("attempt_id") or f"attempt_{uuid4().hex}")
            attempt = Attempt(
                **self._scope(command, case_id=case_id),
                attempt_id=attempt_id,
                attempt_no=attempt_no,
                work_unit_id=work_unit_id,
                work_unit_version=updated.work_unit_version,
                state=AttemptState.RUNNING,
                worker_ref=worker_ref,
                model_ref=command.payload.get("model_ref"),
                tool_refs=tuple(command.payload.get("tool_refs") or ()),
                started_at=command.requested_at,
                input_refs=updated.input_version_refs,
                input_head_digest=updated.input_head_digest,
                lease_owner_ref=worker_ref,
                lease_expires_at=command.requested_at + timedelta(seconds=lease_duration_seconds),
                scheduler_managed=True,
                lease_fencing_token=fencing_token,
                lease_heartbeat_at=command.requested_at,
                recovery_mode=recovery_mode,
                recovery_parent_attempt_id=recovery_parent_attempt_id,
                resume_checkpoint_ref=resume_checkpoint_ref,
                replay_plan_digest=replay_plan_digest,
                current_status="running",
            )
            tx.insert("canonical_work_units", work_unit_id, updated.work_unit_version, updated.model_dump(mode="json"))
            tx.insert("canonical_attempts", attempt_id, attempt.attempt_no, attempt.model_dump(mode="json"))
            event_command = command.model_copy(update={"expected_state_version": state_before})
            events = [
                self._event(
                    tx,
                    event_command,
                    "WORK_UNIT_STARTED",
                    {"work_unit_id": work_unit_id, "attempt_no": attempt_no, "queue_name": queue_name},
                    work_unit_id=work_unit_id,
                ),
                self._event(
                    tx,
                    event_command,
                    "ATTEMPT_STARTED",
                    {
                        "attempt_id": attempt_id,
                        "attempt_no": attempt_no,
                        "input_head_digest": updated.input_head_digest,
                        "scheduler_managed": True,
                    },
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                ),
                self._event(
                    tx,
                    event_command,
                    "SCHEDULER_LEASE_ACQUIRED",
                    self._lease_event_payload(attempt, queue_name=queue_name),
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                ),
            ]
            if recovery_mode:
                events.append(
                    self._event(
                        tx,
                        event_command,
                        "RECOVERY_RETRY_SCHEDULED" if recovery_mode == "retry" else "RECOVERY_RESUME_SCHEDULED",
                        {
                            "work_unit_id": work_unit_id,
                            "attempt_id": attempt_id,
                            "recovery_parent_attempt_id": recovery_parent_attempt_id,
                            "resume_checkpoint_ref": resume_checkpoint_ref,
                            "replay_plan_digest": replay_plan_digest,
                        },
                        work_unit_id=work_unit_id,
                        attempt_id=attempt_id,
                    )
                )
            for event in events:
                tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=state_before,
                state_version_after=state_before + 1,
                event_ids=tuple(event.event_id for event in events),
                projection_refs=(work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def heartbeat_scheduled_attempt_lease(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        attempt_id = str(command.payload["attempt_id"])
        worker_ref = str(command.payload.get("worker_ref") or "")
        if not worker_ref:
            raise LeaseValidationError("worker_ref_required")
        lease_duration_seconds = self._lease_duration(command)
        scope_key, payload_digest, _ = self._idempotency(command, attempt_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
            work_unit, attempt = self._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            if not attempt.get("scheduler_managed"):
                raise LeaseValidationError("scheduler_managed_lease_required")
            attempt_before = int(attempt.get("state_version", 0))
            renewed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": attempt_before + 1,
                    "lease_owner_ref": worker_ref,
                    "lease_expires_at": command.requested_at + timedelta(seconds=lease_duration_seconds),
                    "lease_heartbeat_at": command.requested_at,
                }
            )
            tx.insert("canonical_attempts", attempt_id, renewed_attempt.attempt_no, renewed_attempt.model_dump(mode="json"))
            event = self._event(
                tx,
                command.model_copy(update={"expected_state_version": attempt_before}),
                "SCHEDULER_LEASE_HEARTBEAT_RECORDED",
                self._lease_event_payload(renewed_attempt, queue_name=str(work_unit.get("queue_name") or "point01.default")),
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=attempt_before,
                state_version_after=attempt_before + 1,
                event_ids=(event.event_id,),
                projection_refs=(work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def reclaim_expired_scheduled_attempt_lease(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        attempt_id = str(command.payload["attempt_id"])
        new_worker_ref = str(command.payload.get("worker_ref") or "")
        if not new_worker_ref:
            raise LeaseValidationError("worker_ref_required")
        lease_duration_seconds = self._lease_duration(command)
        scope_key, payload_digest, _ = self._idempotency(command, attempt_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
            work_unit = self._require_case_row(tx, command, case_id, table="canonical_work_units", logical_id=work_unit_id)
            attempt = self._require_case_row(tx, command, case_id, table="canonical_attempts", logical_id=attempt_id)
            if work_unit.get("state") != WorkUnitState.RUNNING.value or attempt.get("state") != AttemptState.RUNNING.value:
                raise IllegalStateTransition("scheduler_reclaim_requires_running_execution")
            if attempt.get("work_unit_id") != work_unit_id or not attempt.get("scheduler_managed"):
                raise LeaseValidationError("scheduler_managed_lease_required")
            expires_at = self._datetime(attempt.get("lease_expires_at"), fallback=command.requested_at)
            if expires_at > command.requested_at:
                raise LeaseValidationError("attempt_lease_not_expired")
            work_unit_before = int(work_unit.get("state_version", 0))
            attempt_before = int(attempt.get("state_version", 0))
            old_owner = str(attempt.get("lease_owner_ref") or "")
            next_token = int(attempt.get("lease_fencing_token") or 0) + 1
            reclaimed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": work_unit_before + 1,
                    "latest_scheduler_fencing_token": next_token,
                }
            )
            reclaimed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": attempt_before + 1,
                    "worker_ref": new_worker_ref,
                    "lease_owner_ref": new_worker_ref,
                    "lease_expires_at": command.requested_at + timedelta(seconds=lease_duration_seconds),
                    "lease_fencing_token": next_token,
                    "lease_heartbeat_at": command.requested_at,
                    "lease_reclaimed_at": command.requested_at,
                }
            )
            tx.insert("canonical_work_units", work_unit_id, reclaimed_work_unit.work_unit_version, reclaimed_work_unit.model_dump(mode="json"))
            tx.insert("canonical_attempts", attempt_id, reclaimed_attempt.attempt_no, reclaimed_attempt.model_dump(mode="json"))
            event = self._event(
                tx,
                command.model_copy(update={"expected_state_version": work_unit_before}),
                "SCHEDULER_LEASE_RECLAIMED",
                {
                    **self._lease_event_payload(reclaimed_attempt, queue_name=str(work_unit.get("queue_name") or "point01.default")),
                    "prior_lease_owner_ref": old_owner,
                    "work_unit_state_version_before": work_unit_before,
                    "work_unit_state_version_after": work_unit_before + 1,
                    "attempt_state_version_before": attempt_before,
                    "attempt_state_version_after": attempt_before + 1,
                },
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=work_unit_before,
                state_version_after=work_unit_before + 1,
                event_ids=(event.event_id,),
                projection_refs=(work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def bind_legacy_task_run(self, command: CommandEnvelope) -> ResultEnvelope:
        """Bind an existing Case to one legacy TaskRun without changing legacy authority."""
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        binding = self._binding(command, case_id)
        scope_key = f"{command.tenant_id}:{command.command_type}:{case_id}:{binding.binding_id}:{command.idempotency_key}"
        payload_digest = canonical_digest({"case_id": case_id, "payload": command.payload})
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            self._require_case_row(tx, command, case_id)
            self._ensure_binding_identity_available(tx, binding, case_id)
            tx.insert("canonical_task_run_bindings", binding.binding_id, binding.binding_version, binding.model_dump(mode="json"))
            event = self._event(
                tx,
                command,
                "LEGACY_TASK_RUN_BOUND",
                {"binding_id": binding.binding_id, "case_id": case_id},
                task_run_id=binding.legacy_run_id or None,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=0,
                state_version_after=1,
                event_ids=(event.event_id,),
                projection_refs=(binding.binding_id,),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def complete_attempt(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        attempt_id = str(command.payload["attempt_id"])
        output_refs = tuple(str(value) for value in command.payload.get("output_artifact_refs", ()))
        scope_key, payload_digest, _ = self._idempotency(command, attempt_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            work_unit, attempt = self._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            self._validate_output_artifacts(attempt_id, output_refs)
            completed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": int(attempt.get("state_version", 0)) + 1,
                    "state": AttemptState.SUCCEEDED.value,
                    "current_status": "succeeded",
                    "ended_at": command.requested_at,
                    "terminal_reason": str(command.payload.get("terminal_reason") or "completed"),
                    "output_refs": output_refs,
                }
            )
            completed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.SUCCEEDED.value,
                    "current_status": "succeeded",
                }
            )
            tx.insert("canonical_attempts", attempt_id, completed_attempt.attempt_no, completed_attempt.model_dump(mode="json"))
            tx.insert("canonical_work_units", work_unit_id, completed_work_unit.work_unit_version, completed_work_unit.model_dump(mode="json"))
            events = self._terminal_events(
                tx,
                command,
                attempt_event_type="ATTEMPT_COMPLETED",
                work_unit_event_type="WORK_UNIT_COMPLETED",
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                attempt_payload={"attempt_id": attempt_id, "output_refs": list(output_refs)},
            )
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=tuple(event.event_id for event in events),
                artifact_refs=output_refs,
                projection_refs=(work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def fail_attempt(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        attempt_id = str(command.payload["attempt_id"])
        failure_type = str(command.payload.get("failure_type") or "")
        if not failure_type:
            raise RuntimeFacadeError("failure_type_required", details={"error_code": "validation_error"})
        if "retryable" not in command.payload:
            raise RuntimeFacadeError("retryable_required", details={"error_code": "validation_error"})
        scope_key, payload_digest, _ = self._idempotency(command, attempt_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            work_unit, attempt = self._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            retryable = self._retry_permitted(work_unit, attempt, failure_type, bool(command.payload["retryable"]))
            failed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": int(attempt.get("state_version", 0)) + 1,
                    "state": AttemptState.FAILED.value,
                    "current_status": "failed",
                    "ended_at": command.requested_at,
                    "failure_type": failure_type,
                    "retryable": retryable,
                    "terminal_reason": str(command.payload.get("terminal_reason") or failure_type),
                }
            )
            failed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.RETRYABLE_FAILED.value if retryable else WorkUnitState.FAILED.value,
                    "current_status": "failed_retryable" if retryable else "failed",
                }
            )
            tx.insert("canonical_attempts", attempt_id, failed_attempt.attempt_no, failed_attempt.model_dump(mode="json"))
            tx.insert("canonical_work_units", work_unit_id, failed_work_unit.work_unit_version, failed_work_unit.model_dump(mode="json"))
            events = self._terminal_events(
                tx,
                command,
                attempt_event_type="ATTEMPT_FAILED",
                work_unit_event_type="WORK_UNIT_FAILED",
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                attempt_payload={
                    "attempt_id": attempt_id,
                    "failure_type": failure_type,
                    "retryable": retryable,
                },
                work_unit_payload={"retryable": retryable},
            )
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=tuple(event.event_id for event in events),
                projection_refs=(work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def cancel_work_unit(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        scope_key, payload_digest, _ = self._idempotency(command, work_unit_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
            work_unit = self._require_case_row(tx, command, case_id, table="canonical_work_units", logical_id=work_unit_id)
            if work_unit["state"] not in {WorkUnitState.PENDING.value, WorkUnitState.RUNNING.value, WorkUnitState.RETRYABLE_FAILED.value}:
                raise IllegalStateTransition("work_unit_must_be_pending_running_or_retryable_failed")
            running_attempts = [
                row
                for row in tx.list_latest("canonical_attempts", case_id=case_id)
                if row["work_unit_id"] == work_unit_id and row["state"] == AttemptState.RUNNING.value
            ]
            cancelled_attempt_ids: list[str] = []
            for attempt in running_attempts:
                cancelled = Attempt.model_validate(
                    {
                        **attempt,
                        "state_version": int(attempt.get("state_version", 0)) + 1,
                        "state": AttemptState.CANCELLED.value,
                        "current_status": "cancelled",
                        "ended_at": command.requested_at,
                        "terminal_reason": str(command.payload.get("terminal_reason") or "work_unit_cancelled"),
                    }
                )
                tx.insert("canonical_attempts", cancelled.attempt_id, cancelled.attempt_no, cancelled.model_dump(mode="json"))
                cancelled_attempt_ids.append(cancelled.attempt_id)
            cancelled_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.CANCELLED.value,
                    "current_status": "cancelled",
                }
            )
            tx.insert("canonical_work_units", work_unit_id, cancelled_work_unit.work_unit_version, cancelled_work_unit.model_dump(mode="json"))
            event = self._event(
                tx,
                command,
                "WORK_UNIT_CANCELLED",
                {"work_unit_id": work_unit_id, "cancelled_attempt_ids": cancelled_attempt_ids},
                work_unit_id=work_unit_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=(event.event_id,),
                projection_refs=(work_unit_id, *cancelled_attempt_ids),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def fork_recovery_work_unit(self, command: CommandEnvelope) -> ResultEnvelope:
        """Create a new queued WorkUnit with immutable failed-attempt/checkpoint lineage.

        This is deliberately a control-plane fork only.  It does not start a
        worker, materialize a checkpoint, or alter the source WorkUnit.
        """
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        source_work_unit_id = str(command.payload.get("source_work_unit_id") or "")
        source_attempt_id = str(command.payload.get("source_attempt_id") or "")
        checkpoint_ref = str(command.payload.get("checkpoint_ref") or "")
        work_unit_id = str(command.payload.get("work_unit_id") or f"wu_{uuid4().hex}")
        if not source_work_unit_id or not source_attempt_id:
            raise MissingDependency("recovery_fork_source_required")
        scope_key, payload_digest, _ = self._idempotency(command, work_unit_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            if tx.get_latest("canonical_work_units", work_unit_id):
                raise IllegalStateTransition("recovery_fork_work_unit_id_already_exists")
            tx.assert_expected_state("canonical_work_units", source_work_unit_id, command.expected_state_version)
            source = self._require_case_row(
                tx, command, case_id, table="canonical_work_units", logical_id=source_work_unit_id
            )
            parent_attempt = self._require_case_row(
                tx, command, case_id, table="canonical_attempts", logical_id=source_attempt_id
            )
            if parent_attempt.get("work_unit_id") != source_work_unit_id or parent_attempt.get("state") != AttemptState.FAILED.value:
                raise IllegalStateTransition("recovery_fork_parent_attempt_must_be_failed_source_attempt")
            checkpoint_ref = self._validate_recovery_checkpoint(
                tx,
                command,
                case_id=case_id,
                checkpoint_ref=checkpoint_ref,
                parent_attempt_id=source_attempt_id,
            )
            input_refs = tuple(dict.fromkeys((*source.get("input_version_refs", ()), checkpoint_ref)))
            forked = WorkUnit(
                **self._scope(command, case_id=case_id),
                work_unit_id=work_unit_id,
                work_unit_version=1,
                state_version=0,
                work_unit_type=str(command.payload.get("work_unit_type") or source["work_unit_type"]),
                target_refs=tuple(command.payload.get("target_refs") or source.get("target_refs") or (case_id,)),
                input_version_refs=input_refs,
                input_version_set_digest=canonical_digest(input_refs),
                expected_state_version=0,
                state=WorkUnitState.PENDING,
                budget_ref=str(command.payload.get("budget_ref") or source.get("budget_ref") or "budget:none"),
                idempotency_key=command.idempotency_key,
                max_attempts=int(command.payload["max_attempts"]) if "max_attempts" in command.payload else int(source.get("max_attempts") or 1),
                retry_budget=int(command.payload["retry_budget"]) if "retry_budget" in command.payload else int(source.get("retry_budget") or 0),
                retry_policy_ref=str(command.payload["retry_policy_ref"]) if "retry_policy_ref" in command.payload else str(source.get("retry_policy_ref") or "retry:none"),
                retryable_failure_types=tuple(command.payload["retryable_failure_types"]) if "retryable_failure_types" in command.payload else tuple(source.get("retryable_failure_types") or ()),
                poison_failure_types=tuple(command.payload["poison_failure_types"]) if "poison_failure_types" in command.payload else tuple(source.get("poison_failure_types") or ("poison",)),
                queue_name=str(command.payload.get("queue_name") or source.get("queue_name") or "point01.default"),
                queue_priority=int(command.payload.get("queue_priority") if "queue_priority" in command.payload else source.get("queue_priority", 0)),
                queued_at=command.requested_at,
                forked_from_work_unit_id=source_work_unit_id,
                forked_from_attempt_id=source_attempt_id,
                recovery_checkpoint_ref=checkpoint_ref,
                input_head_digest=canonical_digest(input_refs),
                current_status=WorkUnitState.PENDING.value,
            )
            tx.insert("canonical_work_units", work_unit_id, forked.work_unit_version, forked.model_dump(mode="json"))
            event_command = command.model_copy(update={"expected_state_version": 0})
            events = [
                self._event(
                    tx,
                    event_command,
                    "WORK_UNIT_CREATED",
                    {"work_unit_id": work_unit_id, "case_id": case_id, "state": WorkUnitState.PENDING.value},
                    work_unit_id=work_unit_id,
                ),
                self._event(
                    tx,
                    event_command,
                    "RECOVERY_FORK_CREATED",
                    {
                        "work_unit_id": work_unit_id,
                        "source_work_unit_id": source_work_unit_id,
                        "source_attempt_id": source_attempt_id,
                        "checkpoint_ref": checkpoint_ref,
                        "input_head_digest": forked.input_head_digest,
                    },
                    work_unit_id=work_unit_id,
                    attempt_id=source_attempt_id,
                ),
            ]
            for event in events:
                tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=0,
                state_version_after=1,
                event_ids=tuple(event.event_id for event in events),
                projection_refs=(work_unit_id, source_work_unit_id, source_attempt_id, checkpoint_ref),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def dead_letter_work_unit(self, command: CommandEnvelope) -> ResultEnvelope:
        """Close an exhausted or poison WorkUnit without admitting another attempt."""
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        source_attempt_id = str(command.payload.get("source_attempt_id") or "")
        reason = str(command.payload.get("dead_letter_reason") or "").strip()
        if not work_unit_id or not source_attempt_id or not reason:
            raise MissingDependency("dead_letter_work_unit_attempt_and_reason_required")
        scope_key, payload_digest, _ = self._idempotency(command, work_unit_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
            work_unit = self._require_case_row(
                tx, command, case_id, table="canonical_work_units", logical_id=work_unit_id
            )
            attempt = self._require_case_row(
                tx, command, case_id, table="canonical_attempts", logical_id=source_attempt_id
            )
            if work_unit.get("state") != WorkUnitState.FAILED.value:
                raise IllegalStateTransition("dead_letter_requires_terminal_failed_work_unit")
            if attempt.get("work_unit_id") != work_unit_id or attempt.get("state") != AttemptState.FAILED.value:
                raise IllegalStateTransition("dead_letter_requires_failed_source_attempt")
            dead_lettered = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.DEAD_LETTERED.value,
                    "current_status": WorkUnitState.DEAD_LETTERED.value,
                    "dead_letter_reason": reason,
                    "dead_lettered_at": command.requested_at,
                }
            )
            tx.insert("canonical_work_units", work_unit_id, dead_lettered.work_unit_version, dead_lettered.model_dump(mode="json"))
            event = self._event(
                tx,
                command,
                "RECOVERY_DEAD_LETTERED",
                {
                    "work_unit_id": work_unit_id,
                    "source_attempt_id": source_attempt_id,
                    "dead_letter_reason": reason,
                    "retry_count": dead_lettered.retry_count,
                    "retry_budget": dead_lettered.retry_budget,
                },
                work_unit_id=work_unit_id,
                attempt_id=source_attempt_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=(event.event_id,),
                projection_refs=(work_unit_id, source_attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def create_checkpoint_version(
        self,
        command: CommandEnvelope,
        *,
        checkpoint_mutation_guard: Callable[[CanonicalTransaction], None] | None = None,
        checkpoint_mutation_finalizer: Callable[[CanonicalTransaction, str], None] | None = None,
    ) -> ResultEnvelope:
        """Persist one immutable checkpoint artifact and its event in one canonical transaction.

        The filesystem object is content-addressed.  Only the canonical artifact
        row plus its event makes it a recoverable checkpoint; a physical object
        left behind by an aborted transaction is intentionally unreferenced.
        """
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        checkpoint_id = str(command.payload.get("checkpoint_id") or "")
        checkpoint_schema_ref = str(command.payload.get("checkpoint_schema_ref") or "")
        snapshot = command.payload.get("snapshot")
        if not work_unit_id or not attempt_id or not checkpoint_id or not checkpoint_schema_ref:
            raise MissingDependency("checkpoint_work_unit_attempt_id_and_schema_required")
        if not isinstance(snapshot, Mapping):
            raise RuntimeFacadeError("checkpoint_snapshot_must_be_mapping")
        snapshot_bytes = len(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode())
        if snapshot_bytes > MAX_CHECKPOINT_SNAPSHOT_BYTES:
            raise RuntimeFacadeError(
                "checkpoint_snapshot_too_large",
                details={"maximum_bytes": MAX_CHECKPOINT_SNAPSHOT_BYTES, "actual_bytes": snapshot_bytes},
            )
        try:
            expected_checkpoint_version = int(command.payload.get("expected_checkpoint_version"))
        except (TypeError, ValueError) as exc:
            raise RuntimeFacadeError("expected_checkpoint_version_required") from exc
        if expected_checkpoint_version < 0:
            raise RuntimeFacadeError("expected_checkpoint_version_must_be_nonnegative")
        supplied_supersedes = str(command.payload.get("supersedes_version_id") or "") or None
        scope_key, payload_digest, _ = self._idempotency(command, checkpoint_id)
        with self.store.transaction() as tx:
            existing_result = tx.get_idempotency(scope_key)
            if existing_result:
                return self._reuse_or_conflict(existing_result, payload_digest)
            work_unit, attempt = self._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            if checkpoint_mutation_guard is not None:
                checkpoint_mutation_guard(tx)
            previous = tx.get_latest("canonical_artifact_versions", checkpoint_id)
            if previous and previous.get("artifact_type") != "runtime_checkpoint":
                raise IllegalStateTransition("checkpoint_id_collides_with_non_checkpoint_artifact")
            actual_checkpoint_version = int(previous.get("artifact_version") or 0) if previous else 0
            if actual_checkpoint_version != expected_checkpoint_version:
                raise StaleStateVersion(
                    f"stale_checkpoint_version:expected={expected_checkpoint_version}:actual={actual_checkpoint_version}"
                )
            expected_supersedes = str(previous.get("artifact_version_id")) if previous else None
            if supplied_supersedes != expected_supersedes:
                raise StaleStateVersion("checkpoint_supersession_parent_mismatch")
            checkpoint_version = actual_checkpoint_version + 1
            checkpoint_version_id = f"{checkpoint_id}:v{checkpoint_version}"
            checkpoint_state_digest = canonical_digest(snapshot)
            checkpoint_payload = {
                "checkpoint_schema_ref": checkpoint_schema_ref,
                "checkpoint_id": checkpoint_id,
                "checkpoint_version": checkpoint_version,
                "checkpoint_version_id": checkpoint_version_id,
                "case_id": case_id,
                "work_unit_id": work_unit_id,
                "producer_attempt_id": attempt_id,
                "input_head_digest": attempt["input_head_digest"],
                "checkpoint_state_digest": checkpoint_state_digest,
                "snapshot": dict(snapshot),
            }
            object_ref = self.object_store.put_json(
                checkpoint_payload,
                namespace="point01/checkpoints",
                artifact_type="runtime_checkpoint",
            )
            artifact = ArtifactVersionEnvelope(
                **self._scope(command, case_id=case_id),
                artifact_id=checkpoint_id,
                artifact_version_id=checkpoint_version_id,
                artifact_version=checkpoint_version,
                artifact_type="runtime_checkpoint",
                payload_business_owner="M5.3_checkpoint_artifact_owner",
                producer_attempt_id=attempt_id,
                input_refs=tuple(work_unit["input_version_refs"]),
                input_refs_digest=work_unit["input_version_set_digest"],
                object_key=str(object_ref["object_key"]),
                object_digest=str(object_ref["digest"]),
                byte_size=int(object_ref["byte_size"]),
                media_type=str(object_ref["media_type"]),
                checkpoint_schema_ref=checkpoint_schema_ref,
                checkpoint_state_digest=checkpoint_state_digest,
                checkpoint_sequence_no=checkpoint_version,
                supersedes_version_id=expected_supersedes,
                current_status="checkpoint_available",
            )
            tx.insert("canonical_artifact_versions", checkpoint_id, checkpoint_version, artifact.model_dump(mode="json"))
            event_command = command.model_copy(update={"expected_state_version": actual_checkpoint_version})
            event = self._event(
                tx,
                event_command,
                "CHECKPOINT_VERSION_CREATED",
                {
                    "checkpoint_id": checkpoint_id,
                    "checkpoint_version_id": checkpoint_version_id,
                    "checkpoint_version": checkpoint_version,
                    "supersedes_version_id": expected_supersedes,
                    "checkpoint_schema_ref": checkpoint_schema_ref,
                    "checkpoint_state_digest": checkpoint_state_digest,
                    "input_head_digest": attempt["input_head_digest"],
                },
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(event)
            if checkpoint_mutation_finalizer is not None:
                checkpoint_mutation_finalizer(tx, checkpoint_version_id)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=actual_checkpoint_version,
                state_version_after=checkpoint_version,
                event_ids=(event.event_id,),
                artifact_refs=(checkpoint_version_id,),
                projection_refs=(checkpoint_id, checkpoint_version_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def get_checkpoint_version(self, *, case_id: str, checkpoint_ref: str) -> dict[str, Any]:
        """Read one exact checkpoint version and verify its content-addressed snapshot."""
        checkpoint_id, checkpoint_version = self._parse_artifact_reference(checkpoint_ref, None)
        if not checkpoint_id or checkpoint_version is None:
            raise MissingDependency("checkpoint_exact_version_required")
        artifact = self.store.get_version("canonical_artifact_versions", checkpoint_id, checkpoint_version)
        if not artifact:
            raise MissingDependency("checkpoint_not_found", details={"checkpoint_ref": checkpoint_ref})
        if artifact.get("case_id") != case_id or artifact.get("artifact_version_id") != checkpoint_ref:
            raise MissingDependency("checkpoint_scope_or_identity_mismatch")
        payload = self._validate_checkpoint_artifact_payload(artifact)
        return {
            "scope": "Point01_M5_3_checkpoint_artifact_versioning_control_plane_only",
            "artifact": artifact,
            "snapshot": payload["snapshot"],
            "checkpoint_payload": payload,
            "worker_started": False,
            "model_call_count": 0,
            "external_call_count": 0,
        }

    def compile_decision_surface(self, command: CommandEnvelope) -> dict[str, Any]:
        """Compile one admitted deterministic P36 fixture without execution objects."""
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        profile = self._planning_fixture_profile(
            str(command.payload.get("compiler_policy_ref") or ""),
            str(command.payload.get("pack_selection_ref") or ""),
        )
        cell_seeds = tuple(profile["cell_seeds"])
        scope_key, payload_digest, _ = self._idempotency(command, case_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_planning_result(existing, payload_digest)
            case, summary = self._require_p02_planning_case(tx, command, case_id)
            self._assert_planning_version(
                "case_version",
                int(command.payload["expected_case_version"]),
                int(case["case_version"]),
            )
            self._assert_planning_version(
                "summary_version",
                int(command.payload["expected_summary_version"]),
                int(summary["summary_version"]),
            )
            contract_id = self._p02_contract_id(case)
            if tx.get_latest("canonical_decision_surface_contract_versions", contract_id):
                raise PlanningConflict("decision_surface_already_exists", details={"case_id": case_id})
            scope = self._scope(command, case_id=case_id)
            contract_version_id = f"{contract_id}:v1"
            cell_ids = {
                seed.cell_key: self._p02_cell_id(contract_id, seed.cell_key)
                for seed in cell_seeds
            }
            contract = DecisionSurfaceContractVersion(
                **scope,
                contract_id=contract_id,
                contract_version_id=contract_version_id,
                contract_version=1,
                query=str(summary["query"]),
                as_of=self._datetime(summary["as_of"], fallback=command.requested_at),
                universe=tuple(summary.get("universe") or ()),
                language=str(summary["language"]),
                sector_pack_refs=(str(profile["pack_selection_ref"]),),
                compiler_policy_ref=str(profile["compiler_policy_ref"]),
                required_cell_ids=tuple(cell_ids[seed.cell_key] for seed in cell_seeds),
                current_status="awaiting_review",
            )
            cells: list[DecisionSurfaceCellVersion] = []
            slots: list[EvidenceSlotVersion] = []
            for seed in cell_seeds:
                cell_id = cell_ids[seed.cell_key]
                cell_version_id = f"{cell_id}:v1"
                cell = DecisionSurfaceCellVersion(
                    **scope,
                    contract_version_id=contract_version_id,
                    cell_id=cell_id,
                    cell_version_id=cell_version_id,
                    cell_version=1,
                    decision_question=seed.decision_question,
                    origin_type=seed.origin_type,
                    owner_role=seed.owner_role,
                    materiality=seed.materiality,
                    stop_rule=seed.stop_rule,
                    what_would_change=seed.what_would_change,
                    current_status="awaiting_review",
                )
                cells.append(cell)
                for slot_seed in seed.evidence_slots:
                    slot_id = self._p02_slot_id(cell_id, slot_seed.evidence_role)
                    slots.append(
                        EvidenceSlotVersion(
                            **scope,
                            cell_version_id=cell_version_id,
                            evidence_slot_id=slot_id,
                            slot_version_id=f"{slot_id}:v1",
                            slot_version=1,
                            evidence_role=slot_seed.evidence_role,
                            entity_scope=slot_seed.entity_scope,
                            period_scope=slot_seed.period_scope,
                            metric_scope=slot_seed.metric_scope,
                            source_policy_ref=slot_seed.source_policy_ref,
                            forbidden_substitutions=slot_seed.forbidden_substitutions,
                            acceptance_role=slot_seed.acceptance_role,
                            required=slot_seed.required,
                            current_status="awaiting_review",
                        )
                    )
            checkpoint = self._p02_checkpoint(
                command,
                case_id=case_id,
                contract_id=contract_id,
                contract_version_id=contract_version_id,
                checkpoint_version=1,
                review_status="awaiting_review",
            )
            tx.insert(
                "canonical_decision_surface_contract_versions",
                contract.contract_id,
                contract.contract_version,
                contract.model_dump(mode="json"),
            )
            for cell in cells:
                tx.insert(
                    "canonical_decision_surface_cell_versions",
                    cell.cell_id,
                    cell.cell_version,
                    cell.model_dump(mode="json"),
                )
            for slot in slots:
                tx.insert(
                    "canonical_evidence_slot_versions",
                    slot.evidence_slot_id,
                    slot.slot_version,
                    slot.model_dump(mode="json"),
                )
            tx.insert(
                "canonical_planning_checkpoint_versions",
                checkpoint.checkpoint_id,
                checkpoint.checkpoint_version,
                checkpoint.model_dump(mode="json"),
            )
            view = self._decision_surface_view(contract, checkpoint, cells, slots)
            tx.put_idempotency(scope_key, payload_digest, view)
            return view

    def revise_decision_surface(self, command: CommandEnvelope) -> dict[str, Any]:
        """Append the next immutable contract, cell, slot and review checkpoint versions."""
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        changes = self._validate_p02_changes(command.payload.get("changes"))
        scope_key, payload_digest, _ = self._idempotency(command, case_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_planning_result(existing, payload_digest)
            case, _ = self._require_p02_planning_case(tx, command, case_id)
            self._assert_planning_version(
                "case_version",
                int(command.payload["expected_case_version"]),
                int(case["case_version"]),
            )
            contract_id = self._p02_contract_id(case)
            contract_row = tx.get_latest("canonical_decision_surface_contract_versions", contract_id)
            if not contract_row:
                raise PlanningNotFound("decision_surface_not_found", details={"case_id": case_id})
            checkpoint_id = self._p02_checkpoint_id(contract_id)
            checkpoint_row = tx.get_latest("canonical_planning_checkpoint_versions", checkpoint_id)
            if not checkpoint_row:
                raise PlanningNotFound("planning_checkpoint_not_found", details={"case_id": case_id})
            self._assert_planning_version(
                "decision_surface_contract_version",
                int(command.payload["expected_decision_surface_contract_version"]),
                int(contract_row["contract_version"]),
            )
            self._assert_planning_version(
                "checkpoint_version",
                int(command.payload["expected_checkpoint_version"]),
                int(checkpoint_row["checkpoint_version"]),
            )
            if checkpoint_row.get("contract_version_id") != contract_row.get("contract_version_id"):
                raise PlanningConflict("checkpoint_contract_head_mismatch")
            old_contract = DecisionSurfaceContractVersion.model_validate(contract_row)
            old_checkpoint = PlanningCheckpointVersion.model_validate(checkpoint_row)
            old_cells, old_slots = self._p02_child_rows(tx, old_contract)
            cells_by_id = {cell.cell_id: cell for cell in old_cells}
            unknown_cell_ids = sorted(set(changes) - set(cells_by_id))
            if unknown_cell_ids:
                raise PlanningConflict("revision_cell_not_found", details={"cell_ids": unknown_cell_ids})
            next_contract_version = old_contract.contract_version + 1
            next_contract_version_id = f"{contract_id}:v{next_contract_version}"
            scope = self._scope(command, case_id=case_id)
            contract = DecisionSurfaceContractVersion(
                **scope,
                contract_id=contract_id,
                contract_version_id=next_contract_version_id,
                contract_version=next_contract_version,
                query=old_contract.query,
                as_of=old_contract.as_of,
                universe=old_contract.universe,
                language=old_contract.language,
                universal_pack_refs=old_contract.universal_pack_refs,
                sector_pack_refs=old_contract.sector_pack_refs,
                report_type_pack_refs=old_contract.report_type_pack_refs,
                compiler_policy_ref=old_contract.compiler_policy_ref,
                required_cell_ids=old_contract.required_cell_ids,
                supersedes_version_id=old_contract.contract_version_id,
                current_status="awaiting_review",
            )
            slots_by_cell_version: dict[str, list[EvidenceSlotVersion]] = {}
            for slot in old_slots:
                slots_by_cell_version.setdefault(slot.cell_version_id, []).append(slot)
            cells: list[DecisionSurfaceCellVersion] = []
            slots: list[EvidenceSlotVersion] = []
            for cell_id in old_contract.required_cell_ids:
                old_cell = cells_by_id[cell_id]
                change = changes.get(cell_id, {})
                cell_version = old_cell.cell_version + 1
                cell_version_id = f"{cell_id}:v{cell_version}"
                cell = DecisionSurfaceCellVersion(
                    **scope,
                    contract_version_id=next_contract_version_id,
                    cell_id=cell_id,
                    cell_version_id=cell_version_id,
                    cell_version=cell_version,
                    decision_question=old_cell.decision_question,
                    origin_type=old_cell.origin_type,
                    owner_role=old_cell.owner_role,
                    materiality=old_cell.materiality,
                    dependency_cell_ids=old_cell.dependency_cell_ids,
                    stop_rule=str(change.get("stop_rule", old_cell.stop_rule)),
                    what_would_change=str(change.get("what_would_change", old_cell.what_would_change)),
                    supersedes_version_id=old_cell.cell_version_id,
                    current_status="awaiting_review",
                )
                cells.append(cell)
                for old_slot in slots_by_cell_version.get(old_cell.cell_version_id, []):
                    slot_version = old_slot.slot_version + 1
                    slots.append(
                        EvidenceSlotVersion(
                            **scope,
                            cell_version_id=cell_version_id,
                            evidence_slot_id=old_slot.evidence_slot_id,
                            slot_version_id=f"{old_slot.evidence_slot_id}:v{slot_version}",
                            slot_version=slot_version,
                            evidence_role=old_slot.evidence_role,
                            entity_scope=old_slot.entity_scope,
                            period_scope=old_slot.period_scope,
                            metric_scope=old_slot.metric_scope,
                            source_policy_ref=old_slot.source_policy_ref,
                            forbidden_substitutions=old_slot.forbidden_substitutions,
                            acceptance_role=old_slot.acceptance_role,
                            required=old_slot.required,
                            supersedes_version_id=old_slot.slot_version_id,
                            current_status="awaiting_review",
                        )
                    )
            checkpoint = self._p02_checkpoint(
                command,
                case_id=case_id,
                contract_id=contract_id,
                contract_version_id=next_contract_version_id,
                checkpoint_version=old_checkpoint.checkpoint_version + 1,
                review_status="awaiting_review",
                supersedes_version_id=old_checkpoint.checkpoint_version_id,
            )
            tx.insert(
                "canonical_decision_surface_contract_versions",
                contract.contract_id,
                contract.contract_version,
                contract.model_dump(mode="json"),
            )
            for cell in cells:
                tx.insert(
                    "canonical_decision_surface_cell_versions",
                    cell.cell_id,
                    cell.cell_version,
                    cell.model_dump(mode="json"),
                )
            for slot in slots:
                tx.insert(
                    "canonical_evidence_slot_versions",
                    slot.evidence_slot_id,
                    slot.slot_version,
                    slot.model_dump(mode="json"),
                )
            tx.insert(
                "canonical_planning_checkpoint_versions",
                checkpoint.checkpoint_id,
                checkpoint.checkpoint_version,
                checkpoint.model_dump(mode="json"),
            )
            view = self._decision_surface_view(contract, checkpoint, cells, slots)
            tx.put_idempotency(scope_key, payload_digest, view)
            return view

    def review_planning_checkpoint(self, command: CommandEnvelope) -> dict[str, Any]:
        """Append only the next accepted or returned planning checkpoint version."""
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        decision = str(command.payload.get("decision") or "")
        if decision not in {"accept", "return"}:
            raise PlanningAuthorityViolation("planning_checkpoint_decision_invalid")
        scope_key, payload_digest, _ = self._idempotency(command, case_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_planning_result(existing, payload_digest)
            case, _ = self._require_p02_planning_case(tx, command, case_id)
            self._assert_planning_version(
                "case_version",
                int(command.payload["expected_case_version"]),
                int(case["case_version"]),
            )
            contract_id = self._p02_contract_id(case)
            contract_row = tx.get_latest("canonical_decision_surface_contract_versions", contract_id)
            checkpoint_id = self._p02_checkpoint_id(contract_id)
            checkpoint_row = tx.get_latest("canonical_planning_checkpoint_versions", checkpoint_id)
            if not contract_row or not checkpoint_row:
                raise PlanningNotFound("decision_surface_not_found", details={"case_id": case_id})
            self._assert_planning_version(
                "decision_surface_contract_version",
                int(command.payload["expected_decision_surface_contract_version"]),
                int(contract_row["contract_version"]),
            )
            self._assert_planning_version(
                "checkpoint_version",
                int(command.payload["expected_checkpoint_version"]),
                int(checkpoint_row["checkpoint_version"]),
            )
            if checkpoint_row.get("contract_version_id") != contract_row.get("contract_version_id"):
                raise PlanningConflict("checkpoint_contract_head_mismatch")
            if checkpoint_row.get("review_status") != "awaiting_review":
                raise PlanningConflict("planning_checkpoint_not_awaiting_review")
            contract = DecisionSurfaceContractVersion.model_validate(contract_row)
            old_checkpoint = PlanningCheckpointVersion.model_validate(checkpoint_row)
            cells, slots = self._p02_child_rows(tx, contract)
            checkpoint = self._p02_checkpoint(
                command,
                case_id=case_id,
                contract_id=contract_id,
                contract_version_id=contract.contract_version_id,
                checkpoint_version=old_checkpoint.checkpoint_version + 1,
                review_status="accepted" if decision == "accept" else "returned",
                supersedes_version_id=old_checkpoint.checkpoint_version_id,
            )
            tx.insert(
                "canonical_planning_checkpoint_versions",
                checkpoint.checkpoint_id,
                checkpoint.checkpoint_version,
                checkpoint.model_dump(mode="json"),
            )
            view = self._decision_surface_view(contract, checkpoint, cells, slots)
            tx.put_idempotency(scope_key, payload_digest, view)
            return view

    def get_decision_surface(
        self,
        case_id: str,
        *,
        tenant_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return self.get_decision_surface_version(
            case_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )

    def get_decision_surface_version(
        self,
        case_id: str,
        *,
        contract_version: int | None = None,
        checkpoint_version: int | None = None,
        tenant_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Read one coherent P02.4 projection without execution or artifact tables."""
        self._authorize("point01_shadow_compiler")
        with self.store.transaction() as tx:
            case = tx.get_latest("canonical_research_cases", case_id)
            if not case or case.get("case_id") != case_id:
                raise PlanningNotFound("case_not_found", details={"case_id": case_id})
            if tenant_id is not None and case.get("tenant_id") != tenant_id:
                raise PlanningNotFound("case_not_found", details={"case_id": case_id})
            if project_id is not None and case.get("project_id") != project_id:
                raise PlanningNotFound("case_not_found", details={"case_id": case_id})
            self._assert_p02_fixture_case(case)
            summary = tx.get_latest(
                "canonical_case_control_versions",
                str(case["case_control_summary_ref"]),
            )
            if (
                not summary
                or summary.get("case_id") != case_id
                or summary.get("tenant_id") != case.get("tenant_id")
                or summary.get("project_id") != case.get("project_id")
            ):
                raise PlanningNotFound("case_summary_not_found", details={"case_id": case_id})
            if summary.get("planning_authority") != "legacy":
                raise PlanningAuthorityViolation("legacy_planning_authority_not_retained")
            contract_id = self._p02_contract_id(case)
            contract_row = (
                tx.get_version("canonical_decision_surface_contract_versions", contract_id, contract_version)
                if contract_version is not None
                else tx.get_latest("canonical_decision_surface_contract_versions", contract_id)
            )
            checkpoint_id = self._p02_checkpoint_id(contract_id)
            checkpoint_row = (
                tx.get_version("canonical_planning_checkpoint_versions", checkpoint_id, checkpoint_version)
                if checkpoint_version is not None
                else tx.get_latest("canonical_planning_checkpoint_versions", checkpoint_id)
            )
            if not contract_row or not checkpoint_row:
                raise PlanningNotFound("decision_surface_not_found", details={"case_id": case_id})
            if checkpoint_row.get("contract_version_id") != contract_row.get("contract_version_id"):
                raise PlanningConflict("checkpoint_contract_version_mismatch")
            contract = DecisionSurfaceContractVersion.model_validate(contract_row)
            checkpoint = PlanningCheckpointVersion.model_validate(checkpoint_row)
            cells, slots = self._p02_child_rows(tx, contract)
            return self._decision_surface_view(contract, checkpoint, cells, slots)

    def commit_decision_surface_bundle(self, command: CommandEnvelope) -> ResultEnvelope:
        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload["work_unit_id"])
        attempt_id = str(command.payload["attempt_id"])
        bundle = dict(command.payload["bundle"])
        contract = DecisionSurfaceContractVersion.model_validate(bundle["contract"])
        cells = [DecisionSurfaceCellVersion.model_validate(row) for row in bundle.get("cells", [])]
        slots = [EvidenceSlotVersion.model_validate(row) for row in bundle.get("slots", [])]
        gaps = [CompileTimeGapVersion.model_validate(row) for row in bundle.get("gaps", [])]
        if contract.case_id != case_id or any(row.case_id != case_id for row in [*cells, *slots, *gaps]):
            raise RuntimeFacadeError("bundle_case_scope_mismatch")
        artifact_payload: Mapping[str, Any] = bundle
        artifact_type = "decision_surface_contract_bundle"
        if "artifact_envelope" in command.payload:
            envelope = command.payload["artifact_envelope"]
            if not isinstance(envelope, Mapping):
                raise RuntimeFacadeError("artifact_envelope_must_be_mapping")
            if canonical_digest(envelope.get("bundle")) != canonical_digest(bundle):
                raise RuntimeFacadeError("artifact_envelope_bundle_mismatch")
            if envelope.get("planning_authority") != "shadow":
                raise RuntimeFacadeError("artifact_envelope_authority_violation")
            artifact_payload = envelope
            artifact_type = str(command.payload.get("artifact_type") or "decision_surface_artifact_envelope")
        object_ref = self.object_store.put_json(
            artifact_payload, namespace="point01/decision_surface", artifact_type=artifact_type
        )
        artifact_id = str(command.payload.get("artifact_id") or f"artifact_{uuid4().hex}")
        artifact_version_id = f"{artifact_id}:v1"
        scope_key, payload_digest, reused = self._idempotency(command, artifact_id)
        if reused:
            return reused
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            work_unit_row, attempt_row = self._require_running_execution(
                tx, command, case_id, work_unit_id, attempt_id
            )
            artifact = ArtifactVersionEnvelope(
                **self._scope(command, case_id=case_id),
                artifact_id=artifact_id,
                artifact_version_id=artifact_version_id,
                artifact_version=1,
                artifact_type=artifact_type,
                payload_business_owner="TECH_01",
                producer_attempt_id=attempt_id,
                input_refs=tuple(work_unit_row["input_version_refs"]),
                input_refs_digest=work_unit_row["input_version_set_digest"],
                object_key=str(object_ref["object_key"]),
                object_digest=str(object_ref["digest"]),
                byte_size=int(object_ref["byte_size"]),
                media_type=str(object_ref["media_type"]),
                current_status="shadow_current",
            )
            tx.insert("canonical_artifact_versions", artifact_id, 1, artifact.model_dump(mode="json"))
            tx.insert("canonical_decision_surface_contract_versions", contract.contract_id, contract.contract_version, contract.model_dump(mode="json"))
            for row in cells:
                tx.insert("canonical_decision_surface_cell_versions", row.cell_id, row.cell_version, row.model_dump(mode="json"))
            for row in slots:
                tx.insert("canonical_evidence_slot_versions", row.evidence_slot_id, row.slot_version, row.model_dump(mode="json"))
            for row in gaps:
                tx.insert("canonical_compile_gap_versions", row.gap_id, row.gap_version, row.model_dump(mode="json"))
            completed_attempt = Attempt.model_validate(
                {
                    **attempt_row,
                    "state_version": int(attempt_row.get("state_version", 0)) + 1,
                    "state": AttemptState.SUCCEEDED.value,
                    "current_status": "succeeded",
                    "ended_at": command.requested_at,
                    "terminal_reason": "decision_surface_bundle_committed",
                    "output_refs": [artifact_version_id],
                }
            )
            completed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit_row,
                    "state": WorkUnitState.SUCCEEDED.value,
                    "current_status": "succeeded",
                    "state_version": command.expected_state_version + 1,
                }
            )
            tx.insert("canonical_attempts", attempt_id, completed_attempt.attempt_no, completed_attempt.model_dump(mode="json"))
            tx.insert("canonical_work_units", work_unit_id, completed_work_unit.work_unit_version, completed_work_unit.model_dump(mode="json"))
            event_specs = (
                ("ARTIFACT_VERSION_CREATED", {"artifact_version_id": artifact_version_id}),
                ("DECISION_SURFACE_COMPILED", {"contract_version_id": contract.contract_version_id}),
                ("ATTEMPT_COMPLETED", {"attempt_id": attempt_id, "output_refs": [artifact_version_id]}),
                ("WORK_UNIT_COMPLETED", {"work_unit_id": work_unit_id}),
            )
            events = []
            for event_type, event_payload in event_specs:
                events.append(
                    self._event(
                        tx,
                        command,
                        event_type,
                        event_payload,
                        work_unit_id=work_unit_id,
                        attempt_id=attempt_id,
                    )
                )
                tx.append_event(events[-1])
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=tuple(event.event_id for event in events),
                artifact_refs=(artifact_version_id,),
                projection_refs=(contract.contract_version_id,),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def list_events(self, task_run_id: str | None = None) -> Sequence[Mapping[str, Any]]:
        return self.store.list_events(task_run_id)

    def recover_case_execution(self, case_id: str) -> dict[str, Any]:
        """Read-only recovery check for a persisted canonical Case."""
        view = self.get_case_execution_view(case_id)
        store_recovery = self.store.recovery_check()
        verified_artifacts: list[str] = []
        for artifact in view["artifact_status"]:
            artifact_ref = str(artifact["artifact_version_id"])
            if artifact.get("artifact_type") == "runtime_checkpoint":
                self.get_checkpoint_version(case_id=case_id, checkpoint_ref=artifact_ref)
            else:
                self.get_artifact_version(artifact_ref, include_payload=True)
            verified_artifacts.append(str(artifact["artifact_version_id"]))
        projection = self.replay_projection()
        return {
            "case_id": case_id,
            "status": "pass" if store_recovery["status"] == "pass" else "fail",
            "store_recovery": store_recovery,
            "verified_artifact_version_ids": tuple(verified_artifacts),
            "projection_digest": projection["projection_digest"],
            "planning_authority": view["planning_authority"],
            "external_call_count": projection["external_call_count"],
        }

    def get_case_execution_view(self, case_id: str) -> dict[str, Any]:
        """Read-only execution view with authority sourced from the Case control summary."""
        case = self.store.get_latest("canonical_research_cases", case_id)
        if not case:
            raise MissingDependency("case_not_found", details={"case_id": case_id})
        planning_authority = self._planning_authority_for_case(case)
        bindings = self.store.list_latest("canonical_task_run_bindings", case_id=case_id)
        work_units = self.store.list_latest("canonical_work_units", case_id=case_id)
        attempts = self.store.list_latest("canonical_attempts", case_id=case_id)
        artifacts = self.store.list_latest("canonical_artifact_versions", case_id=case_id)
        running = [row["work_unit_id"] for row in work_units if row["state"] == WorkUnitState.RUNNING.value]
        paused = [row["work_unit_id"] for row in work_units if row["state"] == WorkUnitState.PAUSED.value]
        retry_pending = [row["work_unit_id"] for row in work_units if row["state"] == WorkUnitState.RETRYABLE_FAILED.value]
        terminal = [
            row["work_unit_id"]
            for row in work_units
            if row["state"]
            in {
                WorkUnitState.SUCCEEDED.value,
                WorkUnitState.FAILED.value,
                WorkUnitState.DEAD_LETTERED.value,
                WorkUnitState.CANCELLED.value,
            }
        ]
        artifact_status = [
            {
                "artifact_version_id": row["artifact_version_id"],
                "producer_attempt_id": row["producer_attempt_id"],
                "status": row["current_status"],
                "digest": row["object_digest"],
                "artifact_type": row["artifact_type"],
                "supersedes_version_id": row.get("supersedes_version_id"),
                "checkpoint_state_digest": row.get("checkpoint_state_digest"),
            }
            for row in artifacts
        ]
        return {
            "case": case,
            "legacy_bindings": bindings,
            "work_units": work_units,
            "attempts": attempts,
            "execution_state": {"running_work_unit_ids": running, "paused_work_unit_ids": paused, "retry_pending_work_unit_ids": retry_pending, "terminal_work_unit_ids": terminal},
            "input_currency": {
                row["work_unit_id"]: {"input_refs": row["input_version_refs"], "input_digest": row["input_version_set_digest"]}
                for row in work_units
            },
            "output_usability": {
                row["attempt_id"]: {
                    "state": row["state"],
                    "output_refs": row["output_refs"],
                    "usable": row["state"] == AttemptState.SUCCEEDED.value,
                }
                for row in attempts
            },
            "planning_authority": planning_authority,
            "artifact_status": artifact_status,
        }

    def get_work_unit_execution_view(self, work_unit_id: str) -> dict[str, Any]:
        work_unit = self.store.get_latest("canonical_work_units", work_unit_id)
        if not work_unit:
            raise MissingDependency("work_unit_not_found", details={"work_unit_id": work_unit_id})
        case = self.store.get_latest("canonical_research_cases", str(work_unit["case_id"]))
        if not case:
            raise MissingDependency("case_not_found", details={"case_id": work_unit["case_id"]})
        attempts = [
            row
            for row in self.store.list_latest("canonical_attempts", case_id=work_unit["case_id"])
            if row["work_unit_id"] == work_unit_id
        ]
        return {
            "work_unit": work_unit,
            "attempt_history": attempts,
            "input_refs": work_unit["input_version_refs"],
            "terminal_reason": {row["attempt_id"]: row.get("terminal_reason") for row in attempts},
            "planning_authority": self._planning_authority_for_case(case),
        }

    def _planning_authority_for_case(self, case: Mapping[str, Any]) -> str:
        """Resolve the only planning-authority source; never infer it from a Case status."""
        control_ref = str(case.get("case_control_summary_ref") or "")
        control = self.store.get_latest("canonical_case_control_versions", control_ref) if control_ref else None
        if not control:
            raise MissingDependency(
                "case_control_summary_not_found",
                details={"case_id": case.get("case_id"), "case_control_summary_ref": control_ref},
            )
        authority = str(control.get("planning_authority") or "")
        if authority not in {"legacy", "canonical_for_lane"}:
            raise RuntimeFacadeError("planning_authority_invalid")
        return authority

    def get_artifact_version(
        self,
        artifact_id: str,
        *,
        artifact_version: int | None = None,
        include_payload: bool = False,
    ) -> dict[str, Any]:
        normalized_id, requested_version = self._parse_artifact_reference(artifact_id, artifact_version)
        artifact = (
            self.store.get_version("canonical_artifact_versions", normalized_id, requested_version)
            if requested_version is not None
            else self.store.get_latest("canonical_artifact_versions", normalized_id)
        )
        if not artifact:
            raise MissingDependency("artifact_version_not_found", details={"artifact_id": artifact_id})
        if Path(str(artifact["object_key"])).is_absolute() or ".." in PurePosixPath(str(artifact["object_key"])).parts:
            raise ArtifactValidationError("nonportable_artifact_object_key")
        result = {"artifact": artifact}
        if include_payload:
            try:
                result["payload"] = self.object_store.get_json(
                    str(artifact["object_key"]), expected_digest=str(artifact["object_digest"])
                )
            except Exception as exc:
                raise ArtifactValidationError("artifact_digest_validation_failed") from exc
        return result

    def replay_projection(self, task_run_id: str | None = None) -> dict[str, Any]:
        events = list(self.store.list_events(task_run_id))
        projection: dict[str, Any] = {
            "event_count": 0,
            "last_event_type": None,
            "event_ids": [],
            "cases": {},
            "work_units": {},
            "attempts": {},
            "artifacts": {},
            "evidence_workspaces": {},
            "numeric_workspaces": {},
            "workpapers": {},
            "deliverables": {},
            "deliverable_reviews": {},
            "trace_manifests": {},
            "external_call_count": 0,
        }
        for event in events:
            if event["event_type"] not in REPLAY_EVENT_TYPES:
                raise UnknownEventSchema("unknown_state_mutating_event", details={"event_type": event["event_type"]})
            projection["event_count"] += 1
            projection["last_event_type"] = event["event_type"]
            projection["event_ids"].append(event["event_id"])
            payload = dict(event.get("payload") or {})
            event_type = event["event_type"]
            if event_type == "RESEARCH_CASE_CREATED":
                case_id = str(payload.get("case_id") or "")
                if not case_id:
                    raise UnknownEventSchema("case_event_missing_case_id")
                projection["cases"][case_id] = {"state": payload.get("case_status", "shadow_created"), "binding_ids": []}
            elif event_type == "LEGACY_TASK_RUN_BOUND":
                case_id = str(payload.get("case_id") or "")
                if case_id and case_id in projection["cases"]:
                    projection["cases"][case_id]["binding_ids"].append(payload.get("binding_id"))
            elif event_type == "WORK_UNIT_CREATED":
                work_unit_id = str(payload.get("work_unit_id") or payload.get("logical_id") or event.get("work_unit_id") or "")
                if not work_unit_id:
                    raise UnknownEventSchema("work_unit_created_missing_id")
                projection["work_units"][work_unit_id] = {"state": "pending", "attempt_ids": []}
            elif event_type == "WORK_UNIT_STARTED":
                work_unit_id = str(event.get("work_unit_id") or payload.get("work_unit_id") or "")
                projection["work_units"].setdefault(work_unit_id, {"attempt_ids": []})["state"] = "running"
            elif event_type == "ATTEMPT_STARTED":
                attempt_id = str(event.get("attempt_id") or payload.get("attempt_id") or "")
                work_unit_id = str(event.get("work_unit_id") or payload.get("work_unit_id") or "")
                if not attempt_id or not work_unit_id:
                    raise UnknownEventSchema("attempt_started_missing_id")
                projection["attempts"][attempt_id] = {"state": "running", "work_unit_id": work_unit_id, "output_refs": []}
                projection["work_units"].setdefault(work_unit_id, {"state": "running", "attempt_ids": []})["attempt_ids"].append(attempt_id)
            elif event_type in {"SCHEDULER_LEASE_ACQUIRED", "SCHEDULER_LEASE_HEARTBEAT_RECORDED", "SCHEDULER_LEASE_RECLAIMED"}:
                attempt_id = str(event.get("attempt_id") or payload.get("attempt_id") or "")
                if not attempt_id:
                    raise UnknownEventSchema("scheduler_lease_event_missing_attempt_id")
                attempt = projection["attempts"].setdefault(attempt_id, {"work_unit_id": event.get("work_unit_id")})
                attempt.update(
                    {
                        "lease_owner_ref": payload.get("lease_owner_ref"),
                        "lease_fencing_token": payload.get("lease_fencing_token"),
                        "lease_expires_at": payload.get("lease_expires_at"),
                    }
                )
            elif event_type in {"ARTIFACT_VERSION_CREATED", "CHECKPOINT_VERSION_CREATED"}:
                artifact_ref = str(payload.get("artifact_version_id") or "")
                if event_type == "CHECKPOINT_VERSION_CREATED":
                    artifact_ref = str(payload.get("checkpoint_version_id") or artifact_ref)
                if not artifact_ref:
                    raise UnknownEventSchema("artifact_event_missing_version_id")
                projection["artifacts"][artifact_ref] = {
                    "producer_attempt_id": event.get("attempt_id"),
                    "artifact_type": "runtime_checkpoint" if event_type == "CHECKPOINT_VERSION_CREATED" else None,
                    "supersedes_version_id": payload.get("supersedes_version_id"),
                    "checkpoint_state_digest": payload.get("checkpoint_state_digest"),
                }
            elif event_type == "ATTEMPT_COMPLETED":
                attempt_id = str(event.get("attempt_id") or payload.get("attempt_id") or "")
                projection["attempts"].setdefault(attempt_id, {"work_unit_id": event.get("work_unit_id")})
                projection["attempts"][attempt_id].update({"state": "succeeded", "output_refs": list(payload.get("output_refs") or [])})
            elif event_type == "ATTEMPT_FAILED":
                attempt_id = str(event.get("attempt_id") or payload.get("attempt_id") or "")
                projection["attempts"].setdefault(attempt_id, {"work_unit_id": event.get("work_unit_id")})
                projection["attempts"][attempt_id].update({"state": "failed", "failure_type": payload.get("failure_type")})
            elif event_type in {"RECOVERY_RETRY_SCHEDULED", "RECOVERY_RESUME_SCHEDULED"}:
                attempt_id = str(event.get("attempt_id") or payload.get("attempt_id") or "")
                if not attempt_id:
                    raise UnknownEventSchema("recovery_schedule_event_missing_attempt_id")
                projection["attempts"].setdefault(attempt_id, {"work_unit_id": event.get("work_unit_id")}).update(
                    {
                        "recovery_mode": "retry" if event_type == "RECOVERY_RETRY_SCHEDULED" else "resume",
                        "recovery_parent_attempt_id": payload.get("recovery_parent_attempt_id"),
                        "resume_checkpoint_ref": payload.get("resume_checkpoint_ref"),
                        "replay_plan_digest": payload.get("replay_plan_digest"),
                    }
                )
            elif event_type == "RECOVERY_FORK_CREATED":
                work_unit_id = str(event.get("work_unit_id") or payload.get("work_unit_id") or "")
                if not work_unit_id:
                    raise UnknownEventSchema("recovery_fork_event_missing_work_unit_id")
                projection["work_units"].setdefault(work_unit_id, {"state": "pending", "attempt_ids": []}).update(
                    {
                        "forked_from_work_unit_id": payload.get("source_work_unit_id"),
                        "forked_from_attempt_id": payload.get("source_attempt_id"),
                        "recovery_checkpoint_ref": payload.get("checkpoint_ref"),
                    }
                )
            elif event_type == "RECOVERY_DEAD_LETTERED":
                work_unit_id = str(event.get("work_unit_id") or payload.get("work_unit_id") or "")
                if not work_unit_id:
                    raise UnknownEventSchema("recovery_dead_letter_event_missing_work_unit_id")
                projection["work_units"].setdefault(work_unit_id, {"attempt_ids": []}).update(
                    {"state": WorkUnitState.DEAD_LETTERED.value, "dead_letter_reason": payload.get("dead_letter_reason")}
                )
            elif event_type in {"WORK_UNIT_COMPLETED", "WORK_UNIT_FAILED", "WORK_UNIT_CANCELLED"}:
                work_unit_id = str(event.get("work_unit_id") or payload.get("work_unit_id") or "")
                state = {
                    "WORK_UNIT_COMPLETED": "succeeded",
                    "WORK_UNIT_FAILED": "retryable_failed" if payload.get("retryable") else "failed",
                    "WORK_UNIT_CANCELLED": "cancelled",
                }[event_type]
                projection["work_units"].setdefault(work_unit_id, {"attempt_ids": []})["state"] = state
                if event_type == "WORK_UNIT_CANCELLED":
                    for attempt_id in payload.get("cancelled_attempt_ids") or []:
                        projection["attempts"].setdefault(str(attempt_id), {"work_unit_id": work_unit_id})["state"] = "cancelled"
            elif event_type == "EVIDENCE_FIXTURE_COMPILED":
                workspace_id = str(payload.get("workspace_id") or "")
                if not workspace_id:
                    raise UnknownEventSchema("evidence_fixture_event_missing_workspace_id")
                projection["evidence_workspaces"][workspace_id] = {
                    "state": "compiled_fixture",
                    "workspace_version": int(event["state_version_after"]),
                    "review_action_ids": [],
                }
            elif event_type in {"EVIDENCE_CANDIDATE_REJECTED", "EVIDENCE_REPAIR_REQUESTED"}:
                workspace_id = str(payload.get("workspace_id") or "")
                action_id = str(payload.get("review_action_id") or "")
                if not workspace_id or not action_id:
                    raise UnknownEventSchema("evidence_review_event_missing_identity")
                workspace = projection["evidence_workspaces"].setdefault(
                    workspace_id,
                    {"state": "compiled_fixture", "workspace_version": 1, "review_action_ids": []},
                )
                workspace["workspace_version"] = int(event["state_version_after"])
                workspace["review_action_ids"].append(action_id)
            elif event_type == "EVIDENCE_REPAIR_COMPLETED":
                workspace_id = str(payload.get("workspace_id") or "")
                outcome_id = str(payload.get("repair_outcome_id") or "")
                if not workspace_id or not outcome_id:
                    raise UnknownEventSchema("evidence_repair_event_missing_identity")
                workspace = projection["evidence_workspaces"].setdefault(
                    workspace_id,
                    {"state": "compiled_fixture", "workspace_version": 1, "review_action_ids": []},
                )
                workspace["workspace_version"] = int(event["state_version_after"])
                workspace.setdefault("repair_outcome_ids", []).append(outcome_id)
            elif event_type == "NUMERIC_FIXTURE_COMPILED":
                numeric_workspace_id = str(payload.get("numeric_workspace_id") or "")
                if not numeric_workspace_id:
                    raise UnknownEventSchema("numeric_fixture_event_missing_workspace_id")
                projection["numeric_workspaces"][numeric_workspace_id] = {
                    "state": "compiled_fixture",
                    "numeric_workspace_version": int(payload.get("numeric_workspace_version") or 1),
                    "evidence_workspace_id": payload.get("evidence_workspace_id"),
                    "fact_ids": list(payload.get("fact_ids") or []),
                }
            elif event_type == "WORKPAPER_FIXTURE_COMPILED":
                workpaper_id = str(payload.get("workpaper_id") or "")
                if not workpaper_id:
                    raise UnknownEventSchema("workpaper_fixture_event_missing_workpaper_id")
                projection["workpapers"][workpaper_id] = {
                    "state": "awaiting_lead_review",
                    "workpaper_version": int(payload.get("workpaper_version") or 1),
                    "judgment_ids": list(payload.get("judgment_ids") or []),
                    "lead_review_ids": [],
                }
            elif event_type == "LEAD_REVIEW_COMPLETED":
                workpaper_id = str(payload.get("workpaper_id") or "")
                lead_review_id = str(payload.get("lead_review_id") or "")
                if not workpaper_id or not lead_review_id:
                    raise UnknownEventSchema("lead_review_event_missing_identity")
                workpaper = projection["workpapers"].setdefault(
                    workpaper_id,
                    {"state": "awaiting_lead_review", "workpaper_version": 1, "judgment_ids": [], "lead_review_ids": []},
                )
                workpaper["state"] = str(payload.get("decision") or "reviewed")
                workpaper.setdefault("lead_review_ids", []).append(lead_review_id)
            elif event_type == "DELIVERABLE_PREVIEW_COMPILED":
                artifact_version_id = str(payload.get("artifact_version_id") or "")
                if not artifact_version_id:
                    raise UnknownEventSchema("deliverable_event_missing_artifact_version_id")
                projection["deliverables"][artifact_version_id] = {
                    "state": "awaiting_review",
                    "artifact_version": int(payload.get("artifact_version") or 1),
                    "canonical_presentation_digest": payload.get("canonical_presentation_digest"),
                    "review_action_ids": [],
                }
            elif event_type == "DELIVERABLE_REVIEW_RECORDED":
                artifact_version_id = str(payload.get("artifact_version_id") or "")
                review_action_id = str(payload.get("review_action_id") or "")
                if not artifact_version_id or not review_action_id:
                    raise UnknownEventSchema("deliverable_review_event_missing_identity")
                deliverable = projection["deliverables"].setdefault(
                    artifact_version_id,
                    {"state": "awaiting_review", "artifact_version": 1, "review_action_ids": []},
                )
                deliverable.setdefault("review_action_ids", []).append(review_action_id)
                action_type = str(payload.get("action_type") or "comment")
                if action_type in {"return_for_repair", "accept_fixture_preview"}:
                    deliverable["state"] = action_type
                projection["deliverable_reviews"][review_action_id] = {
                    "artifact_version_id": artifact_version_id,
                    "action_type": action_type,
                }
            elif event_type == "TRACE_MANIFEST_COMPILED":
                manifest_id = str(payload.get("manifest_id") or "")
                artifact_version_id = str(payload.get("artifact_version_id") or "")
                if not manifest_id or not artifact_version_id:
                    raise UnknownEventSchema("trace_manifest_event_missing_identity")
                projection["trace_manifests"][manifest_id] = {
                    "artifact_version_id": artifact_version_id,
                    "claim_count": int(payload.get("claim_count") or 0),
                    "source_count": int(payload.get("source_count") or 0),
                }
        projection["projection_digest"] = canonical_digest(projection)
        return projection

    def _single_object_command(
        self,
        command: CommandEnvelope,
        *,
        table: str,
        logical_id: str,
        version: int,
        model: Any,
        event_type: str,
        work_unit_id: str | None = None,
    ) -> ResultEnvelope:
        scope_key, payload_digest, reused = self._idempotency(command, logical_id)
        if reused:
            return reused
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            tx.insert(table, logical_id, version, model.model_dump(mode="json"))
            event = self._event(
                tx,
                command,
                event_type,
                {
                    "logical_id": logical_id,
                    "case_id": model.case_id,
                    "work_unit_id": work_unit_id or logical_id if table == "canonical_work_units" else None,
                    "state": str(model.current_status),
                },
                work_unit_id=work_unit_id or (logical_id if table == "canonical_work_units" else None),
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=0,
                state_version_after=1,
                event_ids=(event.event_id,),
                projection_refs=(logical_id,),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def _event(
        self,
        tx: CanonicalTransaction,
        command: CommandEnvelope,
        event_type: str,
        payload: Mapping[str, Any],
        task_run_id: str | None = None,
        work_unit_id: str | None = None,
        attempt_id: str | None = None,
    ) -> EventEnvelope:
        self._ensure_actor_snapshot(tx, command)
        now = utc_now()
        return EventEnvelope(
            event_id=f"event_{uuid4().hex}",
            event_type=event_type,
            task_run_id=task_run_id,
            work_unit_id=work_unit_id,
            attempt_id=attempt_id,
            sequence_no=tx.next_event_sequence(task_run_id),
            occurred_at=now,
            recorded_at=now,
            actor_snapshot_ref=command.actor_snapshot_ref,
            causation_event_id=command.causation_event_id,
            correlation_id=command.correlation_id,
            state_version_before=command.expected_state_version,
            state_version_after=command.expected_state_version + 1,
            payload_digest=canonical_digest(payload),
            payload=dict(payload),
        )

    def _ensure_actor_snapshot(self, tx: CanonicalTransaction, command: CommandEnvelope) -> None:
        existing = tx.get_latest("canonical_actor_snapshots", command.actor_snapshot_ref)
        if existing:
            if existing.get("tenant_id") != command.tenant_id or existing.get("project_id") != command.project_id:
                raise MissingDependency("actor_snapshot_scope_mismatch")
            return
        snapshot = ActorSnapshot(
            **self._scope(command, case_id=None),
            actor_snapshot_id=command.actor_snapshot_ref,
            snapshot_version=1,
            actor_id=command.actor_snapshot_ref,
            actor_type="external_snapshot_reference",
            display_name=command.actor_snapshot_ref,
            current_status="active",
        )
        tx.insert(
            "canonical_actor_snapshots",
            snapshot.actor_snapshot_id,
            snapshot.snapshot_version,
            snapshot.model_dump(mode="json"),
        )

    def _require_case_row(
        self,
        tx: CanonicalTransaction,
        command: CommandEnvelope,
        case_id: str,
        *,
        table: str = "canonical_research_cases",
        logical_id: str | None = None,
    ) -> Mapping[str, Any]:
        row = tx.get_latest(table, logical_id or case_id)
        if not row:
            raise MissingDependency(f"{table}_not_found", details={"case_id": case_id, "logical_id": logical_id})
        if row.get("case_id") != case_id or row.get("tenant_id") != command.tenant_id or row.get("project_id") != command.project_id:
            raise MissingDependency("canonical_scope_mismatch", details={"case_id": case_id, "logical_id": logical_id})
        return row

    def _require_p02_planning_case(
        self,
        tx: CanonicalTransaction,
        command: CommandEnvelope,
        case_id: str,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        case = self._require_case_row(tx, command, case_id)
        self._assert_p02_fixture_case(case)
        summary = self._require_case_row(
            tx,
            command,
            case_id,
            table="canonical_case_control_versions",
            logical_id=str(case["case_control_summary_ref"]),
        )
        if summary.get("planning_authority") != "legacy":
            raise PlanningAuthorityViolation("legacy_planning_authority_not_retained")
        return case, summary

    @staticmethod
    def _assert_p02_fixture_case(case: Mapping[str, Any]) -> None:
        if case.get("case_type") != "fixture_internal":
            raise PlanningAuthorityViolation("fixture_case_required")
        if case.get("data_classification") != "internal":
            raise PlanningAuthorityViolation("internal_case_required")
        if case.get("current_status") not in {"shadow_created", "shadow_active"}:
            raise PlanningAuthorityViolation("shadow_case_required")

    @staticmethod
    def _assert_planning_version(field: str, expected: int, actual: int) -> None:
        if expected != actual:
            raise PlanningVersionConflict(
                f"stale_{field}",
                details={
                    "version_field": field,
                    "expected_version": expected,
                    "current_version": actual,
                },
            )

    @staticmethod
    def _p02_contract_id(case: Mapping[str, Any]) -> str:
        digest = canonical_digest(
            {
                "authority": P02_4_CONTRACT_DIGEST,
                "tenant_id": case["tenant_id"],
                "project_id": case["project_id"],
                "case_id": case["case_id"],
            }
        )
        return f"p02_decision_surface_{digest[:24]}"

    @staticmethod
    def _p02_cell_id(contract_id: str, cell_key: str) -> str:
        return f"p02_cell_{canonical_digest({'contract_id': contract_id, 'cell_key': cell_key})[:24]}"

    @staticmethod
    def _p02_slot_id(cell_id: str, evidence_role: str) -> str:
        return f"p02_slot_{canonical_digest({'cell_id': cell_id, 'evidence_role': evidence_role})[:24]}"

    @staticmethod
    def _p02_checkpoint_id(contract_id: str) -> str:
        return f"p02_checkpoint_{canonical_digest({'contract_id': contract_id})[:24]}"

    def _p02_checkpoint(
        self,
        command: CommandEnvelope,
        *,
        case_id: str,
        contract_id: str,
        contract_version_id: str,
        checkpoint_version: int,
        review_status: str,
        supersedes_version_id: str | None = None,
    ) -> PlanningCheckpointVersion:
        checkpoint_id = self._p02_checkpoint_id(contract_id)
        return PlanningCheckpointVersion(
            **self._scope(command, case_id=case_id),
            checkpoint_id=checkpoint_id,
            checkpoint_version_id=f"{checkpoint_id}:v{checkpoint_version}",
            checkpoint_version=checkpoint_version,
            contract_version_id=contract_version_id,
            review_status=review_status,
            supersedes_version_id=supersedes_version_id,
            current_status=review_status,
        )

    @staticmethod
    def _validate_p02_changes(value: Any) -> dict[str, dict[str, str]]:
        if not isinstance(value, (list, tuple)) or not value:
            raise PlanningConflict("revision_changes_required")
        changes: dict[str, dict[str, str]] = {}
        allowed_keys = {"cell_id", "what_would_change", "stop_rule"}
        for raw_change in value:
            if not isinstance(raw_change, Mapping) or set(raw_change) - allowed_keys:
                raise PlanningConflict("revision_change_shape_invalid")
            cell_id = str(raw_change.get("cell_id") or "").strip()
            what_would_change = str(raw_change.get("what_would_change") or "").strip()
            if not cell_id or not what_would_change:
                raise PlanningConflict("revision_change_required_field_missing")
            if cell_id in changes:
                raise PlanningConflict("revision_change_cell_duplicate", details={"cell_id": cell_id})
            change = {"what_would_change": what_would_change}
            if "stop_rule" in raw_change:
                stop_rule = str(raw_change.get("stop_rule") or "").strip()
                if not stop_rule:
                    raise PlanningConflict("revision_stop_rule_blank", details={"cell_id": cell_id})
                change["stop_rule"] = stop_rule
            changes[cell_id] = change
        return changes

    def _p02_child_rows(
        self,
        tx: CanonicalTransaction,
        contract: DecisionSurfaceContractVersion,
    ) -> tuple[list[DecisionSurfaceCellVersion], list[EvidenceSlotVersion]]:
        cell_rows = [
            DecisionSurfaceCellVersion.model_validate(row)
            for row in tx.list_versions("canonical_decision_surface_cell_versions", case_id=contract.case_id)
            if row.get("contract_version_id") == contract.contract_version_id
        ]
        cells_by_id = {cell.cell_id: cell for cell in cell_rows}
        if set(cells_by_id) != set(contract.required_cell_ids) or len(cell_rows) != len(contract.required_cell_ids):
            raise PlanningConflict("decision_surface_cell_projection_invalid")
        cells = [cells_by_id[cell_id] for cell_id in contract.required_cell_ids]
        cell_version_ids = {cell.cell_version_id for cell in cells}
        slots = [
            EvidenceSlotVersion.model_validate(row)
            for row in tx.list_versions("canonical_evidence_slot_versions", case_id=contract.case_id)
            if row.get("cell_version_id") in cell_version_ids
        ]
        slot_counts = {
            cell.cell_version_id: sum(slot.cell_version_id == cell.cell_version_id for slot in slots)
            for cell in cells
        }
        if any(count < 1 for count in slot_counts.values()) or not all(slot.required for slot in slots):
            raise PlanningConflict("decision_surface_slot_projection_invalid")
        return cells, slots

    @staticmethod
    def _decision_surface_view(
        contract: DecisionSurfaceContractVersion,
        checkpoint: PlanningCheckpointVersion,
        cells: Sequence[DecisionSurfaceCellVersion],
        slots: Sequence[EvidenceSlotVersion],
    ) -> dict[str, Any]:
        slots_by_cell: dict[str, list[EvidenceSlotVersion]] = {}
        for slot in slots:
            slots_by_cell.setdefault(slot.cell_version_id, []).append(slot)
        return {
            "case_id": contract.case_id,
            "contract_id": contract.contract_id,
            "contract_version": contract.contract_version,
            "contract_version_id": contract.contract_version_id,
            "checkpoint_version": checkpoint.checkpoint_version,
            "review_status": checkpoint.review_status,
            "cells": [
                {
                    "cell_id": cell.cell_id,
                    "cell_version": cell.cell_version,
                    "decision_question": cell.decision_question,
                    "owner": cell.owner_role,
                    "materiality": cell.materiality,
                    "stop_rule": cell.stop_rule,
                    "what_would_change": cell.what_would_change,
                    "evidence_slots": [
                        {
                            "evidence_slot_id": slot.evidence_slot_id,
                            "evidence_role": slot.evidence_role,
                            "entity_scope": list(slot.entity_scope),
                            "period_scope": slot.period_scope,
                            "source_policy_ref": slot.source_policy_ref,
                            "required": slot.required,
                        }
                        for slot in slots_by_cell.get(cell.cell_version_id, [])
                    ],
                }
                for cell in cells
            ],
        }

    @staticmethod
    def _reuse_planning_result(existing: Mapping[str, Any], payload_digest: str) -> dict[str, Any]:
        if existing["payload_digest"] != payload_digest:
            raise IdempotencyConflict("idempotency_conflict")
        return dict(existing["result"])

    def _ensure_binding_identity_available(
        self,
        tx: CanonicalTransaction,
        binding: LegacyTaskRunBinding,
        case_id: str,
    ) -> None:
        for existing in tx.list_latest("canonical_task_run_bindings"):
            if existing.get("normalized_identity_digest") != binding.normalized_identity_digest:
                continue
            if existing.get("current_status") != "active":
                continue
            if existing.get("case_id") != case_id:
                raise LegacyBindingConflict(
                    "legacy_binding_conflict",
                    details={"existing_case_id": existing.get("case_id"), "normalized_identity_digest": binding.normalized_identity_digest},
                )
            if existing.get("binding_id") != binding.binding_id:
                raise LegacyBindingConflict("legacy_binding_conflict")

    def _require_running_execution(
        self,
        tx: CanonicalTransaction,
        command: CommandEnvelope,
        case_id: str,
        work_unit_id: str,
        attempt_id: str,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
        work_unit = self._require_case_row(
            tx, command, case_id, table="canonical_work_units", logical_id=work_unit_id
        )
        attempt = self._require_case_row(tx, command, case_id, table="canonical_attempts", logical_id=attempt_id)
        if work_unit.get("state") != WorkUnitState.RUNNING.value:
            raise IllegalStateTransition("work_unit_must_be_running")
        if attempt.get("state") != AttemptState.RUNNING.value or attempt.get("work_unit_id") != work_unit_id:
            raise IllegalStateTransition("attempt_must_be_running_for_work_unit")
        expected_input_head = str(command.payload.get("input_head_digest") or work_unit.get("input_head_digest") or "")
        if expected_input_head != str(work_unit.get("input_head_digest") or ""):
            raise StaleInputHead("stale_input_head")
        if attempt.get("input_head_digest") != work_unit.get("input_head_digest"):
            raise StaleInputHead("attempt_input_head_is_stale")
        lease_expires_at = self._datetime(attempt.get("lease_expires_at"), fallback=command.requested_at)
        if lease_expires_at <= command.requested_at:
            raise LeaseValidationError("attempt_lease_expired")
        command_owner = command.payload.get("lease_owner_ref") or command.payload.get("worker_ref")
        if command_owner and command_owner != attempt.get("lease_owner_ref"):
            raise LeaseValidationError("attempt_lease_owner_mismatch")
        if attempt.get("scheduler_managed"):
            supplied_token = command.payload.get("lease_fencing_token")
            if supplied_token is None:
                raise LeaseValidationError("lease_fencing_token_required")
            if int(supplied_token) != int(attempt.get("lease_fencing_token") or 0):
                raise LeaseValidationError("lease_fencing_token_mismatch")
        return work_unit, attempt

    @staticmethod
    def _retry_permitted(
        work_unit: Mapping[str, Any],
        attempt: Mapping[str, Any],
        failure_type: str,
        requested_retryable: bool,
    ) -> bool:
        retryable_failure_types = {str(value) for value in work_unit.get("retryable_failure_types", ())}
        poison_failure_types = {str(value) for value in work_unit.get("poison_failure_types", ("poison",))}
        poison_failure = failure_type in poison_failure_types or failure_type.startswith("poison_")
        return bool(
            requested_retryable
            and work_unit.get("retry_policy_ref") == "retry:bounded"
            and failure_type in retryable_failure_types
            and not poison_failure
            and int(work_unit.get("retry_count", 0)) < int(work_unit.get("retry_budget", 0))
            and int(attempt.get("attempt_no", 1)) < int(work_unit.get("max_attempts", 1))
        )

    def _validate_output_artifacts(self, attempt_id: str, output_refs: tuple[str, ...]) -> None:
        for reference in output_refs:
            artifact = self.get_artifact_version(reference, include_payload=True)["artifact"]
            if artifact.get("producer_attempt_id") != attempt_id:
                raise ArtifactValidationError(
                    "artifact_producer_attempt_mismatch",
                    details={"artifact_version_id": artifact.get("artifact_version_id"), "attempt_id": attempt_id},
                )

    def _validate_recovery_checkpoint(
        self,
        tx: CanonicalTransaction,
        command: CommandEnvelope,
        *,
        case_id: str,
        checkpoint_ref: str | None,
        parent_attempt_id: str,
    ) -> str:
        """Resolve an exact, in-store artifact reference without owning checkpoint persistence.

        M5.2 only consumes a checkpoint produced elsewhere.  M5.3 owns creation,
        retention and compaction, so this helper deliberately checks identity,
        scope and producer lineage but never reads or writes checkpoint contents.
        """
        reference = str(checkpoint_ref or "")
        artifact_id, artifact_version = self._parse_artifact_reference(reference, None)
        if not artifact_id or artifact_version is None:
            raise MissingDependency("recovery_checkpoint_exact_version_required")
        artifact = tx.get_version("canonical_artifact_versions", artifact_id, artifact_version)
        if not artifact:
            raise MissingDependency("recovery_checkpoint_not_found", details={"checkpoint_ref": reference})
        if artifact.get("artifact_version_id") != reference:
            raise MissingDependency("recovery_checkpoint_reference_identity_mismatch")
        if (
            artifact.get("case_id") != case_id
            or artifact.get("tenant_id") != command.tenant_id
            or artifact.get("project_id") != command.project_id
        ):
            raise MissingDependency("recovery_checkpoint_scope_mismatch")
        if artifact.get("artifact_type") != "runtime_checkpoint":
            raise MissingDependency("recovery_checkpoint_artifact_type_invalid")
        if artifact.get("producer_attempt_id") != parent_attempt_id:
            raise MissingDependency("recovery_checkpoint_parent_attempt_mismatch")
        self._validate_checkpoint_artifact_payload(artifact)
        return reference

    def _validate_checkpoint_artifact_payload(self, artifact: Mapping[str, Any]) -> Mapping[str, Any]:
        if artifact.get("artifact_type") != "runtime_checkpoint":
            raise ArtifactValidationError("checkpoint_artifact_type_invalid")
        checkpoint_id = str(artifact.get("artifact_id") or "")
        checkpoint_version = int(artifact.get("artifact_version") or 0)
        checkpoint_version_id = str(artifact.get("artifact_version_id") or "")
        schema_ref = str(artifact.get("checkpoint_schema_ref") or "")
        state_digest = str(artifact.get("checkpoint_state_digest") or "")
        if not checkpoint_id or checkpoint_version < 1 or checkpoint_version_id != f"{checkpoint_id}:v{checkpoint_version}":
            raise ArtifactValidationError("checkpoint_artifact_identity_invalid")
        if not schema_ref or not state_digest or int(artifact.get("checkpoint_sequence_no") or 0) != checkpoint_version:
            raise ArtifactValidationError("checkpoint_artifact_metadata_invalid")
        try:
            payload = self.object_store.get_json(
                str(artifact["object_key"]), expected_digest=str(artifact["object_digest"])
            )
        except Exception as exc:
            raise ArtifactValidationError("checkpoint_artifact_digest_validation_failed") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("snapshot"), Mapping):
            raise ArtifactValidationError("checkpoint_payload_shape_invalid")
        if (
            payload.get("checkpoint_id") != checkpoint_id
            or payload.get("checkpoint_version_id") != checkpoint_version_id
            or int(payload.get("checkpoint_version") or 0) != checkpoint_version
            or payload.get("checkpoint_schema_ref") != schema_ref
            or payload.get("producer_attempt_id") != artifact.get("producer_attempt_id")
            or payload.get("input_head_digest") != artifact.get("input_refs_digest")
            or payload.get("checkpoint_state_digest") != state_digest
            or canonical_digest(payload["snapshot"]) != state_digest
        ):
            raise ArtifactValidationError("checkpoint_payload_metadata_mismatch")
        return payload

    def _terminal_events(
        self,
        tx: CanonicalTransaction,
        command: CommandEnvelope,
        *,
        attempt_event_type: str,
        work_unit_event_type: str,
        work_unit_id: str,
        attempt_id: str,
        attempt_payload: Mapping[str, Any],
        work_unit_payload: Mapping[str, Any] | None = None,
    ) -> list[EventEnvelope]:
        events = [
            self._event(
                tx,
                command,
                attempt_event_type,
                attempt_payload,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            ),
            self._event(
                tx,
                command,
                work_unit_event_type,
                {"work_unit_id": work_unit_id, "attempt_id": attempt_id, **dict(work_unit_payload or {})},
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            ),
        ]
        for event in events:
            tx.append_event(event)
        return events

    @staticmethod
    def _parse_artifact_reference(artifact_id: str, artifact_version: int | None) -> tuple[str, int | None]:
        if artifact_version is not None:
            return artifact_id, artifact_version
        prefix, marker, suffix = artifact_id.rpartition(":v")
        if marker and suffix.isdigit() and prefix:
            return prefix, int(suffix)
        return artifact_id, None

    @staticmethod
    def project_error(command: CommandEnvelope, error: Exception) -> ResultEnvelope:
        """Project a typed application error without swallowing the original exception."""
        if isinstance(error, RuntimeFacadeError):
            code = error.error_code
            details = error.details
        elif isinstance(error, IdempotencyConflict):
            code, details = "idempotency_conflict", {}
        elif isinstance(error, StaleStateVersion):
            code, details = "stale_state_version", {}
        elif isinstance(error, TransactionConflict):
            code, details = "transaction_conflict", {}
        elif isinstance(error, FeatureFlagError):
            code = "permission_denied" if str(error) == "permission_denied" else "shadow_authority_violation"
            details = {}
        elif isinstance(error, KillSwitchEnabled):
            code, details = "shadow_authority_violation", {"reason": "canonical_kill_switch_enabled"}
        elif isinstance(error, OSError):
            code, details = "artifact_write_failed", {}
        elif isinstance(error, (KeyError, ValueError)):
            code, details = "validation_error", {}
        else:
            code, details = "backend_unavailable", {}
        status = "conflict" if code in {"idempotency_conflict", "stale_state_version", "stale_input_head", "transaction_conflict", "legacy_binding_conflict"} else "rejected"
        return ResultEnvelope(
            command_id=command.command_id,
            status=status,
            state_version_before=command.expected_state_version,
            state_version_after=command.expected_state_version,
            error={"code": code, **details},
        )

    def _binding(self, command: CommandEnvelope, case_id: str) -> LegacyTaskRunBinding:
        identity = {
            "legacy_system": str(command.payload.get("legacy_system") or "r53_r60_runtime_task_spine"),
            "legacy_store_id": str(command.payload.get("legacy_store_id") or "default"),
            "legacy_task_id": str(command.payload["legacy_task_id"]),
            "legacy_run_id": str(command.payload.get("legacy_run_id") or ""),
        }
        binding_id = str(command.payload.get("binding_id") or f"binding_{canonical_digest(identity)[:24]}")
        return LegacyTaskRunBinding(
            **self._scope(command, case_id=case_id),
            binding_id=binding_id,
            binding_version=1,
            **identity,
            normalized_identity_digest=canonical_digest(identity),
            adapter_version="point01_legacy_binding_v1_0",
            current_status="active",
        )

    def _scope(self, command: CommandEnvelope, *, case_id: str | None) -> dict[str, Any]:
        return {
            "tenant_id": command.tenant_id,
            "project_id": command.project_id,
            "case_id": case_id,
            "created_at": command.requested_at,
            "recorded_at": command.requested_at,
            "actor_snapshot_ref": command.actor_snapshot_ref,
            "permission_snapshot_ref": command.permission_snapshot_ref,
            "policy_config_refs": command.policy_config_refs,
            "causation_event_id": command.causation_event_id,
            "correlation_id": command.correlation_id,
        }

    def _authorize(self, consumer: str) -> None:
        self.flags.authorize(FLAG_ID, mode=self.mode, consumer=consumer, grants=self.grants)
        if self.store.kill_switch_enabled():
            raise RuntimeFacadeError("canonical_kill_switch_enabled")

    @staticmethod
    def _require_case(command: CommandEnvelope) -> str:
        if not command.case_id:
            raise RuntimeFacadeError("case_id_required")
        return command.case_id

    @staticmethod
    def _datetime(value: Any, *, fallback: datetime) -> datetime:
        if value is None:
            return fallback
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    @staticmethod
    def _lease_duration(command: CommandEnvelope) -> int:
        lease_duration_seconds = int(command.payload.get("lease_duration_seconds") or 60)
        if not 1 <= lease_duration_seconds <= 3600:
            raise LeaseValidationError("lease_duration_seconds_out_of_range")
        return lease_duration_seconds

    @staticmethod
    def _lease_event_payload(attempt: Attempt, *, queue_name: str) -> dict[str, Any]:
        return {
            "attempt_id": attempt.attempt_id,
            "work_unit_id": attempt.work_unit_id,
            "queue_name": queue_name,
            "lease_owner_ref": attempt.lease_owner_ref,
            "lease_fencing_token": attempt.lease_fencing_token,
            "lease_expires_at": attempt.lease_expires_at.isoformat() if attempt.lease_expires_at else None,
            "lease_heartbeat_at": attempt.lease_heartbeat_at.isoformat() if attempt.lease_heartbeat_at else None,
        }

    @staticmethod
    def _reuse_or_conflict(existing: Mapping[str, Any], payload_digest: str) -> ResultEnvelope:
        if existing["payload_digest"] != payload_digest:
            raise IdempotencyConflict("idempotency_conflict")
        return ResultEnvelope.model_validate(existing["result"]).model_copy(update={"reused_idempotent_result": True})

    def _idempotency(self, command: CommandEnvelope, logical_target: str) -> tuple[str, str, ResultEnvelope | None]:
        scope = f"{command.tenant_id}:{command.command_type}:{logical_target}:{command.idempotency_key}"
        digest = canonical_digest(command.payload)
        return scope, digest, None
