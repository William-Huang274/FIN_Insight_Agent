from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import SkipJsonSchema


SCHEMA_VERSION = "finsight_point01_canonical_runtime_v1_0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_digest(value: Any) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class ScopedVersion(StrictModel):
    schema_version: str = SCHEMA_VERSION
    tenant_id: str
    project_id: str
    case_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    recorded_at: datetime = Field(default_factory=utc_now)
    actor_snapshot_ref: str
    permission_snapshot_ref: str
    policy_config_refs: tuple[str, ...] = ()
    causation_event_id: str | None = None
    correlation_id: str
    content_digest: str = ""
    supersedes_version_id: str | None = None
    current_status: str
    retention_class: str = "institutional_audit"
    data_classification: str = "internal"

    @field_validator("created_at", "recorded_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value

    @field_validator(
        "tenant_id",
        "project_id",
        "actor_snapshot_ref",
        "permission_snapshot_ref",
        "correlation_id",
        mode="before",
    )
    @classmethod
    def require_nonempty(cls, value: Any) -> Any:
        if not str(value or "").strip():
            raise ValueError("nonempty_value_required")
        return value


class CaseStatus(str, Enum):
    SHADOW_CREATED = "shadow_created"
    SHADOW_ACTIVE = "shadow_active"
    PLANNING_CUTOVER_CANDIDATE = "planning_cutover_candidate"
    PLANNING_AUTHORITATIVE = "planning_authoritative"
    ROLLED_BACK = "rolled_back"
    ARCHIVED = "archived"


class WorkUnitState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYABLE_FAILED = "retryable_failed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"
    CANCELLED = "cancelled"


class AttemptState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InstitutionalResearchCase(ScopedVersion):
    case_id: str
    case_version: int = Field(ge=1)
    case_type: str
    created_from_task_ref: str
    case_control_summary_ref: str
    accountable_owner_ref: str
    planning_head_refs: tuple[str, ...] = ()
    current_status: CaseStatus


class CaseControlSummaryVersion(ScopedVersion):
    case_id: str
    summary_version_id: str
    summary_version: int = Field(ge=1)
    query: str
    as_of: datetime
    universe: tuple[str, ...]
    language: str
    planning_authority: str = "legacy"

    @field_validator("as_of")
    @classmethod
    def require_as_of_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class LegacyTaskRunBinding(ScopedVersion):
    case_id: str
    binding_id: str
    binding_version: int = Field(ge=1)
    legacy_system: str
    legacy_store_id: str
    legacy_task_id: str
    legacy_run_id: str
    legacy_authority_status: str = "authoritative"
    normalized_identity_digest: str
    adapter_version: str
    conflict_status: str = "none"


class WorkUnit(ScopedVersion):
    case_id: str
    work_unit_id: str
    work_unit_version: int = Field(ge=1)
    state_version: int = Field(ge=0)
    work_unit_type: str
    target_refs: tuple[str, ...]
    input_version_refs: tuple[str, ...]
    input_version_set_digest: str
    expected_state_version: int = Field(ge=0)
    state: WorkUnitState
    budget_ref: str
    idempotency_key: str
    max_attempts: int = Field(default=1, ge=1)
    retry_budget: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    retry_policy_ref: str = "retry:none"
    retryable_failure_types: tuple[str, ...] = ()
    poison_failure_types: tuple[str, ...] = ("poison",)
    queue_name: str = "point01.default"
    queue_priority: int = Field(default=0, ge=0, le=1000)
    queued_at: datetime | None = None
    latest_scheduler_fencing_token: int = Field(default=0, ge=0)
    forked_from_work_unit_id: str | None = None
    forked_from_attempt_id: str | None = None
    recovery_checkpoint_ref: str | None = None
    dead_letter_reason: str | None = None
    dead_lettered_at: datetime | None = None
    # This is the immutable input-set head for this WorkUnit version. A later
    # input/policy change must create a new WorkUnit, never overwrite this head.
    input_head_digest: str = ""

    @field_validator("queued_at", "dead_lettered_at")
    @classmethod
    def require_queue_time_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)):
            raise ValueError("timezone_aware_utc_required")
        return value


class Attempt(ScopedVersion):
    case_id: str
    attempt_id: str
    attempt_no: int = Field(ge=1)
    state_version: int = Field(default=0, ge=0)
    work_unit_id: str
    work_unit_version: int = Field(ge=1)
    state: AttemptState
    worker_ref: str
    model_ref: str | None = None
    tool_refs: tuple[str, ...] = ()
    started_at: datetime
    ended_at: datetime | None = None
    terminal_reason: str | None = None
    failure_type: str | None = None
    retryable: bool | None = None
    input_refs: tuple[str, ...] = ()
    output_refs: tuple[str, ...] = ()
    input_head_digest: str = ""
    lease_owner_ref: str | None = None
    lease_expires_at: datetime | None = None
    scheduler_managed: bool = False
    lease_fencing_token: int | None = Field(default=None, ge=1)
    lease_heartbeat_at: datetime | None = None
    lease_reclaimed_at: datetime | None = None
    recovery_mode: str | None = None
    recovery_parent_attempt_id: str | None = None
    resume_checkpoint_ref: str | None = None
    replay_plan_digest: str | None = None

    @field_validator("started_at", "ended_at", "lease_expires_at", "lease_heartbeat_at", "lease_reclaimed_at")
    @classmethod
    def require_attempt_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)):
            raise ValueError("timezone_aware_utc_required")
        return value


class ActorSnapshot(ScopedVersion):
    actor_snapshot_id: str
    snapshot_version: int = Field(ge=1)
    actor_id: str
    actor_type: str
    display_name: str
    organization_ref: str | None = None
    role_refs: tuple[str, ...] = ()
    capability_grants: tuple[str, ...] = ()


class EventEnvelope(StrictModel):
    event_id: str
    event_type: str
    task_run_id: str | None = None
    work_unit_id: str | None = None
    attempt_id: str | None = None
    sequence_no: int = Field(ge=1)
    occurred_at: datetime
    recorded_at: datetime
    actor_snapshot_ref: str
    causation_event_id: str | None = None
    correlation_id: str
    state_version_before: int = Field(ge=0)
    state_version_after: int = Field(ge=0)
    payload_ref: str | None = None
    payload_digest: str
    # State transitions need a compact, replayable payload. Large payloads remain
    # externalized through payload_ref / ArtifactVersionEnvelope.
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def require_event_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class CommandEnvelope(StrictModel):
    command_id: str
    command_type: str
    schema_version: str = "1.0"
    tenant_id: str
    project_id: str
    case_id: str | None = None
    actor_snapshot_ref: str
    permission_snapshot_ref: str
    policy_config_refs: tuple[str, ...] = ()
    idempotency_key: str
    expected_state_version: int = Field(ge=0)
    causation_event_id: str | None = None
    correlation_id: str
    requested_at: datetime
    payload: dict[str, Any]

    @field_validator("requested_at")
    @classmethod
    def require_requested_at_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class ResultEnvelope(StrictModel):
    command_id: str
    status: str
    state_version_before: int
    state_version_after: int
    event_ids: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    projection_refs: tuple[str, ...] = ()
    reused_idempotent_result: bool = False
    warnings: tuple[str, ...] = ()
    error: dict[str, Any] | None = None


class ArtifactVersionEnvelope(ScopedVersion):
    case_id: str
    artifact_id: str
    artifact_version_id: str
    artifact_version: int = Field(ge=1)
    artifact_type: str
    payload_business_owner: str
    producer_attempt_id: str
    input_refs: tuple[str, ...]
    input_refs_digest: str
    object_key: str
    object_digest: str
    byte_size: int = Field(ge=0)
    media_type: str
    license_policy_ref: str | None = None
    # M5.3 uses the existing immutable artifact envelope as the only checkpoint
    # identity.  These fields remain null for non-checkpoint artifacts.
    checkpoint_schema_ref: str | None = None
    checkpoint_state_digest: str | None = None
    checkpoint_sequence_no: int | None = Field(default=None, ge=1)


class DecisionSurfaceContractVersion(ScopedVersion):
    case_id: str
    contract_id: str
    contract_version_id: str
    contract_version: int = Field(ge=1)
    query: str
    as_of: datetime
    universe: tuple[str, ...]
    language: str
    universal_pack_refs: tuple[str, ...] = ()
    sector_pack_refs: tuple[str, ...] = ()
    report_type_pack_refs: tuple[str, ...] = ()
    compiler_policy_ref: str
    required_cell_ids: tuple[str, ...]

    @field_validator("as_of")
    @classmethod
    def require_contract_as_of_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("timezone_aware_utc_required")
        return value


class DecisionSurfaceCellVersion(ScopedVersion):
    case_id: str
    contract_version_id: str
    cell_id: str
    cell_version_id: str
    cell_version: int = Field(ge=1)
    decision_question: str
    origin_type: str
    owner_role: str
    materiality: str
    dependency_cell_ids: tuple[str, ...] = ()
    stop_rule: str
    # Persist the P02.4 field without reopening Point 01's frozen schema bundle.
    what_would_change: SkipJsonSchema[str] = ""


class EvidenceSlotVersion(ScopedVersion):
    case_id: str
    cell_version_id: str
    evidence_slot_id: str
    slot_version_id: str
    slot_version: int = Field(ge=1)
    evidence_role: str
    entity_scope: tuple[str, ...]
    period_scope: str
    metric_scope: tuple[str, ...] = ()
    source_policy_ref: str
    forbidden_substitutions: tuple[str, ...] = ()
    acceptance_role: str
    required: bool


class PlanningCheckpointVersion(ScopedVersion):
    case_id: str
    checkpoint_id: str
    checkpoint_version_id: str
    checkpoint_version: int = Field(ge=1)
    contract_version_id: str
    review_status: str

    @field_validator("review_status")
    @classmethod
    def require_review_status(cls, value: str) -> str:
        if value not in {"awaiting_review", "accepted", "returned"}:
            raise ValueError("planning_checkpoint_review_status_invalid")
        return value


class CompileTimeGapVersion(ScopedVersion):
    case_id: str
    cell_version_id: str
    slot_version_id: str | None = None
    gap_id: str
    gap_version_id: str
    gap_version: int = Field(ge=1)
    gap_type: str
    reason: str
    materiality: str
    owner_suggestion: str
    next_action: str


class EvidenceWorkbenchProjectionVersion(ScopedVersion):
    case_id: str
    workspace_id: str
    projection_version_id: str
    projection_version: int = Field(ge=1)
    workspace_version: int = Field(ge=1)
    contract_version_id: str
    checkpoint_version_id: str
    checkpoint_version: int = Field(ge=1)
    work_unit_id: str
    work_unit_version: int = Field(ge=1)
    work_unit_state_version: int = Field(ge=0)
    fixture_contract_ref: str
    fixture_contract_digest: str
    evidence_slots: tuple[dict[str, Any], ...]
    compiled_counts: dict[str, int]
    hard_boundaries: dict[str, int | str]


class EvidenceReviewActionVersion(ScopedVersion):
    case_id: str
    review_action_id: str
    review_action_version_id: str
    review_action_version: int = Field(ge=1)
    workspace_id: str
    workspace_projection_version_id: str
    workspace_version_before: int = Field(ge=1)
    workspace_version_after: int = Field(ge=2)
    action_type: str
    evidence_slot_id: str
    candidate_id: str | None = None
    reason: str


class EvidenceRepairOutcomeVersion(ScopedVersion):
    case_id: str
    repair_outcome_id: str
    repair_outcome_version_id: str
    repair_outcome_version: int = Field(ge=1)
    workspace_id: str
    workspace_projection_version_id: str
    workspace_version_before: int = Field(ge=1)
    workspace_version_after: int = Field(ge=2)
    request_review_action_id: str
    evidence_slot_id: str
    attempt_no: int = Field(ge=1)
    attempt_state: str
    route_id: str
    candidate: dict[str, Any]
    model_call_count: int = Field(ge=0)
    external_call_count: int = Field(ge=0)
    tool_invocation_count: int = Field(ge=0)


class NumericWorkbenchProjectionVersion(ScopedVersion):
    case_id: str
    numeric_workspace_id: str
    numeric_projection_version_id: str
    numeric_workspace_version: int = Field(ge=1)
    evidence_workspace_id: str
    evidence_projection_version_id: str
    evidence_workspace_version: int = Field(ge=1)
    facts: tuple[dict[str, Any], ...]
    hard_boundaries: dict[str, int | str]


class WorkpaperProjectionVersion(ScopedVersion):
    case_id: str
    workpaper_id: str
    workpaper_projection_version_id: str
    workpaper_version: int = Field(ge=1)
    evidence_workspace_id: str
    evidence_workspace_version: int = Field(ge=1)
    numeric_workspace_id: str
    numeric_workspace_version: int = Field(ge=1)
    judgments: tuple[dict[str, Any], ...]
    hard_boundaries: dict[str, int | str]


class LeadReviewDecisionVersion(ScopedVersion):
    case_id: str
    lead_review_id: str
    lead_review_version_id: str
    lead_review_version: int = Field(ge=1)
    workpaper_id: str
    workpaper_projection_version_id: str
    workpaper_version: int = Field(ge=1)
    workpaper_content_digest: str
    decision: str
    reason: str
    writer_admission: dict[str, Any] | None = None


class CanonicalPresentationModelVersion(ScopedVersion):
    case_id: str
    deliverable_id: str
    artifact_version_id: str
    artifact_version: int = Field(ge=1)
    workpaper_id: str
    workpaper_projection_version_id: str
    workpaper_version: int = Field(ge=1)
    workpaper_content_digest: str
    lead_review_id: str
    writer_admission_id: str
    writer_brief_digest: str
    canonical_presentation_id: str
    canonical_presentation_digest: str
    title: str
    sections: tuple[dict[str, Any], ...]
    material_claims: tuple[dict[str, Any], ...]
    renderings: dict[str, Any]
    hard_boundaries: dict[str, int | str]


class DeliverableReviewActionVersion(ScopedVersion):
    case_id: str
    review_action_id: str
    review_action_version_id: str
    review_action_version: int = Field(ge=1)
    artifact_version_id: str
    artifact_version: int = Field(ge=1)
    artifact_content_digest: str
    canonical_presentation_digest: str
    action_type: str
    reason: str
    terminal: bool


class ArtifactProvenanceManifestVersion(ScopedVersion):
    case_id: str
    manifest_id: str
    manifest_version_id: str
    manifest_version: int = Field(ge=1)
    artifact_version_id: str
    artifact_version: int = Field(ge=1)
    artifact_content_digest: str
    canonical_presentation_digest: str
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    claim_to_source: dict[str, tuple[str, ...]]
    source_to_claim: dict[str, tuple[str, ...]]
    redaction_summary: dict[str, int | str]


class ShadowComparisonRecord(ScopedVersion):
    case_id: str
    comparison_id: str
    comparison_version: int = Field(ge=1)
    legacy_plan_ref: str
    canonical_contract_version_id: str
    rubric_version: str
    summary_metrics: dict[str, float | int | str]
    details_artifact_ref: str


class LaneCutoverDecision(ScopedVersion):
    case_id: str
    cutover_id: str
    decision_version: int = Field(ge=1)
    lane_id: str
    decision: str
    gate_evidence_refs: tuple[str, ...]
    previous_authority: str
    requested_authority: str
    approved_store_identity: str
    approved_contract_version_id: str
    approved_contract_digest: str
    approved_artifact_version_id: str
    approved_artifact_digest: str
    approved_comparison_id: str
    approved_comparison_digest: str
    approval_id: str
    approval_registry_ref: str
    effective_at: datetime | None = None

    @field_validator("effective_at")
    @classmethod
    def require_effective_at_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)):
            raise ValueError("timezone_aware_utc_required")
        return value


class LegacyCanonicalIdentityMap(ScopedVersion):
    case_id: str | None = None
    mapping_id: str
    mapping_version: int = Field(ge=1)
    legacy_system: str
    legacy_object_type: str
    legacy_object_id: str
    canonical_object_type: str
    canonical_object_id: str
    normalized_identity_digest: str


CANONICAL_MODELS: ClassVar[tuple[type[BaseModel], ...]] = (
    InstitutionalResearchCase,
    CaseControlSummaryVersion,
    LegacyTaskRunBinding,
    WorkUnit,
    Attempt,
    ActorSnapshot,
    EventEnvelope,
    ArtifactVersionEnvelope,
    DecisionSurfaceContractVersion,
    DecisionSurfaceCellVersion,
    EvidenceSlotVersion,
    CompileTimeGapVersion,
    EvidenceWorkbenchProjectionVersion,
    EvidenceReviewActionVersion,
    EvidenceRepairOutcomeVersion,
    NumericWorkbenchProjectionVersion,
    WorkpaperProjectionVersion,
    LeadReviewDecisionVersion,
    CanonicalPresentationModelVersion,
    DeliverableReviewActionVersion,
    ArtifactProvenanceManifestVersion,
    ShadowComparisonRecord,
    LaneCutoverDecision,
    LegacyCanonicalIdentityMap,
)
