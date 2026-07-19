from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench.api_contracts import request_trace_id

from ...application.case_service import CasePrincipal
from ...application.integrity_service import (
    CompileNumericDraft,
    CompileWorkpaperDraft,
    ExecuteRepairDraft,
    IntegrityService,
    IntegrityServiceError,
    LeadReviewDraft,
)
from .evidence import EvidenceWorkbenchView


class ExecuteRepairCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_workspace_version: int = Field(ge=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class CompileNumericCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_evidence_workspace_version: int = Field(ge=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class CompileWorkpaperCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_numeric_workspace_version: int = Field(ge=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class LeadReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_workpaper_version: int = Field(ge=1)
    expected_content_digest: str = Field(min_length=1)
    decision: Literal["admit_fixture_writer_preview", "return_for_repair"]
    reason: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class NumericFactView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    evidence_slot_id: str
    candidate_id: str
    parser_candidate_id: str
    normalized_fact_id: str
    numeric_trace_id: str
    promotion_decision_id: str
    entity_ref: str
    row_label: str
    normalized_value: str
    unit: str
    scale_multiplier: int | float
    period: str
    source_coordinate: str
    metric_definition_ref: str
    program_steps: list[str]
    output_value: str
    promotion_status: str
    promotion_scope: str
    writer_citable: bool
    boundary: str


class NumericWorkbenchView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    numeric_workspace_id: str
    numeric_workspace_version: int
    evidence_workspace_id: str
    evidence_workspace_version: int
    status: str
    facts: list[NumericFactView]
    counts: dict[str, int]
    hard_boundaries: dict[str, int | str]


class WorkpaperJudgmentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgment_id: str
    cell_id: str
    evidence_role: str
    decision_question: str
    owner_role: str
    judgment_status: str
    confidence: str
    judgment: str
    evidence_refs: list[str]
    numeric_refs: list[str]
    repair_outcome_refs: list[str]
    counter_thesis: str
    what_would_change: str
    remaining_gaps: list[str]


class LeadReviewView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_review_id: str
    workpaper_version: int
    content_digest: str
    decision: Literal["admit_fixture_writer_preview", "return_for_repair"]
    reason: str
    actor_ref: str
    reviewed_at: str


class WriterAdmissionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    writer_admission_id: str
    status: str
    scope: str
    fixture_only: bool
    writer_execution_authorized: bool
    boundary: str
    admitted_at: str


class WorkpaperView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    workpaper_id: str
    workpaper_version: int
    content_digest: str
    status: str
    evidence_workspace_id: str
    evidence_workspace_version: int
    numeric_workspace_id: str
    numeric_workspace_version: int
    judgments: list[WorkpaperJudgmentView]
    lead_review: LeadReviewView | None
    writer_admission: WriterAdmissionView | None
    hard_boundaries: dict[str, int | str]


def build_integrity_router(service: IntegrityService) -> APIRouter:
    router = APIRouter(tags=["vt2-integrity-workpaper"])

    @router.post(
        "/cases/{case_id}/evidence/slots/{evidence_slot_id}/execute-repair",
        operation_id="executeEvidenceRepairFixture",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=EvidenceWorkbenchView,
    )
    def execute_repair(
        case_id: str,
        evidence_slot_id: str,
        command: ExecuteRepairCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.execute_repair(
                case_id,
                evidence_slot_id,
                ExecuteRepairDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        )
        response.headers["ETag"] = f'"evidence-workspace={projection["workspace_version"]}"'
        return projection

    @router.get(
        "/cases/{case_id}/integrity/numeric",
        operation_id="getNumericWorkbench",
        response_model=NumericWorkbenchView,
    )
    def get_numeric(
        case_id: str,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.get_numeric(
                case_id, _principal(tenant_id, project_id, actor_id, permissions)
            )
        )
        response.headers["ETag"] = f'"numeric-workspace={projection["numeric_workspace_version"]}"'
        return projection

    @router.post(
        "/cases/{case_id}/integrity/numeric/compile",
        operation_id="compileNumericFixture",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=NumericWorkbenchView,
    )
    def compile_numeric(
        case_id: str,
        command: CompileNumericCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.compile_numeric(
                case_id,
                CompileNumericDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        )
        response.headers["ETag"] = f'"numeric-workspace={projection["numeric_workspace_version"]}"'
        return projection

    @router.get(
        "/cases/{case_id}/workpaper",
        operation_id="getWorkpaper",
        response_model=WorkpaperView,
    )
    def get_workpaper(
        case_id: str,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.get_workpaper(
                case_id, _principal(tenant_id, project_id, actor_id, permissions)
            )
        )
        response.headers["ETag"] = f'"workpaper={projection["workpaper_version"]}:{projection["content_digest"]}"'
        return projection

    @router.post(
        "/cases/{case_id}/workpaper/compile",
        operation_id="compileWorkpaperFixture",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=WorkpaperView,
    )
    def compile_workpaper(
        case_id: str,
        command: CompileWorkpaperCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.compile_workpaper(
                case_id,
                CompileWorkpaperDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        )
        response.headers["ETag"] = f'"workpaper={projection["workpaper_version"]}:{projection["content_digest"]}"'
        return projection

    @router.post(
        "/cases/{case_id}/workpaper/lead-review",
        operation_id="completeLeadReviewFixture",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=WorkpaperView,
    )
    def complete_lead_review(
        case_id: str,
        command: LeadReviewCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.complete_lead_review(
                case_id,
                LeadReviewDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        )
        response.headers["ETag"] = f'"workpaper={projection["workpaper_version"]}:{projection["content_digest"]}"'
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
        permissions=frozenset(
            item.strip() for item in (permissions or "").split(",") if item.strip()
        ),
    )


def _call(operation: Any) -> dict[str, Any]:
    try:
        return operation()
    except IntegrityServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
