from __future__ import annotations

from typing import Any, Mapping


ROLE_EVIDENCE_SELECTOR_SCHEMA_VERSION = "finsight_role_evidence_selector_v0_1"
ROLE_SOURCE_LAYER_SELECTOR_SCHEMA_VERSION = "finsight_role_source_layer_selector_v0_1"
ROLE_SOURCE_LAYER_DISTRIBUTION_SCHEMA_VERSION = "finsight_role_source_layer_distribution_v0_1"

ROLE_POLICIES = {
    "fundamental_analyst": {
        "max_rows": 48,
        "preferred_terms": ("financial_statement", "income", "balance", "cash_flow", "fundamental_statement_pack", "derived_metric"),
        "required_source_families": ("primary_sec_filing",),
    },
    "product_technology_analyst": {
        "max_rows": 48,
        "preferred_terms": ("product", "sku", "model", "spec", "capacity", "generation", "company_product_evidence_graph"),
        "required_source_families": ("company_product_evidence_graph", "primary_sec_filing", "public_source_context", "live_public_web_context"),
    },
    "market_valuation_analyst": {
        "max_rows": 32,
        "preferred_terms": ("market", "valuation", "price", "volume", "event_window", "share"),
        "required_source_families": ("market_snapshot", "industry_snapshot", "relationship_graph"),
    },
    "industry_supply_chain_analyst": {
        "max_rows": 48,
        "preferred_terms": (
            "industry",
            "supply",
            "customer",
            "deployment",
            "order",
            "contract",
            "relationship",
            "readthrough",
            "company_product_evidence_graph",
        ),
        "required_source_families": (
            "industry_snapshot",
            "relationship_graph",
            "company_product_evidence_graph",
            "public_source_context",
            "live_public_web_context",
        ),
    },
    "capital_ownership_macro_analyst": {
        "max_rows": 40,
        "preferred_terms": ("debt", "credit", "offering", "13f", "ownership", "insider", "macro", "capital"),
        "required_source_families": ("primary_sec_filing", "public_source_context"),
    },
    "risk_counterevidence_analyst": {
        "max_rows": 32,
        "preferred_terms": ("risk", "litigation", "regulatory", "conflict", "unsupported", "counter"),
        "required_source_families": ("primary_sec_filing", "company_authored_unaudited_sec_filing", "public_source_context"),
    },
}

ROLE_SOURCE_LAYER_POLICIES = {
    "fundamental_analyst": {
        "specialist_slots": ("fundamental", "capital_macro"),
        "required_layers": ("L1", "L2"),
        "preferred_statuses": ("exact_authority_ready", "runtime_ready_context", "structured_not_promoted", "staging_parser_gate_pending"),
    },
    "product_technology_analyst": {
        "specialist_slots": ("product_technology",),
        "required_layers": ("L1", "L2", "L3"),
        "preferred_statuses": ("exact_authority_ready", "runtime_ready_context", "structured_not_promoted", "staging_parser_gate_pending"),
    },
    "industry_supply_chain_analyst": {
        "specialist_slots": ("industry_supply_chain",),
        "required_layers": ("L2", "L3"),
        "preferred_statuses": ("runtime_ready_context", "structured_not_promoted", "staging_parser_gate_pending"),
    },
    "market_valuation_analyst": {
        "specialist_slots": ("market_valuation", "industry_supply_chain"),
        "required_layers": ("L2", "L3"),
        "preferred_statuses": ("runtime_ready_context", "structured_not_promoted"),
    },
    "risk_counterevidence_analyst": {
        "specialist_slots": ("risk_counterevidence", "industry_supply_chain"),
        "required_layers": ("L1", "L2", "L3", "L4"),
        "preferred_statuses": ("runtime_ready_context", "structured_not_promoted", "staging_parser_gate_pending", "blocked_by_auth_or_policy"),
    },
    "capital_ownership_macro_analyst": {
        "specialist_slots": ("capital_macro", "fundamental"),
        "required_layers": ("L1", "L2", "L3"),
        "preferred_statuses": ("exact_authority_ready", "runtime_ready_context", "structured_not_promoted", "staging_parser_gate_pending"),
    },
}

SOURCE_LAYER_REPAIRABLE_STATUSES = {
    "exact_authority_ready",
    "runtime_ready_context",
    "structured_not_promoted",
    "staging_parser_gate_pending",
    "crawlable_not_parsed_or_not_routed",
}


def select_role_evidence(
    rows: list[Mapping[str, Any]],
    *,
    role: str,
    max_rows: int | None = None,
) -> dict[str, Any]:
    policy = ROLE_POLICIES.get(role, {"max_rows": 24, "preferred_terms": (), "required_source_families": ()})
    limit = int(max_rows or policy["max_rows"])
    scored = []
    dropped = []
    for index, row in enumerate(rows):
        score = _score_row(row, preferred_terms=policy["preferred_terms"], source_families=policy["required_source_families"])
        item = {"row": dict(row), "score": score, "input_index": index}
        if score <= 0:
            dropped.append({**item, "drop_reason": "role_policy_no_match"})
        else:
            scored.append(item)
    selected = sorted(scored, key=lambda item: (-int(item["score"]), int(item["input_index"])))[:limit]
    cap_hit = len(scored) > len(selected)
    return {
        "schema_version": ROLE_EVIDENCE_SELECTOR_SCHEMA_VERSION,
        "role": role,
        "input_count": len(rows),
        "selected_count": len(selected),
        "dropped_count": len(dropped) + max(0, len(scored) - len(selected)),
        "cap_hit": cap_hit,
        "cap_reason": "role_quota_limit" if cap_hit else "",
        "selected_rows": [item["row"] for item in selected],
        "dropped_taxonomy": _dropped_taxonomy(dropped, cap_hit=cap_hit, capped_count=max(0, len(scored) - len(selected))),
        "policy": {
            "max_rows": limit,
            "preferred_terms": list(policy["preferred_terms"]),
            "required_source_families": list(policy["required_source_families"]),
        },
    }


def select_role_source_layers(
    source_layer_capability: Mapping[str, Any] | None,
    *,
    role: str,
    max_rows: int | None = None,
) -> dict[str, Any]:
    policy = ROLE_SOURCE_LAYER_POLICIES.get(
        role,
        {"specialist_slots": (), "required_layers": ("L1", "L2", "L3"), "preferred_statuses": tuple(SOURCE_LAYER_REPAIRABLE_STATUSES)},
    )
    rows = [
        dict(row)
        for row in (source_layer_capability or {}).get("rows") or []
        if isinstance(row, Mapping)
    ]
    slots = {str(item) for item in policy.get("specialist_slots") or []}
    required_layers = [str(item) for item in policy.get("required_layers") or []]
    candidates = [
        row
        for row in rows
        if not slots or not {str(item) for item in row.get("specialist_slots") or []}.isdisjoint(slots)
    ]
    preferred_statuses = {str(item) for item in policy.get("preferred_statuses") or []}
    selected_candidates = [
        row
        for row in candidates
        if str(row.get("layer_id") or "") in set(required_layers)
        and (
            str(row.get("evidence_graph_status") or "") in preferred_statuses
            or bool(row.get("context_or_proxy_allowed"))
            or bool(row.get("exact_value_authority_ready"))
        )
    ]
    selected_candidates.sort(key=_source_layer_sort_key)
    limit = int(max_rows or 12)
    selected = selected_candidates[: max(1, limit)]
    by_layer = _count_rows_by_key(candidates, "layer_id")
    selected_by_layer = _count_rows_by_key(selected, "layer_id")
    by_status = _count_rows_by_key(candidates, "evidence_graph_status")
    selected_by_status = _count_rows_by_key(selected, "evidence_graph_status")
    missing_required_layers = [
        layer
        for layer in required_layers
        if not any(str(row.get("layer_id") or "") == layer for row in candidates)
    ]
    selected_missing_required_layers = [
        layer
        for layer in required_layers
        if not any(str(row.get("layer_id") or "") == layer for row in selected_candidates)
    ]
    exact_authority_violations = [
        str(row.get("source_id") or "")
        for row in candidates
        if str(row.get("layer_id") or "") in {"L2", "L3", "L4"}
        and (bool(row.get("exact_value_authority_ready")) or bool(row.get("can_support_company_exact_fact")))
    ]
    return {
        "schema_version": ROLE_SOURCE_LAYER_SELECTOR_SCHEMA_VERSION,
        "role": role,
        "input_count": len(rows),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "required_layers": required_layers,
        "specialist_slots": sorted(slots),
        "by_layer": by_layer,
        "selected_by_layer": selected_by_layer,
        "by_evidence_graph_status": by_status,
        "selected_by_evidence_graph_status": selected_by_status,
        "missing_required_layers": missing_required_layers,
        "selected_missing_required_layers": selected_missing_required_layers,
        "repairable_candidate_count": sum(
            1 for row in candidates if str(row.get("evidence_graph_status") or "") in SOURCE_LAYER_REPAIRABLE_STATUSES
        ),
        "not_registered_count": sum(1 for row in candidates if str(row.get("evidence_graph_status") or "") == "not_registered"),
        "exact_authority_violation_sources": exact_authority_violations,
        "coverage_status": "fail"
        if exact_authority_violations
        else "gap"
        if selected_missing_required_layers
        else "pass",
        "selected_sources": [_compact_source_layer_row(row) for row in selected],
        "selection_policy": "role_source_layer_required_slots_with_proxy_boundary_v0_1",
    }


def build_role_source_layer_distribution(
    source_layer_capability: Mapping[str, Any] | None,
    *,
    roles: list[str] | tuple[str, ...],
    max_rows_per_role: int | None = None,
) -> dict[str, Any]:
    role_rows = {
        role: select_role_source_layers(source_layer_capability or {}, role=role, max_rows=max_rows_per_role)
        for role in roles
    }
    failed_roles = [
        role
        for role, row in role_rows.items()
        if row.get("coverage_status") == "fail"
    ]
    gap_roles = [
        role
        for role, row in role_rows.items()
        if row.get("coverage_status") == "gap"
    ]
    return {
        "schema_version": ROLE_SOURCE_LAYER_DISTRIBUTION_SCHEMA_VERSION,
        "role_count": len(role_rows),
        "roles": role_rows,
        "failed_roles": failed_roles,
        "gap_roles": gap_roles,
        "status": "fail" if failed_roles else "gap" if gap_roles else "pass",
        "policy": "specialists_receive_auditable_l1_l2_l3_source_layer_distribution_without_proxy_exact_promotion_v0_1",
    }


def _score_row(row: Mapping[str, Any], *, preferred_terms: tuple[str, ...], source_families: tuple[str, ...]) -> int:
    haystack = " ".join(str(row.get(key) or "") for key in row.keys()).lower()
    source = str(row.get("source_family") or row.get("source_tier") or "").lower()
    score = 0
    if source in {item.lower() for item in source_families}:
        score += 3
    for term in preferred_terms:
        if term.lower() in haystack:
            score += 2
    if row.get("evidence_ref") or row.get("evidence_id"):
        score += 1
    if str(row.get("authority") or "").lower() in {"exact", "company_disclosed", "primary"}:
        score += 2
    return score


def _source_layer_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str]:
    status_rank = {
        "exact_authority_ready": 0,
        "runtime_ready_context": 1,
        "structured_not_promoted": 2,
        "staging_parser_gate_pending": 3,
        "crawlable_not_parsed_or_not_routed": 4,
        "missing_runtime_route": 5,
        "not_registered": 6,
        "blocked_by_auth_or_policy": 7,
    }.get(str(row.get("evidence_graph_status") or ""), 8)
    layer_rank = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}.get(str(row.get("layer_id") or ""), 4)
    return (status_rank, layer_rank, str(row.get("source_id") or ""))


def _compact_source_layer_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(row.get("source_id") or ""),
        "layer_id": str(row.get("layer_id") or ""),
        "evidence_graph_status": str(row.get("evidence_graph_status") or ""),
        "claim_scope": str(row.get("claim_scope") or ""),
        "context_or_proxy_allowed": bool(row.get("context_or_proxy_allowed")),
        "exact_value_authority_ready": bool(row.get("exact_value_authority_ready")),
        "memo_usage": str(row.get("memo_usage") or ""),
        "blocking_reason": str(row.get("blocking_reason") or ""),
        "next_action": str(row.get("next_action") or ""),
        "source_entity_role": str(row.get("source_entity_role") or ""),
        "issuer_binding_status": str(row.get("issuer_binding_status") or ""),
        "product_binding_status": str(row.get("product_binding_status") or ""),
        "counterparty_binding_status": str(row.get("counterparty_binding_status") or ""),
    }


def _count_rows_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _dropped_taxonomy(dropped: list[Mapping[str, Any]], *, cap_hit: bool, capped_count: int) -> dict[str, int]:
    taxonomy: dict[str, int] = {}
    for item in dropped:
        reason = str(item.get("drop_reason") or "unknown")
        taxonomy[reason] = taxonomy.get(reason, 0) + 1
    if cap_hit:
        taxonomy["role_quota_limit"] = taxonomy.get("role_quota_limit", 0) + capped_count
    return taxonomy
