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
    ranking_comparison: dict[str, Any] | None
    lanes: list[dict[str, Any]]
    known_boundary: str
    projection_digest: str


class EvidenceRequestPeriodBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: str | None
    end_date: str | None
    fiscal_years: list[int]


class EvidenceRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    request_id: str
    cell_id: str
    requester_role: str
    evidence_domain: str
    case_key: str
    subject_ticker: str
    research_as_of: str
    target_entities: list[str]
    requested_facet_ids: list[str]
    metric_intents: list[str]
    product_intents: list[str]
    period: EvidenceRequestPeriodBody
    granularity: str
    unit: str
    acceptable_sources: list[str]
    acceptable_proxy: bool
    forbidden_proxy: list[str]
    stop_condition: str
    clarification_policy: str


class EvidenceRequestExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["request_scoped_typed_local_retrieval_ready"]
    product_mode: Literal["current"]
    case_key: str
    candidate_state: Literal["candidate_not_evidence"]
    execution_mode: Literal["immutable_current_snapshot_filtering"]
    request: dict[str, Any]
    request_digest: str
    query_plan: dict[str, Any]
    source_snapshot: dict[str, Any]
    summary: dict[str, Any]
    typed_gaps: list[dict[str, Any]]
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

    @router.post(
        "/research-cases/{case_key}/retrieval-requests",
        operation_id="executeEvidenceRequest",
        response_model=EvidenceRequestExecutionResponse,
    )
    def execute_evidence_request(
        case_key: str,
        request: EvidenceRequestBody,
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.execute_request(
                case_key,
                request.model_dump(mode="json"),
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
            f'"evidence-request={projection["projection_digest"]}"'
        )
        return projection

    return router


__all__ = [
    "EvidenceRequestBody",
    "EvidenceRequestExecutionResponse",
    "EvidenceRequestPeriodBody",
    "build_research_retrieval_router",
]
