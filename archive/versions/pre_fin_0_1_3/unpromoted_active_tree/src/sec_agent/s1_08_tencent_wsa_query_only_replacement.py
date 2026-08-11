from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import PROMOTION_STATUS


AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_authority_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_query_only_replacement_result_v1_0"
)
REQUEST_CAPTURE_SCHEMA = (
    "fin_ia_0_1_3_s1_08_tencent_wsa_query_only_safe_request_capture_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S1_08.tencent_wsa_query_only_replacement:v1"
RUN_SCOPE = "S1_08_PAID_BROAD_SEARCH_TENCENT_WSA_QUERY_ONLY_REPLACEMENT_DIAGNOSTIC"


class TencentWSAQueryOnlyReplacementError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def compile_query_only_request(query: Mapping[str, Any]) -> dict[str, str]:
    query_text = str(query.get("query_text") or "").strip()
    if not query_text:
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_query_text_missing"
        )
    if query.get("request_body_fields") != ["Query"]:
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_request_fields_invalid"
        )
    if query.get("optional_fields") != []:
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_optional_fields_forbidden"
        )
    forbidden = {
        "mode",
        "Mode",
        "site",
        "Site",
        "from_time",
        "FromTime",
        "to_time",
        "ToTime",
        "cnt",
        "Cnt",
        "industry",
        "Industry",
        "freshness",
        "Freshness",
        "deeplinks",
        "Deeplinks",
    }
    if forbidden.intersection(query):
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_optional_field_surface_forbidden"
        )
    return {"Query": query_text}


def build_safe_request_capture(
    *, endpoint: str, request_body: Mapping[str, Any]
) -> dict[str, Any]:
    if set(request_body) != {"Query"}:
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_compiled_body_not_exact"
        )
    return {
        "schema_version": REQUEST_CAPTURE_SCHEMA,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "protocol": "https",
        "method": "POST",
        "action": "SearchPro",
        "version": "2025-05-08",
        "region": "",
        "request_body": dict(request_body),
        "request_body_fields": ["Query"],
        "optional_fields_omitted": [
            "Mode",
            "Site",
            "FromTime",
            "ToTime",
            "Cnt",
            "Industry",
            "Freshness",
            "Deeplinks",
        ],
        "credential_fields_present": False,
        "authorization_or_signature_present": False,
        "capture_before_transport": True,
    }


def load_query_only_replacement_authority(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    body = dict(payload)
    digest = body.pop("authority_digest", None)
    if (
        body.get("schema_version") != AUTHORITY_SCHEMA
        or body.get("contract_ref") != CONTRACT_REF
        or body.get("status") != "issued_unconsumed"
        or body.get("authorized_scope") != RUN_SCOPE
        or digest != canonical_digest(body)
    ):
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_authority_identity_invalid"
        )
    execution = body.get("execution_contract") or {}
    if (
        execution.get("provider_call_ceiling") != 1
        or execution.get("network_call_ceiling") != 1
        or execution.get("retry_ceiling") != 0
        or execution.get("model_call_ceiling") != 0
        or execution.get("document_fetch_ceiling") != 0
        or execution.get("evidence_promotion_allowed") is not False
        or execution.get("production_capability_claim_allowed") is not False
    ):
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_authority_boundary_invalid"
        )
    if body.get("predecessor_attempt_id") != (
        "fin013-s1-08-tencent-wsa-single-call-diagnostic-r1"
    ):
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_predecessor_invalid"
        )
    compile_query_only_request(body.get("query") or {})
    return payload


def build_query_only_terminal_result(
    *,
    admission_id: str,
    source_commit: str,
    status: str,
    terminal_code: str,
    request_capture: Mapping[str, Any],
    provider_projection: Mapping[str, Any] | None,
    network_call_count: int,
    elapsed_ms: int,
    sdk_version: str,
    failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if set((request_capture.get("request_body") or {}).keys()) != {"Query"}:
        raise TencentWSAQueryOnlyReplacementError(
            "tencent_wsa_query_only_terminal_request_not_exact"
        )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_id": admission_id,
        "predecessor_attempt_id": (
            "fin013-s1-08-tencent-wsa-single-call-diagnostic-r1"
        ),
        "admission_consumed": bool(network_call_count),
        "source_commit": source_commit,
        "status": status,
        "terminal_code": terminal_code,
        "request_capture": dict(request_capture),
        "provider_projection": dict(provider_projection or {}),
        "failure": dict(failure or {}),
        "observed_counts": {
            "provider_calls": network_call_count,
            "network_calls": network_call_count,
            "retry_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
        },
        "elapsed_ms": int(elapsed_ms),
        "sdk": {"package": "tencentcloud-sdk-python", "version": sdk_version},
        "capability_boundary": {
            "promotion_status": PROMOTION_STATUS,
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
            "production_capability_claim_allowed": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}
