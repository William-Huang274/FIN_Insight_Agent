from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from ...application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
    ResearchEvidencePackServiceError,
)


class ResearchEvidencePackListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    projection_mode: Literal["current"]
    status: Literal["reviewed_evidence_catalog_ready"]
    result_digest: str
    items: list[dict[str, Any]]
    evidence_objects_ready: bool
    unavailable_case_keys: list[str]
    next_cursor: None = None
    hard_boundaries: dict[str, Any]
    known_boundary: str
    projection_digest: str


class ResearchEvidencePackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    projection_mode: Literal["current"]
    status: Literal["reviewed_local_evidence_pack_ready_with_declared_gaps"]
    result_digest: str
    case_key: str
    evidence_object_ready: bool
    artifact_digest: str
    pack_payload_digest: str
    summary: dict[str, Any]
    evidence_items: list[dict[str, Any]]
    rejected_items: list[dict[str, Any]]
    residual_gaps: list[dict[str, Any]]
    consumer_contract: dict[str, Any]
    hard_boundaries: dict[str, Any]
    known_boundary: str
    projection_digest: str


def build_research_evidence_pack_router(
    service: ResearchEvidencePackService,
) -> APIRouter:
    router = APIRouter(tags=["current-research-evidence-packs"])

    @router.get(
        "/current-research/evidence-packs",
        operation_id="listCurrentResearchEvidencePacks",
        response_model=ResearchEvidencePackListResponse,
    )
    def list_current_research_evidence_packs(
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.list_cases(_principal(product_mode, permissions))
        except ResearchEvidencePackServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = (
            f'"research-evidence-packs={projection["projection_digest"]}"'
        )
        return projection

    @router.get(
        "/current-research/evidence-packs/{case_key}",
        operation_id="getCurrentResearchEvidencePack",
        response_model=ResearchEvidencePackResponse,
    )
    def get_current_research_evidence_pack(
        case_key: str,
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
                case_key, _principal(product_mode, permissions)
            )
        except ResearchEvidencePackServiceError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = (
            f'"research-evidence-pack={projection["projection_digest"]}"'
        )
        return projection

    return router


def _principal(
    product_mode: str | None, permissions: str | None
) -> ResearchEvidencePackPrincipal:
    return ResearchEvidencePackPrincipal(
        mode=(product_mode or "").strip(),
        permissions=frozenset(
            item.strip()
            for item in (permissions or "").split(",")
            if item.strip()
        ),
    )


def _raise_service_error(error: ResearchEvidencePackServiceError) -> None:
    raise HTTPException(
        status_code=error.status_code, detail=error.detail
    ) from error
