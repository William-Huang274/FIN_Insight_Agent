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
    canonical_spine: dict[str, Any] | None = None
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
    execution_plan: dict[str, Any] | None
    source_snapshot: dict[str, Any]
    summary: dict[str, Any]
    typed_gaps: list[dict[str, Any]]
    typed_fact_results: list[dict[str, Any]]
    lanes: list[dict[str, Any]]
    known_boundary: str
    projection_digest: str


class ResearchObjectivePeriodBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: str | None
    fiscal_years: list[int]


class ResearchObjectiveBudgetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_evidence_requests: int
    max_metric_intents_per_request: int
    max_product_intents_per_request: int
    max_model_calls: int


class ResearchObjectiveDraftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    raw_question: str
    task_type: str
    case_key: str
    required_slot_ids: list[str]
    allowed_source_types: list[str]
    forbidden_source_types: list[str]
    output_format: str
    gap_policy: str
    reviewer_role: str
    period: ResearchObjectivePeriodBody
    budget: ResearchObjectiveBudgetBody
    pass_criteria: list[str]


class PlannerAtomBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facet_id: str
    target_entity: str
    metric_ids: list[str]
    product_intents: list[str]


class ResearchPlannerAtomsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    objective_id: str
    atoms: list[PlannerAtomBody]


class MaterialProductIntentDispositionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_intent_index: int
    disposition: Literal[
        "hard_material_axis",
        "contextual_retrieval_only",
        "temporal_directive",
    ]


class MaterialRequirementAtomBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facet_id: str
    role: Literal["direct", "bridge", "context", "counter"]
    metric_intent_indices: list[int]
    product_intent_indices: list[int]
    period_mode: Literal["any", "all_periods_same_basis"]
    coverage_mode: Literal["single_binding", "collective_axes"]


class MaterialRequestScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    product_intent_dispositions: list[MaterialProductIntentDispositionBody]
    requirement_atoms: list[MaterialRequirementAtomBody]


class ResearchMaterialScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    research_plan_digest: str
    request_scopes: list[MaterialRequestScopeBody]


class ControlledResearchPlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: ResearchObjectiveDraftBody
    planner: ResearchPlannerAtomsBody
    material_scope: ResearchMaterialScopeBody | None = None


class ControlledResearchPlanExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    status: Literal["controlled_research_plan_zero_call_executed"]
    product_mode: Literal["current"]
    case_key: str
    objective: dict[str, Any]
    compiled_plan: dict[str, Any]
    summary: dict[str, Any]
    material_scope: dict[str, Any] | None
    request_results: list[dict[str, Any]]
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

    @router.post(
        "/research-cases/{case_key}/controlled-research-plans",
        operation_id="executeControlledResearchPlan",
        response_model=ControlledResearchPlanExecutionResponse,
    )
    def execute_controlled_research_plan(
        case_key: str,
        request: ControlledResearchPlanBody,
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        try:
            projection = service.execute_controlled_plan(
                case_key,
                request.objective.model_dump(mode="json"),
                request.planner.model_dump(mode="json"),
                ResearchRetrievalPrincipal(
                    mode=(product_mode or "").strip(),
                    permissions=frozenset(
                        item.strip()
                        for item in (permissions or "").split(",")
                        if item.strip()
                    ),
                ),
                material_scope_payload=(
                    request.material_scope.model_dump(mode="json")
                    if request.material_scope is not None
                    else None
                ),
            )
        except ResearchRetrievalServiceError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.detail
            ) from exc
        response.headers["ETag"] = (
            f'"controlled-research-plan={projection["projection_digest"]}"'
        )
        return projection

    return router


__all__ = [
    "ControlledResearchPlanBody",
    "ControlledResearchPlanExecutionResponse",
    "EvidenceRequestBody",
    "EvidenceRequestExecutionResponse",
    "EvidenceRequestPeriodBody",
    "PlannerAtomBody",
    "MaterialProductIntentDispositionBody",
    "MaterialRequirementAtomBody",
    "MaterialRequestScopeBody",
    "ResearchMaterialScopeBody",
    "ResearchObjectiveBudgetBody",
    "ResearchObjectiveDraftBody",
    "ResearchObjectivePeriodBody",
    "ResearchPlannerAtomsBody",
    "build_research_retrieval_router",
]
