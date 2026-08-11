from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.fin_0_1_2_s4_t06_current_product_projection import (
    CURRENT_PRODUCT_SURFACES,
    CurrentProductPrincipal,
    CurrentProductProjectionError,
    CurrentProductProjectionService,
)
from ...application.fin_0_1_2_s4_t06_current_review_control import (
    CurrentProductReviewControlService,
    CurrentReviewControlError,
    CurrentReviewControlPrincipal,
    CurrentReturnForRepairDraft,
)
from ...application.fin_0_1_2_s4_t07_reviewer_packet import (
    CurrentProductReviewerPacketError,
    CurrentProductReviewerPacketService,
)
from ...application.fin_0_1_2_s4_t07_reviewer_session import (
    CurrentProductReviewerSessionService,
    QualifiedReviewDecisionDraft,
    ReviewerSessionError,
)


CurrentProductSurface = Literal[
    "case",
    "run",
    "evidence",
    "numeric",
    "graph",
    "gaps",
    "workpaper",
    "report",
    "trace",
    "quality",
]


class CurrentProductCaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    projection_mode: Literal["current"]
    manifest_digest: str
    items: list[dict[str, Any]]
    next_cursor: None = None


class CurrentProductSurfaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    projection_mode: Literal["current"]
    manifest_digest: str
    case_key: str
    case_projection_digest: str
    surface: CurrentProductSurface
    view_digest: str
    data: dict[str, Any]


class CurrentReturnForRepairCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_manifest_digest: str = Field(min_length=64, max_length=64)
    expected_case_projection_digest: str = Field(min_length=64, max_length=64)
    target_surface: CurrentProductSurface
    expected_target_view_digest: str = Field(min_length=64, max_length=64)
    target_ref: str = Field(min_length=1, max_length=160)
    reason_code: Literal[
        "missing_authority",
        "numeric_scope_or_unit",
        "unsupported_inference",
        "missing_counterevidence",
        "lineage_mismatch",
        "delivery_clarity",
    ]
    reviewer_note: str = Field(min_length=1, max_length=500)
    actor_ref: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=160)


class CurrentReviewControlStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    projection_mode: Literal["current"]
    case_key: str
    manifest_digest: str
    case_projection_digest: str
    event_count: int
    head_event_digest: str | None
    return_requests: list[dict[str, Any]]
    replay_integrity: Literal["pass"]
    replay_digest: str
    T07_handoff: dict[str, Any]
    hard_boundaries: dict[str, Any]


class CurrentReviewerPacketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    projection_mode: Literal["current"]
    status: Literal["ready_for_authenticated_qualified_human_review"]
    case_key: Literal["NVDA"]
    exact_binding: dict[str, Any]
    review_checklist: list[dict[str, Any]]
    review_burden: dict[str, Any]
    sections: dict[str, Any]
    decision_boundary: dict[str, Any]
    hard_boundaries: dict[str, Any]
    packet_digest: str


class QualifiedReviewDecisionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["accept_exact_version", "return_for_repair"]
    reviewer_note: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=160)
    target_surface: CurrentProductSurface | None = None
    expected_target_view_digest: str | None = Field(
        default=None, min_length=64, max_length=64
    )
    reason_code: str | None = Field(default=None, min_length=1, max_length=120)


class QualifiedReviewStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    case_key: Literal["NVDA"]
    session: dict[str, Any]
    exact_binding: dict[str, Any]
    decision: dict[str, Any] | None
    event_replay: dict[str, Any]
    acceptance: dict[str, Any]
    state_digest: str


def build_current_product_router(
    service: CurrentProductProjectionService,
    review_control_service: CurrentProductReviewControlService | None = None,
    reviewer_packet_service: CurrentProductReviewerPacketService | None = None,
    reviewer_session_service: CurrentProductReviewerSessionService | None = None,
) -> APIRouter:
    router = APIRouter(tags=["fin-0.1.2-current-product-projection"])

    @router.get(
        "/current-product/cases",
        response_model=CurrentProductCaseListResponse,
    )
    def list_current_product_cases(
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
        except CurrentProductProjectionError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = f'"manifest={projection["manifest_digest"]}"'
        return projection

    @router.get(
        "/current-product/cases/{case_key}",
        response_model=CurrentProductSurfaceResponse,
    )
    def get_current_product_case(
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
        except CurrentProductProjectionError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = f'"view={projection["view_digest"]}"'
        return projection

    if review_control_service is not None:

        @router.get(
            "/current-product/cases/{case_key}/review-control",
            response_model=CurrentReviewControlStateResponse,
        )
        def get_current_review_control(
            case_key: str,
            response: Response,
            product_mode: Annotated[
                str | None, Header(alias="X-Fin-Product-Mode")
            ] = None,
            actor_id: Annotated[
                str | None, Header(alias="X-Fin-Current-Actor")
            ] = None,
            permissions: Annotated[
                str | None, Header(alias="X-Fin-Case-Permissions")
            ] = None,
        ) -> dict[str, Any]:
            try:
                projection = review_control_service.get_state(
                    case_key,
                    _review_principal(product_mode, actor_id, permissions),
                )
            except CurrentReviewControlError as exc:
                _raise_review_control_error(exc)
            response.headers["ETag"] = (
                f'"review-replay={projection["replay_digest"]}"'
            )
            return projection

    if reviewer_session_service is not None:

        @router.get(
            "/current-product/cases/NVDA/qualified-review",
            response_model=QualifiedReviewStateResponse,
        )
        def get_qualified_review_state(
            response: Response,
            authorization: Annotated[
                str | None, Header(alias="Authorization")
            ] = None,
        ) -> dict[str, Any]:
            try:
                state = reviewer_session_service.get_review_state(
                    _bearer_credential(authorization)
                )
            except ReviewerSessionError as exc:
                raise HTTPException(
                    status_code=exc.status_code, detail=exc.detail
                ) from exc
            response.headers["ETag"] = f'"qualified-review={state["state_digest"]}"'
            return state

        @router.post(
            "/current-product/cases/NVDA/qualified-review/decisions",
            response_model=QualifiedReviewStateResponse,
        )
        def record_qualified_review_decision(
            command: QualifiedReviewDecisionCommand,
            response: Response,
            authorization: Annotated[
                str | None, Header(alias="Authorization")
            ] = None,
        ) -> dict[str, Any]:
            try:
                state = reviewer_session_service.record_decision(
                    _bearer_credential(authorization),
                    QualifiedReviewDecisionDraft(**command.model_dump()),
                )
            except ReviewerSessionError as exc:
                raise HTTPException(
                    status_code=exc.status_code, detail=exc.detail
                ) from exc
            response.headers["ETag"] = f'"qualified-review={state["state_digest"]}"'
            return state

    if reviewer_packet_service is not None:

        @router.get(
            "/current-product/cases/{case_key}/reviewer-packet",
            response_model=CurrentReviewerPacketResponse,
        )
        def get_current_product_reviewer_packet(
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
                packet = reviewer_packet_service.get_packet(
                    case_key, _principal(product_mode, permissions)
                )
            except CurrentProductReviewerPacketError as exc:
                raise HTTPException(
                    status_code=exc.status_code, detail=exc.detail
                ) from exc
            response.headers["ETag"] = f'"review-packet={packet["packet_digest"]}"'
            return packet

    if review_control_service is not None:

        @router.post(
            "/current-product/cases/{case_key}/return-requests",
            status_code=status.HTTP_202_ACCEPTED,
            response_model=CurrentReviewControlStateResponse,
        )
        def request_current_product_repair(
            case_key: str,
            command: CurrentReturnForRepairCommand,
            response: Response,
            product_mode: Annotated[
                str | None, Header(alias="X-Fin-Product-Mode")
            ] = None,
            actor_id: Annotated[
                str | None, Header(alias="X-Fin-Current-Actor")
            ] = None,
            permissions: Annotated[
                str | None, Header(alias="X-Fin-Case-Permissions")
            ] = None,
        ) -> dict[str, Any]:
            try:
                projection = review_control_service.request_return_for_repair(
                    case_key,
                    CurrentReturnForRepairDraft(**command.model_dump()),
                    _review_principal(product_mode, actor_id, permissions),
                )
            except CurrentReviewControlError as exc:
                _raise_review_control_error(exc)
            response.headers["ETag"] = (
                f'"review-replay={projection["replay_digest"]}"'
            )
            return projection

    @router.get(
        "/current-product/cases/{case_key}/{surface}",
        response_model=CurrentProductSurfaceResponse,
    )
    def get_current_product_surface(
        case_key: str,
        surface: CurrentProductSurface,
        response: Response,
        product_mode: Annotated[
            str | None, Header(alias="X-Fin-Product-Mode")
        ] = None,
        permissions: Annotated[
            str | None, Header(alias="X-Fin-Case-Permissions")
        ] = None,
    ) -> dict[str, Any]:
        if surface not in CURRENT_PRODUCT_SURFACES:
            raise HTTPException(
                status_code=404,
                detail={"reason": "current_product_surface_not_found"},
            )
        try:
            projection = service.get_surface(
                case_key,
                surface,
                _principal(product_mode, permissions),
            )
        except CurrentProductProjectionError as exc:
            _raise_service_error(exc)
        response.headers["ETag"] = f'"view={projection["view_digest"]}"'
        return projection

    return router


def _principal(
    product_mode: str | None, permissions: str | None
) -> CurrentProductPrincipal:
    return CurrentProductPrincipal(
        mode=(product_mode or "").strip(),
        permissions=frozenset(
            item.strip()
            for item in (permissions or "").split(",")
            if item.strip()
        ),
    )


def _bearer_credential(authorization: str | None) -> str:
    value = (authorization or "").strip()
    if not value.startswith("Bearer ") or not value[7:].strip():
        raise ReviewerSessionError("t07_reviewer_bearer_credential_required", 401)
    return value[7:].strip()


def _review_principal(
    product_mode: str | None,
    actor_id: str | None,
    permissions: str | None,
) -> CurrentReviewControlPrincipal:
    return CurrentReviewControlPrincipal(
        mode=(product_mode or "").strip(),
        actor_id=(actor_id or "").strip(),
        permissions=frozenset(
            item.strip()
            for item in (permissions or "").split(",")
            if item.strip()
        ),
    )


def _raise_service_error(error: CurrentProductProjectionError) -> None:
    raise HTTPException(
        status_code=error.status_code, detail=error.detail
    ) from error


def _raise_review_control_error(error: CurrentReviewControlError) -> None:
    raise HTTPException(
        status_code=error.status_code, detail=error.detail
    ) from error
