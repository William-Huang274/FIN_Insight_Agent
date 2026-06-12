from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from sec_agent.kg_minimal_registry import load_kg_minimal_registry, validate_kg_minimal_registry
from sec_agent.project_inventory import SOURCE_FAMILY_AUTHORITY


SOURCE_CAPABILITY_ROUTER_SCHEMA_VERSION = "sec_agent_source_capability_router_v0.1"

ROUTE_SOURCE_FAMILY: dict[str, str] = {
    "ledger_first": "primary_sec_filing",
    "filing_text": "primary_sec_filing",
    "risk_text": "primary_sec_filing",
    "8k_commentary": "company_authored_unaudited_sec_filing",
    "milvus_semantic": "milvus_semantic",
    "market_snapshot": "market_snapshot",
    "industry_snapshot": "industry_snapshot",
    "relationship_graph": "relationship_graph",
    "live_public_web_context": "live_public_web_context",
    "run_artifact": "run_artifact",
}


def build_source_capability_router(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build an explicit D8 source capability decision layer for a graph run."""
    kg_registry = _kg_minimal_registry(state)
    kg_validation = validate_kg_minimal_registry(kg_registry)
    source_boundaries = _source_boundaries(kg_registry)
    policy_inputs = _source_policy_inputs(state)
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    retrieval_plan = state.get("retrieval_plan") if isinstance(state.get("retrieval_plan"), Mapping) else {}
    evidence_plan = state.get("evidence_requirement_plan") if isinstance(state.get("evidence_requirement_plan"), Mapping) else {}
    authority = inventory.get("source_family_authority") if isinstance(inventory.get("source_family_authority"), Mapping) else SOURCE_FAMILY_AUTHORITY
    availability = inventory.get("source_family_availability") if isinstance(inventory.get("source_family_availability"), Mapping) else {}
    available_families = set(_string_list(inventory.get("available_source_families") or inventory.get("source_families")))
    allowed_families = set(_string_list(activation.get("allowed_source_families")))

    routes = [dict(row) for row in retrieval_plan.get("routes") or [] if isinstance(row, Mapping)]
    requirements = [dict(row) for row in evidence_plan.get("requirements") or [] if isinstance(row, Mapping)]
    route_families = {ROUTE_SOURCE_FAMILY.get(str(route.get("retrieval_route") or ""), "") for route in routes}
    requested_families = set()
    for requirement in requirements:
        requested_families.update(_string_list(requirement.get("source_families")))
    family_set = sorted(set(authority) | set(source_boundaries) | available_families | allowed_families | route_families | requested_families)

    capabilities = [
        _source_capability(
            family,
            authority=authority,
            source_boundaries=source_boundaries,
            availability=availability,
            available_families=available_families,
            allowed_families=allowed_families,
        )
        for family in family_set
        if family
    ]
    capability_by_family = {row["source_family"]: row for row in capabilities}
    decisions = [
        _route_decision(
            route,
            capability_by_family=capability_by_family,
            allowed_families=allowed_families,
            policy_inputs=policy_inputs,
        )
        for route in routes
    ]
    payload = {
        "schema_version": SOURCE_CAPABILITY_ROUTER_SCHEMA_VERSION,
        "policy": "explicit_source_capability_router_no_weak_proxy_fallback_v0_2",
        "registry_schema_version": str(kg_registry.get("schema_version") or ""),
        "registry_validation_status": kg_validation.get("status") or "",
        "policy_inputs": policy_inputs,
        "capability_count": len(capabilities),
        "decision_count": len(decisions),
        "source_capabilities": capabilities,
        "route_decisions": decisions,
        "summary": {
            "by_decision_status": dict(sorted(Counter(row.get("decision_status") or "unknown" for row in decisions).items())),
            "by_source_family": dict(sorted(Counter(row.get("source_family") or "unknown" for row in decisions).items())),
            "exact_authority_source_families": sorted(
                row["source_family"] for row in capabilities if row.get("claim_authority") in {"exact_authority", "limited_exact_authority"}
            ),
            "context_only_source_families": sorted(row["source_family"] for row in capabilities if row.get("context_only")),
            "blocked_decision_count": len([row for row in decisions if row.get("decision_status") == "blocked"]),
            "gap_decision_count": len([row for row in decisions if row.get("decision_status") == "gap"]),
            "commercial_gap_decision_count": len([row for row in decisions if row.get("gap_type") == "commercial_gap"]),
            "registry_boundary_family_count": len(source_boundaries),
        },
    }
    payload["validation"] = validate_source_capability_router(payload)
    return payload


def validate_source_capability_router(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    capabilities = [row for row in payload.get("source_capabilities") or [] if isinstance(row, Mapping)]
    decisions = [row for row in payload.get("route_decisions") or [] if isinstance(row, Mapping)]
    seen_families: set[str] = set()
    for row in capabilities:
        family = str(row.get("source_family") or "").strip()
        if not family:
            errors.append({"type": "source_family_required"})
            continue
        if family in seen_families:
            errors.append({"type": "duplicate_source_family_capability", "source_family": family})
        seen_families.add(family)
        if row.get("context_only") is True and row.get("exact_value_authority") is True:
            errors.append({"type": "context_only_source_has_exact_value_authority", "source_family": family})
    for row in decisions:
        status = str(row.get("decision_status") or "").strip()
        if status not in {"allowed", "blocked", "gap"}:
            errors.append({"type": "invalid_source_capability_decision_status", "route_id": row.get("route_id"), "status": status})
        if status == "allowed" and row.get("available") is False:
            errors.append({"type": "allowed_decision_for_unavailable_source", "route_id": row.get("route_id")})
        if row.get("context_only") is True and row.get("claim_authority") == "exact_authority":
            errors.append({"type": "context_only_route_marked_exact_authority", "route_id": row.get("route_id")})
        if status in {"blocked", "gap"} and not str(row.get("gap_type") or "").strip():
            warnings.append({"type": "blocked_or_gap_decision_without_gap_type", "route_id": row.get("route_id")})
    return {
        "schema_version": "sec_agent_source_capability_router_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _source_capability(
    family: str,
    *,
    authority: Mapping[str, Any],
    source_boundaries: Mapping[str, Mapping[str, Any]],
    availability: Mapping[str, Any],
    available_families: set[str],
    allowed_families: set[str],
) -> dict[str, Any]:
    auth = authority.get(family) if isinstance(authority.get(family), Mapping) else {}
    boundary = source_boundaries.get(family) if isinstance(source_boundaries.get(family), Mapping) else {}
    avail = availability.get(family) if isinstance(availability.get(family), Mapping) else {}
    has_inventory = bool(availability or available_families)
    available = bool(avail.get("available")) if "available" in avail else (family in available_families if has_inventory else True)
    boundary_authority = str(boundary.get("authority") or "")
    exact = auth.get("exact_value_authority", False)
    if boundary_authority in {"exact_company_fact", "limited_exact_company_disclosed_product_fact"}:
        exact = exact if exact is not False else True
    if boundary_authority in {"context_only", "parser_gated_context_only", "commercial_deferred_gap"}:
        exact = False
    context_only = bool(auth.get("context_only")) or exact is False or boundary_authority in {"context_only", "parser_gated_context_only"}
    return {
        "source_family": family,
        "available": available,
        "status": str(avail.get("status") or ("available" if available else "unavailable")),
        "allowed_by_activation": family in allowed_families if allowed_families else True,
        "authority_tier": str(auth.get("authority_tier") or "unknown"),
        "exact_value_authority": exact,
        "context_only": context_only,
        "claim_authority": _claim_authority(exact=exact, context_only=context_only),
        "allowed_claim_scope": str(auth.get("allowed_claim_scope") or ",".join(_string_list(boundary.get("allowed_claims")))),
        "boundary_authority": boundary_authority,
        "boundary_allowed_claims": _string_list(boundary.get("allowed_claims")),
        "boundary_forbidden_claims": _string_list(boundary.get("forbidden_claims")),
        "required_gates": _string_list(boundary.get("required_gates")),
        "gap_policy": str(boundary.get("gap_policy") or _gap_policy_for_family(family, available=available, allowed_by_activation=family in allowed_families if allowed_families else True)),
    }


def _route_decision(
    route: Mapping[str, Any],
    *,
    capability_by_family: Mapping[str, Mapping[str, Any]],
    allowed_families: set[str],
    policy_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    route_name = str(route.get("retrieval_route") or "").strip()
    family = ROUTE_SOURCE_FAMILY.get(route_name) or str(route.get("source_family") or "").strip()
    capability = capability_by_family.get(family) if isinstance(capability_by_family.get(family), Mapping) else {}
    allowed_by_activation = bool(capability.get("allowed_by_activation", True))
    available = bool(capability.get("available", True))
    required_authority = str(route.get("required_authority") or policy_inputs.get("required_authority") or "").strip()
    claim_type = str(route.get("claim_type") or policy_inputs.get("claim_type") or "").strip()
    metric_type = str(route.get("metric_type") or policy_inputs.get("metric_type") or "").strip()
    boundary_authority = str(capability.get("boundary_authority") or "")
    if allowed_families and family not in allowed_families:
        status = "blocked"
        gap_type = "source_boundary_blocked"
        reason = "source_family_not_allowed_by_activation"
    elif boundary_authority == "commercial_deferred_gap" or capability.get("gap_policy") == "expose_commercial_gap_do_not_proxy":
        status = "gap"
        gap_type = "commercial_gap"
        reason = "commercial_tracker_deferred_under_no_commercial_policy"
    elif not available:
        status = "gap"
        gap_type = "coverage_gap"
        reason = "source_family_unavailable"
    elif _requires_exact_authority(required_authority=required_authority, claim_type=claim_type, metric_type=metric_type) and capability.get("context_only"):
        status = "blocked"
        gap_type = "source_boundary_blocked"
        reason = "context_only_source_cannot_satisfy_exact_company_fact_authority"
    else:
        status = "allowed"
        gap_type = ""
        reason = "source_family_allowed"
    return {
        "route_id": str(route.get("route_id") or ""),
        "task_id": str(route.get("task_id") or ""),
        "evidence_requirement_id": str(route.get("evidence_requirement_id") or ""),
        "retrieval_route": route_name,
        "source_family": family,
        "decision_status": status,
        "reason": reason,
        "gap_type": gap_type,
        "available": available,
        "allowed_by_activation": allowed_by_activation,
        "authority_tier": str(capability.get("authority_tier") or "unknown"),
        "exact_value_authority": capability.get("exact_value_authority", False),
        "context_only": bool(capability.get("context_only")),
        "claim_authority": str(capability.get("claim_authority") or "context_only"),
        "allowed_claim_scope": str(capability.get("allowed_claim_scope") or ""),
        "boundary_authority": boundary_authority,
        "boundary_allowed_claims": list(capability.get("boundary_allowed_claims") or []),
        "boundary_forbidden_claims": list(capability.get("boundary_forbidden_claims") or []),
        "required_gates": list(capability.get("required_gates") or []),
        "query_intent": str(policy_inputs.get("query_intent") or ""),
        "industry_schema": str(policy_inputs.get("industry_schema") or ""),
        "metric_type": metric_type,
        "claim_type": claim_type,
        "required_authority": required_authority,
        "route_cost_tier": str(route.get("route_cost_tier") or ""),
    }


def _kg_minimal_registry(state: Mapping[str, Any]) -> dict[str, Any]:
    registry = state.get("kg_minimal_registry")
    if isinstance(registry, Mapping):
        return dict(registry)
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    registry = inventory.get("kg_minimal_registry") if isinstance(inventory.get("kg_minimal_registry"), Mapping) else {}
    if registry:
        return dict(registry)
    path = state.get("kg_minimal_registry_path") or inventory.get("kg_minimal_registry_path")
    return load_kg_minimal_registry(path if str(path or "").strip() else None)


def _source_boundaries(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    k3 = registry.get("k3_source_policy_minimal") if isinstance(registry.get("k3_source_policy_minimal"), Mapping) else {}
    boundaries = k3.get("source_family_claim_boundaries") if isinstance(k3.get("source_family_claim_boundaries"), Mapping) else {}
    return {str(family): dict(policy) for family, policy in boundaries.items() if isinstance(policy, Mapping)}


def _source_policy_inputs(state: Mapping[str, Any]) -> dict[str, Any]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    metadata = activation.get("metadata") if isinstance(activation.get("metadata"), Mapping) else {}
    metric_families = _string_list(contract.get("metric_families") or contract.get("metrics"))
    return {
        "query_intent": str(contract.get("intent") or contract.get("task_type") or activation.get("execution_mode") or ""),
        "industry_schema": str(contract.get("industry_schema") or metadata.get("industry_schema") or ""),
        "metric_type": str(contract.get("metric_type") or _infer_metric_type(metric_families)),
        "claim_type": str(contract.get("claim_type") or ""),
        "required_authority": str(contract.get("required_authority") or ""),
        "metric_families": metric_families,
    }


def _infer_metric_type(metric_families: list[str]) -> str:
    joined = " ".join(metric_families).lower()
    if any(token in joined for token in ("shipment", "delivery", "subscriber", "asp", "arpu", "product", "unit", "production", "capacity")):
        return "product_kpi"
    if any(token in joined for token in ("revenue", "margin", "cash", "capex", "debt", "inventory", "income")):
        return "financial_metric"
    return ""


def _requires_exact_authority(*, required_authority: str, claim_type: str, metric_type: str) -> bool:
    text = " ".join([required_authority, claim_type]).lower()
    return any(
        token in text
        for token in (
            "exact",
            "company_fact",
            "reported_financial_fact",
            "company_disclosed_product_kpi",
        )
    )


def _claim_authority(*, exact: Any, context_only: bool) -> str:
    if exact is True:
        return "exact_authority"
    if exact and exact is not False:
        return "limited_exact_authority"
    if context_only:
        return "context_only"
    return "no_claim_authority"


def _gap_policy_for_family(family: str, *, available: bool, allowed_by_activation: bool) -> str:
    if not allowed_by_activation:
        return "block_source_boundary"
    if not available:
        return "expose_coverage_gap"
    if family in {"public_source_context", "live_public_web_context", "milvus_semantic", "market_snapshot", "industry_snapshot", "relationship_graph"}:
        return "context_only_do_not_promote_to_company_fact"
    return "route_allowed_subject_to_downstream_gates"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]
