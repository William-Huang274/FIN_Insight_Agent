from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.case_service import CasePrincipal
from ...application.human_baseline_service import (
    AnalystBaselineSubmission,
    HumanBaselineService,
    HumanBaselineServiceError,
    SeniorReviewSubmission,
)


class StartHumanBaselineCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class SubmitAnalystBaselineCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strongest_source: str = Field(min_length=1)
    material_limitation: str = Field(min_length=1)
    numeric_verification: str = Field(min_length=1)
    weakest_judgment: str = Field(min_length=1)
    required_modification: str = Field(min_length=1)
    writer_usefulness_score: int = Field(ge=1, le=5)
    writer_usefulness_reason: str = Field(min_length=1)
    time_to_find_source_seconds: int = Field(ge=0)
    time_to_verify_numeric_seconds: int = Field(ge=0)
    time_to_identify_weakest_judgment_seconds: int = Field(ge=0)
    time_to_review_writer_seconds: int = Field(ge=0)
    repeated_work_count: int = Field(ge=0)
    blocking_ui_issue: str = ""
    idempotency_key: str = Field(min_length=1)


class SubmitSeniorReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_ref: str = Field(min_length=1)
    reviewer_role: Literal["senior_analyst", "domain_reviewer"]
    decision: Literal["approve", "conditional_approve", "return_for_follow_up"]
    research_quality_score: int = Field(ge=1, le=5)
    evidence_quality_score: int = Field(ge=1, le=5)
    senior_reviewability_score: int = Field(ge=1, le=5)
    numeric_reproducibility_confirmed: bool
    gap_boundaries_preserved: bool
    exact_digest_confirmed: bool
    review_comment: str = Field(min_length=1)
    bounded_follow_up: list[str] = Field(default_factory=list, max_length=3)
    idempotency_key: str = Field(min_length=1)


def build_human_baseline_router(service: HumanBaselineService) -> APIRouter:
    router = APIRouter(tags=["fin-0.1-human-baseline"])

    @router.get("/cases/{case_id}/human-baseline/sessions")
    def list_sessions(
        case_id: str,
        principal: Annotated[PrincipalHeaders, Depends()],
    ) -> dict[str, Any]:
        return _invoke(lambda: service.list_sessions(case_id, principal.value()))

    @router.post(
        "/cases/{case_id}/human-baseline/sessions",
        status_code=status.HTTP_201_CREATED,
    )
    def start_session(
        case_id: str,
        command: StartHumanBaselineCommand,
        principal: Annotated[PrincipalHeaders, Depends()],
    ) -> dict[str, Any]:
        return _invoke(
            lambda: service.start_session(
                case_id,
                principal.value(),
                participant_ref=command.participant_ref,
                idempotency_key=command.idempotency_key,
            )
        )

    @router.get("/cases/{case_id}/human-baseline/sessions/{session_id}")
    def get_session(
        case_id: str,
        session_id: str,
        principal: Annotated[PrincipalHeaders, Depends()],
    ) -> dict[str, Any]:
        return _invoke(lambda: service.get_session(case_id, session_id, principal.value()))

    @router.post("/cases/{case_id}/human-baseline/sessions/{session_id}/analyst-submission")
    def submit_analyst(
        case_id: str,
        session_id: str,
        command: SubmitAnalystBaselineCommand,
        principal: Annotated[PrincipalHeaders, Depends()],
    ) -> dict[str, Any]:
        return _invoke(
            lambda: service.submit_analyst_baseline(
                case_id,
                session_id,
                principal.value(),
                AnalystBaselineSubmission(**command.model_dump()),
            )
        )

    @router.post("/cases/{case_id}/human-baseline/sessions/{session_id}/senior-review")
    def submit_senior_review(
        case_id: str,
        session_id: str,
        command: SubmitSeniorReviewCommand,
        principal: Annotated[PrincipalHeaders, Depends()],
    ) -> dict[str, Any]:
        payload = command.model_dump()
        payload["bounded_follow_up"] = tuple(payload["bounded_follow_up"])
        return _invoke(
            lambda: service.submit_senior_review(
                case_id,
                session_id,
                principal.value(),
                SeniorReviewSubmission(**payload),
            )
        )

    return router


class PrincipalHeaders:
    def __init__(
        self,
        tenant_id: Annotated[str | None, Header(alias="X-Fin-Case-Tenant")] = None,
        project_id: Annotated[str | None, Header(alias="X-Fin-Case-Project")] = None,
        actor_id: Annotated[str | None, Header(alias="X-Fin-Case-Actor")] = None,
        permissions: Annotated[str | None, Header(alias="X-Fin-Case-Permissions")] = None,
    ) -> None:
        self._principal = CasePrincipal(
            tenant_id=(tenant_id or "").strip(),
            project_id=(project_id or "").strip(),
            actor_id=(actor_id or "").strip(),
            permissions=frozenset(
                item.strip() for item in (permissions or "").split(",") if item.strip()
            ),
        )

    def value(self) -> CasePrincipal:
        return self._principal


def _invoke(call: Any) -> dict[str, Any]:
    try:
        return call()
    except HumanBaselineServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
