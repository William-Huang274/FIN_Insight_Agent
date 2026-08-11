from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sec_agent.canonical_runtime.facade import (
    PlanningAuthorityViolation,
    PlanningConflict,
    PlanningNotFound,
    PlanningVersionConflict,
    RuntimeFacade,
    RuntimeFacadeError,
)
from sec_agent.canonical_runtime.feature_flags import FeatureFlagError
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.store import IdempotencyConflict, TransactionConflict

from .case_service import CasePrincipal, CaseService


@dataclass(frozen=True)
class CompileDecisionSurfaceDraft:
    expected_case_version: int
    expected_summary_version: int
    compiler_policy_ref: str
    pack_selection_ref: str
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class ReviseDecisionSurfaceDraft:
    expected_case_version: int
    expected_decision_surface_contract_version: int
    expected_checkpoint_version: int
    changes: tuple[Mapping[str, str], ...]
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class PlanningCheckpointDecisionDraft:
    decision: str
    expected_case_version: int
    expected_decision_surface_contract_version: int
    expected_checkpoint_version: int
    actor_ref: str
    idempotency_key: str


class PlanningServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class PlanningService:
    """Workbench permission boundary for the internal P02.4 fixture workflow."""

    def __init__(self, facade: RuntimeFacade | None, *, unavailable_reason: str | None = None):
        self._facade = facade
        self._unavailable_reason = unavailable_reason

    @classmethod
    def from_case_service(cls, service: CaseService) -> "PlanningService":
        facade = getattr(service, "_facade", None)
        if facade is None:
            return cls(None, unavailable_reason="explicit_fixture_root_required")
        return cls(facade)

    @classmethod
    def unavailable(cls, reason: str = "explicit_fixture_root_required") -> "PlanningService":
        return cls(None, unavailable_reason=reason)

    def compile_decision_surface(
        self,
        case_id: str,
        draft: CompileDecisionSurfaceDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "planning:write")
        self._require_actor(draft.actor_ref, principal)
        envelope = self._command(
            command_type="COMPILE_DECISION_SURFACE",
            case_id=case_id,
            actor_ref=draft.actor_ref,
            idempotency_key=draft.idempotency_key,
            expected_state_version=draft.expected_case_version,
            trace_id=trace_id,
            principal=principal,
            payload={
                "expected_case_version": draft.expected_case_version,
                "expected_summary_version": draft.expected_summary_version,
                "compiler_policy_ref": draft.compiler_policy_ref,
                "pack_selection_ref": draft.pack_selection_ref,
                "actor_ref": draft.actor_ref,
            },
        )
        return self._invoke(self._facade_or_raise().compile_decision_surface, envelope)

    def revise_decision_surface(
        self,
        case_id: str,
        draft: ReviseDecisionSurfaceDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "planning:write")
        self._require_actor(draft.actor_ref, principal)
        envelope = self._command(
            command_type="REVISE_DECISION_SURFACE",
            case_id=case_id,
            actor_ref=draft.actor_ref,
            idempotency_key=draft.idempotency_key,
            expected_state_version=draft.expected_decision_surface_contract_version,
            trace_id=trace_id,
            principal=principal,
            payload={
                "expected_case_version": draft.expected_case_version,
                "expected_decision_surface_contract_version": draft.expected_decision_surface_contract_version,
                "expected_checkpoint_version": draft.expected_checkpoint_version,
                "changes": [dict(change) for change in draft.changes],
                "actor_ref": draft.actor_ref,
            },
        )
        return self._invoke(self._facade_or_raise().revise_decision_surface, envelope)

    def review_planning_checkpoint(
        self,
        case_id: str,
        draft: PlanningCheckpointDecisionDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "planning:review")
        self._require_actor(draft.actor_ref, principal)
        envelope = self._command(
            command_type="REVIEW_PLANNING_CHECKPOINT",
            case_id=case_id,
            actor_ref=draft.actor_ref,
            idempotency_key=draft.idempotency_key,
            expected_state_version=draft.expected_checkpoint_version,
            trace_id=trace_id,
            principal=principal,
            payload={
                "decision": draft.decision,
                "expected_case_version": draft.expected_case_version,
                "expected_decision_surface_contract_version": draft.expected_decision_surface_contract_version,
                "expected_checkpoint_version": draft.expected_checkpoint_version,
                "actor_ref": draft.actor_ref,
            },
        )
        return self._invoke(self._facade_or_raise().review_planning_checkpoint, envelope)

    def get_decision_surface(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "planning:read")
        try:
            return self._facade_or_raise().get_decision_surface(
                case_id,
                tenant_id=principal.tenant_id,
                project_id=principal.project_id,
            )
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
        if not case_id.strip() or not idempotency_key.strip() or not trace_id.strip():
            raise PlanningServiceError("request_validation_error", 422)
        actor_snapshot_ref = actor_ref if actor_ref.startswith("fixture_actor:") else f"fixture_actor:{actor_ref}"
        command_id = "p02_planning_" + canonical_digest(
            {
                "command_type": command_type,
                "case_id": case_id,
                "idempotency_key": idempotency_key,
            }
        )[:24]
        if "compiler_policy_ref" in payload and "pack_selection_ref" in payload:
            contract_digest = self._facade_or_raise().planning_fixture_contract_digest(
                str(payload["compiler_policy_ref"]),
                str(payload["pack_selection_ref"]),
            )
        else:
            contract_digest = self._facade_or_raise().planning_fixture_contract_digest_for_case(
                case_id
            )
        return CommandEnvelope(
            command_id=command_id,
            command_type=command_type,
            tenant_id=principal.tenant_id,
            project_id=principal.project_id,
            case_id=case_id,
            actor_snapshot_ref=actor_snapshot_ref,
            permission_snapshot_ref=f"fixture_permissions:{principal.tenant_id}:{principal.actor_id}",
            policy_config_refs=(
                "point02.p02_4.fixture.internal",
                "contract:" + contract_digest,
            ),
            idempotency_key=idempotency_key,
            expected_state_version=expected_state_version,
            correlation_id=trace_id,
            requested_at=utc_now(),
            payload=dict(payload),
        )

    def _facade_or_raise(self) -> RuntimeFacade:
        if self._facade is None:
            raise PlanningServiceError(
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
            raise PlanningServiceError("permission_denied", 403, required_permission=permission)

    @staticmethod
    def _require_actor(actor_ref: str, principal: CasePrincipal) -> None:
        allowed = {principal.actor_id, f"fixture_actor:{principal.actor_id}"}
        if actor_ref not in allowed:
            raise PlanningServiceError("actor_scope_mismatch", 403)

    def _invoke(self, method: Any, envelope: CommandEnvelope) -> dict[str, Any]:
        try:
            return method(envelope)
        except Exception as exc:
            raise self._service_error(exc) from exc

    @staticmethod
    def _service_error(error: Exception) -> PlanningServiceError:
        if isinstance(error, PlanningServiceError):
            return error
        if isinstance(error, IdempotencyConflict):
            return PlanningServiceError("idempotency_conflict", 409)
        if isinstance(error, TransactionConflict):
            return PlanningServiceError("transaction_conflict", 409)
        if isinstance(error, PlanningVersionConflict):
            return PlanningServiceError(
                "version_conflict",
                409,
                conflict_reason=str(error),
                **error.details,
            )
        if isinstance(error, PlanningConflict):
            return PlanningServiceError(str(error), 409, **error.details)
        if isinstance(error, PlanningNotFound):
            return PlanningServiceError(str(error), 404, **error.details)
        if isinstance(error, PlanningAuthorityViolation):
            return PlanningServiceError(str(error), 403, **error.details)
        if isinstance(error, FeatureFlagError):
            return PlanningServiceError("operation_not_admitted", 403, cause=str(error))
        if isinstance(error, (KeyError, ValueError)):
            return PlanningServiceError("request_validation_error", 422, cause=str(error))
        if isinstance(error, RuntimeFacadeError):
            return PlanningServiceError("planning_operation_rejected", 403, cause=str(error))
        return PlanningServiceError("planning_backend_unavailable", 503)
