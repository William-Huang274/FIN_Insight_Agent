from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_"
    "diagnostic_canary_authority_decision_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_"
    "diagnostic_canary_exact_once_execution_result_v1_0.json"
)
EXPECTED_AUTHORITY_SHA256 = (
    "5d08c4755a811764c404f1445edda097b97d3e3f2b4f02fad971501cb995fdba"
)
CANARY_ID = (
    "fin01-s4-t06-entry-sub2api-gpt-5p5-responses-"
    "strict-schema-public-diagnostic-r1"
)
WORK_ITEM_ID = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-EXACT-ONCE-EXECUTION"
)
RESULT_SCHEMA_VERSION = (
    "fin_ia_0_1_s4_t06_entry_sub2api_public_nonsensitive_"
    "diagnostic_canary_exact_once_execution_result_v1_0"
)
IMPLEMENTATION_NEXT_ACTION = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT"
)
POST_RESULT_NEXT_ACTION = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-POST-RESULT-PROGRAM-DISPOSITION"
)
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise HTTPError(
            req.full_url,
            code,
            "redirect_not_allowed",
            headers,
            fp,
        )


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_authority() -> dict[str, Any]:
    if not AUTHORITY_PATH.is_file():
        raise RuntimeError("diagnostic_authority_missing")
    if _file_sha256(AUTHORITY_PATH) != EXPECTED_AUTHORITY_SHA256:
        raise RuntimeError("diagnostic_authority_digest_mismatch")
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    permissions = authority["authority"]
    if (
        authority.get("next_action") != IMPLEMENTATION_NEXT_ACTION
        or authority.get("next_action_authorized") is not True
        or permissions.get("future_exact_once_diagnostic_execution_authorized")
        is not True
        or permissions.get("credential_read_write_or_presence_probe_authorized")
        is not False
    ):
        raise RuntimeError("diagnostic_execution_not_authorized")
    if authority["exact_diagnostic_canary"]["canary_id"] != CANARY_ID:
        raise RuntimeError("diagnostic_canary_identity_mismatch")
    return authority


def _derive_exact_request(
    authority: Mapping[str, Any],
) -> tuple[str, dict[str, str], dict[str, Any]]:
    provider = authority["provider_contract"]
    request = authority["exact_request_contract"]
    url = str(provider["full_request_url"])
    marker = provider["static_client_marker"]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        str(marker["header_name"]): str(marker["header_value"]),
        "User-Agent": "FIN-Insight-Synthetic-Diagnostic/1.0",
    }
    body = {
        "model": str(provider["model"]),
        "input": [
            {
                "role": "system",
                "content": str(request["system_input"]),
            },
            {
                "role": "user",
                "content": str(request["user_input"]),
            },
        ],
        "text": {
            "format": request["text_format"],
        },
        "max_output_tokens": int(request["maximum_output_tokens"]),
        "store": bool(request["store"]),
        "stream": bool(request["stream"]),
    }
    return url, headers, body


def _request_digests(
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
) -> dict[str, str]:
    safe_header_shape = sorted(
        name.lower()
        for name in headers
        if name.lower() != "x-openai-actor-authorization"
    )
    return {
        "request_url_sha256": _text_sha256(url),
        "request_body_sha256": _canonical_sha256(body),
        "strict_schema_sha256": _canonical_sha256(
            body["text"]["format"]["schema"]
        ),
        "system_input_sha256": _text_sha256(
            str(body["input"][0]["content"])
        ),
        "user_input_sha256": _text_sha256(
            str(body["input"][1]["content"])
        ),
        "non_marker_header_name_shape_sha256": _canonical_sha256(
            safe_header_shape
        ),
    }


def _extract_output_text(raw: Mapping[str, Any]) -> str:
    direct = raw.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    output = raw.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, Mapping)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                return str(part["text"])
    return ""


def _parse_and_validate_exact(
    raw: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    output_text = _extract_output_text(raw)
    if not output_text:
        return None, "provider_envelope_missing_output_text"
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        return None, "strict_schema_parse_failed"
    if not isinstance(parsed, dict):
        return None, "strict_schema_root_not_object"
    if set(parsed) != set(expected):
        return None, "strict_schema_field_set_mismatch"
    if parsed != dict(expected):
        return None, "local_exact_value_validation_failed"
    return parsed, None


def _fake_transport_preflight(
    body: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    fixture = {
        "id": "fixture-not-persisted",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            expected,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
        },
    }
    parsed, failure = _parse_and_validate_exact(fixture, expected)
    return (
        failure is None
        and parsed == dict(expected)
        and body["text"]["format"]["strict"] is True
        and body["store"] is False
        and body["stream"] is False
    )


def preflight(*, result_path: Path = RESULT_PATH) -> dict[str, Any]:
    authority = _load_authority()
    if result_path.exists():
        raise RuntimeError("diagnostic_canary_identity_already_consumed")
    url, headers, body = _derive_exact_request(authority)
    provider = authority["provider_contract"]
    budget = authority["hard_budget"]
    marker_name = str(
        provider["static_client_marker"]["header_name"]
    ).lower()
    header_names = {name.lower() for name in headers}
    if url != "http://43.135.174.27:8080/responses":
        raise RuntimeError("diagnostic_request_url_mismatch")
    if body["model"] != "gpt-5.5":
        raise RuntimeError("diagnostic_model_alias_mismatch")
    if "authorization" in header_names or marker_name not in header_names:
        raise RuntimeError("diagnostic_auth_header_contract_mismatch")
    if (
        int(budget["maximum_network_calls"]) != 1
        or int(budget["maximum_transport_attempts"]) != 1
        or int(budget["retry_budget"]) != 0
        or int(body["max_output_tokens"]) != 128
    ):
        raise RuntimeError("diagnostic_budget_contract_mismatch")
    expected = authority["exact_request_contract"][
        "expected_exact_values"
    ]
    if not _fake_transport_preflight(body, expected):
        raise RuntimeError("diagnostic_fake_transport_preflight_failed")
    return {
        "status": "pass_zero_call_exact_diagnostic_preflight",
        "canary_id": CANARY_ID,
        "authority_decision_sha256": EXPECTED_AUTHORITY_SHA256,
        "request_digests": _request_digests(url, headers, body),
        "exact_request_url": url,
        "model": body["model"],
        "wire_api": "responses",
        "strict_json_schema": True,
        "credential_reads": 0,
        "credential_writes": 0,
        "authorization_or_bearer_header_present": False,
        "fixed_client_marker_header_present": True,
        "fake_transport_exact_wire_parse_and_value_validation_pass": True,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "transport_attempts": 0,
        "_url": url,
        "_headers": headers,
        "_body": body,
        "_expected": expected,
        "_timeout_seconds": int(provider["timeout_seconds"]),
    }


def _call_id_digest(raw: Mapping[str, Any], header_id: str) -> str:
    call_id = header_id or str(raw.get("id") or "")
    return (
        hashlib.sha256(call_id.encode("utf-8")).hexdigest()
        if call_id
        else ""
    )


def _sanitized_usage(raw: Mapping[str, Any]) -> dict[str, int]:
    usage = raw.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def _http_post_once(
    *,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers=dict(headers),
        method="POST",
    )
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            latency_ms = int((time.perf_counter() - started) * 1000)
            if len(payload) > MAX_RESPONSE_BYTES:
                return {
                    "transport_status": "response_too_large",
                    "http_status": int(response.status),
                    "latency_ms": latency_ms,
                    "transport_attempt_count": 1,
                }
            try:
                raw = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {
                    "transport_status": "invalid_json_response",
                    "http_status": int(response.status),
                    "latency_ms": latency_ms,
                    "transport_attempt_count": 1,
                }
            raw = raw if isinstance(raw, Mapping) else {}
            header_id = str(
                response.headers.get("x-request-id")
                or response.headers.get("request-id")
                or ""
            )
            return {
                "transport_status": "ok",
                "http_status": int(response.status),
                "latency_ms": latency_ms,
                "transport_attempt_count": 1,
                "call_id_digest": _call_id_digest(raw, header_id),
                "raw": raw,
            }
    except HTTPError as exc:
        return {
            "transport_status": "http_error",
            "http_status": int(exc.code),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "transport_attempt_count": 1,
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "transport_status": (
                f"transport_exception:{type(exc).__name__}"
            ),
            "http_status": 0,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "transport_attempt_count": 1,
        }


def _base_result(
    preflight_result: Mapping[str, Any],
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    raw = transport.get("raw")
    raw = raw if isinstance(raw, Mapping) else {}
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "recorded_at": _utc_now(),
        "work_item_id": WORK_ITEM_ID,
        "canary_id": CANARY_ID,
        "status": "terminal_failed_no_retry",
        "authority_decision_sha256": EXPECTED_AUTHORITY_SHA256,
        "request_digests": preflight_result["request_digests"],
        "provider_contract": {
            "provider_family": "self_hosted_Sub2API",
            "base_url": "http://43.135.174.27:8080",
            "endpoint_path": "/responses",
            "model": "gpt-5.5",
            "wire_api": "responses",
            "requires_openai_auth": False,
            "timeout_seconds": 30,
            "maximum_output_tokens": 128,
        },
        "transport_status": str(
            transport.get("transport_status") or "unknown"
        ),
        "http_status": int(transport.get("http_status") or 0),
        "response_status": str(raw.get("status") or ""),
        "call_id_digest": str(transport.get("call_id_digest") or ""),
        "usage": _sanitized_usage(raw),
        "latency_ms": int(transport.get("latency_ms") or 0),
        "transport_attempt_count": int(
            transport.get("transport_attempt_count") or 0
        ),
        "observed_counts": {
            "semantic_model_calls": 1,
            "provider_calls": 1,
            "network_calls": 1,
            "transport_attempts": int(
                transport.get("transport_attempt_count") or 0
            ),
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "chat_completions_calls": 0,
            "credential_reads": 0,
            "credential_writes": 0,
            "canonical_work_unit_attempt_run_writes": 0,
            "business_artifact_writes": 0,
        },
        "strict_schema_parse_pass": False,
        "local_exact_value_validation_pass": False,
        "content_free_output_shape": {},
        "raw_provider_response_persisted": False,
        "provider_output_text_persisted": False,
        "request_or_response_headers_persisted": False,
        "static_client_marker_value_persisted": False,
        "private_reasoning_persisted": False,
        "credential_persisted": False,
        "stack_trace_persisted": False,
        "result_is_diagnostic_only": True,
        "result_closes_RC_P36_074": False,
        "result_admits_T06_or_full_chain": False,
        "retry_count": 0,
        "provider_hopping_count": 0,
        "automatic_repair_count": 0,
    }


def _failure_class(
    transport: Mapping[str, Any],
    response_status: str,
) -> str:
    status = int(transport.get("http_status") or 0)
    transport_status = str(transport.get("transport_status") or "")
    if status in {400, 422}:
        return "strict_schema_request_rejected_or_unsupported"
    if status in {401, 403, 404, 429}:
        return "model_or_endpoint_access_rejected"
    if status >= 300:
        return "HTTP_status_not_success"
    if transport_status == "invalid_json_response":
        return "provider_envelope_invalid"
    if transport_status == "response_too_large":
        return "output_token_or_response_size_budget_exceeded"
    if transport_status != "ok":
        return "route_or_connection_failed"
    if response_status != "completed":
        return "response_not_completed"
    return "provider_envelope_invalid"


def _persist_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")


def execute(
    *,
    result_path: Path = RESULT_PATH,
    transport_fn: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    checked = preflight(result_path=result_path)
    url = str(checked.pop("_url"))
    headers = dict(checked.pop("_headers"))
    body = dict(checked.pop("_body"))
    expected = dict(checked.pop("_expected"))
    timeout_seconds = int(checked.pop("_timeout_seconds"))
    transport = (
        _http_post_once(
            url=url,
            headers=headers,
            body=body,
            timeout_seconds=timeout_seconds,
        )
        if transport_fn is None
        else transport_fn(
            url=url,
            headers=headers,
            body=body,
            timeout_seconds=timeout_seconds,
        )
    )
    if not isinstance(transport, Mapping):
        transport = {
            "transport_status": "provider_envelope_not_mapping",
            "http_status": 0,
            "transport_attempt_count": 1,
        }
    result = _base_result(checked, transport)
    if int(result["transport_attempt_count"]) != 1:
        result["failure_class"] = "transport_attempt_count_not_one"
        result["next_action"] = POST_RESULT_NEXT_ACTION
        _persist_once(result_path, result)
        return result
    raw = transport.get("raw")
    raw = raw if isinstance(raw, Mapping) else {}
    if (
        transport.get("transport_status") != "ok"
        or int(result["http_status"]) < 200
        or int(result["http_status"]) >= 300
        or result["response_status"] != "completed"
    ):
        result["failure_class"] = _failure_class(
            transport,
            str(result["response_status"]),
        )
        result["next_action"] = POST_RESULT_NEXT_ACTION
        _persist_once(result_path, result)
        return result
    parsed, failure = _parse_and_validate_exact(raw, expected)
    if failure is not None or parsed is None:
        result["failure_class"] = failure or "provider_envelope_invalid"
        result["next_action"] = POST_RESULT_NEXT_ACTION
        _persist_once(result_path, result)
        return result
    result.update(
        {
            "status": (
                "pass_exact_once_public_diagnostic_route_wire_"
                "strict_schema_compatible"
            ),
            "failure_class": None,
            "strict_schema_parse_pass": True,
            "local_exact_value_validation_pass": True,
            "content_free_output_shape": {
                "top_level_type": "object",
                "top_level_field_count": len(parsed),
                "top_level_fields": sorted(parsed),
                "all_values_exact_expected_enum_members": True,
            },
            "next_action": POST_RESULT_NEXT_ACTION,
        }
    )
    _persist_once(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Consume the exact-once identity and send one synthetic request.",
    )
    args = parser.parse_args()
    if args.execute:
        result = execute()
    else:
        result = preflight()
        for key in (
            "_url",
            "_headers",
            "_body",
            "_expected",
            "_timeout_seconds",
        ):
            result.pop(key, None)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(result["status"]).startswith("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
