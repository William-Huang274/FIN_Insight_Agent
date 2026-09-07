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
EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION_V1_1 = (
    "fin_ia_s1_external_source_ladder_plan_v1_1"
)
EXTERNAL_SOURCE_LADDER_SUCCESSOR_SPEC_SCHEMA_VERSION = (
    "fin_ia_s1_external_source_ladder_successor_spec_v1_0"
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
_PROPOSITIONS = {
    "DELL-PROP-PRICE-CONFIGURATION",
    "DELL-PROP-UNIT-VOLUME",
    "DELL-PROP-PVM-BRIDGE",
    "DELL-PROP-CUSTOMER-DEMAND",
    "DELL-PROP-SUPPLY-CHAIN",
    "DELL-PROP-VALUE-POOL",
    "DELL-PROP-COUNTEREVIDENCE-WWC",
}


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
    schema_version = str(value.get("schema_version") or "")
    expected_status = {
        EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION: (
            "approved_exact_once_external_locator_and_original_capture_plan"
        ),
        EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION_V1_1: (
            "approved_bounded_external_locator_replay_and_residual_successor_plan"
        ),
    }.get(schema_version)
    provider_units = [
        row
        for row in units or ()
        if str(row.get("execution_mode") or "provider") == "provider"
    ]
    _require(
        expected_status is not None
        and value.get("status") == expected_status
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
        and len(provider_units) <= int(budget["provider_call_ceiling"])
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
            and (not site or _SAFE_SITE.fullmatch(site) is not None)
            and (
                schema_version == EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION
                or str(unit.get("execution_mode") or "") in {"replay", "provider"}
            ),
            "external_ladder_query_unit_invalid",
        )
        unit_ids.add(unit_id)
        propositions.add(proposition_id)
    _require(
        propositions == _PROPOSITIONS,
        "external_ladder_proposition_coverage_invalid",
    )
    registry_hosts: set[str] = set()
    for row in source_registry:
        _require(isinstance(row, Mapping), "external_ladder_source_registry_invalid")
        host = str(row.get("host") or "").strip().lower()
        allowed_tiers = row.get("allowed_ladder_tiers")
        safe_aliases = row.get("safe_host_aliases")
        _require(
            _SAFE_SITE.fullmatch(host) is not None
            and host not in registry_hosts
            and str(row.get("speaker_entity") or "")
            and str(row.get("source_class") or "")
            and str(row.get("source_role") or "")
            and isinstance(row.get("relationship_directions"), list)
            and row["relationship_directions"]
            and (
                schema_version == EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION
                or (
                    str(row.get("source_family_id") or "") == host
                    and isinstance(allowed_tiers, list)
                    and bool(allowed_tiers)
                    and set(str(item) for item in allowed_tiers).issubset(_TIERS)
                    and isinstance(safe_aliases, list)
                    and all(
                        _SAFE_SITE.fullmatch(str(alias).lower()) is not None
                        for alias in safe_aliases
                    )
                )
            ),
            "external_ladder_source_registry_invalid",
        )
        registry_hosts.add(host)
    if schema_version == EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION_V1_1:
        policies = value.get("candidate_selection_policy")
        _require(
            isinstance(policies, Mapping)
            and set(str(key) for key in policies) == _PROPOSITIONS,
            "external_ladder_candidate_policy_invalid",
        )
        for proposition_id, raw in policies.items():
            _require(
                proposition_id in _PROPOSITIONS
                and isinstance(raw, Mapping)
                and isinstance(raw.get("scope_anchor_terms"), list)
                and bool(raw["scope_anchor_terms"])
                and isinstance(raw.get("material_signal_terms"), list)
                and bool(raw["material_signal_terms"])
                and int(raw.get("minimum_scope_anchor_hits") or 0) >= 1
                and int(raw.get("minimum_material_signal_hits") or 0) >= 1
                and 0 <= int(raw.get("context_blocks_before") or 0) <= 2
                and 0 <= int(raw.get("context_blocks_after") or 0) <= 2,
                "external_ladder_candidate_policy_invalid",
            )
    return value


def validate_external_source_ladder_successor_spec(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _validated_digest(value, "spec_digest", "external_ladder_successor_spec_digest_invalid")
    predecessor = value.get("predecessor_binding")
    budget = value.get("execution_budget")
    new_units = value.get("new_query_units")
    role_tiers = value.get("source_role_tier_policy")
    additions = value.get("source_registry_additions")
    candidate_policy = value.get("candidate_selection_policy")
    _require(
        value.get("schema_version")
        == EXTERNAL_SOURCE_LADDER_SUCCESSOR_SPEC_SCHEMA_VERSION
        and value.get("status")
        == "approved_bounded_replay_and_residual_external_successor"
        and str(value.get("successor_id") or "")
        and str(value.get("case_key") or "").upper() == "DELL"
        and _valid_date(value.get("research_as_of"))
        and isinstance(predecessor, Mapping)
        and str(predecessor.get("plan_ref") or "")
        and len(str(predecessor.get("plan_sha256") or "")) == 64
        and len(str(predecessor.get("plan_digest") or "")) == 64
        and str(predecessor.get("public_result_ref") or "")
        and len(str(predecessor.get("public_result_sha256") or "")) == 64
        and len(str(predecessor.get("public_result_digest") or "")) == 64
        and str(predecessor.get("private_result_ref") or "")
        and len(str(predecessor.get("private_result_sha256") or "")) == 64
        and isinstance(value.get("replay_query_unit_ids"), list)
        and bool(value["replay_query_unit_ids"])
        and len(value["replay_query_unit_ids"])
        == len(set(str(item) for item in value["replay_query_unit_ids"]))
        and isinstance(budget, Mapping)
        and int(budget.get("provider_call_ceiling") or 0) >= len(new_units or ())
        and int(budget.get("original_fetch_ceiling") or 0) > 0
        and int(budget.get("original_fetch_ceiling_per_query") or 0) > 0
        and int(budget.get("original_fetch_ceiling_per_domain") or 0) > 0
        and int(budget.get("result_ceiling_per_call") or 0) == 10
        and budget.get("retry_ceiling") == 0
        and budget.get("model_call_ceiling") == 0
        and isinstance(new_units, list)
        and bool(new_units)
        and isinstance(role_tiers, Mapping)
        and bool(role_tiers)
        and all(
            isinstance(tiers, list)
            and bool(tiers)
            and set(str(tier) for tier in tiers).issubset(_TIERS)
            for tiers in role_tiers.values()
        )
        and isinstance(additions, list)
        and isinstance(candidate_policy, Mapping)
        and set(str(key) for key in candidate_policy) == _PROPOSITIONS,
        "external_ladder_successor_spec_shape_invalid",
    )
    return value


def compile_external_source_ladder_successor_plan(
    *,
    base_plan: Mapping[str, Any],
    successor_spec: Mapping[str, Any],
) -> dict[str, Any]:
    base = validate_external_source_ladder_plan(base_plan)
    spec = validate_external_source_ladder_successor_spec(successor_spec)
    predecessor = spec["predecessor_binding"]
    base_units = {str(row["query_unit_id"]): deepcopy(dict(row)) for row in base["query_units"]}
    _require(
        base.get("schema_version") == EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION
        and str(base.get("case_key") or "").upper() == "DELL"
        and base.get("research_as_of") == spec.get("research_as_of")
        and base.get("plan_digest") == predecessor.get("plan_digest")
        and set(str(item) for item in spec["replay_query_unit_ids"]) == set(base_units),
        "external_ladder_successor_predecessor_mismatch",
    )
    combined_units: list[dict[str, Any]] = []
    for unit_id in spec["replay_query_unit_ids"]:
        combined_units.append({**base_units[str(unit_id)], "execution_mode": "replay"})
    seen_units = set(base_units)
    for raw in spec["new_query_units"]:
        _require(isinstance(raw, Mapping), "external_ladder_successor_query_unit_invalid")
        unit = deepcopy(dict(raw))
        unit_id = str(unit.get("query_unit_id") or "")
        _require(
            unit_id and unit_id not in seen_units,
            "external_ladder_successor_query_unit_invalid",
        )
        unit["execution_mode"] = "provider"
        combined_units.append(unit)
        seen_units.add(unit_id)

    registry: list[dict[str, Any]] = []
    registry_hosts: set[str] = set()
    role_tiers = spec["source_role_tier_policy"]
    for raw in [*base["source_domain_registry"], *spec["source_registry_additions"]]:
        row = deepcopy(dict(raw))
        host = str(row.get("host") or "").lower()
        role = str(row.get("source_role") or "")
        _require(
            host not in registry_hosts and role in role_tiers,
            "external_ladder_successor_source_registry_invalid",
        )
        aliases = {str(value).lower() for value in row.get("safe_host_aliases") or ()}
        if host.count(".") == 1:
            aliases.add("www." + host)
        aliases.discard(host)
        row.update(
            {
                "host": host,
                "source_family_id": host,
                "safe_host_aliases": sorted(aliases),
                "allowed_ladder_tiers": sorted(
                    {str(value) for value in role_tiers[role]}
                ),
            }
        )
        registry.append(row)
        registry_hosts.add(host)

    body = {
        "schema_version": EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION_V1_1,
        "plan_id": str(spec["successor_id"]),
        "status": "approved_bounded_external_locator_replay_and_residual_successor_plan",
        "recorded_at": str(spec.get("recorded_at") or ""),
        "case_key": "DELL",
        "research_as_of": str(spec["research_as_of"]),
        "program_ref": base.get("program_ref"),
        "internal_result_ref": base.get("internal_result_ref"),
        "source_use_policy_ref": base.get("source_use_policy_ref"),
        "predecessor_binding": deepcopy(dict(predecessor)),
        "purpose": str(spec.get("purpose") or ""),
        "execution_budget": deepcopy(dict(spec["execution_budget"])),
        "token_budget_basis": deepcopy(dict(spec["token_budget_basis"])),
        "query_units": combined_units,
        "source_domain_registry": registry,
        "candidate_selection_policy": deepcopy(dict(spec["candidate_selection_policy"])),
        "authority": deepcopy(dict(spec.get("authority") or {})),
    }
    return validate_external_source_ladder_plan(
        {**body, "plan_digest": canonical_digest(body)}
    )


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
    # Tencent WSA Standard represents a successful zero-result response as
    # `Pages: null` (with a normal RequestId/Version envelope).  Preserve the
    # distinction between that state and a malformed response where `Pages`
    # is absent, or an explicit provider error is present.
    if "Pages" in response and pages is None:
        _require(
            not response.get("Error")
            and bool(str(response.get("RequestId") or "").strip()),
            "external_ladder_provider_zero_result_envelope_invalid",
        )
        pages = []
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


def source_family_allowed_hosts(
    registry_row: Mapping[str, Any],
    *,
    observed_host: str | None = None,
) -> list[str]:
    host = str(registry_row.get("host") or "").strip().lower()
    _require(_SAFE_SITE.fullmatch(host) is not None, "external_ladder_source_family_invalid")
    allowed = {host}
    for alias in registry_row.get("safe_host_aliases") or ():
        normalized = str(alias).strip().lower()
        _require(
            _SAFE_SITE.fullmatch(normalized) is not None,
            "external_ladder_source_family_invalid",
        )
        allowed.add(normalized)
    if observed_host:
        normalized = str(observed_host).strip().lower()
        _require(
            normalized == host or normalized.endswith("." + host),
            "external_ladder_source_family_observed_host_invalid",
        )
        allowed.add(normalized)
    return sorted(allowed)


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
        unit = by_unit[unit_id]
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
            allowed_tiers = {
                str(value) for value in registry_row.get("allowed_ladder_tiers") or ()
            }
            if allowed_tiers and str(unit["tier_id"]) not in allowed_tiers:
                rejected.append(
                    {
                        "query_unit_id": unit_id,
                        "canonical_url": url,
                        "reason": "source_tier_not_allowed_for_query_tier",
                        "query_tier_id": str(unit["tier_id"]),
                        "source_allowed_tiers": sorted(allowed_tiers),
                        "source_family_id": str(
                            registry_row.get("source_family_id")
                            or registry_row.get("host")
                            or ""
                        ),
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
            source_family_id = str(
                registry_row.get("source_family_id")
                or registry_row.get("host")
                or host
            ).lower()
            if domain_counts.get(source_family_id, 0) >= per_domain:
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
                    "source_family_id": source_family_id,
                    "fetch_status": "approved_for_original_capture",
                }
            )
            seen_urls.add(url)
            domain_counts[source_family_id] = domain_counts.get(source_family_id, 0) + 1
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
            "selected_source_family_count": len(domain_counts),
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
    "EXTERNAL_SOURCE_LADDER_PLAN_SCHEMA_VERSION_V1_1",
    "EXTERNAL_SOURCE_LADDER_SUCCESSOR_SPEC_SCHEMA_VERSION",
    "SAFE_PROVIDER_REQUEST_SCHEMA_VERSION",
    "ExternalSourceLadderError",
    "build_external_fetch_shortlist",
    "canonicalize_external_url",
    "compile_safe_provider_request",
    "compile_external_source_ladder_successor_plan",
    "normalize_tencent_search_response",
    "source_family_allowed_hosts",
    "validate_external_source_ladder_plan",
    "validate_external_source_ladder_successor_spec",
]
