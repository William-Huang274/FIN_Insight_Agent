from __future__ import annotations

from copy import deepcopy
from datetime import date
import ipaddress
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .query_plan import canonical_digest


EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_external_source_ladder_plan_v1_0"
)
EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION = (
    "fin_ia_s1_external_locator_bundle_v1_0"
)
EXTERNAL_FETCH_SHORTLIST_SCHEMA_VERSION = (
    "fin_ia_s1_external_fetch_shortlist_v1_0"
)
SAFE_PROVIDER_REQUEST_SCHEMA_VERSION = (
    "fin_ia_s1_external_provider_safe_request_v1_0"
)

_TIERS = {
    "official_subject_regulator_customer_supplier",
    "industry_association_market_tracking",
    "product_procurement_channel_deployment",
    "trusted_context_analyst_counterevidence",
}
_TRACKING_KEYS = {
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
_SENSITIVE_KEYS = {
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
_SAFE_SITE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class ExternalSourceLadderError(ValueError):
    """An external locator or fetch plan lost its case, scope, or safety boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ExternalSourceLadderError(code)


def _valid_date(value: object) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def _validated_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop(field, ""))
    _require(digest == canonical_digest(body), code)


def validate_external_source_ladder_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _validated_digest(value, "plan_digest", "external_ladder_plan_digest_invalid")
    budget = value.get("execution_budget")
    units = value.get("query_units")
    source_registry = value.get("source_domain_registry")
    token_basis = value.get("token_budget_basis")
    _require(
        value.get("schema_version") == EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION
        and value.get("status") == "approved_exact_once_external_locator_and_original_capture_plan"
        and str(value.get("plan_id") or "")
        and str(value.get("case_key") or "").upper() == "DELL"
        and _valid_date(value.get("research_as_of"))
        and isinstance(budget, Mapping)
        and int(budget.get("provider_call_ceiling") or 0) > 0
        and int(budget.get("original_fetch_ceiling") or 0) > 0
        and int(budget.get("original_fetch_ceiling_per_query") or 0) > 0
        and int(budget.get("original_fetch_ceiling_per_domain") or 0) > 0
        and int(budget.get("result_ceiling_per_call") or 0) == 10
        and budget.get("retry_ceiling") == 0
        and budget.get("model_call_ceiling") == 0
        and isinstance(token_basis, Mapping)
        and token_basis.get("model_tokens") == 0
        and token_basis.get("cost_and_latency_are_secondary_constraints") is True
        and str(token_basis.get("node_purpose") or "")
        and str(token_basis.get("input_scale_basis") or "")
        and isinstance(token_basis.get("required_outputs"), list)
        and token_basis["required_outputs"]
        and str(token_basis.get("materiality_and_quality_risk") or "")
        and str(token_basis.get("comparable_run_evidence") or "")
        and str(token_basis.get("stop_and_truncation_behavior") or "")
        and isinstance(units, list)
        and units
        and len(units) <= int(budget["provider_call_ceiling"])
        and isinstance(source_registry, list)
        and source_registry,
        "external_ladder_plan_shape_invalid",
    )
    unit_ids: set[str] = set()
    propositions: set[str] = set()
    for unit in units:
        _require(isinstance(unit, Mapping), "external_ladder_query_unit_invalid")
        unit_id = str(unit.get("query_unit_id") or "")
        proposition_id = str(unit.get("proposition_id") or "")
        query = str(unit.get("query") or "").strip()
        site = str(unit.get("site") or "").strip().lower()
        _require(
            unit_id
            and unit_id not in unit_ids
            and proposition_id.startswith("DELL-PROP-")
            and str(unit.get("tier_id") or "") in _TIERS
            and query
            and len(query) <= 600
            and isinstance(unit.get("expected_output_ids"), list)
            and unit["expected_output_ids"]
            and isinstance(unit.get("relationship_directions"), list)
            and unit["relationship_directions"]
            and isinstance(unit.get("speaker_or_source_targets"), list)
            and unit["speaker_or_source_targets"]
            and (not site or _SAFE_SITE.fullmatch(site) is not None),
            "external_ladder_query_unit_invalid",
        )
        unit_ids.add(unit_id)
        propositions.add(proposition_id)
    _require(
        propositions
        == {
            "DELL-PROP-PRICE-CONFIGURATION",
            "DELL-PROP-UNIT-VOLUME",
            "DELL-PROP-PVM-BRIDGE",
            "DELL-PROP-CUSTOMER-DEMAND",
            "DELL-PROP-SUPPLY-CHAIN",
            "DELL-PROP-VALUE-POOL",
            "DELL-PROP-COUNTEREVIDENCE-WWC",
        },
        "external_ladder_proposition_coverage_invalid",
    )
    registry_hosts: set[str] = set()
    for row in source_registry:
        _require(isinstance(row, Mapping), "external_ladder_source_registry_invalid")
        host = str(row.get("host") or "").strip().lower()
        _require(
            _SAFE_SITE.fullmatch(host) is not None
            and host not in registry_hosts
            and str(row.get("speaker_entity") or "")
            and str(row.get("source_class") or "")
            and str(row.get("source_role") or "")
            and isinstance(row.get("relationship_directions"), list)
            and row["relationship_directions"],
            "external_ladder_source_registry_invalid",
        )
        registry_hosts.add(host)
    return value


def compile_safe_provider_request(query_unit: Mapping[str, Any]) -> dict[str, Any]:
    query = str(query_unit.get("query") or "").strip()
    site = str(query_unit.get("site") or "").strip().lower()
    _require(
        query
        and len(query) <= 600
        and (not site or _SAFE_SITE.fullmatch(site) is not None),
        "external_ladder_provider_request_invalid",
    )
    request_body: dict[str, Any] = {"Query": query}
    if site:
        request_body["Site"] = site
    body = {
        "schema_version": SAFE_PROVIDER_REQUEST_SCHEMA_VERSION,
        "provider_id": "tencent_wsa_searchpro_standard_locator_v1",
        "endpoint": "wsa.tencentcloudapi.com",
        "protocol": "https",
        "action": "SearchPro",
        "version": "2025-05-08",
        "region": "",
        "query_unit_id": str(query_unit.get("query_unit_id") or ""),
        "request_body": request_body,
        "credential_fields_present": False,
        "authorization_or_signature_present": False,
        "capture_before_transport": True,
        "provider_result_is_locator_only": True,
    }
    return {**body, "request_digest": canonical_digest(body)}


def canonicalize_external_url(raw_url: str) -> str:
    parts = urlsplit(str(raw_url).strip())
    _require(
        parts.scheme.lower() == "https"
        and bool(parts.hostname)
        and not parts.username
        and not parts.password,
        "external_ladder_locator_url_invalid",
    )
    host = str(parts.hostname).lower().rstrip(".")
    _require(
        host not in {"localhost", "localhost.localdomain"}
        and not host.endswith(".local"),
        "external_ladder_locator_host_forbidden",
    )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    _require(
        address is None
        or not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ),
        "external_ladder_locator_host_forbidden",
    )
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.casefold()
        if lowered.startswith("utm_") or lowered in _TRACKING_KEYS:
            continue
        if lowered in _SENSITIVE_KEYS:
            continue
        query.append((key, value))
    netloc = host
    if parts.port and parts.port != 443:
        netloc = f"{host}:{parts.port}"
    return urlunsplit(("https", netloc, parts.path or "/", urlencode(sorted(query)), ""))


def normalize_tencent_search_response(
    *,
    raw_payload: Mapping[str, Any],
    query_unit: Mapping[str, Any],
    safe_request: Mapping[str, Any],
    result_ceiling: int = 10,
) -> dict[str, Any]:
    _validated_digest(safe_request, "request_digest", "external_ladder_safe_request_digest_invalid")
    response = (
        raw_payload.get("Response")
        if isinstance(raw_payload.get("Response"), Mapping)
        else raw_payload
    )
    _require(isinstance(response, Mapping), "external_ladder_provider_response_invalid")
    pages = response.get("Pages")
    _require(isinstance(pages, list), "external_ladder_provider_pages_missing")
    locators_by_url: dict[str, dict[str, Any]] = {}
    rejections: list[dict[str, Any]] = []
    for provider_rank, raw_page in enumerate(pages[:result_ceiling], start=1):
        try:
            page = json.loads(raw_page) if isinstance(raw_page, str) else raw_page
        except json.JSONDecodeError:
            rejections.append({"provider_rank": provider_rank, "code": "page_invalid_json"})
            continue
        if not isinstance(page, Mapping):
            rejections.append({"provider_rank": provider_rank, "code": "page_not_object"})
            continue
        try:
            url = canonicalize_external_url(str(page.get("url") or ""))
        except ExternalSourceLadderError as exc:
            rejections.append({"provider_rank": provider_rank, "code": str(exc)})
            continue
        title = str(page.get("title") or "").strip()
        if not title:
            rejections.append({"provider_rank": provider_rank, "code": "page_title_missing"})
            continue
        locator_body = {
            "query_unit_id": str(query_unit.get("query_unit_id") or ""),
            "proposition_id": str(query_unit.get("proposition_id") or ""),
            "tier_id": str(query_unit.get("tier_id") or ""),
            "expected_output_ids": list(query_unit.get("expected_output_ids") or []),
            "relationship_directions": list(query_unit.get("relationship_directions") or []),
            "provider_rank": provider_rank,
            "canonical_url": url,
            "source_domain": urlsplit(url).hostname or "",
            "title": title,
            "passage": str(page.get("passage") or "").strip(),
            "provider_date_telemetry": str(page.get("date") or "").strip() or None,
            "provider_score": (
                float(page["score"])
                if isinstance(page.get("score"), (int, float))
                else None
            ),
            "provider_result_is_locator_only": True,
            "candidate_not_evidence": True,
            "writer_citable": False,
            "numeric_authority": "none",
        }
        locator = {**locator_body, "locator_digest": canonical_digest(locator_body)}
        current = locators_by_url.get(url)
        if current is None or provider_rank < int(current["provider_rank"]):
            locators_by_url[url] = locator
    body = {
        "schema_version": EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION,
        "query_unit_id": str(query_unit.get("query_unit_id") or ""),
        "safe_request_digest": str(safe_request.get("request_digest") or ""),
        "provider_request_id": str(response.get("RequestId") or "") or None,
        "provider_version": str(response.get("Version") or "") or None,
        "provider_message": str(response.get("Msg") or "") or None,
        "locators": sorted(
            locators_by_url.values(), key=lambda row: int(row["provider_rank"])
        ),
        "rejections": rejections,
        "raw_page_count": len(pages),
        "provider_date_is_authority": False,
        "evidence_promotion_allowed": False,
    }
    return {**body, "bundle_digest": canonical_digest(body)}


def _registry_match(host: str, registry: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    exact = [row for row in registry if str(row.get("host") or "").lower() == host]
    if exact:
        return exact[0]
    suffix = [
        row
        for row in registry
        if host.endswith("." + str(row.get("host") or "").lower())
    ]
    if not suffix:
        return None
    return max(suffix, key=lambda row: len(str(row.get("host") or "")))


def build_external_fetch_shortlist(
    *,
    plan: Mapping[str, Any],
    locator_bundles: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validated = validate_external_source_ladder_plan(plan)
    by_unit = {str(row["query_unit_id"]): row for row in validated["query_units"]}
    _require(
        len(locator_bundles) == len(by_unit)
        and {str(row.get("query_unit_id") or "") for row in locator_bundles}
        == set(by_unit),
        "external_ladder_locator_coverage_invalid",
    )
    registry = list(validated["source_domain_registry"])
    per_unit = int(validated["execution_budget"]["original_fetch_ceiling_per_query"])
    per_domain = int(validated["execution_budget"]["original_fetch_ceiling_per_domain"])
    global_ceiling = int(validated["execution_budget"]["original_fetch_ceiling"])
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    domain_counts: dict[str, int] = {}
    for bundle in sorted(locator_bundles, key=lambda row: str(row["query_unit_id"])):
        _validated_digest(bundle, "bundle_digest", "external_ladder_locator_digest_invalid")
        unit_id = str(bundle["query_unit_id"])
        unit_selected = 0
        for locator in bundle.get("locators") or ():
            url = str(locator["canonical_url"])
            host = str(locator["source_domain"]).lower()
            registry_row = _registry_match(host, registry)
            if registry_row is None:
                rejected.append(
                    {
                        "query_unit_id": unit_id,
                        "canonical_url": url,
                        "reason": "source_domain_not_in_reviewed_registry",
                    }
                )
                continue
            if url in seen_urls:
                rejected.append(
                    {
                        "query_unit_id": unit_id,
                        "canonical_url": url,
                        "reason": "duplicate_locator_already_selected",
                    }
                )
                continue
            if domain_counts.get(host, 0) >= per_domain:
                rejected.append(
                    {
                        "query_unit_id": unit_id,
                        "canonical_url": url,
                        "reason": "per_domain_fetch_ceiling_reached",
                    }
                )
                continue
            if unit_selected >= per_unit or len(selected) >= global_ceiling:
                rejected.append(
                    {
                        "query_unit_id": unit_id,
                        "canonical_url": url,
                        "reason": "fair_fetch_ceiling_reached",
                    }
                )
                continue
            selected.append(
                {
                    **dict(locator),
                    "source_registry": deepcopy(dict(registry_row)),
                    "fetch_status": "approved_for_original_capture",
                }
            )
            seen_urls.add(url)
            domain_counts[host] = domain_counts.get(host, 0) + 1
            unit_selected += 1
    body = {
        "schema_version": EXTERNAL_FETCH_SHORTLIST_SCHEMA_VERSION,
        "case_key": str(validated["case_key"]).upper(),
        "research_as_of": str(validated["research_as_of"]),
        "plan_digest": str(validated["plan_digest"]),
        "selected": selected,
        "rejected": rejected,
        "summary": {
            "locator_count": sum(
                len(row.get("locators") or ()) for row in locator_bundles
            ),
            "selected_original_fetch_count": len(selected),
            "rejected_locator_count": len(rejected),
            "selected_proposition_count": len(
                {str(row["proposition_id"]) for row in selected}
            ),
            "selected_tier_count": len({str(row["tier_id"]) for row in selected}),
            "selected_domain_count": len(domain_counts),
        },
        "authority": {
            "provider_result_is_locator_only": True,
            "original_capture_required_before_parse": True,
            "candidate_decision_required": True,
            "evidence_promotion_allowed": False,
        },
    }
    return {**body, "shortlist_digest": canonical_digest(body)}


__all__ = [
    "EXTERNAL_FETCH_SHORTLIST_SCHEMA_VERSION",
    "EXTERNAL_LOCATOR_BUNDLE_SCHEMA_VERSION",
    "EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION",
    "SAFE_PROVIDER_REQUEST_SCHEMA_VERSION",
    "ExternalSourceLadderError",
    "build_external_fetch_shortlist",
    "canonicalize_external_url",
    "compile_safe_provider_request",
    "normalize_tencent_search_response",
    "validate_external_source_ladder_plan",
]
