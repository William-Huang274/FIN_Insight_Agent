from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.candidate_bundle import CandidateBundle
from sec_agent.canonical_runtime.evidence_gate import EvidenceGatePolicy, FixtureEvidenceGate
from sec_agent.canonical_runtime.evidence_request import EvidenceRequest
from sec_agent.canonical_runtime.models import (
    EvidenceRepairOutcomeVersion,
    EventEnvelope,
    LeadReviewDecisionVersion,
    NumericWorkbenchProjectionVersion,
    WorkpaperProjectionVersion,
    canonical_digest,
    utc_now,
)
from sec_agent.canonical_runtime.parser_numeric import (
    NumericFixtureObservation,
    ParserNumericFixtureCompiler,
    ParserNumericPolicy,
)
from sec_agent.canonical_runtime.store import IdempotencyConflict, TransactionConflict
from sec_agent.runtime_resource_registry import read_registered_runtime_json

from .case_service import CasePrincipal, CaseService, load_p36_candidate_profile
from .evidence_service import EvidenceService, EvidenceServiceError


CONTRACT_RELATIVE_PATH = (
    "configs/releases/fin_ia_0_1_vt2_three_cell_integrity_workpaper_contract_v1_0.json"
)
CONTRACT_RESOURCE_ID = "application.contract.integrity_workpaper"
REPAIR_TABLE = "canonical_evidence_repair_outcome_versions"
NUMERIC_TABLE = "canonical_numeric_workbench_projection_versions"
WORKPAPER_TABLE = "canonical_workpaper_projection_versions"
LEAD_REVIEW_TABLE = "canonical_lead_review_decision_versions"


@dataclass(frozen=True)
class ExecuteRepairDraft:
    expected_workspace_version: int
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class CompileNumericDraft:
    expected_evidence_workspace_version: int
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class CompileWorkpaperDraft:
    expected_numeric_workspace_version: int
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class LeadReviewDraft:
    expected_workpaper_version: int
    expected_content_digest: str
    decision: str
    reason: str
    actor_ref: str
    idempotency_key: str


class IntegrityServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class IntegrityService:
    """Fixture-only Point 3-5 vertical product boundary."""

    def __init__(
        self,
        facade: Any | None,
        evidence: EvidenceService,
        *,
        contract: Mapping[str, Any],
        p36_profile: Mapping[str, Any] | None = None,
    ):
        self._facade = facade
        self._evidence = evidence
        self._contract = dict(contract)
        self._p36_profile = dict(p36_profile or {})
        self._configure()

    @classmethod
    def from_services(
        cls,
        case_service: CaseService,
        evidence_service: EvidenceService,
        *,
        repo_root: str | Path,
    ) -> "IntegrityService":
        contract = read_registered_runtime_json(repo_root, CONTRACT_RESOURCE_ID)
        return cls(
            getattr(case_service, "_facade", None),
            evidence_service,
            contract=contract,
            p36_profile=load_p36_candidate_profile(repo_root),
        )

    def _configure(self) -> None:
        if self._contract.get("schema_version") != (
            "fin_ia_0_1_vt2_three_cell_integrity_workpaper_contract_v1_0"
        ):
            raise ValueError("vt2_integrity_contract_version_invalid")
        boundaries = self._contract["hard_boundaries"]
        for key in (
            "network_calls",
            "tool_invocations",
            "model_calls",
            "provider_calls",
            "paid_full_chain",
            "writer_execution",
            "runtime_promotion",
            "release_evidence",
        ):
            if boundaries.get(key) != 0:
                raise ValueError(f"vt2_integrity_boundary_open:{key}")
        numeric = self._contract["numeric_fixture"]
        self._parser = ParserNumericFixtureCompiler(
            policy=ParserNumericPolicy.model_validate(numeric["parser_policy"])
        )
        self._gate = FixtureEvidenceGate(
            policy=EvidenceGatePolicy.model_validate(numeric["evidence_gate_policy"])
        )
        self._contract_digest = canonical_digest(self._contract)

    def execute_repair(
        self,
        case_id: str,
        evidence_slot_id: str,
        draft: ExecuteRepairDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_command(
            case_id,
            draft.actor_ref,
            draft.idempotency_key,
            principal,
            "evidence:repair",
            trace_id,
        )
        store = self._store()
        payload_digest = canonical_digest(
            {"operation": "execute_repair", "case_id": case_id, "slot": evidence_slot_id, **draft.__dict__}
        )
        scope_key = self._scope(case_id, draft.idempotency_key, principal)
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._evidence._case_row(tx, case_id, principal)
                    self._evidence._actor_snapshot(tx, draft.actor_ref, principal)
                    projection = self._evidence._projection_row(tx, case_id, principal)
                    assert projection is not None
                    current_version = self._evidence._workspace_version(tx, projection)
                    if draft.expected_workspace_version != current_version:
                        raise IntegrityServiceError(
                            "version_conflict",
                            409,
                            expected_version=draft.expected_workspace_version,
                            current_version=current_version,
                        )
                    slot = self._slot(projection, evidence_slot_id)
                    repair_contract = self._contract["repair_fixture"]
                    if slot["evidence_role"] != repair_contract["target_evidence_role"]:
                        raise IntegrityServiceError("repair_fixture_role_not_admitted", 409)
                    requests = [
                        row
                        for row in self._evidence._actions(
                            tx, case_id, principal, str(projection["workspace_id"])
                        )
                        if row["action_type"] == "request_repair"
                        and row["evidence_slot_id"] == evidence_slot_id
                    ]
                    if not requests:
                        raise IntegrityServiceError("repair_request_required", 409)
                    request_action = requests[-1]
                    existing = self._repair_rows(tx, case_id, principal, str(projection["workspace_id"]))
                    if any(row["evidence_slot_id"] == evidence_slot_id for row in existing):
                        raise IntegrityServiceError("repair_already_completed", 409)
                    candidate = self._repair_candidate(repair_contract["candidate"])
                    outcome_id = "repair_outcome_" + canonical_digest(
                        {
                            "workspace_id": projection["workspace_id"],
                            "slot_id": evidence_slot_id,
                            "request_action_id": request_action["review_action_id"],
                            "candidate_id": candidate["candidate_id"],
                        }
                    )[:24]
                    outcome = EvidenceRepairOutcomeVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._evidence._permission_ref(principal),
                        policy_config_refs=(
                            "vt2.three_cell.repair.fixture.internal",
                            f"contract:{self._contract_digest}",
                        ),
                        correlation_id=trace_id,
                        current_status="completed_fixture",
                        repair_outcome_id=outcome_id,
                        repair_outcome_version_id=f"{outcome_id}:v1",
                        repair_outcome_version=1,
                        workspace_id=str(projection["workspace_id"]),
                        workspace_projection_version_id=str(projection["projection_version_id"]),
                        workspace_version_before=current_version,
                        workspace_version_after=current_version + 1,
                        request_review_action_id=str(request_action["review_action_id"]),
                        evidence_slot_id=evidence_slot_id,
                        attempt_no=1,
                        attempt_state="completed_fixture_no_retry",
                        route_id=str(candidate["route_id"]),
                        candidate=candidate,
                        model_call_count=0,
                        external_call_count=0,
                        tool_invocation_count=0,
                    )
                    outcome = self._with_digest(outcome)
                    tx.insert(REPAIR_TABLE, outcome_id, 1, outcome.model_dump(mode="json"))
                    event = self._event(
                        tx,
                        event_type="EVIDENCE_REPAIR_COMPLETED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        work_unit_id=str(projection["work_unit_id"]),
                        state_before=current_version,
                        state_after=current_version + 1,
                        payload={
                            "workspace_id": projection["workspace_id"],
                            "repair_outcome_id": outcome_id,
                            "evidence_slot_id": evidence_slot_id,
                            "candidate_id": candidate["candidate_id"],
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {"repair_outcome_id": outcome_id, "workspace_version": current_version + 1},
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self._evidence.get_workbench(case_id, principal)

    def get_numeric(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "numeric:read")
        row = self._single_row(NUMERIC_TABLE, case_id, principal, "numeric_workspace_not_found")
        return self._numeric_view(row)

    def compile_numeric(
        self,
        case_id: str,
        draft: CompileNumericDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_command(
            case_id,
            draft.actor_ref,
            draft.idempotency_key,
            principal,
            "numeric:write",
            trace_id,
        )
        store = self._store()
        payload_digest = canonical_digest(
            {"operation": "compile_numeric", "case_id": case_id, **draft.__dict__}
        )
        scope_key = self._scope(case_id, draft.idempotency_key, principal)
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._evidence._case_row(tx, case_id, principal)
                    self._evidence._actor_snapshot(tx, draft.actor_ref, principal)
                    projection = self._evidence._projection_row(tx, case_id, principal)
                    assert projection is not None
                    evidence_version = self._evidence._workspace_version(tx, projection)
                    if draft.expected_evidence_workspace_version != evidence_version:
                        raise IntegrityServiceError(
                            "version_conflict",
                            409,
                            expected_version=draft.expected_evidence_workspace_version,
                            current_version=evidence_version,
                        )
                    if not self._repair_rows(tx, case_id, principal, str(projection["workspace_id"])):
                        raise IntegrityServiceError("completed_repair_required", 409)
                    if self._rows(tx, NUMERIC_TABLE, case_id, principal):
                        raise IntegrityServiceError("numeric_workspace_already_compiled", 409)
                    slot = self._slot_by_role(projection, self._contract["numeric_fixture"]["source_evidence_role"])
                    request = EvidenceRequest.model_validate(slot.get("request_contract"))
                    bundle = CandidateBundle.model_validate(slot.get("candidate_bundle_contract"))
                    numeric_contract = self._contract["numeric_fixture"]
                    observation = NumericFixtureObservation.model_validate(numeric_contract["observation"])
                    parser = self._parser.compile(
                        bundle=bundle,
                        observation=observation,
                        metric_definition_ref=numeric_contract["metric_definition_ref"],
                    )
                    gate = self._gate.evaluate(
                        request=request,
                        bundle=bundle,
                        parser_candidate=parser.parser_candidate,
                        fact=parser.normalized_fact,
                        trace=parser.trace,
                    )
                    if gate.decision.decision != "fixture_accepted_for_gate_simulation":
                        raise IntegrityServiceError(
                            "numeric_fixture_gate_rejected",
                            409,
                            hard_failure_codes=list(gate.decision.hard_failure_codes),
                        )
                    promotion_payload = {
                        **numeric_contract["internal_promotion"],
                        "fixture_gate_decision_id": gate.decision.decision_id,
                        "fixture_gate_decision_digest": gate.decision.decision_digest,
                        "normalized_fact_digest": parser.normalized_fact.normalized_fact_digest,
                        "numeric_trace_digest": parser.trace.trace_digest,
                    }
                    promotion_digest = canonical_digest(promotion_payload)
                    promotion_decision_id = f"internal_fixture_promotion_{promotion_digest[:20]}"
                    candidate = next(
                        item for item in bundle.candidates if item.candidate_id == observation.candidate_id
                    )
                    fact = {
                        "cell_id": slot["cell_id"],
                        "evidence_slot_id": slot["evidence_slot_id"],
                        "candidate_id": candidate.candidate_id,
                        "parser_candidate_id": parser.parser_candidate.parser_candidate_id,
                        "normalized_fact_id": parser.normalized_fact.normalized_fact_id,
                        "numeric_trace_id": parser.trace.numeric_trace_id,
                        "promotion_decision_id": promotion_decision_id,
                        "entity_ref": candidate.entity_ref,
                        "row_label": parser.normalized_fact.row_label,
                        "normalized_value": parser.normalized_fact.normalized_value,
                        "unit": parser.normalized_fact.unit,
                        "scale_multiplier": parser.normalized_fact.scale_multiplier,
                        "period": parser.normalized_fact.period,
                        "source_coordinate": parser.normalized_fact.source_coordinate,
                        "metric_definition_ref": parser.trace.metric_definition_ref,
                        "program_steps": list(parser.trace.program_steps),
                        "output_value": parser.trace.output_value,
                        "promotion_status": numeric_contract["internal_promotion"]["decision"],
                        "promotion_scope": numeric_contract["internal_promotion"]["scope"],
                        "writer_citable": False,
                        "boundary": "Internal fixture judgment only; not writer-citable and not release evidence.",
                    }
                    workspace_id = "numeric_workspace_" + canonical_digest(
                        {
                            "case_id": case_id,
                            "evidence_workspace_id": projection["workspace_id"],
                            "evidence_workspace_version": evidence_version,
                            "fact_id": fact["normalized_fact_id"],
                        }
                    )[:24]
                    numeric = NumericWorkbenchProjectionVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._evidence._permission_ref(principal),
                        policy_config_refs=(
                            "vt2.three_cell.numeric.fixture.internal",
                            f"contract:{self._contract_digest}",
                        ),
                        correlation_id=trace_id,
                        current_status="compiled_fixture",
                        numeric_workspace_id=workspace_id,
                        numeric_projection_version_id=f"{workspace_id}:v1",
                        numeric_workspace_version=1,
                        evidence_workspace_id=str(projection["workspace_id"]),
                        evidence_projection_version_id=str(projection["projection_version_id"]),
                        evidence_workspace_version=evidence_version,
                        facts=(fact,),
                        hard_boundaries=dict(self._contract["hard_boundaries"]),
                    )
                    numeric = self._with_digest(numeric)
                    tx.insert(NUMERIC_TABLE, workspace_id, 1, numeric.model_dump(mode="json"))
                    event = self._event(
                        tx,
                        event_type="NUMERIC_FIXTURE_COMPILED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        work_unit_id=str(projection["work_unit_id"]),
                        state_before=0,
                        state_after=1,
                        payload={
                            "numeric_workspace_id": workspace_id,
                            "numeric_workspace_version": 1,
                            "evidence_workspace_id": projection["workspace_id"],
                            "fact_ids": [fact["normalized_fact_id"]],
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {"numeric_workspace_id": workspace_id, "numeric_workspace_version": 1},
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self.get_numeric(case_id, principal)

    def get_workpaper(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "workpaper:read")
        row = self._single_row(WORKPAPER_TABLE, case_id, principal, "workpaper_not_found")
        return self._workpaper_view(row, principal)

    def compile_workpaper(
        self,
        case_id: str,
        draft: CompileWorkpaperDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_command(
            case_id,
            draft.actor_ref,
            draft.idempotency_key,
            principal,
            "workpaper:write",
            trace_id,
        )
        store = self._store()
        payload_digest = canonical_digest(
            {"operation": "compile_workpaper", "case_id": case_id, **draft.__dict__}
        )
        scope_key = self._scope(case_id, draft.idempotency_key, principal)
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._evidence._case_row(tx, case_id, principal)
                    self._evidence._actor_snapshot(tx, draft.actor_ref, principal)
                    if self._rows(tx, WORKPAPER_TABLE, case_id, principal):
                        raise IntegrityServiceError("workpaper_already_compiled", 409)
                    numeric = self._single_row_from(tx, NUMERIC_TABLE, case_id, principal, "numeric_workspace_required")
                    if draft.expected_numeric_workspace_version != int(numeric["numeric_workspace_version"]):
                        raise IntegrityServiceError(
                            "version_conflict",
                            409,
                            expected_version=draft.expected_numeric_workspace_version,
                            current_version=numeric["numeric_workspace_version"],
                        )
                    evidence = self._evidence._projection_row(tx, case_id, principal)
                    assert evidence is not None
                    evidence_version = self._evidence._workspace_version(tx, evidence)
                    repair_rows = self._repair_rows(tx, case_id, principal, str(evidence["workspace_id"]))
                    if not repair_rows:
                        raise IntegrityServiceError("completed_repair_required", 409)
                    cells = {
                        str(row["cell_id"]): row
                        for row in tx.list_versions("canonical_decision_surface_cell_versions", case_id=case_id)
                        if self._matches(row, case_id, principal)
                        and row.get("contract_version_id") == evidence["contract_version_id"]
                    }
                    rejected = {
                        str(row["candidate_id"])
                        for row in self._evidence._actions(
                            tx, case_id, principal, str(evidence["workspace_id"])
                        )
                        if row["action_type"] == "reject_candidate" and row.get("candidate_id")
                    }
                    workpaper_profile = self._workpaper_profile_for(evidence)
                    required_roles = tuple(workpaper_profile["required_judgment_roles"])
                    judgments = tuple(
                        self._judgment(
                            slot,
                            cells[str(slot["cell_id"])],
                            numeric,
                            repair_rows,
                            rejected,
                            workpaper_profile,
                        )
                        for slot in evidence["evidence_slots"]
                        if slot["evidence_role"] in required_roles
                    )
                    if len(judgments) != len(required_roles):
                        raise IntegrityServiceError("p36_judgment_cardinality_violation", 409)
                    workpaper_id = "workpaper_" + canonical_digest(
                        {
                            "case_id": case_id,
                            "evidence_workspace_id": evidence["workspace_id"],
                            "evidence_workspace_version": evidence_version,
                            "numeric_workspace_id": numeric["numeric_workspace_id"],
                            "judgment_ids": [row["judgment_id"] for row in judgments],
                        }
                    )[:24]
                    workpaper = WorkpaperProjectionVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._evidence._permission_ref(principal),
                        policy_config_refs=(
                            "vt4.p36.workpaper.fixture.internal"
                            if len(required_roles) > 3
                            else "vt2.three_cell.workpaper.fixture.internal",
                            "contract:"
                            + (
                                canonical_digest(self._p36_profile)
                                if len(required_roles) > 3
                                else self._contract_digest
                            ),
                        ),
                        correlation_id=trace_id,
                        current_status="awaiting_lead_review",
                        workpaper_id=workpaper_id,
                        workpaper_projection_version_id=f"{workpaper_id}:v1",
                        workpaper_version=1,
                        evidence_workspace_id=str(evidence["workspace_id"]),
                        evidence_workspace_version=evidence_version,
                        numeric_workspace_id=str(numeric["numeric_workspace_id"]),
                        numeric_workspace_version=int(numeric["numeric_workspace_version"]),
                        judgments=judgments,
                        hard_boundaries=dict(self._contract["hard_boundaries"]),
                    )
                    workpaper = self._with_digest(workpaper)
                    tx.insert(WORKPAPER_TABLE, workpaper_id, 1, workpaper.model_dump(mode="json"))
                    event = self._event(
                        tx,
                        event_type="WORKPAPER_FIXTURE_COMPILED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        work_unit_id=str(evidence["work_unit_id"]),
                        state_before=0,
                        state_after=1,
                        payload={
                            "workpaper_id": workpaper_id,
                            "workpaper_version": 1,
                            "judgment_ids": [row["judgment_id"] for row in judgments],
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {"workpaper_id": workpaper_id, "workpaper_version": 1},
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self.get_workpaper(case_id, principal)

    def complete_lead_review(
        self,
        case_id: str,
        draft: LeadReviewDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_command(
            case_id,
            draft.actor_ref,
            draft.idempotency_key,
            principal,
            "lead_review:decide",
            trace_id,
        )
        if draft.decision not in self._contract["workpaper_fixture"]["lead_review_decisions"]:
            raise IntegrityServiceError("lead_review_decision_not_allowed", 422)
        if not draft.reason.strip():
            raise IntegrityServiceError("lead_review_reason_required", 422)
        store = self._store()
        payload_digest = canonical_digest(
            {"operation": "complete_lead_review", "case_id": case_id, **draft.__dict__}
        )
        scope_key = self._scope(case_id, draft.idempotency_key, principal)
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._evidence._case_row(tx, case_id, principal)
                    self._evidence._actor_snapshot(tx, draft.actor_ref, principal)
                    workpaper = self._single_row_from(tx, WORKPAPER_TABLE, case_id, principal, "workpaper_required")
                    if draft.expected_workpaper_version != int(workpaper["workpaper_version"]):
                        raise IntegrityServiceError("version_conflict", 409)
                    if draft.expected_content_digest != workpaper["content_digest"]:
                        raise IntegrityServiceError("workpaper_content_digest_mismatch", 409)
                    if self._rows(tx, LEAD_REVIEW_TABLE, case_id, principal):
                        raise IntegrityServiceError("workpaper_already_reviewed", 409)
                    review_id = "lead_review_" + canonical_digest(
                        {
                            "workpaper_id": workpaper["workpaper_id"],
                            "content_digest": workpaper["content_digest"],
                            "decision": draft.decision,
                            "actor_ref": draft.actor_ref,
                        }
                    )[:24]
                    admission = None
                    if draft.decision == "admit_fixture_writer_preview":
                        admission = {
                            "writer_admission_id": "writer_admission_" + canonical_digest(
                                {"review_id": review_id, "workpaper": workpaper["content_digest"]}
                            )[:24],
                            "status": "fixture_preview_admitted",
                            "scope": "fixture_preview_only_no_writer_execution",
                            "fixture_only": True,
                            "writer_execution_authorized": False,
                            "boundary": "Point 6 Writer has not executed; this admission cannot be used as release evidence.",
                            "admitted_at": utc_now().isoformat(),
                        }
                    review = LeadReviewDecisionVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._evidence._permission_ref(principal),
                        policy_config_refs=(
                            "vt4.p36.lead_review.fixture.internal"
                            if len(workpaper["judgments"]) > 3
                            else "vt2.three_cell.lead_review.fixture.internal",
                            str(workpaper["policy_config_refs"][-1]),
                        ),
                        correlation_id=trace_id,
                        current_status=draft.decision,
                        lead_review_id=review_id,
                        lead_review_version_id=f"{review_id}:v1",
                        lead_review_version=1,
                        workpaper_id=str(workpaper["workpaper_id"]),
                        workpaper_projection_version_id=str(workpaper["workpaper_projection_version_id"]),
                        workpaper_version=int(workpaper["workpaper_version"]),
                        workpaper_content_digest=str(workpaper["content_digest"]),
                        decision=draft.decision,
                        reason=draft.reason.strip(),
                        writer_admission=admission,
                    )
                    review = self._with_digest(review)
                    tx.insert(LEAD_REVIEW_TABLE, review_id, 1, review.model_dump(mode="json"))
                    evidence = self._evidence._projection_row(tx, case_id, principal)
                    assert evidence is not None
                    event = self._event(
                        tx,
                        event_type="LEAD_REVIEW_COMPLETED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        work_unit_id=str(evidence["work_unit_id"]),
                        state_before=0,
                        state_after=1,
                        payload={
                            "workpaper_id": workpaper["workpaper_id"],
                            "lead_review_id": review_id,
                            "decision": draft.decision,
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {"lead_review_id": review_id, "workpaper_id": workpaper["workpaper_id"]},
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self.get_workpaper(case_id, principal)

    def _judgment(
        self,
        slot: Mapping[str, Any],
        cell: Mapping[str, Any],
        numeric: Mapping[str, Any],
        repairs: list[Mapping[str, Any]],
        rejected: set[str],
        workpaper_profile: Mapping[str, Any],
    ) -> dict[str, Any]:
        role = str(slot["evidence_role"])
        evidence_refs = [
            str(row["candidate_id"])
            for row in slot["candidate_bundle_contract"]["candidates"]
            if row["candidate_id"] not in rejected
        ]
        repair_refs = [
            str(row["repair_outcome_id"])
            for row in repairs
            if row["evidence_slot_id"] == slot["evidence_slot_id"]
        ]
        if repair_refs:
            evidence_refs.extend(
                str(row["candidate"]["candidate_id"])
                for row in repairs
                if row["evidence_slot_id"] == slot["evidence_slot_id"]
            )
        numeric_refs = [
            str(row["normalized_fact_id"])
            for row in numeric["facts"]
            if row["evidence_slot_id"] == slot["evidence_slot_id"]
        ]
        fallback_templates = {
            "demand_signal": (
                "Issuer demand evidence and neighboring hyperscaler capacity context support a bounded demand signal, while live-source validation remains deferred.",
                "Reported growth may reflect pull-forward or capacity ordering rather than durable end demand.",
                ["live_source_not_executed"],
                "medium",
            ),
            "revenue_capture": (
                "The advanced-packaging capacity fixture supplies a reproducible bottleneck metric, but it does not by itself prove issuer margin capture.",
                "Upstream constraints may capture economics while accelerator or server margins dilute.",
                ["margin_capture_not_proven"],
                "medium",
            ),
            "thesis_counterevidence": (
                "The completed policy repair identifies export-control scope as material counterevidence to shipment and customer-access assumptions.",
                "A narrower live policy scope or rapid compliant product redesign could reduce the modeled risk.",
                ["live_policy_validation_not_executed"],
                "low",
            ),
        }
        templates = workpaper_profile.get("judgment_templates") or fallback_templates
        template = templates[role]
        if isinstance(template, Mapping):
            judgment = str(template["judgment"])
            counter_thesis = str(template["counter_thesis"])
            gaps = [str(value) for value in template["remaining_gaps"]]
            confidence = str(template["confidence"])
        else:
            judgment, counter_thesis, gaps, confidence = template
        payload = {
            "cell_id": slot["cell_id"],
            "evidence_role": role,
            "decision_question": slot["decision_question"],
            "owner_role": slot["owner"],
            "judgment_status": workpaper_profile["judgment_status_by_role"][role],
            "confidence": confidence,
            "judgment": judgment,
            "evidence_refs": sorted(set(evidence_refs)),
            "numeric_refs": sorted(set(numeric_refs)),
            "repair_outcome_refs": sorted(set(repair_refs)),
            "counter_thesis": counter_thesis,
            "what_would_change": str(cell["what_would_change"]),
            "remaining_gaps": gaps,
        }
        return {"judgment_id": "cell_judgment_" + canonical_digest(payload)[:24], **payload}

    def _workpaper_profile_for(self, evidence: Mapping[str, Any]) -> Mapping[str, Any]:
        roles = tuple(str(slot["evidence_role"]) for slot in evidence["evidence_slots"])
        profile = self._p36_profile.get("workpaper_profile", {})
        profile_roles = tuple(profile.get("required_judgment_roles", ()))
        if profile_roles and set(roles) == set(profile_roles):
            return profile
        base = self._contract["workpaper_fixture"]
        base_roles = tuple(base["required_judgment_roles"])
        if set(roles) != set(base_roles):
            raise IntegrityServiceError("workpaper_profile_not_admitted", 409)
        return {
            "required_judgment_roles": base_roles,
            "judgment_status_by_role": base["judgment_status_by_role"],
        }

    def _numeric_view(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "case_id": row["case_id"],
            "numeric_workspace_id": row["numeric_workspace_id"],
            "numeric_workspace_version": row["numeric_workspace_version"],
            "evidence_workspace_id": row["evidence_workspace_id"],
            "evidence_workspace_version": row["evidence_workspace_version"],
            "status": row["current_status"],
            "facts": list(row["facts"]),
            "counts": {"fact_count": len(row["facts"]), "promoted_for_internal_fixture_count": len(row["facts"])},
            "hard_boundaries": dict(row["hard_boundaries"]),
        }

    def _workpaper_view(self, row: Mapping[str, Any], principal: CasePrincipal) -> dict[str, Any]:
        reviews = self._rows(self._store(), LEAD_REVIEW_TABLE, str(row["case_id"]), principal)
        review = reviews[-1] if reviews else None
        lead_view = None
        if review:
            lead_view = {
                "lead_review_id": review["lead_review_id"],
                "workpaper_version": review["workpaper_version"],
                "content_digest": review["workpaper_content_digest"],
                "decision": review["decision"],
                "reason": review["reason"],
                "actor_ref": review["actor_snapshot_ref"],
                "reviewed_at": review["recorded_at"],
            }
        return {
            "case_id": row["case_id"],
            "workpaper_id": row["workpaper_id"],
            "workpaper_version": row["workpaper_version"],
            "content_digest": row["content_digest"],
            "status": review["decision"] if review else row["current_status"],
            "evidence_workspace_id": row["evidence_workspace_id"],
            "evidence_workspace_version": row["evidence_workspace_version"],
            "numeric_workspace_id": row["numeric_workspace_id"],
            "numeric_workspace_version": row["numeric_workspace_version"],
            "judgments": list(row["judgments"]),
            "lead_review": lead_view,
            "writer_admission": dict(review["writer_admission"]) if review and review.get("writer_admission") else None,
            "hard_boundaries": dict(row["hard_boundaries"]),
        }

    def _repair_candidate(self, row: Mapping[str, Any]) -> dict[str, Any]:
        metadata = dict(row["metadata"])
        display = dict(row["display"])
        return {
            **metadata,
            "display_state": "candidate",
            "title": display["title"],
            "source_name": display["source_name"],
            "source_type": display["source_type"],
            "published_at": display["published_at"],
            "citation": display["citation"],
            "excerpt": display["excerpt"],
            "authority_label": display["authority_label"],
            "source_authority": "official_policy_fixture",
            "applicability_boundary": display["applicability_boundary"],
            "promotion_boundary": "not_in_Point03_VT1",
        }

    @staticmethod
    def _slot(projection: Mapping[str, Any], evidence_slot_id: str) -> Mapping[str, Any]:
        row = next(
            (item for item in projection["evidence_slots"] if item["evidence_slot_id"] == evidence_slot_id),
            None,
        )
        if row is None:
            raise IntegrityServiceError("evidence_slot_not_found", 404)
        return row

    @staticmethod
    def _slot_by_role(projection: Mapping[str, Any], role: str) -> Mapping[str, Any]:
        row = next((item for item in projection["evidence_slots"] if item["evidence_role"] == role), None)
        if row is None:
            raise IntegrityServiceError("evidence_role_not_found", 404)
        return row

    def _single_row(
        self, table: str, case_id: str, principal: CasePrincipal, missing_code: str
    ) -> Mapping[str, Any]:
        return self._single_row_from(self._store(), table, case_id, principal, missing_code)

    def _single_row_from(
        self,
        catalog: Any,
        table: str,
        case_id: str,
        principal: CasePrincipal,
        missing_code: str,
    ) -> Mapping[str, Any]:
        rows = self._rows(catalog, table, case_id, principal)
        if len(rows) > 1:
            raise IntegrityServiceError(f"{missing_code}_cardinality_violation", 409)
        if not rows:
            raise IntegrityServiceError(missing_code, 404, case_id=case_id)
        return rows[0]

    def _repair_rows(
        self, catalog: Any, case_id: str, principal: CasePrincipal, workspace_id: str
    ) -> list[Mapping[str, Any]]:
        return [
            row
            for row in self._rows(catalog, REPAIR_TABLE, case_id, principal)
            if row["workspace_id"] == workspace_id
        ]

    def _rows(
        self, catalog: Any, table: str, case_id: str, principal: CasePrincipal
    ) -> list[Mapping[str, Any]]:
        return [
            row
            for row in catalog.list_versions(table, case_id=case_id)
            if self._matches(row, case_id, principal)
        ]

    @staticmethod
    def _matches(row: Mapping[str, Any], case_id: str, principal: CasePrincipal) -> bool:
        return (
            row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and row.get("case_id") == case_id
        )

    def _require_command(
        self,
        case_id: str,
        actor_ref: str,
        idempotency_key: str,
        principal: CasePrincipal,
        permission: str,
        trace_id: str,
    ) -> None:
        self._require_permission(principal, permission)
        if actor_ref != principal.actor_id:
            raise IntegrityServiceError("actor_scope_mismatch", 403)
        if not case_id.strip() or not idempotency_key.strip() or not trace_id.strip():
            raise IntegrityServiceError("request_validation_error", 422)

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if (
            not principal.tenant_id
            or not principal.project_id
            or not principal.actor_id
            or permission not in principal.permissions
        ):
            raise IntegrityServiceError("permission_denied", 403, required_permission=permission)

    def _store(self) -> Any:
        if self._facade is None:
            raise IntegrityServiceError("operation_not_admitted", 403)
        return self._facade.store

    @staticmethod
    def _scope(case_id: str, key: str, principal: CasePrincipal) -> str:
        return f"vt2:{principal.tenant_id}:{principal.project_id}:{case_id}:{key}"

    @staticmethod
    def _check_idempotency(catalog: Any, scope_key: str, payload_digest: str) -> bool:
        existing = catalog.get_idempotency(scope_key)
        if not existing:
            return False
        if existing["payload_digest"] != payload_digest:
            raise IdempotencyConflict("vt2_idempotency_payload_conflict")
        return True

    @staticmethod
    def _with_digest(model: Any) -> Any:
        payload = model.model_dump(mode="json")
        payload["content_digest"] = ""
        return model.model_copy(update={"content_digest": canonical_digest(payload)})

    @staticmethod
    def _event(
        catalog: Any,
        *,
        event_type: str,
        actor_ref: str,
        trace_id: str,
        work_unit_id: str,
        state_before: int,
        state_after: int,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        now = utc_now()
        return EventEnvelope(
            event_id="event_vt2_" + canonical_digest(
                {"event_type": event_type, "trace_id": trace_id, "payload": payload}
            )[:24],
            event_type=event_type,
            work_unit_id=work_unit_id,
            sequence_no=catalog.next_event_sequence(None),
            occurred_at=now,
            recorded_at=now,
            actor_snapshot_ref=f"fixture_actor:{actor_ref}",
            correlation_id=trace_id,
            state_version_before=state_before,
            state_version_after=state_after,
            payload_digest=canonical_digest(payload),
            payload=payload,
        )

    @staticmethod
    def _service_error(error: Exception) -> IntegrityServiceError:
        if isinstance(error, IntegrityServiceError):
            return error
        if isinstance(error, EvidenceServiceError):
            detail = {key: value for key, value in error.detail.items() if key != "reason"}
            return IntegrityServiceError(error.error_code, error.status_code, **detail)
        if isinstance(error, IdempotencyConflict):
            return IntegrityServiceError("idempotency_conflict", 409)
        if isinstance(error, TransactionConflict):
            return IntegrityServiceError("version_conflict", 409, conflict_reason=str(error))
        if isinstance(error, (KeyError, ValueError, TypeError)):
            return IntegrityServiceError("vt2_fixture_contract_invalid", 409, cause=str(error))
        return IntegrityServiceError("integrity_backend_unavailable", 503, cause=str(error))
