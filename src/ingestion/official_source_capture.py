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
from urllib.parse import urljoin, urlparse

import requests


CAPTURE_SCHEMA_VERSION = "fin_ia_official_source_capture_v1_0"
CAPTURE_PLAN_SCHEMA_VERSION = "fin_ia_s1b_official_source_capture_plan_v1_0"
CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1d_official_source_capture_plan_v1_1"
)
CAPTURE_PLAN_BROWSER_SCHEMA_VERSION = (
    "fin_ia_s1d_official_source_browser_capture_plan_v1_2"
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
class _TransportPreflightResponse:
    request_url: str
    status_code: int
    final_url: str
    headers: Mapping[str, str]
    redirect_chain: tuple[str, ...]
    body: bytes


@dataclass(frozen=True)
class _TransportResponse:
    status_code: int
    final_url: str
    headers: Mapping[str, str]
    redirect_chain: tuple[str, ...]
    body: bytes
    transport_attempts: int
    preflight_responses: tuple[_TransportPreflightResponse, ...] = ()


TransportFetcher = Callable[[Mapping[str, Any]], _TransportResponse]


def validate_capture_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    schema_version = str(value.get("schema_version") or "")
    if schema_version not in {
        CAPTURE_PLAN_SCHEMA_VERSION,
        CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION,
        CAPTURE_PLAN_BROWSER_SCHEMA_VERSION,
    }:
        raise OfficialSourceCaptureError("official_capture_plan_schema_invalid")
    expected_status = (
        "s1d_official_source_capture_plan"
        if schema_version
        in {
            CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION,
            CAPTURE_PLAN_BROWSER_SCHEMA_VERSION,
        }
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
        transport = str(source.get("transport") or "requests")
        if not (
            route_id
            and route_id not in route_ids
            and parsed.scheme == "https"
            and (parsed.hostname or "").lower() in allowed_hosts
            and expected_types
            and int(source.get("byte_ceiling") or 0) > 0
            and int(source.get("timeout_seconds") or 0) > 0
            and transport
            in (
                {
                    "requests",
                    "curl",
                    "playwright_api_request",
                    "playwright_browser_download",
                }
                if schema_version == CAPTURE_PLAN_BROWSER_SCHEMA_VERSION
                else {"requests", "curl", "playwright_api_request"}
                if schema_version == CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION
                else {"requests", "curl"}
            )
            and 0 <= int(source.get("max_transport_retries") or 0) <= 2
        ):
            raise OfficialSourceCaptureError("official_capture_source_invalid")
        if transport == "playwright_browser_download":
            discovery_url = str(source.get("discovery_url") or "").strip()
            discovery = urlparse(discovery_url)
            selector = str(source.get("link_selector") or "").strip()
            expected_download_url = str(
                source.get("expected_download_url") or url
            ).strip()
            expected_download = urlparse(expected_download_url)
            if not (
                schema_version == CAPTURE_PLAN_BROWSER_SCHEMA_VERSION
                and discovery.scheme == "https"
                and (discovery.hostname or "").lower() in allowed_hosts
                and expected_download.scheme == "https"
                and (expected_download.hostname or "").lower() in allowed_hosts
                and selector
                and len(selector) <= 512
                and "\n" not in selector
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
        validated["schema_version"]
        in {
            CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION,
            CAPTURE_PLAN_BROWSER_SCHEMA_VERSION,
        }
    )
    result_prefix = "s1d" if successor else "s1b"
    result = {
        "schema_version": (
            "fin_ia_s1d_official_source_capture_result_v1_2"
            if validated["schema_version"] == CAPTURE_PLAN_BROWSER_SCHEMA_VERSION
            else "fin_ia_s1d_official_source_capture_result_v1_1"
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
        "discovery_url": str(source.get("discovery_url") or "") or None,
        "expected_download_url": str(
            source.get("expected_download_url") or ""
        )
        or None,
    }
    request_ref = _persist_cas(object_root, request_capture)
    preflight_refs: list[dict[str, Any]] = []

    def persist_preflight(response: _TransportPreflightResponse) -> None:
        preflight_refs.append(
            _persist_preflight_capture(
                object_root,
                response,
                case_key=case_key,
                route_id=route_id,
                request_capture_ref=request_ref,
            )
        )

    try:
        response = _fetch_source(
            source,
            session=session,
            transport_fetchers=transport_fetchers,
            preflight_recorder=persist_preflight,
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
            "preflight_response_refs": preflight_refs,
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
            "preflight_captures": preflight_refs,
        }

    for preflight in response.preflight_responses:
        persist_preflight(preflight)
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
        "preflight_response_refs": preflight_refs,
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
        "preflight_captures": preflight_refs,
    }


def _fetch_source(
    source: Mapping[str, Any],
    *,
    session: requests.Session,
    transport_fetchers: Mapping[str, TransportFetcher],
    preflight_recorder: Callable[[_TransportPreflightResponse], None],
) -> _TransportResponse:
    transport = str(source.get("transport") or "requests")
    injected = transport_fetchers.get(transport)
    if injected is not None:
        return injected(source)
    if transport == "curl":
        return _fetch_with_curl(source)
    if transport == "playwright_api_request":
        return _fetch_with_playwright_api_request(source)
    if transport == "playwright_browser_download":
        return _fetch_with_playwright_browser_download(
            source,
            preflight_recorder=preflight_recorder,
        )
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


def _fetch_with_playwright_browser_download(
    source: Mapping[str, Any],
    *,
    preflight_recorder: Callable[[_TransportPreflightResponse], None],
) -> _TransportResponse:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise OfficialSourceCaptureError(
            "official_source_playwright_unavailable"
        ) from exc

    discovery_url = str(source["discovery_url"])
    expected_download_url = str(
        source.get("expected_download_url") or source["url"]
    )
    allowed_hosts = {
        str(host).strip().lower() for host in source.get("allowed_hosts") or ()
    }
    timeout_ms = int(source["timeout_seconds"]) * 1000
    byte_ceiling = int(source["byte_ceiling"])
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(
                channel=str(source.get("browser_channel") or "msedge"),
                headless=True,
                args=["--disable-pdf-extension"],
            )
            try:
                context = browser.new_context(
                    accept_downloads=True,
                    locale="en-US",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                allowed_documents = {discovery_url, expected_download_url}

                def route_request(route):  # noqa: ANN001
                    request_url = str(route.request.url)
                    parsed = urlparse(request_url)
                    if (
                        route.request.resource_type == "document"
                        and (parsed.hostname or "").lower() in allowed_hosts
                        and any(
                            request_url.startswith(allowed)
                            for allowed in allowed_documents
                        )
                    ):
                        route.continue_()
                    else:
                        route.abort()

                context.route("**/*", route_request)
                page = context.new_page()
                discovery_response = page.goto(
                    discovery_url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                if discovery_response is None:
                    raise OfficialSourceCaptureError(
                        "official_source_browser_discovery_response_missing"
                    )
                discovery_body = discovery_response.body()
                if len(discovery_body) > byte_ceiling:
                    raise OfficialSourceCaptureError(
                        "official_source_body_too_large"
                    )
                discovery_preflight = _TransportPreflightResponse(
                    request_url=discovery_url,
                    status_code=int(discovery_response.status),
                    final_url=str(discovery_response.url),
                    headers={
                        str(key).lower(): str(value)
                        for key, value in discovery_response.headers.items()
                    },
                    redirect_chain=(),
                    body=discovery_body,
                )
                preflight_recorder(discovery_preflight)
                if not 200 <= discovery_response.status < 300:
                    raise OfficialSourceCaptureError(
                        f"official_source_browser_discovery_http_{discovery_response.status}"
                    )
                locator = page.locator(str(source["link_selector"])).first
                locator.wait_for(state="attached", timeout=timeout_ms)
                href = str(locator.get_attribute("href") or "")
                resolved_href = urljoin(str(page.url), href)
                resolved = urlparse(resolved_href)
                if not (
                    resolved_href == expected_download_url
                    and (resolved.hostname or "").lower() in allowed_hosts
                ):
                    raise OfficialSourceCaptureError(
                        "official_source_browser_download_link_mismatch"
                    )
                response_metadata: dict[str, Any] = {}

                def observe_response(observed):  # noqa: ANN001
                    if str(observed.url).startswith(expected_download_url):
                        response_metadata.update(
                            {
                                "status_code": int(observed.status),
                                "final_url": str(observed.url),
                                "headers": {
                                    str(key).lower(): str(value)
                                    for key, value in observed.headers.items()
                                },
                            }
                        )

                page.on("response", observe_response)
                with page.expect_download(timeout=timeout_ms) as pending_download:
                    locator.click(timeout=timeout_ms)
                download = pending_download.value
                failure = download.failure()
                if failure:
                    raise OfficialSourceCaptureError(
                        "official_source_browser_download_failure"
                    )
                downloaded_path = download.path()
                if downloaded_path is None:
                    raise OfficialSourceCaptureError(
                        "official_source_browser_download_path_missing"
                    )
                body = Path(downloaded_path).read_bytes()
                if len(body) > byte_ceiling:
                    raise OfficialSourceCaptureError(
                        "official_source_body_too_large"
                    )
                return _TransportResponse(
                    status_code=int(response_metadata.get("status_code") or 200),
                    final_url=str(
                        response_metadata.get("final_url") or download.url
                    ),
                    headers=dict(
                        response_metadata.get("headers")
                        or {
                            "content-type": "application/pdf",
                            "content-length": str(len(body)),
                        }
                    ),
                    redirect_chain=(),
                    body=body,
                    transport_attempts=2,
                )
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise OfficialSourceCaptureError(
            "official_source_browser_timeout"
        ) from exc
    except PlaywrightError as exc:
        raise OfficialSourceCaptureError(
            "official_source_browser_transport_failure"
        ) from exc


def _persist_preflight_capture(
    object_root: Path,
    response: _TransportPreflightResponse,
    *,
    case_key: str,
    route_id: str,
    request_capture_ref: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "capture_kind": "source_transport_preflight_response",
        "case_key": case_key,
        "route_id": route_id,
        "request_capture_ref": request_capture_ref["object_ref"],
        "request_capture_digest": request_capture_ref["sha256"],
        "request_url": response.request_url,
        "status_code": response.status_code,
        "final_url": response.final_url,
        "headers": {
            str(key).lower(): str(value)
            for key, value in response.headers.items()
            if str(key).lower() in SAFE_RESPONSE_HEADERS
        },
        "redirect_chain": list(response.redirect_chain),
        "body_base64": base64.b64encode(response.body).decode("ascii"),
        "body_sha256": hashlib.sha256(response.body).hexdigest(),
        "body_bytes": len(response.body),
        "capture_before_target_link_evaluation": True,
        "credential_cookie_authorization_present": False,
    }
    return _persist_cas(object_root, payload)


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
    if isinstance(exc, requests.ConnectTimeout):
        return "official_source_transport_connect_timeout"
    if isinstance(exc, requests.ReadTimeout):
        return "official_source_transport_read_timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "official_source_transport_tls_error"
    if isinstance(exc, requests.exceptions.ProxyError):
        return "official_source_transport_proxy_error"
    if isinstance(exc, requests.exceptions.ChunkedEncodingError):
        return "official_source_transport_response_stream_error"
    if isinstance(exc, requests.TooManyRedirects):
        return "official_source_transport_redirect_error"
    if isinstance(exc, requests.exceptions.InvalidURL):
        return "official_source_transport_invalid_url"
    if isinstance(exc, requests.Timeout):
        return "official_source_transport_timeout"
    if isinstance(exc, requests.ConnectionError):
        return "official_source_transport_connection_error"
    if isinstance(exc, requests.RequestException):
        return "official_source_transport_request_error"
    return "official_source_transport_unclassified_error"


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
    "CAPTURE_PLAN_BROWSER_SCHEMA_VERSION",
    "CAPTURE_SCHEMA_VERSION",
    "OfficialSourceCaptureError",
    "capture_plan",
    "validate_capture_plan",
]
