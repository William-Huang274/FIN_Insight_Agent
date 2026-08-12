from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from ...application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
    ResearchRetrievalServiceError,
)


class ResearchRetrievalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["typed_local_retrieval_snapshot_ready"]
    product_mode: Literal["current"]
    case_key: str
    candidate_state: Literal["candidate_not_evidence"]
    query_plan_digest: str
    result_digest: str
    source_snapshot: dict[str, Any]
    summary: dict[str, Any]
    source_gap_summary: dict[str, Any]
    business_findings_zh: list[str]
    lanes: list[dict[str, Any]]
    known_boundary: str
    projection_digest: str


def build_research_retrieval_router(
    service: ResearchRetrievalService,
) -> APIRouter:
    router = APIRouter(tags=["research-retrieval"])

    @router.get(
        "/research-cases/{case_key}/retrieval",
        operation_id="getResearchRetrievalSnapshot",
        response_model=ResearchRetrievalResponse,
    )
    def get_research_retrieval(
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
                case_key,
                ResearchRetrievalPrincipal(
                    mode=(product_mode or "").strip(),
                    permissions=frozenset(
                        item.strip()
                        for item in (permissions or "").split(",")
                        if item.strip()
                    ),
                ),
            )
        except ResearchRetrievalServiceError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.detail
            ) from exc
        response.headers["ETag"] = (
            f'"research-retrieval={projection["projection_digest"]}"'
        )
        return projection

    return router


__all__ = ["build_research_retrieval_router"]
