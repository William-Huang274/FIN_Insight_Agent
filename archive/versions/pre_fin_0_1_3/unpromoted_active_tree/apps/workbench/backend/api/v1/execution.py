from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.case_service import CasePrincipal
from ...application.execution_service import (
    AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
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

    work_unit_type: Literal[
        VT1_WORK_UNIT_TYPE,
        AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
        BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
    ]
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


class ResearchRunEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    sequence: int = Field(ge=0)
    event_type: str
    occurred_at: datetime
    causation_event_id: str | None = None
    details: dict[str, Any]
    redacted_fields: list[str]
    private_chain_of_thought_included: Literal[False] = False


class ResearchRunArtifactView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_version_id: str
    artifact_type: str
    producer_attempt_id: str
    current_status: str
    object_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_refs: list[str]
    payload: dict[str, Any]
    payload_exact: bool
    redacted_fields: list[str]


class ResearchRunProjectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_run_id: str
    research_run_version_id: str
    work_unit_id: str
    work_unit_type: str
    attempt_id: str
    execution_profile_version_ref: str
    state: str
    started_at: datetime
    ended_at: datetime | None = None
    terminal_reason: str | None = None
    output_refs: list[str]
    events: list[ResearchRunEventView]
    artifacts: list[ResearchRunArtifactView]


class ResearchRunProjectionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    runs: list[ResearchRunProjectionItem]
    private_chain_of_thought_included: Literal[False] = False


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
        background_tasks: BackgroundTasks,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            principal = _principal(tenant_id, project_id, actor_id, permissions)
            trace_id = request_trace_id(request)
            view = service.create_work_unit(
                case_id,
                CreateWorkUnitDraft(**command.model_dump()),
                principal,
                trace_id=trace_id,
            )
            work_unit_id = service.pending_work_unit_id_for_type(
                case_id,
                command.work_unit_type,
                principal,
                idempotency_key=command.idempotency_key,
            )
            if service.background_dispatch_enabled and work_unit_id:
                background_tasks.add_task(
                    service.dispatch_queued_work_unit,
                    case_id,
                    work_unit_id,
                    principal,
                    trace_id=trace_id,
                )
            return view
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

    @router.get(
        "/cases/{case_id}/execution-projection",
        operation_id="getResearchRunProjection",
        response_model=ResearchRunProjectionView,
    )
    def get_research_run_projection(
        case_id: str,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.get_research_run_projection(
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
