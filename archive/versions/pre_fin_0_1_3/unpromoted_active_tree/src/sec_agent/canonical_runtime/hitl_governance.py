from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Mapping

from pydantic import Field, field_validator

from .facade import IllegalStateTransition, MissingDependency, RuntimeFacade
from .models import Attempt, AttemptState, CommandEnvelope, ResultEnvelope, ScopedVersion, StrictModel, WorkUnit, WorkUnitState, canonical_digest


class ApprovalRegistryRecord(StrictModel):
    """Authoritative approval-registry read supplied to the temporary control plane."""

    approval_id: str
    approval_registry_ref: str
    scope_digest: str
    approval_state: Literal["active", "revoked"]
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class HITLApprovalReceipt(ScopedVersion):
    approval_id: str
    approval_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    work_unit_id: str
    attempt_id: str
    checkpoint_ref: str
    scope_digest: str
    approval_registry_ref: str
    approval_registry_digest: str
    approval_status: Literal["active", "revoked"]
    expires_at: datetime
    review_action_id: str

    @field_validator("expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class HITLApprovalError(RuntimeError):
    pass


class HITLGovernanceService:
    """M5.6 durable approval/pause/resume over the canonical temporary store.

    The registry is deliberately an explicit constructor input.  A local receipt
    never grants itself authority: record, resume and invalidation all re-check
    a current registry record.  No worker, provider or external review system is
    started by this service.
    """

    def __init__(self, facade: RuntimeFacade, *, approval_registry: Mapping[str, ApprovalRegistryRecord]):
        self.facade = facade
        self._approval_registry = dict(approval_registry)

    def replace_approval_registry(self, approval_registry: Mapping[str, ApprovalRegistryRecord]) -> None:
        """Replace the authoritative read model after an external registry refresh."""
        self._approval_registry = dict(approval_registry)

    def register_authority(self, command: CommandEnvelope, record: ApprovalRegistryRecord) -> ResultEnvelope:
        """Persist one authoritative registry state; the constructor mapping is only a compatibility seed."""
        case_id = self.facade._require_case(command)
        scope_key, payload_digest, _ = self.facade._idempotency(command, f"hitl_registry:{record.approval_id}")
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            previous = tx.get_latest("canonical_hitl_registry_versions", record.approval_id)
            version = int(previous.get("registry_version", 0)) + 1 if previous else 1
            row = {
                **self.facade._scope(command, case_id=case_id),
                "registry_id": record.approval_id,
                "registry_version": version,
                "state_version": version,
                "approval_registry_ref": record.approval_registry_ref,
                "scope_digest": record.scope_digest,
                "approval_state": record.approval_state,
                "expires_at": record.expires_at.isoformat(),
                "current_status": record.approval_state,
                "supersedes_version_id": f"{record.approval_id}:v{version - 1}" if previous else None,
                "content_digest": canonical_digest(record),
            }
            tx.insert("canonical_hitl_registry_versions", record.approval_id, version, row)
            event = self.facade._event(tx, command, "HITL_REGISTRY_STATE_RECORDED", {"approval_id": record.approval_id, "registry_ref": record.approval_registry_ref, "approval_state": record.approval_state, "scope_digest": record.scope_digest})
            tx.append_event(event)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=version - 1, state_version_after=version, event_ids=(event.event_id,), projection_refs=(record.approval_id,))
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        self._approval_registry[record.approval_id] = record
        return result

    def pause(self, command: CommandEnvelope) -> ResultEnvelope:
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        approval_id = str(command.payload.get("approval_id") or "")
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        checkpoint_ref = str(command.payload.get("checkpoint_ref") or "")
        supplied_scope_digest = str(command.payload.get("scope_digest") or "")
        if not all((approval_id, work_unit_id, attempt_id, checkpoint_ref, supplied_scope_digest)):
            raise HITLApprovalError("hitl_approval_pause_fields_required")
        scope_key, payload_digest, _ = self.facade._idempotency(command, approval_id)
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            if tx.get_latest("canonical_hitl_approval_versions", approval_id):
                raise HITLApprovalError("hitl_approval_already_recorded")
            work_unit, attempt = self.facade._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            if not attempt.get("scheduler_managed"):
                raise IllegalStateTransition("hitl_pause_requires_scheduler_managed_attempt")
            checkpoint = self._require_checkpoint(tx, case_id=case_id, checkpoint_ref=checkpoint_ref, attempt_id=attempt_id)
            scope_digest = self._scope_digest(command, work_unit_id=work_unit_id, attempt_id=attempt_id, checkpoint_ref=checkpoint_ref)
            if supplied_scope_digest != scope_digest:
                raise HITLApprovalError("hitl_scope_digest_mismatch")
            registry = self._require_registry(approval_id, scope_digest=scope_digest, at=command.requested_at, expected_state="active", tx=tx, case_id=case_id)
            approval = HITLApprovalReceipt(
                **self.facade._scope(command, case_id=case_id),
                approval_id=approval_id,
                approval_version=1,
                state_version=1,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                checkpoint_ref=checkpoint_ref,
                scope_digest=scope_digest,
                approval_registry_ref=registry.approval_registry_ref,
                approval_registry_digest=canonical_digest(registry),
                approval_status="active",
                expires_at=registry.expires_at,
                review_action_id=f"review_action:{approval_id}:pause",
                current_status="active",
            )
            paused_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": int(attempt.get("state_version", 0)) + 1,
                    "state": AttemptState.PAUSED.value,
                    "current_status": "paused",
                    "lease_owner_ref": None,
                    "lease_expires_at": None,
                    "lease_heartbeat_at": command.requested_at,
                }
            )
            paused_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.PAUSED.value,
                    "current_status": "paused_hitl",
                }
            )
            tx.insert("canonical_hitl_approval_versions", approval_id, 1, approval.model_dump(mode="json"))
            tx.insert("canonical_attempts", attempt_id, paused_attempt.attempt_no, paused_attempt.model_dump(mode="json"))
            tx.insert("canonical_work_units", work_unit_id, paused_work_unit.work_unit_version, paused_work_unit.model_dump(mode="json"))
            approval_event = self.facade._event(
                tx,
                command.model_copy(update={"expected_state_version": 0}),
                "HITL_APPROVAL_RECORDED",
                {
                    "approval_id": approval_id,
                    "approval_registry_ref": registry.approval_registry_ref,
                    "scope_digest": scope_digest,
                    "checkpoint_ref": checkpoint_ref,
                    "checkpoint_state_digest": checkpoint.get("checkpoint_state_digest"),
                    "review_action_id": approval.review_action_id,
                },
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(approval_event)
            pause_event = self.facade._event(
                tx,
                command,
                "HITL_WORK_UNIT_PAUSED",
                {"approval_id": approval_id, "checkpoint_ref": checkpoint_ref, "released_lease_fencing_token": attempt.get("lease_fencing_token")},
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(pause_event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=(approval_event.event_id, pause_event.event_id),
                artifact_refs=(checkpoint_ref,),
                projection_refs=(approval_id, work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def resume(self, command: CommandEnvelope) -> ResultEnvelope:
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        approval_id = str(command.payload.get("approval_id") or "")
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        supplied_scope_digest = str(command.payload.get("scope_digest") or "")
        worker_ref = str(command.payload.get("worker_ref") or "")
        if not all((approval_id, work_unit_id, attempt_id, supplied_scope_digest, worker_ref)):
            raise HITLApprovalError("hitl_approval_resume_fields_required")
        scope_key, payload_digest, _ = self.facade._idempotency(command, approval_id)
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_work_units", work_unit_id, command.expected_state_version)
            approval = tx.get_latest("canonical_hitl_approval_versions", approval_id)
            if not approval or approval.get("case_id") != case_id:
                raise MissingDependency("hitl_approval_not_found")
            if approval.get("approval_status") != "active":
                raise HITLApprovalError("hitl_approval_not_active")
            if supplied_scope_digest != approval.get("scope_digest"):
                raise HITLApprovalError("hitl_resume_scope_digest_mismatch")
            self._require_registry(
                approval_id,
                scope_digest=supplied_scope_digest,
                at=command.requested_at,
                expected_state="active",
                approval_registry_ref=str(approval["approval_registry_ref"]),
                approval_registry_digest=str(approval["approval_registry_digest"]),
                tx=tx,
                case_id=case_id,
            )
            work_unit = self.facade._require_case_row(tx, command, case_id, table="canonical_work_units", logical_id=work_unit_id)
            attempt = self.facade._require_case_row(tx, command, case_id, table="canonical_attempts", logical_id=attempt_id)
            if work_unit.get("state") != WorkUnitState.PAUSED.value or attempt.get("state") != AttemptState.PAUSED.value:
                raise IllegalStateTransition("hitl_resume_requires_paused_work_unit_and_attempt")
            if approval.get("work_unit_id") != work_unit_id or approval.get("attempt_id") != attempt_id:
                raise HITLApprovalError("hitl_approval_execution_identity_mismatch")
            checkpoint_ref = str(approval["checkpoint_ref"])
            self._require_checkpoint(tx, case_id=case_id, checkpoint_ref=checkpoint_ref, attempt_id=attempt_id)
            scope_digest = self._scope_digest(command, work_unit_id=work_unit_id, attempt_id=attempt_id, checkpoint_ref=checkpoint_ref)
            if scope_digest != supplied_scope_digest:
                raise HITLApprovalError("hitl_current_scope_digest_mismatch")
            lease_duration = self.facade._lease_duration(command)
            next_token = int(work_unit.get("latest_scheduler_fencing_token", 0)) + 1
            resumed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": int(attempt.get("state_version", 0)) + 1,
                    "state": AttemptState.RUNNING.value,
                    "current_status": "running",
                    "lease_owner_ref": worker_ref,
                    "lease_expires_at": command.requested_at + timedelta(seconds=lease_duration),
                    "lease_heartbeat_at": command.requested_at,
                    "lease_fencing_token": next_token,
                }
            )
            resumed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.RUNNING.value,
                    "current_status": "running",
                    "latest_scheduler_fencing_token": next_token,
                }
            )
            tx.insert("canonical_attempts", attempt_id, resumed_attempt.attempt_no, resumed_attempt.model_dump(mode="json"))
            tx.insert("canonical_work_units", work_unit_id, resumed_work_unit.work_unit_version, resumed_work_unit.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command,
                "HITL_WORK_UNIT_RESUMED",
                {"approval_id": approval_id, "checkpoint_ref": checkpoint_ref, "lease_fencing_token": next_token, "worker_ref": worker_ref},
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=(event.event_id,),
                artifact_refs=(checkpoint_ref,),
                projection_refs=(approval_id, work_unit_id, attempt_id),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def invalidate(self, command: CommandEnvelope) -> ResultEnvelope:
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        approval_id = str(command.payload.get("approval_id") or "")
        reason = str(command.payload.get("reason") or "")
        if not approval_id or not reason:
            raise HITLApprovalError("hitl_approval_invalidation_fields_required")
        scope_key, payload_digest, _ = self.facade._idempotency(command, approval_id)
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            tx.assert_expected_state("canonical_hitl_approval_versions", approval_id, command.expected_state_version)
            approval = tx.get_latest("canonical_hitl_approval_versions", approval_id)
            if not approval or approval.get("case_id") != case_id:
                raise MissingDependency("hitl_approval_not_found")
            if approval.get("approval_status") != "active":
                raise HITLApprovalError("hitl_approval_not_active")
            self._require_registry(
                approval_id,
                scope_digest=str(approval["scope_digest"]),
                at=command.requested_at,
                expected_state="revoked",
                approval_registry_ref=str(approval["approval_registry_ref"]),
                tx=tx,
                case_id=case_id,
            )
            invalidated = HITLApprovalReceipt.model_validate(
                {
                    **approval,
                    "approval_version": int(approval["approval_version"]) + 1,
                    "state_version": int(approval["state_version"]) + 1,
                    "approval_status": "revoked",
                    "current_status": "revoked",
                    "supersedes_version_id": f"{approval_id}:v{approval['approval_version']}",
                    "review_action_id": f"review_action:{approval_id}:invalidated",
                    "causation_event_id": command.causation_event_id,
                }
            )
            tx.insert("canonical_hitl_approval_versions", approval_id, invalidated.approval_version, invalidated.model_dump(mode="json"))
            event = self.facade._event(
                tx,
                command,
                "HITL_APPROVAL_INVALIDATED",
                {"approval_id": approval_id, "reason": reason, "approval_registry_ref": approval["approval_registry_ref"], "scope_digest": approval["scope_digest"]},
                work_unit_id=str(approval["work_unit_id"]),
                attempt_id=str(approval["attempt_id"]),
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=(event.event_id,),
                projection_refs=(approval_id, str(approval["work_unit_id"])),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def review_queue(self, *, case_id: str, at: datetime | None = None) -> dict[str, Any]:
        as_of = at or datetime.now(timezone.utc)
        approvals = self.facade.store.list_latest("canonical_hitl_approval_versions", case_id=case_id)
        records: list[dict[str, Any]] = []
        for approval in approvals:
            work_unit = self.facade.store.get_latest("canonical_work_units", str(approval["work_unit_id"]))
            registry_state = "missing"
            persisted = self.facade.store.get_latest("canonical_hitl_registry_versions", str(approval["approval_id"]))
            if persisted and persisted.get("case_id") == case_id:
                registry_state = str(persisted.get("approval_state") or "missing")
            else:
                registry = self._approval_registry.get(str(approval["approval_id"]))
                if registry:
                    registry_state = registry.approval_state
            eligible = bool(
                work_unit
                and work_unit.get("state") == WorkUnitState.PAUSED.value
                and approval.get("approval_status") == "active"
                and registry_state == "active"
                and self._as_utc(approval["expires_at"]) > as_of
            )
            records.append(
                {
                    "approval_id": approval["approval_id"],
                    "approval_status": approval["approval_status"],
                    "work_unit_id": approval["work_unit_id"],
                    "attempt_id": approval["attempt_id"],
                    "checkpoint_ref": approval["checkpoint_ref"],
                    "scope_digest": approval["scope_digest"],
                    "approval_registry_ref": approval["approval_registry_ref"],
                    "registry_state": registry_state,
                    "eligible_to_resume": eligible,
                    "review_action_id": approval["review_action_id"],
                }
            )
        records.sort(key=lambda item: item["approval_id"])
        return {
            "scope": "Point01_M5_6_durable_hitl_approval_control_plane_only",
            "case_id": case_id,
            "review_queue": records,
            "paused_count": sum(1 for record in records if record["eligible_to_resume"]),
            "worker_started": False,
            "model_call_count": 0,
            "external_call_count": 0,
        }

    def _require_checkpoint(self, tx: Any, *, case_id: str, checkpoint_ref: str, attempt_id: str) -> Mapping[str, Any]:
        checkpoint_id, checkpoint_version = self.facade._parse_artifact_reference(checkpoint_ref, None)
        if not checkpoint_id or checkpoint_version is None:
            raise MissingDependency("checkpoint_exact_version_required")
        artifact = tx.get_version("canonical_artifact_versions", checkpoint_id, checkpoint_version)
        if not artifact or artifact.get("case_id") != case_id or artifact.get("artifact_version_id") != checkpoint_ref:
            raise MissingDependency("hitl_checkpoint_not_found_or_scope_mismatch")
        if artifact.get("artifact_type") != "runtime_checkpoint" or artifact.get("producer_attempt_id") != attempt_id:
            raise MissingDependency("hitl_checkpoint_producer_or_type_mismatch")
        self.facade._validate_checkpoint_artifact_payload(artifact)
        return artifact

    def _require_registry(
        self,
        approval_id: str,
        *,
        scope_digest: str,
        at: datetime,
        expected_state: Literal["active", "revoked"],
        approval_registry_ref: str | None = None,
        approval_registry_digest: str | None = None,
        tx: Any | None = None,
        case_id: str | None = None,
    ) -> ApprovalRegistryRecord:
        record = self._approval_registry.get(approval_id)
        if tx is not None:
            persisted = tx.get_latest("canonical_hitl_registry_versions", approval_id)
            if persisted:
                if case_id is not None and persisted.get("case_id") != case_id:
                    raise HITLApprovalError("hitl_authoritative_registry_scope_mismatch")
                record = ApprovalRegistryRecord(approval_id=approval_id, approval_registry_ref=str(persisted["approval_registry_ref"]), scope_digest=str(persisted["scope_digest"]), approval_state=str(persisted["approval_state"]), expires_at=self._as_utc(persisted["expires_at"]))
        if not record:
            raise HITLApprovalError("hitl_authoritative_registry_record_required")
        if record.scope_digest != scope_digest or record.approval_state != expected_state:
            raise HITLApprovalError("hitl_authoritative_registry_scope_or_state_mismatch")
        if approval_registry_ref is not None and record.approval_registry_ref != approval_registry_ref:
            raise HITLApprovalError("hitl_authoritative_registry_ref_mismatch")
        if approval_registry_digest is not None and canonical_digest(record) != approval_registry_digest:
            raise HITLApprovalError("hitl_authoritative_registry_digest_mismatch")
        if expected_state == "active" and record.expires_at <= at:
            raise HITLApprovalError("hitl_approval_expired")
        return record

    @staticmethod
    def _scope_digest(command: CommandEnvelope, *, work_unit_id: str, attempt_id: str, checkpoint_ref: str) -> str:
        return canonical_digest(
            {
                "case_id": command.case_id,
                "work_unit_id": work_unit_id,
                "attempt_id": attempt_id,
                "checkpoint_ref": checkpoint_ref,
                "tenant_id": command.tenant_id,
                "project_id": command.project_id,
                "permission_snapshot_ref": command.permission_snapshot_ref,
            }
        )

    @staticmethod
    def _as_utc(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


HITL_GOVERNANCE_MODELS = (ApprovalRegistryRecord, HITLApprovalReceipt)
