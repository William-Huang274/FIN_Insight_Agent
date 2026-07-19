from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.case_service import CasePrincipal
from ...application.execution_service import (
    CancelWorkUnitDraft,
    CreateWorkUnitDraft,
    ExecutionService,
    ExecutionServiceError,
    VT1_FENCING_TOKEN,
    VT1_WORK_UNIT_TYPE,
)
from sec_agent.workbench.api_contracts import request_trace_id


class CreateWorkUnitCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_unit_type: Literal[VT1_WORK_UNIT_TYPE]
    expected_case_version: int = Field(ge=0)
    input_head_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class CancelWorkUnitCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_work_unit_version: int = Field(ge=0)
    expected_state_version: int = Field(ge=0)
    fencing_token: Literal[VT1_FENCING_TOKEN]
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class WorkUnitExecutionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_unit_id: str
    work_unit_version: int = Field(ge=0)
    state_version: int = Field(ge=0)
    state: str
    input_head_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class WorkUnitExecutionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    work_units: list[WorkUnitExecutionItem]


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    sequence: int = Field(ge=0)
    event_type: str
    occurred_at: datetime
    typed_stop: str | None = None


class ActivityTraceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_version: int = Field(ge=0)
    events: list[ActivityEvent]


def build_execution_router(service: ExecutionService) -> APIRouter:
    router = APIRouter(tags=["point02-execution"])

    @router.get(
        "/cases/{case_id}/work-units",
        operation_id="listWorkUnits",
        response_model=WorkUnitExecutionView,
    )
    def list_work_units(
        case_id: str,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.list_work_units(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
            )
        except ExecutionServiceError as exc:
            _raise_service_error(exc)

    @router.post(
        "/cases/{case_id}/work-units",
        operation_id="createWorkUnit",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=WorkUnitExecutionView,
    )
    def create_work_unit(
        case_id: str,
        command: CreateWorkUnitCommand,
        request: Request,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.create_work_unit(
                case_id,
                CreateWorkUnitDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except ExecutionServiceError as exc:
            _raise_service_error(exc)

    @router.post(
        "/cases/{case_id}/work-units/{work_unit_id}/cancel",
        operation_id="cancelWorkUnit",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=WorkUnitExecutionView,
    )
    def cancel_work_unit(
        case_id: str,
        work_unit_id: str,
        command: CancelWorkUnitCommand,
        request: Request,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.cancel_work_unit(
                case_id,
                work_unit_id,
                CancelWorkUnitDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        except ExecutionServiceError as exc:
            _raise_service_error(exc)

    @router.get(
        "/cases/{case_id}/activity",
        operation_id="getActivityTrace",
        response_model=ActivityTraceView,
    )
    def get_activity(
        case_id: str,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.get_activity(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
            )
        except ExecutionServiceError as exc:
            _raise_service_error(exc)

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


def _raise_service_error(error: ExecutionServiceError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error
