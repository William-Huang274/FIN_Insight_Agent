from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.case_service import CasePrincipal
from ...application.planning_service import (
    CompileDecisionSurfaceDraft,
    PlanningCheckpointDecisionDraft,
    PlanningService,
    PlanningServiceError,
    ReviseDecisionSurfaceDraft,
)
from sec_agent.workbench.api_contracts import request_trace_id


class CompileDecisionSurfaceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_case_version: int = Field(ge=0)
    expected_summary_version: int = Field(ge=0)
    compiler_policy_ref: Literal["fixture:p36-three-cell-v1", "fixture:p36-ten-cell-v1"]
    pack_selection_ref: Literal["fixture:p36-ai-infrastructure-v1", "fixture:p36-ai-infrastructure-v2"]
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class DecisionSurfaceRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str = Field(min_length=1)
    what_would_change: str = Field(min_length=1)
    stop_rule: str | None = Field(default=None, min_length=1)


class ReviseDecisionSurfaceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_case_version: int = Field(ge=0)
    expected_decision_surface_contract_version: int = Field(ge=0)
    expected_checkpoint_version: int = Field(ge=0)
    changes: list[DecisionSurfaceRevision] = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class PlanningCheckpointDecisionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["accept", "return"]
    expected_case_version: int = Field(ge=0)
    expected_decision_surface_contract_version: int = Field(ge=0)
    expected_checkpoint_version: int = Field(ge=0)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class EvidenceSlotView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_slot_id: str
    evidence_role: str
    entity_scope: list[str]
    period_scope: str
    source_policy_ref: str
    required: bool


class DecisionSurfaceCellView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    cell_version: int = Field(ge=1)
    decision_question: str
    owner: str
    materiality: str
    stop_rule: str
    what_would_change: str
    evidence_slots: list[EvidenceSlotView]


class DecisionSurfaceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    contract_id: str
    contract_version: int = Field(ge=1)
    contract_version_id: str
    checkpoint_version: int = Field(ge=1)
    review_status: Literal["awaiting_review", "accepted", "returned"]
    cells: list[DecisionSurfaceCellView]


def build_planning_router(service: PlanningService) -> APIRouter:
    router = APIRouter(tags=["point02-planning"])

    @router.post(
        "/cases/{case_id}/planning/compile",
        operation_id="compileDecisionSurface",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=DecisionSurfaceView,
    )
    def compile_decision_surface(
        case_id: str,
        command: CompileDecisionSurfaceCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.compile_decision_surface(
                case_id,
                CompileDecisionSurfaceDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except PlanningServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _planning_etag(projection)
        return projection

    @router.patch(
        "/cases/{case_id}/decision-surface",
        operation_id="reviseDecisionSurface",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=DecisionSurfaceView,
    )
    def revise_decision_surface(
        case_id: str,
        command: ReviseDecisionSurfaceCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.revise_decision_surface(
                case_id,
                ReviseDecisionSurfaceDraft(
                    expected_case_version=command.expected_case_version,
                    expected_decision_surface_contract_version=command.expected_decision_surface_contract_version,
                    expected_checkpoint_version=command.expected_checkpoint_version,
                    changes=tuple(change.model_dump(exclude_none=True) for change in command.changes),
                    actor_ref=command.actor_ref,
                    idempotency_key=command.idempotency_key,
                ),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except PlanningServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _planning_etag(projection)
        return projection

    @router.post(
        "/cases/{case_id}/planning/checkpoint",
        operation_id="reviewPlanningCheckpoint",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=DecisionSurfaceView,
    )
    def review_planning_checkpoint(
        case_id: str,
        command: PlanningCheckpointDecisionCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.review_planning_checkpoint(
                case_id,
                PlanningCheckpointDecisionDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except PlanningServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _planning_etag(projection)
        return projection

    @router.get(
        "/cases/{case_id}/decision-surface",
        operation_id="getDecisionSurface",
        response_model=DecisionSurfaceView,
    )
    def get_decision_surface(
        case_id: str,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.get_decision_surface(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
            )
        except PlanningServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _planning_etag(projection)
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


def _raise_service_error(error: PlanningServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _planning_etag(projection: dict[str, Any]) -> str:
    return (
        f'"decision-surface={projection["contract_version"]};'
        f'checkpoint={projection["checkpoint_version"]}"'
    )
