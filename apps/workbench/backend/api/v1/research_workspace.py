from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from ...application.research_workspace_service import (
    ResearchWorkspacePrincipal,
    ResearchWorkspaceService,
    ResearchWorkspaceServiceError,
)


class ResearchWorkspaceCaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["identity_bound_research_case_catalog_ready"]
    product_mode: Literal["current"]
    primary_route: Literal["/workspace"]
    evidence_pack_result_digest: str
    items: list[dict[str, Any]]
    evidence_objects_ready: bool
    unavailable_case_keys: list[str]
    next_cursor: None = None
    surface_policy: dict[str, Any]
    known_boundary: str
    projection_digest: str


class ResearchWorkspaceCaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["identity_bound_research_case_ready"]
    product_mode: Literal["current"]
    case_id: str
    case_version: int
    case_key: str
    subject: dict[str, Any]
    subject_digest: str
    research_as_of: str
    language: str
    pack_binding: dict[str, Any]
    evidence_summary: dict[str, Any]
    available_surfaces: list[str]
    evidence_object_ready: bool
    research_context: dict[str, Any]
    evidence_pack_uri: str
    surface_policy: dict[str, Any]
    known_boundary: str
    projection_digest: str


class ResearchWorkspaceEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["identity_bound_reviewed_evidence_ready"]
    product_mode: Literal["current"]
    case_id: str
    case_version: int
    case_key: str
    subject: dict[str, Any]
    subject_digest: str
    research_context: dict[str, Any]
    pack_binding: dict[str, Any]
    evidence_items: list[dict[str, Any]]
    rejected_items: list[dict[str, Any]]
    residual_gaps: list[dict[str, Any]]
    consumer_contract: dict[str, Any]
    hard_boundaries: dict[str, Any]
    known_boundary: str
    projection_digest: str


def build_research_workspace_router(
    service: ResearchWorkspaceService,
) -> APIRouter:
    router = APIRouter(tags=["research-workspace"])

    @router.get(
        "/research-cases",
        operation_id="listResearchWorkspaceCases",
        response_model=ResearchWorkspaceCaseListResponse,
    )
    def list_research_cases(
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.list_cases(
                _principal(product_mode, permissions)
            )
        except ResearchWorkspaceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = (
            f'"research-workspace={projection["projection_digest"]}"'
        )
        return projection

    @router.get(
        "/research-cases/{case_id}",
        operation_id="getResearchWorkspaceCase",
        response_model=ResearchWorkspaceCaseResponse,
    )
    def get_research_case(
        case_id: str,
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.get_case(
                case_id, _principal(product_mode, permissions)
            )
        except ResearchWorkspaceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = (
            f'"research-case={projection["projection_digest"]}"'
        )
        return projection

    @router.get(
        "/research-cases/{case_id}/evidence",
        operation_id="getResearchWorkspaceEvidence",
        response_model=ResearchWorkspaceEvidenceResponse,
    )
    def get_research_case_evidence(
        case_id: str,
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.get_evidence(
                case_id, _principal(product_mode, permissions)
            )
        except ResearchWorkspaceServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = (
            f'"research-evidence={projection["projection_digest"]}"'
        )
        return projection

    return router


def _principal(
    product_mode: str | None, permissions: str | None
) -> ResearchWorkspacePrincipal:
    return ResearchWorkspacePrincipal(
        mode=(product_mode or "").strip(),
        permissions=frozenset(
            item.strip()
            for item in (permissions or "").split(",")
            if item.strip()
        ),
    )


def _raise_service_error(error: ResearchWorkspaceServiceError) -> None:
    raise HTTPException(
        status_code=error.status_code, detail=error.detail
    ) from error


__all__ = ["build_research_workspace_router"]
