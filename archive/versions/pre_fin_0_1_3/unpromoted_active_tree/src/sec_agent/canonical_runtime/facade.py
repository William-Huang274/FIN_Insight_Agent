from __future__ import annotations

from copy import deepcopy
import json
import re
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from .failure_observation_policy import (
    is_registered_failure_observation,
    normalize_optional_failure_observation,
)
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
    ResearchRunState,
    ResearchRunVersion,
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
PROVIDER_OUTPUT_CAPTURE_POLICY_REF = (
    "fin01.s3.provider_output_capture.assistant_final_text_only:v1"
)
PROVIDER_OUTPUT_CAPTURE_SCHEMA_REF = "fin01.provider_output_capture:v1"
PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF = (
    "fin01.runtime.provider_interaction_audit_capture:v2"
)
PROVIDER_INTERACTION_AUDIT_CAPTURE_SCHEMA_REF = (
    "fin01.provider_interaction_audit_capture:v2"
)
PROVIDER_OUTPUT_CAPTURE_SCHEMA_REFS = {
    PROVIDER_OUTPUT_CAPTURE_POLICY_REF: PROVIDER_OUTPUT_CAPTURE_SCHEMA_REF,
    PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF: (
        PROVIDER_INTERACTION_AUDIT_CAPTURE_SCHEMA_REF
    ),
}
MAX_PROVIDER_OUTPUT_CAPTURE_COUNT = 12
MAX_PROVIDER_OUTPUT_CAPTURE_BYTES = 131_072
MAX_PROVIDER_OUTPUT_CAPTURE_TOTAL_BYTES = 524_288
MAX_PROVIDER_INTERACTION_AUDIT_CAPTURE_BYTES = 524_288
MAX_PROVIDER_INTERACTION_AUDIT_CAPTURE_TOTAL_BYTES = 4_194_304
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


_SECRET_SAFE_BOUNDED_FAILURE_CODE = re.compile(r"^[a-z0-9_:.-]{1,256}$")
_BOUNDED_FAILURE_CODE_NAMESPACES = (
    "bounded_agent_",
    "s3_bounded_",
    "s4_",
)


def _is_secret_safe_bounded_failure_code(value: object) -> bool:
    """Accept only typed, deterministic bounded-runtime failure identifiers."""

    return (
        isinstance(value, str)
        and value.startswith(_BOUNDED_FAILURE_CODE_NAMESPACES)
        and _SECRET_SAFE_BOUNDED_FAILURE_CODE.fullmatch(value) is not None
    )


_CAPTURE_SECRET_PATTERNS = (
    re.compile(r"(?i)\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}"),
    re.compile(
        r"(?i)\b(?:authorization|proxy-authorization)\s*:\s*\S+"
    ),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|password|cookie)\s*[:=]\s*"
        r"[\"']?[A-Za-z0-9._~+/-]{16,}"
    ),
)


def _capture_contains_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            _capture_contains_secret(key) or _capture_contains_secret(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_capture_contains_secret(item) for item in value)
    if not isinstance(value, str):
        return False
    return any(pattern.search(value) for pattern in _CAPTURE_SECRET_PATTERNS)


def _validate_provider_output_captures(value: object) -> list[dict[str, Any]]:
    """Validate versioned restricted interaction captures before object write."""

    if value is None:
        return []
    if not isinstance(value, list) or not (
        1 <= len(value) <= MAX_PROVIDER_OUTPUT_CAPTURE_COUNT
    ):
        raise ArtifactValidationError("provider_output_capture_cardinality_invalid")
    v1_required_keys = {
        "capture_policy_ref",
        "capture_sequence",
        "stage",
        "call_id",
        "provider",
        "model",
        "provider_status",
        "finish_reason",
        "assistant_output_text",
        "assistant_output_present",
        "raw_provider_response_included",
        "private_reasoning_included",
    }
    v2_required_keys = v1_required_keys | {
        "model_visible_request",
        "model_visible_request_digest",
        "nonsecret_inference_arguments",
        "nonsecret_inference_arguments_digest",
        "provider_route",
        "provider_route_digest",
        "validator_match_index",
        "raw_request_envelope_included",
        "credentials_included",
    }
    allowed_inference_keys = {
        "api_surface",
        "tools",
        "tool_choice",
        "response_format",
        "temperature",
        "max_tokens",
        "max_output_tokens",
        "timeout_seconds",
        "stream",
        "enable_thinking",
        "reasoning_effort",
        "text",
        "reasoning",
    }
    allowed_semantic_classes = {
        "reporting_period_label",
        "request_local_identifier",
        "unknown_reporting_period_label",
        "financial_amount",
        "percentage",
        "measurement",
        "material_numeric_value",
    }
    rows: list[dict[str, Any]] = []
    total_bytes = 0
    policy_refs: set[str] = set()
    for expected_sequence, raw in enumerate(value, 1):
        if not isinstance(raw, Mapping):
            raise ArtifactValidationError("provider_output_capture_shape_invalid")
        row = dict(raw)
        policy_ref = str(row.get("capture_policy_ref") or "")
        policy_refs.add(policy_ref)
        required_keys = (
            v1_required_keys
            if policy_ref == PROVIDER_OUTPUT_CAPTURE_POLICY_REF
            else v2_required_keys
            if policy_ref == PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            else set()
        )
        if not required_keys or set(row) != required_keys:
            raise ArtifactValidationError("provider_output_capture_shape_invalid")
        text = row.get("assistant_output_text")
        text_bytes = len(text.encode("utf-8")) if isinstance(text, str) else -1
        output_present = row.get("assistant_output_present")
        if (
            row.get("capture_sequence") != expected_sequence
            or not all(
                isinstance(row.get(key), str) and str(row[key]).strip()
                for key in ("stage", "call_id", "provider", "model")
            )
            or not isinstance(row.get("provider_status"), str)
            or not isinstance(row.get("finish_reason"), str)
            or not isinstance(text, str)
            or type(output_present) is not bool
            or (output_present is False and text != "")
            or row.get("raw_provider_response_included") is not False
            or row.get("private_reasoning_included") is not False
            or text_bytes < 0
            or text_bytes > MAX_PROVIDER_OUTPUT_CAPTURE_BYTES
        ):
            raise ArtifactValidationError("provider_output_capture_contract_invalid")
        row_bytes = text_bytes
        if policy_ref == PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF:
            request = row.get("model_visible_request")
            arguments = row.get("nonsecret_inference_arguments")
            route = row.get("provider_route")
            match_index = row.get("validator_match_index")
            request_valid = (
                isinstance(request, list)
                and 1 <= len(request) <= 8
                and all(
                    isinstance(item, Mapping)
                    and set(item) == {"role", "content"}
                    and item.get("role")
                    in {"system", "developer", "user"}
                    and isinstance(item.get("content"), str)
                    for item in request
                )
            )
            arguments_valid = (
                isinstance(arguments, Mapping)
                and set(arguments).issubset(allowed_inference_keys)
                and arguments.get("api_surface")
                in {"chat_completions", "responses"}
            )
            route_valid = (
                isinstance(route, Mapping)
                and set(route) == {"base_url", "request_path"}
                and isinstance(route.get("base_url"), str)
                and re.fullmatch(
                    r"https?://[^/?#@\s]+(?::\d+)?"
                    r"(?:/[A-Za-z0-9._~!$&'()*+,;=:%-]*)*",
                    route["base_url"],
                )
                is not None
                and route.get("request_path")
                in {"/chat/completions", "/responses"}
            )
            index_valid = (
                isinstance(match_index, list)
                and len(match_index) <= 64
                and all(
                    isinstance(item, Mapping)
                    and set(item)
                    == {
                        "validator_rule_code",
                        "field_path",
                        "semantic_class",
                        "terminal",
                        "raw_match_persisted",
                    }
                    and item.get("validator_rule_code")
                    == "material_numeric_provider_narrative_boundary_v2"
                    and isinstance(item.get("field_path"), str)
                    and re.fullmatch(
                        r"\$(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+",
                        str(item.get("field_path")),
                    )
                    is not None
                    and item.get("semantic_class")
                    in allowed_semantic_classes
                    and type(item.get("terminal")) is bool
                    and item.get("raw_match_persisted") is False
                    for item in match_index
                )
            )
            if (
                not request_valid
                or not arguments_valid
                or not route_valid
                or not index_valid
                or row.get("model_visible_request_digest")
                != canonical_digest(request)
                or row.get("nonsecret_inference_arguments_digest")
                != canonical_digest(arguments)
                or row.get("provider_route_digest")
                != canonical_digest(route)
                or row.get("raw_request_envelope_included") is not False
                or row.get("credentials_included") is not False
                or _capture_contains_secret(
                    {
                        "assistant_output_text": text,
                        "model_visible_request": request,
                        "nonsecret_inference_arguments": arguments,
                        "provider_route": route,
                    }
                )
            ):
                raise ArtifactValidationError(
                    "provider_interaction_audit_capture_contract_invalid"
                )
            row_bytes = len(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if row_bytes > MAX_PROVIDER_INTERACTION_AUDIT_CAPTURE_BYTES:
                raise ArtifactValidationError(
                    "provider_interaction_audit_capture_bytes_exceeded"
                )
        total_bytes += row_bytes
        rows.append(row)
    if len(policy_refs) != 1:
        raise ArtifactValidationError("provider_output_capture_policy_mixed")
    policy_ref = next(iter(policy_refs))
    total_limit = (
        MAX_PROVIDER_OUTPUT_CAPTURE_TOTAL_BYTES
        if policy_ref == PROVIDER_OUTPUT_CAPTURE_POLICY_REF
        else MAX_PROVIDER_INTERACTION_AUDIT_CAPTURE_TOTAL_BYTES
    )
    if total_bytes > total_limit:
        raise ArtifactValidationError("provider_output_capture_total_bytes_exceeded")
    return rows


def _provider_output_capture_payloads(
    captures: Sequence[Mapping[str, Any]],
    *,
    case_id: str,
    work_unit_id: str,
    attempt_id: str,
    research_run_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            "schema_ref": PROVIDER_OUTPUT_CAPTURE_SCHEMA_REFS[
                str(row["capture_policy_ref"])
            ],
            "access_class": "internal_restricted_run_audit",
            "retention_class": "follow_research_run_retention",
            "case_id": case_id,
            "work_unit_id": work_unit_id,
            "attempt_id": attempt_id,
            "research_run_id": research_run_id,
            **dict(row),
        }
        for row in captures
    ]


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
        "RESEARCH_RUN_STARTED",
        "AGENT_DEFINITION_VERSIONS_SELECTED",
        "SKILL_PACK_CONSUMPTION_RECORDED",
        "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
        "RESEARCH_LEAD_FIXTURE_COMPLETED",
        "SPECIALIST_FIXTURE_COMPLETED",
        "TOOL_FIXTURE_OBSERVATION_RECORDED",
        "GRAPH_FIXTURE_OBSERVATION_RECORDED",
        "WRITER_FIXTURE_COMPLETED",
        "VERIFIER_FIXTURE_COMPLETED",
        "RESEARCH_RUN_COMPLETED",
        "RESEARCH_RUN_FAILED",
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
            task_run_id = str(command.payload.get("task_run_id") or "") or None
            events = []
            events.append(
                self._event(
                    tx,
                    event_command,
                    "WORK_UNIT_STARTED",
                    {"work_unit_id": work_unit_id, "attempt_no": attempt_no, "queue_name": queue_name},
                    task_run_id=task_run_id,
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                )
            )
            tx.append_event(events[-1])
            events.append(
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
                    task_run_id=task_run_id,
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                )
            )
            tx.append_event(events[-1])
            events.append(
                self._event(
                    tx,
                    event_command,
                    "SCHEDULER_LEASE_ACQUIRED",
                    self._lease_event_payload(attempt, queue_name=queue_name),
                    task_run_id=task_run_id,
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                )
            )
            tx.append_event(events[-1])
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
                        task_run_id=task_run_id,
                        work_unit_id=work_unit_id,
                        attempt_id=attempt_id,
                    )
                )
                tx.append_event(events[-1])
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

    def start_research_run(self, command: CommandEnvelope) -> ResultEnvelope:
        """Bind one exact running Attempt to its single immutable ResearchRun identity."""

        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        research_run_id = str(command.payload.get("research_run_id") or "")
        profile_ref = str(command.payload.get("execution_profile_version_ref") or "")
        if not work_unit_id or not attempt_id or not research_run_id or not profile_ref:
            raise MissingDependency("research_run_identity_required")
        scope_key, payload_digest, _ = self._idempotency(command, research_run_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            work_unit, attempt = self._require_running_execution(
                tx, command, case_id, work_unit_id, attempt_id
            )
            sibling_runs = [
                row
                for row in tx.list_latest("canonical_research_run_versions", case_id=case_id)
                if row.get("attempt_id") == attempt_id
            ]
            if sibling_runs:
                raise IllegalStateTransition("attempt_research_run_identity_already_bound")
            input_refs = tuple(str(value) for value in attempt.get("input_refs", ()))
            if input_refs != tuple(str(value) for value in work_unit.get("input_version_refs", ())):
                raise StaleInputHead("research_run_business_inputs_are_stale")
            research_run = ResearchRunVersion(
                **self._scope(command, case_id=case_id),
                research_run_id=research_run_id,
                research_run_version_id=f"{research_run_id}:v1",
                research_run_version=1,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                execution_profile_version_ref=profile_ref,
                parent_research_run_id=(
                    str(command.payload.get("parent_research_run_id") or "") or None
                ),
                input_refs=input_refs,
                input_refs_digest=canonical_digest(input_refs),
                state=ResearchRunState.RUNNING,
                started_at=command.requested_at,
                current_status=ResearchRunState.RUNNING.value,
            )
            tx.insert(
                "canonical_research_run_versions",
                research_run_id,
                research_run.research_run_version,
                research_run.model_dump(mode="json"),
            )
            event = self._event(
                tx,
                command,
                "RESEARCH_RUN_STARTED",
                {
                    "research_run_id": research_run_id,
                    "research_run_version_id": research_run.research_run_version_id,
                    "execution_profile_version_ref": profile_ref,
                },
                task_run_id=research_run_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=0,
                state_version_after=1,
                event_ids=(event.event_id,),
                projection_refs=(research_run.research_run_version_id,),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def record_research_run_trace(self, command: CommandEnvelope) -> ResultEnvelope:
        """Append one bounded, Run-scoped execution trace event without business mutation."""

        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        research_run_id = str(command.payload.get("research_run_id") or "")
        event_type = str(command.payload.get("event_type") or "")
        event_payload = command.payload.get("event_payload")
        allowed_event_types = {
            "AGENT_DEFINITION_VERSIONS_SELECTED",
            "SKILL_PACK_CONSUMPTION_RECORDED",
            "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
            "RESEARCH_LEAD_FIXTURE_COMPLETED",
            "SPECIALIST_FIXTURE_COMPLETED",
            "TOOL_FIXTURE_OBSERVATION_RECORDED",
            "GRAPH_FIXTURE_OBSERVATION_RECORDED",
            "WRITER_FIXTURE_COMPLETED",
            "VERIFIER_FIXTURE_COMPLETED",
            "BOUNDED_AGENT_T02_CONTRACT_PROBE_COMPLETED",
            "BOUNDED_AGENT_INPUT_BOUND",
            "BOUNDED_AGENT_VERSIONS_SELECTED",
            "BOUNDED_AGENT_SPECIALIST_COMPLETED",
            "BOUNDED_AGENT_LEAD_ADJUDICATED",
            "BOUNDED_AGENT_WRITER_COMPLETED",
            "BOUNDED_AGENT_VERIFIERS_COMPLETED",
            "BOUNDED_AGENT_EXECUTION_COMPLETED",
            "S3_BOUNDED_AGENT_NODE_COMPLETED",
            "S3_BOUNDED_AGENT_EXECUTION_COMPLETED",
        }
        if not all((work_unit_id, attempt_id, research_run_id)):
            raise MissingDependency("research_run_trace_identity_required")
        if event_type not in allowed_event_types or not isinstance(event_payload, Mapping):
            raise ArtifactValidationError("research_run_trace_event_not_admitted")
        scope_key, payload_digest, _ = self._idempotency(
            command, f"{research_run_id}:{event_type}"
        )
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            self._require_running_execution(tx, command, case_id, work_unit_id, attempt_id)
            research_run = self._require_case_row(
                tx,
                command,
                case_id,
                table="canonical_research_run_versions",
                logical_id=research_run_id,
            )
            if (
                research_run.get("state") != ResearchRunState.RUNNING.value
                or research_run.get("work_unit_id") != work_unit_id
                or research_run.get("attempt_id") != attempt_id
            ):
                raise IllegalStateTransition("research_run_trace_execution_identity_mismatch")
            event = self._event(
                tx,
                command,
                event_type,
                dict(event_payload),
                task_run_id=research_run_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                advances_state=False,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version,
                event_ids=(event.event_id,),
                projection_refs=(research_run_id,),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def _persist_provider_output_captures(
        self,
        captures: Sequence[Mapping[str, Any]],
        *,
        case_id: str,
        work_unit_id: str,
        attempt_id: str,
        research_run_id: str,
    ) -> list[dict[str, Any]]:
        payloads = _provider_output_capture_payloads(
            captures,
            case_id=case_id,
            work_unit_id=work_unit_id,
            attempt_id=attempt_id,
            research_run_id=research_run_id,
        )
        refs: list[dict[str, Any]] = []
        for payload in payloads:
            object_ref = self.object_store.put_json(
                payload,
                namespace="fin01/provider-output-captures",
                artifact_type="provider_output_capture",
            )
            refs.append(
                {
                    "schema_ref": str(payload["schema_ref"]),
                    "capture_policy_ref": str(
                        payload["capture_policy_ref"]
                    ),
                    "access_class": "internal_restricted_run_audit",
                    "retention_class": "follow_research_run_retention",
                    "capture_sequence": int(payload["capture_sequence"]),
                    "stage": str(payload["stage"]),
                    "call_id": str(payload["call_id"]),
                    "provider": str(payload["provider"]),
                    "model": str(payload["model"]),
                    "assistant_output_present": bool(
                        payload["assistant_output_present"]
                    ),
                    "object_key": str(object_ref["object_key"]),
                    "object_digest": str(object_ref["digest"]),
                    "byte_size": int(object_ref["byte_size"]),
                    "media_type": str(object_ref["media_type"]),
                    "raw_provider_response_persisted": False,
                    "private_reasoning_persisted": False,
                    **(
                        {
                            "model_visible_request_digest": str(
                                payload["model_visible_request_digest"]
                            ),
                            "nonsecret_inference_arguments_digest": str(
                                payload[
                                    "nonsecret_inference_arguments_digest"
                                ]
                            ),
                            "provider_route_digest": str(
                                payload["provider_route_digest"]
                            ),
                            "validator_match_index": deepcopy(
                                payload["validator_match_index"]
                            ),
                            "raw_request_envelope_persisted": False,
                            "credentials_persisted": False,
                        }
                        if payload["capture_policy_ref"]
                        == PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
                        else {}
                    ),
                }
            )
        return refs

    def record_research_run_provider_output_captures(
        self, command: CommandEnvelope
    ) -> ResultEnvelope:
        """Persist safe assistant-final-text captures before terminal adjudication."""

        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        research_run_id = str(command.payload.get("research_run_id") or "")
        captures = _validate_provider_output_captures(
            command.payload.get("provider_output_captures")
        )
        if not all((work_unit_id, attempt_id, research_run_id)) or not captures:
            raise MissingDependency("provider_output_capture_running_identity_required")
        scope_key, payload_digest, _ = self._idempotency(
            command, f"{research_run_id}:provider-output-captures"
        )
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            self._require_running_execution(
                tx, command, case_id, work_unit_id, attempt_id
            )
            research_run = self._require_case_row(
                tx,
                command,
                case_id,
                table="canonical_research_run_versions",
                logical_id=research_run_id,
            )
            if (
                research_run.get("state") != ResearchRunState.RUNNING.value
                or research_run.get("work_unit_id") != work_unit_id
                or research_run.get("attempt_id") != attempt_id
            ):
                raise IllegalStateTransition(
                    "provider_output_capture_execution_identity_mismatch"
                )
            if str(research_run.get("execution_profile_version_ref") or "") not in {
                "fin01.execution_profile.bounded_agent_internal:v1",
                "fin01.execution_profile.bounded_agent_internal_three_cell:v1",
            }:
                raise ArtifactValidationError(
                    "provider_output_capture_profile_not_admitted"
                )
            refs = self._persist_provider_output_captures(
                captures,
                case_id=case_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                research_run_id=research_run_id,
            )
            event = self._event(
                tx,
                command,
                "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED",
                {
                    "research_run_id": research_run_id,
                    "provider_output_capture_policy_ref": (
                        str(captures[0]["capture_policy_ref"])
                    ),
                    "provider_output_capture_refs": refs,
                },
                task_run_id=research_run_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                advances_state=False,
            )
            tx.append_event(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version,
                event_ids=(event.event_id,),
                projection_refs=(research_run_id,),
            )
            tx.put_idempotency(
                scope_key, payload_digest, result.model_dump(mode="json")
            )
        return result

    def read_research_run_provider_output_captures(
        self, research_run_id: str
    ) -> tuple[dict[str, Any], ...]:
        """Read exact final assistant texts through durable Run audit references."""

        self._authorize("point01_shadow_compiler")
        run_id = str(research_run_id or "").strip()
        if not run_id or not self.store.get_latest(
            "canonical_research_run_versions", run_id
        ):
            raise MissingDependency("provider_output_capture_research_run_required")
        terminal_events = [
            row
            for row in self.store.list_events()
            if row.get("task_run_id") == run_id
            and row.get("event_type")
            in {"RESEARCH_RUN_COMPLETED", "RESEARCH_RUN_FAILED"}
        ]
        capture_events = [
            row
            for row in self.store.list_events()
            if row.get("task_run_id") == run_id
            and row.get("event_type") == "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED"
        ]
        if len(terminal_events) > 1 or len(capture_events) > 1:
            raise ArtifactValidationError(
                "provider_output_capture_audit_event_cardinality_invalid"
            )
        terminal_refs = (
            terminal_events[0].get("payload", {}).get(
                "provider_output_capture_refs", []
            )
            if terminal_events
            else []
        )
        durable_refs = (
            capture_events[0].get("payload", {}).get(
                "provider_output_capture_refs", []
            )
            if capture_events
            else []
        )
        if terminal_refs and durable_refs and terminal_refs != durable_refs:
            raise ArtifactValidationError(
                "provider_output_capture_audit_refs_conflict"
            )
        refs = durable_refs or terminal_refs
        if not refs:
            raise MissingDependency("provider_output_capture_audit_event_required")
        if not isinstance(refs, list):
            raise ArtifactValidationError("provider_output_capture_refs_invalid")
        captures: list[dict[str, Any]] = []
        for ref in refs:
            capture_policy_ref = (
                str(ref.get("capture_policy_ref") or "")
                if isinstance(ref, Mapping)
                else ""
            )
            expected_schema_ref = PROVIDER_OUTPUT_CAPTURE_SCHEMA_REFS.get(
                capture_policy_ref
            )
            if (
                not isinstance(ref, Mapping)
                or expected_schema_ref is None
                or ref.get("access_class") != "internal_restricted_run_audit"
                or not isinstance(ref.get("object_key"), str)
                or not isinstance(ref.get("object_digest"), str)
            ):
                raise ArtifactValidationError("provider_output_capture_ref_invalid")
            payload = self.object_store.get_json(
                str(ref["object_key"]),
                expected_digest=str(ref["object_digest"]),
            )
            if (
                not isinstance(payload, Mapping)
                or payload.get("schema_ref") != expected_schema_ref
                or payload.get("capture_policy_ref")
                != capture_policy_ref
                or payload.get("research_run_id") != run_id
                or payload.get("capture_sequence") != ref.get("capture_sequence")
                or payload.get("call_id") != ref.get("call_id")
                or payload.get("private_reasoning_included") is not False
                or payload.get("raw_provider_response_included") is not False
                or (
                    capture_policy_ref
                    == PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
                    and (
                        payload.get("credentials_included") is not False
                        or payload.get("raw_request_envelope_included")
                        is not False
                        or payload.get("model_visible_request_digest")
                        != ref.get("model_visible_request_digest")
                        or payload.get(
                            "nonsecret_inference_arguments_digest"
                        )
                        != ref.get(
                            "nonsecret_inference_arguments_digest"
                        )
                        or payload.get("provider_route_digest")
                        != ref.get("provider_route_digest")
                        or payload.get("validator_match_index")
                        != ref.get("validator_match_index")
                    )
                )
            ):
                raise ArtifactValidationError(
                    "provider_output_capture_payload_lineage_invalid"
                )
            captures.append(dict(payload))
        return tuple(captures)

    def complete_research_run(self, command: CommandEnvelope) -> ResultEnvelope:
        """Commit a typed profile result and terminal Run/Attempt/WorkUnit truth."""

        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        research_run_id = str(command.payload.get("research_run_id") or "")
        provider_output_captures = _validate_provider_output_captures(
            command.payload.get("provider_output_captures")
        )
        artifact_id = str(command.payload.get("artifact_id") or "")
        artifact_payload = command.payload.get("artifact_payload")
        artifact_type = str(
            command.payload.get("artifact_type") or "deterministic_research_result"
        )
        raw_artifacts = command.payload.get("artifacts")
        if isinstance(raw_artifacts, list) and any(
            not isinstance(row, Mapping) for row in raw_artifacts
        ):
            raise ArtifactValidationError("profile_execution_artifact_entry_invalid")
        artifact_specs = (
            [dict(row) for row in raw_artifacts if isinstance(row, Mapping)]
            if isinstance(raw_artifacts, list)
            else [
                {
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_type,
                    "artifact_payload": artifact_payload,
                }
            ]
        )
        admitted_artifact_types = {
            "deterministic_research_result",
            "s3_three_cell_workpaper",
            "s3_three_cell_report",
            "s3_three_cell_trace_review",
            "agent_fixture_shadow_result",
            "agent_fixture_evidence",
            "agent_fixture_numeric",
            "agent_fixture_judgment",
            "agent_fixture_workpaper",
            "agent_fixture_report",
            "agent_fixture_trace",
            "bounded_agent_manifest",
            "bounded_agent_evidence",
            "bounded_agent_numeric",
            "bounded_agent_judgment",
            "bounded_agent_workpaper",
            "bounded_agent_report",
            "bounded_agent_trace",
            "bounded_agent_verification",
            "agent_fallback_comparison",
        }
        if not artifact_specs or any(
            str(row.get("artifact_type") or "") not in admitted_artifact_types
            for row in artifact_specs
        ):
            raise ArtifactValidationError("research_run_artifact_type_not_admitted")
        if not all((work_unit_id, attempt_id, research_run_id)) or any(
            not str(row.get("artifact_id") or "") for row in artifact_specs
        ):
            raise MissingDependency("research_run_completion_identity_required")
        if any(not isinstance(row.get("artifact_payload"), Mapping) for row in artifact_specs):
            raise ArtifactValidationError("profile_execution_result_payload_required")
        scope_key, payload_digest, _ = self._idempotency(command, research_run_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
        current_run = self.store.get_latest("canonical_research_run_versions", research_run_id)
        if not current_run or current_run.get("state") != ResearchRunState.RUNNING.value:
            raise IllegalStateTransition("research_run_must_be_running")
        expected_artifact_types = {
            "fin01.execution_profile.p36_local_deterministic:v1": {
                "deterministic_research_result",
                "s3_three_cell_workpaper",
                "s3_three_cell_report",
                "s3_three_cell_trace_review",
            },
            "fin01.execution_profile.agent_fixture_shadow:v1": {
                "agent_fixture_shadow_result",
                "agent_fixture_evidence",
                "agent_fixture_numeric",
                "agent_fixture_judgment",
                "agent_fixture_workpaper",
                "agent_fixture_report",
                "agent_fixture_trace",
            },
            "fin01.execution_profile.bounded_agent_internal:v1": {
                "bounded_agent_manifest",
                "bounded_agent_evidence",
                "bounded_agent_numeric",
                "bounded_agent_judgment",
                "bounded_agent_workpaper",
                "bounded_agent_report",
                "bounded_agent_trace",
                "bounded_agent_verification",
                "agent_fallback_comparison",
            },
            "fin01.execution_profile.bounded_agent_internal_three_cell:v1": {
                "bounded_agent_manifest",
                "bounded_agent_evidence",
                "bounded_agent_numeric",
                "bounded_agent_judgment",
                "bounded_agent_workpaper",
                "bounded_agent_report",
                "bounded_agent_trace",
                "bounded_agent_verification",
                "agent_fallback_comparison",
            },
        }.get(str(current_run.get("execution_profile_version_ref") or ""))
        actual_artifact_types = {
            str(row.get("artifact_type") or "") for row in artifact_specs
        }
        artifact_ids = [str(row.get("artifact_id") or "") for row in artifact_specs]
        if (
            expected_artifact_types != actual_artifact_types
            or len(artifact_specs) != len(actual_artifact_types)
            or len(artifact_ids) != len(set(artifact_ids))
        ):
            raise ArtifactValidationError("research_run_profile_artifact_type_mismatch")
        if provider_output_captures and str(
            current_run.get("execution_profile_version_ref") or ""
        ) not in {
            "fin01.execution_profile.bounded_agent_internal:v1",
            "fin01.execution_profile.bounded_agent_internal_three_cell:v1",
        }:
            raise ArtifactValidationError(
                "provider_output_capture_profile_not_admitted"
            )
        run_version_id = str(current_run["research_run_version_id"])
        for row in artifact_specs:
            expected_version_id = f"{row['artifact_id']}:v1"
            payload = row["artifact_payload"]
            if (
                payload.get("artifact_version_id") != expected_version_id
                or payload.get("research_run_id") != research_run_id
                or payload.get("research_run_version_id") != run_version_id
            ):
                raise ArtifactValidationError("research_run_artifact_payload_lineage_mismatch")
        object_refs = [
            self.object_store.put_json(
                dict(row["artifact_payload"]),
                namespace="fin01/research-runs",
                artifact_type=str(row["artifact_type"]),
            )
            for row in artifact_specs
        ]
        provider_output_capture_refs = self._persist_provider_output_captures(
            provider_output_captures,
            case_id=case_id,
            work_unit_id=work_unit_id,
            attempt_id=attempt_id,
            research_run_id=research_run_id,
        )
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            work_unit, attempt = self._require_running_execution(
                tx, command, case_id, work_unit_id, attempt_id
            )
            research_run = self._require_case_row(
                tx,
                command,
                case_id,
                table="canonical_research_run_versions",
                logical_id=research_run_id,
            )
            if (
                research_run.get("state") != ResearchRunState.RUNNING.value
                or research_run.get("work_unit_id") != work_unit_id
                or research_run.get("attempt_id") != attempt_id
            ):
                raise IllegalStateTransition("research_run_execution_identity_mismatch")
            business_input_refs = tuple(str(value) for value in attempt.get("input_refs", ()))
            if (
                tuple(str(value) for value in research_run.get("input_refs", ())) != business_input_refs
                or research_run.get("input_refs_digest") != canonical_digest(business_input_refs)
            ):
                raise StaleInputHead("research_run_business_inputs_are_stale")
            run_version_id = str(research_run["research_run_version_id"])
            artifact_input_refs = tuple(dict.fromkeys((run_version_id, *business_input_refs)))
            artifacts = []
            for artifact_spec, object_ref in zip(artifact_specs, object_refs, strict=True):
                current_artifact_id = str(artifact_spec["artifact_id"])
                artifacts.append(
                    ArtifactVersionEnvelope(
                        **self._scope(command, case_id=case_id),
                        artifact_id=current_artifact_id,
                        artifact_version_id=f"{current_artifact_id}:v1",
                        artifact_version=1,
                        artifact_type=str(artifact_spec["artifact_type"]),
                        payload_business_owner="Fin01ResearchRuntime",
                        producer_attempt_id=attempt_id,
                        input_refs=artifact_input_refs,
                        input_refs_digest=canonical_digest(artifact_input_refs),
                        object_key=str(object_ref["object_key"]),
                        object_digest=str(object_ref["digest"]),
                        byte_size=int(object_ref["byte_size"]),
                        media_type=str(object_ref["media_type"]),
                        current_status="available",
                    )
                )
            artifact_version_ids = tuple(
                artifact.artifact_version_id for artifact in artifacts
            )
            artifact_version_id = artifact_version_ids[0]
            completed_run = ResearchRunVersion.model_validate(
                {
                    **research_run,
                    "research_run_version_id": f"{research_run_id}:v2",
                    "research_run_version": 2,
                    "state": ResearchRunState.SUCCEEDED.value,
                    "ended_at": command.requested_at,
                    "terminal_reason": str(command.payload.get("terminal_reason") or "completed"),
                    "supersedes_version_id": run_version_id,
                    "current_status": ResearchRunState.SUCCEEDED.value,
                    "recorded_at": command.requested_at,
                }
            )
            completed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": int(attempt.get("state_version", 0)) + 1,
                    "state": AttemptState.SUCCEEDED.value,
                    "ended_at": command.requested_at,
                    "terminal_reason": "completed",
                    "output_refs": artifact_version_ids,
                    "current_status": AttemptState.SUCCEEDED.value,
                }
            )
            completed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.SUCCEEDED.value,
                    "current_status": WorkUnitState.SUCCEEDED.value,
                }
            )
            for artifact in artifacts:
                tx.insert(
                    "canonical_artifact_versions",
                    artifact.artifact_id,
                    1,
                    artifact.model_dump(mode="json"),
                )
            tx.insert(
                "canonical_research_run_versions",
                research_run_id,
                2,
                completed_run.model_dump(mode="json"),
            )
            tx.insert(
                "canonical_attempts",
                attempt_id,
                completed_attempt.attempt_no,
                completed_attempt.model_dump(mode="json"),
            )
            tx.insert(
                "canonical_work_units",
                work_unit_id,
                completed_work_unit.work_unit_version,
                completed_work_unit.model_dump(mode="json"),
            )
            event_specs = (
                *(
                    (
                        "ARTIFACT_VERSION_CREATED",
                        {
                            "artifact_version_id": artifact.artifact_version_id,
                            "artifact_type": artifact.artifact_type,
                            "research_run_version_id": run_version_id,
                        },
                    )
                    for artifact in artifacts
                ),
                (
                    "RESEARCH_RUN_COMPLETED",
                    {
                        "research_run_id": research_run_id,
                        "research_run_version_id": completed_run.research_run_version_id,
                        "artifact_version_id": artifact_version_id,
                        "artifact_version_ids": list(artifact_version_ids),
                        **(
                            {
                                "provider_output_capture_policy_ref": (
                                    str(
                                        provider_output_captures[0][
                                            "capture_policy_ref"
                                        ]
                                    )
                                ),
                                "provider_output_capture_refs": (
                                    provider_output_capture_refs
                                ),
                            }
                            if provider_output_capture_refs
                            else {}
                        ),
                    },
                ),
                ("ATTEMPT_COMPLETED", {"attempt_id": attempt_id, "output_refs": list(artifact_version_ids)}),
                ("WORK_UNIT_COMPLETED", {"work_unit_id": work_unit_id, "attempt_id": attempt_id}),
            )
            events = []
            for event_type, event_payload in event_specs:
                event = self._event(
                    tx,
                    command,
                    event_type,
                    event_payload,
                    task_run_id=research_run_id,
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                )
                tx.append_event(event)
                events.append(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=tuple(event.event_id for event in events),
                artifact_refs=artifact_version_ids,
                projection_refs=(
                    work_unit_id,
                    attempt_id,
                    completed_run.research_run_version_id,
                ),
            )
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def fail_research_run(self, command: CommandEnvelope) -> ResultEnvelope:
        """Persist terminal failure without creating an artifact or hidden fallback."""

        self._authorize("point01_shadow_compiler")
        case_id = self._require_case(command)
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        attempt_id = str(command.payload.get("attempt_id") or "")
        research_run_id = str(command.payload.get("research_run_id") or "")
        provider_output_captures = _validate_provider_output_captures(
            command.payload.get("provider_output_captures")
        )
        failure_type = str(command.payload.get("failure_type") or "profile_execution_failed")
        terminal_reason = str(command.payload.get("terminal_reason") or failure_type)
        failure_observation = command.payload.get("failure_observation")
        if failure_observation is not None and not isinstance(failure_observation, Mapping):
            raise ArtifactValidationError("research_run_failure_observation_invalid")
        if isinstance(failure_observation, Mapping):
            failure_observation, _ = normalize_optional_failure_observation(
                failure_observation
            )
            allowed_observation_keys = {
                "stage",
                "contract_ref",
                "lifecycle_phase",
                "failure_code",
                "failure_codes",
                "output_shape",
                "failure_telemetry",
                "observed_counts",
                "estimated_cost_usd",
                "usage_receipts",
                "completed_node_receipts",
                "private_reasoning_persisted",
                "raw_provider_response_persisted",
            }
            allowed_receipt_keys = {
                "stage",
                "call_id",
                "provider",
                "model",
                "status",
                "finish_reason",
                "input_tokens",
                "input_cache_hit_tokens",
                "input_cache_miss_tokens",
                "output_tokens",
                "total_tokens",
                "estimated_cost_usd",
                "latency_ms",
                "transport_attempt_count",
            }
            receipts = failure_observation.get("usage_receipts") or []
            completed_node_receipts = (
                failure_observation.get("completed_node_receipts")
            )
            lifecycle_phase = failure_observation.get("lifecycle_phase")
            typed_failure_code = failure_observation.get("failure_code")
            output_shape = failure_observation.get("output_shape")
            failure_telemetry = failure_observation.get("failure_telemetry")
            strict_tool_arguments = (
                failure_telemetry.get("strict_tool_arguments")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            segmented_specialist_shape = (
                failure_telemetry.get("segmented_specialist_shape")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            segmented_specialist_text = (
                failure_telemetry.get("segmented_specialist_text")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            segmented_specialist_authority = (
                failure_telemetry.get("segmented_specialist_authority")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            segmented_specialist_fact_authority = (
                failure_telemetry.get(
                    "segmented_specialist_fact_authority"
                )
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            segmented_specialist_epistemic_status = (
                failure_telemetry.get(
                    "segmented_specialist_epistemic_status"
                )
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            research_lead_contract = (
                failure_telemetry.get("research_lead_contract")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            memo_writer_contract = (
                failure_telemetry.get("memo_writer_contract")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            scoped_identity_contract = (
                failure_telemetry.get("scoped_identity_contract")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            verifier_state_machine = (
                failure_telemetry.get("verifier_state_machine")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            profile_artifact_lineage = (
                failure_telemetry.get("profile_artifact_lineage")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            registered_observation = (
                failure_telemetry.get("registered_observation")
                if isinstance(failure_telemetry, Mapping)
                else None
            )
            allowed_failure_telemetry_keys = {
                "strict_tool_arguments",
                "segmented_specialist_shape",
                "segmented_specialist_text",
                "segmented_specialist_authority",
                "segmented_specialist_fact_authority",
                "segmented_specialist_epistemic_status",
                "research_lead_contract",
                "memo_writer_contract",
                "scoped_identity_contract",
                "verifier_state_machine",
                "profile_artifact_lineage",
                "registered_observation",
            }
            required_strict_tool_argument_keys = {
                "parser_contract",
                "parse_subtype",
                "raw_arguments_persisted",
                "argument_digest_persisted",
                "argument_length_persisted",
            }
            allowed_strict_tool_parse_subtypes = {
                "json_decode_error",
                "duplicate_key",
                "non_object",
            }
            required_segmented_specialist_shape_keys = {
                "parser_contract",
                "segment_id",
                "shape_subtype",
                "missing_key_count",
                "unexpected_key_count",
                "raw_output_persisted",
                "arbitrary_key_names_persisted",
            }
            allowed_segment_ids = {
                "facts_explanation_and_terminal",
                "owner_grade_claim_cards",
                "actionable_what_would_change_tasks",
            }
            allowed_segmented_shape_subtypes = {
                "top_level_keys_missing",
                "top_level_keys_unexpected",
                "program_cell_id_mismatch",
            }
            required_segmented_specialist_text_keys = {
                "validator_contract",
                "segment_id",
                "field_id",
                "text_subtype",
                "failing_item_count",
                "raw_text_persisted",
                "item_index_persisted",
                "arbitrary_key_names_persisted",
                "private_reasoning_persisted",
            }
            allowed_segmented_text_fields = {
                "fact_layer.statement_or_boundary",
                "explanation_layer",
                "remaining_gaps",
                "judgment_layer",
                "what_would_change",
            }
            allowed_segmented_text_subtypes = {
                "item_not_string",
                "item_blank",
                "item_over_max_unicode_characters",
            }
            required_segmented_specialist_authority_keys = {
                "validator_contract",
                "segment_id",
                "field_id",
                "authority_subtype",
                "failing_item_count",
                "raw_ref_persisted",
                "ref_digest_persisted",
                "item_index_persisted",
                "arbitrary_key_names_persisted",
                "private_reasoning_persisted",
            }
            allowed_segmented_authority_subtypes = {
                "item_not_nonblank_string",
                "evidence_or_numeric_ref_misclassified_as_context",
                "outside_current_cell_context_authority",
            }
            required_segmented_specialist_fact_authority_keys = {
                "validator_contract",
                "segment_id",
                "field_id",
                "authority_subtype",
                "failing_item_count",
                "raw_ref_persisted",
                "ref_digest_persisted",
                "item_index_persisted",
                "arbitrary_key_names_persisted",
                "private_reasoning_persisted",
            }
            allowed_segmented_fact_authority_subtypes = {
                "fact_layer_not_array",
                "support_type_invalid",
                "support_refs_not_array",
                "support_refs_empty",
                "item_not_nonblank_string",
                "candidate_or_graph_ref_misclassified_as_fact",
                "evidence_or_numeric_cross_type",
                "outside_current_cell_fact_authority",
                "support_ref_duplicate",
            }
            required_segmented_specialist_epistemic_status_keys = {
                "validator_contract",
                "segment_id",
                "field_id",
                "status_subtype",
                "failing_item_count",
                "raw_claim_persisted",
                "support_fact_ids_persisted",
                "cannot_support_text_persisted",
                "item_index_persisted",
                "arbitrary_key_names_persisted",
                "private_reasoning_persisted",
            }
            allowed_segmented_epistemic_status_subtypes = {
                "cannot_infer_has_support_fact_ids",
                "cannot_infer_missing_cannot_support",
                "cannot_infer_has_support_and_missing_boundary",
            }
            required_research_lead_contract_keys = {
                "validator_contract",
                "failure_family",
                "failure_subtype",
                "field_id",
                "failing_item_count",
                "raw_text_persisted",
                "ref_or_digest_persisted",
                "item_index_persisted",
                "arbitrary_key_names_persisted",
                "private_reasoning_persisted",
            }
            allowed_research_lead_failure_families = {
                "parse",
                "shape",
                "cardinality",
                "text",
                "authority",
                "capacity",
                "assembly",
                "semantic",
            }
            allowed_research_lead_failure_subtypes = {
                "native_json_required",
                "json_decode_failed",
                "duplicate_key",
                "non_object",
                "top_level_keys_missing",
                "top_level_keys_unexpected",
                "item_schema_invalid",
                "below_minimum",
                "above_maximum",
                "item_not_string",
                "item_blank",
                "item_over_max_unicode_characters",
                "claim_ref_invalid",
                "task_ref_invalid",
                "provider_length_stop",
                "provider_segment_over_max_utf8_bytes",
                "deterministic_heads_invalid",
                "assembled_output_over_max_utf8_bytes",
                "canonical_validation_failed",
                "involved_claim_ref_duplicate",
                "fact_presence_summary_invalid",
                "fact_presence_summary_mismatch",
                "explicit_global_fact_presence_statement_conflict",
            }
            allowed_research_lead_field_ids = {
                "top_level",
                "cross_cell_dependencies",
                "conflict_adjudications",
                "variant_view",
                "remaining_gaps",
                "cell_heads",
                "assembled_output",
                "conflict_adjudications.fact_presence_summary",
            }
            required_memo_writer_contract_keys = {
                "validator_contract",
                "failure_family",
                "failure_subtype",
                "field_id",
                "failing_item_count",
                "raw_text_persisted",
                "ref_or_digest_persisted",
                "item_index_persisted",
                "arbitrary_key_names_persisted",
                "private_reasoning_persisted",
            }
            allowed_memo_writer_failure_families = {
                "shape",
                "cardinality",
                "text",
                "authority",
                "assembly",
                "semantic",
            }
            required_scoped_identity_contract_keys = {
                "identity_kind",
                "failure_subtype",
                "failing_item_count",
            }
            allowed_scoped_identity_kinds = {
                "claim",
                "what_would_change",
            }
            allowed_scoped_identity_failure_subtypes = {
                "duplicate_local_id_same_cell",
                "raw_local_id_cross_cell_ambiguous",
                "scoped_ref_duplicate",
                "scoped_ref_mismatch",
                "unknown_scoped_ref",
            }
            required_verifier_state_machine_keys = {
                "validator_contract",
                "failure_subtype",
                "failing_layer_count",
                "nonempty_issue_layer_count",
                "nonempty_ref_layer_count",
                "raw_issue_codes_persisted",
                "raw_refs_persisted",
                "repair_owner_persisted",
                "raw_output_persisted",
                "private_reasoning_persisted",
            }
            allowed_verifier_state_machine_subtypes = {
                "pass_with_nonempty_issue_codes",
                "pass_with_nonempty_refs",
                "pass_with_repair_owner",
                "nonpass_without_issue_codes",
                "nonpass_without_refs",
                "nonpass_without_repair_owner",
                "decision_findings_state_conflict",
            }
            required_profile_artifact_lineage_keys = {
                "validation_contract_ref",
                "validation_subtype",
                "artifact_type",
                "lineage_family",
                "raw_output_persisted",
                "private_reasoning_persisted",
                "credential_persisted",
                "stack_persisted",
            }
            allowed_profile_artifact_lineage_subtypes = {
                "bounded_agent_profile_lineage_contract_mismatch",
                "bounded_agent_profile_lineage_digest_mismatch",
                "bounded_agent_profile_lineage_overlay_mismatch",
            }
            allowed_profile_artifact_lineage_artifact_types = {
                "bounded_agent_manifest",
                "bounded_agent_trace",
                "s4_case_runtime",
            }
            allowed_profile_artifact_lineage_families = {
                "legacy_s3",
                "s4_base",
                "s4_research_profile_overlay",
                "unresolved",
            }
            allowed_memo_writer_failure_subtypes = {
                "top_level_keys_mismatch",
                "claim_rendering_schema_invalid",
                "claim_rendering_cardinality_mismatch",
                "claim_ref_invalid",
                "claim_ref_duplicate",
                "analysis_text_blank",
                "analysis_text_over_max_unicode_characters",
                "graph_terminology_invalid",
                "canonical_validation_failed",
            }
            allowed_memo_writer_field_ids = {
                "top_level",
                "claim_renderings",
                "claim_renderings.claim_id",
                "claim_renderings.analysis_text_zh_cn",
                "assembled_output",
            }
            allowed_output_shape_keys = {
                "outer_key_count",
                "expected_outer_keys_present",
                "missing_outer_keys",
                "unexpected_outer_key_count",
                "unexpected_outer_keys_digest",
                "recognized_wrapper_keys_present",
                "expected_outer_value_types",
                "result_key_count",
                "expected_result_keys_present",
                "missing_result_keys",
                "unexpected_result_key_count",
                "unexpected_result_keys_digest",
                "expected_result_value_types",
            }
            result_shape_keys = {
                "result_key_count",
                "expected_result_keys_present",
                "missing_result_keys",
                "unexpected_result_key_count",
                "unexpected_result_keys_digest",
                "expected_result_value_types",
            }
            result_shape_present = isinstance(output_shape, Mapping) and bool(
                set(output_shape) & result_shape_keys
            )
            if (
                set(failure_observation) - allowed_observation_keys
                or failure_observation.get("private_reasoning_persisted") is not False
                or failure_observation.get("raw_provider_response_persisted") is not False
                or not isinstance(failure_observation.get("observed_counts"), Mapping)
                or not isinstance(failure_observation.get("failure_codes"), list)
                or any(
                    not _is_secret_safe_bounded_failure_code(code)
                    for code in (failure_observation.get("failure_codes") or [])
                )
                or (
                    failure_observation.get("contract_ref") is not None
                    and (
                        failure_observation.get("contract_ref")
                        != (
                            "fin01.bounded_agent."
                            "post_provider_failure_envelope:v1"
                        )
                        or lifecycle_phase
                        not in {
                            "node_envelope_accounting",
                            "post_node_validation",
                            "post_verifier_call_accounting",
                            "execution_artifact_assembly",
                            "adapter_output_conversion",
                            "profile_artifact_ref_binding",
                            "profile_result_validation",
                            "profile_trace_recording",
                        }
                        or not _is_secret_safe_bounded_failure_code(
                            typed_failure_code
                        )
                        or typed_failure_code
                        not in failure_observation.get(
                            "failure_codes", ()
                        )
                        or not isinstance(
                            completed_node_receipts, list
                        )
                        or any(
                            not isinstance(row, Mapping)
                            or set(row)
                            - {
                                "node_id",
                                "input_digest",
                                "output_digest",
                                "observed_counts",
                                "version_bindings",
                                "s4_case_runtime_consumption",
                            }
                            or not isinstance(
                                row.get("node_id"), str
                            )
                            or not isinstance(
                                row.get("input_digest"), str
                            )
                            or not isinstance(
                                row.get("output_digest"), str
                            )
                            or not isinstance(
                                row.get("observed_counts"), Mapping
                            )
                            or not isinstance(
                                row.get("version_bindings"), Mapping
                            )
                            for row in completed_node_receipts
                        )
                    )
                )
                or (
                    output_shape is not None
                    and (
                        not isinstance(output_shape, Mapping)
                        or set(output_shape) - allowed_output_shape_keys
                        or not isinstance(output_shape.get("outer_key_count"), int)
                        or not isinstance(
                            output_shape.get("unexpected_outer_key_count"), int
                        )
                        or not isinstance(
                            output_shape.get("expected_outer_keys_present"), list
                        )
                        or not isinstance(output_shape.get("missing_outer_keys"), list)
                        or not isinstance(
                            output_shape.get("recognized_wrapper_keys_present"), list
                        )
                        or not isinstance(
                            output_shape.get("expected_outer_value_types"), Mapping
                        )
                        or (
                            result_shape_present
                            and (
                                not isinstance(output_shape.get("result_key_count"), int)
                                or not isinstance(
                                    output_shape.get("unexpected_result_key_count"), int
                                )
                                or not isinstance(
                                    output_shape.get("expected_result_keys_present"), list
                                )
                                or not isinstance(
                                    output_shape.get("missing_result_keys"), list
                                )
                                or not isinstance(
                                    output_shape.get("expected_result_value_types"), Mapping
                                )
                                or result_shape_keys - set(output_shape)
                            )
                        )
                    )
                )
                or (
                    failure_telemetry is not None
                    and (
                        not isinstance(failure_telemetry, Mapping)
                        or len(failure_telemetry) != 1
                        or not set(failure_telemetry).issubset(
                            allowed_failure_telemetry_keys
                        )
                        or (
                            "registered_observation" in failure_telemetry
                            and not is_registered_failure_observation(
                                registered_observation
                            )
                        )
                        or (
                            "strict_tool_arguments" in failure_telemetry
                            and (
                                not isinstance(strict_tool_arguments, Mapping)
                                or set(strict_tool_arguments)
                                != required_strict_tool_argument_keys
                                or strict_tool_arguments.get("parser_contract")
                                != "native_json_object_no_fence_no_duplicate_keys"
                                or strict_tool_arguments.get("parse_subtype")
                                not in allowed_strict_tool_parse_subtypes
                                or strict_tool_arguments.get(
                                    "raw_arguments_persisted"
                                )
                                is not False
                                or strict_tool_arguments.get(
                                    "argument_digest_persisted"
                                )
                                is not False
                                or strict_tool_arguments.get(
                                    "argument_length_persisted"
                                )
                                is not False
                            )
                        )
                        or (
                            "segmented_specialist_shape" in failure_telemetry
                            and (
                                not isinstance(
                                    segmented_specialist_shape, Mapping
                                )
                                or set(segmented_specialist_shape)
                                != required_segmented_specialist_shape_keys
                                or segmented_specialist_shape.get(
                                    "parser_contract"
                                )
                                != "closed_segment_top_level_shape:v1"
                                or segmented_specialist_shape.get("segment_id")
                                not in allowed_segment_ids
                                or segmented_specialist_shape.get(
                                    "shape_subtype"
                                )
                                not in allowed_segmented_shape_subtypes
                                or type(
                                    segmented_specialist_shape.get(
                                        "missing_key_count"
                                    )
                                )
                                is not int
                                or segmented_specialist_shape.get(
                                    "missing_key_count"
                                )
                                < 0
                                or type(
                                    segmented_specialist_shape.get(
                                        "unexpected_key_count"
                                    )
                                )
                                is not int
                                or segmented_specialist_shape.get(
                                    "unexpected_key_count"
                                )
                                < 0
                                or segmented_specialist_shape.get(
                                    "raw_output_persisted"
                                )
                                is not False
                                or segmented_specialist_shape.get(
                                    "arbitrary_key_names_persisted"
                                )
                                is not False
                            )
                        )
                        or (
                            "segmented_specialist_text" in failure_telemetry
                            and (
                                not isinstance(
                                    segmented_specialist_text, Mapping
                                )
                                or set(segmented_specialist_text)
                                != required_segmented_specialist_text_keys
                                or segmented_specialist_text.get(
                                    "validator_contract"
                                )
                                != "closed_segment_narrative_text:v1"
                                or segmented_specialist_text.get("segment_id")
                                not in allowed_segment_ids
                                or segmented_specialist_text.get("field_id")
                                not in allowed_segmented_text_fields
                                or segmented_specialist_text.get("text_subtype")
                                not in allowed_segmented_text_subtypes
                                or type(
                                    segmented_specialist_text.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or segmented_specialist_text.get(
                                    "failing_item_count"
                                )
                                <= 0
                                or segmented_specialist_text.get(
                                    "raw_text_persisted"
                                )
                                is not False
                                or segmented_specialist_text.get(
                                    "item_index_persisted"
                                )
                                is not False
                                or segmented_specialist_text.get(
                                    "arbitrary_key_names_persisted"
                                )
                                is not False
                                or segmented_specialist_text.get(
                                    "private_reasoning_persisted"
                                )
                                is not False
                            )
                        )
                        or (
                            "segmented_specialist_authority" in failure_telemetry
                            and (
                                not isinstance(
                                    segmented_specialist_authority, Mapping
                                )
                                or set(segmented_specialist_authority)
                                != required_segmented_specialist_authority_keys
                                or segmented_specialist_authority.get(
                                    "validator_contract"
                                )
                                != "closed_segment_context_authority:v1"
                                or segmented_specialist_authority.get("segment_id")
                                != "owner_grade_claim_cards"
                                or segmented_specialist_authority.get("field_id")
                                != "judgment_layer.context_refs"
                                or segmented_specialist_authority.get(
                                    "authority_subtype"
                                )
                                not in allowed_segmented_authority_subtypes
                                or type(
                                    segmented_specialist_authority.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or segmented_specialist_authority.get(
                                    "failing_item_count"
                                )
                                <= 0
                                or any(
                                    segmented_specialist_authority.get(key)
                                    is not False
                                    for key in (
                                        "raw_ref_persisted",
                                        "ref_digest_persisted",
                                        "item_index_persisted",
                                        "arbitrary_key_names_persisted",
                                        "private_reasoning_persisted",
                                    )
                                )
                            )
                        )
                        or (
                            "segmented_specialist_fact_authority"
                            in failure_telemetry
                            and (
                                not isinstance(
                                    segmented_specialist_fact_authority,
                                    Mapping,
                                )
                                or set(segmented_specialist_fact_authority)
                                != required_segmented_specialist_fact_authority_keys
                                or segmented_specialist_fact_authority.get(
                                    "validator_contract"
                                )
                                != "closed_fact_support_authority:v1"
                                or segmented_specialist_fact_authority.get(
                                    "segment_id"
                                )
                                != "facts_explanation_and_terminal"
                                or segmented_specialist_fact_authority.get(
                                    "field_id"
                                )
                                != "fact_layer.support_refs"
                                or segmented_specialist_fact_authority.get(
                                    "authority_subtype"
                                )
                                not in allowed_segmented_fact_authority_subtypes
                                or type(
                                    segmented_specialist_fact_authority.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or segmented_specialist_fact_authority.get(
                                    "failing_item_count"
                                )
                                <= 0
                                or any(
                                    segmented_specialist_fact_authority.get(key)
                                    is not False
                                    for key in (
                                        "raw_ref_persisted",
                                        "ref_digest_persisted",
                                        "item_index_persisted",
                                        "arbitrary_key_names_persisted",
                                        "private_reasoning_persisted",
                                    )
                                )
                            )
                        )
                        or (
                            "segmented_specialist_epistemic_status"
                            in failure_telemetry
                            and (
                                not isinstance(
                                    segmented_specialist_epistemic_status,
                                    Mapping,
                                )
                                or set(segmented_specialist_epistemic_status)
                                != required_segmented_specialist_epistemic_status_keys
                                or segmented_specialist_epistemic_status.get(
                                    "validator_contract"
                                )
                                != "closed_claim_card_epistemic_status_state:v1"
                                or segmented_specialist_epistemic_status.get(
                                    "segment_id"
                                )
                                != "owner_grade_claim_cards"
                                or segmented_specialist_epistemic_status.get(
                                    "field_id"
                                )
                                != (
                                    "judgment_layer.epistemic_status_support_fact_ids_"
                                    "qualification_cannot_support"
                                )
                                or segmented_specialist_epistemic_status.get(
                                    "status_subtype"
                                )
                                not in allowed_segmented_epistemic_status_subtypes
                                or type(
                                    segmented_specialist_epistemic_status.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or segmented_specialist_epistemic_status.get(
                                    "failing_item_count"
                                )
                                <= 0
                                or any(
                                    segmented_specialist_epistemic_status.get(key)
                                    is not False
                                    for key in (
                                        "raw_claim_persisted",
                                        "support_fact_ids_persisted",
                                        "cannot_support_text_persisted",
                                        "item_index_persisted",
                                        "arbitrary_key_names_persisted",
                                        "private_reasoning_persisted",
                                    )
                                )
                            )
                        )
                        or (
                            "research_lead_contract" in failure_telemetry
                            and (
                                not isinstance(research_lead_contract, Mapping)
                                or set(research_lead_contract)
                                != required_research_lead_contract_keys
                                or research_lead_contract.get(
                                    "validator_contract"
                                )
                                not in {
                                    "closed_research_lead_output:v2",
                                    "closed_research_lead_output:v3",
                                }
                                or research_lead_contract.get("failure_family")
                                not in allowed_research_lead_failure_families
                                or research_lead_contract.get("failure_subtype")
                                not in allowed_research_lead_failure_subtypes
                                or research_lead_contract.get("field_id")
                                not in allowed_research_lead_field_ids
                                or (
                                    research_lead_contract.get(
                                        "validator_contract"
                                    )
                                    == "closed_research_lead_output:v2"
                                    and (
                                        research_lead_contract.get(
                                            "failure_family"
                                        )
                                        == "semantic"
                                        or research_lead_contract.get(
                                            "failure_subtype"
                                        )
                                        in {
                                            "involved_claim_ref_duplicate",
                                            "fact_presence_summary_invalid",
                                            "fact_presence_summary_mismatch",
                                            (
                                                "explicit_global_fact_presence_"
                                                "statement_conflict"
                                            ),
                                        }
                                        or research_lead_contract.get(
                                            "field_id"
                                        )
                                        == (
                                            "conflict_adjudications."
                                            "fact_presence_summary"
                                        )
                                    )
                                )
                                or type(
                                    research_lead_contract.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or research_lead_contract.get(
                                    "failing_item_count"
                                )
                                < 0
                                or any(
                                    research_lead_contract.get(key) is not False
                                    for key in (
                                        "raw_text_persisted",
                                        "ref_or_digest_persisted",
                                        "item_index_persisted",
                                        "arbitrary_key_names_persisted",
                                        "private_reasoning_persisted",
                                    )
                                )
                            )
                        )
                        or (
                            "memo_writer_contract" in failure_telemetry
                            and (
                                not isinstance(memo_writer_contract, Mapping)
                                or set(memo_writer_contract)
                                != required_memo_writer_contract_keys
                                or memo_writer_contract.get("validator_contract")
                                != "closed_memo_writer_output:v2"
                                or memo_writer_contract.get("failure_family")
                                not in allowed_memo_writer_failure_families
                                or memo_writer_contract.get("failure_subtype")
                                not in allowed_memo_writer_failure_subtypes
                                or memo_writer_contract.get("field_id")
                                not in allowed_memo_writer_field_ids
                                or type(
                                    memo_writer_contract.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or memo_writer_contract.get(
                                    "failing_item_count"
                                )
                                < 0
                                or any(
                                    memo_writer_contract.get(key) is not False
                                    for key in (
                                        "raw_text_persisted",
                                        "ref_or_digest_persisted",
                                        "item_index_persisted",
                                        "arbitrary_key_names_persisted",
                                        "private_reasoning_persisted",
                                    )
                                )
                            )
                        )
                        or (
                            "scoped_identity_contract" in failure_telemetry
                            and (
                                not isinstance(
                                    scoped_identity_contract, Mapping
                                )
                                or set(scoped_identity_contract)
                                != required_scoped_identity_contract_keys
                                or scoped_identity_contract.get("identity_kind")
                                not in allowed_scoped_identity_kinds
                                or scoped_identity_contract.get(
                                    "failure_subtype"
                                )
                                not in allowed_scoped_identity_failure_subtypes
                                or type(
                                    scoped_identity_contract.get(
                                        "failing_item_count"
                                    )
                                )
                                is not int
                                or scoped_identity_contract.get(
                                    "failing_item_count"
                                )
                                <= 0
                            )
                        )
                        or (
                            "verifier_state_machine" in failure_telemetry
                            and (
                                not isinstance(
                                    verifier_state_machine, Mapping
                                )
                                or set(verifier_state_machine)
                                != required_verifier_state_machine_keys
                                or verifier_state_machine.get(
                                    "validator_contract"
                                )
                                != (
                                    "fin01.s3.owner_grade_verifier_"
                                    "output_state_machine:v1"
                                )
                                or verifier_state_machine.get(
                                    "failure_subtype"
                                )
                                not in allowed_verifier_state_machine_subtypes
                                or type(
                                    verifier_state_machine.get(
                                        "failing_layer_count"
                                    )
                                )
                                is not int
                                or verifier_state_machine.get(
                                    "failing_layer_count"
                                )
                                <= 0
                                or any(
                                    type(verifier_state_machine.get(key))
                                    is not int
                                    or verifier_state_machine.get(key) < 0
                                    for key in (
                                        "nonempty_issue_layer_count",
                                        "nonempty_ref_layer_count",
                                    )
                                )
                                or any(
                                    verifier_state_machine.get(key) is not False
                                    for key in (
                                        "raw_issue_codes_persisted",
                                        "raw_refs_persisted",
                                        "repair_owner_persisted",
                                        "raw_output_persisted",
                                        "private_reasoning_persisted",
                                    )
                                )
                            )
                        )
                        or (
                            "profile_artifact_lineage"
                            in failure_telemetry
                            and (
                                not isinstance(
                                    profile_artifact_lineage, Mapping
                                )
                                or set(profile_artifact_lineage)
                                != required_profile_artifact_lineage_keys
                                or profile_artifact_lineage.get(
                                    "validation_contract_ref"
                                )
                                != (
                                    "fin01.bounded_agent."
                                    "profile_aware_artifact_lineage_"
                                    "validation:v1"
                                )
                                or profile_artifact_lineage.get(
                                    "validation_subtype"
                                )
                                not in (
                                    allowed_profile_artifact_lineage_subtypes
                                )
                                or profile_artifact_lineage.get(
                                    "artifact_type"
                                )
                                not in (
                                    allowed_profile_artifact_lineage_artifact_types
                                )
                                or profile_artifact_lineage.get(
                                    "lineage_family"
                                )
                                not in (
                                    allowed_profile_artifact_lineage_families
                                )
                                or any(
                                    profile_artifact_lineage.get(key)
                                    is not False
                                    for key in (
                                        "raw_output_persisted",
                                        "private_reasoning_persisted",
                                        "credential_persisted",
                                        "stack_persisted",
                                    )
                                )
                            )
                        )
                    )
                )
                or not isinstance(receipts, list)
                or any(
                    not isinstance(row, Mapping) or set(row) - allowed_receipt_keys
                    for row in receipts
                )
            ):
                raise ArtifactValidationError("research_run_failure_observation_not_secret_safe")
        if not all((work_unit_id, attempt_id, research_run_id)):
            raise MissingDependency("research_run_failure_identity_required")
        scope_key, payload_digest, _ = self._idempotency(command, research_run_id)
        with self.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self._reuse_or_conflict(existing, payload_digest)
            work_unit, attempt = self._require_running_execution(
                tx, command, case_id, work_unit_id, attempt_id
            )
            research_run = self._require_case_row(
                tx,
                command,
                case_id,
                table="canonical_research_run_versions",
                logical_id=research_run_id,
            )
            if (
                research_run.get("state") != ResearchRunState.RUNNING.value
                or research_run.get("work_unit_id") != work_unit_id
                or research_run.get("attempt_id") != attempt_id
            ):
                raise IllegalStateTransition("research_run_execution_identity_mismatch")
            if provider_output_captures and str(
                research_run.get("execution_profile_version_ref") or ""
            ) not in {
                "fin01.execution_profile.bounded_agent_internal:v1",
                "fin01.execution_profile.bounded_agent_internal_three_cell:v1",
            }:
                raise ArtifactValidationError(
                    "provider_output_capture_profile_not_admitted"
                )
            provider_output_capture_refs = self._persist_provider_output_captures(
                provider_output_captures,
                case_id=case_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                research_run_id=research_run_id,
            )
            failed_run = ResearchRunVersion.model_validate(
                {
                    **research_run,
                    "research_run_version_id": f"{research_run_id}:v2",
                    "research_run_version": 2,
                    "state": ResearchRunState.FAILED.value,
                    "ended_at": command.requested_at,
                    "terminal_reason": terminal_reason,
                    "supersedes_version_id": research_run["research_run_version_id"],
                    "current_status": ResearchRunState.FAILED.value,
                    "recorded_at": command.requested_at,
                }
            )
            failed_attempt = Attempt.model_validate(
                {
                    **attempt,
                    "state_version": int(attempt.get("state_version", 0)) + 1,
                    "state": AttemptState.FAILED.value,
                    "ended_at": command.requested_at,
                    "failure_type": failure_type,
                    "retryable": False,
                    "terminal_reason": terminal_reason,
                    "current_status": AttemptState.FAILED.value,
                }
            )
            failed_work_unit = WorkUnit.model_validate(
                {
                    **work_unit,
                    "state_version": command.expected_state_version + 1,
                    "state": WorkUnitState.FAILED.value,
                    "current_status": WorkUnitState.FAILED.value,
                }
            )
            tx.insert("canonical_research_run_versions", research_run_id, 2, failed_run.model_dump(mode="json"))
            tx.insert("canonical_attempts", attempt_id, failed_attempt.attempt_no, failed_attempt.model_dump(mode="json"))
            tx.insert("canonical_work_units", work_unit_id, failed_work_unit.work_unit_version, failed_work_unit.model_dump(mode="json"))
            event_specs = (
                (
                    "RESEARCH_RUN_FAILED",
                    {
                        "research_run_id": research_run_id,
                        "research_run_version_id": failed_run.research_run_version_id,
                        "failure_type": failure_type,
                        "failure_observation": dict(failure_observation or {}),
                        **(
                            {
                                "provider_output_capture_policy_ref": (
                                    str(
                                        provider_output_captures[0][
                                            "capture_policy_ref"
                                        ]
                                    )
                                ),
                                "provider_output_capture_refs": (
                                    provider_output_capture_refs
                                ),
                            }
                            if provider_output_capture_refs
                            else {}
                        ),
                    },
                ),
                ("ATTEMPT_FAILED", {"attempt_id": attempt_id, "failure_type": failure_type, "retryable": False}),
                ("WORK_UNIT_FAILED", {"work_unit_id": work_unit_id, "attempt_id": attempt_id, "retryable": False}),
            )
            events = []
            for event_type, event_payload in event_specs:
                event = self._event(
                    tx,
                    command,
                    event_type,
                    event_payload,
                    task_run_id=research_run_id,
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                )
                tx.append_event(event)
                events.append(event)
            result = ResultEnvelope(
                command_id=command.command_id,
                status="succeeded",
                state_version_before=command.expected_state_version,
                state_version_after=command.expected_state_version + 1,
                event_ids=tuple(event.event_id for event in events),
                projection_refs=(work_unit_id, attempt_id, failed_run.research_run_version_id),
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
            "research_runs": {},
            "research_run_traces": {},
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
            elif event_type == "RESEARCH_RUN_STARTED":
                research_run_id = str(event.get("task_run_id") or payload.get("research_run_id") or "")
                if not research_run_id:
                    raise UnknownEventSchema("research_run_started_missing_id")
                projection["research_runs"][research_run_id] = {
                    "state": "running",
                    "research_run_version_id": payload.get("research_run_version_id"),
                    "work_unit_id": event.get("work_unit_id"),
                    "attempt_id": event.get("attempt_id"),
                    "execution_profile_version_ref": payload.get("execution_profile_version_ref"),
                }
            elif event_type in {
                "AGENT_DEFINITION_VERSIONS_SELECTED",
                "SKILL_PACK_CONSUMPTION_RECORDED",
                "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
                "RESEARCH_LEAD_FIXTURE_COMPLETED",
                "SPECIALIST_FIXTURE_COMPLETED",
                "TOOL_FIXTURE_OBSERVATION_RECORDED",
                "GRAPH_FIXTURE_OBSERVATION_RECORDED",
                "WRITER_FIXTURE_COMPLETED",
                "VERIFIER_FIXTURE_COMPLETED",
            }:
                research_run_id = str(event.get("task_run_id") or "")
                if not research_run_id:
                    raise UnknownEventSchema("research_run_trace_missing_run_id")
                projection["research_run_traces"].setdefault(research_run_id, []).append(
                    {
                        "event_type": event_type,
                        "event_id": event["event_id"],
                        "causation_event_id": event.get("causation_event_id"),
                        "payload": payload,
                    }
                )
            elif event_type in {"RESEARCH_RUN_COMPLETED", "RESEARCH_RUN_FAILED"}:
                research_run_id = str(event.get("task_run_id") or payload.get("research_run_id") or "")
                if not research_run_id:
                    raise UnknownEventSchema("research_run_terminal_missing_id")
                projection["research_runs"].setdefault(
                    research_run_id,
                    {
                        "work_unit_id": event.get("work_unit_id"),
                        "attempt_id": event.get("attempt_id"),
                    },
                ).update(
                    {
                        "state": "succeeded" if event_type == "RESEARCH_RUN_COMPLETED" else "failed",
                        "research_run_version_id": payload.get("research_run_version_id"),
                        "artifact_version_id": payload.get("artifact_version_id"),
                        "failure_type": payload.get("failure_type"),
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
                    "artifact_type": "runtime_checkpoint" if event_type == "CHECKPOINT_VERSION_CREATED" else payload.get("artifact_type"),
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
        advances_state: bool = True,
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
            state_version_after=command.expected_state_version + (1 if advances_state else 0),
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
