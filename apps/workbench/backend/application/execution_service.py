from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sec_agent.canonical_runtime.facade import (
    IllegalStateTransition,
    MissingDependency,
    PlanningAuthorityViolation,
    PlanningConflict,
    PlanningNotFound,
    PlanningVersionConflict,
    RuntimeFacade,
    RuntimeFacadeError,
)
from sec_agent.canonical_runtime.feature_flags import FeatureFlagError
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.store import (
    IdempotencyConflict,
    StaleStateVersion,
    TransactionConflict,
)

from .case_service import CasePrincipal, CaseService


VT1_WORK_UNIT_TYPE = "p36_evidence_fixture_entry"
VT1_FENCING_TOKEN = "fixture-no-lease"
VT1_CANCEL_REASON = "analyst_cancelled_fixture_work_unit"


@dataclass(frozen=True)
class CreateWorkUnitDraft:
    work_unit_type: str
    expected_case_version: int
    input_head_digest: str
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class CancelWorkUnitDraft:
    expected_work_unit_version: int
    expected_state_version: int
    fencing_token: str
    actor_ref: str
    idempotency_key: str


class ExecutionServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class ExecutionService:
    """VT1 execution admission and canonical read-model projection boundary."""

    def __init__(self, facade: RuntimeFacade | None, *, unavailable_reason: str | None = None):
        self._facade = facade
        self._unavailable_reason = unavailable_reason

    @classmethod
    def from_case_service(cls, service: CaseService) -> "ExecutionService":
        facade = getattr(service, "_facade", None)
        if facade is None:
            return cls(None, unavailable_reason="explicit_fixture_root_required")
        return cls(facade)

    @classmethod
    def unavailable(cls, reason: str = "explicit_fixture_root_required") -> "ExecutionService":
        return cls(None, unavailable_reason=reason)

    def create_work_unit(
        self,
        case_id: str,
        draft: CreateWorkUnitDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "execution:write")
        self._require_actor(draft.actor_ref, principal)
        self._require_request_identity(case_id, draft.idempotency_key, trace_id)
        if draft.work_unit_type != VT1_WORK_UNIT_TYPE:
            raise ExecutionServiceError("work_unit_type_not_admitted", 403)

        case = self._case_row(case_id, principal)
        current_case_version = int(case["case_version"])
        if draft.expected_case_version != current_case_version:
            raise ExecutionServiceError(
                "version_conflict",
                409,
                expected_version=draft.expected_case_version,
                current_version=current_case_version,
            )

        planning = self._latest_planning(case_id, principal)
        if planning.get("review_status") != "accepted":
            raise ExecutionServiceError(
                "accepted_planning_checkpoint_required",
                409,
                review_status=planning.get("review_status"),
            )
        contract_version_id = str(planning["contract_version_id"])
        input_version_refs = (contract_version_id,)
        expected_digest = canonical_digest(input_version_refs)
        if draft.input_head_digest != expected_digest:
            raise ExecutionServiceError(
                "input_head_digest_mismatch",
                409,
                expected_input_head_digest=expected_digest,
            )

        work_unit_id = "wu_p02_5_" + canonical_digest(
            {
                "tenant_id": principal.tenant_id,
                "project_id": principal.project_id,
                "case_id": case_id,
                "contract_version_id": contract_version_id,
            }
        )[:24]
        existing_work_units = self._vt1_work_units(case_id, principal)
        if len(existing_work_units) > 1:
            raise ExecutionServiceError("vt1_work_unit_cardinality_violation", 409)
        if existing_work_units:
            existing = existing_work_units[0]
            if (
                existing.get("work_unit_id") != work_unit_id
                or existing.get("idempotency_key") != draft.idempotency_key
            ):
                raise ExecutionServiceError(
                    "vt1_work_unit_already_exists",
                    409,
                    work_unit_id=str(existing["work_unit_id"]),
                )
        envelope = self._command(
            command_type="CREATE_WORK_UNIT",
            case_id=case_id,
            actor_ref=draft.actor_ref,
            idempotency_key=draft.idempotency_key,
            expected_state_version=0,
            trace_id=trace_id,
            principal=principal,
            payload={
                "work_unit_id": work_unit_id,
                "work_unit_type": VT1_WORK_UNIT_TYPE,
                "target_refs": (case_id,),
                "input_version_refs": input_version_refs,
                "expected_case_version": draft.expected_case_version,
                "actor_ref": draft.actor_ref,
                "budget_ref": "budget:none",
                "max_attempts": 1,
                "retry_budget": 0,
                "retry_policy_ref": "retry:none",
                "queue_name": "point02.vt1.fixture",
            },
        )
        self._invoke(self._facade_or_raise().create_work_unit, envelope)
        return self._work_unit_view(case_id, principal)

    def list_work_units(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "execution:read")
        self._case_row(case_id, principal)
        return self._work_unit_view(case_id, principal)

    def cancel_work_unit(
        self,
        case_id: str,
        work_unit_id: str,
        draft: CancelWorkUnitDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "execution:write")
        self._require_actor(draft.actor_ref, principal)
        self._require_request_identity(case_id, draft.idempotency_key, trace_id)
        if not work_unit_id.strip():
            raise ExecutionServiceError("request_validation_error", 422, field="work_unit_id")
        if draft.fencing_token != VT1_FENCING_TOKEN:
            raise ExecutionServiceError("fixture_fencing_token_required", 409)

        self._case_row(case_id, principal)
        work_unit = self._work_unit_row(case_id, work_unit_id, principal)
        if work_unit.get("work_unit_type") != VT1_WORK_UNIT_TYPE:
            raise ExecutionServiceError("work_unit_not_admitted", 403, work_unit_id=work_unit_id)

        current_work_unit_version = int(work_unit["work_unit_version"])
        if draft.expected_work_unit_version != current_work_unit_version:
            raise ExecutionServiceError(
                "version_conflict",
                409,
                expected_version=draft.expected_work_unit_version,
                current_version=current_work_unit_version,
            )
        state = str(work_unit["state"])
        current_state_version = int(work_unit["state_version"])
        if state == "pending" and draft.expected_state_version != current_state_version:
            raise ExecutionServiceError(
                "version_conflict",
                409,
                expected_version=draft.expected_state_version,
                current_version=current_state_version,
            )
        if state not in {"pending", "cancelled"}:
            raise ExecutionServiceError(
                "fixture_work_unit_must_be_pending",
                409,
                current_state=state,
            )

        envelope = self._command(
            command_type="CANCEL_WORK_UNIT",
            case_id=case_id,
            actor_ref=draft.actor_ref,
            idempotency_key=draft.idempotency_key,
            expected_state_version=draft.expected_state_version,
            trace_id=trace_id,
            principal=principal,
            payload={
                "work_unit_id": work_unit_id,
                "expected_work_unit_version": draft.expected_work_unit_version,
                "expected_state_version": draft.expected_state_version,
                "fencing_token": VT1_FENCING_TOKEN,
                "actor_ref": draft.actor_ref,
                "terminal_reason": VT1_CANCEL_REASON,
            },
        )
        self._invoke(self._facade_or_raise().cancel_work_unit, envelope)
        return self._work_unit_view(case_id, principal)

    def get_activity(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "activity:read")
        case = self._case_row(case_id, principal)
        work_unit_ids = {
            str(row["work_unit_id"])
            for row in self._vt1_work_units(case_id, principal)
        }
        events = []
        for event in self._facade_or_raise().store.list_events():
            if str(event.get("work_unit_id") or "") not in work_unit_ids:
                continue
            event_type = str(event["event_type"])
            events.append(
                {
                    "event_id": str(event["event_id"]),
                    "sequence": int(event["sequence_no"]),
                    "event_type": event_type,
                    "occurred_at": str(event["occurred_at"]),
                    "typed_stop": VT1_CANCEL_REASON if event_type == "WORK_UNIT_CANCELLED" else None,
                }
            )
        return {
            "case_id": case_id,
            "case_version": int(case["case_version"]),
            "events": events,
        }

    def _work_unit_view(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        rows = self._vt1_work_units(case_id, principal)
        return {
            "case_id": case_id,
            "work_units": [
                {
                    "work_unit_id": str(row["work_unit_id"]),
                    "work_unit_version": int(row["work_unit_version"]),
                    "state_version": int(row["state_version"]),
                    "state": str(row["state"]),
                    "input_head_digest": str(row["input_head_digest"]),
                }
                for row in sorted(rows, key=lambda row: str(row["work_unit_id"]))
            ],
        }

    def _vt1_work_units(self, case_id: str, principal: CasePrincipal) -> list[Mapping[str, Any]]:
        return [
            row
            for row in self._facade_or_raise().store.list_latest("canonical_work_units", case_id=case_id)
            if row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and row.get("case_id") == case_id
            and row.get("work_unit_type") == VT1_WORK_UNIT_TYPE
        ]

    def _case_row(self, case_id: str, principal: CasePrincipal) -> Mapping[str, Any]:
        if not case_id.strip():
            raise ExecutionServiceError("request_validation_error", 422, field="case_id")
        case = self._facade_or_raise().store.get_latest("canonical_research_cases", case_id)
        if (
            not case
            or case.get("case_id") != case_id
            or case.get("tenant_id") != principal.tenant_id
            or case.get("project_id") != principal.project_id
        ):
            raise ExecutionServiceError("case_not_found", 404, case_id=case_id)
        return case

    def _work_unit_row(
        self,
        case_id: str,
        work_unit_id: str,
        principal: CasePrincipal,
    ) -> Mapping[str, Any]:
        row = self._facade_or_raise().store.get_latest("canonical_work_units", work_unit_id)
        if (
            not row
            or row.get("work_unit_id") != work_unit_id
            or row.get("case_id") != case_id
            or row.get("tenant_id") != principal.tenant_id
            or row.get("project_id") != principal.project_id
        ):
            raise ExecutionServiceError("work_unit_not_found", 404, work_unit_id=work_unit_id)
        return row

    def _latest_planning(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        try:
            return self._facade_or_raise().get_decision_surface(
                case_id,
                tenant_id=principal.tenant_id,
                project_id=principal.project_id,
            )
        except PlanningNotFound as exc:
            raise ExecutionServiceError(
                "accepted_planning_checkpoint_required",
                409,
            ) from exc
        except Exception as exc:
            raise self._service_error(exc) from exc

    def _command(
        self,
        *,
        command_type: str,
        case_id: str,
        actor_ref: str,
        idempotency_key: str,
        expected_state_version: int,
        trace_id: str,
        principal: CasePrincipal,
        payload: Mapping[str, Any],
    ) -> CommandEnvelope:
        return CommandEnvelope(
            command_id="p02_execution_" + canonical_digest(
                {
                    "command_type": command_type,
                    "case_id": case_id,
                    "idempotency_key": idempotency_key,
                }
            )[:24],
            command_type=command_type,
            tenant_id=principal.tenant_id,
            project_id=principal.project_id,
            case_id=case_id,
            actor_snapshot_ref=f"fixture_actor:{actor_ref}",
            permission_snapshot_ref=f"fixture_permissions:{principal.tenant_id}:{principal.actor_id}",
            policy_config_refs=("point02.p02_5.vt1.fixture.internal",),
            idempotency_key=idempotency_key,
            expected_state_version=expected_state_version,
            correlation_id=trace_id,
            requested_at=utc_now(),
            payload=dict(payload),
        )

    def _facade_or_raise(self) -> RuntimeFacade:
        if self._facade is None:
            raise ExecutionServiceError(
                "operation_not_admitted",
                403,
                reason_detail=self._unavailable_reason,
            )
        return self._facade

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if (
            not principal.tenant_id
            or not principal.project_id
            or not principal.actor_id
            or permission not in principal.permissions
        ):
            raise ExecutionServiceError("permission_denied", 403, required_permission=permission)

    @staticmethod
    def _require_actor(actor_ref: str, principal: CasePrincipal) -> None:
        if actor_ref != principal.actor_id:
            raise ExecutionServiceError("actor_scope_mismatch", 403)

    @staticmethod
    def _require_request_identity(case_id: str, idempotency_key: str, trace_id: str) -> None:
        if not case_id.strip() or not idempotency_key.strip() or not trace_id.strip():
            raise ExecutionServiceError("request_validation_error", 422)

    def _invoke(self, method: Any, envelope: CommandEnvelope) -> None:
        try:
            method(envelope)
        except Exception as exc:
            raise self._service_error(exc) from exc

    @staticmethod
    def _service_error(error: Exception) -> ExecutionServiceError:
        if isinstance(error, ExecutionServiceError):
            return error
        if isinstance(error, IdempotencyConflict):
            return ExecutionServiceError("idempotency_conflict", 409)
        if isinstance(error, (StaleStateVersion, TransactionConflict)):
            return ExecutionServiceError("version_conflict", 409, conflict_reason=str(error))
        if isinstance(error, PlanningVersionConflict):
            return ExecutionServiceError("version_conflict", 409, **error.details)
        if isinstance(error, PlanningConflict):
            return ExecutionServiceError(str(error), 409, **error.details)
        if isinstance(error, (PlanningNotFound, MissingDependency)):
            return ExecutionServiceError(str(error), 404, **error.details)
        if isinstance(error, (PlanningAuthorityViolation, FeatureFlagError)):
            return ExecutionServiceError("operation_not_admitted", 403, cause=str(error))
        if isinstance(error, IllegalStateTransition):
            return ExecutionServiceError(str(error), 409, **error.details)
        if isinstance(error, (KeyError, ValueError)):
            return ExecutionServiceError("request_validation_error", 422, cause=str(error))
        if isinstance(error, RuntimeFacadeError):
            return ExecutionServiceError("execution_operation_rejected", 409, cause=str(error))
        return ExecutionServiceError("execution_backend_unavailable", 503)
