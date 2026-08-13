from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import requests


CAPTURE_SCHEMA_VERSION = "fin_ia_official_source_capture_v1_0"
CAPTURE_PLAN_SCHEMA_VERSION = "fin_ia_s1b_official_source_capture_plan_v1_0"
CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1d_official_source_capture_plan_v1_1"
)
SAFE_RESPONSE_HEADERS = {
    "content-length",
    "content-type",
    "etag",
    "last-modified",
}


class OfficialSourceCaptureError(RuntimeError):
    """Raised when an official source cannot be captured without weakening policy."""


@dataclass(frozen=True)
class _TransportResponse:
    status_code: int
    final_url: str
    headers: Mapping[str, str]
    redirect_chain: tuple[str, ...]
    body: bytes
    transport_attempts: int


TransportFetcher = Callable[[Mapping[str, Any]], _TransportResponse]


def validate_capture_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    schema_version = str(value.get("schema_version") or "")
    if schema_version not in {
        CAPTURE_PLAN_SCHEMA_VERSION,
        CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION,
    }:
        raise OfficialSourceCaptureError("official_capture_plan_schema_invalid")
    expected_status = (
        "s1d_official_source_capture_plan"
        if schema_version == CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION
        else "s1b_official_source_capture_plan"
    )
    if value.get("status") != expected_status:
        raise OfficialSourceCaptureError("official_capture_plan_status_invalid")
    policy = value.get("policy")
    sources = value.get("sources")
    if not (
        isinstance(policy, Mapping)
        and policy.get("capture_before_parse") is True
        and policy.get("https_only") is True
        and policy.get("credentials_forbidden") is True
        and isinstance(sources, list)
        and sources
    ):
        raise OfficialSourceCaptureError("official_capture_plan_shape_invalid")
    route_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            raise OfficialSourceCaptureError("official_capture_source_invalid")
        route_id = str(source.get("route_id") or "").strip()
        url = str(source.get("url") or "").strip()
        parsed = urlparse(url)
        allowed_hosts = {
            str(host).strip().lower() for host in source.get("allowed_hosts") or ()
        }
        expected_types = [
            str(item).strip().lower()
            for item in source.get("expected_content_types") or ()
        ]
        if not (
            route_id
            and route_id not in route_ids
            and parsed.scheme == "https"
            and (parsed.hostname or "").lower() in allowed_hosts
            and expected_types
            and int(source.get("byte_ceiling") or 0) > 0
            and int(source.get("timeout_seconds") or 0) > 0
            and str(source.get("transport") or "requests")
            in (
                {"requests", "curl", "playwright_api_request"}
                if schema_version == CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION
                else {"requests", "curl"}
            )
            and 0 <= int(source.get("max_transport_retries") or 0) <= 2
        ):
            raise OfficialSourceCaptureError("official_capture_source_invalid")
        route_ids.add(route_id)
    return value


def capture_plan(
    plan: Mapping[str, Any],
    *,
    output_root: Path,
    attempt_id: str,
    session: requests.Session | None = None,
    transport_fetchers: Mapping[str, TransportFetcher] | None = None,
) -> dict[str, Any]:
    validated = validate_capture_plan(plan)
    root = output_root.resolve() / attempt_id
    if root.exists():
        raise OfficialSourceCaptureError("official_capture_attempt_already_exists")
    object_root = root / "objects"
    active_session = session or requests.Session()
    rows: list[dict[str, Any]] = []
    for source in validated["sources"]:
        rows.append(
            _capture_source(
                source,
                object_root=object_root,
                session=active_session,
                transport_fetchers=transport_fetchers or {},
            )
        )
    successor = (
        validated["schema_version"] == CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION
    )
    result_prefix = "s1d" if successor else "s1b"
    result = {
        "schema_version": (
            "fin_ia_s1d_official_source_capture_result_v1_1"
            if successor
            else "fin_ia_s1b_official_source_capture_result_v1_0"
        ),
        "status": (
            f"{result_prefix}_official_sources_captured"
            if all(row["status"] == "captured" for row in rows)
            else f"{result_prefix}_official_source_capture_incomplete"
        ),
        "attempt_id": attempt_id,
        "source_routes_executed": len(rows),
        "network_attempts_lower_bound": sum(
            int(row.get("transport_attempts") or row.get("transport_attempts_lower_bound") or 1)
            for row in rows
        ),
        "network_attempts_upper_bound": sum(
            int(row.get("transport_attempts") or row.get("transport_attempts_upper_bound") or 1)
            for row in rows
        ),
        "model_calls": 0,
        "sources": rows,
    }
    _persist_result(root / "result.json", result)
    return result


def _capture_source(
    source: Mapping[str, Any],
    *,
    object_root: Path,
    session: requests.Session,
    transport_fetchers: Mapping[str, TransportFetcher],
) -> dict[str, Any]:
    route_id = str(source["route_id"])
    case_key = str(source["case_key"])
    url = str(source["url"])
    allowed_hosts = {
        str(host).strip().lower() for host in source.get("allowed_hosts") or ()
    }
    request_capture = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "capture_kind": "source_request",
        "case_key": case_key,
        "route_id": route_id,
        "method": "GET",
        "url": url,
        "operator_contact_configured": bool(_operator_contact()),
        "credential_cookie_authorization_present": False,
        "transport_adapter": str(source.get("transport") or "requests"),
        "max_transport_retries": int(source.get("max_transport_retries") or 0),
    }
    request_ref = _persist_cas(object_root, request_capture)
    try:
        response = _fetch_source(
            source,
            session=session,
            transport_fetchers=transport_fetchers,
        )
    except (requests.RequestException, OfficialSourceCaptureError) as exc:
        failure = {
            "schema_version": CAPTURE_SCHEMA_VERSION,
            "capture_kind": "source_transport_failure",
            "case_key": case_key,
            "route_id": route_id,
            "request_capture_ref": request_ref["object_ref"],
            "request_capture_digest": request_ref["sha256"],
            "failure_code": _failure_code(exc),
            "capture_before_parse": True,
            "credential_cookie_authorization_present": False,
        }
        failure_ref = _persist_cas(object_root, failure)
        return {
            "route_id": route_id,
            "status": "transport_failure",
            "failure_code": failure["failure_code"],
            "transport_attempts_lower_bound": 1,
            "transport_attempts_upper_bound": 1
            + int(source.get("max_transport_retries") or 0),
            "request_capture": request_ref,
            "response_capture": failure_ref,
        }

    final = urlparse(response.final_url)
    content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].lower()
    expected_types = {
        str(item).strip().lower()
        for item in source.get("expected_content_types") or ()
    }
    response_capture = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "capture_kind": "source_response",
        "case_key": case_key,
        "route_id": route_id,
        "request_capture_ref": request_ref["object_ref"],
        "request_capture_digest": request_ref["sha256"],
        "status_code": int(response.status_code),
        "final_url": str(response.final_url),
        "headers": {
            str(key).lower(): str(value)
            for key, value in response.headers.items()
            if str(key).lower() in SAFE_RESPONSE_HEADERS
        },
        "redirect_chain": list(response.redirect_chain),
        "body_base64": base64.b64encode(response.body).decode("ascii"),
        "body_sha256": hashlib.sha256(response.body).hexdigest(),
        "body_bytes": len(response.body),
        "capture_before_parse": True,
        "credential_cookie_authorization_present": False,
    }
    response_ref = _persist_cas(object_root, response_capture)
    if not 200 <= response.status_code < 300:
        status = "http_failure"
        failure_code = f"official_source_http_{response.status_code}"
    elif final.scheme != "https" or (final.hostname or "").lower() not in allowed_hosts:
        status = "rejected_final_url"
        failure_code = "official_source_final_url_not_allowlisted"
    elif content_type not in expected_types:
        status = "rejected_content_type"
        failure_code = "official_source_content_type_unexpected"
    else:
        status = "captured"
        failure_code = None
    return {
        "route_id": route_id,
        "status": status,
        "failure_code": failure_code,
        "content_type": content_type,
        "body_bytes": len(response.body),
        "body_sha256": response_capture["body_sha256"],
        "transport_attempts": response.transport_attempts,
        "request_capture": request_ref,
        "response_capture": response_ref,
    }


def _fetch_source(
    source: Mapping[str, Any],
    *,
    session: requests.Session,
    transport_fetchers: Mapping[str, TransportFetcher],
) -> _TransportResponse:
    transport = str(source.get("transport") or "requests")
    injected = transport_fetchers.get(transport)
    if injected is not None:
        return injected(source)
    if transport == "curl":
        return _fetch_with_curl(source)
    if transport == "playwright_api_request":
        return _fetch_with_playwright_api_request(source)
    response = session.get(
        str(source["url"]),
        headers={
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1",
            "User-Agent": _official_source_user_agent(),
            "Connection": "close",
        },
        allow_redirects=True,
        stream=True,
        timeout=(10, int(source["timeout_seconds"])),
    )
    body = _read_requests_body(response, int(source["byte_ceiling"]))
    return _TransportResponse(
        status_code=int(response.status_code),
        final_url=str(response.url),
        headers={str(key).lower(): str(value) for key, value in response.headers.items()},
        redirect_chain=tuple(str(item.url) for item in response.history),
        body=body,
        transport_attempts=1,
    )


def _fetch_with_playwright_api_request(
    source: Mapping[str, Any],
) -> _TransportResponse:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise OfficialSourceCaptureError(
            "official_source_playwright_unavailable"
        ) from exc

    try:
        with sync_playwright() as runtime:
            context = runtime.request.new_context(
                extra_http_headers={
                    "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1",
                    "User-Agent": _official_source_user_agent(),
                },
                ignore_https_errors=False,
            )
            try:
                response = context.get(
                    str(source["url"]),
                    fail_on_status_code=False,
                    max_redirects=10,
                    timeout=int(source["timeout_seconds"]) * 1000,
                )
                body = response.body()
                if len(body) > int(source["byte_ceiling"]):
                    raise OfficialSourceCaptureError(
                        "official_source_body_too_large"
                    )
                return _TransportResponse(
                    status_code=int(response.status),
                    final_url=str(response.url),
                    headers={
                        str(key).lower(): str(value)
                        for key, value in response.headers.items()
                    },
                    redirect_chain=(),
                    body=body,
                    transport_attempts=1,
                )
            finally:
                context.dispose()
    except PlaywrightTimeoutError as exc:
        raise OfficialSourceCaptureError(
            "official_source_playwright_timeout"
        ) from exc
    except PlaywrightError as exc:
        raise OfficialSourceCaptureError(
            "official_source_playwright_transport_failure"
        ) from exc


def _fetch_with_curl(source: Mapping[str, Any]) -> _TransportResponse:
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        raise OfficialSourceCaptureError("official_source_curl_unavailable")
    marker = b"\nFIN_CAPTURE_META:"
    command = [
        executable,
        "-L",
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "10",
        "--max-time",
        str(int(source["timeout_seconds"])),
        "--max-filesize",
        str(int(source["byte_ceiling"])),
        "--retry",
        str(int(source.get("max_transport_retries") or 0)),
        "--retry-all-errors",
        "--retry-delay",
        "2",
        "--retry-max-time",
        str(int(source.get("retry_total_seconds") or 90)),
        "--config",
        "-",
        "--write-out",
        "\nFIN_CAPTURE_META:%{json}",
        str(source["url"]),
    ]
    curl_config = (
        'header = "Accept: text/html,application/pdf;q=0.9,*/*;q=0.1"\n'
        f'user-agent = "{_official_source_user_agent()}"\n'
    ).encode("utf-8")
    try:
        completed = subprocess.run(
            command,
            input=curl_config,
            capture_output=True,
            check=False,
            timeout=int(source.get("retry_total_seconds") or 90) + 10,
        )
    except subprocess.TimeoutExpired as exc:
        raise OfficialSourceCaptureError(
            "official_source_curl_total_timeout"
        ) from exc
    body, found, metadata_bytes = completed.stdout.rpartition(marker)
    if completed.returncode != 0 or not found:
        raise OfficialSourceCaptureError("official_source_curl_transport_failure")
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialSourceCaptureError("official_source_curl_metadata_invalid") from exc
    if len(body) > int(source["byte_ceiling"]):
        raise OfficialSourceCaptureError("official_source_body_too_large")
    content_type = str(metadata.get("content_type") or "")
    content_length = str(metadata.get("size_download") or len(body))
    return _TransportResponse(
        status_code=int(metadata.get("http_code") or 0),
        final_url=str(metadata.get("url_effective") or ""),
        headers={"content-type": content_type, "content-length": content_length},
        redirect_chain=(),
        body=body,
        transport_attempts=int(metadata.get("num_retries") or 0) + 1,
    )


def _read_requests_body(response: requests.Response, byte_ceiling: int) -> bytes:
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        observed += len(chunk)
        if observed > byte_ceiling:
            raise OfficialSourceCaptureError("official_source_body_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def _operator_contact() -> str:
    return str(os.getenv("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()


def _official_source_user_agent() -> str:
    contact = _operator_contact()
    return f"FIN-Insight-Agent/0.1.3 {contact}" if contact else "FIN-Insight-Agent/0.1.3"


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, OfficialSourceCaptureError):
        return str(exc)
    if isinstance(exc, requests.Timeout):
        return "official_source_transport_timeout"
    if isinstance(exc, requests.ConnectionError):
        return "official_source_transport_connection_error"
    return "official_source_transport_error"


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _persist_cas(root: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    data = _canonical_json_bytes(payload)
    digest = hashlib.sha256(data).hexdigest()
    path = root / "raw" / digest[:2] / digest[2:4] / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise OfficialSourceCaptureError("official_capture_cas_collision")
    path.write_bytes(data)
    return {
        "object_ref": path.as_posix(),
        "sha256": digest,
        "bytes": len(data),
    }


def _persist_result(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json_bytes(payload))


__all__ = [
    "CAPTURE_PLAN_SCHEMA_VERSION",
    "CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION",
    "CAPTURE_SCHEMA_VERSION",
    "OfficialSourceCaptureError",
    "capture_plan",
    "validate_capture_plan",
]
