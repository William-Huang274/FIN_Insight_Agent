from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ingestion.source_intake import SourceIntakeError

from ..application.source_intake_service import SourceIntakeService


class AutomaticSourceIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str | None = Field(default=None, min_length=1, max_length=128)


def build_source_intake_router(service: SourceIntakeService) -> APIRouter:
    router = APIRouter(prefix="/operations/source-intake", tags=["operations"])

    @router.get("/routes", operation_id="listSourceIntakeRoutes")
    def list_routes() -> dict[str, Any]:
        return {
            "routes": service.routes(),
            "boundary": "captured_source_is_not_evidence",
        }

    @router.get("/attempts", operation_id="listSourceIntakeAttempts")
    def list_attempts(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        return {
            "attempts": service.attempts(limit=limit),
            "raw_bytes_exposed": False,
        }

    @router.post(
        "/uploads/{route_id}",
        operation_id="uploadOfficialSourcePdf",
    )
    async def upload_source(
        route_id: str,
        request: Request,
        attempt_id: str | None = Query(default=None, min_length=1, max_length=128),
    ) -> dict[str, Any]:
        try:
            ceiling = service.route_byte_ceiling(route_id)
        except SourceIntakeError as exc:
            _raise_source_intake_http(exc)
        declared_length = request.headers.get("content-length")
        if declared_length:
            try:
                if int(declared_length) > ceiling:
                    raise HTTPException(413, "source_intake_body_too_large")
            except ValueError as exc:
                raise HTTPException(
                    400, "source_intake_content_length_invalid"
                ) from exc
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > ceiling:
                raise HTTPException(413, "source_intake_body_too_large")
        try:
            attempt = service.upload(
                route_id=route_id,
                attempt_id=attempt_id,
                body=bytes(body),
                declared_content_type=str(
                    request.headers.get("content-type") or ""
                ),
            )
        except SourceIntakeError as exc:
            _raise_source_intake_http(exc)
        return {
            "attempt": attempt,
            "boundary": "captured_source_is_not_evidence",
        }

    @router.post(
        "/automatic/{route_id}",
        operation_id="acquireOfficialSourceAutomatically",
    )
    def acquire_automatic(
        route_id: str,
        payload: AutomaticSourceIntakeRequest,
    ) -> dict[str, Any]:
        try:
            attempt = service.acquire_automatic(
                route_id=route_id,
                attempt_id=payload.attempt_id,
            )
        except SourceIntakeError as exc:
            _raise_source_intake_http(exc)
        return {
            "attempt": attempt,
            "boundary": "captured_source_is_not_evidence",
        }

    return router


def _raise_source_intake_http(exc: SourceIntakeError) -> None:
    code = str(exc)
    if code == "source_intake_route_not_found":
        status = 404
    elif code == "source_intake_attempt_already_exists":
        status = 409
    elif code == "source_intake_body_too_large":
        status = 413
    elif code.endswith("_forbidden"):
        status = 403
    else:
        status = 422
    raise HTTPException(status, code) from exc


__all__ = ["build_source_intake_router"]
