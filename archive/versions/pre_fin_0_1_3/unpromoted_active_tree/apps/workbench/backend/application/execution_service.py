from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

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
AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE = "agent_fixture_shadow_entry"
BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE = "bounded_agent_internal_entry"
FIN01_ADMITTED_WORK_UNIT_TYPES = frozenset(
    (VT1_WORK_UNIT_TYPE, AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE)
)
VT1_FENCING_TOKEN = "fixture-no-lease"
VT1_CANCEL_REASON = "analyst_cancelled_fixture_work_unit"
PRIVATE_TRACE_KEY_TOKENS = (
    "chain_of_thought",
    "internal_monologue",
    "hidden_thought",
    "private_thought",
    "private_reasoning",
    "hidden_reasoning",
    "reasoning_trace",
    "scratchpad",
)


def predict_work_unit_id(
    *,
    tenant_id: str,
    project_id: str,
    case_id: str,
    contract_version_id: str,
    work_unit_type: str,
    execution_identity: str,
) -> str:
    """Predict the canonical WorkUnit identity without reading or writing state."""

    work_unit_identity = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "case_id": case_id,
        "contract_version_id": contract_version_id,
    }
    if work_unit_type != VT1_WORK_UNIT_TYPE:
        if not execution_identity.strip():
            raise ValueError("non_vt1_execution_identity_required")
        work_unit_identity["work_unit_type"] = work_unit_type
        work_unit_identity["execution_identity"] = execution_identity
    return "wu_p02_5_" + canonical_digest(work_unit_identity)[:24]


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


class QueuedWorkUnitRuntime(Protocol):
    @property
    def admitted_work_unit_types(self) -> frozenset[str]: ...

    def dispatch_once(
        self,
        command: CommandEnvelope,
        principal: CasePrincipal,
    ) -> dict[str, Any]: ...


class ExecutionService:
    """Execution admission and canonical read-model projection boundary."""

    def __init__(
        self,
        facade: RuntimeFacade | None,
        *,
        runtime: QueuedWorkUnitRuntime | None = None,
        unavailable_reason: str | None = None,
    ):
        self._facade = facade
        self._runtime = runtime
        self._unavailable_reason = unavailable_reason
        runtime_types = (
            frozenset(runtime.admitted_work_unit_types)
            if runtime is not None
            else FIN01_ADMITTED_WORK_UNIT_TYPES
        )
        if not FIN01_ADMITTED_WORK_UNIT_TYPES.issubset(runtime_types):
            raise ValueError("runtime_must_preserve_fin01_baseline_work_unit_types")
        self._admitted_work_unit_types = runtime_types

    @classmethod
    def from_case_service(
        cls,
        service: CaseService,
        *,
        runtime: QueuedWorkUnitRuntime | None = None,
    ) -> "ExecutionService":
        facade = getattr(service, "_facade", None)
        if facade is None:
            return cls(None, unavailable_reason="explicit_fixture_root_required")
        return cls(facade, runtime=runtime)

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
        if draft.work_unit_type not in self._admitted_work_unit_types:
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

        work_unit_id = predict_work_unit_id(
            tenant_id=principal.tenant_id,
            project_id=principal.project_id,
            case_id=case_id,
            contract_version_id=contract_version_id,
            work_unit_type=draft.work_unit_type,
            execution_identity=draft.idempotency_key,
        )
        existing_work_units = self._work_units_by_type(
            case_id, principal, draft.work_unit_type
        )
        if draft.work_unit_type == VT1_WORK_UNIT_TYPE and len(existing_work_units) > 1:
            raise ExecutionServiceError("vt1_work_unit_cardinality_violation", 409)
        matching_identity = [
            row
            for row in existing_work_units
            if row.get("idempotency_key") == draft.idempotency_key
        ]
        if len(matching_identity) > 1:
            raise ExecutionServiceError("work_unit_execution_identity_ambiguous", 409)
        if draft.work_unit_type == VT1_WORK_UNIT_TYPE and existing_work_units:
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
        elif matching_identity and matching_identity[0].get("work_unit_id") != work_unit_id:
            raise ExecutionServiceError(
                "work_unit_execution_identity_conflict",
                409,
                work_unit_id=str(matching_identity[0]["work_unit_id"]),
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
                "work_unit_type": draft.work_unit_type,
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

    @property
    def background_dispatch_enabled(self) -> bool:
        return self._runtime is not None

    @staticmethod
    def dispatchable_work_unit_id(view: Mapping[str, Any]) -> str | None:
        pending = [
            str(row.get("work_unit_id") or "")
            for row in view.get("work_units", ())
            if isinstance(row, Mapping) and row.get("state") == "pending"
        ]
        return pending[0] if len(pending) == 1 and pending[0] else None

    def pending_work_unit_id_for_type(
        self,
        case_id: str,
        work_unit_type: str,
        principal: CasePrincipal,
        *,
        idempotency_key: str | None = None,
    ) -> str | None:
        pending = [
            str(row.get("work_unit_id") or "")
            for row in self._work_units_by_type(case_id, principal, work_unit_type)
            if row.get("state") == "pending"
            and (
                idempotency_key is None
                or row.get("idempotency_key") == idempotency_key
            )
        ]
        return pending[0] if len(pending) == 1 and pending[0] else None

    def dispatch_queued_work_unit(
        self,
        case_id: str,
        work_unit_id: str,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        if self._runtime is None:
            return {"status": "not_dispatched", "reason": "runtime_not_configured"}
        self._require_permission(principal, "execution:write")
        work_unit = self._work_unit_row(case_id, work_unit_id, principal)
        if work_unit.get("state") != "pending":
            return {
                "status": "not_dispatched",
                "work_unit_id": work_unit_id,
                "work_unit_state": str(work_unit.get("state") or "unknown"),
            }
        envelope = self._command(
            command_type="DISPATCH_QUEUED_WORK_UNIT",
            case_id=case_id,
            actor_ref=principal.actor_id,
            idempotency_key=f"{work_unit['idempotency_key']}:dispatch",
            expected_state_version=int(work_unit.get("state_version") or 0),
            trace_id=trace_id,
            principal=principal,
            payload={"work_unit_id": work_unit_id},
        )
        return self._runtime.dispatch_once(envelope, principal)

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
        if work_unit.get("work_unit_type") not in self._admitted_work_unit_types:
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

    def get_research_run_projection(
        self,
        case_id: str,
        principal: CasePrincipal,
    ) -> dict[str, Any]:
        """Project exact Run/Event/Artifact truth without exposing private reasoning."""

        self._require_permission(principal, "execution:read")
        self._case_row(case_id, principal)
        facade = self._facade_or_raise()
        work_units = {
            str(row["work_unit_id"]): row
            for row in self._vt1_work_units(case_id, principal)
        }
        attempts = {
            str(row["attempt_id"]): row
            for row in facade.store.list_latest("canonical_attempts", case_id=case_id)
            if row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and str(row.get("work_unit_id") or "") in work_units
        }
        runs = [
            row
            for row in facade.store.list_latest(
                "canonical_research_run_versions", case_id=case_id
            )
            if row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and str(row.get("work_unit_id") or "") in work_units
            and str(row.get("attempt_id") or "") in attempts
        ]
        artifacts_by_attempt: dict[str, list[Mapping[str, Any]]] = {}
        for artifact in facade.store.list_latest(
            "canonical_artifact_versions", case_id=case_id
        ):
            attempt_id = str(artifact.get("producer_attempt_id") or "")
            if (
                artifact.get("tenant_id") == principal.tenant_id
                and artifact.get("project_id") == principal.project_id
                and attempt_id in attempts
            ):
                artifacts_by_attempt.setdefault(attempt_id, []).append(artifact)

        return {
            "case_id": case_id,
            "runs": [
                self._research_run_projection_item(
                    row,
                    work_unit=work_units[str(row["work_unit_id"])],
                    attempt=attempts[str(row["attempt_id"])],
                    artifacts=artifacts_by_attempt.get(str(row["attempt_id"]), []),
                )
                for row in sorted(
                    runs,
                    key=lambda item: (
                        str(item.get("started_at") or ""),
                        str(item.get("research_run_id") or ""),
                    ),
                    reverse=True,
                )
            ],
            "private_chain_of_thought_included": False,
        }

    def _research_run_projection_item(
        self,
        run: Mapping[str, Any],
        *,
        work_unit: Mapping[str, Any],
        attempt: Mapping[str, Any],
        artifacts: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        facade = self._facade_or_raise()
        research_run_id = str(run["research_run_id"])
        projected_events: list[dict[str, Any]] = []
        for event in facade.store.list_events(research_run_id):
            if (
                str(event.get("work_unit_id") or "") != str(run["work_unit_id"])
                or str(event.get("attempt_id") or "") != str(run["attempt_id"])
            ):
                raise ExecutionServiceError(
                    "research_run_projection_lineage_invalid",
                    409,
                    event_id=str(event.get("event_id") or ""),
                )
            safe_payload, redacted = self._without_private_trace_fields(
                event.get("payload") or {}
            )
            projected_events.append(
                {
                    "event_id": str(event["event_id"]),
                    "sequence": int(event["sequence_no"]),
                    "event_type": str(event["event_type"]),
                    "occurred_at": str(event["occurred_at"]),
                    "causation_event_id": event.get("causation_event_id"),
                    "details": safe_payload,
                    "redacted_fields": redacted,
                    "private_chain_of_thought_included": False,
                }
            )

        projected_artifacts: list[dict[str, Any]] = []
        output_refs = set(attempt.get("output_refs") or ())
        for artifact in sorted(
            artifacts, key=lambda item: (str(item.get("artifact_type")), str(item.get("artifact_version_id")))
        ):
            if str(artifact["artifact_version_id"]) not in output_refs:
                continue
            artifact_view = facade.get_artifact_version(
                str(artifact["artifact_version_id"]), include_payload=True
            )
            safe_payload, redacted = self._without_private_trace_fields(
                artifact_view.get("payload") or {}
            )
            projected_artifacts.append(
                {
                    "artifact_version_id": str(artifact["artifact_version_id"]),
                    "artifact_type": str(artifact["artifact_type"]),
                    "producer_attempt_id": str(artifact["producer_attempt_id"]),
                    "current_status": str(artifact["current_status"]),
                    "object_digest": str(artifact["object_digest"]),
                    "input_refs": list(artifact.get("input_refs") or ()),
                    "payload": safe_payload,
                    "payload_exact": not redacted,
                    "redacted_fields": redacted,
                }
            )
        if {row["artifact_version_id"] for row in projected_artifacts} != output_refs:
            raise ExecutionServiceError(
                "research_run_projection_artifact_lineage_invalid",
                409,
                research_run_id=research_run_id,
            )

        return {
            "research_run_id": research_run_id,
            "research_run_version_id": str(run["research_run_version_id"]),
            "work_unit_id": str(run["work_unit_id"]),
            "work_unit_type": str(work_unit["work_unit_type"]),
            "attempt_id": str(run["attempt_id"]),
            "execution_profile_version_ref": str(run["execution_profile_version_ref"]),
            "state": str(run["state"]),
            "started_at": str(run["started_at"]),
            "ended_at": str(run["ended_at"]) if run.get("ended_at") else None,
            "terminal_reason": run.get("terminal_reason") or attempt.get("terminal_reason"),
            "output_refs": list(attempt.get("output_refs") or ()),
            "events": projected_events,
            "artifacts": projected_artifacts,
        }

    @classmethod
    def _without_private_trace_fields(
        cls,
        value: Any,
        *,
        path: str = "$",
    ) -> tuple[Any, list[str]]:
        if isinstance(value, Mapping):
            safe: dict[str, Any] = {}
            redacted: list[str] = []
            for raw_key, raw_value in value.items():
                key = str(raw_key)
                normalized = key.lower().replace("-", "_")
                child_path = f"{path}.{key}"
                if any(token in normalized for token in PRIVATE_TRACE_KEY_TOKENS):
                    redacted.append(child_path)
                    continue
                child, child_redacted = cls._without_private_trace_fields(
                    raw_value, path=child_path
                )
                safe[key] = child
                redacted.extend(child_redacted)
            return safe, redacted
        if isinstance(value, (list, tuple)):
            safe_items: list[Any] = []
            redacted = []
            for index, item in enumerate(value):
                child, child_redacted = cls._without_private_trace_fields(
                    item, path=f"{path}[{index}]"
                )
                safe_items.append(child)
                redacted.extend(child_redacted)
            return safe_items, redacted
        return value, []

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
            and row.get("work_unit_type") in self._admitted_work_unit_types
        ]

    def _work_units_by_type(
        self,
        case_id: str,
        principal: CasePrincipal,
        work_unit_type: str,
    ) -> list[Mapping[str, Any]]:
        return [
            row
            for row in self._vt1_work_units(case_id, principal)
            if row.get("work_unit_type") == work_unit_type
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
