from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from ...application.fin_0_1_2_s4_t06_current_product_projection import (
    CURRENT_PRODUCT_SURFACES,
    CurrentProductPrincipal,
    CurrentProductProjectionError,
    CurrentProductProjectionService,
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


def build_current_product_router(
    service: CurrentProductProjectionService,
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
            raise HTTPException(status_code=404, detail={"reason": "current_product_surface_not_found"})
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


def _raise_service_error(error: CurrentProductProjectionError) -> None:
    raise HTTPException(
        status_code=error.status_code, detail=error.detail
    ) from error
