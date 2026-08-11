from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.case_service import CasePrincipal, CaseService, CaseServiceError, CreateCaseDraft
from sec_agent.workbench.api_contracts import request_trace_id


class CreateCaseDraftCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    as_of: datetime
    language: str = Field(min_length=1)
    source_policy_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class TaskCenterRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int = Field(ge=0)
    query: str
    status: str
    updated_at: datetime


class TaskCenterProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskCenterRow]
    next_cursor: str | None = None


class CaseWorkspaceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int = Field(ge=0)
    summary_version: int = Field(ge=0)
    query: str
    as_of: datetime
    language: str
    planning_checkpoint_state: str


def build_cases_router(service: CaseService) -> APIRouter:
    router = APIRouter(tags=["point02-cases"])

    @router.post("/cases", status_code=status.HTTP_202_ACCEPTED, response_model=CaseWorkspaceProjection)
    def create_case(
        command: CreateCaseDraftCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.create_case(
                CreateCaseDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except CaseServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _case_etag(projection["case_version"])
        return projection

    @router.get("/cases", response_model=TaskCenterProjection)
    def list_cases(
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.list_cases(_principal(tenant_id, project_id, actor_id, permissions))
        except CaseServiceError as exc:
            _raise_service_error(exc)

    @router.get("/cases/{case_id}", response_model=CaseWorkspaceProjection)
    def get_case(
        case_id: str,
        response: Response,
        expected_case_version: Annotated[int | None, Header(alias="X-Fin-Case-Expected-Version")] = None,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.get_case(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
                expected_case_version=expected_case_version,
            )
        except CaseServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = _case_etag(projection["case_version"])
        return projection

    return router


def _principal(tenant_id: str | None, project_id: str | None, actor_id: str | None, permissions: str | None) -> CasePrincipal:
    return CasePrincipal(
        tenant_id=(tenant_id or "").strip(),
        project_id=(project_id or "").strip(),
        actor_id=(actor_id or "").strip(),
        permissions=frozenset(item.strip() for item in (permissions or "").split(",") if item.strip()),
    )


def _raise_service_error(error: CaseServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _case_etag(version: int) -> str:
    return f'"case-version={version}"'
