from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from .runtime_ids import new_trace_id


TRACE_HEADER = "X-Trace-Id"
ELAPSED_HEADER = "X-Elapsed-Time-Ms"
API_ERROR_SCHEMA_VERSION = "finsight_workbench_api_error_v0.1"
_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_LOGGER = logging.getLogger("finsight.workbench.api")


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = API_ERROR_SCHEMA_VERSION
    error_code: str
    message: str
    status_code: int
    trace_id: str
    detail: Any | None = None


def install_api_contracts(app: FastAPI) -> None:
    configure_api_logging()

    @app.middleware("http")
    async def trace_request(request: Request, call_next):
        trace_id = request_trace_id(request)
        request.state.trace_id = trace_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = max(0, int(round((time.perf_counter() - started) * 1000)))
        response.headers[TRACE_HEADER] = trace_id
        response.headers[ELAPSED_HEADER] = str(elapsed_ms)
        log_api_request(
            request=request,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            trace_id=trace_id,
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        return _error_response(
            request=request,
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        return _error_response(
            request=request,
            status_code=422,
            detail=exc.errors(),
            error_code="request_validation_error",
            message="Request validation failed.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        trace_id = request_trace_id(request)
        _LOGGER.exception(
            _json_log(
                {
                    "event": "api_unhandled_exception",
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        )
        return _error_response(
            request=request,
            status_code=500,
            detail="internal_server_error",
            error_code="internal_server_error",
            message="Internal server error.",
        )


def configure_api_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def request_trace_id(request: Request) -> str:
    state_trace = getattr(getattr(request, "state", object()), "trace_id", "")
    if isinstance(state_trace, str) and state_trace:
        return state_trace
    header_trace = str(request.headers.get(TRACE_HEADER, "")).strip()
    if _TRACE_ID_RE.match(header_trace):
        return header_trace
    return new_trace_id()


def log_api_request(*, request: Request, status_code: int, elapsed_ms: int, trace_id: str) -> None:
    _LOGGER.info(
        _json_log(
            {
                "event": "api_request",
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "elapsed_ms": elapsed_ms,
            }
        )
    )


def _error_response(
    *,
    request: Request,
    status_code: int,
    detail: Any,
    error_code: str | None = None,
    message: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    trace_id = request_trace_id(request)
    elapsed_ms = "0"
    error = ApiError(
        error_code=error_code or _error_code_from_detail(status_code, detail),
        message=message or _message_from_detail(detail),
        status_code=status_code,
        trace_id=trace_id,
        detail=detail,
    )
    response_headers = dict(headers or {})
    response_headers[TRACE_HEADER] = trace_id
    response_headers[ELAPSED_HEADER] = elapsed_ms
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "error": error.model_dump(mode="json"),
        },
        headers=response_headers,
    )


def _error_code_from_detail(status_code: int, detail: Any) -> str:
    if isinstance(detail, dict) and str(detail.get("reason") or "").strip():
        return _sanitize_error_code(str(detail["reason"]))
    if isinstance(detail, str) and detail.strip():
        token = re.split(r"[:\s]+", detail.strip(), maxsplit=1)[0]
        return _sanitize_error_code(token)
    return f"http_{status_code}"


def _sanitize_error_code(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower()).strip("_")
    return text or "http_error"


def _message_from_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict) and str(detail.get("reason") or "").strip():
        return str(detail["reason"])
    return "Request failed."


def _json_log(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
