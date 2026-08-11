from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from sec_agent.workbench.api_contracts import request_trace_id

from ...application.case_service import CasePrincipal
from ...application.deliverable_service import (
    CompileDeliverablePreviewDraft,
    DeliverableService,
    DeliverableServiceError,
    ReviewDeliverableDraft,
)


class CompileDeliverablePreviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_workpaper_version: int = Field(ge=1)
    expected_workpaper_content_digest: str = Field(min_length=1)
    writer_admission_id: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class ReviewDeliverableCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_artifact_version: int = Field(ge=1)
    expected_content_digest: str = Field(min_length=1)
    expected_canonical_presentation_digest: str = Field(min_length=1)
    action_type: Literal["comment", "return_for_repair", "accept_fixture_preview"]
    reason: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class RenderingView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    content_digest: str
    canonical_presentation_digest: str


class MaterialClaimView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    cell_id: str
    claim_text: str
    claim_kind: str
    evidence_refs: list[str]
    numeric_refs: list[str]
    repair_outcome_refs: list[str]
    gap_refs: list[str]


class DeliverableReviewActionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_action_id: str
    review_action_version_id: str
    action_type: Literal["comment", "return_for_repair", "accept_fixture_preview"]
    reason: str
    terminal: bool
    actor_ref: str
    reviewed_at: str
    artifact_version_id: str
    artifact_version: int
    content_digest: str
    canonical_presentation_digest: str


class DeliverablePreviewView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    deliverable_id: str
    artifact_version_id: str
    artifact_version: int
    content_digest: str
    canonical_presentation_digest: str
    status: str
    title: str
    sections: list[dict[str, Any]]
    material_claims: list[MaterialClaimView]
    renderings: dict[str, RenderingView]
    review_actions: list[DeliverableReviewActionView]
    hard_boundaries: dict[str, int | str]


class DeliverableTraceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    manifest_id: str
    artifact_version_id: str
    artifact_version: int
    artifact_content_digest: str
    canonical_presentation_digest: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]
    claim_to_source: dict[str, list[str]]
    source_to_claim: dict[str, list[str]]
    redaction_summary: dict[str, int | str]


def build_deliverables_router(service: DeliverableService) -> APIRouter:
    router = APIRouter(tags=["vt3-deliverable-review-trace"])

    @router.get(
        "/cases/{case_id}/deliverables",
        operation_id="getDeliverableHead",
        response_model=DeliverablePreviewView,
    )
    def get_deliverable_head(
        case_id: str,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.get_latest(
                case_id, _principal(tenant_id, project_id, actor_id, permissions)
            )
        )
        _set_deliverable_etag(response, projection)
        return projection

    @router.post(
        "/cases/{case_id}/deliverables",
        operation_id="compileDeliverablePreviewFixture",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=DeliverablePreviewView,
    )
    def compile_deliverable_preview(
        case_id: str,
        command: CompileDeliverablePreviewCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.compile_preview(
                case_id,
                CompileDeliverablePreviewDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        )
        _set_deliverable_etag(response, projection)
        return projection

    @router.post(
        "/artifacts/{deliverable_id}/versions/{artifact_version}/review-actions",
        operation_id="createDeliverableReviewAction",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=DeliverablePreviewView,
    )
    def create_deliverable_review_action(
        deliverable_id: str,
        artifact_version: int,
        command: ReviewDeliverableCommand,
        request: Request,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        projection = _call(
            lambda: service.review_version(
                deliverable_id,
                artifact_version,
                ReviewDeliverableDraft(**command.model_dump()),
                _principal(tenant_id, project_id, actor_id, permissions),
                trace_id=request_trace_id(request),
            )
        )
        _set_deliverable_etag(response, projection)
        return projection

    @router.get(
        "/cases/{case_id}/trace",
        operation_id="getCaseTrace",
        response_model=DeliverableTraceView,
    )
    def get_case_trace(
        case_id: str,
        response: Response,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> dict[str, Any]:
        trace = _call(
            lambda: service.get_trace(
                case_id,
                _principal(tenant_id, project_id, actor_id, permissions),
            )
        )
        response.headers["ETag"] = (
            f'"trace={trace["artifact_version"]}:{trace["artifact_content_digest"]}:'
            f'{trace["canonical_presentation_digest"]}"'
        )
        return trace

    return router


def _set_deliverable_etag(response: Response, projection: dict[str, Any]) -> None:
    response.headers["ETag"] = (
        f'"deliverable={projection["artifact_version"]}:{projection["content_digest"]}:'
        f'{projection["canonical_presentation_digest"]}"'
    )


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
    except DeliverableServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
