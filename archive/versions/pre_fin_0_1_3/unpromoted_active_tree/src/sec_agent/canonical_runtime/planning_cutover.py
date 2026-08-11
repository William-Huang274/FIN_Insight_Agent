"""M4 case-scoped DecisionSurface planning cutover contracts.

This module is deliberately narrower than a runtime migration.  It can make
canonical planning authoritative for one explicitly approved Case, retains a
read-only legacy compatibility projection, and records a reversible authority
decision.  It never changes legacy TaskRun write ownership or admits
Evidence/Writer/model/full-chain runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal, Mapping, Sequence
from uuid import uuid4

from pydantic import Field

from .feature_flags import FeatureFlagRegistry
from .models import (
    ActorSnapshot,
    CaseControlSummaryVersion,
    CaseStatus,
    EventEnvelope,
    InstitutionalResearchCase,
    LaneCutoverDecision,
    StrictModel,
    canonical_digest,
    utc_now,
)
from .protocols import CanonicalStore, CanonicalTransaction


CUTOVER_FLAG_ID = "decision_surface_planning_cutover_v1_0"
CUTOVER_MODE = "case_scoped"
CUTOVER_CONSUMER = "planning_authority_cutover"
READ_CONSUMER = "planning_authority_read_projection"


class PlanningCutoverError(RuntimeError):
    pass


class CutoverEligibilityError(PlanningCutoverError):
    pass


class CutoverApprovalError(PlanningCutoverError):
    pass


class CutoverAuthorityConflict(PlanningCutoverError):
    pass


class CutoverScope(StrictModel):
    tenant_id: str
    project_id: str
    case_id: str
    lane_id: str
    scope_kind: Literal["case"] = "case"
    feature_flag_id: str = CUTOVER_FLAG_ID
    feature_flag_mode: str = CUTOVER_MODE


class LaneEligibilityPolicy(StrictModel):
    policy_ref: str
    required_feature_flag_id: str = CUTOVER_FLAG_ID
    required_feature_flag_mode: str = CUTOVER_MODE
    require_complete_consumer_inventory: bool = True
    require_legacy_compatibility_projection: bool = True
    allowed_scope_kinds: tuple[str, ...] = ("case",)


class LaneEligibilityRecord(StrictModel):
    scope: CutoverScope
    status: Literal["eligible", "ineligible"]
    consumer_inventory_complete: bool
    legacy_projection_ready: bool
    reasons: tuple[str, ...] = ()
    eligibility_digest: str


class CutoverApprovalReceipt(StrictModel):
    approval_id: str
    approval_registry_ref: str
    status: Literal["approved", "rejected", "pending"]
    approver_type: Literal["fixture_human", "human"]
    schema_digest: str
    policy_digest: str
    store_identity: str
    contract_version_id: str
    contract_digest: str
    artifact_version_id: str
    artifact_digest: str
    comparison_id: str
    comparison_digest: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def valid_for(self, request: "LaneCutoverRequest", *, now: datetime) -> bool:
        return bool(
            self.status == "approved"
            and self.revoked_at is None
            and self.issued_at <= now < self.expires_at
            and self.schema_digest == request.schema_digest
            and self.policy_digest == request.policy_digest
            and self.store_identity == request.store_identity
            and self.contract_version_id == request.contract_version_id
            and self.contract_digest == request.contract_digest
            and self.artifact_version_id == request.artifact_version_id
            and self.artifact_digest == request.artifact_digest
            and self.comparison_id == request.comparison_id
            and self.comparison_digest == request.comparison_digest
        )


class LaneCutoverRequest(StrictModel):
    cutover_id: str
    scope: CutoverScope
    expected_authority_version: int = Field(ge=1)
    schema_digest: str
    policy_digest: str
    store_identity: str
    contract_version_id: str
    contract_digest: str
    artifact_version_id: str
    artifact_digest: str
    comparison_id: str
    comparison_digest: str
    approval: CutoverApprovalReceipt
    gate_evidence_refs: tuple[str, ...]

    @property
    def request_digest(self) -> str:
        return canonical_digest(self)


class LegacyProjectionMapping(StrictModel):
    legacy_required_item_id: str
    canonical_cell_key: str
    information_loss_tags: tuple[str, ...]


class LegacyRequiredItemProjection(StrictModel):
    case_id: str
    contract_version_id: str
    planning_authority: Literal["canonical_for_lane"]
    required_items: tuple[dict[str, Any], ...]
    mapping_rows: tuple[LegacyProjectionMapping, ...]
    read_only: bool = True
    projection_digest: str


class PlanningAuthorityReadModel(StrictModel):
    scope: CutoverScope
    authority: Literal["legacy", "canonical_for_lane"]
    contract: dict[str, Any]
    cells: tuple[dict[str, Any], ...]
    slots: tuple[dict[str, Any], ...]
    gaps: tuple[dict[str, Any], ...]
    current_cutover_decision: dict[str, Any] | None
    legacy_projection: LegacyRequiredItemProjection | None = None
    read_only: bool = True


class WorkbenchDecisionSurfaceProjection(StrictModel):
    case_id: str
    authority_label: Literal["legacy", "canonical_for_lane"]
    contract_version_id: str
    cells: tuple[dict[str, Any], ...]
    slots: tuple[dict[str, Any], ...]
    gaps: tuple[dict[str, Any], ...]
    cutover_decision: dict[str, Any] | None
    read_only: bool = True


class CutoverRecoveryReport(StrictModel):
    case_id: str
    status: Literal["pass", "fail"]
    authority: Literal["legacy", "canonical_for_lane"]
    decision_count: int
    event_types: tuple[str, ...]
    store_recovery_status: str
    errors: tuple[str, ...] = ()


class PlanningCutoverPreflight(StrictModel):
    """Read-only binding inventory used before a human pilot approval is requested."""

    scope: CutoverScope
    store_identity: str
    authority: Literal["legacy", "canonical_for_lane"]
    contract_version_id: str
    contract_digest: str
    artifact_version_id: str
    artifact_digest: str
    comparison_id: str
    comparison_digest: str
    downstream_consumer_count: int
    read_only: bool = True


class PlanningLaneCutoverService:
    """Atomic, append-only cutover and rollback for one approved planning Case."""

    def __init__(
        self,
        store: CanonicalStore,
        flags: FeatureFlagRegistry,
        policy: LaneEligibilityPolicy,
        *,
        grants: set[str] | frozenset[str],
        approval_resolver: Callable[[str], CutoverApprovalReceipt] | None = None,
    ):
        self.store = store
        self.flags = flags
        self.policy = policy
        self.grants = frozenset(grants)
        self.approval_resolver = approval_resolver

    def evaluate_eligibility(
        self,
        scope: CutoverScope,
        *,
        consumer_inventory_complete: bool,
        legacy_projection_ready: bool,
    ) -> LaneEligibilityRecord:
        reasons: list[str] = []
        if scope.scope_kind not in self.policy.allowed_scope_kinds:
            reasons.append("scope_kind_not_allowed")
        if scope.feature_flag_id != self.policy.required_feature_flag_id or scope.feature_flag_mode != self.policy.required_feature_flag_mode:
            reasons.append("feature_flag_scope_mismatch")
        if self.policy.require_complete_consumer_inventory and not consumer_inventory_complete:
            reasons.append("consumer_inventory_incomplete")
        if self.policy.require_legacy_compatibility_projection and not legacy_projection_ready:
            reasons.append("legacy_projection_not_ready")
        return LaneEligibilityRecord(
            scope=scope,
            status="eligible" if not reasons else "ineligible",
            consumer_inventory_complete=consumer_inventory_complete,
            legacy_projection_ready=legacy_projection_ready,
            reasons=tuple(reasons),
            eligibility_digest=canonical_digest(
                {
                    "scope": scope.model_dump(mode="json"),
                    "policy": self.policy.model_dump(mode="json"),
                    "consumer_inventory_complete": consumer_inventory_complete,
                    "legacy_projection_ready": legacy_projection_ready,
                }
            ),
        )

    def request_cutover(
        self,
        request: LaneCutoverRequest,
        eligibility: LaneEligibilityRecord,
        *,
        actor_snapshot_ref: str,
        permission_snapshot_ref: str,
        correlation_id: str,
        now: datetime | None = None,
    ) -> LaneCutoverDecision:
        now = now or utc_now()
        self._authorize(CUTOVER_CONSUMER)
        self._validate_request(request, eligibility, now=now)
        self._assert_case_scope(request.scope)
        existing = self.store.get_latest("canonical_lane_cutover_decisions", request.cutover_id)
        if existing:
            if existing.get("content_digest") == request.request_digest:
                return LaneCutoverDecision.model_validate(existing)
            raise CutoverAuthorityConflict("cutover_idempotency_conflict")
        with self.store.transaction() as tx:
            case = self._require_case(tx, request.scope)
            control = self._require_control(tx, request.scope, case)
            self._assert_legacy_authority(control, request)
            self._validate_current_approval(request, now=now)
            self._assert_exact_store_bindings(tx, request)
            self._ensure_actor_snapshot(
                tx,
                scope=request.scope,
                actor_snapshot_ref=actor_snapshot_ref,
                permission_snapshot_ref=permission_snapshot_ref,
                correlation_id=correlation_id,
                now=now,
            )
            decision = self._decision(
                request,
                version=1,
                decision="requested",
                current_status="requested",
                actor_snapshot_ref=actor_snapshot_ref,
                permission_snapshot_ref=permission_snapshot_ref,
                correlation_id=correlation_id,
                now=now,
            )
            tx.insert("canonical_lane_cutover_decisions", request.cutover_id, 1, decision.model_dump(mode="json"))
            tx.append_event(
                self._event(
                    tx,
                    scope=request.scope,
                    event_type="PLANNING_CUTOVER_REQUESTED",
                    payload={
                        "cutover_id": request.cutover_id,
                        "request_digest": request.request_digest,
                        "approval_id": request.approval.approval_id,
                        "approval_registry_ref": request.approval.approval_registry_ref,
                        "state_subject": "lane_cutover_decision",
                        "decision_version_before": 0,
                        "decision_version_after": decision.decision_version,
                        "case_control_summary_version_before": int(control["summary_version"]),
                        "case_control_summary_version_after": int(control["summary_version"]),
                        "case_version_before": int(case["case_version"]),
                        "case_version_after": int(case["case_version"]),
                    },
                    state_version_before=0,
                    state_version_after=decision.decision_version,
                    actor_snapshot_ref=actor_snapshot_ref,
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        return decision

    def execute_cutover(
        self,
        request: LaneCutoverRequest,
        *,
        actor_snapshot_ref: str,
        permission_snapshot_ref: str,
        correlation_id: str,
        now: datetime | None = None,
    ) -> LaneCutoverDecision:
        now = now or utc_now()
        self._authorize(CUTOVER_CONSUMER)
        self._assert_case_scope(request.scope)
        with self.store.transaction() as tx:
            case = self._require_case(tx, request.scope)
            control = self._require_control(tx, request.scope, case)
            prior = tx.get_latest("canonical_lane_cutover_decisions", request.cutover_id)
            if not prior or prior.get("current_status") != "requested" or prior.get("content_digest") != request.request_digest:
                raise CutoverAuthorityConflict("cutover_request_missing_stale_or_tampered")
            self._assert_legacy_authority(control, request)
            self._validate_current_approval(request, now=now)
            self._assert_exact_store_bindings(tx, request)
            self._ensure_actor_snapshot(
                tx,
                scope=request.scope,
                actor_snapshot_ref=actor_snapshot_ref,
                permission_snapshot_ref=permission_snapshot_ref,
                correlation_id=correlation_id,
                now=now,
            )
            decision = self._decision(
                request,
                version=2,
                decision="approved",
                current_status="executed",
                actor_snapshot_ref=actor_snapshot_ref,
                permission_snapshot_ref=permission_snapshot_ref,
                correlation_id=correlation_id,
                now=now,
                effective_at=now,
            )
            next_control = CaseControlSummaryVersion.model_validate(
                {
                    **control,
                    "summary_version": int(control["summary_version"]) + 1,
                    "planning_authority": "canonical_for_lane",
                    "current_status": "planning_authoritative",
                    "supersedes_version_id": f"{control['summary_version_id']}:v{control['summary_version']}",
                    "recorded_at": now,
                }
            )
            next_case = InstitutionalResearchCase.model_validate(
                {
                    **case,
                    "case_version": int(case["case_version"]) + 1,
                    "current_status": CaseStatus.PLANNING_AUTHORITATIVE.value,
                    "supersedes_version_id": f"{case['case_id']}:v{case['case_version']}",
                    "recorded_at": now,
                }
            )
            tx.insert("canonical_lane_cutover_decisions", request.cutover_id, 2, decision.model_dump(mode="json"))
            tx.insert("canonical_case_control_versions", next_control.summary_version_id, next_control.summary_version, next_control.model_dump(mode="json"))
            tx.insert("canonical_research_cases", request.scope.case_id, next_case.case_version, next_case.model_dump(mode="json"))
            tx.append_event(
                self._event(
                    tx,
                    scope=request.scope,
                    event_type="PLANNING_CUTOVER_DECIDED",
                    payload={
                        "cutover_id": request.cutover_id,
                        "approval_id": request.approval.approval_id,
                        "approval_registry_ref": request.approval.approval_registry_ref,
                        "state_subject": "lane_cutover_decision",
                        "decision_version_before": int(prior["decision_version"]),
                        "decision_version_after": decision.decision_version,
                        "case_control_summary_version_before": int(control["summary_version"]),
                        "case_control_summary_version_after": int(control["summary_version"]),
                        "case_version_before": int(case["case_version"]),
                        "case_version_after": int(case["case_version"]),
                    },
                    state_version_before=int(prior["decision_version"]),
                    state_version_after=decision.decision_version,
                    actor_snapshot_ref=actor_snapshot_ref,
                    correlation_id=correlation_id,
                    now=now,
                )
            )
            tx.append_event(
                self._event(
                    tx,
                    scope=request.scope,
                    event_type="PLANNING_AUTHORITY_CHANGED",
                    payload={
                        "case_id": request.scope.case_id,
                        "authority": "canonical_for_lane",
                        "cutover_id": request.cutover_id,
                        "approval_id": request.approval.approval_id,
                        "approval_registry_ref": request.approval.approval_registry_ref,
                        "state_subject": "case_control_summary",
                        "decision_version_before": int(prior["decision_version"]),
                        "decision_version_after": decision.decision_version,
                        "case_control_summary_version_before": int(control["summary_version"]),
                        "case_control_summary_version_after": next_control.summary_version,
                        "case_version_before": int(case["case_version"]),
                        "case_version_after": next_case.case_version,
                    },
                    state_version_before=int(control["summary_version"]),
                    state_version_after=next_control.summary_version,
                    actor_snapshot_ref=actor_snapshot_ref,
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        return decision

    def rollback_cutover(
        self,
        request: LaneCutoverRequest,
        *,
        reason: str,
        actor_snapshot_ref: str,
        permission_snapshot_ref: str,
        correlation_id: str,
        now: datetime | None = None,
    ) -> LaneCutoverDecision:
        now = now or utc_now()
        if not reason.strip():
            raise PlanningCutoverError("rollback_reason_required")
        self._authorize(CUTOVER_CONSUMER)
        self._assert_case_scope(request.scope)
        with self.store.transaction(rollback_control=True) as tx:
            case = self._require_case(tx, request.scope)
            control = self._require_control(tx, request.scope, case)
            prior = tx.get_latest("canonical_lane_cutover_decisions", request.cutover_id)
            if not prior or prior.get("current_status") != "executed":
                raise CutoverAuthorityConflict("cutover_not_executed")
            if control.get("planning_authority") != "canonical_for_lane":
                raise CutoverAuthorityConflict("case_authority_not_canonical_for_lane")
            self._ensure_actor_snapshot(
                tx,
                scope=request.scope,
                actor_snapshot_ref=actor_snapshot_ref,
                permission_snapshot_ref=permission_snapshot_ref,
                correlation_id=correlation_id,
                now=now,
            )
            decision = self._decision(
                request,
                version=3,
                decision="rollback",
                current_status="rolled_back",
                actor_snapshot_ref=actor_snapshot_ref,
                permission_snapshot_ref=permission_snapshot_ref,
                correlation_id=correlation_id,
                now=now,
                effective_at=now,
                requested_authority="legacy",
                previous_authority="canonical_for_lane",
                extra_ref=f"rollback_reason:{reason}",
            )
            next_control = CaseControlSummaryVersion.model_validate(
                {
                    **control,
                    "summary_version": int(control["summary_version"]) + 1,
                    "planning_authority": "legacy",
                    "current_status": "rolled_back",
                    "supersedes_version_id": f"{control['summary_version_id']}:v{control['summary_version']}",
                    "recorded_at": now,
                }
            )
            next_case = InstitutionalResearchCase.model_validate(
                {
                    **case,
                    "case_version": int(case["case_version"]) + 1,
                    "current_status": CaseStatus.ROLLED_BACK.value,
                    "supersedes_version_id": f"{case['case_id']}:v{case['case_version']}",
                    "recorded_at": now,
                }
            )
            tx.insert("canonical_lane_cutover_decisions", request.cutover_id, 3, decision.model_dump(mode="json"))
            tx.insert("canonical_case_control_versions", next_control.summary_version_id, next_control.summary_version, next_control.model_dump(mode="json"))
            tx.insert("canonical_research_cases", request.scope.case_id, next_case.case_version, next_case.model_dump(mode="json"))
            tx.append_event(
                self._event(
                    tx,
                    scope=request.scope,
                    event_type="PLANNING_ROLLBACK_EXECUTED",
                    payload={
                        "cutover_id": request.cutover_id,
                        "reason": reason,
                        "authority": "legacy",
                        "approval_id": request.approval.approval_id,
                        "approval_registry_ref": request.approval.approval_registry_ref,
                        "state_subject": "case_control_summary",
                        "decision_version_before": int(prior["decision_version"]),
                        "decision_version_after": decision.decision_version,
                        "case_control_summary_version_before": int(control["summary_version"]),
                        "case_control_summary_version_after": next_control.summary_version,
                        "case_version_before": int(case["case_version"]),
                        "case_version_after": next_case.case_version,
                    },
                    state_version_before=int(control["summary_version"]),
                    state_version_after=next_control.summary_version,
                    actor_snapshot_ref=actor_snapshot_ref,
                    correlation_id=correlation_id,
                    now=now,
                )
            )
        return decision

    def get_read_model(
        self,
        scope: CutoverScope,
        *,
        mappings: tuple[LegacyProjectionMapping, ...] = (),
    ) -> PlanningAuthorityReadModel:
        self._authorize(READ_CONSUMER)
        self._assert_case_scope(scope)
        case = self.store.get_latest("canonical_research_cases", scope.case_id)
        if not case:
            raise PlanningCutoverError("case_not_found")
        self._assert_case_mapping_scope(case, scope)
        control = self.store.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
        if not control:
            raise PlanningCutoverError("case_control_summary_not_found")
        authority = str(control.get("planning_authority") or "legacy")
        if authority not in {"legacy", "canonical_for_lane"}:
            raise PlanningCutoverError("planning_authority_invalid")
        decision = self._latest_decision(scope.case_id, scope.lane_id)
        approved_contract_version_id: str | None = None
        if authority == "canonical_for_lane":
            if not decision or decision.get("current_status") != "executed":
                raise PlanningCutoverError("canonical_authority_decision_missing_or_not_executed")
            self._assert_decision_store_bindings(scope, decision)
            approved_contract_version_id = str(decision["approved_contract_version_id"])
        contracts = self.store.list_versions("canonical_decision_surface_contract_versions", case_id=scope.case_id)
        if not contracts:
            raise PlanningCutoverError("canonical_planning_contract_not_found")
        contract = (
            self._exact_row(contracts, "contract_version_id", approved_contract_version_id, "approved_contract_version")
            if approved_contract_version_id
            else sorted(contracts, key=lambda row: str(row.get("contract_version_id")))[-1]
        )
        cells = tuple(
            sorted(
                (
                    row
                    for row in self._latest_by_identity(
                        self.store.list_versions("canonical_decision_surface_cell_versions", case_id=scope.case_id),
                        identity_field="cell_id",
                        version_field="cell_version",
                    )
                    if row.get("contract_version_id") == contract["contract_version_id"]
                ),
                key=lambda row: str(row["cell_id"]),
            )
        )
        cell_version_ids = {str(row["cell_version_id"]) for row in cells}
        slots = tuple(
            sorted(
                (
                    row
                    for row in self._latest_by_identity(
                        self.store.list_versions("canonical_evidence_slot_versions", case_id=scope.case_id),
                        identity_field="evidence_slot_id",
                        version_field="slot_version",
                    )
                    if row["cell_version_id"] in cell_version_ids
                ),
                key=lambda row: str(row["evidence_slot_id"]),
            )
        )
        slot_version_ids = {str(row["slot_version_id"]) for row in slots}
        gaps = tuple(
            sorted(
                (
                    row
                    for row in self._latest_by_identity(
                        self.store.list_versions("canonical_compile_gap_versions", case_id=scope.case_id),
                        identity_field="gap_id",
                        version_field="gap_version",
                    )
                    if not row.get("slot_version_id") or row["slot_version_id"] in slot_version_ids
                ),
                key=lambda row: str(row["gap_id"]),
            )
        )
        legacy_projection = None
        if authority == "canonical_for_lane":
            legacy_projection = self.project_legacy_required_items(
                case_id=scope.case_id,
                contract=contract,
                cells=cells,
                slots=slots,
                mappings=mappings,
            )
        return PlanningAuthorityReadModel(
            scope=scope,
            authority=authority,
            contract=contract,
            cells=cells,
            slots=slots,
            gaps=gaps,
            current_cutover_decision=decision,
            legacy_projection=legacy_projection,
        )

    def project_legacy_required_items(
        self,
        *,
        case_id: str,
        contract: Mapping[str, Any],
        cells: tuple[Mapping[str, Any], ...],
        slots: tuple[Mapping[str, Any], ...],
        mappings: tuple[LegacyProjectionMapping, ...],
    ) -> LegacyRequiredItemProjection:
        cell_by_projection_key = {str(row.get("cell_key") or row["cell_id"]): row for row in cells}
        slot_by_cell = {}
        for slot in slots:
            slot_by_cell.setdefault(str(slot["cell_version_id"]), []).append(slot)
        required_items: list[dict[str, Any]] = []
        for mapping in mappings:
            cell = cell_by_projection_key.get(mapping.canonical_cell_key)
            if cell is None:
                raise PlanningCutoverError("legacy_projection_mapping_cell_missing")
            cell_slots = slot_by_cell.get(str(cell["cell_version_id"]), [])
            required_items.append(
                {
                    "required_item_id": mapping.legacy_required_item_id,
                    "question": cell["decision_question"],
                    "owner_role": cell["owner_role"],
                    "evidence_roles": tuple(sorted(str(slot["evidence_role"]) for slot in cell_slots)),
                    "source_policy_refs": tuple(sorted(str(slot["source_policy_ref"]) for slot in cell_slots)),
                    "read_only_projection": True,
                    "information_loss_tags": mapping.information_loss_tags,
                }
            )
        if not required_items:
            raise PlanningCutoverError("legacy_projection_mapping_required")
        return LegacyRequiredItemProjection(
            case_id=case_id,
            contract_version_id=str(contract["contract_version_id"]),
            planning_authority="canonical_for_lane",
            required_items=tuple(required_items),
            mapping_rows=mappings,
            projection_digest=canonical_digest({"contract": contract, "mappings": [row.model_dump(mode="json") for row in mappings]}),
        )

    def workbench_projection(
        self,
        scope: CutoverScope,
        *,
        mappings: tuple[LegacyProjectionMapping, ...] = (),
    ) -> WorkbenchDecisionSurfaceProjection:
        read_model = self.get_read_model(scope, mappings=mappings)
        return WorkbenchDecisionSurfaceProjection(
            case_id=scope.case_id,
            authority_label=read_model.authority,
            contract_version_id=str(read_model.contract["contract_version_id"]),
            cells=read_model.cells,
            slots=read_model.slots,
            gaps=read_model.gaps,
            cutover_decision=read_model.current_cutover_decision,
        )

    def recover_cutover(self, scope: CutoverScope) -> CutoverRecoveryReport:
        self._assert_case_scope(scope)
        case = self.store.get_latest("canonical_research_cases", scope.case_id)
        if not case:
            raise PlanningCutoverError("case_not_found")
        self._assert_case_mapping_scope(case, scope)
        control = self.store.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
        if not control:
            raise PlanningCutoverError("case_control_summary_not_found")
        decisions = [row for row in self.store.list_latest("canonical_lane_cutover_decisions", case_id=scope.case_id) if row.get("lane_id") == scope.lane_id]
        event_types = tuple(
            row["event_type"]
            for row in self.store.list_events()
            if row.get("payload", {}).get("cutover_id") in {row.get("cutover_id") for row in decisions}
        )
        recovery = self.store.recovery_check()
        errors = []
        if control.get("planning_authority") not in {"legacy", "canonical_for_lane"}:
            errors.append("invalid_case_authority")
        if control.get("planning_authority") == "canonical_for_lane" and "PLANNING_AUTHORITY_CHANGED" not in event_types:
            errors.append("authority_change_event_missing")
        return CutoverRecoveryReport(
            case_id=scope.case_id,
            status="pass" if recovery.get("status") == "pass" and not errors else "fail",
            authority=str(control.get("planning_authority")),
            decision_count=len(decisions),
            event_types=event_types,
            store_recovery_status=str(recovery.get("status")),
            errors=tuple(errors),
        )

    def read_only_preflight(
        self,
        scope: CutoverScope,
        *,
        downstream_consumer_ids: tuple[str, ...] = (),
    ) -> PlanningCutoverPreflight:
        """Inventory exact immutable bindings without requesting or changing authority."""
        self._authorize(READ_CONSUMER)
        self._assert_case_scope(scope)
        if downstream_consumer_ids:
            raise CutoverEligibilityError("synthetic_pilot_downstream_consumers_must_be_empty")
        case = self.store.get_latest("canonical_research_cases", scope.case_id)
        if not case:
            raise PlanningCutoverError("case_not_found")
        self._assert_case_mapping_scope(case, scope)
        control = self.store.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
        if not control:
            raise PlanningCutoverError("case_control_summary_not_found")
        contracts = self.store.list_versions("canonical_decision_surface_contract_versions", case_id=scope.case_id)
        artifacts = self.store.list_versions("canonical_artifact_versions", case_id=scope.case_id)
        if not contracts or not artifacts:
            raise PlanningCutoverError("pilot_preflight_contract_or_artifact_missing")
        contract = sorted(contracts, key=lambda row: str(row["contract_version_id"]))[-1]
        artifact = sorted(artifacts, key=lambda row: str(row["artifact_version_id"]))[-1]
        comparisons = [
            row
            for row in self.store.list_versions("canonical_shadow_comparisons", case_id=scope.case_id)
            if row.get("canonical_contract_version_id") == contract["contract_version_id"]
        ]
        if not comparisons:
            raise PlanningCutoverError("pilot_preflight_comparison_missing")
        comparison = sorted(comparisons, key=lambda row: str(row["comparison_id"]))[-1]
        return PlanningCutoverPreflight(
            scope=scope,
            store_identity=self.store.store_identity(),
            authority=str(control.get("planning_authority") or "legacy"),
            contract_version_id=str(contract["contract_version_id"]),
            contract_digest=canonical_digest(contract),
            artifact_version_id=str(artifact["artifact_version_id"]),
            artifact_digest=str(artifact["object_digest"]),
            comparison_id=str(comparison["comparison_id"]),
            comparison_digest=canonical_digest(comparison),
            downstream_consumer_count=0,
        )

    def _validate_request(self, request: LaneCutoverRequest, eligibility: LaneEligibilityRecord, *, now: datetime) -> None:
        if eligibility.scope != request.scope or eligibility.status != "eligible":
            raise CutoverEligibilityError("lane_not_eligible")
        self._validate_current_approval(request, now=now)
        required_refs = {
            request.schema_digest,
            request.policy_digest,
            request.store_identity,
            request.contract_version_id,
            request.contract_digest,
            request.artifact_version_id,
            request.artifact_digest,
            request.comparison_id,
            request.comparison_digest,
        }
        if not required_refs.issubset(set(request.gate_evidence_refs)):
            raise CutoverApprovalError("gate_evidence_hash_binding_incomplete")

    def _validate_current_approval(self, request: LaneCutoverRequest, *, now: datetime) -> None:
        approval = request.approval
        if self.approval_resolver is not None:
            approval = self.approval_resolver(request.approval.approval_id)
            if (
                approval.approval_id != request.approval.approval_id
                or approval.approval_registry_ref != request.approval.approval_registry_ref
            ):
                raise CutoverApprovalError("approval_resolver_identity_mismatch")
        elif approval.approver_type == "human":
            raise CutoverApprovalError("approval_revocation_resolver_required_for_human_cutover")
        if not approval.valid_for(request, now=now):
            raise CutoverApprovalError("approval_missing_expired_revoked_or_hash_mismatch")

    def _assert_exact_store_bindings(self, catalog: CanonicalStore | CanonicalTransaction, request: LaneCutoverRequest) -> None:
        self._assert_binding_values(
            catalog,
            request.scope,
            store_identity=request.store_identity,
            contract_version_id=request.contract_version_id,
            contract_digest=request.contract_digest,
            artifact_version_id=request.artifact_version_id,
            artifact_digest=request.artifact_digest,
            comparison_id=request.comparison_id,
            comparison_digest=request.comparison_digest,
        )

    def _assert_decision_store_bindings(self, scope: CutoverScope, decision: Mapping[str, Any]) -> None:
        self._assert_binding_values(
            self.store,
            scope,
            store_identity=str(decision.get("approved_store_identity") or ""),
            contract_version_id=str(decision.get("approved_contract_version_id") or ""),
            contract_digest=str(decision.get("approved_contract_digest") or ""),
            artifact_version_id=str(decision.get("approved_artifact_version_id") or ""),
            artifact_digest=str(decision.get("approved_artifact_digest") or ""),
            comparison_id=str(decision.get("approved_comparison_id") or ""),
            comparison_digest=str(decision.get("approved_comparison_digest") or ""),
        )

    def _assert_binding_values(
        self,
        catalog: CanonicalStore | CanonicalTransaction,
        scope: CutoverScope,
        *,
        store_identity: str,
        contract_version_id: str,
        contract_digest: str,
        artifact_version_id: str,
        artifact_digest: str,
        comparison_id: str,
        comparison_digest: str,
    ) -> None:
        if store_identity != self.store.store_identity():
            raise CutoverApprovalError("approved_store_identity_mismatch")
        contract = self._exact_row(
            self._catalog_rows(catalog, "canonical_decision_surface_contract_versions", scope.case_id),
            "contract_version_id",
            contract_version_id,
            "approved_contract_version",
        )
        artifact = self._exact_row(
            self._catalog_rows(catalog, "canonical_artifact_versions", scope.case_id),
            "artifact_version_id",
            artifact_version_id,
            "approved_artifact_version",
        )
        comparison = self._exact_row(
            self._catalog_rows(catalog, "canonical_shadow_comparisons", scope.case_id),
            "comparison_id",
            comparison_id,
            "approved_comparison",
        )
        if canonical_digest(contract) != contract_digest:
            raise CutoverApprovalError("approved_contract_digest_mismatch")
        if str(artifact.get("object_digest") or "") != artifact_digest:
            raise CutoverApprovalError("approved_artifact_digest_mismatch")
        if comparison.get("canonical_contract_version_id") != contract_version_id:
            raise CutoverApprovalError("approved_comparison_contract_mismatch")
        if canonical_digest(comparison) != comparison_digest:
            raise CutoverApprovalError("approved_comparison_digest_mismatch")

    @staticmethod
    def _exact_row(
        rows: Sequence[Mapping[str, Any]],
        field: str,
        expected: str | None,
        error_prefix: str,
    ) -> Mapping[str, Any]:
        if not expected:
            raise PlanningCutoverError(f"{error_prefix}_missing")
        matches = [row for row in rows if str(row.get(field) or "") == expected]
        if len(matches) != 1:
            raise PlanningCutoverError(f"{error_prefix}_missing_or_ambiguous")
        return matches[0]

    @staticmethod
    def _catalog_rows(
        catalog: CanonicalStore | CanonicalTransaction,
        table: str,
        case_id: str,
    ) -> Sequence[Mapping[str, Any]]:
        return catalog.list_versions(table, case_id=case_id)

    @staticmethod
    def _latest_by_identity(
        rows: Sequence[Mapping[str, Any]],
        *,
        identity_field: str,
        version_field: str,
    ) -> tuple[Mapping[str, Any], ...]:
        latest: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            identity = str(row[identity_field])
            current = latest.get(identity)
            if current is None or int(row[version_field]) > int(current[version_field]):
                latest[identity] = row
        return tuple(latest.values())

    def _assert_case_scope(self, scope: CutoverScope) -> None:
        if not all((scope.tenant_id.strip(), scope.project_id.strip(), scope.case_id.strip(), scope.lane_id.strip())):
            raise CutoverEligibilityError("case_scope_fields_required")

    def _authorize(self, consumer: str) -> None:
        self.flags.authorize(CUTOVER_FLAG_ID, mode=CUTOVER_MODE, consumer=consumer, grants=self.grants)

    @staticmethod
    def _require_case(tx: CanonicalTransaction, scope: CutoverScope) -> Mapping[str, Any]:
        case = tx.get_latest("canonical_research_cases", scope.case_id)
        if not case:
            raise PlanningCutoverError("case_not_found")
        if case.get("tenant_id") != scope.tenant_id or case.get("project_id") != scope.project_id or case.get("case_id") != scope.case_id:
            raise PlanningCutoverError("tenant_project_case_scope_mismatch")
        return case

    @staticmethod
    def _assert_legacy_authority(control: Mapping[str, Any], request: LaneCutoverRequest) -> None:
        if control.get("planning_authority") != "legacy":
            raise CutoverAuthorityConflict("previous_authority_must_be_legacy")
        if int(control.get("summary_version", 0)) != request.expected_authority_version:
            raise CutoverAuthorityConflict("stale_authority_version")

    @staticmethod
    def _assert_case_mapping_scope(case: Mapping[str, Any], scope: CutoverScope) -> None:
        if case.get("tenant_id") != scope.tenant_id or case.get("project_id") != scope.project_id or case.get("case_id") != scope.case_id:
            raise PlanningCutoverError("tenant_project_case_scope_mismatch")

    @staticmethod
    def _require_control(
        tx: CanonicalTransaction,
        scope: CutoverScope,
        case: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        control = tx.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
        if not control:
            raise PlanningCutoverError("case_control_summary_not_found")
        if control.get("tenant_id") != scope.tenant_id or control.get("project_id") != scope.project_id or control.get("case_id") != scope.case_id:
            raise PlanningCutoverError("case_control_scope_mismatch")
        return control

    @staticmethod
    def _decision(
        request: LaneCutoverRequest,
        *,
        version: int,
        decision: str,
        current_status: str,
        actor_snapshot_ref: str,
        permission_snapshot_ref: str,
        correlation_id: str,
        now: datetime,
        effective_at: datetime | None = None,
        requested_authority: str = "canonical_for_lane",
        previous_authority: str = "legacy",
        extra_ref: str | None = None,
    ) -> LaneCutoverDecision:
        refs = (*request.gate_evidence_refs, f"request_digest:{request.request_digest}")
        if extra_ref:
            refs = (*refs, extra_ref)
        return LaneCutoverDecision(
            tenant_id=request.scope.tenant_id,
            project_id=request.scope.project_id,
            case_id=request.scope.case_id,
            created_at=now,
            recorded_at=now,
            actor_snapshot_ref=actor_snapshot_ref,
            permission_snapshot_ref=permission_snapshot_ref,
            policy_config_refs=(request.policy_digest,),
            correlation_id=correlation_id,
            content_digest=request.request_digest,
            current_status=current_status,
            cutover_id=request.cutover_id,
            decision_version=version,
            lane_id=request.scope.lane_id,
            decision=decision,
            gate_evidence_refs=refs,
            previous_authority=previous_authority,
            requested_authority=requested_authority,
            approved_store_identity=request.store_identity,
            approved_contract_version_id=request.contract_version_id,
            approved_contract_digest=request.contract_digest,
            approved_artifact_version_id=request.artifact_version_id,
            approved_artifact_digest=request.artifact_digest,
            approved_comparison_id=request.comparison_id,
            approved_comparison_digest=request.comparison_digest,
            approval_id=request.approval.approval_id,
            approval_registry_ref=request.approval.approval_registry_ref,
            effective_at=effective_at,
        )

    @staticmethod
    def _event(
        tx: CanonicalTransaction,
        *,
        scope: CutoverScope,
        event_type: str,
        payload: Mapping[str, Any],
        state_version_before: int,
        state_version_after: int,
        actor_snapshot_ref: str,
        correlation_id: str,
        now: datetime,
    ) -> EventEnvelope:
        return EventEnvelope(
            event_id=f"event_{uuid4().hex}",
            event_type=event_type,
            sequence_no=tx.next_event_sequence(None),
            occurred_at=now,
            recorded_at=now,
            actor_snapshot_ref=actor_snapshot_ref,
            correlation_id=correlation_id,
            state_version_before=state_version_before,
            state_version_after=state_version_after,
            payload_digest=canonical_digest(payload),
            payload=dict(payload),
        )

    @staticmethod
    def _ensure_actor_snapshot(
        tx: CanonicalTransaction,
        *,
        scope: CutoverScope,
        actor_snapshot_ref: str,
        permission_snapshot_ref: str,
        correlation_id: str,
        now: datetime,
    ) -> None:
        existing = tx.get_latest("canonical_actor_snapshots", actor_snapshot_ref)
        if existing:
            if existing.get("tenant_id") != scope.tenant_id or existing.get("project_id") != scope.project_id:
                raise PlanningCutoverError("actor_snapshot_scope_mismatch")
            return
        snapshot = ActorSnapshot(
            tenant_id=scope.tenant_id,
            project_id=scope.project_id,
            created_at=now,
            recorded_at=now,
            actor_snapshot_ref=actor_snapshot_ref,
            permission_snapshot_ref=permission_snapshot_ref,
            correlation_id=correlation_id,
            actor_snapshot_id=actor_snapshot_ref,
            snapshot_version=1,
            actor_id=actor_snapshot_ref,
            actor_type="cutover_control_actor",
            display_name=actor_snapshot_ref,
            current_status="active",
        )
        tx.insert("canonical_actor_snapshots", actor_snapshot_ref, 1, snapshot.model_dump(mode="json"))

    def _latest_decision(self, case_id: str, lane_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.store.list_latest("canonical_lane_cutover_decisions", case_id=case_id) if row.get("lane_id") == lane_id]
        if not rows:
            return None
        return max(rows, key=lambda row: int(row.get("decision_version", 0)))
