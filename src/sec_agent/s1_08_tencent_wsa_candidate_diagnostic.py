from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sec_agent.canonical_runtime.models import canonical_digest


PROFILE_SCHEMA = "fin_ia_0_1_3_s1_08_tencent_wsa_candidate_profile_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_08_tencent_wsa_single_call_diagnostic_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.tencent_wsa_candidate_paid_broad_search:v1"
PROMOTION_STATUS = "candidate_locator_diagnostic_only"
_TRACKING_QUERY_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "source",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "key",
        "password",
        "secret",
        "sig",
        "signature",
        "token",
    }
)


class TencentWSADiagnosticError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_tencent_wsa_candidate_profile(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != PROFILE_SCHEMA
        or payload.get("contract_ref") != CONTRACT_REF
        or payload.get("provider_id") != "tencent_cloud_wsa_searchpro_candidate_v1"
    ):
        raise TencentWSADiagnosticError("tencent_wsa_profile_identity_invalid")
    api = payload.get("api_contract") or {}
    if (
        api.get("endpoint") != "wsa.tencentcloudapi.com"
        or api.get("protocol") != "https"
        or api.get("action") != "SearchPro"
        or api.get("version") != "2025-05-08"
        or api.get("region_required") is not False
    ):
        raise TencentWSADiagnosticError("tencent_wsa_profile_api_contract_invalid")
    auth = payload.get("authentication") or {}
    if (
        auth.get("mode") != "tencent_cloud_api3_ak_sk_signature"
        or auth.get("credential_persistence_allowed") is not False
        or auth.get("credential_logging_allowed") is not False
    ):
        raise TencentWSADiagnosticError("tencent_wsa_profile_auth_boundary_invalid")
    budget = payload.get("diagnostic_budget") or {}
    if (
        budget.get("provider_call_ceiling") != 1
        or budget.get("retry_ceiling") != 0
        or budget.get("model_call_ceiling") != 0
        or budget.get("result_ceiling") != 10
    ):
        raise TencentWSADiagnosticError("tencent_wsa_profile_budget_invalid")
    boundary = payload.get("capability_boundary") or {}
    if (
        boundary.get("promotion_status") != PROMOTION_STATUS
        or boundary.get("evidence_promotion_allowed") is not False
        or boundary.get("writer_citable") is not False
        or boundary.get("financial_fact_authority") is not False
        or boundary.get("production_capability_claim_allowed") is not False
        or boundary.get("numeric_authority") != "none"
    ):
        raise TencentWSADiagnosticError("tencent_wsa_profile_false_promotion")
    return payload


def canonicalize_candidate_locator(raw_url: str) -> str:
    parts = urlsplit(str(raw_url).strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise TencentWSADiagnosticError("tencent_wsa_locator_invalid")
    if parts.username or parts.password:
        raise TencentWSADiagnosticError("tencent_wsa_locator_credentials_forbidden")
    host = parts.hostname.lower().rstrip(".")
    port = parts.port
    if port and not (
        (parts.scheme.lower() == "http" and port == 80)
        or (parts.scheme.lower() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in _TRACKING_QUERY_KEYS:
            continue
        if lowered in _SENSITIVE_QUERY_KEYS:
            continue
        query.append((key, value))
    path = parts.path or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            host,
            path,
            urlencode(sorted(query)),
            "",
        )
    )


def normalize_search_pro_response(
    payload: Mapping[str, Any], *, result_ceiling: int = 10
) -> dict[str, Any]:
    response = payload.get("Response") if isinstance(payload.get("Response"), Mapping) else payload
    if not isinstance(response, Mapping):
        raise TencentWSADiagnosticError("tencent_wsa_response_schema_invalid")
    pages = response.get("Pages")
    if not isinstance(pages, list):
        raise TencentWSADiagnosticError("tencent_wsa_response_pages_missing")
    if result_ceiling <= 0 or result_ceiling > 10:
        raise TencentWSADiagnosticError("tencent_wsa_result_ceiling_invalid")

    locators_by_url: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for provider_rank, raw_page in enumerate(pages[:result_ceiling], start=1):
        try:
            page = json.loads(raw_page) if isinstance(raw_page, str) else raw_page
        except json.JSONDecodeError:
            rejected.append({"provider_rank": provider_rank, "code": "page_invalid_json"})
            continue
        if not isinstance(page, Mapping):
            rejected.append({"provider_rank": provider_rank, "code": "page_not_object"})
            continue
        try:
            canonical_url = canonicalize_candidate_locator(str(page.get("url") or ""))
        except TencentWSADiagnosticError as exc:
            rejected.append({"provider_rank": provider_rank, "code": exc.code})
            continue
        title = str(page.get("title") or "").strip()
        if not title:
            rejected.append({"provider_rank": provider_rank, "code": "page_title_missing"})
            continue
        score = page.get("score")
        normalized_score = float(score) if isinstance(score, (int, float)) else None
        locator_body = {
            "provider_rank": provider_rank,
            "canonical_url": canonical_url,
            "source_domain": urlsplit(canonical_url).hostname or "",
            "title": title,
            "published_at_raw": str(page.get("date") or "").strip() or None,
            "passage": str(page.get("passage") or "").strip(),
            "site": str(page.get("site") or "").strip() or None,
            "provider_score": normalized_score,
            "promotion_status": PROMOTION_STATUS,
            "evidence_promotion_allowed": False,
            "writer_citable": False,
            "financial_fact_authority": False,
            "numeric_authority": "none",
        }
        locator = {**locator_body, "locator_digest": canonical_digest(locator_body)}
        existing = locators_by_url.get(canonical_url)
        if existing is None or provider_rank < int(existing["provider_rank"]):
            locators_by_url[canonical_url] = locator

    locators = sorted(locators_by_url.values(), key=lambda item: int(item["provider_rank"]))
    return {
        "query": str(response.get("Query") or ""),
        "provider_version": str(response.get("Version") or "") or None,
        "provider_message": str(response.get("Msg") or "") or None,
        "request_id": str(response.get("RequestId") or "") or None,
        "raw_page_count": len(pages),
        "normalized_unique_locator_count": len(locators),
        "published_date_count": sum(
            1 for locator in locators if locator.get("published_at_raw")
        ),
        "locators": locators,
        "rejections": rejected,
        "locator_bundle_digest": canonical_digest(locators),
    }


def build_terminal_result(
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
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "admission_id": admission_id,
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


def redact_runtime_value(value: Any, secrets: Sequence[str]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): redact_runtime_value(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_runtime_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [redact_runtime_value(item, secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value
