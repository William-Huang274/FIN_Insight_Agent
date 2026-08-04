from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from ...application.case_service import CasePrincipal
from ...application.local_research_service import (
    LocalResearchServiceError,
    P36LocalResearchService,
)


class LocalResearchCandidateView(BaseModel):
    model_config = ConfigDict(extra="allow")

    candidate_id: str
    retrieval_lane: Literal["object_bm25", "gold_fact_sql", "research_graph"]
    rank: int
    score: float | None
    ticker: str
    title: str
    excerpt: str
    source_name: str
    source_type: str
    published_at: str
    citation_url: str
    citation_span: str
    evidence_ref: str
    authority_mode: str
    claim_boundary: str
    exact_value_authority: bool
    numeric_eligible: bool
    writer_citable: Literal[False]
    promotion_status: Literal["candidate_not_promoted"]


class LocalResearchCellView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_key: str
    evidence_role: str
    decision_question: str
    retrieval_lane: Literal["object_bm25", "gold_fact_sql", "research_graph"]
    status: Literal["candidate_ready", "typed_gap"]
    typed_gap: str | None
    candidates: list[LocalResearchCandidateView]


class LocalResearchSourceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    schema_version: str
    record_count: int
    snapshot_digest: str


class LocalResearchPreviewView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_digest: str
    case_id: str
    case_version: int
    query: str
    as_of: str
    research_mode: Literal["bounded_local_read_only"]
    status: Literal["candidate_preview_ready"]
    selected_cell_count: int
    candidate_count: int
    cells: list[LocalResearchCellView]
    source_inventory: list[LocalResearchSourceView]
    execution_counts: dict[str, int]
    boundary: str


class LocalAnalysisPreviewView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_digest: str
    case_id: str
    case_version: int
    as_of: str
    source_preview_digest: str
    analysis_mode: Literal["bounded_local_deterministic_preview"]
    status: Literal["internal_analysis_preview_ready"]
    numeric: dict[str, Any]
    repairs: list[dict[str, Any]]
    judgments: list[dict[str, Any]]
    workpaper: dict[str, Any]
    writer: dict[str, Any]
    execution_counts: dict[str, int]
    hard_boundaries: dict[str, int]
    boundary: str


def build_local_research_router(service: P36LocalResearchService) -> APIRouter:
    router = APIRouter(tags=["p36-local-research"])

    @router.get(
        "/cases/{case_id}/local-research-preview",
        operation_id="getP36LocalResearchPreview",
        response_model=LocalResearchPreviewView,
    )
    def get_local_research_preview(
        case_id: str,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.preview(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
            )
        except LocalResearchServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @router.get(
        "/cases/{case_id}/local-analysis-preview",
        operation_id="getP36LocalAnalysisPreview",
        response_model=LocalAnalysisPreviewView,
    )
    def get_local_analysis_preview(
        case_id: str,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        try:
            return service.analysis_preview(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
            )
        except LocalResearchServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

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
