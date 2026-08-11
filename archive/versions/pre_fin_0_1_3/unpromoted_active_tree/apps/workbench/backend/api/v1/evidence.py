from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench.api_contracts import request_trace_id

from ...application.case_service import CasePrincipal
from ...application.evidence_service import (
    CompileEvidenceFixtureDraft,
    EvidenceReviewDraft,
    EvidenceService,
    EvidenceServiceError,
)


class CompileEvidenceFixtureCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_workspace_version: int = Field(ge=0)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class EvidenceReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_workspace_version: int = Field(ge=1)
    reason: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class EvidenceCandidateView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    display_state: Literal["candidate", "context_only", "rejected"]
    candidate_kind: str
    title: str
    source_name: str
    source_type: str
    published_at: str
    citation: str
    excerpt: str
    authority_label: str
    source_authority: str
    source_role: str
    source_authority_rank: int
    source_policy_ref: str
    route_id: str
    document_id: str
    document_version: str
    entity_ref: str
    period_ref: str
    section_or_table_ref: str
    content_ref: str
    applicability_boundary: str
    promotion_boundary: Literal["not_in_Point03_VT1"]
    review_reason: str | None = None


class EvidenceSlotWorkbenchView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_slot_id: str
    evidence_role: str
    cell_id: str
    decision_question: str
    owner: str
    required: bool
    display_state: Literal["candidate", "typed_gap", "repair_requested"]
    request_id: str
    request_digest: str
    tool_plan_id: str
    tool_plan_status: str
    bundle_id: str
    bundle_status: str
    exhaustion_status: str
    typed_gap_codes: list[str]
    candidates: list[EvidenceCandidateView]


class EvidenceCountsView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_count: int
    total_candidate_count: int
    candidate_count: int
    context_only_count: int
    rejected_count: int
    typed_gap_count: int
    repair_requested_count: int
    repair_completed_count: int
    review_action_count: int


class EvidenceReviewActionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_action_id: str
    action_type: Literal["reject_candidate", "request_repair"]
    evidence_slot_id: str
    candidate_id: str | None
    reason: str
    actor_ref: str
    recorded_at: str
    workspace_version_after: int


class EvidenceRepairOutcomeView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repair_outcome_id: str
    evidence_slot_id: str
    request_review_action_id: str
    attempt_no: int
    attempt_state: str
    route_id: str
    candidate_id: str
    completed_at: str
    external_call_count: int
    tool_invocation_count: int
    boundary: str


class EvidenceWorkbenchView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    workspace_id: str
    workspace_version: int
    projection_version_id: str
    status: str
    fixture_mode: Literal["fixture_shadow_internal_only"]
    decision_surface_contract_version_id: str
    planning_checkpoint_version_id: str
    work_unit_id: str
    counts: EvidenceCountsView
    slots: list[EvidenceSlotWorkbenchView]
    review_actions: list[EvidenceReviewActionView]
    repair_outcomes: list[EvidenceRepairOutcomeView]
    available_actions: list[Literal["reject_candidate", "request_repair", "execute_repair"]]
    hard_boundaries: dict[str, int | str]


def build_evidence_router(service: EvidenceService) -> APIRouter:
    router = APIRouter(tags=["point03-evidence"])

    @router.get(
        "/cases/{case_id}/evidence",
        operation_id="getEvidenceWorkbench",
        response_model=EvidenceWorkbenchView,
    )
    def get_evidence(
        case_id: str,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.get_workbench(
                case_id, _principal(tenant_id, project_id, actor_id, permissions)
            )
        except EvidenceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _etag(projection)
        return projection

    @router.post(
        "/cases/{case_id}/evidence/compile",
        operation_id="compileEvidenceFixture",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=EvidenceWorkbenchView,
    )
    def compile_evidence(
        case_id: str,
        command: CompileEvidenceFixtureCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.compile_fixture(
                case_id,
                CompileEvidenceFixtureDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except EvidenceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _etag(projection)
        return projection

    @router.post(
        "/cases/{case_id}/evidence/candidates/{candidate_id}/reject",
        operation_id="rejectEvidenceCandidate",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=EvidenceWorkbenchView,
    )
    def reject_candidate(
        case_id: str,
        candidate_id: str,
        command: EvidenceReviewCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.reject_candidate(
                case_id,
                candidate_id,
                EvidenceReviewDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except EvidenceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _etag(projection)
        return projection

    @router.post(
        "/cases/{case_id}/evidence/slots/{evidence_slot_id}/request-repair",
        operation_id="requestEvidenceRepair",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=EvidenceWorkbenchView,
    )
    def request_repair(
        case_id: str,
        evidence_slot_id: str,
        command: EvidenceReviewCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.request_repair(
                case_id,
                evidence_slot_id,
                EvidenceReviewDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except EvidenceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _etag(projection)
        return projection

    return router


def _principal(
    tenant_id: str | None,
    project_id: str | None,
    actor_id: str | None,
    permissions: str | None,
) -> CasePrincipal:
    return CasePrincipal(
        tenant_id=(tenant_id or "").strip(),
        project_id=(project_id or "").strip(),
        actor_id=(actor_id or "").strip(),
        permissions=frozenset(item.strip() for item in (permissions or "").split(",") if item.strip()),
    )


def _raise_service_error(error: EvidenceServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _etag(projection: dict[str, Any]) -> str:
    return f'"evidence-workspace={projection["workspace_version"]}"'
